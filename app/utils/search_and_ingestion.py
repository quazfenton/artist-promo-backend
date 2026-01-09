"""
Search index and webhook ingestion system
"""
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Any
from datetime import datetime, timedelta
import json
import threading
from app.models.staging import ResolvedEntity
from app.models.database import SessionLocal, Contact
from app.utils.evidence_ledger import log_evidence, store_evidence_in_db
from app.utils.manager_resolution import calculate_entity_merge_confidence

class SearchIndex:
    """Local search index for fast lookup of contacts and entities"""
    
    def __init__(self):
        self.email_index = defaultdict(set)  # email -> {entity_ids}
        self.domain_index = defaultdict(set)  # domain -> {entity_ids}
        self.name_index = defaultdict(set)    # name -> {entity_ids}
        self.artist_index = defaultdict(set)  # artist -> {entity_ids}
        self.manager_index = defaultdict(set) # manager -> {entity_ids}
        self.lock = threading.RLock()  # Thread-safe operations
        
    def add_contact(self, email: str, entity_id: int, name: str = None, 
                   artist: str = None, manager: str = None):
        """Add a contact to the search index"""
        with self.lock:
            if email:
                self.email_index[email].add(entity_id)
                
                # Index domain separately
                if '@' in email:
                    domain = email.split('@')[1]
                    self.domain_index[domain].add(entity_id)
            
            if name:
                self.name_index[name.lower()].add(entity_id)
            
            if artist:
                self.artist_index[artist.lower()].add(entity_id)
            
            if manager:
                self.manager_index[manager.lower()].add(entity_id)
    
    def remove_contact(self, email: str, entity_id: int):
        """Remove a contact from the search index"""
        with self.lock:
            if email:
                self.email_index[email].discard(entity_id)
                
                if '@' in email:
                    domain = email.split('@')[1]
                    self.domain_index[domain].discard(entity_id)
    
    def search_email(self, email: str) -> Set[int]:
        """Search for entity IDs by email"""
        return self.email_index.get(email, set())
    
    def search_domain(self, domain: str) -> Set[int]:
        """Search for entity IDs by domain"""
        return self.domain_index.get(domain, set())
    
    def search_name(self, name: str) -> Set[int]:
        """Search for entity IDs by name"""
        return self.name_index.get(name.lower(), set())
    
    def search_artist(self, artist: str) -> Set[int]:
        """Search for entity IDs by artist"""
        return self.artist_index.get(artist.lower(), set())
    
    def search_manager(self, manager: str) -> Set[int]:
        """Search for entity IDs by manager"""
        return self.manager_index.get(manager.lower(), set())
    
    def fuzzy_search(self, query: str, threshold: float = 0.6) -> Dict[str, Set[int]]:
        """Fuzzy search across all indices"""
        results = {
            "emails": set(),
            "names": set(),
            "domains": set()
        }
        
        query_lower = query.lower()
        
        # Search emails (partial match)
        for email, entity_ids in self.email_index.items():
            if query_lower in email.lower():
                results["emails"].update(entity_ids)
        
        # Search names (partial match)
        for name, entity_ids in self.name_index.items():
            if query_lower in name.lower():
                results["names"].update(entity_ids)
        
        # Search domains (partial match)
        for domain, entity_ids in self.domain_index.items():
            if query_lower in domain.lower():
                results["domains"].update(entity_ids)
        
        return results
    
    def get_all_entities(self) -> Set[int]:
        """Get all indexed entity IDs"""
        with self.lock:
            all_ids = set()
            for index in [self.email_index, self.domain_index, self.name_index]:
                for entity_ids in index.values():
                    all_ids.update(entity_ids)
            return all_ids

