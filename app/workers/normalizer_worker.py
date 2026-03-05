"""
Signal Normalizer Worker - Converts raw signals to normalized staging contacts

This worker consumes normalization jobs from the Redis queue,
reads raw signal data, normalizes it into standardized contact format,
creates staging contact records, and triggers entity resolution.

Usage:
    python -m app.workers.normalizer_worker

Environment Variables:
    DATABASE_URL: Database connection string
    REDIS_URL: Redis connection URL
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workers.queue_adapter import (
    dequeue_job,
    complete_job,
    fail_job,
    enqueue_job,
    push_to_dead_letter
)
from app.models.staging import ScraperRawSignal, StagingContact
from app.models.database import SessionLocal, engine, Base
from app.utils.pipeline_orchestrator import SignalNormalizer
from loguru import logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logger.bind(service="normalizer-worker")

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)


async def normalize_signals(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw signals into staging contacts
    
    Args:
        job: Job payload with raw_signal_id
        
    Returns:
        Result dict with staging contact IDs
        
    Raises:
        ValueError: If raw signal not found
        Exception: If normalization fails
    """
    raw_signal_id = job["params"]["raw_signal_id"]
    job_id = job["job_id"]
    
    log.info(f"Normalizing raw signal {raw_signal_id} for job {job_id}")
    
    db = SessionLocal()
    try:
        # Fetch raw signal
        raw_signal = db.query(ScraperRawSignal).filter(
            ScraperRawSignal.id == raw_signal_id
        ).first()
        
        if not raw_signal:
            raise ValueError(f"Raw signal {raw_signal_id} not found")
        
        log.info(
            f"Processing raw signal {raw_signal_id}",
            extra={
                "source_platform": raw_signal.source_platform,
                "job_id": raw_signal.job_id,
                "payload_size": len(json.dumps(raw_signal.payload)) if raw_signal.payload else 0
            }
        )
        
        # Normalize using SignalNormalizer
        normalizer = SignalNormalizer()
        staging_contacts = normalizer.normalize_raw_signal(raw_signal)
        
        if not staging_contacts:
            log.warning(f"No staging contacts created from raw signal {raw_signal_id}")
            return {
                "raw_signal_id": raw_signal_id,
                "staging_contact_ids": [],
                "contacts_created": 0,
                "warning": "No contacts extracted"
            }
        
        # Save staging contacts to database
        staging_ids = []
        for staging_contact in staging_contacts:
            db.add(staging_contact)
            db.flush()
            staging_ids.append(staging_contact.id)

        db.commit()
        
        log.info(
            f"Normalized raw signal {raw_signal_id} into {len(staging_contacts)} staging contacts",
            extra={
                "staging_ids": staging_ids,
                "contact_types": [sc.contact_type for sc in staging_contacts],
                "emails_found": [sc.email for sc in staging_contacts if sc.email]
            }
        )
        
        # Enqueue next stage: entity resolution
        if staging_contacts:
            enqueue_job(
                job_type="resolve:entities",
                params={"staging_contact_ids": staging_ids},
                source="worker",
                priority=job.get("priority", 5),
                dedupe_key=f"resolve:{','.join(map(str, staging_ids))}"
            )
            log.info(f"Enqueued entity resolution for {len(staging_contacts)} contacts")
        
        return {
            "raw_signal_id": raw_signal_id,
            "staging_contact_ids": staging_ids,
            "contacts_created": len(staging_contacts),
            "platform": raw_signal.source_platform
        }
        
    except Exception as e:
        db.rollback()
        log.error(f"Normalization failed for raw signal {raw_signal_id}: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


async def worker_loop():
    """
    Main worker loop - continuously processes normalization jobs
    
    This loop:
    1. Polls Redis queue for normalization jobs
    2. Fetches raw signal data
    3. Normalizes to staging contacts
    4. Creates staging contact records
    5. Triggers entity resolution stage
    6. Tracks job completion/failure
    """
    log.info("Starting normalizer worker loop...")
    log.info("Listening on queue: queue:normalize")
    log.info(f"Database URL: {os.getenv('DATABASE_URL', 'not set')}")
    log.info(f"Redis URL: {os.getenv('REDIS_URL', 'not set')}")
    
    while True:
        job = None
        try:
            # Dequeue job (blocking with timeout)
            job = dequeue_job("queue:normalize", timeout=5)
            
            if not job:
                # No jobs available, wait before polling again
                await asyncio.sleep(1)
                continue
            
            log.info(
                f"Processing normalization job {job['job_id']}",
                extra={
                    "job_id": job["job_id"],
                    "job_type": job["type"],
                    "source": job.get("source", "unknown")
                }
            )
            
            # Execute normalization
            result = await normalize_signals(job)
            
            # Mark job as completed
            complete_job(job["job_id"], result)
            
            log.info(
                f"Job {job['job_id']} completed: {result}",
                extra={
                    "contacts_created": result.get("contacts_created", 0),
                    "staging_count": len(result.get("staging_contact_ids", []))
                }
            )
            
        except asyncio.CancelledError:
            log.warning("Normalizer worker received shutdown signal, stopping...")
            break
            
        except Exception as e:
            log.error(
                f"Job {job.get('job_id', 'unknown') if job else 'unknown'} failed: {str(e)}",
                exc_info=True
            )
            
            if job:
                # Mark job as failed
                fail_job(job["job_id"], str(e))
                
                # Push to dead letter queue after 3 failures
                failure_count = job.get("params", {}).get("_failure_count", 0) + 1
                if failure_count >= 3:
                    push_to_dead_letter(job, str(e))
                    log.error(f"Job {job['job_id']} moved to dead letter queue after {failure_count} failures")
                else:
                    # Re-enqueue with failure count for retry
                    log.warning(f"Re-enqueueing job {job['job_id']} for retry (attempt {failure_count})")
                    retry_params = dict(job.get("params", {}))
                    retry_params["_failure_count"] = failure_count
                    enqueue_job(
                        job_type=job["type"],
                        params=retry_params,
                        source=job.get("source", "worker"),
                        priority=job.get("priority", 5),
                        dedupe_key=job.get("dedupe_key")
                    )


if __name__ == "__main__":
    try:
        log.info("="*60)
        log.info("NORMALIZER WORKER STARTING")
        log.info("="*60)
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        log.info("Worker stopped by user")
    except Exception as e:
        log.error(f"Worker crashed: {str(e)}", exc_info=True)
        sys.exit(1)
