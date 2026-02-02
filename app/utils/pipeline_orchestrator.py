"""
Pipeline orchestrator and state machine for the contact discovery pipeline
"""
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import json
from app.models.staging import ScraperRawSignal, StagingContact, ResolvedEntity, GraphNode, GraphEdge, ClusterRun
from app.models.database import SessionLocal, Contact
from app.utils.evidence_ledger import log_evidence, store_evidence_in_db
from app.utils.manager_resolution import calculate_cluster_quality_score, get_cluster_risk_level
from app.utils.temporal_scoring import calculate_evidence_trust_score
from app.utils.email_canonicalization import canonicalize_email, is_business_email
from app.utils.link_in_bio_resolver import aggregate_contact_info_from_multiple_sources

class PipelineState(Enum):
    """States in the pipeline"""
    SCRAPED = "scraped"
    NORMALIZED = "normalized"
    CLUSTERED = "clustered"
    SCORED = "scored"
    VERIFIED = "verified"
    READY_TO_SEND = "ready_to_send"
    CONTACTED = "contacted"
    FAILED = "failed"

class PipelineOrchestrator:
    """Orchestrates the entire pipeline from scraping to outreach"""
    
    def __init__(self):
        self.state_transitions = {
            PipelineState.SCRAPED: [PipelineState.NORMALIZED],
            PipelineState.NORMALIZED: [PipelineState.CLUSTERED],
            PipelineState.CLUSTERED: [PipelineState.SCORED],
            PipelineState.SCORED: [PipelineState.VERIFIED, PipelineState.READY_TO_SEND],
            PipelineState.VERIFIED: [PipelineState.READY_TO_SEND],
            PipelineState.READY_TO_SEND: [PipelineState.CONTACTED, PipelineState.FAILED],
            PipelineState.CONTACTED: [PipelineState.SCRAPED],  # For follow-ups
            PipelineState.FAILED: [PipelineState.SCRAPED]  # For retries
        }
    
    def can_advance_state(self, current_state: PipelineState, new_state: PipelineState) -> bool:
        """Check if state transition is valid"""
        return new_state in self.state_transitions.get(current_state, [])
    
    def advance_state(self, record_id: int, new_state: PipelineState,
                     entity_type: str = "resolved_entity") -> bool:
        """Advance a record to a new state"""
        # We can't validate the transition without knowing the current state
        # So we'll just proceed with the state update
        
        db = SessionLocal()
        try:
            if entity_type == "resolved_entity":
                entity = db.query(ResolvedEntity).filter(ResolvedEntity.id == record_id).first()
                if entity:
                    entity.last_updated = datetime.utcnow()
                    # In a real system, you'd have a state field
                    # For now, we'll just log the transition
                    print(f"Advanced entity {record_id} to {new_state.value}")
                    db.commit()  # Commit the changes
                    return True
            elif entity_type == "contact":
                contact = db.query(Contact).filter(Contact.id == record_id).first()
                if contact:
                    contact.updated_at = datetime.utcnow()
                    print(f"Advanced contact {record_id} to {new_state.value}")
                    db.commit()  # Commit the changes
                    return True
            elif entity_type == "raw_signal":
                signal = db.query(ScraperRawSignal).filter(ScraperRawSignal.id == record_id).first()
                if signal:
                    print(f"Advanced raw signal {record_id} to {new_state.value}")
                    return True
        finally:
            db.close()
        
        return False

