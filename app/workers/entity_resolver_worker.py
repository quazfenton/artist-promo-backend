"""
Entity Resolver and Enrichment Worker - resolves duplicates and enriches contacts
"""
import asyncio
import json
import time
from typing import Dict, Any, Optional, List
import logging
from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, push_to_dead_letter, fingerprint, seen_before, mark_seen
from app.models.staging import StagingContact, ResolvedEntity
from app.models.database import SessionLocal, Contact, ContactType, Platform
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, and_, or_
import os
import hashlib
from app.utils.email_validator import EmailValidator

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)

class EntityResolverEnrichmentWorker:
    def __init__(self):
        self.running = True
        self.email_validator = EmailValidator()

    def generate_merge_key(self, contact_data: Dict[str, Any]) -> str:
        """
        Generate a deterministic merge key for deduplication
        Priority order: verified email > email + name > domain + name > username
        """
        email = contact_data.get('email', '')
        name = contact_data.get('name', '').lower().strip()
        username = contact_data.get('platform_ids', {}).get('username', '')
        
        # If we have an email, use it as the primary key
        if email:
            # Normalize email (lowercase, strip)
            normalized_email = email.lower().strip()
            return f"email:{normalized_email}"
        
        # If no email, try domain + name combination
        if name:
            # Extract domain from any available social handles
            social_handles = contact_data.get('social_handles', {})
            for platform, handle in social_handles.items():
                if handle:
                    if platform == 'website':
                        # Extract domain from website
                        import re
                        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', handle)
                        if domain_match:
                            domain = domain_match.group(1)
                            return f"domain_name:{domain}_{name}"
            
            # Use name as fallback
            return f"name:{name}"
        
        # Last resort: use username
        if username:
            return f"username:{username.lower().strip()}"
        
        # If nothing else, use a hash of available data
        data_str = f"{name}_{email}_{username}"
        return f"hash:{hashlib.md5(data_str.encode()).hexdigest()}"

    def calculate_confidence_score(self, staging_contacts: List[StagingContact]) -> int:
        """
        Calculate combined confidence score based on multiple factors
        """
        if not staging_contacts:
            return 0
        
        total_score = 0
        count = 0
        
        for contact in staging_contacts:
            score = contact.confidence_score or 0
            
            # Boost score if contact appears in multiple places
            if contact.provenance:
                source_count = len(contact.provenance.get('raw_signal_ids', [])) if contact.provenance.get('raw_signal_ids') else 1
                score *= min(source_count, 3)  # Cap at 3x boost
            
            # Boost for verified emails
            if contact.email:
                validation_result = self.email_validator.advanced_validate(contact.email)
                if validation_result.get('valid') and validation_result.get('deliverable'):
                    score += 15
            
            total_score += score
            count += 1
        
        return min(int(total_score / count) if count > 0 else 0, 100)

    def merge_contact_data(self, staging_contacts: List[StagingContact]) -> Dict[str, Any]:
        """
        Merge multiple staging contacts into a single resolved entity
        """
        if not staging_contacts:
            return {}
        
        # Start with the first contact as base
        base_contact = staging_contacts[0]
        
        merged_data = {
            'name': base_contact.name,
            'email': base_contact.email,
            'contact_type': base_contact.contact_type,
            'social_handles': base_contact.social_handles or {},
            'follower_count': base_contact.follower_count or 0,
            'bio': base_contact.bio,
            'source_urls': [base_contact.source_url] if base_contact.source_url else [],
        }
        
        # Merge data from other contacts
        for contact in staging_contacts[1:]:
            # Update name if not set or if this one seems more complete
            if not merged_data['name'] and contact.name:
                merged_data['name'] = contact.name
            
            # Update email if not set
            if not merged_data['email'] and contact.email:
                merged_data['email'] = contact.email
            
            # Update contact type if not set
            if not merged_data['contact_type'] and contact.contact_type:
                merged_data['contact_type'] = contact.contact_type
            
            # Merge social handles
            if contact.social_handles:
                merged_data['social_handles'].update(contact.social_handles or {})
            
            # Take highest follower count
            if contact.follower_count and contact.follower_count > merged_data['follower_count']:
                merged_data['follower_count'] = contact.follower_count
            
            # Merge bio if not set
            if not merged_data['bio'] and contact.bio:
                merged_data['bio'] = contact.bio
            
            # Add source URLs
            if contact.source_url and contact.source_url not in merged_data['source_urls']:
                merged_data['source_urls'].append(contact.source_url)
        
        return merged_data

    async def process_enrichment(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform enrichment on contact data
        """
        enriched_data = contact_data.copy()
        
        # Enrich email if available
        if contact_data.get('email'):
            try:
                # Validate and enrich email
                validation_result = self.email_validator.advanced_validate(contact_data['email'])
                enriched_data['email_validated'] = validation_result.get('valid', False)
                enriched_data['email_deliverable'] = validation_result.get('deliverable', False)
                
                # Try to enrich with Hunter.io if available
                hunter_result = self.email_validator.enrich_with_hunter(contact_data['email'])
                if hunter_result:
                    enriched_data['hunter_enrichment'] = hunter_result
            except Exception as e:
                logger.warning(f"Email enrichment failed for {contact_data.get('email')}: {str(e)}")
        
        # Additional enrichment can go here
        # e.g., WHOIS lookup for domains, social profile validation, etc.
        
        return enriched_data

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single entity resolution and enrichment job"""
        job_type = job["type"]
        
        if job_type == "enrich:entity":
            normalized_job_id = job["params"].get("normalized_job_id")
            
            db = SessionLocal()
            try:
                # Find staging contacts associated with this normalization job
                # We'll look for staging contacts that came from the raw signals of this job
                # Using a more efficient database-level filter
                from sqlalchemy import text
                staging_contacts = db.query(StagingContact).filter(
                    db.query(StagingContact.provenance["job_id"].astext).filter(
                        StagingContact.provenance["job_id"].astext == normalized_job_id
                    ).all()
                
                if not staging_contacts:
                    logger.info(f"No staging contacts found for job {normalized_job_id}")
                    return {
                        "status": "completed",
                        "resolved_count": 0,
                        "processed_staging": 0
                    }
                
                # Group staging contacts by merge key
                grouped_contacts = {}
                for contact in staging_contacts:
                    # Generate merge key for this contact
                    contact_data = {
                        'name': contact.name,
                        'email': contact.email,
                        'contact_type': contact.contact_type,
                        'social_handles': contact.social_handles,
                        'follower_count': contact.follower_count,
                        'bio': contact.bio,
                        'source_url': contact.source_url
                    }
                    merge_key = self.generate_merge_key(contact_data)
                    
                    if merge_key not in grouped_contacts:
                        grouped_contacts[merge_key] = []
                    grouped_contacts[merge_key].append(contact)
                
                resolved_count = 0
                
                # Process each group of contacts
                for merge_key, contact_group in grouped_contacts.items():
                    # Merge the contact data
                    merged_data = self.merge_contact_data(contact_group)
                    
                    # Calculate confidence score
                    confidence_score = self.calculate_confidence_score(contact_group)
                    
                    # Enrich the merged data
                    enriched_data = await self.process_enrichment(merged_data)
                    
                    # Create resolved entity
                    resolved_entity = ResolvedEntity(
                        merge_key=merge_key,
                        confidence_score=confidence_score,
                        contact_type=enriched_data.get('contact_type'),
                        email=enriched_data.get('email'),
                        name=enriched_data.get('name'),
                        social_handles=enriched_data.get('social_handles'),
                        follower_count=enriched_data.get('follower_count', 0),
                        bio=enriched_data.get('bio'),
                        source_urls=enriched_data.get('source_urls'),
                        staging_contact_ids=[c.id for c in contact_group]  # Store IDs of merged contacts
                    )
                    
                    db.add(resolved_entity)
                    resolved_count += 1
                
                db.commit()
                
                # Queue graph building job
                from app.workers.queue_adapter import enqueue_job
                enqueue_job(
                    job_type="graph:build",
                    params={"resolved_job_id": job["job_id"]},
                    source="entity_resolver",
                    priority=job.get("priority", 5)
                )
                
                return {
                    "status": "completed",
                    "resolved_count": resolved_count,
                    "processed_staging": len(staging_contacts),
                    "groups_created": len(grouped_contacts)
                }
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error resolving entities: {str(e)}")
                raise
            finally:
                db.close()
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    async def run(self):
        """Main worker loop"""
        logger.info("Starting Entity Resolver and Enrichment Worker...")
        
        while self.running:
            try:
                # Get a job from the enrich queue
                job = dequeue_job("queue:enrich", timeout=5)
                
                if job:
                    logger.info(f"Processing entity resolution job: {job['job_id']}")
                    
                    # Check for duplicate job using fingerprint
                    fp = fingerprint(job)
                    if seen_before(fp):
                        logger.info(f"Skipping duplicate entity resolution job: {job['job_id']}")
                        continue
                    
                    mark_seen(fp)
                    
                    try:
                        # Process the job
                        result = await self.process_job(job)
                        
                        # Mark job as completed
                        complete_job(job["job_id"], result)
                        
                        logger.info(f"Entity resolution job {job['job_id']} completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Entity resolution job {job['job_id']} failed: {str(e)}")
                        fail_job(job["job_id"], str(e))
                        push_to_dead_letter(job, str(e))
                else:
                    # No job available, sleep briefly
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Entity Resolver Worker interrupted")
                self.running = False
            except Exception as e:
                logger.error(f"Entity Resolver Worker error: {str(e)}")
                await asyncio.sleep(5)  # Wait before continuing to avoid rapid error loops

    def stop(self):
        """Stop the worker"""
        self.running = False

# For running as standalone script
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Entity Resolver and Enrichment Worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers")
    args = parser.parse_args()
    
    async def main():
        # Create and run worker(s)
        workers = []
        tasks = []
        for _ in range(args.concurrency):
            worker = EntityResolverEnrichmentWorker()
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