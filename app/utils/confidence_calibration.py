"""
Confidence decay and trust calibration system
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import math
from collections import defaultdict
import threading
from app.utils.temporal_scoring import freshness_weight
from app.utils.evidence_ledger import calculate_trust_score

class ConfidenceDecayManager:
    """Manages confidence decay over time"""
    
    def __init__(self, default_decay_rate: float = 0.05, days_to_half_life: int = 180):
        """
        Initialize with default decay parameters
        - default_decay_rate: exponential decay rate
        - days_to_half_life: number of days for confidence to halve
        """
        self.default_decay_rate = default_decay_rate
        self.days_to_half_life = days_to_half_life
        self.decay_rates = {}  # Per-entity custom decay rates
        self.lock = threading.RLock()
    
    def calculate_decayed_confidence(self, base_score: float, last_seen: datetime, 
                                   entity_id: str = None) -> float:
        """Calculate confidence after applying temporal decay"""
        if not last_seen:
            return base_score
        
        # Get entity-specific decay rate if available
        decay_rate = self.decay_rates.get(entity_id, self.default_decay_rate)
        
        days_since_seen = (datetime.utcnow() - last_seen).days
        decay_factor = math.exp(-decay_rate * days_since_seen)
        
        decayed_score = max(0, base_score * decay_factor)
        return min(100, decayed_score)  # Cap at 100
    
    def set_entity_decay_rate(self, entity_id: str, decay_rate: float):
        """Set custom decay rate for specific entity"""
        with self.lock:
            self.decay_rates[entity_id] = decay_rate
    
    def get_decay_rate(self, entity_id: str) -> float:
        """Get decay rate for entity"""
        return self.decay_rates.get(entity_id, self.default_decay_rate)
    
    def calculate_half_life_decay(self, base_score: float, last_seen: datetime, 
                                entity_id: str = None) -> float:
        """Calculate decay using half-life formula"""
        if not last_seen:
            return base_score
        
        days_since_seen = (datetime.utcnow() - last_seen).days
        
        # Half-life decay: score = base_score * (0.5)^(days/half_life)
        if self.days_to_half_life > 0:
            decay_factor = pow(0.5, days_since_seen / self.days_to_half_life)
            decayed_score = base_score * decay_factor
            return max(0, min(100, decayed_score))
        else:
            return base_score

class SourceTrustCalibrator:
    """Calibrates trust based on source reliability"""
    
    def __init__(self):
        # Default source trust weights
        self.source_weights = {
            "official_site": 1.0,
            "social_bio": 0.8,
            "mirror": 0.6,
            "whois": 0.9,
            "press_kit": 0.95,
            "link_in_bio": 0.7,
            "forum": 0.4,
            "third_party": 0.5,
            "nitter": 0.7,
            "invidious": 0.7,
            "imginn": 0.6,
            "proxitok": 0.6,
            "libreddit": 0.5,
            "web_scrape": 0.8,
            "manual_entry": 0.9,
            "api_response": 0.95
        }
        
        # Track source performance
        self.source_performance = defaultdict(lambda: {"successes": 0, "failures": 0})
        self.lock = threading.RLock()
    
    def get_source_weight(self, source: str) -> float:
        """Get trust weight for a source"""
        return self.source_weights.get(source, 0.3)  # Default low weight
    
    def update_source_performance(self, source: str, success: bool):
        """Update source performance metrics"""
        with self.lock:
            if success:
                self.source_performance[source]["successes"] += 1
            else:
                self.source_performance[source]["failures"] += 1
    
    def calculate_dynamic_source_weight(self, source: str) -> float:
        """Calculate dynamic weight based on source performance"""
        perf = self.source_performance[source]
        total = perf["successes"] + perf["failures"]
        
        if total == 0:
            return self.get_source_weight(source)
        
        # Performance ratio (0-1)
        performance_ratio = perf["successes"] / total
        
        # Base weight
        base_weight = self.get_source_weight(source)
        
        # Adjust based on performance
        adjusted_weight = base_weight * (0.7 + 0.3 * performance_ratio)  # Weight between 70-100% of base
        
        return min(1.0, max(0.1, adjusted_weight))  # Clamp between 0.1 and 1.0
    
    def weighted_signal(self, source: str, base_confidence: float = 1.0) -> float:
        """Apply source weighting to a signal"""
        weight = self.calculate_dynamic_source_weight(source)
        return base_confidence * weight
    
    def calibrate_evidence_trust(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate trust scores with source calibration"""
        if not evidence_items:
            return {"overall_trust": 0.0, "source_trust": 0.0, "temporal_trust": 0.0}
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for evidence in evidence_items:
            confidence = evidence.get('confidence', 1.0)
            source = evidence.get('source', 'unknown')
            timestamp = evidence.get('timestamp')
            
            # Get calibrated source weight
            source_weight = self.calculate_dynamic_source_weight(source)
            
            # Get temporal weight
            temporal_weight = freshness_weight(timestamp) if timestamp else 1.0
            
            # Calculate weighted score
            weighted_score = confidence * source_weight * temporal_weight
            
            total_weighted_score += weighted_score
            total_weight += source_weight * temporal_weight
        
        overall_trust = total_weighted_score / total_weight if total_weight > 0 else 0.0
        
        return {
            "overall_trust": overall_trust,
            "source_trust": sum(e.get('confidence', 1.0) * self.calculate_dynamic_source_weight(e.get('source', 'unknown')) 
                              for e in evidence_items) / len(evidence_items) if evidence_items else 0.0,
            "temporal_trust": sum(freshness_weight(e.get('timestamp')) if e.get('timestamp') else 1.0 
                                for e in evidence_items) / len(evidence_items) if evidence_items else 0.0
        }

