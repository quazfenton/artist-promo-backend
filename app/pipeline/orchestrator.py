"""
Pipeline orchestrator for the enhanced scraping pipeline
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.utils.email_utils import decode_obfuscated_email, validate_email_address
from app.utils.pipeline_state import PipelineState, PipelineStep
from app.utils.error_handler import handle_pipeline_error
from app.scrapers.social import scrape_social_platforms
from app.scrapers.pdf_metadata import extract_emails_from_document
from app.scrapers.captions import extract_video_captions_emails
from app.scrapers.reverse_image import extract_exif_emails
from app.scrapers.sample_packs import extract_sample_pack_producer_info
from app.scrapers.domain_infrastructure import comprehensive_domain_analysis
from app.scrapers.event_venues import extract_venue_booking_contacts
from app.scrapers.conference_academic import extract_conference_speaker_contacts
from app.scrapers.general_docs import batch_extract_from_documents
from app.models.database import SessionLocal, ScraperRawSignal, StagingContact, ResolvedEntity

logger = logging.getLogger(__name__)

# Stub implementations for missing scraper functions
async def extract_contact_from_music_platform(url):
    """Stub implementation for music platform contact extraction"""
    logger.warning(f"Music platform scraper not implemented for: {url}")
    return []

async def extract_contact_from_link_in_bio(url):
    """Stub implementation for link-in-bio contact extraction"""
    logger.warning(f"Link-in-bio scraper not implemented for: {url}")
    return []

async def extract_contact_from_press_kit(url):
    """Stub implementation for press kit contact extraction"""
    logger.warning(f"Press kit scraper not implemented for: {url}")
    return []

async def extract_contact_from_podcast_page(url):
    """Stub implementation for podcast page contact extraction"""
    logger.warning(f"Podcast page scraper not implemented for: {url}")
    return []

async def extract_contact_from_news_article(url):
    """Stub implementation for news article contact extraction"""
    logger.warning(f"News article scraper not implemented for: {url}")
    return []

async def extract_contact_from_general_web(url):
    """Stub implementation for general web contact extraction"""
    logger.warning(f"General web scraper not implemented for: {url}")
    return []

class PipelineStateManager:
    """Manage pipeline state and progress"""

    def __init__(self):
        pass

    async def initialize_pipeline(self, job_id: str, source_urls: List[str]) -> Dict[str, Any]:
        """Initialize pipeline state"""
        return {"job_id": job_id, "source_urls": source_urls}

    async def update_step_status(self, job_id: str, step: Any, status: str):
        """Update step status"""
        pass

    async def finalize_pipeline(self, job_id: str, results: Any) -> Dict[str, Any]:
        """Finalize pipeline"""
        return {"job_id": job_id, "results": results}

    async def fail_pipeline(self, job_id: str, error: str):
        """Mark pipeline as failed"""
        pass

class PipelineErrorHandler:
    """Handle pipeline errors"""

    def __init__(self):
        pass

    async def handle_error(self, job_id: str, error: Exception, step: str) -> Dict[str, Any]:
        """Handle pipeline error"""
        return {"job_id": job_id, "error": str(error), "step": step}

class PipelineOrchestrator:
    """Main orchestrator for the scraping and contact resolution pipeline"""

    def __init__(self):
        self.state_manager = PipelineStateManager()
        self.error_handler = PipelineErrorHandler()
    
    async def run_full_pipeline(self, source_urls: List[str], job_id: str) -> Dict[str, Any]:
        """Run the complete scraping and resolution pipeline"""
        try:
            # Initialize pipeline state
            pipeline_state = await self.state_manager.initialize_pipeline(
                job_id=job_id,
                source_urls=source_urls
            )
            
            # Step 1: Raw signal collection
            raw_signals = await self._collect_raw_signals(source_urls, job_id)
            await self.state_manager.update_step_status(job_id, PipelineStep.COLLECT_RAW_SIGNALS, "completed")
            
            # Step 2: Signal normalization
            normalized_signals = await self._normalize_signals(raw_signals)
            await self.state_manager.update_step_status(job_id, PipelineStep.NORMALIZE_SIGNALS, "completed")
            
            # Step 3: Entity resolution
            resolved_entities = await self._resolve_entities(normalized_signals)
            await self.state_manager.update_step_status(job_id, PipelineStep.RESOLVE_ENTITIES, "completed")
            
            # Step 4: Graph clustering
            clusters = await self._cluster_entities(resolved_entities)
            await self.state_manager.update_step_status(job_id, PipelineStep.CLUSTER_ENTITIES, "completed")
            
            # Step 5: Confidence scoring
            scored_clusters = await self._score_clusters(clusters)
            await self.state_manager.update_step_status(job_id, PipelineStep.SCORE_CLUSTERS, "completed")
            
            # Step 6: Verification
            verified_clusters = await self._verify_clusters(scored_clusters)
            await self.state_manager.update_step_status(job_id, PipelineStep.VERIFY_CONTACTS, "completed")
            
            # Step 7: Ready for outreach
            ready_clusters = await self._prepare_for_outreach(verified_clusters)
            await self.state_manager.update_step_status(job_id, PipelineStep.READY_FOR_OUTREACH, "completed")
            
            # Finalize pipeline
            final_result = await self.state_manager.finalize_pipeline(
                job_id=job_id,
                results=ready_clusters
            )
            
            return {
                "status": "completed",
                "job_id": job_id,
                "results": final_result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = await self.error_handler.handle_error(
                job_id=job_id,
                error=e,
                step="pipeline_execution"
            )
            
            await self.state_manager.fail_pipeline(job_id, str(e))
            
            return {
                "status": "failed",
                "job_id": job_id,
                "error": str(e),
                "error_details": error_info,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _collect_raw_signals(self, source_urls: List[str], job_id: str) -> List[Dict[str, Any]]:
        """Collect raw signals from various sources"""
        raw_signals = []
        
        for url in source_urls:
            try:
                # Determine source type and use appropriate scraper
                if any(platform in url.lower() for platform in ['instagram', 'twitter', 'youtube', 'tiktok', 'facebook']):
                    signals = await scrape_social_platforms([url])
                elif any(ext in url.lower() for ext in ['.pdf', '.doc', '.docx', '.ppt', '.pptx']):
                    signals = await extract_emails_from_document(url)
                elif any(platform in url.lower() for platform in ['spotify', 'apple', 'soundcloud']):
                    signals = await extract_contact_from_music_platform(url)
                elif any(platform in url.lower() for platform in ['linktr', 'bio.fm', 'beacons', 'linktree']):
                    signals = await extract_contact_from_link_in_bio(url)
                elif any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    signals = await extract_exif_emails(url)
                elif any(keyword in url.lower() for keyword in ['press', 'kit', 'media']):
                    signals = await extract_contact_from_press_kit(url)
                elif any(keyword in url.lower() for keyword in ['podcast', 'episode', 'show']):
                    signals = await extract_contact_from_podcast_page(url)
                elif any(keyword in url.lower() for keyword in ['blog', 'article', 'news']):
                    signals = await extract_contact_from_news_article(url)
                else:
                    # Default to general web scraping
                    signals = await extract_contact_from_general_web(url)
                
                # Format signals for database insertion
                for signal in signals:
                    raw_signal = {
                        "job_id": job_id,
                        "source_url": url,
                        "source_type": self._classify_source_type(url),
                        "payload": signal,
                        "confidence_score": signal.get("confidence", 80),  # Default confidence
                        "created_at": datetime.utcnow().isoformat()
                    }
                    raw_signals.append(raw_signal)
                    
            except Exception as e:
                logger.error(f"Error collecting signals from {url}: {str(e)}")
                # Continue with other URLs
                continue
        
        # Save raw signals to database and return the saved records with IDs
        db = SessionLocal()
        try:
            saved_raw_signals = []
            for signal_data in raw_signals:
                raw_signal = ScraperRawSignal(**signal_data)
                db.add(raw_signal)
                saved_raw_signals.append(raw_signal)
            db.commit()

            # Refresh to get the IDs
            for raw_signal in saved_raw_signals:
                db.refresh(raw_signal)
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving raw signals to database: {str(e)}")
            raise
        finally:
            db.close()

        # Return the saved raw signal records with IDs
        return saved_raw_signals
    
    async def _normalize_signals(self, raw_signals: List[Any]) -> List[Dict[str, Any]]:
        """Normalize raw signals into standardized format"""
        normalized_signals = []

        for raw_signal in raw_signals:
            try:
                # Handle both dict and ORM object formats
                if hasattr(raw_signal, 'payload'):
                    # This is an ORM object with attributes
                    payload = raw_signal.payload or {}
                    source_type = getattr(raw_signal, 'source_type', 'unknown')
                else:
                    # This is a dict
                    payload = raw_signal.get("payload", {})
                    source_type = raw_signal.get("source_type", "unknown")
                
                if source_type == "social":
                    normalized = self._normalize_social_signal(payload)
                elif source_type == "document":
                    normalized = self._normalize_document_signal(payload)
                elif source_type == "music_platform":
                    normalized = self._normalize_music_platform_signal(payload)
                elif source_type == "link_in_bio":
                    normalized = self._normalize_link_in_bio_signal(payload)
                elif source_type == "image":
                    normalized = self._normalize_image_signal(payload)
                elif source_type == "press_kit":
                    normalized = self._normalize_press_kit_signal(payload)
                elif source_type == "podcast":
                    normalized = self._normalize_podcast_signal(payload)
                elif source_type == "news":
                    normalized = self._normalize_news_signal(payload)
                else:
                    normalized = self._normalize_generic_signal(payload)
                
                # Add provenance information
                normalized["provenance"] = {
                    "original_source": raw_signal.get("source_url"),
                    "source_type": source_type,
                    "confidence_score": raw_signal.get("confidence_score", 80),
                    "extraction_timestamp": raw_signal.get("created_at")
                }
                
                normalized_signals.append(normalized)
                
            except Exception as e:
                logger.error(f"Error normalizing signal from {raw_signal.get('source_url')}: {str(e)}")
                continue  # Continue with other signals
        
        # Save normalized signals with proper raw_signal_id references
        db = SessionLocal()
        try:
            # Save normalized signals with proper raw_signal_id references
            for i, signal_data in enumerate(normalized_signals):
                # Get the raw signal ID from the already saved raw signal
                raw_signal_obj = raw_signals[i] if i < len(raw_signals) else None
                raw_signal_id = raw_signal_obj.id if raw_signal_obj and hasattr(raw_signal_obj, 'id') else None

                staging_contact = StagingContact(
                    raw_signal_id=raw_signal_id,
                    name=signal_data.get("name"),
                    email=signal_data.get("email"),
                    contact_type=signal_data.get("contact_type"),
                    social_handles=signal_data.get("social_handles"),
                    confidence_score=signal_data.get("confidence_score", 80),
                    platform_ids=signal_data.get("platform_ids"),
                    follower_count=signal_data.get("follower_count", 0),
                    bio=signal_data.get("bio"),
                    source_url=signal_data.get("source_url"),
                    provenance=signal_data.get("provenance")
                )
                db.add(staging_contact)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving normalized signals to database: {str(e)}")
            raise
        finally:
            db.close()
        
        return normalized_signals
    
    async def _resolve_entities(self, normalized_signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve entities by merging duplicates and enriching data"""
        # Group signals by potential merge keys (email, domain, name patterns)
        entity_groups = self._group_by_merge_key(normalized_signals)
        
        resolved_entities = []
        
        for merge_key, signals in entity_groups.items():
            try:
                # Merge signals for this entity
                resolved_entity = self._merge_entity_signals(signals)
                
                # Enrich with additional information
                enriched_entity = await self._enrich_entity(resolved_entity)
                
                resolved_entities.append(enriched_entity)
                
            except Exception as e:
                logger.error(f"Error resolving entity with key {merge_key}: {str(e)}")
                continue
        
        # Save resolved entities to database
        db = SessionLocal()
        try:
            for entity_data in resolved_entities:
                resolved_entity = ResolvedEntity(
                    merge_key=entity_data.get("merge_key"),
                    confidence_score=entity_data.get("confidence_score", 80),
                    contact_type=entity_data.get("contact_type"),
                    email=entity_data.get("email"),
                    name=entity_data.get("name"),
                    social_handles=entity_data.get("social_handles"),
                    follower_count=entity_data.get("follower_count", 0),
                    bio=entity_data.get("bio"),
                    source_urls=entity_data.get("source_urls", []),
                    provenance=entity_data.get("provenance", {})
                )
                db.add(resolved_entity)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving resolved entities to database: {str(e)}")
            raise
        finally:
            db.close()
        
        return resolved_entities
    
    async def _cluster_entities(self, resolved_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cluster entities based on relationships and commonalities"""
        # This would implement graph-based clustering
        # For now, we'll do basic clustering by domain and common connections
        clusters = []
        
        # Group by domain (potential management companies)
        domain_clusters = {}
        for entity in resolved_entities:
            email = entity.get("email")
            if email and "@" in email:
                domain = email.split("@")[1]
                if domain not in domain_clusters:
                    domain_clusters[domain] = []
                domain_clusters[domain].append(entity)
        
        # Create clusters from domain groups
        for domain, entities in domain_clusters.items():
            if len(entities) > 1:  # Only cluster if multiple entities
                cluster = {
                    "cluster_id": f"domain_{domain}",
                    "cluster_type": "domain_based",
                    "entities": entities,
                    "size": len(entities),
                    "domain": domain,
                    "confidence_score": min(100, len(entities) * 20)  # More entities = higher confidence
                }
                clusters.append(cluster)
        
        # Also cluster by common social connections
        social_clusters = self._cluster_by_social_connections(resolved_entities)
        clusters.extend(social_clusters)
        
        return clusters
    
    async def _score_clusters(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score clusters based on quality and completeness"""
        scored_clusters = []
        
        for cluster in clusters:
            try:
                # Calculate cluster quality score
                quality_score = self._calculate_cluster_quality(cluster)
                
                cluster["quality_score"] = quality_score
                cluster["readiness_score"] = self._calculate_readiness_score(cluster)
                
                scored_clusters.append(cluster)
                
            except Exception as e:
                logger.error(f"Error scoring cluster {cluster.get('cluster_id')}: {str(e)}")
                continue
        
        return scored_clusters
    
    async def _verify_clusters(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verify cluster members and validate contact information"""
        verified_clusters = []
        
        for cluster in clusters:
            try:
                # Verify emails in cluster
                verified_entities = []
                for entity in cluster.get("entities", []):
                    if entity.get("email"):
                        is_valid = await self._verify_email(entity["email"])
                        if is_valid:
                            entity["email_verified"] = True
                            verified_entities.append(entity)
                
                original_entity_count = len(cluster.get("entities", []))
                cluster["entities"] = verified_entities
                cluster["verification_rate"] = len(verified_entities) / original_entity_count if original_entity_count > 0 else 0
                
                verified_clusters.append(cluster)
                
            except Exception as e:
                logger.error(f"Error verifying cluster {cluster.get('cluster_id')}: {str(e)}")
                continue
        
        return verified_clusters
    
    async def _prepare_for_outreach(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare clusters for outreach by selecting best contacts"""
        ready_clusters = []
        
        for cluster in clusters:
            try:
                # Select the best contact from each cluster for outreach
                best_contact = self._select_best_contact_for_outreach(cluster)
                
                if best_contact:
                    cluster["primary_contact"] = best_contact
                    cluster["ready_for_outreach"] = True
                    ready_clusters.append(cluster)
                else:
                    cluster["ready_for_outreach"] = False
                    ready_clusters.append(cluster)
                
            except Exception as e:
                logger.error(f"Error preparing cluster {cluster.get('cluster_id')} for outreach: {str(e)}")
                continue
        
        return ready_clusters
    
    def _classify_source_type(self, url: str) -> str:
        """Classify source type based on URL"""
        url_lower = url.lower()
        
        if any(platform in url_lower for platform in ['instagram', 'twitter', 'youtube', 'tiktok', 'facebook']):
            return "social"
        elif any(platform in url_lower for platform in ['spotify', 'apple', 'soundcloud', 'bandcamp']):
            return "music_platform"
        elif any(ext in url_lower for ext in ['.pdf', '.doc', '.docx', '.ppt', '.pptx']):
            return "document"
        elif any(platform in url_lower for platform in ['linktr', 'bio.fm', 'beacons', 'linktree']):
            return "link_in_bio"
        elif any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
            return "image"
        elif any(keyword in url_lower for keyword in ['press', 'kit', 'media']):
            return "press_kit"
        elif any(keyword in url_lower for keyword in ['podcast', 'episode', 'show']):
            return "podcast"
        elif any(keyword in url_lower for keyword in ['blog', 'article', 'news']):
            return "news"
        else:
            return "general_web"
    
    def _normalize_social_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize social media signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "social_media_manager"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 80),
            "platform_ids": payload.get("platform_ids", {}),
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_document_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize document signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "document_contact"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 70),
            "platform_ids": {},
            "follower_count": 0,
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_music_platform_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize music platform signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "music_curator"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 75),
            "platform_ids": payload.get("platform_ids", {}),
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_link_in_bio_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize link-in-bio signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "link_in_bio_contact"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 65),
            "platform_ids": {},
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_image_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize image signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "image_metadata_contact"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 60),
            "platform_ids": {},
            "follower_count": 0,
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_press_kit_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize press kit signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "press_contact"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 85),
            "platform_ids": {},
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_podcast_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize podcast signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "podcast_host"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 70),
            "platform_ids": payload.get("platform_ids", {}),
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_news_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize news article signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "publicist"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 65),
            "platform_ids": {},
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _normalize_generic_signal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize generic signal"""
        return {
            "name": payload.get("name"),
            "email": payload.get("email"),
            "contact_type": payload.get("contact_type", "general_contact"),
            "social_handles": payload.get("social_handles", {}),
            "confidence_score": payload.get("confidence_score", 60),
            "platform_ids": {},
            "follower_count": payload.get("follower_count", 0),
            "bio": payload.get("bio"),
            "source_url": payload.get("source_url")
        }
    
    def _group_by_merge_key(self, signals: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group signals by potential merge keys"""
        groups = {}
        
        for signal in signals:
            email = signal.get("email")
            name = signal.get("name")
            
            # Create merge key
            if name and email:
                # Use domain + name combination when both are available
                domain = email.split("@")[1] if "@" in email else "unknown"
                key = f"domain_name:{domain}:{name.lower()}"
            elif email:
                # Use email as primary key when name is not available
                key = f"email:{email.lower()}"
            elif name:
                # Use name as fallback
                key = f"name:{name.lower()}"
            else:
                # Use source URL as last resort
                key = f"url:{signal.get('source_url', 'unknown')}"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(signal)
        
        return groups
    
    def _merge_entity_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple signals for the same entity"""
        if not signals:
            return {}
        
        # Start with first signal as base
        base = signals[0].copy()
        
        # Merge information from other signals
        for signal in signals[1:]:
            # Merge social handles
            base_social = base.get("social_handles", {})
            signal_social = signal.get("social_handles", {})
            base_social.update(signal_social)
            base["social_handles"] = base_social
            
            # Merge bio information (prefer longer, more detailed bios)
            signal_bio = signal.get("bio", "")
            base_bio = base.get("bio", "")
            if len(signal_bio) > len(base_bio):
                base["bio"] = signal_bio
            
            # Merge follower counts (take highest)
            signal_followers = signal.get("follower_count", 0)
            base_followers = base.get("follower_count", 0)
            base["follower_count"] = max(base_followers, signal_followers)
            
            # Merge source URLs
            signal_source = signal.get("source_url")
            base_sources = base.get("source_urls", [])
            if signal_source and signal_source not in base_sources:
                base_sources.append(signal_source)
            base["source_urls"] = base_sources
            
            # Update confidence score (average of all signals)
            signal_confidence = signal.get("confidence_score", 80)
            base_confidence = base.get("confidence_score", 80)
            base["confidence_score"] = (base_confidence + signal_confidence) / 2
        
        base["merge_key"] = f"merged:{base.get('email', base.get('name', 'unknown'))}"
        
        return base
    
    async def _enrich_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich entity with additional information"""
        enriched = entity.copy()
        
        # Enrich with domain analysis if email exists
        email = entity.get("email")
        if email and "@" in email:
            domain = email.split("@")[1]
            domain_analysis = await comprehensive_domain_analysis(domain)
            
            # Add domain reputation info
            enriched["domain_reputation"] = domain_analysis.get("reputation_score", 50)
            enriched["domain_trust_signals"] = domain_analysis.get("trust_signals", [])
        
        # Add social media verification if handles exist
        social_handles = entity.get("social_handles", {})
        if social_handles:
            verified_handles = await self._verify_social_handles(social_handles)
            enriched["social_handles_verified"] = verified_handles
        
        return enriched
    
    def _cluster_by_social_connections(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cluster entities based on shared social connections"""
        clusters = []
        
        # This is a simplified implementation
        # In a real system, you'd build a graph of connections
        # and use community detection algorithms
        
        # Group by common social handles
        handle_clusters = {}
        for entity in entities:
            social_handles = entity.get("social_handles", {})
            for platform, handle in social_handles.items():
                if handle:
                    key = f"{platform}:{handle.lower()}"
                    if key not in handle_clusters:
                        handle_clusters[key] = []
                    handle_clusters[key].append(entity)
        
        # Create clusters from handle groups
        for key, entities_in_cluster in handle_clusters.items():
            if len(entities_in_cluster) > 1:
                cluster = {
                    "cluster_id": f"social_{key}",
                    "cluster_type": "social_connection",
                    "entities": entities_in_cluster,
                    "size": len(entities_in_cluster),
                    "connection_key": key,
                    "confidence_score": min(100, len(entities_in_cluster) * 15)
                }
                clusters.append(cluster)
        
        return clusters
    
    def _calculate_cluster_quality(self, cluster: Dict[str, Any]) -> float:
        """Calculate quality score for a cluster"""
        entities = cluster.get("entities", [])
        if not entities:
            return 0
        
        # Calculate based on various factors
        total_confidence = sum(e.get("confidence_score", 0) for e in entities)
        avg_confidence = total_confidence / len(entities) if entities else 0
        
        # Boost for verified emails
        verified_count = sum(1 for e in entities if e.get("email_verified", False))
        verification_bonus = (verified_count / len(entities)) * 20
        
        # Boost for social media presence
        social_count = sum(1 for e in entities if e.get("social_handles"))
        social_bonus = min(10, social_count * 2)
        
        # Boost for domain reputation
        domain_reputation = sum(e.get("domain_reputation", 50) for e in entities) / len(entities) if entities else 50
        reputation_bonus = (domain_reputation / 100) * 15
        
        quality_score = avg_confidence + verification_bonus + social_bonus + reputation_bonus
        return min(100, quality_score)
    
    def _calculate_readiness_score(self, cluster: Dict[str, Any]) -> float:
        """Calculate readiness for outreach"""
        quality_score = cluster.get("quality_score", 0)
        verification_rate = cluster.get("verification_rate", 0)
        
        # Readiness is based on quality and verification
        readiness = (quality_score * 0.7) + (verification_rate * 100 * 0.3)
        return min(100, readiness)
    
    def _select_best_contact_for_outreach(self, cluster: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select the best contact from a cluster for outreach"""
        entities = cluster.get("entities", [])
        if not entities:
            return None
        
        # Sort by a combination of confidence, verification, and social presence
        def contact_score(entity):
            confidence = entity.get("confidence_score", 0)
            verified = 10 if entity.get("email_verified", False) else 0
            has_social = 5 if entity.get("social_handles") else 0
            has_bio = 5 if entity.get("bio") else 0
            follower_boost = min(15, (entity.get("follower_count", 0) / 1000))
            
            return confidence + verified + has_social + has_bio + follower_boost
        
        # Find entity with highest score
        best_entity = max(entities, key=contact_score)
        
        # Only return if meets minimum thresholds
        if contact_score(best_entity) >= 70:
            return best_entity
        else:
            return None
    
    async def _verify_email(self, email: str) -> bool:
        """Verify email address"""
        # This would typically use an email verification service
        # For now, we'll just validate format and do a basic check
        return validate_email_address(email)
    
    async def _verify_social_handles(self, handles: Dict[str, str]) -> Dict[str, bool]:
        """Verify social media handles"""
        verified = {}
        
        for platform, handle in handles.items():
            try:
                # This would typically make API calls to verify handles
                # For now, we'll just return True for all handles
                verified[handle] = True
            except Exception:
                verified[handle] = False
        
        return verified

# Global instance
pipeline_orchestrator = PipelineOrchestrator()

def get_pipeline_orchestrator() -> PipelineOrchestrator:
    """Get the pipeline orchestrator instance"""
    return pipeline_orchestrator