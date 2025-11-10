"""Add intelligence and ML features

Revision ID: 003
Revises: 002
Create Date: 2024-11-10 03:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    # Add semantic analysis fields to contacts
    op.add_column('contacts', sa.Column('semantic_tags', sa.JSON(), nullable=True))
    op.add_column('contacts', sa.Column('similarity_score', sa.Float(), nullable=True))
    op.add_column('contacts', sa.Column('audio_profile', sa.JSON(), nullable=True))
    
    # Add audio profile to playlists
    op.add_column('playlists', sa.Column('audio_profile', sa.JSON(), nullable=True))
    
    # Create email templates table
    op.create_table('email_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('variant', sa.String(length=1), nullable=False),
        sa.Column('campaign_type', sa.String(length=100), nullable=False),
        sa.Column('sent_count', sa.Integer(), nullable=True),
        sa.Column('opened_count', sa.Integer(), nullable=True),
        sa.Column('clicked_count', sa.Integer(), nullable=True),
        sa.Column('replied_count', sa.Integer(), nullable=True),
        sa.Column('open_rate', sa.Float(), nullable=True),
        sa.Column('click_rate', sa.Float(), nullable=True),
        sa.Column('reply_rate', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create A/B test campaigns table
    op.create_table('ab_test_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_ids', sa.String(length=255), nullable=False),
        sa.Column('test_size_per_variant', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('winner_template_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add indexes for performance
    op.create_index('idx_contacts_semantic', 'contacts', ['semantic_tags'], postgresql_using='gin')
    op.create_index('idx_contacts_similarity', 'contacts', ['similarity_score'])
    op.create_index('idx_playlists_audio', 'playlists', ['audio_profile'], postgresql_using='gin')
    op.create_index('idx_templates_performance', 'email_templates', ['reply_rate', 'confidence_score'])

def downgrade():
    # Drop indexes
    op.drop_index('idx_templates_performance', table_name='email_templates')
    op.drop_index('idx_playlists_audio', table_name='playlists')
    op.drop_index('idx_contacts_similarity', table_name='contacts')
    op.drop_index('idx_contacts_semantic', table_name='contacts')
    
    # Drop tables
    op.drop_table('ab_test_campaigns')
    op.drop_table('email_templates')
    
    # Drop columns
    op.drop_column('playlists', 'audio_profile')
    op.drop_column('contacts', 'audio_profile')
    op.drop_column('contacts', 'similarity_score')
    op.drop_column('contacts', 'semantic_tags')