class WrongContactDetector:
    """Detects and handles wrong contact responses"""
    
    def __init__(self):
        self.wrong_contacts = set()  # Set of emails marked as wrong
        self.contact_history = defaultdict(list)  # email -> [(timestamp, outcome)]
        self.lock = threading.RLock()
    
    def mark_wrong_contact(self, email: str):
        """Mark an email as wrong contact"""
        with self.lock:
            self.wrong_contacts.add(email)
            # Reduce confidence for this contact
            self._reduce_contact_confidence(email)
    
    def is_wrong_contact(self, email: str) -> bool:
        """Check if email is marked as wrong contact"""
        return email in self.wrong_contacts
    
    def record_contact_outcome(self, email: str, outcome: str, timestamp: datetime = None):
        """Record outcome of contact attempt"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.lock:
            self.contact_history[email].append((timestamp, outcome))
            
            # Clean old records (keep last 90 days)
            cutoff = datetime.utcnow() - timedelta(days=90)
            self.contact_history[email] = [
                (t, o) for t, o in self.contact_history[email] if t > cutoff
            ]
    
    def get_contact_reliability(self, email: str) -> float:
        """Get reliability score for contact (0-100)"""
        with self.lock:
            if email in self.wrong_contacts:
                return 0.0  # Completely unreliable
            
            outcomes = self.contact_history[email]
            if not outcomes:
                return 100.0  # No history, assume reliable
            
            # Calculate success rate
            successful_outcomes = sum(1 for _, outcome in outcomes if outcome in ['replied', 'positive', 'confirmed'])
            total_outcomes = len(outcomes)
            
            if total_outcomes == 0:
                return 100.0
            
            success_rate = successful_outcomes / total_outcomes
            return success_rate * 100
    
    def _reduce_contact_confidence(self, email: str, reduction: float = 40):
        """Reduce confidence for a contact"""
        # In a real system, this would update the contact's confidence score
        # For now, we'll just log it
        print(f"Reduced confidence for {email} by {reduction} points due to wrong contact marking")

class ManagerDriftTracker:
    """Tracks changes in artist-manager relationships over time"""
    
    def __init__(self):
        self.relationship_history = defaultdict(list)  # artist -> [(start_date, manager, end_date)]
        self.current_relationships = {}  # artist -> manager
        self.lock = threading.RLock()
    
    def record_relationship(self, artist: str, manager: str, start_date: datetime = None):
        """Record a new artist-manager relationship"""
        if start_date is None:
            start_date = datetime.utcnow()
        
        with self.lock:
            # End previous relationship if exists
            if artist in self.current_relationships:
                self.end_relationship(artist, start_date)
            
            # Start new relationship
            self.current_relationships[artist] = manager
            self.relationship_history[artist].append({
                "manager": manager,
                "start_date": start_date,
                "end_date": None
            })
    
    def end_relationship(self, artist: str, end_date: datetime = None):
        """End current relationship for an artist"""
        if end_date is None:
            end_date = datetime.utcnow()
        
        with self.lock:
            if artist in self.current_relationships:
                # Find the current (active) relationship
                for rel in reversed(self.relationship_history[artist]):
                    if rel["end_date"] is None:
                        rel["end_date"] = end_date
                        break
                
                del self.current_relationships[artist]
    
    def get_artist_history(self, artist: str) -> List[Dict[str, Any]]:
        """Get relationship history for an artist"""
        with self.lock:
            return self.relationship_history[artist].copy()
    
    def detect_manager_change(self, artist: str, new_manager: str) -> bool:
        """Detect if there's been a manager change"""
        with self.lock:
            current_manager = self.current_relationships.get(artist)
            return current_manager is not None and current_manager != new_manager
    
    def get_current_manager(self, artist: str) -> Optional[str]:
        """Get current manager for an artist"""
        return self.current_relationships.get(artist)
    
    def get_manager_artists(self, manager: str) -> List[str]:
        """Get all artists currently managed by a manager"""
        with self.lock:
            return [artist for artist, mgr in self.current_relationships.items() if mgr == manager]

