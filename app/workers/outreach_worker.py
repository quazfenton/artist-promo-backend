"""
Outreach Worker - makes decisions about outreach and sends communications
"""
import asyncio
import json
import time
from typing import Dict, Any, Optional, List
import logging
from app.workers.queue_adapter import dequeue_job, complete_job, fail_job, push_to_dead_letter, fingerprint, seen_before, mark_seen
from app.models.staging import ClusterRun, ResolvedEntity
from app.models.database import SessionLocal, Contact, ContactType, Platform
from app.integrations.email import send_email_via_sendgrid, send_email_via_smtp
from app.outreach.templates import generate_outreach_message
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import os
import random

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)

class OutreachWorker:
    def __init__(self):
        self.running = True
        self.email_transport = os.getenv("EMAIL_TRANSPORT", "smtp")  # smtp or sendgrid

    def confidence_tier(self, score: int) -> str:
        """
        Categorize contacts by confidence score
        """
        if score >= 80:
            return "PRIMARY"
        elif score >= 60:
            return "SECONDARY"
        elif score >= 40:
            return "VERIFY"
        else:
            return "DO_NOT_CONTACT"

    def outreach_strategy(self, cluster_data: Dict[str, Any]) -> str:
        """
        Select outreach strategy based on cluster characteristics
        """
        artist_count = cluster_data.get("artist_count", 0)
        
        if artist_count >= 5:
            return "portfolio"
        elif artist_count >= 2:
            return "network"
        else:
            return "single_artist"

    def build_cluster_context(self, cluster_run: ClusterRun) -> Dict[str, Any]:
        """
        Build context for outreach decision making
        """
        # Get the entities in this cluster
        db = SessionLocal()
        try:
            # For now, we'll create a basic context
            # In a real implementation, you'd join with resolved entities that are part of this cluster
            context = {
                "cluster_id": cluster_run.cluster_id,
                "member_count": len(cluster_run.node_ids) if cluster_run.node_ids else 0,
                "cluster_properties": cluster_run.cluster_properties or {},
                "confidence_score": cluster_run.cluster_properties.get("avg_confidence_score", 0) if cluster_run.cluster_properties else 0,
                "influence_score": cluster_run.cluster_properties.get("influence_score", 0) if cluster_run.cluster_properties else 0,
                "artist_count": cluster_run.cluster_properties.get("member_count", 0) if cluster_run.cluster_properties else 0
            }
            return context
        finally:
            db.close()

    def select_best_contact(self, cluster_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Select the best contact for outreach from a cluster
        """
        # In a real implementation, this would query the resolved entities
        # and select the one with the highest confidence score in the cluster
        # For now, we'll return a dummy contact based on cluster metrics
        if cluster_context.get("confidence_score", 0) > 40:
            # This is a simplified example - in reality you'd query the DB
            # for the resolved entities in this cluster and pick the best one
            return {
                "email": "contact@example.com",
                "name": "Example Manager",
                "confidence": cluster_context.get("confidence_score", 50)
            }
        return None

    def should_send_outreach(self, contact: Dict[str, Any], cluster_context: Dict[str, Any]) -> bool:
        """
        Decide whether to send outreach based on contact and cluster characteristics
        """
        # Check confidence tier
        tier = self.confidence_tier(contact.get("confidence", 0))
        if tier == "DO_NOT_CONTACT":
            return False

        # Check cluster influence
        influence_score = cluster_context.get("influence_score", 0)
        if influence_score < 20:  # Threshold for sending outreach
            return False

        # Additional checks can go here
        return True

    async def send_outreach_message(self, contact: Dict[str, Any], cluster_context: Dict[str, Any]) -> bool:
        """
        Send outreach message to selected contact
        """
        try:
            # Generate personalized message
            message = generate_outreach_message(contact, cluster_context)
            
            # Determine email transport
            if self.email_transport == "sendgrid":
                success = await send_email_via_sendgrid(
                    to_email=contact["email"],
                    subject=message["subject"],
                    body=message["body"]
                )
            else:
                success = await send_email_via_smtp(
                    to_email=contact["email"],
                    subject=message["subject"],
                    body=message["body"]
                )
            
            if success:
                logger.info(f"Outreach sent successfully to {contact['email']}")
                
                # Update contact record to reflect outreach
                db = SessionLocal()
                try:
                    # Find the corresponding resolved entity
                    resolved_entity = db.query(ResolvedEntity).filter(
                        ResolvedEntity.email == contact["email"]
                    ).first()
                    
                    if resolved_entity:
                        # Update outreach tracking
                        if not hasattr(resolved_entity, 'outreach_history'):
                            resolved_entity.outreach_history = []
                        resolved_entity.outreach_history.append({
                            "timestamp": time.time(),
                            "type": "outreach",
                            "status": "sent",
                            "cluster_context": cluster_context
                        })
                        db.commit()
                except Exception as e:
                    logger.error(f"Error updating outreach history: {str(e)}")
                finally:
                    db.close()
                
                return True
            else:
                logger.warning(f"Failed to send outreach to {contact['email']}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending outreach to {contact['email']}: {str(e)}")
            return False

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single outreach decision job"""
        job_type = job["type"]
        
        if job_type == "outreach:decision":
            cluster_run_id = job["params"].get("cluster_run_id")
            
            db = SessionLocal()
            try:
                # Get the cluster run
                cluster_run = db.query(ClusterRun).filter(
                    ClusterRun.run_id == cluster_run_id
                ).first()
                
                if not cluster_run:
                    logger.warning(f"Cluster run {cluster_run_id} not found")
                    return {
                        "status": "completed",
                        "clusters_processed": 0,
                        "outreach_attempts": 0,
                        "outreach_successes": 0
                    }
                
                # Build context for this cluster
                cluster_context = self.build_cluster_context(cluster_run)
                
                # Select best contact for outreach
                contact = self.select_best_contact(cluster_context)
                
                if not contact:
                    logger.info(f"No suitable contact found for cluster {cluster_run.cluster_id}")
                    return {
                        "status": "completed",
                        "clusters_processed": 1,
                        "outreach_attempts": 0,
                        "outreach_successes": 0
                    }
                
                # Check if we should send outreach
                if self.should_send_outreach(contact, cluster_context):
                    # Send the outreach message
                    success = await self.send_outreach_message(contact, cluster_context)
                    
                    return {
                        "status": "completed",
                        "clusters_processed": 1,
                        "outreach_attempts": 1,
                        "outreach_successes": 1 if success else 0,
                        "contact_selected": contact["email"]
                    }
                else:
                    logger.info(f"Skipping outreach for {contact['email']} based on criteria")
                    return {
                        "status": "completed",
                        "clusters_processed": 1,
                        "outreach_attempts": 0,
                        "outreach_successes": 0,
                        "skip_reason": "criteria_not_met"
                    }
                
            except Exception as e:
                logger.error(f"Error in outreach decision: {str(e)}")
                raise
            finally:
                db.close()
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    async def run(self):
        """Main worker loop"""
        logger.info("Starting Outreach Worker...")
        
        while self.running:
            try:
                # Get a job from the outreach queue
                job = dequeue_job("queue:outreach", timeout=5)
                
                if job:
                    logger.info(f"Processing outreach job: {job['job_id']}")
                    
                    # Check for duplicate job using fingerprint
                    fp = fingerprint(job)
                    if seen_before(fp):
                        logger.info(f"Skipping duplicate outreach job: {job['job_id']}")
                        continue
                    
                    mark_seen(fp)
                    
                    try:
                        # Process the job
                        result = await self.process_job(job)
                        
                        # Mark job as completed
                        complete_job(job["job_id"], result)
                        
                        logger.info(f"Outreach job {job['job_id']} completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Outreach job {job['job_id']} failed: {str(e)}")
                        fail_job(job["job_id"], str(e))
                        push_to_dead_letter(job, str(e))
                else:
                    # No job available, sleep briefly
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Outreach Worker interrupted")
                self.running = False
            except Exception as e:
                logger.error(f"Outreach Worker error: {str(e)}")
                await asyncio.sleep(5)  # Wait before continuing to avoid rapid error loops

    def stop(self):
        """Stop the worker"""
        self.running = False

# For running as standalone script
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Outreach Worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers")
    args = parser.parse_args()
    
    async def main():
        # Create and run worker(s)
        workers = []
        for i in range(args.concurrency):
            worker = OutreachWorker()
            workers.append(worker)
            # Run each worker in a separate task
            asyncio.create_task(worker.run())
        
        try:
            try:
                # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
                    if isinstance(result, Exception):
                        logger.error("Worker task failed", exc_info=result)
                        raise result
            except KeyboardInterrupt:
                logger.info("Shutting down workers...")
                for worker in workers:
                    worker.stop()
