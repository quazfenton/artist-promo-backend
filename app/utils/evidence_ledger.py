"""
Evidence ledger system for tracking why we trust email addresses

This module provides machine-auditable evidence tracking for contact
verification, enabling legal defensibility and explainable automation.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm.attributes import flag_modified
from loguru import logger

from app.models.database import SessionLocal
from app.models.staging import ResolvedEntity, Evidence


@dataclass
class EvidenceRecord:
    """Data class for evidence records"""
    email: str
    source: str
    signal: str
    url: str
    timestamp: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = None


def log_evidence(
    email: str, 
    source: str, 
    signal: str, 
    url: str, 
    confidence: float = 1.0, 
    metadata: Dict[str, Any] = None
) -> EvidenceRecord:
    """
    Create evidence record for an email address
    
    Args:
        email: Email address being verified
        source: Source of evidence (official_site, social_bio, mirror, whois, press_kit)
        signal: Signal type (bio_email, whois_email, link_in_bio, etc.)
        url: URL where evidence was found
        confidence: Confidence score (0.0-1.0)
        metadata: Additional context (screenshot_hash, page_title, etc.)
        
    Returns:
        EvidenceRecord object
    """
    return EvidenceRecord(
        email=email,
        source=source,
        signal=signal,
        url=url,
        timestamp=datetime.utcnow().isoformat(),
        confidence=confidence,
        metadata=metadata or {}
    )


def store_evidence_in_db(
    evidence: EvidenceRecord, 
    entity_id: Optional[int] = None, 
    email: Optional[str] = None
) -> Optional[Evidence]:
    """
    Store evidence in the database with proper foreign key relationship
    
    Args:
        evidence: EvidenceRecord to store
        entity_id: ResolvedEntity ID (if known)
        email: Email to lookup entity by (if entity_id not provided)
        
    Returns:
        Evidence object if successful, None otherwise
        
    Raises:
        ValueError: If neither entity_id nor email is provided
    """
    db = SessionLocal()
    try:
        # Find entity
        if entity_id:
            resolved_entity = db.query(ResolvedEntity).filter(
                ResolvedEntity.id == entity_id
            ).first()
        elif email:
            resolved_entity = db.query(ResolvedEntity).filter(
                ResolvedEntity.email == email
            ).first()
        else:
            raise ValueError("Either entity_id or email must be provided")
        
        if not resolved_entity:
            logger.warning(f"No resolved entity found for email {email}")
            return None
        
        # Create evidence record
        evidence_obj = Evidence(
            entity_id=resolved_entity.id,
            email=evidence.email,
            source=evidence.source,
            signal=evidence.signal,
            url=evidence.url,
            confidence=evidence.confidence,
            metadata=evidence.metadata
        )
        
        db.add(evidence_obj)
        db.commit()
        db.refresh(evidence_obj)
        
        logger.info(
            f"Stored evidence {evidence_obj.id} for entity {resolved_entity.id}",
            extra={
                "evidence_id": evidence_obj.id,
                "entity_id": resolved_entity.id,
                "email": evidence.email,
                "source": evidence.source,
                "signal": evidence.signal
            }
        )
        
        return evidence_obj
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing evidence: {str(e)}", exc_info=True)
        return None
    finally:
        db.close()


def get_evidence_for_email(email: str) -> List[EvidenceRecord]:
    """
    Retrieve all evidence for a given email
    
    Args:
        email: Email address to lookup
        
    Returns:
        List of EvidenceRecord objects, empty list if none found
    """
    db = SessionLocal()
    try:
        resolved_entity = db.query(ResolvedEntity).filter(
            ResolvedEntity.email == email
        ).first()
        
        if not resolved_entity:
            return []
        
        # Query evidence table
        evidence_records = db.query(Evidence).filter(
            Evidence.entity_id == resolved_entity.id
        ).order_by(Evidence.created_at.desc()).all()
        
        # Convert to EvidenceRecord objects
        return [
            EvidenceRecord(
                email=e.email,
                source=e.source,
                signal=e.signal,
                url=e.url,
                timestamp=e.created_at.isoformat(),
                confidence=e.confidence,
                metadata=e.metadata
            )
            for e in evidence_records
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving evidence for {email}: {str(e)}", exc_info=True)
        return []
    finally:
        db.close()


def get_evidence_for_entity(entity_id: int) -> List[EvidenceRecord]:
    """
    Retrieve all evidence for a resolved entity
    
    Args:
        entity_id: ResolvedEntity ID
        
    Returns:
        List of EvidenceRecord objects
    """
    db = SessionLocal()
    try:
        evidence_records = db.query(Evidence).filter(
            Evidence.entity_id == entity_id
        ).order_by(Evidence.created_at.desc()).all()
        
        return [
            EvidenceRecord(
                email=e.email,
                source=e.source,
                signal=e.signal,
                url=e.url,
                timestamp=e.created_at.isoformat(),
                confidence=e.confidence,
                metadata=e.metadata
            )
            for e in evidence_records
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving evidence for entity {entity_id}: {str(e)}", exc_info=True)
        return []
    finally:
        db.close()


def calculate_trust_score(email: str) -> float:
    """
    Calculate trust score based on accumulated evidence
    
    Applies temporal decay and source weighting to calculate
    an overall trust score for an email address.
    
    Args:
        email: Email address to score
        
    Returns:
        Trust score (0.0-1.0)
    """
    from app.utils.temporal_scoring import freshness_weight
    
    evidence_list = get_evidence_for_email(email)
    if not evidence_list:
        return 0.0
    
    # Weight different types of evidence
    evidence_weights = {
        "official_site": 1.0,
        "social_bio": 0.8,
        "mirror": 0.6,
        "whois": 0.9,
        "press_kit": 0.95,
        "link_in_bio": 0.7,
        "forum": 0.4,
        "third_party": 0.5
    }
    
    total_score = 0.0
    total_weight = 0.0
    
    for evidence in evidence_list:
        # Get source weight
        source_weight = evidence_weights.get(evidence.source, 0.5)
        
        # Get temporal weight
        temporal_weight = freshness_weight(evidence.timestamp)
        
        # Calculate weighted score
        weighted_score = evidence.confidence * source_weight * temporal_weight
        total_score += weighted_score
        total_weight += source_weight * temporal_weight
    
    trust_score = total_score / total_weight if total_weight > 0 else 0.0
    
    logger.info(
        f"Calculated trust score {trust_score:.2f} for {email}",
        extra={
            "email": email,
            "trust_score": trust_score,
            "evidence_count": len(evidence_list)
        }
    )
    
    return trust_score


def update_entity_trust_scores() -> Dict[str, Any]:
    """
    Update trust scores for all resolved entities
    
    Returns:
        Dict with statistics about the update
    """
    db = SessionLocal()
    try:
        entities = db.query(ResolvedEntity).all()
        updated_count = 0
        total_score = 0.0
        
        for entity in entities:
            if entity.email:
                trust_score = calculate_trust_score(entity.email)
                entity.quality_score = trust_score * 100  # Convert to 0-100 scale
                updated_count += 1
                total_score += trust_score
        
        db.commit()
        
        avg_score = total_score / updated_count if updated_count > 0 else 0.0
        
        logger.info(
            f"Updated trust scores for {updated_count} entities",
            extra={
                "updated_count": updated_count,
                "average_score": avg_score,
                "total_entities": len(entities)
            }
        )
        
        return {
            "updated_count": updated_count,
            "average_score": avg_score,
            "total_entities": len(entities)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating trust scores: {str(e)}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()