class ColdStartSafety:
    """Provides safety mechanisms for cold start situations"""
    
    def __init__(self, min_confidence_threshold: float = 60.0):
        self.min_confidence_threshold = min_confidence_threshold
        self.low_confidence_warnings = []
        self.lock = threading.RLock()
    
    def is_safe_mode(self, cluster: Dict[str, Any]) -> bool:
        """Check if system should be in safe mode"""
        resolution_confidence = cluster.get("resolution_confidence", 0)
        top_email_confidence = 0
        
        if "scored_emails" in cluster and cluster["scored_emails"]:
            top_email_confidence = max(
                email.get("confidence", 0) for email in cluster["scored_emails"]
            )
        
        return (resolution_confidence < self.min_confidence_threshold or 
                top_email_confidence < 70)
    
    def should_allow_outreach(self, cluster: Dict[str, Any]) -> bool:
        """Check if outreach should be allowed for this cluster"""
        if self.is_safe_mode(cluster):
            return False
        
        # Check other safety conditions
        top_email = cluster.get("scored_emails", [{}])[0] if cluster.get("scored_emails") else {}
        confidence = top_email.get("confidence", 0)
        
        return confidence >= 70
    
    def add_warning(self, warning: str, timestamp: datetime = None):
        """Add a safety warning"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.lock:
            self.low_confidence_warnings.append({
                "warning": warning,
                "timestamp": timestamp,
                "cluster_id": None  # Could be tied to specific clusters
            })
    
    def get_safety_report(self) -> Dict[str, Any]:
        """Get safety status report"""
        with self.lock:
            return {
                "min_confidence_threshold": self.min_confidence_threshold,
                "warning_count": len(self.low_confidence_warnings),
                "recent_warnings": self.low_confidence_warnings[-10:]  # Last 10 warnings
            }

class SendReadinessGate:
    """Final arbiter before sending outreach"""
    
    def __init__(self, cooldown_scheduler, wrong_contact_detector, cold_start_safety):
        self.cooldown_scheduler = cooldown_scheduler
        self.wrong_contact_detector = wrong_contact_detector
        self.cold_start_safety = cold_start_safety
    
    def is_ready_to_send(self, cluster: Dict[str, Any]) -> bool:
        """Check if cluster is ready for outreach"""
        # Check if in safe mode
        if self.cold_start_safety.is_safe_mode(cluster):
            return False
        
        # Check top email confidence
        top_email = cluster.get("scored_emails", [{}])[0] if cluster.get("scored_emails") else {}
        if top_email.get("confidence", 0) < 70:
            return False
        
        # Check manager availability (if manager_id is provided)
        manager_id = cluster.get("manager_id")
        if manager_id:
            # In a real system, you'd check manager-specific limits
            # For now, we'll assume manager can receive
            pass
        
        # Check if email is marked as wrong contact
        email = top_email.get("email")
        if email and self.wrong_contact_detector.is_wrong_contact(email):
            return False
        
        # Check cooldown
        if email and not self.cooldown_scheduler.can_contact(email):
            return False
        
        return True

# Global instances
confidence_decay_manager = ConfidenceDecayManager()
source_trust_calibrator = SourceTrustCalibrator()
wrong_contact_detector = WrongContactDetector()
manager_drift_tracker = ManagerDriftTracker()
cold_start_safety = ColdStartSafety()
send_readiness_gate = SendReadinessGate(cooldown_scheduler, wrong_contact_detector, cold_start_safety)

def get_confidence_decay_manager() -> ConfidenceDecayManager:
    """Get the confidence decay manager instance"""
    return confidence_decay_manager

def get_source_trust_calibrator() -> SourceTrustCalibrator:
    """Get the source trust calibrator instance"""
    return source_trust_calibrator

def get_wrong_contact_detector() -> WrongContactDetector:
    """Get the wrong contact detector instance"""
    return wrong_contact_detector

def get_manager_drift_tracker() -> ManagerDriftTracker:
    """Get the manager drift tracker instance"""
    return manager_drift_tracker

def get_cold_start_safety() -> ColdStartSafety:
    """Get the cold start safety instance"""
    return cold_start_safety

def get_send_readiness_gate() -> SendReadinessGate:
    """Get the send readiness gate instance"""
    return send_readiness_gate