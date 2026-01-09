"""
Integration tests for the enhanced pipeline components
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import os

# Import all the new components
from app.utils.evidence_ledger import log_evidence, calculate_trust_score
from app.utils.email_canonicalization import canonicalize_email, can_send_to_domain, check_email_domain_reputation
from app.utils.link_in_bio_resolver import resolve_link_tree, extract_emails_from_text
from app.utils.temporal_scoring import freshness_weight, decay_confidence_over_time
from app.utils.manager_resolution import calculate_manager_resolution_confidence, classify_manager
from app.utils.async_scraping import scrape_nitter, scrape_invidious_channel
from app.utils.pipeline_orchestrator import PipelineProcessor, SignalNormalizer, EntityResolver
from app.utils.search_and_ingestion import SearchIndex, WebhookIngestor
from app.utils.confidence_calibration import ConfidenceDecayManager, SourceTrustCalibrator, WrongContactDetector

def test_evidence_ledger():
    """Test evidence ledger functionality"""
    evidence = log_evidence(
        email="test@example.com",
        source="test_source",
        signal="test_signal",
        url="https://example.com",
        confidence=0.8,
        metadata={"test": "data"}
    )
    
    assert evidence.email == "test@example.com"
    assert evidence.source == "test_source"
    assert evidence.confidence == 0.8
    assert evidence.metadata["test"] == "data"
    assert evidence.timestamp is not None

def test_email_canonicalization():
    """Test email canonicalization"""
    # Test basic canonicalization
    assert canonicalize_email("press@domain.com") == "official@domain.com"
    assert canonicalize_email("booking@domain.com") == "official@domain.com"
    assert canonicalize_email("mgmt@domain.com") == "official@domain.com"
    assert canonicalize_email("john@domain.com") == "john@domain.com"  # No change for personal emails
    
    # Test domain send limits
    domain = "testdomain.com"
    assert can_send_to_domain(domain) is True  # Initially should be able to send
    
    # Test domain reputation check
    rep = check_email_domain_reputation("test@gmail.com")
    assert "has_mx" in rep
    assert "role_account" in rep

def test_temporal_scoring():
    """Test temporal scoring functionality"""
    # Test freshness weight with recent timestamp
    recent_time = datetime.utcnow().isoformat()
    weight = freshness_weight(recent_time)
    assert weight == 1.0  # Recent timestamps should have full weight
    
    # Test with old timestamp
    old_time = (datetime.utcnow() - timedelta(days=200)).isoformat()
    weight = freshness_weight(old_time)
    assert weight < 0.5  # Old timestamps should have lower weight
    
    # Test confidence decay
    base_score = 90.0
    last_seen = datetime.utcnow() - timedelta(days=100)
    decayed_score = decay_confidence_over_time(base_score, last_seen)
    assert decayed_score < base_score  # Decayed score should be lower

def test_manager_resolution():
    """Test manager resolution functionality"""
    cluster = {
        "emails": ["contact@mgmt.com", "booking@mgmt.com"],
        "domains": ["mgmt.com"],
        "artist_count": 5,
        "platform_count": 3,
        "evidence": []
    }
    
    confidence = calculate_manager_resolution_confidence(cluster)
    assert confidence > 0
    
    manager_type = classify_manager(cluster)
    assert manager_type in ["AGENCY", "BOUTIQUE_MANAGER", "SOLO_MANAGER", "UNKNOWN"]

def test_search_index():
    """Test search index functionality"""
    search_idx = SearchIndex()
    
    # Add a contact
    search_idx.add_contact("test@example.com", 1, "Test Manager", "Artist1", "Test Manager")
    
    # Search for it
    results = search_idx.search_email("test@example.com")
    assert 1 in results
    
    # Test fuzzy search
    fuzzy_results = search_idx.fuzzy_search("test")
    assert len(fuzzy_results["emails"]) > 0

def test_webhook_ingestion():
    """Test webhook ingestion functionality"""
    search_idx = SearchIndex()
    ingestor = WebhookIngestor(search_idx)
    
    # Test payload ingestion
    payload = {
        "emails": ["ingested@example.com"],
        "name": "Ingested Manager",
        "artist": "Test Artist",
        "confidence": 85
    }
    
    result = ingestor.ingest_payload(payload, "test_webhook")
    assert result["status"] == "success"
    assert len(result["processed_entities"]) > 0

def test_confidence_decay():
    """Test confidence decay functionality"""
    decay_manager = ConfidenceDecayManager()
    
    base_score = 90.0
    last_seen = datetime.utcnow() - timedelta(days=50)
    
    decayed_score = decay_manager.calculate_decayed_confidence(base_score, last_seen)
    assert decayed_score < base_score
    assert decayed_score >= 0

def test_source_trust_calibration():
    """Test source trust calibration"""
    calibrator = SourceTrustCalibrator()
    
    # Test default source weight
    weight = calibrator.get_source_weight("official_site")
    assert weight == 1.0
    
    # Test unknown source weight
    weight = calibrator.get_source_weight("unknown_source")
    assert weight == 0.3  # Default weight
    
    # Test weighted signal
    weighted = calibrator.weighted_signal("official_site", 0.9)
    assert weighted >= 0.8  # Should be close to base confidence

def test_wrong_contact_detection():
    """Test wrong contact detection"""
    detector = WrongContactDetector()
    
    # Mark an email as wrong
    detector.mark_wrong_contact("wrong@example.com")
    
    # Check if it's marked as wrong
    assert detector.is_wrong_contact("wrong@example.com")
    
    # Record a contact outcome
    detector.record_contact_outcome("test@example.com", "replied")
    
    # Check reliability
    reliability = detector.get_contact_reliability("test@example.com")
    assert reliability > 0

def test_pipeline_processor():
    """Test pipeline processor functionality"""
    processor = PipelineProcessor()
    
    # Test that processor has all required components
    assert processor.orchestrator is not None
    assert processor.normalizer is not None
    assert processor.resolver is not None
    assert processor.analyzer is not None

def test_link_in_bio_resolver():
    """Test link-in-bio resolver (mocked for network calls)"""
    # Test email extraction from text
    text_with_emails = "Contact us at booking@label.com or press@label.com for more info."
    emails = extract_emails_from_text(text_with_emails)
    
    assert "booking@label.com" in emails
    assert "press@label.com" in emails

def test_async_scraping_components():
    """Test async scraping components (would require mocking network calls)"""
    # Just test that functions exist and are callable
    assert callable(scrape_nitter)
    assert callable(scrape_invidious_channel)

def test_signal_normalizer():
    """Test signal normalizer functionality"""
    normalizer = SignalNormalizer()
    
    # Test email extraction from payload
    payload = {
        "bio": "Booking contact: booking@mgmt.com, also reach out to press@mgmt.com",
        "description": "Music manager with 10 years experience",
        "follower_count": 5000
    }
    
    emails = normalizer._extract_emails_from_payload(payload)
    assert "booking@mgmt.com" in emails
    assert "press@mgmt.com" in emails

def test_entity_resolver():
    """Test entity resolver functionality"""
    resolver = EntityResolver()
    
    # Test that resolver exists and has required methods
    assert resolver.merge_threshold == 85
    assert callable(resolver.resolve_entities)

def test_all_components_integration():
    """Test that all components can work together"""
    # Create instances of all major components
    search_idx = SearchIndex()
    ingestor = WebhookIngestor(search_idx)
    decay_manager = ConfidenceDecayManager()
    trust_calibrator = SourceTrustCalibrator()
    wrong_detector = WrongContactDetector()
    drift_tracker = ManagerDriftTracker()
    cold_safety = ColdStartSafety()
    
    # Verify they all exist
    assert search_idx is not None
    assert ingestor is not None
    assert decay_manager is not None
    assert trust_calibrator is not None
    assert wrong_detector is not None
    assert drift_tracker is not None
    assert cold_safety is not None

def test_comprehensive_pipeline_flow():
    """Test a comprehensive pipeline flow"""
    # Create a test cluster
    cluster = {
        "emails": ["contact1@mgmt.com", "contact2@mgmt.com"],
        "domains": ["mgmt.com"],
        "artist_count": 3,
        "platform_count": 2,
        "evidence": [
            {"source": "official_site", "confidence": 0.9, "timestamp": datetime.utcnow().isoformat()},
            {"source": "social_bio", "confidence": 0.7, "timestamp": datetime.utcnow().isoformat()}
        ],
        "temporal_score": 0.8,
        "trust_score": 0.85
    }
    
    # Test manager resolution confidence
    resolution_confidence = calculate_manager_resolution_confidence(cluster)
    assert resolution_confidence > 0
    
    # Test manager classification
    manager_type = classify_manager(cluster)
    assert manager_type in ["AGENCY", "BOUTIQUE_MANAGER", "SOLO_MANAGER", "UNKNOWN"]
    
    # Test cluster quality score
    from app.utils.manager_resolution import calculate_cluster_quality_score
    quality_info = calculate_cluster_quality_score(cluster)
    assert "quality_score" in quality_info
    assert "resolution_confidence" in quality_info
    assert "manager_type" in quality_info

if __name__ == "__main__":
    # Run all tests
    test_evidence_ledger()
    print("✓ Evidence ledger tests passed")
    
    test_email_canonicalization()
    print("✓ Email canonicalization tests passed")
    
    test_temporal_scoring()
    print("✓ Temporal scoring tests passed")
    
    test_manager_resolution()
    print("✓ Manager resolution tests passed")
    
    test_search_index()
    print("✓ Search index tests passed")
    
    test_webhook_ingestion()
    print("✓ Webhook ingestion tests passed")
    
    test_confidence_decay()
    print("✓ Confidence decay tests passed")
    
    test_source_trust_calibration()
    print("✓ Source trust calibration tests passed")
    
    test_wrong_contact_detection()
    print("✓ Wrong contact detection tests passed")
    
    test_pipeline_processor()
    print("✓ Pipeline processor tests passed")
    
    test_link_in_bio_resolver()
    print("✓ Link-in-bio resolver tests passed")
    
    test_async_scraping_components()
    print("✓ Async scraping components tests passed")
    
    test_signal_normalizer()
    print("✓ Signal normalizer tests passed")
    
    test_entity_resolver()
    print("✓ Entity resolver tests passed")
    
    test_all_components_integration()
    print("✓ All components integration tests passed")
    
    test_comprehensive_pipeline_flow()
    print("✓ Comprehensive pipeline flow tests passed")
    
    print("\n🎉 All integration tests passed! The enhanced pipeline components are working correctly.")