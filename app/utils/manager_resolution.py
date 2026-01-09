"""
Manager resolution confidence and clustering system
"""
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict
import math
from app.utils.temporal_scoring import calculate_temporal_strength, calculate_evidence_trust_score

def calculate_manager_resolution_confidence(cluster: Dict[str, Any]) -> float:
    """
    Calculate confidence in manager resolution based on multiple signals
    """
    signals = 0
    
    # Email count contributes to confidence (more emails = more confidence)
    email_count = len(cluster.get("emails", []))
    signals += email_count * 2
    
    # Domain count contributes (different domains suggest real entity)
    domain_count = len(cluster.get("domains", []))
    signals += domain_count * 3
    
    # Platform presence (more platforms = more confidence)
    platform_count = cluster.get("platform_count", 1)
    signals += platform_count
    
    # Evidence count (more evidence = more confidence)
    evidence_count = len(cluster.get("evidence", []))
    signals += evidence_count * 1.5
    
    # Temporal consistency (longer history = more confidence)
    temporal_score = cluster.get("temporal_score", 0)
    signals += temporal_score * 0.5
    
    # Trust score from evidence
    trust_score = cluster.get("trust_score", 0)
    signals += trust_score * 0.3
    
    # Cap at 100
    confidence = min(100, signals * 2)  # Scale factor to make it reasonable
    return confidence

