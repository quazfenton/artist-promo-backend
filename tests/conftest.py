"""
Pytest fixtures for artist-promo-backend tests

Provides:
- Database session fixtures
- Test data factories
- Mock external services
- Common test utilities
"""
import pytest
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext

from app.models.database import Base, get_db
from app.models.staging import ScraperRawSignal, StagingContact, ResolvedEntity
from app.models.evidence import Evidence


# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///./test_artist_promo.db"
)


@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    return create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )


@pytest.fixture(scope="session")
def tables(engine):
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine, tables) -> Session:
    """
    Create a fresh database session for each test
    
    Automatically rolls back at the end of the test to prevent pollution.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user"""
    from app.auth.models import User
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=pwd_context.hash("Test123!"),
        role="user",
        is_active=True
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def test_admin_user(db_session: Session):
    """Create a test admin user"""
    from app.auth.models import User
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username="adminuser",
        email="admin@example.com",
        hashed_password=pwd_context.hash("Admin123!"),
        role="admin",
        is_active=True
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def test_contact(db_session: Session):
    """Create a test contact"""
    from app.models.database import Contact, ContactType, Platform
    
    contact = Contact(
        full_name="Test Manager",
        email="test@manager.com",
        contact_type=ContactType.MANAGER,
        follower_count=10000,
        priority_score=75.0,
        verified=True,
        source_platform=Platform.INSTAGRAM.value
    )
    
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    
    return contact


@pytest.fixture
def test_playlist(db_session: Session):
    """Create a test playlist"""
    from app.models.database import Playlist, Platform
    
    playlist = Playlist(
        platform_id="spotify:playlist:123456",
        name="Test Hip-Hop Playlist",
        platform=Platform.SPOTIFY.value,
        follower_count=50000,
        owner_username="testcurator",
        relevance_score=85.0
    )
    
    db_session.add(playlist)
    db_session.commit()
    db_session.refresh(playlist)
    
    return playlist


@pytest.fixture
def test_raw_signal(db_session: Session):
    """Create a test raw signal"""
    signal = ScraperRawSignal(
        job_id="test-job-123",
        source_platform="spotify",
        payload={
            "playlists": [
                {
                    "id": "playlist123",
                    "name": "Test Playlist",
                    "followers": 50000
                }
            ]
        },
        dedupe_key="test-dedupe-key",
        signal_status="new",
        record_count=1
    )
    
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    
    return signal


@pytest.fixture
def test_staging_contact(db_session: Session):
    """Create a test staging contact"""
    contact = StagingContact(
        full_name="Staging Manager",
        email="staging@manager.com",
        contact_type="manager",
        source_platform="instagram",
        source_url="https://instagram.com/testmanager",
        follower_count=5000,
        confidence_score=0.8
    )
    
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    
    return contact


@pytest.fixture
def test_resolved_entity(db_session: Session):
    """Create a test resolved entity"""
    from app.utils.pipeline_orchestrator import PipelineState
    
    entity = ResolvedEntity(
        name="Resolved Manager",
        email="resolved@manager.com",
        entity_type="manager",
        confidence_score=0.95,
        source_urls=[
            {
                "url": "https://example.com",
                "source": "official_site",
                "found_at": datetime.utcnow().isoformat()
            }
        ],
        pipeline_state=PipelineState.NORMALIZED.value,
        outreach_ready=True,
        quality_score=90.0
    )
    
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    
    return entity


@pytest.fixture
def test_evidence(db_session: Session):
    """Create a test evidence record"""
    evidence = Evidence(
        entity_id=1,
        email="evidence@test.com",
        source="official_site",
        signal="bio_email",
        url="https://example.com/contact",
        confidence=0.9,
        trust_score=0.85,
        metadata={
            "html_snippet": "<a href='mailto:evidence@test.com'>Contact</a>",
            "screenshot": "base64_encoded_screenshot"
        }
    )
    
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    
    return evidence


@pytest.fixture
def mock_spotify_scraper():
    """Create a mock Spotify scraper"""
    from unittest.mock import Mock, MagicMock
    
    mock_scraper = Mock()
    mock_scraper.scrape = MagicMock(return_value=[
        {
            "id": "playlist123",
            "name": "Test Playlist",
            "followers": 50000,
            "owner": "testcurator"
        }
    ])
    
    return mock_scraper


@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    from unittest.mock import Mock
    
    mock_redis = Mock()
    mock_redis.lpush = Mock(return_value=1)
    mock_redis.brpop = Mock(return_value=None)  # No jobs by default
    mock_redis.hset = Mock(return_value=1)
    mock_redis.hget = Mock(return_value=None)
    mock_redis.llen = Mock(return_value=0)
    
    return mock_redis


@pytest.fixture
def auth_headers(test_user, client):
    """Get authentication headers for test user"""
    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "Test123!"}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    return {}


@pytest.fixture
def admin_auth_headers(test_admin_user, client):
    """Get authentication headers for admin user"""
    response = client.post(
        "/auth/login",
        json={"username": "adminuser", "password": "Admin123!"}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    return {}


@pytest.fixture
def sample_contact_data():
    """Sample contact data for testing"""
    return {
        "full_name": "John Manager",
        "email": "john@management.com",
        "contact_type": "manager",
        "follower_count": 25000,
        "source_platform": "instagram",
        "source_url": "https://instagram.com/johnmanager",
        "genres": ["hip-hop", "rap"],
        "priority_score": 80.0
    }


@pytest.fixture
def sample_playlist_data():
    """Sample playlist data for testing"""
    return {
        "platform_id": "spotify:playlist:abcdef123456",
        "name": "Fresh Hip-Hop",
        "platform": "spotify",
        "follower_count": 100000,
        "owner_username": "hiphopcurator",
        "relevance_score": 90.0
    }


@pytest.fixture
def sample_scrape_params():
    """Sample scraping parameters"""
    return {
        "genre": "hip-hop",
        "min_followers": 1000,
        "max_results": 50
    }


# Helper functions for tests

def create_test_user(db_session: Session, username: str = None, role: str = "user"):
    """Helper to create a test user"""
    from app.auth.models import User
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        username=username or f"testuser_{datetime.utcnow().timestamp()}",
        email=f"{username or 'testuser'}@example.com",
        hashed_password=pwd_context.hash("Test123!"),
        role=role,
        is_active=True
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


def create_test_contact(db_session: Session, **kwargs):
    """Helper to create a test contact with custom fields"""
    from app.models.database import Contact, ContactType, Platform
    
    contact_data = {
        "full_name": "Test Contact",
        "email": f"test_{datetime.utcnow().timestamp()}@example.com",
        "contact_type": ContactType.MANAGER,
        "follower_count": 10000,
        "priority_score": 75.0,
        "verified": False,
        "source_platform": Platform.INSTAGRAM.value
    }
    
    contact_data.update(kwargs)
    
    contact = Contact(**contact_data)
    
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    
    return contact
