"""
Temporal signal strength and freshness scoring system
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
import math

def freshness_weight(timestamp: str) -> float:
    """
    Calculate freshness weight based on how recent the signal is
    """
    try:
        if isinstance(timestamp, str):
            # Parse ISO format timestamp
            signal_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            signal_time = timestamp
            
        now = datetime.utcnow()
        age = now - signal_time
        
        # Freshness weights: newer signals are more valuable
        if age < timedelta(days=7):  # Less than a week
            return 1.0
        elif age < timedelta(days=30):  # Less than a month
            return 0.8
        elif age < timedelta(days=90):  # Less than 3 months
            return 0.6
        elif age < timedelta(days=180):  # Less than 6 months
            return 0.4
        elif age < timedelta(days=365):  # Less than a year
            return 0.2
        else:  # Older than a year
            return 0.1
    except Exception:
        # If timestamp parsing fails, assume old
        return 0.1

def decay_confidence_over_time(base_score: float, last_seen: datetime, decay_rate: float = 0.05) -> float:
    """
    Apply temporal decay to confidence scores
    """
    if not last_seen:
        return base_score
    
    days_since_seen = (datetime.utcnow() - last_seen).days
    decay_factor = math.exp(-decay_rate * days_since_seen)
    return max(0, base_score * decay_factor)

def calculate_temporal_score(evidence_items: List[Dict[str, Any]]) -> float:
    """
    Calculate overall temporal score based on all evidence items
    """
    if not evidence_items:
        return 0.0
    
    total_weighted_score = 0.0
    total_weight = 0.0
    
    for evidence in evidence_items:
        confidence = evidence.get('confidence', 1.0)
        timestamp = evidence.get('timestamp')
        
        freshness = freshness_weight(timestamp)
        weighted_score = confidence * freshness
        
        total_weighted_score += weighted_score
        total_weight += freshness
    
    return total_weighted_score / total_weight if total_weight > 0 else 0.0

def get_signal_recency_category(timestamp: str) -> str:
    """
    Categorize signal recency
    """
    try:
        if isinstance(timestamp, str):
            signal_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            signal_time = timestamp
            
        now = datetime.utcnow()
        age = now - signal_time
        
        if age < timedelta(days=7):
            return "fresh"
        elif age < timedelta(days=30):
            return "recent"
        elif age < timedelta(days=90):
            return "established"
        elif age < timedelta(days=365):
            return "old"
        else:
            return "archived"
    except:
        return "unknown"

def calculate_evidence_trust_score(evidence_items: List[Dict[str, Any]],
                                 source_weights: Dict[str, float] = None) -> Dict[str, float]:
    """
    Calculate trust score considering both temporal and source factors
    """
    if source_weights is None:
        # Default source trust weights
        source_weights = {
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
    
    for evidence in evidence_items:
        confidence = evidence.get('confidence', 1.0)
        timestamp = evidence.get('timestamp')
        source = evidence.get('source', 'unknown')
        
        # Get source weight
        source_weight = source_weights.get(source, 0.5)
        
        # Get temporal weight
        temporal_weight = freshness_weight(timestamp)
        
        # Calculate weighted score
        weighted_score = confidence * source_weight * temporal_weight
        
        total_score += weighted_score
        total_weight += source_weight * temporal_weight
    
    overall_score = total_score / total_weight if total_weight > 0 else 0.0
    
    return {
        "overall_trust_score": overall_score,
        "temporal_score": calculate_temporal_strength(evidence_items),
        "source_trust_score": sum(e.get('confidence', 1.0) * source_weights.get(e.get('source', 'unknown'), 0.5)
                                  for e in evidence_items) / len(evidence_items) if evidence_items else 0.0
    }

def calculate_temporal_strength(evidence_items: List[Dict[str, Any]]) -> float:
    """
    Calculate temporal strength score based on all evidence items
    """
    if not evidence_items:
        return 0.0

    total_weighted_score = 0.0
    total_weight = 0.0

    for evidence in evidence_items:
        confidence = evidence.get('confidence', 1.0)
        timestamp = evidence.get('timestamp')

        temporal_weight = freshness_weight(timestamp)
        weighted_score = confidence * temporal_weight

        total_weighted_score += weighted_score
        total_weight += temporal_weight

    return total_weighted_score / total_weight if total_weight > 0 else 0.0

def should_refresh_signal(timestamp: str, max_age_days: int = 90) -> bool:
    """
    Determine if a signal should be refreshed based on age
    """
    try:
        if isinstance(timestamp, str):
            signal_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            signal_time = timestamp
            
        age = (datetime.utcnow() - signal_time).days
        return age > max_age_days
    except:
        # If parsing fails, assume it needs refresh
        return True

def calculate_manager_activity_score(contact_records: List[Dict[str, Any]]) -> float:
    """
    Calculate manager activity based on recency of signals
    """
    if not contact_records:
        return 0.0
    
    recent_signals = 0
    total_signals = len(contact_records)
    
    for record in contact_records:
        timestamp = record.get('timestamp')
        if freshness_weight(timestamp) >= 0.6:  # Recent (within 3 months)
            recent_signals += 1
    
    return (recent_signals / total_signals) * 100 if total_signals > 0 else 0.0

def calculate_signal_consistency_score(evidence_items: List[Dict[str, Any]]) -> float:
    """
    Calculate how consistent signals are over time
    """
    if len(evidence_items) < 2:
        return 100.0 if evidence_items else 0.0
    
    # Sort by timestamp
    sorted_evidence = sorted(evidence_items, key=lambda x: x.get('timestamp', ''))
    
    # Calculate gaps between signals
    total_gap = 0
    gaps = []
    
    for i in range(1, len(sorted_evidence)):
        prev_time = datetime.fromisoformat(sorted_evidence[i-1]['timestamp'].replace('Z', '+00:00'))
        curr_time = datetime.fromisoformat(sorted_evidence[i]['timestamp'].replace('Z', '+00:00'))
        gap = (curr_time - prev_time).days
        gaps.append(gap)
        total_gap += gap
    
    avg_gap = total_gap / len(gaps) if gaps else 0
    
    # Lower average gap means more consistent signals
    # Cap at 365 days for normalization
    normalized_gap = min(avg_gap, 365)
    consistency_score = max(0, 100 - (normalized_gap / 365 * 100))
    
    return consistency_score

def get_optimal_refresh_interval(evidence_items: List[Dict[str, Any]]) -> int:
    """
    Suggest optimal refresh interval based on signal patterns
    """
    if not evidence_items:
        return 90  # Default to 3 months
    
    # Calculate average time between signals
    sorted_evidence = sorted(evidence_items, key=lambda x: x.get('timestamp', ''))
    
    if len(sorted_evidence) < 2:
        return 90  # Default if insufficient data
    
    gaps = []
    for i in range(1, len(sorted_evidence)):
        prev_time = datetime.fromisoformat(sorted_evidence[i-1]['timestamp'].replace('Z', '+00:00'))
        curr_time = datetime.fromisoformat(sorted_evidence[i]['timestamp'].replace('Z', '+00:00'))
        gap = (curr_time - prev_time).days
        gaps.append(gap)
    
    if not gaps:
        return 90
    
    avg_gap = sum(gaps) / len(gaps)
    
    # Suggest refresh interval as half the average gap, but within reasonable bounds
    suggested_interval = max(7, min(180, int(avg_gap / 2)))  # Between 1 week and 6 months
    return suggested_interval