def calculate_contact_surface_area(cluster: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate contact surface area - how exposed/reachable this manager is
    """
    emails = cluster.get("emails", [])
    domains = cluster.get("domains", [])
    platform_count = cluster.get("platform_count", 1)
    
    return {
        "email_count": len(emails),
        "domain_count": len(domains),
        "platform_count": platform_count,
        "surface_score": (
            len(emails) +
            2 * len(domains) +  # Domains are more valuable
            platform_count
        )
    }

def classify_manager(cluster: Dict[str, Any]) -> str:
    """
    Classify manager type based on cluster characteristics
    """
    artist_count = cluster.get("artist_count", 0)
    email_count = len(cluster.get("emails", []))
    domain_count = len(cluster.get("domains", []))
    
    if artist_count >= 10 or (artist_count >= 5 and domain_count >= 2):
        return "AGENCY"
    elif artist_count >= 3 or (artist_count >= 2 and email_count >= 2):
        return "BOUTIQUE_MANAGER"
    elif artist_count >= 1:
        return "SOLO_MANAGER"
    else:
        return "UNKNOWN"

def calculate_cluster_stability(cluster: Dict[str, Any]) -> float:
    """
    Calculate how stable/consistent the cluster is
    """
    emails = cluster.get("emails", [])
    domains = cluster.get("domains", [])
    platforms = cluster.get("platforms", [])
    evidence = cluster.get("evidence", [])
    
    stability_factors = []
    
    # Email consistency (more emails = more stable)
    if len(emails) >= 3:
        stability_factors.append(1.0)
    elif len(emails) >= 2:
        stability_factors.append(0.7)
    elif len(emails) >= 1:
        stability_factors.append(0.4)
    else:
        stability_factors.append(0.1)
    
    # Domain diversity (more domains = more stable)
    if len(domains) >= 2:
        stability_factors.append(1.0)
    elif len(domains) >= 1:
        stability_factors.append(0.6)
    else:
        stability_factors.append(0.2)
    
    # Platform presence
    if len(platforms) >= 3:
        stability_factors.append(1.0)
    elif len(platforms) >= 2:
        stability_factors.append(0.7)
    elif len(platforms) >= 1:
        stability_factors.append(0.4)
    else:
        stability_factors.append(0.1)
    
    # Evidence consistency
    if len(evidence) >= 5:
        stability_factors.append(1.0)
    elif len(evidence) >= 3:
        stability_factors.append(0.8)
    elif len(evidence) >= 1:
        stability_factors.append(0.5)
    else:
        stability_factors.append(0.2)
    
    # Average stability score
    avg_stability = sum(stability_factors) / len(stability_factors) if stability_factors else 0.0
    return avg_stability * 100

def detect_manager_change(old_cluster: Dict[str, Any], new_cluster: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if there's been a manager change between clusters
    """
    old_domains = set(old_cluster.get("domains", []))
    new_domains = set(new_cluster.get("domains", []))
    
    old_emails = set(old_cluster.get("emails", []))
    new_emails = set(new_cluster.get("emails", []))
    
    # Check domain changes
    domain_change = old_domains != new_domains
    email_change = old_emails != new_emails
    
    # Calculate overlap
    domain_overlap = len(old_domains.intersection(new_domains))
    email_overlap = len(old_emails.intersection(new_emails))
    
    return {
        "domain_change": domain_change,
        "email_change": email_change,
        "domain_overlap_ratio": len(old_domains.intersection(new_domains)) / max(len(old_domains), len(new_domains), 1),
        "email_overlap_ratio": len(old_emails.intersection(new_emails)) / max(len(old_emails), len(new_emails), 1),
        "likely_change": domain_change or email_change,
        "change_severity": "HIGH" if (domain_change and email_change) else "MEDIUM" if (domain_change or email_change) else "LOW"
    }

def calculate_entity_merge_confidence(entity1: Dict[str, Any], entity2: Dict[str, Any], 
                                   similarity_threshold: float = 0.8) -> float:
    """
    Calculate confidence that two entities should be merged
    """
    # Calculate various similarity scores
    email_similarity = calculate_email_similarity(entity1.get("emails", []), entity2.get("emails", []))
    domain_similarity = calculate_domain_similarity(entity1.get("domains", []), entity2.get("domains", []))
    name_similarity = calculate_name_similarity(entity1.get("name", ""), entity2.get("name", ""))
    bio_similarity = calculate_bio_similarity(entity1.get("bio", ""), entity2.get("bio", ""))
    
    # Weighted average of similarities
    weighted_score = (
        email_similarity * 0.4 +      # Email similarity is most important
        domain_similarity * 0.3 +     # Domain similarity is important
        name_similarity * 0.2 +       # Name similarity is moderate
        bio_similarity * 0.1          # Bio similarity is supportive
    )
    
    return weighted_score * 100

def calculate_email_similarity(emails1: List[str], emails2: List[str]) -> float:
    """
    Calculate similarity between two sets of emails
    """
    if not emails1 and not emails2:
        return 1.0
    if not emails1 or not emails2:
        return 0.0
    
    set1 = set(emails1)
    set2 = set(emails2)
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0

def calculate_domain_similarity(domains1: List[str], domains2: List[str]) -> float:
    """
    Calculate similarity between two sets of domains
    """
    if not domains1 and not domains2:
        return 1.0
    if not domains1 or not domains2:
        return 0.0
    
    set1 = set(domains1)
    set2 = set(domains2)
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0

def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names (simple implementation)
    """
    if not name1 and not name2:
        return 1.0
    if not name1 or not name2:
        return 0.0
    
    name1_clean = name1.lower().replace(" ", "").replace(".", "")
    name2_clean = name2.lower().replace(" ", "").replace(".", "")
    
    # Simple character-based similarity
    if name1_clean == name2_clean:
        return 1.0
    
    # Calculate similarity based on common substrings
    common_chars = set(name1_clean) & set(name2_clean)
    total_chars = set(name1_clean) | set(name2_clean)
    
    return len(common_chars) / len(total_chars) if total_chars else 0.0

def calculate_bio_similarity(bio1: str, bio2: str) -> float:
    """
    Calculate similarity between two bios (simple implementation)
    """
    if not bio1 and not bio2:
        return 1.0
    if not bio1 or not bio2:
        return 0.0
    
    # Simple word-based similarity
    words1 = set(bio1.lower().split())
    words2 = set(bio2.lower().split())
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0

def calculate_cluster_influence_score(cluster: Dict[str, Any]) -> float:
    """
    Calculate influence score for a cluster based on various factors
    """
    # Factors that contribute to influence
    email_count = len(cluster.get("emails", []))
    domain_count = len(cluster.get("domains", []))
    artist_count = cluster.get("artist_count", 0)
    follower_sum = cluster.get("total_followers", 0)
    platform_count = cluster.get("platform_count", 1)
    
    # Calculate weighted influence score
    influence_score = (
        email_count * 5 +           # Each email adds influence
        domain_count * 10 +         # Domains are more influential
        artist_count * 15 +         # Each artist adds significant influence
        min(follower_sum / 10000, 50) +  # Followers (capped)
        platform_count * 3          # Platform presence
    )
    
    # Normalize to 0-100 scale
    normalized_score = min(100, influence_score / 2)  # Adjust divisor as needed
    return normalized_score

def calculate_cluster_quality_score(cluster: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate comprehensive quality score for a cluster
    """
    resolution_confidence = calculate_manager_resolution_confidence(cluster)
    stability_score = calculate_cluster_stability(cluster)
    influence_score = calculate_cluster_influence_score(cluster)
    surface_area = calculate_contact_surface_area(cluster)
    
    # Weighted quality score
    quality_score = (
        resolution_confidence * 0.4 +
        stability_score * 0.3 +
        influence_score * 0.2 +
        surface_area["surface_score"] * 0.1
    )
    
    return {
        "quality_score": min(100, quality_score),
        "resolution_confidence": resolution_confidence,
        "stability_score": stability_score,
        "influence_score": influence_score,
        "surface_area_score": surface_area["surface_score"],
        "manager_type": classify_manager(cluster)
    }

def should_merge_entities(entity1: Dict[str, Any], entity2: Dict[str, Any], 
                        confidence_threshold: float = 70) -> bool:
    """
    Determine if two entities should be merged based on confidence
    """
    confidence = calculate_entity_merge_confidence(entity1, entity2)
    return confidence >= confidence_threshold

def get_cluster_risk_level(cluster: Dict[str, Any]) -> str:
    """
    Assess risk level of contacting this cluster
    """
    quality_score = cluster.get("quality_score", 0)
    resolution_confidence = cluster.get("resolution_confidence", 0)
    surface_area_score = cluster.get("surface_area_score", 0)
    
    if quality_score >= 80 and resolution_confidence >= 80:
        return "LOW_RISK"
    elif quality_score >= 60 and resolution_confidence >= 60:
        return "MEDIUM_RISK"
    elif quality_score >= 40 and resolution_confidence >= 40:
        return "HIGH_RISK"
    else:
        return "EXTREME_RISK"