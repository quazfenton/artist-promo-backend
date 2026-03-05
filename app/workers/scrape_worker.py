#!/usr/bin/env python3
"""
Scrape Worker - Consumes scrape jobs from queue and processes them

This worker:
1. Dequeues scrape jobs from Redis queue
2. Executes the appropriate scraper
3. Creates ScraperRawSignal records for pipeline processing
4. Enqueues normalization jobs
5. Tracks job completion/failure

Usage:
    python -m app.workers.scrape_worker
"""
import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Type
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, enqueue_job
from app.models.database import SessionLocal
from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
from app.scrapers.youtube_scraper import YouTubeChannelScraper
from app.scrapers.instagram_scraper import InstagramScraper
from app.scrapers.web_scraper import WebContactScraper

# Configure logging
logger.add(
    "logs/scrape_worker_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO"
)

# Map job types to scraper classes
SCRAPER_MAP: Dict[str, Type] = {
    "spotify_playlist": SpotifyPlaylistScraper,
    "youtube_channel": YouTubeChannelScraper,
    "instagram_profile": InstagramScraper,
    "web_contact": WebContactScraper,
}


async def process_scrape_job(job: dict) -> dict:
    """
    Process a single scrape job
    
    Args:
        job: Job dictionary from queue
        
    Returns:
        dict with job results
        
    Raises:
        Exception: If job processing fails
    """
    job_id = job["job_id"]
    job_type = job["type"]
    params = job.get("params", {})
    
    logger.info(f"Processing scrape job {job_id}: {job_type} with params {params}")
    
    try:
        # Get scraper class from map
        scraper_class = SCRAPER_MAP.get(job_type)
        if not scraper_class:
            raise ValueError(f"Unknown scraper type: {job_type}")
        
        # Initialize scraper
        scraper = scraper_class()
        
        # Run scraper (sync method, may take time)
        logger.info(f"Running scraper for {job_type}")
        results = scraper.scrape(**params)
        
        if not results:
            logger.warning(f"Scraper {job_type} returned no results")
            results = []
        
        logger.info(f"Scraper completed with {len(results)} results")
        
        # Create raw signal for pipeline processing
        db = SessionLocal()
        raw_signal_id = None
        
        try:
            from app.models.staging import ScraperRawSignal
            
            # Create raw signal record
            raw_signal = ScraperRawSignal(
                job_id=job_id,
                source_platform=job_type.split("_")[0],  # e.g., "spotify" from "spotify_playlist"
                payload={"results": results, "params": params},
                dedupe_key=f"{job_type}:{job_id}:{datetime.utcnow().isoformat()}",
                signal_status="new",
                record_count=len(results)
            )
            
            db.add(raw_signal)
            db.commit()
            db.refresh(raw_signal)
            raw_signal_id = raw_signal.id
            
            logger.info(f"Created raw signal {raw_signal_id} for job {job_id}")
            
            # Enqueue normalization job to process the raw signal
            enqueue_job(
                job_type="normalize:signals",
                params={"raw_signal_id": raw_signal_id},
                priority=job.get("priority", 5),
                max_retries=3
            )
            
            logger.info(f"Enqueued normalization job for raw signal {raw_signal_id}")
            
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error creating raw signal: {db_error}", exc_info=True)
            raise
        finally:
            db.close()
        
        return {
            "success": True,
            "raw_signal_id": raw_signal_id,
            "result_count": len(results),
            "job_type": job_type
        }
        
    except Exception as e:
        logger.error(f"Scrape job {job_id} failed: {str(e)}", exc_info=True)
        raise


async def worker_loop():
    """
    Main worker loop - continuously consume jobs from queue
    
    This loop:
    1. Dequeues jobs from the scrape queue
    2. Processes each job
    3. Marks job as complete or failed
    4. Waits before polling again if no jobs
    """
    logger.info("=" * 60)
    logger.info("Starting Scrape Worker")
    logger.info(f"Queue: queue:scrape")
    logger.info(f"Polling interval: 5 seconds")
    logger.info("=" * 60)
    
    jobs_processed = 0
    jobs_failed = 0
    
    while True:
        try:
            # Dequeue job from scrape queue
            job = dequeue_job("queue:scrape")
            
            if job:
                logger.info(f"Dequeued job: {job['job_id']} (type: {job['type']})")
                
                try:
                    # Process the job
                    result = await process_scrape_job(job)
                    
                    # Mark job as complete
                    complete_job(job["job_id"], result)
                    
                    jobs_processed += 1
                    logger.info(f"✓ Completed job {job['job_id']} - {result.get('result_count', 0)} results")
                    
                except Exception as e:
                    # Mark job as failed
                    error_message = str(e)
                    fail_job(job["job_id"], error_message)
                    
                    jobs_failed += 1
                    logger.error(f"✗ Job {job['job_id']} failed: {error_message}")
            else:
                # No jobs available, wait before polling again
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled, shutting down...")
            break
        except Exception as e:
            # Unexpected error in worker loop
            logger.error(f"Worker loop error: {str(e)}", exc_info=True)
            await asyncio.sleep(10)  # Wait before retrying
        
        # Log stats every 10 jobs
        if jobs_processed > 0 and jobs_processed % 10 == 0:
            logger.info(f"Worker stats: {jobs_processed} completed, {jobs_failed} failed")


def main():
    """Entry point for scrape worker"""
    logger.info("Scrape Worker starting...")
    
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
