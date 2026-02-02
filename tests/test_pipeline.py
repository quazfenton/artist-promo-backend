"""
Integration tests for the pipeline system
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base as MainBase, Contact
from app.models.staging import Base as StagingBase, ScraperRawSignal, StagingContact, ResolvedEntity
from app.workers.queue_adapter import enqueue_job

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_pipeline.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
MainBase.metadata.create_all(bind=engine)
StagingBase.metadata.create_all(bind=engine)

def override_get_db():
    """Override dependency to use test database"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def test_enqueue_job():
    """Test that jobs can be enqueued properly"""
    # Test basic job enqueue
    job_id = enqueue_job(
        job_type="scrape:test",
        params={"test_param": "test_value"},
        source="test",
        priority=5
    )
    
    assert job_id is not None
    assert len(job_id) > 0
    
    # Test job status retrieval
    from app.workers.queue_adapter import get_job_status
    status = get_job_status(job_id)
    
    # Initially should be queued
    assert status["status"] == "queued"

def test_scraper_raw_signal_creation():
    """Test that scraper raw signals can be created"""
    db = TestingSessionLocal()
    
    try:
        # Create a test raw signal
        raw_signal = ScraperRawSignal(
            job_id="test-job-id",
            source_platform="test_platform",
            payload={"test": "data"},
            dedupe_key="test:dedupe:key"
        )
        
        db.add(raw_signal)
        db.commit()
        
        # Verify it was created
        retrieved = db.query(ScraperRawSignal).filter(
            ScraperRawSignal.job_id == "test-job-id"
        ).first()
        
        assert retrieved is not None
        assert retrieved.source_platform == "test_platform"
        assert retrieved.payload == {"test": "data"}
        
    finally:
        db.close()

def test_staging_contact_creation():
    """Test that staging contacts can be created"""
    db = TestingSessionLocal()
    
    try:
        # Create a test staging contact
        staging_contact = StagingContact(
            name="Test Contact",
            email="test@example.com",
            contact_type="playlist_curator",
            confidence_score=85,
            provenance={"source_job": "test-job-id"}
        )
        
        db.add(staging_contact)
        db.commit()
        
        # Verify it was created
        retrieved = db.query(StagingContact).filter(
            StagingContact.email == "test@example.com"
        ).first()
        
        assert retrieved is not None
        assert retrieved.name == "Test Contact"
        assert retrieved.contact_type == "playlist_curator"
        assert retrieved.confidence_score == 85
        
    finally:
        db.close()

def test_resolved_entity_creation():
    """Test that resolved entities can be created"""
    db = TestingSessionLocal()
    
    try:
        # Create a test resolved entity
        resolved_entity = ResolvedEntity(
            merge_key="email:test@example.com",
            confidence_score=90,
            contact_type="manager",
            email="test@example.com",
            name="Test Manager"
        )
        
        db.add(resolved_entity)
        db.commit()
        
        # Verify it was created
        retrieved = db.query(ResolvedEntity).filter(
            ResolvedEntity.email == "test@example.com"
        ).first()
        
        assert retrieved is not None
        assert retrieved.name == "Test Manager"
        assert retrieved.contact_type == "manager"
        assert retrieved.confidence_score == 90
        
    finally:
        db.close()

def test_queue_length_functions():
    """Test queue length functions"""
    from app.workers.queue_adapter import get_queue_length, get_active_queues
    
    # Test getting queue length for a non-existent queue
    length = get_queue_length("queue:test_nonexistent")
    assert length == 0
    
    # Test getting active queues
    queues = get_active_queues()
    assert isinstance(queues, dict)
    # Should have at least some queues defined
    assert isinstance(queues, dict)

def test_job_fingerprinting():
    """Test job fingerprinting for idempotency"""
    from app.workers.queue_adapter import fingerprint
    
    job1 = {
        "job_id": "abc123",
        "type": "scrape:spotify",
        "params": {"genre": "hip-hop", "limit": 50}
    }
    
    job2 = {
        "job_id": "def456",  # Different job_id but same content
        "type": "scrape:spotify",
        "params": {"genre": "hip-hop", "limit": 50}
    }
    
    job3 = {
        "job_id": "ghi789",
        "type": "scrape:spotify", 
        "params": {"genre": "rock", "limit": 50}  # Different params
    }
    
    fp1 = fingerprint(job1)
    fp2 = fingerprint(job2) 
    fp3 = fingerprint(job3)
    
    # Jobs with same content should have same fingerprint (ignoring job_id)
    assert fp1 == fp2
    
    # Jobs with different content should have different fingerprints
    assert fp1 != fp3

def test_queue_adapter_imports():
    """Test that queue adapter can be imported without errors"""
    from app.workers import queue_adapter
    assert hasattr(queue_adapter, 'enqueue_job')
    assert hasattr(queue_adapter, 'dequeue_job')
    assert hasattr(queue_adapter, 'get_job_status')

def test_worker_imports():
    """Test that workers can be imported without errors"""
    # Test that worker modules can be imported
    from app.workers import scrape_worker
    from app.workers import signal_normalizer_worker
    from app.workers import entity_resolver_worker
    from app.workers import graph_cluster_worker
    from app.workers import outreach_worker
    
    # Verify they have the expected classes
    assert hasattr(scrape_worker, 'ScrapeWorker')
    assert hasattr(signal_normalizer_worker, 'SignalNormalizerWorker')
    assert hasattr(entity_resolver_worker, 'EntityResolverEnrichmentWorker')
    assert hasattr(graph_cluster_worker, 'GraphBuilderClusterWorker')
    assert hasattr(outreach_worker, 'OutreachWorker')

if __name__ == "__main__":
    pytest.main([__file__])