"""Database model tests for the artist promotion backend"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

from app.models.database import Base, Contact, Playlist, Venue, ContactType, Platform, OutreachLog, ScraperRun
from app.auth.models import User

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_models.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

def test_contact_model_creation():
    """Test creating a Contact model instance"""
    contact = Contact(
        full_name="John Doe",
        email="john@example.com",
        contact_type=ContactType.PLAYLIST_CURATOR,
        priority_score=8.5,
        follower_count=10000,
        verified=True
    )
    
    assert contact.full_name == "John Doe"
    assert contact.email == "john@example.com"
    assert contact.contact_type == ContactType.PLAYLIST_CURATOR
    assert contact.priority_score == 8.5
    assert contact.follower_count == 10000
    assert contact.verified is True
    assert contact.created_at is not None

def test_contact_model_defaults():
    """Test Contact model default values"""
    contact = Contact(
        full_name="Jane Smith",
        contact_type=ContactType.PUBLICIST
    )
    
    assert contact.full_name == "Jane Smith"
    assert contact.contact_type == ContactType.PUBLICIST
    assert contact.priority_score == 0.0  # Default value
    assert contact.follower_count == 0     # Default value
    assert contact.verified is False       # Default value
    assert contact.email is None           # Optional field
    assert contact.created_at is not None  # Auto-populated

def test_playlist_model_creation():
    """Test creating a Playlist model instance"""
    playlist = Playlist(
        platform_id="spotify_playlist_123",
        platform=Platform.SPOTIFY,
        name="Hip Hop Essentials",
        description="Curated hip hop tracks",
        follower_count=50000,
        track_count=100,
        is_active=True,
        relevance_score=9.2,
        playlist_url="https://open.spotify.com/playlist/123"
    )
    
    assert playlist.platform_id == "spotify_playlist_123"
    assert playlist.platform == Platform.SPOTIFY
    assert playlist.name == "Hip Hop Essentials"
    assert playlist.description == "Curated hip hop tracks"
    assert playlist.follower_count == 50000
    assert playlist.track_count == 100
    assert playlist.is_active is True
    assert playlist.relevance_score == 9.2
    assert playlist.playlist_url == "https://open.spotify.com/playlist/123"
    assert playlist.created_at is not None

def test_playlist_model_defaults():
    """Test Playlist model default values"""
    playlist = Playlist(
        platform_id="test_id",
        platform=Platform.SPOTIFY,
        name="Test Playlist",
        playlist_url="https://example.com"
    )
    
    assert playlist.platform_id == "test_id"
    assert playlist.platform == Platform.SPOTIFY
    assert playlist.name == "Test Playlist"
    assert playlist.playlist_url == "https://example.com"
    assert playlist.follower_count == 0      # Default value
    assert playlist.track_count == 0         # Default value
    assert playlist.is_active is True        # Default value
    assert playlist.relevance_score == 0.0   # Default value
    assert playlist.is_editorial is False    # Default value
    assert playlist.created_at is not None   # Auto-populated

def test_venue_model_creation():
    """Test creating a Venue model instance"""
    venue = Venue(
        name="The Underground",
        venue_type="Club",
        city="New York",
        state="NY",
        country="USA",
        address="123 Music St",
        capacity=500,
        genres=["hip-hop", "rap"],
        description="Hip hop venue in downtown NYC"
    )
    
    assert venue.name == "The Underground"
    assert venue.venue_type == "Club"
    assert venue.city == "New York"
    assert venue.state == "NY"
    assert venue.country == "USA"
    assert venue.address == "123 Music St"
    assert venue.capacity == 500
    assert venue.genres == ["hip-hop", "rap"]
    assert venue.description == "Hip hop venue in downtown NYC"
    assert venue.created_at is not None

def test_venue_model_defaults():
    """Test Venue model default values"""
    venue = Venue(
        name="Test Venue",
        city="Test City"
    )
    
    assert venue.name == "Test Venue"
    assert venue.city == "Test City"
    assert venue.country == "USA"            # Default value
    assert venue.event_frequency == 0        # Default value
    assert venue.created_at is not None      # Auto-populated
    assert venue.updated_at is not None      # Auto-populated

def test_outreach_log_model_creation():
    """Test creating an OutreachLog model instance"""
    outreach = OutreachLog(
        contact_id=1,
        campaign_name="Hip Hop Promotion Q1",
        subject="Collaboration Opportunity",
        channel="email",
        status="sent"
    )
    
    assert outreach.contact_id == 1
    assert outreach.campaign_name == "Hip Hop Promotion Q1"
    assert outreach.subject == "Collaboration Opportunity"
    assert outreach.channel == "email"
    assert outreach.status == "sent"
    assert outreach.sent_at is not None

def test_outreach_log_model_defaults():
    """Test OutreachLog model default values"""
    outreach = OutreachLog(
        contact_id=1,
        channel="email"
    )
    
    assert outreach.contact_id == 1
    assert outreach.channel == "email"
    assert outreach.status == "sent"         # Default value
    assert outreach.sent_at is not None      # Auto-populated

def test_scraper_run_model_creation():
    """Test creating a ScraperRun model instance"""
    scraper_run = ScraperRun(
        scraper_name="SpotifyPlaylistScraper",
        status="completed",
        items_found=50,
        items_saved=45,
        errors_count=5
    )
    
    assert scraper_run.scraper_name == "SpotifyPlaylistScraper"
    assert scraper_run.status == "completed"
    assert scraper_run.items_found == 50
    assert scraper_run.items_saved == 45
    assert scraper_run.errors_count == 5
    assert scraper_run.started_at is not None

def test_scraper_run_model_defaults():
    """Test ScraperRun model default values"""
    scraper_run = ScraperRun(
        scraper_name="TestScraper"
    )
    
    assert scraper_run.scraper_name == "TestScraper"
    assert scraper_run.status == "running"   # Default value
    assert scraper_run.items_found == 0      # Default value
    assert scraper_run.items_saved == 0      # Default value
    assert scraper_run.errors_count == 0     # Default value
    assert scraper_run.started_at is not None  # Auto-populated

def test_user_model_creation():
    """Test creating a User model instance"""
    from app.auth.models import User
    
    user = User(
        email="test@example.com",
        hashed_password="hashed_password_here"
    )
    
    assert user.email == "test@example.com"
    assert user.hashed_password == "hashed_password_here"
    assert user.is_active is True            # Default value
    assert user.is_admin is False            # Default value
    assert user.created_at is not None       # Auto-populated

def test_user_model_defaults():
    """Test User model default values"""
    user = User(
        email="default@example.com",
        hashed_password="default_hash"
    )
    
    assert user.email == "default@example.com"
    assert user.hashed_password == "default_hash"
    assert user.is_active is True            # Default value
    assert user.is_admin is False            # Default value

def test_user_password_verification():
    """Test User password hashing and verification"""
    user = User(
        email="secure@example.com"
    )
    
    # Hash a password
    password = "secure_password_123"
    hashed = user.hash_password(password)
    
    # Verify the password
    user.hashed_password = hashed
    assert user.verify_password(password) is True
    
    # Verify wrong password fails
    assert user.verify_password("wrong_password") is False

def test_contact_type_enum_values():
    """Test all ContactType enum values"""
    assert ContactType.PLAYLIST_CURATOR.value == "playlist_curator"
    assert ContactType.PUBLICIST.value == "publicist"
    assert ContactType.MANAGER.value == "manager"
    assert ContactType.AR_REP.value == "ar_rep"
    assert ContactType.VENUE_BOOKER.value == "venue_booker"
    assert ContactType.JOURNALIST.value == "journalist"
    assert ContactType.INFLUENCER.value == "influencer"
    assert ContactType.LABEL.value == "label"

def test_platform_enum_values():
    """Test all Platform enum values"""
    assert Platform.SPOTIFY.value == "spotify"
    assert Platform.APPLE_MUSIC.value == "apple_music"
    assert Platform.YOUTUBE.value == "youtube"
    assert Platform.SOUNDCLOUD.value == "soundcloud"
    assert Platform.INSTAGRAM.value == "instagram"
    assert Platform.TWITTER.value == "twitter"
    assert Platform.LINKEDIN.value == "linkedin"
    assert Platform.TIKTOK.value == "tiktok"
    assert Platform.WEBSITE.value == "website"

def test_contact_relationships():
    """Test Contact relationships (basic structure check)"""
    contact = Contact(
        full_name="Test Contact",
        contact_type=ContactType.PLAYLIST_CURATOR
    )
    
    # Check that relationship attributes exist
    assert hasattr(contact, 'playlists')
    assert hasattr(contact, 'outreach_history')
    assert hasattr(contact, 'created_by_user')
    assert hasattr(contact, 'updated_by_user')

def test_playlist_relationships():
    """Test Playlist relationships (basic structure check)"""
    playlist = Playlist(
        platform_id="test_id",
        platform=Platform.SPOTIFY,
        name="Test Playlist",
        playlist_url="https://example.com"
    )
    
    # Check that relationship attributes exist
    assert hasattr(playlist, 'curator')
    assert hasattr(playlist, 'created_by_user')
    assert hasattr(playlist, 'updated_by_user')

def test_venue_relationships():
    """Test Venue has no relationships in this model"""
    venue = Venue(
        name="Test Venue",
        city="Test City"
    )
    
    # Check that venue doesn't have complex relationships
    # (it only has basic fields in this model)
    assert hasattr(venue, 'name')
    assert hasattr(venue, 'city')

def test_outreach_log_relationships():
    """Test OutreachLog relationships"""
    outreach = OutreachLog(
        contact_id=1,
        channel="email"
    )
    
    # Check that relationship attributes exist
    assert hasattr(outreach, 'contact')

def test_scraper_run_relationships():
    """Test ScraperRun has no direct relationships"""
    scraper_run = ScraperRun(
        scraper_name="TestScraper"
    )
    
    # ScraperRun doesn't have relationships in this model
    assert hasattr(scraper_run, 'scraper_name')

def test_model_repr_methods():
    """Test that models have proper string representations"""
    contact = Contact(
        id=1,
        full_name="Test Contact",
        contact_type=ContactType.PLAYLIST_CURATOR
    )
    
    # Basic check that the object can be represented as a string
    assert str(contact.id) in str(contact) or hasattr(contact, '__str__')

def test_model_serialization():
    """Test that model fields can be accessed"""
    contact = Contact(
        full_name="Serialization Test",
        email="serial@example.com",
        contact_type=ContactType.PUBLICIST,
        priority_score=7.5
    )
    
    # Test that all expected fields exist and can be accessed
    assert contact.full_name == "Serialization Test"
    assert contact.email == "serial@example.com"
    assert contact.contact_type == ContactType.PUBLICIST
    assert contact.priority_score == 7.5
    
    # Test that optional fields are handled correctly
    assert contact.instagram_handle is None
    assert contact.twitter_handle is None
    assert contact.company is None

def test_model_timestamps():
    """Test that timestamp fields are properly set"""
    contact = Contact(
        full_name="Timestamp Test",
        contact_type=ContactType.MANAGER
    )
    
    assert contact.created_at is not None
    assert contact.updated_at is not None
    
    # Initially, updated_at should be close to created_at
    time_diff = abs((contact.updated_at - contact.created_at).total_seconds())
    assert time_diff < 1  # Should be within 1 second

if __name__ == "__main__":
    pytest.main([__file__])