class SignalNormalizer:
    """Normalizes raw signals into standardized format"""
    
    def __init__(self):
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    def normalize_raw_signal(self, raw_signal: ScraperRawSignal) -> List[StagingContact]:
        """Convert raw signal to normalized staging contacts"""
        payload = raw_signal.payload or {}
        staging_contacts = []
        
        # Extract emails from various sources
        emails = self._extract_emails_from_payload(payload)
        
        # Extract other contact info
        name = payload.get('name') or payload.get('display_name') or payload.get('full_name')
        bio = payload.get('bio') or payload.get('description')
        follower_count = payload.get('follower_count', 0)
        platform_ids = payload.get('platform_ids', {})
        
        # Create staging contacts for each email found
        for email in emails:
            staging_contact = StagingContact(
                raw_signal_id=raw_signal.id,
                name=name,
                email=email,
                contact_type=self._infer_contact_type(raw_signal.source_platform, bio),
                social_handles=self._extract_social_handles(payload),
                confidence_score=self._calculate_initial_confidence(email, follower_count),
                platform_ids=platform_ids,
                follower_count=follower_count,
                bio=bio,
                source_url=payload.get('source_url') or raw_signal.dedupe_key,
                provenance={
                    'job_id': raw_signal.job_id,
                    'source_platform': raw_signal.source_platform,
                    'raw_signal_id': raw_signal.id,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            staging_contacts.append(staging_contact)
        
        return staging_contacts
    
    def _extract_emails_from_payload(self, payload: Dict[str, Any]) -> List[str]:
        """Extract emails from payload data"""
        import re
        
        emails = set()
        
        # Extract from bio/description
        bio = payload.get('bio') or payload.get('description', '')
        bio_emails = re.findall(self.email_pattern, bio)
        emails.update(bio_emails)
        
        # Extract from links
        links = payload.get('links', [])
        for link in links:
            link_emails = re.findall(self.email_pattern, link)
            emails.update(link_emails)
        
        # Extract from specific email fields
        if 'email' in payload and payload['email']:
            emails.add(payload['email'])
        
        if 'emails' in payload and isinstance(payload['emails'], list):
            emails.update(payload['emails'])
        
        # Extract from website content if available
        website_content = payload.get('website_content', '')
        website_emails = re.findall(self.email_pattern, website_content)
        emails.update(website_emails)
        
        return list(emails)
    
    def _infer_contact_type(self, platform: str, bio: str) -> str:
        """Infer contact type from platform and bio"""
        bio_lower = bio.lower() if bio else ""
        
        # Keywords that suggest different contact types
        if any(keyword in bio_lower for keyword in ['booking', 'bookings', 'manager', 'mgmt', 'management']):
            return 'manager'
        elif any(keyword in bio_lower for keyword in ['publicist', 'press', 'media', 'pr']):
            return 'publicist'
        elif any(keyword in bio_lower for keyword in ['curator', 'playlist', 'dj', 'radio']):
            return 'playlist_curator'
        elif any(keyword in bio_lower for keyword in ['label', 'records', 'music']):
            return 'label'
        elif any(keyword in bio_lower for keyword in ['venue', 'booker', 'booking']):
            return 'venue_booker'
        elif any(keyword in bio_lower for keyword in ['journalist', 'writer', 'blog']):
            return 'journalist'
        elif any(keyword in bio_lower for keyword in ['influencer', 'content', 'creator']):
            return 'influencer'
        elif platform == 'instagram':
            return 'influencer'
        elif platform == 'youtube':
            return 'playlist_curator'
        else:
            return 'unknown'
    
    def _extract_social_handles(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Extract social media handles"""
        handles = {}
        
        # Common social media fields
        social_fields = {
            'instagram': ['instagram', 'instagram_handle', 'ig'],
            'twitter': ['twitter', 'twitter_handle', 'x', 'x_handle'],
            'youtube': ['youtube', 'youtube_channel', 'yt'],
            'tiktok': ['tiktok', 'tiktok_handle'],
            'facebook': ['facebook', 'fb'],
            'linkedin': ['linkedin', 'linkedin_profile']
        }
        
        for platform, field_names in social_fields.items():
            for field in field_names:
                if field in payload and payload[field]:
                    handles[platform] = payload[field]
                    break
        
        return handles
    
    def _calculate_initial_confidence(self, email: str, follower_count: int) -> int:
        """Calculate initial confidence score"""
        confidence = 10  # Base confidence
        
        # Boost for business emails
        if is_business_email(email):
            confidence += 20
        
        # Boost for higher follower counts
        if follower_count > 10000:
            confidence += 20
        elif follower_count > 5000:
            confidence += 15
        elif follower_count > 1000:
            confidence += 10
        elif follower_count > 100:
            confidence += 5
        
        # Cap at 100
        return min(100, confidence)

class EntityResolver:
    """Resolves and deduplicates staging contacts into resolved entities"""
    
    def __init__(self):
        self.merge_threshold = 85  # Confidence threshold for merging
    
    def resolve_entities(self, staging_contacts: List[StagingContact]) -> List[ResolvedEntity]:
        """Resolve staging contacts into canonical entities"""
        resolved_entities = []
        
        # Group contacts by merge key (canonicalized email or domain+name)
        grouped_contacts = self._group_by_merge_key(staging_contacts)
        
        for merge_key, contacts in grouped_contacts.items():
            # Merge contacts with the same key
            resolved_entity = self._merge_contacts(merge_key, contacts)
            resolved_entities.append(resolved_entity)
        
        return resolved_entities
    
    def _group_by_merge_key(self, contacts: List[StagingContact]) -> Dict[str, List[StagingContact]]:
        """Group contacts by merge key"""
        groups = {}
        
        for contact in contacts:
            # Use canonicalized email as primary key
            if contact.email:
                key = canonicalize_email(contact.email)
            else:
                # Fallback to domain + name combination
                domain = contact.source_url.split('/')[2] if contact.source_url else 'unknown'
                name = contact.name or 'unknown'
                key = f"{domain}:{name}".lower()
            
            if key not in groups:
                groups[key] = []
            groups[key].append(contact)
        
        return groups
    
    def _merge_contacts(self, merge_key: str, contacts: List[StagingContact]) -> ResolvedEntity:
        """Merge multiple contacts into a single resolved entity"""
        # Start with the first contact as base
        base_contact = contacts[0]
        
        # Collect all unique information
        all_emails = set()
        all_names = set()
        all_bios = set()
        all_handles = {}
        all_source_urls = set()
        all_evidence = []
        
        total_follower_count = 0
        total_confidence = 0
        
        for contact in contacts:
            if contact.email:
                all_emails.add(contact.email)
            if contact.name:
                all_names.add(contact.name)
            if contact.bio:
                all_bios.add(contact.bio)
            if contact.social_handles:
                all_handles.update(contact.social_handles)
            if contact.source_url:
                all_source_urls.add(contact.source_url)
            
            total_follower_count += contact.follower_count or 0
            total_confidence += contact.confidence_score or 0
            
            # Add evidence
            all_evidence.append({
                'source': contact.provenance.get('source_platform', 'unknown') if contact.provenance else 'unknown',
                'signal': 'contact_merge',
                'url': contact.source_url,
                'timestamp': datetime.utcnow().isoformat(),
                'confidence': contact.confidence_score or 0
            })
        
        # Calculate merged values
        primary_email = list(all_emails)[0] if all_emails else None
        primary_name = list(all_names)[0] if all_names else None
        primary_bio = list(all_bios)[0] if all_bios else None
        
        avg_confidence = total_confidence / len(contacts) if contacts else 0
        avg_follower_count = total_follower_count / len(contacts) if contacts else 0
        
        # Determine contact type (majority vote or first non-unknown)
        contact_types = [c.contact_type for c in contacts if c.contact_type and c.contact_type != 'unknown']
        primary_contact_type = contact_types[0] if contact_types else 'unknown'
        
        # Create resolved entity
        resolved_entity = ResolvedEntity(
            merge_key=merge_key,
            confidence_score=min(100, int(avg_confidence)),
            contact_type=primary_contact_type,
            email=primary_email,
            name=primary_name,
            social_handles=all_handles,
            follower_count=int(avg_follower_count),
            bio=primary_bio,
            source_urls=list(all_source_urls),
            staging_contact_ids=[c.id for c in contacts]
        )
        
        return resolved_entity

class ClusterAnalyzer:
    """Analyzes and clusters resolved entities"""
    
    def __init__(self):
        pass
    
    def analyze_clusters(self, resolved_entities: List[ResolvedEntity]) -> List[Dict[str, Any]]:
        """Analyze and create clusters from resolved entities"""
        clusters = []
        
        # Group by domain (potential management companies)
        domain_groups = {}
        for entity in resolved_entities:
            if entity.email:
                domain = entity.email.split('@')[1]
                if domain not in domain_groups:
                    domain_groups[domain] = []
                domain_groups[domain].append(entity)
        
        # Create clusters based on domain groups
        for domain, entities in domain_groups.items():
            if len(entities) > 1:  # Only cluster if multiple entities
                cluster = self._create_cluster(domain, entities)
                clusters.append(cluster)
        
        # Also create clusters based on similar names
        name_clusters = self._cluster_by_name_similarity(resolved_entities)
        clusters.extend(name_clusters)
        
        return clusters
    
    def _create_cluster(self, domain: str, entities: List[ResolvedEntity]) -> Dict[str, Any]:
        """Create a cluster based on domain"""
        all_emails = []
        all_names = []
        all_artists = []
        
        for entity in entities:
            if entity.email:
                all_emails.append(entity.email)
            if entity.name:
                all_names.append(entity.name)
        
        cluster = {
            "cluster_id": f"domain_{domain}",
            "domain": domain,
            "entities": [e.id for e in entities],
            "emails": all_emails,
            "names": all_names,
            "entity_count": len(entities),
            "confidence_score": min(100, len(entities) * 20),  # More entities = higher confidence
            "cluster_type": "domain_based"
        }
        
        # Calculate quality score
        quality_score = self._calculate_cluster_quality(cluster)
        cluster["quality_score"] = quality_score
        cluster["risk_level"] = get_cluster_risk_level(cluster)
        
        return cluster
    
    def _cluster_by_name_similarity(self, entities: List[ResolvedEntity]) -> List[Dict[str, Any]]:
        """Create clusters based on name similarity"""
        # This is a simplified implementation
        # In a real system, you'd use more sophisticated similarity algorithms
        clusters = []
        
        # Group entities by first few letters of name (simplified)
        name_groups = {}
        for entity in entities:
            if entity.name:
                name_prefix = entity.name.lower()[:3]  # First 3 letters
                if name_prefix not in name_groups:
                    name_groups[name_prefix] = []
                name_groups[name_prefix].append(entity)
        
        for prefix, entities in name_groups.items():
            if len(entities) > 1:
                cluster = {
                    "cluster_id": f"name_{prefix}",
                    "name_prefix": prefix,
                    "entities": [e.id for e in entities],
                    "entity_count": len(entities),
                    "confidence_score": min(100, len(entities) * 15),
                    "cluster_type": "name_based"
                }
                clusters.append(cluster)
        
        return clusters
    
    def _calculate_cluster_quality(self, cluster: Dict[str, Any]) -> float:
        """Calculate quality score for a cluster"""
        # Use the manager resolution utility
        quality_info = calculate_cluster_quality_score(cluster)
        return quality_info["quality_score"]

class PipelineProcessor:
    """Main processor that runs the entire pipeline"""
    
    def __init__(self):
        self.orchestrator = PipelineOrchestrator()
        self.normalizer = SignalNormalizer()
        self.resolver = EntityResolver()
        self.analyzer = ClusterAnalyzer()
    
    async def process_raw_signals(self, raw_signal_ids: List[int]) -> Dict[str, Any]:
        """Process raw signals through the entire pipeline"""
        db = SessionLocal()
        try:
            # Step 1: Get raw signals
            raw_signals = db.query(ScraperRawSignal).filter(
                ScraperRawSignal.id.in_(raw_signal_ids)
            ).all()
            
            # Step 2: Normalize signals
            all_staging_contacts = []
            for raw_signal in raw_signals:
                staging_contacts = self.normalizer.normalize_raw_signal(raw_signal)
                all_staging_contacts.extend(staging_contacts)
                
                # Advance state to normalized
                self.orchestrator.advance_state(raw_signal.id, PipelineState.NORMALIZED, "raw_signal")
            
            # Save staging contacts to database
            for staging_contact in all_staging_contacts:
                db.add(staging_contact)
            db.commit()
            
            # Step 3: Resolve entities
            resolved_entities = self.resolver.resolve_entities(all_staging_contacts)
            
            # Save resolved entities to database
            for entity in resolved_entities:
                db.add(entity)
            db.commit()
            
            # Step 4: Analyze clusters
            clusters = self.analyzer.analyze_clusters(resolved_entities)
            
            # Save clusters to database
            for i, cluster in enumerate(clusters):
                cluster_run = ClusterRun(
                    run_id=f"cluster_run_{datetime.utcnow().isoformat()}_{i}",
                    cluster_id=cluster["cluster_id"],
                    node_ids=cluster["entities"],
                    cluster_properties=cluster
                )
                db.add(cluster_run)
            db.commit()
            
            # Step 5: Score and verify
            for entity in resolved_entities:
                # Calculate trust scores
                evidence_items = []  # In a real system, you'd have evidence
                trust_scores = calculate_evidence_trust_score(evidence_items)
                entity.confidence_score = trust_scores.get("overall_trust_score", entity.confidence_score)
                
                # Advance state to scored
                self.orchestrator.advance_state(entity.id, PipelineState.SCORED, "resolved_entity")
            
            db.commit()
            
            # Step 6: Mark as ready to send (if quality is high enough)
            for entity in resolved_entities:
                quality_info = calculate_cluster_quality_score({
                    "emails": [entity.email] if entity.email else [],
                    "domains": [entity.email.split('@')[1]] if entity.email and '@' in entity.email else [],
                    "artist_count": 1,
                    "platform_count": 1,
                    "evidence": [],
                    "quality_score": entity.confidence_score,
                    "resolution_confidence": entity.confidence_score,
                    "surface_area_score": 10
                })
                
                if quality_info["quality_score"] >= 70:  # High quality threshold
                    self.orchestrator.advance_state(entity.id, PipelineState.READY_TO_SEND, "resolved_entity")
            
            db.commit()
            
            return {
                "status": "completed",
                "raw_signals_processed": len(raw_signals),
                "staging_contacts_created": len(all_staging_contacts),
                "resolved_entities_created": len(resolved_entities),
                "clusters_identified": len(clusters),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

# Singleton instance
pipeline_processor = PipelineProcessor()

def get_pipeline_processor() -> PipelineProcessor:
    """Get the pipeline processor instance"""
    return pipeline_processor