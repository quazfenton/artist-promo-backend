"""
Database models for artist promotion system
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, 
    JSON, ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
import bcrypt

Base = declarative_base()


class ContactType(str, enum.Enum):
    PLAYLIST_CURATOR = "playlist_curator"
    PUBLICIST = "publicist"
    MANAGER = "manager"
    AR_REP = "ar_rep"
    VENUE_BOOKER = "venue_booker"
    JOURNALIST = "journalist"
    INFLUENCER = "influencer"
    LABEL = "label"


class Platform(str, enum.Enum):
    SPOTIFY = "spotify"
    APPLE_MUSIC = "apple_music"
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    WEBSITE = "website"


class User(Base):
    """User authentication table"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))
    
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


class Contact(Base):
    """Main contacts table"""
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identity
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    contact_type = Column(SQLEnum(ContactType), nullable=False)
    
    # Contact Info
    email = Column(String(255), nullable=True, index=True)
    email_verified = Column(Boolean, default=False)
    phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Social Handles
    instagram_handle = Column(String(255), nullable=True)
    twitter_handle = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    
    # Professional Details
    company = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    genres = Column(JSON, nullable=True)  # ["hip-hop", "rap", "trap"]
    
    # Metrics
    follower_count = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    response_rate = Column(Float, nullable=True)
    
    # Scoring
    priority_score = Column(Float, default=0.0, index=True)
    llm_quality_score = Column(Float, nullable=True)
    match_score = Column(Float, nullable=True)
    
    # Source & Verification
    source_platform = Column(SQLEnum(Platform), nullable=True)
    source_url = Column(String(500), nullable=True)
    verified = Column(Boolean, default=False)
    last_verified_at = Column(DateTime, nullable=True)
    
    # Audit & Soft Delete
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_active_at = Column(DateTime, nullable=True)
    
    # Relationships
    playlists = relationship("Playlist", back_populates="curator")
    outreach_history = relationship("OutreachLog", back_populates="contact")
    created_by_user = relationship("User", foreign_keys=[created_by])
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_contact_type_score', 'contact_type', 'priority_score'),
        Index('idx_email_verified', 'email', 'email_verified'),
        Index('idx_active_contacts', 'deleted_at', 'priority_score'),
        Index('idx_contact_search', 'full_name', 'email', 'company'),
    )


class Playlist(Base):
    """Playlists discovered (Spotify, Apple Music, etc.)"""
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identity
    platform_id = Column(String(255), unique=True, index=True)
    platform = Column(SQLEnum(Platform), nullable=False)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    # Owner Info
    curator_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    owner_username = Column(String(255), nullable=True)
    owner_url = Column(String(500), nullable=True)
    
    # Metrics
    follower_count = Column(Integer, default=0)
    track_count = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=True)
    
    # Metadata
    genres = Column(JSON, nullable=True)
    mood_tags = Column(JSON, nullable=True)
    is_editorial = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # URLs
    playlist_url = Column(String(500), nullable=False)
    embed_url = Column(String(500), nullable=True)
    
    # Scoring
    relevance_score = Column(Float, default=0.0)
    
    # Audit & Soft Delete
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    curator = relationship("Contact", back_populates="playlists")
    created_by_user = relationship("User", foreign_keys=[created_by])
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    
    __table_args__ = (
        Index('idx_platform_followers', 'platform', 'follower_count'),
        Index('idx_active_playlists', 'is_active', 'deleted_at', 'last_updated'),
        Index('idx_playlist_search', 'name', 'owner_username'),
    )


class Venue(Base):
    """Venues for booking"""
    __tablename__ = "venues"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic Info
    name = Column(String(255), nullable=False)
    venue_type = Column(String(100), nullable=True)  # Club, Bar, Festival, etc.
    
    # Location
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), default="USA")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Contact
    booking_email = Column(String(255), nullable=True)
    general_email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Details
    capacity = Column(Integer, nullable=True)
    genres = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    
    # Metrics
    event_frequency = Column(Integer, default=0)  # events per month
    avg_attendance = Column(Integer, nullable=True)
    
    # Scoring
    venue_score = Column(Float, default=0.0)
    vibe_match_score = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_city_score', 'city', 'venue_score'),
    )


class OutreachLog(Base):
    """Track outreach history"""
    __tablename__ = "outreach_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    
    # Outreach Details
    campaign_name = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    message_body = Column(Text, nullable=True)
    channel = Column(String(50), nullable=False)  # email, dm, linkedin, etc.
    
    # Status
    sent_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="sent")  # sent, opened, replied, bounced, etc.
    
    # Metadata
    n8n_execution_id = Column(String(255), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    
    # Relationships
    contact = relationship("Contact", back_populates="outreach_history")


class ScraperRun(Base):
    """Track scraper executions"""
    __tablename__ = "scraper_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    scraper_name = Column(String(100), nullable=False)
    status = Column(String(50), default="running")  # running, completed, failed
    
    # Stats
    items_found = Column(Integer, default=0)
    items_saved = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Logs
    error_log = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)


# ==================== VIEWS / MATERIALIZED QUERIES ====================

class TopCurator(Base):
    """High-priority curators view"""
    __tablename__ = "top_curators_view"
    __table_args__ = {'info': {'is_view': True}}
    
    id = Column(Integer, primary_key=True)
    full_name = Column(String(255))
    email = Column(String(255))
    priority_score = Column(Float)
    follower_count = Column(Integer)
    contact_type = Column(String(50))
