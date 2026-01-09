"""
Scrape Worker - processes scraping jobs from the queue
"""
import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, Optional
import logging
from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, push_to_dead_letter, fingerprint, seen_before, mark_seen
from app.models.staging import ScraperRawSignal
from app.models.database import SessionLocal, Contact
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import os

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)

class ScrapeWorker:
    def __init__(self):
        self.session = None
        self.running = True

    async def initialize_session(self):
        """Initialize HTTP session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single scraping job"""
        job_type = job["type"]  # e.g., "scrape:spotify_playlist"
        
        if job_type.startswith("scrape:"):
            platform = job_type.split(":")[1].split("_")[0]  # e.g., "spotify"
            
            # Import the appropriate scraper
            if platform == "spotify":
                from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
                scraper_cls = SpotifyPlaylistScraper
            elif platform == "youtube":
                from app.scrapers.youtube_scraper import YouTubeChannelScraper
                scraper_cls = YouTubeChannelScraper
            elif platform == "instagram":
                from app.scrapers.instagram_scraper import InstagramScraper
                scraper_cls = InstagramScraper
            elif platform == "web":
                from app.scrapers.web_scraper import WebContactScraper
                scraper_cls = WebContactScraper
            else:
                raise ValueError(f"Unknown scraper platform: {platform}")
            
            # Create scraper instance
            scraper = scraper_cls()
            
            # Run the scrape with the provided parameters
            params = job.get("params", {})
            
            # Different scrapers expect different parameters
            # Check if the scraper method is async
            import inspect
            if platform == "spotify":
                if inspect.iscoroutinefunction(scraper.safe_scrape):
                    results = await scraper.safe_scrape(
                        genre=params.get("genre", "hip-hop"),
                        min_followers=params.get("min_followers", 500),
                        limit=params.get("limit", 50)
                    )
                else:
                    results = scraper.safe_scrape(
                        genre=params.get("genre", "hip-hop"),
                        min_followers=params.get("min_followers", 500),
                        limit=params.get("limit", 50)
                    )
            elif platform == "youtube":
                if inspect.iscoroutinefunction(scraper.safe_scrape):
                    results = await scraper.safe_scrape(
                        query=params.get("query", "hip hop playlist"),
                        max_results=params.get("max_results", 50)
                    )
                else:
                    results = scraper.safe_scrape(
                        query=params.get("query", "hip hop playlist"),
                        max_results=params.get("max_results", 50)
                    )
            elif platform == "instagram":
                if params.get("username"):
                    if inspect.iscoroutinefunction(scraper.safe_scrape):
                        results = [await scraper.safe_scrape(username=params["username"])]
                    else:
                        results = [scraper.safe_scrape(username=params["username"])]
                else:
                    if inspect.iscoroutinefunction(scraper.safe_scrape):
                        results = await scraper.safe_scrape(hashtag=params.get("hashtag"))
                    else:
                        results = scraper.safe_scrape(hashtag=params.get("hashtag"))
            elif platform == "web":
                if inspect.iscoroutinefunction(scraper.safe_scrape):
                    results = await scraper.safe_scrape(url=params["url"])
                else:
                    results = scraper.safe_scrape(url=params["url"])
            else:
                results = []
            
            # Save raw signals to staging table
            db = SessionLocal()
            try:
                for result in results:
                    raw_signal = ScraperRawSignal(
                        job_id=job["job_id"],
                        source_platform=platform,
                        payload=result,
                        dedupe_key=f"{platform}:{result.get('id', result.get('platform_id', 'unknown'))}"
                    )
                    db.add(raw_signal)
                
                db.commit()
                
                # After saving raw signals, queue normalization job
                from app.workers.queue_adapter import enqueue_job
                enqueue_job(
                    job_type="normalize:signals",
                    params={"raw_signal_job_id": job["job_id"]},
                    source="scrape_worker",
                    priority=job.get("priority", 5)
                )
                
                return {
                    "status": "completed",
                    "results_count": len(results),
                    "raw_signals_saved": len(results),
                    "platform": platform
                }
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving raw signals: {str(e)}")
                raise
            finally:
                db.close()
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    async def run(self):
        """Main worker loop"""
        logger.info("Starting Scrape Worker...")
        
        while self.running:
            try:
                # Get a job from the scrape queue
                job = dequeue_job("queue:scrape", timeout=5)
                
                if job:
                    logger.info(f"Processing job: {job['job_id']} - {job['type']}")
                    
                    # Check for duplicate job using fingerprint
                    fp = fingerprint(job)
                    if seen_before(fp):
                        logger.info(f"Skipping duplicate job: {job['job_id']}")
                        continue
                    
                    mark_seen(fp)
                    
                    try:
                        # Process the job
                        result = await self.process_job(job)
                        
                        # Mark job as completed
                        complete_job(job["job_id"], result)
                        
                        logger.info(f"Job {job['job_id']} completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Job {job['job_id']} failed: {str(e)}")
                        fail_job(job["job_id"], str(e))
                        push_to_dead_letter(job, str(e))
                else:
                    # No job available, sleep briefly
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Scrape Worker interrupted")
                self.running = False
            except Exception as e:
                logger.error(f"Scrape Worker error: {str(e)}")
                await asyncio.sleep(5)  # Wait before continuing to avoid rapid error loops

        if self.session:
            await self.session.close()

    def stop(self):
        """Stop the worker"""
        self.running = False

# For running as standalone script
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers")
    args = parser.parse_args()
    
    async def main():
        # Create and run worker(s)
        workers = []
        for i in range(args.concurrency):
            worker = ScrapeWorker()
            workers.append(worker)
            # Run each worker in a separate task
            asyncio.create_task(worker.run())
        
        try:
            # Keep the main task running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down workers...")
            for worker in workers:
                worker.stop()
    
    asyncio.run(main())