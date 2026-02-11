"""
Signal Normalizer Worker - normalizes raw signals into staging contacts
"""
import asyncio
import json
import time
from typing import Dict, Any, Optional
import logging
from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, push_to_dead_letter, fingerprint, seen_before, mark_seen
from app.models.staging import ScraperRawSignal, StagingContact
from app.models.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, and_
import os
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)

class SignalNormalizerWorker:
    def __init__(self):
        self.running = True

    def extract_emails(self, text: str) -> list:
        """Extract emails from text using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return list(set(re.findall(email_pattern, text or "")))

    def normalize_record(self, raw_signal: ScraperRawSignal) -> list:
        """Convert raw signal into normalized staging contacts"""
        payload = raw_signal.payload or {}
        normalized_contacts = []
        
        # Extract common fields from different platforms
        if raw_signal.source_platform == "spotify":
            # Spotify curator data
            curator_profile = payload.get('curator_profile', {})
            if curator_profile:
                emails = self.extract_emails(curator_profile.get('bio', ''))
                
                contact = {
                    'name': curator_profile.get('display_name'),
                    'email': emails[0] if emails else None,
                    'contact_type': 'playlist_curator',
                    'social_handles': {
                        'instagram': curator_profile.get('instagram_handle'),
                        'twitter': curator_profile.get('twitter_handle'),
                    },
                    'follower_count': curator_profile.get('follower_count', 0),
                    'bio': curator_profile.get('bio'),
                    'source_url': curator_profile.get('profile_url'),
                    'platform_ids': {
                        'spotify_user_id': curator_profile.get('user_id'),
                        'username': curator_profile.get('username')
                    }
                }
                normalized_contacts.append(contact)
                
        elif raw_signal.source_platform == "youtube":
            # YouTube channel data
            emails = self.extract_emails(payload.get('description', ''))
            
            contact = {
                'name': payload.get('channel_name'),
                'email': emails[0] if emails else payload.get('business_email'),
                'contact_type': 'playlist_curator',
                'social_handles': {},
                'follower_count': payload.get('subscriber_count', 0),
                'bio': payload.get('description'),
                'source_url': payload.get('channel_url'),
                'platform_ids': {
                    'youtube_channel_id': payload.get('channel_id'),
                    'youtube_username': payload.get('username')
                }
            }
            normalized_contacts.append(contact)
            
        elif raw_signal.source_platform == "instagram":
            # Instagram profile data
            profile_data = payload
            emails = self.extract_emails(profile_data.get('bio', ''))
            
            contact = {
                'name': profile_data.get('full_name'),
                'email': emails[0] if emails else profile_data.get('business_email'),
                'contact_type': 'influencer',
                'social_handles': {
                    'instagram': profile_data.get('username'),
                    'website': profile_data.get('website'),
                },
                'follower_count': profile_data.get('follower_count', 0),
                'bio': profile_data.get('bio'),
                'source_url': profile_data.get('profile_url'),
                'platform_ids': {
                    'instagram_username': profile_data.get('username'),
                    'instagram_user_id': profile_data.get('user_id')
                }
            }
            normalized_contacts.append(contact)
            
        elif raw_signal.source_platform == "web":
            # Web scraper data
            web_data = payload
            for email in web_data.get('emails', []):
                contact = {
                    'name': web_data.get('name'),
                    'email': email,
                    'contact_type': 'publicist',
                    'social_handles': {},
                    'follower_count': 0,
                    'bio': web_data.get('description'),
                    'source_url': web_data.get('url'),
                    'platform_ids': {
                        'website_url': web_data.get('url')
                    }
                }
                normalized_contacts.append(contact)
        
        # Calculate confidence scores based on available data
        for contact in normalized_contacts:
            confidence = 10  # Base confidence
            
            # Add points for different data quality indicators
            if contact.get('email'):
                confidence += 20
                # Check if it's a business email
                email = contact['email']
                if email and not any(domain in email for domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']):
                    confidence += 10
            
            if contact.get('social_handles'):
                confidence += 15
            
            if contact.get('follower_count', 0) > 1000:
                confidence += 10
            elif contact.get('follower_count', 0) > 100:
                confidence += 5
            
            if contact.get('bio'):
                confidence += 10
            
            contact['confidence_score'] = min(confidence, 100)  # Cap at 100
        
        return normalized_contacts

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single normalization job"""
        job_type = job["type"]
        
        if job_type == "normalize:signals":
            raw_signal_job_id = job["params"].get("raw_signal_job_id")
            
            db = SessionLocal()
            try:
                # Find raw signals associated with this job
                raw_signals = db.query(ScraperRawSignal).filter(
                    ScraperRawSignal.job_id == raw_signal_job_id
                ).all()
                
                normalized_count = 0
                
                for raw_signal in raw_signals:
                    # Normalize the raw signal
                    normalized_contacts = self.normalize_record(raw_signal)
                    
                    # Save normalized contacts to staging table
                    for contact_data in normalized_contacts:
                        staging_contact = StagingContact(
                            raw_signal_id=raw_signal.id,
                            name=contact_data.get('name'),
                            email=contact_data.get('email'),
                            contact_type=contact_data.get('contact_type'),
                            social_handles=contact_data.get('social_handles'),
                            confidence_score=contact_data.get('confidence_score', 0),
                            platform_ids=contact_data.get('platform_ids'),
                            follower_count=contact_data.get('follower_count', 0),
                            bio=contact_data.get('bio'),
                            source_url=contact_data.get('source_url'),
                            provenance={
                                'job_id': job["job_id"],
                                'source_platform': raw_signal.source_platform,
                                'raw_signal_id': raw_signal.id
                            }
                        )
                        db.add(staging_contact)
                        normalized_count += 1
                
                db.commit()
                
                # Queue entity resolution job
                from app.workers.queue_adapter import enqueue_job
                enqueue_job(
                    job_type="enrich:entity",
                    params={"normalized_job_id": job["job_id"]},
                    source="signal_normalizer",
                    priority=job.get("priority", 5)
                )
                
                return {
                    "status": "completed",
                    "normalized_count": normalized_count,
                    "raw_signals_processed": len(raw_signals)
                }
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error normalizing signals: {str(e)}")
                raise
            finally:
                db.close()
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    async def run(self):
        """Main worker loop"""
        logger.info("Starting Signal Normalizer Worker...")
        
        while self.running:
            try:
                # Get a job from the normalize queue
                job = dequeue_job("queue:normalize", timeout=5)
                
                if job:
                    logger.info(f"Processing normalization job: {job['job_id']}")
                    
                    # Check for duplicate job using fingerprint
                    fp = fingerprint(job)
                    if seen_before(fp):
                        logger.info(f"Skipping duplicate normalization job: {job['job_id']}")
                        continue
                    
                    mark_seen(fp)
                    
                    try:
                        # Process the job
                        result = await self.process_job(job)
                        
                        # Mark job as completed
                        complete_job(job["job_id"], result)
                        
                        logger.info(f"Normalization job {job['job_id']} completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Normalization job {job['job_id']} failed: {str(e)}")
                        fail_job(job["job_id"], str(e))
                        push_to_dead_letter(job, str(e))
                else:
                    # No job available, sleep briefly
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Signal Normalizer Worker interrupted")
                self.running = False
            except Exception as e:
                logger.error(f"Signal Normalizer Worker error: {str(e)}")
                await asyncio.sleep(5)  # Wait before continuing to avoid rapid error loops

    def stop(self):
        """Stop the worker"""
        self.running = False

# For running as standalone script
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Signal Normalizer Worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers")
    args = parser.parse_args()
    
    async def main():
        # Create and run worker(s)
        workers = []
        tasks = []
        for _ in range(args.concurrency):
            worker = SignalNormalizerWorker()
            workers.append(worker)
            # Run each worker in a separate task and store the reference
            task = asyncio.create_task(worker.run())
            tasks.append(task)

        try:
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutting down workers...")
            for worker in workers:
                worker.stop()
            # Wait for tasks to complete gracefully
            await asyncio.gather(*tasks, return_exceptions=True)
    
    asyncio.run(main())