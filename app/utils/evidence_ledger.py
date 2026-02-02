"""
Evidence ledger system for tracking why we trust email addresses
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any
import json
from sqlalchemy.orm.attributes import flag_modified
from app.models.database import SessionLocal
from app.models.staging import ResolvedEntity

@dataclass
class Evidence:
    email: str
    source: str
    signal: str
    url: str
    timestamp: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = None

def log_evidence(email: str, source: str, signal: str, url: str, confidence: float = 1.0, metadata: Dict[str, Any] = None) -> Evidence:
    """
    Log evidence for an email address with machine-auditable trail
    """
    return Evidence(
        email=email,
        source=source,
        signal=signal,
        url=url,
        timestamp=datetime.utcnow().isoformat(),
        confidence=confidence,
        metadata=metadata or {}
    )

def store_evidence_in_db(evidence: Evidence):
    """
    Store evidence in the database for audit trail
    """
    db = SessionLocal()
    try:
        # In a real implementation, we'd have an evidence table
        # For now, we'll add it to the resolved entity's provenance
        resolved_entity = db.query(ResolvedEntity).filter(
            ResolvedEntity.email == evidence.email
        ).first()

        if resolved_entity:
            # Add evidence to provenance
            if not resolved_entity.source_urls:
                resolved_entity.source_urls = []
            new_evidence = {
                "source": evidence.source,
                "signal": evidence.signal,
                "url": evidence.url,
                "timestamp": evidence.timestamp,
                "confidence": evidence.confidence,
                "metadata": evidence.metadata
<<<<<<< HEAD
            }
            resolved_entity.source_urls = [*resolved_entity.source_urls, new_evidence]
=======
            })
            # Notify SQLAlchemy of the in-place mutation
            flag_modified(resolved_entity, 'source_urls')
>>>>>>> 6495f98 (loc)
            db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

def get_evidence_for_email(email: str) -> List[Evidence]:
    """
    Retrieve all evidence for a given email
    """
    db = SessionLocal()
    try:
        resolved_entity = db.query(ResolvedEntity).filter(
            ResolvedEntity.email == email
        ).first()
        
        if resolved_entity and resolved_entity.source_urls:
            # Convert stored evidence back to Evidence objects
            evidence_list = []
            for item in resolved_entity.source_urls:
                evidence_list.append(Evidence(
                    email=email,
                    source=item.get("source", ""),
                    signal=item.get("signal", ""),
                    url=item.get("url", ""),
                    timestamp=item.get("timestamp", ""),
                    confidence=item.get("confidence", 1.0),
                    metadata=item.get("metadata", {})
                ))
            return evidence_list
        return []
    finally:
        db.close()

def calculate_trust_score(email: str) -> float:
    """
    Calculate trust score based on accumulated evidence
    """
    evidence_list = get_evidence_for_email(email)
    if not evidence_list:
        return 0.0
    
    # Weight different types of evidence
    evidence_weights = {
        "official_site": 1.0,
        "social_bio": 0.8,
        "mirror": 0.6,
        "whois": 0.9,
        "press_kit": 0.95
    }
    
    total_score = 0.0
    total_weight = 0.0
    
    for evidence in evidence_list:
        weight = evidence_weights.get(evidence.signal, 0.5)
        score = evidence.confidence * weight
        total_score += score
        total_weight += weight
    
    return total_score / total_weight if total_weight > 0 else 0.0