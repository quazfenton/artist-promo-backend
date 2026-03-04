"""add evidence table and state tracking fields to resolved_entities"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '006_add_evidence_and_state_tracking'
down_revision = '005_add_staging_and_graph_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Create evidence table
    op.create_table(
        'evidence',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('entity_id', sa.Integer, sa.ForeignKey('resolved_entities.id'), nullable=False, index=True),
        sa.Column('email', sa.String, nullable=False, index=True),
        sa.Column('source', sa.String, nullable=False),  # official_site, social_bio, mirror, whois, press_kit
        sa.Column('signal', sa.String, nullable=False),  # bio_email, whois_email, link_in_bio, etc.
        sa.Column('url', sa.String, nullable=False),
        sa.Column('confidence', sa.Float, default=1.0),
        sa.Column('metadata', sa.JSON),  # Additional context like screenshot_hash, page_title, etc.
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Index('idx_evidence_entity', 'entity_id'),
        sa.Index('idx_evidence_email', 'email'),
        sa.Index('idx_evidence_source', 'source'),
        sa.Index('idx_evidence_created', 'created_at')
    )
    
    # Add state tracking fields to resolved_entities
    op.add_column('resolved_entities', sa.Column('pipeline_state', sa.String, default='scraped', nullable=True))
    op.add_column('resolved_entities', sa.Column('state_history', sa.JSON, default=list, nullable=True))
    op.add_column('resolved_entities', sa.Column('quality_score', sa.Float, default=0.0, nullable=True))
    op.add_column('resolved_entities', sa.Column('outreach_ready', sa.Boolean, default=False, nullable=True))
    op.add_column('resolved_entities', sa.Column('last_verified_at', sa.DateTime, nullable=True))
    
    # Create indexes for new fields
    op.create_index('idx_resolved_entities_state', 'resolved_entities', ['pipeline_state'])
    op.create_index('idx_resolved_entities_outreach_ready', 'resolved_entities', ['outreach_ready'])

def downgrade():
    # Remove indexes
    op.drop_index('idx_resolved_entities_outreach_ready', table_name='resolved_entities')
    op.drop_index('idx_resolved_entities_state', table_name='resolved_entities')
    
    # Remove state tracking fields from resolved_entities
    op.drop_column('resolved_entities', 'last_verified_at')
    op.drop_column('resolved_entities', 'outreach_ready')
    op.drop_column('resolved_entities', 'quality_score')
    op.drop_column('resolved_entities', 'state_history')
    op.drop_column('resolved_entities', 'pipeline_state')
    
    # Drop evidence table
    op.drop_table('evidence')
