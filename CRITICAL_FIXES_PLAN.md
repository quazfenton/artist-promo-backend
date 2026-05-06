# Artist Promo Backend - Critical Fixes Implementation Plan

**Date:** March 5, 2026
**Based on:** Comprehensive Review 2026-03-03
**Priority:** P0 Critical Fixes First

---

## Executive Summary

The codebase has **excellent architecture design** but **critical implementation gaps**:

1. **Worker Queue System** - Jobs are enqueued but never consumed
2. **Pipeline State Machine** - Not actually enforced
3. **Scraper Integration** - Scrapers don't create raw signals
4. **Evidence Ledger** - No dedicated table, trust scores never used
5. **Test Coverage** - Essentially non-existent

**Estimated Fix Time:** 40-50 hours for P0 fixes

---

## Phase 1: Critical Worker Queue Fixes (P0)

### Issue 1.1: Workers Don't Consume Jobs

**Files to Fix:**
- `app/workers/scrape_worker.py`
- `app/workers/signal_normalizer_worker.py`
- `app/workers/entity_resolver_worker.py`
- `app/workers/graph_cluster_worker.py`
- `app/workers/outreach_worker.py`

**Fix Required:** Add worker loop to consume queued jobs

### Issue 1.2: Job Status Not Trackable

**Files to Create:**
- `app/api/jobs.py` - Add job status endpoint (PARTIALLY EXISTS)
- `app/workers/queue_adapter.py` - Add job tracking

**Fix Required:** Complete job status tracking

---

## Phase 2: Pipeline Integration (P0)

### Issue 2.1: Scrapers Don't Create Raw Signals

**Files to Fix:**
- `app/scrapers/base_scraper.py`
- `app/scrapers/spotify_scraper.py`
- `app/scrapers/youtube_scraper.py`
- `app/scrapers/instagram_scraper.py`
- `app/scrapers/web_scraper.py`

**Fix Required:** Create `ScraperRawSignal` on successful scrape

### Issue 2.2: State Machine Not Enforced

**Files to Fix:**
- `app/models/staging.py` - Add `pipeline_state` to `ResolvedEntity`
- `app/utils/pipeline_orchestrator.py` - Enforce state transitions

**Fix Required:** Track and enforce pipeline states

---

## Phase 3: Evidence & Trust System (P1)

### Issue 3.1: No Dedicated Evidence Table

**Files to Create:**
- `app/models/evidence.py` - New Evidence table
- `app/utils/evidence_ledger.py` - Update to use new table

**Fix Required:** Create queryable evidence storage

### Issue 3.2: Trust Scores Never Calculated

**Files to Fix:**
- `app/utils/pipeline_orchestrator.py` - Apply trust scores during resolution
- `app/utils/evidence_ledger.py` - Integrate with entity creation

**Fix Required:** Calculate and store trust scores

---

## Phase 4: Testing Infrastructure (P1)

### Issue 4.1: No Test Coverage

**Files to Create:**
- `tests/conftest.py` - Pytest fixtures
- `tests/unit/test_pipeline_orchestrator.py`
- `tests/unit/test_queue_adapter.py`
- `tests/integration/test_scraper_integration.py`
- `tests/e2e/test_full_pipeline.py`

**Fix Required:** Comprehensive test suite

---

## Detailed Implementation Tasks

### Task 1.1: Implement Worker Loop

**File:** `app/workers/scrape_worker.py`

```python
#!/usr/bin/env python3
"""
Scrape Worker - Consumes scrape jobs from queue
"""
import asyncio
import os
import sys
from datetime import datetime
from loguru import logger
from app.workers.queue_adapter import dequeue_job, complete_job, fail_job
from app.models.database import SessionLocal
from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
from app.scrapers.youtube_scraper import YouTubeChannelScraper
from app.scrapers.instagram_scraper import InstagramScraper
from app.scrapers.web_scraper import WebContactScraper

SCRAPER_MAP = {
    "spotify_playlist": SpotifyPlaylistScraper,
    "youtube_channel": YouTubeChannelScraper,
    "instagram_profile": InstagramScraper,
    "web_contact": WebContactScraper,
}

async def process_scrape_job(job: dict):
    """Process a single scrape job"""
    job_id = job["job_id"]
    job_type = job["type"]
    params = job.get("params", {})
    
    logger.info(f"Processing scrape job {job_id}: {job_type}")
    
    try:
        # Get scraper class
        scraper_class = SCRAPER_MAP.get(job_type)
        if not scraper_class:
            raise ValueError(f"Unknown scraper type: {job_type}")
        
        # Initialize and run scraper
        scraper = scraper_class()
        results = scraper.scrape(**params)
        
        # Create raw signal for pipeline
        db = SessionLocal()
        try:
            from app.models.staging import ScraperRawSignal
            raw_signal = ScraperRawSignal(
                job_id=job_id,
                source_platform=job_type.split("_")[0],
                payload={"results": results},
                dedupe_key=f"{job_type}:{job_id}:{datetime.utcnow().isoformat()}",
                signal_status="new"
            )
            db.add(raw_signal)
            db.commit()
            db.refresh(raw_signal)
            
            # Enqueue normalization job
            from app.workers.queue_adapter import enqueue_job
            enqueue_job(
                job_type="normalize:signals",
                params={"raw_signal_id": raw_signal.id},
                priority=job.get("priority", 5)
            )
            
            logger.info(f"Created raw signal {raw_signal.id} for job {job_id}")
        finally:
            db.close()
        
        return {"success": True, "raw_signal_id": raw_signal.id, "count": len(results)}
        
    except Exception as e:
        logger.error(f"Scrape job {job_id} failed: {str(e)}", exc_info=True)
        raise

async def worker_loop():
    """Main worker loop - consume jobs from queue"""
    logger.info("Starting scrape worker loop...")
    
    while True:
        try:
            # Dequeue job
            job = dequeue_job("queue:scrape")
            
            if job:
                logger.info(f"Dequeued job: {job['job_id']}")
                
                try:
                    result = await process_scrape_job(job)
                    complete_job(job["job_id"], result)
                    logger.info(f"Completed job {job['job_id']}")
                except Exception as e:
                    fail_job(job["job_id"], str(e))
                    logger.error(f"Job {job['job_id']} failed: {str(e)}")
            else:
                # No jobs, wait before polling again
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"Worker loop error: {str(e)}", exc_info=True)
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(worker_loop())
```

