"""
Evidence Ledger - Machine-auditable contact verification

This module provides:
- Evidence storage with full provenance tracking
- Trust score calculation based on evidence quality
- Legal defensibility through complete audit trails
- Temporal awareness with freshness-weighted scoring
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from typing import List, Dict, Optional
from loguru import logger

from app.models.database import Base


class Evidence(Base):
    """
    Evidence record for contact verification
    
    Each piece of evidence is tracked with:
    - Source: Where the evidence was found (official_site, social_bio, whois, etc.)
    - Signal: What type of signal it is (bio_email, whois_email, contact_form, etc.)
    - URL: The exact URL where evidence was found
    - Confidence: Initial confidence score based on source reliability
    - Metadata: Additional context about the evidence
    """
    __tablename__ = "evidence"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("resolved_entities.id"), nullable=False, index=True)
    
    # Evidence details
    email = Column(String(255), nullable=False, index=True)
    source = Column(String(100), nullable=False)  # official_site, social_bio, whois, press_kit, etc.
    signal = Column(String(100), nullable=False)  # bio_email, whois_email, contact_form, etc.
    url = Column(Text)  # Source URL where evidence was found
    
    # Scoring
    confidence = Column(Float, default=1.0)  # Initial confidence score (0-1)
    trust_score = Column(Float, default=0.0)  # Calculated trust score
    
    # Metadata
    metadata = Column(JSON, default=dict)  # Additional context (screenshot, html snippet, etc.)
    found_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    entity = relationship("ResolvedEntity", back_populates="evidence")
    
    __table_args__ = (
        Index('idx_evidence_entity_email', 'entity_id', 'email'),
        Index('idx_evidence_source', 'source'),
        Index('idx_evidence_signal', 'signal'),
    )
    
    def to_dict(self) -> dict:
        """Convert evidence to dictionary"""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "email": self.email,
            "source": self.source,
            "signal": self.signal,
            "url": self.url,
            "confidence": self.confidence,
            "trust_score": self.trust_score,
            "metadata": self.metadata,
            "found_at": self.found_at.isoformat() if self.found_at else None
        }
    
    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, entity={self.entity_id}, email={self.email}, source={self.source})>"


class EvidenceSource:
    """
    Evidence source types with reliability scores
    
    Sources are ranked by reliability:
    1. Official website contact page (highest)
    2. Verified social media bios
    3. Domain WHOIS records
    4. Press kits and media resources
    5. Third-party databases (lowest)
    """
    
    # Source reliability scores (0-1)
    RELIABILITY_SCORES = {
        "official_site": 1.0,        # Official website
        "verified_social": 0.9,      # Verified social media
        "whois": 0.8,               # Domain registration
        "press_kit": 0.85,          # Official press kit
        "interview": 0.7,           # Published interview
        "database": 0.6,            # Third-party database
        "user_submitted": 0.4,      # User submission
        "inferred": 0.3,            # Inferred from context
    }
    
    @classmethod
    def get_reliability(cls, source: str) -> float:
        """Get reliability score for a source type"""
        return cls.RELIABILITY_SCORES.get(source, 0.5)
    
    @classmethod
    def get_all_sources(cls) -> List[str]:
        """Get all known source types"""
        return list(cls.RELIABILITY_SCORES.keys())


class SignalType:
    """
    Signal types with confidence modifiers
    
    Signals are ranked by confidence:
    1. Direct email in bio (highest)
    2. Contact form submission
    3. Email in WHOIS record
    4. Email pattern inference (lowest)
    """
    
    # Signal confidence modifiers
    CONFIDENCE_MODIFIERS = {
        "bio_email": 1.0,           # Email directly in bio
        "contact_page": 0.95,       # Contact page email
        "whois_email": 0.8,         # WHOIS record email
        "press_email": 0.9,         # Press contact email
        "pattern_match": 0.6,       # Inferred from pattern
        "social_handle": 0.7,       # Social media handle
        "phone_number": 0.85,       # Phone number
    }
    
    @classmethod
    def get_confidence(cls, signal: str) -> float:
        """Get confidence modifier for a signal type"""
        return cls.CONFIDENCE_MODIFIERS.get(signal, 0.5)
    
    @classmethod
    def get_all_signals(cls) -> List[str]:
        """Get all known signal types"""
        return list(cls.CONFIDENCE_MODIFIERS.keys())


class EvidenceLedger:
    """
    Evidence ledger for tracking and calculating trust scores
    
    Usage:
        ledger = EvidenceLedger(db)
        
        # Add evidence
        evidence = ledger.add_evidence(
            entity_id=123,
            email="manager@example.com",
            source="official_site",
            signal="bio_email",
            url="https://example.com/contact"
        )
        
        # Calculate trust score
        trust_score = ledger.calculate_trust_score("manager@example.com")
    """
    
    def __init__(self, db_session):
        """
        Initialize evidence ledger
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def add_evidence(
        self,
        entity_id: int,
        email: str,
        source: str,
        signal: str,
        url: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Evidence:
        """
        Add a new piece of evidence
        
        Args:
            entity_id: Resolved entity ID
            email: Email address
            source: Source type (official_site, social_bio, etc.)
            signal: Signal type (bio_email, whois_email, etc.)
            url: Source URL
            metadata: Additional metadata
            
        Returns:
            Evidence record
        """
        # Calculate initial confidence
        source_reliability = EvidenceSource.get_reliability(source)
        signal_confidence = SignalType.get_confidence(signal)
        initial_confidence = (source_reliability + signal_confidence) / 2
        
        evidence = Evidence(
            entity_id=entity_id,
            email=email.lower().strip(),
            source=source,
            signal=signal,
            url=url,
            confidence=initial_confidence,
            trust_score=initial_confidence,  # Initial trust = confidence
            metadata=metadata or {}
        )
        
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        
        logger.info(f"Added evidence: {email} from {source}/{signal} (confidence: {initial_confidence:.2f})")
        
        return evidence
    
    def get_evidence_for_entity(self, entity_id: int) -> List[Evidence]:
        """
        Get all evidence for an entity
        
        Args:
            entity_id: Entity ID
            
        Returns:
            List of Evidence records
        """
        return self.db.query(Evidence).filter(
            Evidence.entity_id == entity_id
        ).order_by(Evidence.found_at.desc()).all()
    
    def get_evidence_for_email(self, email: str) -> List[Evidence]:
        """
        Get all evidence for an email address
        
        Args:
            email: Email address
            
        Returns:
            List of Evidence records
        """
        return self.db.query(Evidence).filter(
            Evidence.email == email.lower().strip()
        ).order_by(Evidence.found_at.desc()).all()
    
    def calculate_trust_score(self, email: str) -> float:
        """
        Calculate trust score for an email address
        
        Trust score is calculated from:
        1. Number of independent sources
        2. Source reliability scores
        3. Signal confidence scores
        4. Temporal freshness
        
        Args:
            email: Email address
            
        Returns:
            Trust score (0-100)
        """
        evidence_list = self.get_evidence_for_email(email)
        
        if not evidence_list:
            return 0.0
        
        # Calculate base score from evidence
        total_weight = 0
        weighted_score = 0
        
        for evidence in evidence_list:
            # Weight by recency (newer evidence weighs more)
            age_days = (datetime.now(timezone.utc) - evidence.found_at.replace(tzinfo=timezone.utc)).days
            recency_weight = max(0.5, 1.0 - (age_days / 365))  # Decay over 1 year
            
            weight = evidence.confidence * recency_weight
            weighted_score += evidence.confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Normalize to 0-100 scale
        base_score = (weighted_score / total_weight) * 100
        
        # Apply bonus for multiple independent sources
        unique_sources = len(set(e.source for e in evidence_list))
        if unique_sources >= 3:
            base_score = min(100, base_score * 1.2)  # 20% bonus for 3+ sources
        elif unique_sources >= 2:
            base_score = min(100, base_score * 1.1)  # 10% bonus for 2+ sources
        
        return round(base_score, 2)
    
    def update_trust_scores(self, entity_id: int) -> Dict[str, float]:
        """
        Update trust scores for all emails associated with an entity
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Dictionary of email -> trust_score
        """
        evidence_list = self.get_evidence_for_entity(entity_id)
        
        scores = {}
        unique_emails = set(e.email for e in evidence_list)
        
        for email in unique_emails:
            score = self.calculate_trust_score(email)
            scores[email] = score
            
            # Update evidence records
            for evidence in evidence_list:
                if evidence.email == email:
                    evidence.trust_score = score / 100  # Store as 0-1
        
        self.db.commit()
        
        logger.info(f"Updated trust scores for {len(scores)} emails on entity {entity_id}")
        
        return scores
    
    def get_audit_trail(self, entity_id: int) -> List[dict]:
        """
        Get complete audit trail for an entity
        
        Args:
            entity_id: Entity ID
            
        Returns:
            List of evidence records in chronological order
        """
        evidence_list = self.get_evidence_for_entity(entity_id)
        return [e.to_dict() for e in evidence_list]


# Convenience function to get ledger instance
def get_evidence_ledger(db_session):
    """Get EvidenceLedger instance"""
    return EvidenceLedger(db_session)
