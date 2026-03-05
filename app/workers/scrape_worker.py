"""
Scrape Worker - Consumes scraping jobs from Redis queue

This worker continuously polls the Redis queue for scraping jobs,
executes the appropriate scraper, creates raw signal records,
and triggers the next pipeline stage (normalization).

Usage:
    python -m app.workers.scrape_worker

Environment Variables:
    DATABASE_URL: Database connection string
    REDIS_URL: Redis connection URL
    SPOTIFY_CLIENT_ID: Spotify API client ID
    SPOTIFY_CLIENT_SECRET: Spotify API client secret
    YOUTUBE_API_KEY: YouTube API key
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
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
from app.models.staging import ScraperRawSignal
from app.models.database import SessionLocal, engine, Base
from loguru import logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logger.bind(service="scrape-worker")

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Scraper registry - lazy loaded to avoid circular imports
SCRAPER_MAP = {
    "spotify": None,
    "youtube": None,
    "instagram": None,
    "web": None,
}


def get_scraper(platform: str):
    """
    Lazy loader for scrapers to avoid circular imports
    
    Args:
        platform: Platform name (spotify, youtube, instagram, web)
        
    Returns:
        Scraper class for the platform
    """
    if platform == "spotify":
        from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
        return SpotifyPlaylistScraper
    elif platform == "youtube":
        from app.scrapers.youtube_scraper import YouTubeChannelScraper
        return YouTubeChannelScraper
    elif platform == "instagram":
        from app.scrapers.instagram_scraper import InstagramScraper
        return InstagramScraper
    elif platform == "web":
        from app.scrapers.web_scraper import WebContactScraper
        return WebContactScraper
    else:
        raise ValueError(f"Unknown platform: {platform}")


async def execute_scraper(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute scraper based on job type and create raw signal
    
    Args:
        job: Job payload from queue
        
    Returns:
        Result dict with raw_signal_id and stats
        
    Raises:
        ValueError: If job type is invalid or scraper not found
        Exception: If scraper execution fails
    """
    job_type = job["type"]  # e.g., "scrape:spotify_playlist"
    job_id = job["job_id"]
    params = job.get("params", {})
    dedupe_key = job.get("dedupe_key")
    
    log.info(f"Executing job {job_id} of type {job_type}")
    
    if not job_type.startswith("scrape:"):
        raise ValueError(f"Invalid job type: {job_type}")
    
    # Extract platform from job type
    # Format: "scrape:spotify_playlist" -> "spotify"
    platform = job_type.split(":")[1].split("_")[0]
    
    # Get scraper class
    try:
        scraper_cls = get_scraper(platform)
    except ValueError as e:
        log.error(f"Unknown platform {platform}: {str(e)}")
        raise
    
    scraper = scraper_cls()
    
    try:
        # Execute scraper (most scrapers are sync, wrap in async)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, 
            lambda: scraper.scrape(**params)
        )
        
        # Handle None results
        if results is None:
            results = []
        
        # Get scraper stats
        stats = scraper.get_stats() if hasattr(scraper, 'get_stats') else {}
        
        # Create raw signal record
        db = SessionLocal()
        try:
            raw_signal = ScraperRawSignal(
                job_id=job_id,
                source_platform=platform,
                payload={
                    "results": results,
                    "stats": stats,
                    "scraped_at": datetime.utcnow().isoformat()
                },
                dedupe_key=dedupe_key or f"{platform}:{job_id}"
            )
            db.add(raw_signal)
            db.commit()
            db.refresh(raw_signal)
            
            log.info(
                f"Created raw signal {raw_signal.id} for job {job_id}",
                extra={
                    "raw_signal_id": raw_signal.id, 
                    "items_found": len(results),
                    "platform": platform
                }
            )
            
            # Enqueue next pipeline stage: normalization
            enqueue_job(
                job_type="normalize:signals",
                params={"raw_signal_id": raw_signal.id},
                source="worker",
                priority=job.get("priority", 5),
                dedupe_key=f"normalize:{raw_signal.id}"
            )
            
            return {
                "raw_signal_id": raw_signal.id,
                "items_found": len(results),
                "platform": platform,
                "stats": stats
            }
            
        finally:
            db.close()
            
    except Exception as e:
        log.error(f"Scraper execution failed for job {job_id}: {str(e)}", exc_info=True)
        raise


async def worker_loop():
    """
    Main worker loop - continuously processes jobs from queue
    
    This loop:
    1. Polls Redis queue for new jobs
    2. Executes the appropriate scraper
    3. Creates raw signal records
    4. Triggers next pipeline stage
    5. Tracks job completion/failure
    """
    log.info("Starting scrape worker loop...")
    log.info("Listening on queue: queue:scrape")
    log.info(f"Database URL: {os.getenv('DATABASE_URL', 'not set')}")
    log.info(f"Redis URL: {os.getenv('REDIS_URL', 'not set')}")
    
    while True:
        job = None
        try:
            # Dequeue job (blocking with timeout)
            job = dequeue_job("queue:scrape", timeout=5)
            
            if not job:
                # No jobs available, wait before polling again
                await asyncio.sleep(1)
                continue
            
            log.info(
                f"Processing job {job['job_id']}",
                extra={
                    "job_id": job["job_id"],
                    "job_type": job["type"],
                    "source": job.get("source", "unknown"),
                    "priority": job.get("priority", 5)
                }
            )
            
            # Execute scraper
            result = await execute_scraper(job)
            
            # Mark job as completed
            complete_job(job["job_id"], result)
            
            log.info(
                f"Job {job['job_id']} completed successfully",
                extra={
                    "result": result,
                    "processing_time": "N/A"  # Could add timing
                }
            )
            
        except asyncio.CancelledError:
            log.warning("Worker received shutdown signal, stopping...")
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
        log.info("SCRAPE WORKER STARTING")
        log.info("="*60)
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        log.info("Worker stopped by user")
    except Exception as e:
        log.error(f"Worker crashed: {str(e)}", exc_info=True)
        sys.exit(1)