---

### Task 2.1: Add Pipeline State to ResolvedEntity

**File:** `app/models/staging.py`

Add to `ResolvedEntity` class:
```python
class ResolvedEntity(Base):
    # ... existing fields ...
    
    # NEW: Pipeline state tracking
    pipeline_state = Column(
        String,
        default=PipelineState.SCRAPED.value,
        nullable=False,
        index=True
    )
    outreach_ready = Column(Boolean, default=False)
    quality_score = Column(Float, default=0.0)
    state_history = Column(JSON, default=list)  # Track state transitions
```

---

### Task 2.2: Create Evidence Table

**File:** `app/models/evidence.py` (NEW)

```python
"""
Evidence Ledger - Machine-auditable contact verification
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base

class Evidence(Base):
    __tablename__ = "evidence"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("resolved_entities.id"), nullable=False)
    
    # Evidence details
    email = Column(String, index=True, nullable=False)
    source = Column(String, nullable=False)  # official_site, social_bio, whois, etc.
    signal = Column(String, nullable=False)  # bio_email, whois_email, contact_form, etc.
    url = Column(String)  # Source URL where evidence was found
    confidence = Column(Float, default=1.0)  # Initial confidence score
    
    # Metadata
    metadata = Column(JSON, default=dict)  # Additional context
    found_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    entity = relationship("ResolvedEntity", back_populates="evidence")
    
    __table_args__ = (
        Index('idx_evidence_entity_email', 'entity_id', 'email'),
        Index('idx_evidence_source', 'source'),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "email": self.email,
            "source": self.source,
            "signal": self.signal,
            "url": self.url,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "found_at": self.found_at.isoformat()
        }
```

---

### Task 3.1: Create Test Fixtures

**File:** `tests/conftest.py` (NEW)

```python
"""
Pytest fixtures for artist-promo-backend tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, get_db

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    return create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

@pytest.fixture(scope="session")
def tables(engine):
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(engine, tables):
    """Create a fresh database session for each test"""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from app.auth.models import User
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=pwd_context.hash("Test123!"),
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_contact(db_session):
    """Create a test contact"""
    from app.models.database import Contact, ContactType
    
    contact = Contact(
        full_name="Test Manager",
        email="test@manager.com",
        contact_type=ContactType.MANAGER,
        follower_count=10000,
        priority_score=75.0
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact
```

---

## Testing Strategy

### Unit Tests
- Test each pipeline stage independently
- Mock external API calls
- Test error conditions

### Integration Tests
- Test queue adapter with Redis
- Test database operations
- Test scraper integration

### E2E Tests
- Test full pipeline from scrape to outreach
- Test job lifecycle
- Test webhook ingestion

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Workers consume jobs from queue
- [ ] Job status endpoint returns accurate status
- [ ] Failed jobs are properly tracked

### Phase 2 Complete When:
- [ ] Scrapers create `ScraperRawSignal` records
- [ ] Pipeline state transitions are enforced
- [ ] Entities progress through pipeline stages

### Phase 3 Complete When:
- [ ] Evidence table exists and is populated
- [ ] Trust scores are calculated and stored
- [ ] Evidence is queryable for audits

### Phase 4 Complete When:
- [ ] Unit test coverage > 70%
- [ ] Integration tests pass
- [ ] E2E pipeline test passes

---

## Next Steps

1. **Start with Task 1.1** - Worker loop is most critical
2. **Then Task 2.1** - Pipeline state tracking
3. **Then Task 3.1** - Evidence table
4. **Finally Task 4.1** - Test coverage

Each task is independent and can be tested individually.