class WebhookIngestor:
    """Handles webhook ingestion for external signals"""
    
    def __init__(self, search_index: SearchIndex):
        self.search_index = search_index
        self.ingestion_queue = deque(maxlen=1000)  # Limited queue for recent items
        self.processed_payloads = {}  # Track processed payloads to avoid duplicates
        self.lock = threading.RLock()
    
    def ingest_payload(self, payload: Dict[str, Any], source: str = "webhook") -> Dict[str, Any]:
        """Ingest a payload from external source"""
        with self.lock:
            # Create a unique key for this payload to avoid duplicates
            payload_key = self._create_payload_key(payload)
            
            if payload_key in self.processed_payloads:
                return {"status": "duplicate", "message": "Payload already processed"}
            
            # Add to ingestion queue
            self.ingestion_queue.append({
                "payload": payload,
                "source": source,
                "timestamp": datetime.utcnow(),
                "payload_key": payload_key
            })
            
            # Process the payload
            result = self._process_payload(payload, source)
            
            # Mark as processed
            self.processed_payloads[payload_key] = {
                "timestamp": datetime.utcnow(),
                "result": result
            }
            
            # Clean old processed payloads (keep last 1000)
            if len(self.processed_payloads) > 1000:
                oldest_keys = sorted(self.processed_payloads.keys())[:-1000]
                for key in oldest_keys:
                    del self.processed_payloads[key]
            
            return result
    
    def _create_payload_key(self, payload: Dict[str, Any]) -> str:
        """Create a unique key for a payload"""
        import hashlib
        import json
        
        # Create a hash of the payload content
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.md5(payload_str.encode()).hexdigest()
    
    def _process_payload(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Process an ingested payload"""
        try:
            # Extract relevant information from payload
            emails = payload.get("emails", [])
            if isinstance(emails, str):
                emails = [emails]
            
            name = payload.get("name")
            artist = payload.get("artist")
            manager = payload.get("manager")
            domain = payload.get("domain")
            
            # Process each email
            processed_entities = []
            for email in emails:
                # Create or update entity in database
                entity_id = self._create_or_update_entity(email, name, artist, manager, domain, source, payload)
                
                # Add to search index
                self.search_index.add_contact(email, entity_id, name, artist, manager)
                
                processed_entities.append(entity_id)
            
            # Handle other fields
            if domain and not emails:  # Domain-only entry
                # Create a placeholder entity
                entity_id = self._create_domain_placeholder(domain, source, payload)
                self.search_index.add_contact("", entity_id, name, artist, manager)
                processed_entities.append(entity_id)
            
            return {
                "status": "success",
                "processed_entities": processed_entities,
                "source": source,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "source": source,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _create_or_update_entity(self, email: str, name: str, artist: str, 
                               manager: str, domain: str, source: str, 
                               payload: Dict[str, Any]) -> int:
        """Create or update an entity in the database"""
        db = SessionLocal()
        try:
            # Check if entity already exists
            existing = db.query(ResolvedEntity).filter(
                ResolvedEntity.email == email
            ).first()
            
            if existing:
                # Update existing entity
                if name:
                    existing.name = name
                if artist:
                    # Add to artist list if not already there
                    if not existing.source_urls:
                        existing.source_urls = []
                    if artist not in existing.source_urls:
                        existing.source_urls.append(artist)
                if payload.get("confidence"):
                    existing.confidence_score = payload["confidence"]
                
                entity_id = existing.id
            else:
                # Create new entity
                new_entity = ResolvedEntity(
                    email=email,
                    name=name,
                    contact_type=payload.get("contact_type", "unknown"),
                    confidence_score=payload.get("confidence", 50),
                    source_urls=[artist] if artist else [],
                    merge_key=f"ingested:{email}",
                    bio=payload.get("bio", ""),
                    social_handles=payload.get("social_handles", {}),
                    follower_count=payload.get("follower_count", 0)
                )
                
                db.add(new_entity)
                db.commit()
                entity_id = new_entity.id
            
            # Log evidence for this ingestion
            evidence = log_evidence(
                email=email,
                source=source,
                signal="webhook_ingestion",
                url=payload.get("source_url", ""),
                confidence=payload.get("confidence", 1.0),
                metadata=payload
            )
            store_evidence_in_db(evidence)
            
            return entity_id
            
        finally:
            db.close()
    
    def _create_domain_placeholder(self, domain: str, source: str, 
                                 payload: Dict[str, Any]) -> int:
        """Create a domain-only placeholder entity"""
        db = SessionLocal()
        try:
            # Create a placeholder entity for domain
            placeholder = ResolvedEntity(
                email=f"placeholder@{domain}",
                name=f"Domain Placeholder: {domain}",
                contact_type="domain_placeholder",
                confidence_score=payload.get("confidence", 30),
                merge_key=f"domain:{domain}",
                bio=payload.get("description", ""),
                source_urls=[payload.get("source_url", "")],
                follower_count=0
            )
            
            db.add(placeholder)
            db.commit()
            
            return placeholder.id
            
        finally:
            db.close()
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics about webhook ingestion"""
        with self.lock:
            return {
                "queue_size": len(self.ingestion_queue),
                "processed_count": len(self.processed_payloads),
                "recent_ingestions": [
                    {
                        "source": item["source"],
                        "timestamp": item["timestamp"].isoformat(),
                        "payload_size": len(json.dumps(item["payload"]))
                    }
                    for item in list(self.ingestion_queue)[-10:]  # Last 10 items
                ]
            }

class OutboundCooldownScheduler:
    """Manages cooldown periods between outbound contacts"""
    
    def __init__(self, default_cooldown_days: int = 14):
        self.default_cooldown = default_cooldown_days
        self.contact_log = {}  # email -> last_contact_time
        self.lock = threading.RLock()
    
    def can_contact(self, email: str, cooldown_days: int = None) -> bool:
        """Check if we can contact this email"""
        if cooldown_days is None:
            cooldown_days = self.default_cooldown
        
        with self.lock:
            if email not in self.contact_log:
                return True
            
            last_contact = self.contact_log[email]
            time_since_contact = datetime.utcnow() - last_contact
            
            return time_since_contact.days >= cooldown_days
    
    def mark_contacted(self, email: str):
        """Mark that we contacted this email"""
        with self.lock:
            self.contact_log[email] = datetime.utcnow()
    
    def get_next_available_contact(self, email: str, cooldown_days: int = None) -> datetime:
        """Get when we can next contact this email"""
        if cooldown_days is None:
            cooldown_days = self.default_cooldown
        
        with self.lock:
            last_contact = self.contact_log.get(email, datetime.min)
            return last_contact + timedelta(days=cooldown_days)
    
    def clear_expired_cooldowns(self, days_to_keep: int = 365):
        """Remove cooldowns older than specified days"""
        with self.lock:
            cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
            expired_emails = [
                email for email, last_contact in self.contact_log.items()
                if last_contact < cutoff
            ]
            
            for email in expired_emails:
                del self.contact_log[email]

class PipelineHealthMonitor:
    """Monitors pipeline health and metrics"""
    
    def __init__(self):
        self.metrics = {
            "scrape_failures": 0,
            "emails_found": 0,
            "clusters_formed": 0,
            "entities_resolved": 0,
            "verification_successes": 0,
            "outreach_attempts": 0,
            "outreach_successes": 0
        }
        self.errors = deque(maxlen=100)  # Keep last 100 errors
        self.lock = threading.RLock()
    
    def increment_metric(self, metric_name: str, amount: int = 1):
        """Increment a metric"""
        with self.lock:
            if metric_name in self.metrics:
                self.metrics[metric_name] += amount
            else:
                self.metrics[metric_name] = amount
    
    def log_error(self, error: str, source: str = "unknown"):
        """Log an error"""
        with self.lock:
            self.errors.append({
                "error": error,
                "source": source,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get current health metrics"""
        with self.lock:
            return {
                "metrics": self.metrics.copy(),
                "error_count": len(self.errors),
                "recent_errors": list(self.errors)[-10:],  # Last 10 errors
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def reset_metrics(self):
        """Reset all metrics"""
        with self.lock:
            for key in self.metrics:
                self.metrics[key] = 0
            self.errors.clear()

# Global instances
search_index = SearchIndex()
webhook_ingestor = WebhookIngestor(search_index)
cooldown_scheduler = OutboundCooldownScheduler()
health_monitor = PipelineHealthMonitor()

def get_search_index() -> SearchIndex:
    """Get the search index instance"""
    return search_index

def get_webhook_ingestor() -> WebhookIngestor:
    """Get the webhook ingestor instance"""
    return webhook_ingestor

def get_cooldown_scheduler() -> OutboundCooldownScheduler:
    """Get the cooldown scheduler instance"""
    return cooldown_scheduler

def get_health_monitor() -> PipelineHealthMonitor:
    """Get the health monitor instance"""
    return health_monitor