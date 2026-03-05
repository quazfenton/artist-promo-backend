#!/usr/bin/env python3
"""
Signal Normalizer Worker - Consumes normalization jobs from queue

This worker:
1. Dequeues normalization jobs from Redis queue
2. Processes raw signals into normalized staging contacts
3. Applies email canonicalization
4. Creates StagingContact records
5. Enqueues entity resolution jobs

Usage:
    python -m app.workers.signal_normalizer_worker
"""
import asyncio
import os
import sys
from datetime import datetime
from typing import List, Dict
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, enqueue_job
from app.models.database import SessionLocal
from app.utils.email_canonicalization import canonicalize_email

# Configure logging
logger.add(
    "logs/normalizer_worker_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO"
)


def normalize_contact_data(raw_data: dict) -> dict:
    """
    Normalize raw contact data
    
    Args:
        raw_data: Raw contact data from scraper
        
    Returns:
        Normalized contact data
    """
    normalized = {}
    
    # Extract and normalize email
    if 'email' in raw_data:
        normalized['email'] = canonicalize_email(raw_data['email'])
    
    # Extract name
    normalized['name'] = raw_data.get('name', raw_data.get('owner', ''))
    
    # Extract contact type
    normalized['contact_type'] = raw_data.get('contact_type', 'playlist_curator')
    
    # Extract social handles
    normalized['social_handles'] = {
        'instagram': raw_data.get('instagram'),
        'twitter': raw_data.get('twitter'),
        'youtube': raw_data.get('youtube')
    }
    
    # Extract follower count
    normalized['follower_count'] = raw_data.get('followers', raw_data.get('follower_count', 0))
    
    # Extract bio
    normalized['bio'] = raw_data.get('bio', raw_data.get('description', ''))
    
    # Extract source URL
    normalized['source_url'] = raw_data.get('url', raw_data.get('source_url', ''))
    
    return normalized


async def process_normalization_job(job: dict) -> dict:
    """
    Process a single normalization job
    
    Args:
        job: Job dictionary from queue
        
    Returns:
        dict with normalization results
    """
    job_id = job["job_id"]
    raw_signal_id = job["params"].get("raw_signal_id")
    
    logger.info(f"Processing normalization job {job_id} for raw signal {raw_signal_id}")
    
    try:
        db = SessionLocal()
        
        try:
            # Get raw signal
            from app.models.staging import ScraperRawSignal, StagingContact
            
            raw_signal = db.query(ScraperRawSignal).filter(
                ScraperRawSignal.id == raw_signal_id
            ).first()
            
            if not raw_signal:
                raise ValueError(f"Raw signal {raw_signal_id} not found")
            
            # Process raw signal payload
            payload = raw_signal.payload or {}
            results = payload.get('results', [])
            
            if not results:
                logger.warning(f"Raw signal {raw_signal_id} has no results")
                results = [payload]
            
            # Normalize each result
            normalized_count = 0
            for result in results:
                try:
                    normalized = normalize_contact_data(result)
                    
                    if not normalized.get('email') and not normalized.get('name'):
                        continue  # Skip if no identifying information
                    
                    # Create staging contact
                    staging_contact = StagingContact(
                        raw_signal_id=raw_signal_id,
                        name=normalized.get('name'),
                        email=normalized.get('email'),
                        contact_type=normalized.get('contact_type'),
                        social_handles=normalized.get('social_handles'),
                        confidence_score=calculate_confidence_score(normalized, raw_signal.source_platform),
                        platform_ids={raw_signal.source_platform: result.get('id')},
                        follower_count=normalized.get('follower_count', 0),
                        bio=normalized.get('bio'),
                        source_url=normalized.get('source_url'),
                        provenance={
                            'job_id': job_id,
                            'raw_signal_id': raw_signal_id,
                            'source_platform': raw_signal.source_platform,
                            'normalized_at': datetime.utcnow().isoformat()
                        }
                    )
                    
                    db.add(staging_contact)
                    normalized_count += 1
                    
                except Exception as e:
                    logger.error(f"Error normalizing result: {e}")
                    continue
            
            db.commit()
            
            logger.info(f"Normalized {normalized_count} contacts from raw signal {raw_signal_id}")
            
            # Update raw signal status
            raw_signal.signal_status = "normalized"
            db.commit()
            
            # Enqueue entity resolution job if we have normalized contacts
            if normalized_count > 0:
                enqueue_job(
                    job_type="resolve:entities",
                    params={"raw_signal_id": raw_signal_id},
                    priority=job.get("priority", 5),
                    max_retries=3
                )
                logger.info(f"Enqueued entity resolution job for raw signal {raw_signal_id}")
            
            return {
                "success": True,
                "normalized_count": normalized_count,
                "raw_signal_id": raw_signal_id
            }
            
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error in normalization: {db_error}", exc_info=True)
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Normalization job {job_id} failed: {str(e)}", exc_info=True)
        raise


def calculate_confidence_score(normalized: dict, platform: str) -> int:
    """
    Calculate confidence score for normalized contact
    
    Args:
        normalized: Normalized contact data
        platform: Source platform
        
    Returns:
        Confidence score (0-100)
    """
    score = 50  # Base score
    
    # Email adds confidence
    if normalized.get('email'):
        score += 20
    
    # Name adds confidence
    if normalized.get('name'):
        score += 15
    
    # High follower count adds confidence
    if normalized.get('follower_count', 0) > 10000:
        score += 10
    elif normalized.get('follower_count', 0) > 1000:
        score += 5
    
    # Bio adds confidence
    if normalized.get('bio'):
        score += 5
    
    # Platform-specific bonuses
    platform_bonuses = {
        'spotify': 5,
        'instagram': 5,
        'youtube': 5,
        'official_site': 10
    }
    score += platform_bonuses.get(platform, 0)
    
    return min(100, max(0, score))


async def worker_loop():
    """Main worker loop - consume normalization jobs from queue"""
    logger.info("=" * 60)
    logger.info("Starting Signal Normalizer Worker")
    logger.info(f"Queue: queue:normalize")
    logger.info(f"Polling interval: 5 seconds")
    logger.info("=" * 60)
    
    jobs_processed = 0
    jobs_failed = 0
    
    while True:
        try:
            # Dequeue job from normalize queue
            job = dequeue_job("queue:normalize")
            
            if job:
                logger.info(f"Dequeued normalization job: {job['job_id']}")
                
                try:
                    # Process the job
                    result = await process_normalization_job(job)
                    
                    # Mark job as complete
                    complete_job(job["job_id"], result)
                    
                    jobs_processed += 1
                    logger.info(f"✓ Completed normalization job {job['job_id']} - {result.get('normalized_count', 0)} contacts")
                    
                except Exception as e:
                    # Mark job as failed
                    error_message = str(e)
                    fail_job(job["job_id"], error_message)
                    
                    jobs_failed += 1
                    logger.error(f"✗ Normalization job {job['job_id']} failed: {error_message}")
            else:
                # No jobs available, wait before polling again
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled, shutting down...")
            break
        except Exception as e:
            # Unexpected error in worker loop
            logger.error(f"Worker loop error: {str(e)}", exc_info=True)
            await asyncio.sleep(10)
        
        # Log stats every 10 jobs
        if jobs_processed > 0 and jobs_processed % 10 == 0:
            logger.info(f"Worker stats: {jobs_processed} completed, {jobs_failed} failed")


def main():
    """Entry point for signal normalizer worker"""
    logger.info("Signal Normalizer Worker starting...")
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    try:
        # Run the worker loop
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker crashed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
