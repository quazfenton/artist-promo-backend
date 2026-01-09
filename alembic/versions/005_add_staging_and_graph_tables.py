"""create staging and graph tables"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '005_add_staging_and_graph_tables'
down_revision = '004_add_missing_indexes_constraints'
branch_labels = None
depends_on = None

def upgrade():
    # Create scraper_raw_signals table
    op.create_table(
        'scraper_raw_signals',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('job_id', sa.String, unique=True),
        sa.Column('source_platform', sa.String),
        sa.Column('payload', sa.JSON),
        sa.Column('dedupe_key', sa.String, index=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_scraper_raw_signals_platform', 'source_platform'),
        sa.Index('idx_scraper_raw_signals_created', 'created_at')
    )
    
    # Create staging_contacts table
    op.create_table(
        'staging_contacts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('raw_signal_id', sa.Integer, sa.ForeignKey('scraper_raw_signals.id')),
        sa.Column('name', sa.String),
        sa.Column('email', sa.String, index=True),
        sa.Column('contact_type', sa.String),
        sa.Column('social_handles', sa.JSON),
        sa.Column('confidence_score', sa.Integer),
        sa.Column('platform_ids', sa.JSON),
        sa.Column('follower_count', sa.Integer, default=0),
        sa.Column('bio', sa.String),
        sa.Column('source_url', sa.String),
        sa.Column('provenance', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_staging_contacts_email', 'email'),
        sa.Index('idx_staging_contacts_confidence', 'confidence_score'),
        sa.Index('idx_staging_contacts_type', 'contact_type'),
        sa.Index('idx_staging_contacts_created', 'created_at')
    )
    
    # Create resolved_entities table
    op.create_table(
        'resolved_entities',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('canonical_contact_id', sa.Integer, sa.ForeignKey('contacts.id'), nullable=True),
        sa.Column('staging_contact_ids', sa.JSON),
        sa.Column('merge_key', sa.String, index=True),
        sa.Column('confidence_score', sa.Integer),
        sa.Column('contact_type', sa.String),
        sa.Column('email', sa.String, index=True),
        sa.Column('name', sa.String),
        sa.Column('social_handles', sa.JSON),
        sa.Column('follower_count', sa.Integer, default=0),
        sa.Column('bio', sa.String),
        sa.Column('source_urls', sa.JSON),
        sa.Column('last_updated', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Index('idx_resolved_entities_merge_key', 'merge_key'),
        sa.Index('idx_resolved_entities_canonical', 'canonical_contact_id'),
        sa.Index('idx_resolved_entities_email', 'email'),
        sa.Index('idx_resolved_entities_confidence', 'confidence_score')
    )
    
    # Create graph_nodes table
    op.create_table(
        'graph_nodes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('entity_id', sa.Integer, sa.ForeignKey('resolved_entities.id')),
        sa.Column('node_type', sa.String),
        sa.Column('name', sa.String),
        sa.Column('properties', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_graph_nodes_type', 'node_type'),
        sa.Index('idx_graph_nodes_entity', 'entity_id')
    )
    
    # Create graph_edges table
    op.create_table(
        'graph_edges',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('source_node_id', sa.Integer, sa.ForeignKey('graph_nodes.id')),
        sa.Column('target_node_id', sa.Integer, sa.ForeignKey('graph_nodes.id')),
        sa.Column('weight', sa.Integer, default=1),
        sa.Column('relation_type', sa.String),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_graph_edges_source', 'source_node_id'),
        sa.Index('idx_graph_edges_target', 'target_node_id'),
        sa.Index('idx_graph_edges_relation', 'relation_type')
    )
    
    # Create cluster_runs table
    op.create_table(
        'cluster_runs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('run_id', sa.String, unique=True),
        sa.Column('cluster_id', sa.String),
        sa.Column('node_ids', sa.JSON),
        sa.Column('cluster_properties', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_cluster_runs_run_id', 'run_id'),
        sa.Index('idx_cluster_runs_cluster', 'cluster_id')
    )
    
    # Create job_tracker table
    op.create_table(
        'job_tracker',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('job_id', sa.String, unique=True),
        sa.Column('job_type', sa.String),
        sa.Column('status', sa.String, default="pending"),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('error_message', sa.String),
        sa.Column('result', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_job_tracker_job_id', 'job_id'),
        sa.Index('idx_job_tracker_type', 'job_type'),
        sa.Index('idx_job_tracker_status', 'status')
    )

def downgrade():
    op.drop_table('job_tracker')
    op.drop_table('cluster_runs')
    op.drop_table('graph_edges')
    op.drop_table('graph_nodes')
    op.drop_table('resolved_entities')
    op.drop_table('staging_contacts')
    op.drop_table('scraper_raw_signals')