"""Staging and graph models for the pipeline"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, Float, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class ScraperRawSignal(Base):
    """Raw outputs of scrapers"""
    __tablename__ = "scraper_raw_signals"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, index=True)  # From the job queue
    source_platform = Column(String)   # spotify, youtube, instagram, etc.
    payload = Column(JSON)             # raw scraper output
    dedupe_key = Column(String, index=True)  # For idempotency
    created_at = Column(DateTime, server_default=func.now())
    
    # Index for faster querying
    __table_args__ = (
        Index('idx_scraper_raw_signals_platform', 'source_platform'),
        Index('idx_scraper_raw_signals_created', 'created_at'),
    )

class StagingContact(Base):
    """Normalized, unresolved candidate contacts"""
    __tablename__ = "staging_contacts"

    id = Column(Integer, primary_key=True)
    raw_signal_id = Column(Integer, ForeignKey("scraper_raw_signals.id"))  # FK to raw signal
    name = Column(String)
    email = Column(String, index=True)
    contact_type = Column(String)  # playlist_curator, publicist, manager, etc.
    social_handles = Column(JSON)  # {"instagram": "@handle", "twitter": "@handle"}
    confidence_score = Column(Integer)  # 0-100
    platform_ids = Column(JSON)         # e.g., {"spotify_user_id": "xyz123"}
    follower_count = Column(Integer, default=0)
    bio = Column(String)
    source_url = Column(String)
    provenance = Column(JSON)           # source job, scraper info, traceability
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship
    raw_signal = relationship("ScraperRawSignal", backref="staging_contacts")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_staging_contacts_email', 'email'),
        Index('idx_staging_contacts_confidence', 'confidence_score'),
        Index('idx_staging_contacts_type', 'contact_type'),
        Index('idx_staging_contacts_created', 'created_at'),
    )

class ResolvedEntity(Base):
    """Merged canonical entities that map to main Contact table"""
    __tablename__ = "resolved_entities"

    id = Column(Integer, primary_key=True)
    canonical_contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)  # FK to main Contact
    staging_contact_ids = Column(JSON)  # list of merged staging contact IDs
    merge_key = Column(String, index=True)  # deterministic merge key (email, domain+name, etc.)
    confidence_score = Column(Integer)  # combined confidence after merging
    contact_type = Column(String)  # resolved contact type
    email = Column(String, index=True)  # resolved email
    name = Column(String)  # resolved name
    social_handles = Column(JSON)  # merged social handles
    follower_count = Column(Integer, default=0)  # merged follower count
    bio = Column(String)  # merged bio
    source_urls = Column(JSON)  # merged source URLs
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship to canonical contact
    canonical_contact = relationship("Contact", backref="resolved_entities")
    
    # Indexes
    __table_args__ = (
        Index('idx_resolved_entities_merge_key', 'merge_key'),
        Index('idx_resolved_entities_canonical', 'canonical_contact_id'),
        Index('idx_resolved_entities_email', 'email'),
        Index('idx_resolved_entities_confidence', 'confidence_score'),
    )

class GraphNode(Base):
    """Nodes in the manager/artist/curator graph"""
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("resolved_entities.id"))  # Points to resolved entity
    node_type = Column(String)  # "manager", "curator", "artist", "venue", "playlist"
    name = Column(String)  # Node name
    properties = Column(JSON)  # Additional properties like follower count, genre, etc.
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship
    entity = relationship("ResolvedEntity", backref="graph_nodes")
    
    # Indexes
    __table_args__ = (
        Index('idx_graph_nodes_type', 'node_type'),
        Index('idx_graph_nodes_entity', 'entity_id'),
    )

class GraphEdge(Base):
    """Edges between nodes with type and weight"""
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True)
    source_node_id = Column(Integer, ForeignKey("graph_nodes.id"))  # Source node
    target_node_id = Column(Integer, ForeignKey("graph_nodes.id"))  # Target node
    weight = Column(Integer, default=1)  # Relationship strength
    relation_type = Column(String)  # "represents", "follows", "manages", "collaborates", "plays_at"
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_node_id], backref="outgoing_edges")
    target_node = relationship("GraphNode", foreign_keys=[target_node_id], backref="incoming_edges")
    
    # Indexes
    __table_args__ = (
        Index('idx_graph_edges_source', 'source_node_id'),
        Index('idx_graph_edges_target', 'target_node_id'),
        Index('idx_graph_edges_relation', 'relation_type'),
    )

class ClusterRun(Base):
    """Store cluster analysis results"""
    __tablename__ = "cluster_runs"

    id = Column(Integer, primary_key=True)
    run_id = Column(String, unique=True, index=True)  # Unique run identifier
    cluster_id = Column(String)  # Cluster label
    node_ids = Column(JSON)  # List of node IDs in this cluster
    cluster_properties = Column(JSON)  # Properties like influence score, member count, etc.
    created_at = Column(DateTime, server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_cluster_runs_run_id', 'run_id'),
        Index('idx_cluster_runs_cluster', 'cluster_id'),
    )

class JobTracker(Base):
    """Track job execution for idempotency and monitoring"""
    __tablename__ = "job_tracker"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, index=True)  # Same as in queue
    job_type = Column(String)  # scrape:spotify, normalize:signals, etc.
    status = Column(String, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(String)
    result = Column(JSON)  # Job result if successful
    created_at = Column(DateTime, server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_job_tracker_job_id', 'job_id'),
        Index('idx_job_tracker_type', 'job_type'),
        Index('idx_job_tracker_status', 'status'),
    )