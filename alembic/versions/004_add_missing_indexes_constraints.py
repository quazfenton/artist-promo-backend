"""Database migration for additional indexes and constraints"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = '004_add_missing_indexes_constraints'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing indexes for better performance
    op.create_index('ix_contacts_type_priority', 'contacts', ['contact_type', 'priority_score'], unique=False)
    op.create_index('ix_contacts_email_verified', 'contacts', ['email', 'email_verified'], unique=False)
    op.create_index('ix_contacts_follower_count', 'contacts', ['follower_count'], unique=False)
    op.create_index('ix_contacts_last_active', 'contacts', ['last_active_at'], unique=False)
    op.create_index('ix_contacts_genres', 'contacts', ['genres'], postgresql_using='gin')
    
    op.create_index('ix_playlists_platform_followers', 'playlists', ['platform', 'follower_count'], unique=False)
    op.create_index('ix_playlists_is_active', 'playlists', ['is_active'], unique=False)
    op.create_index('ix_playlists_genres', 'playlists', ['genres'], postgresql_using='gin')
    op.create_index('ix_playlists_relevance_score', 'playlists', ['relevance_score'], unique=False)
    
    op.create_index('ix_venues_city', 'venues', ['city'], unique=False)
    op.create_index('ix_venues_capacity', 'venues', ['capacity'], unique=False)
    op.create_index('ix_venues_genres', 'venues', ['genres'], postgresql_using='gin')
    
    op.create_index('ix_outreach_logs_contact_id', 'outreach_logs', ['contact_id'], unique=False)
    op.create_index('ix_outreach_logs_status', 'outreach_logs', ['status'], unique=False)
    op.create_index('ix_outreach_logs_sent_at', 'outreach_logs', ['sent_at'], unique=False)
    
    op.create_index('ix_scraper_runs_scraper_name', 'scraper_runs', ['scraper_name'], unique=False)
    op.create_index('ix_scraper_runs_status', 'scraper_runs', ['status'], unique=False)
    op.create_index('ix_scraper_runs_started_at', 'scraper_runs', ['started_at'], unique=False)
    
    # Add composite indexes for common queries
    op.create_index('ix_contacts_type_score_verified', 'contacts', ['contact_type', 'priority_score', 'verified'], unique=False)
    op.create_index('ix_contacts_platform_follower', 'contacts', ['source_platform', 'follower_count'], unique=False)
    
    # Add indexes for soft delete queries
    op.create_index('ix_contacts_not_deleted', 'contacts', ['deleted_at'], unique=False, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index('ix_playlists_not_deleted', 'playlists', ['deleted_at'], unique=False, postgresql_where=sa.text("deleted_at IS NULL"))
    
    # Add foreign key constraints if they don't exist
    # Contacts table
    try:
        op.create_foreign_key('fk_contacts_created_by_users', 'contacts', 'users', ['created_by'], ['id'])
    except:
        pass  # Constraint might already exist
    
    try:
        op.create_foreign_key('fk_contacts_updated_by_users', 'contacts', 'users', ['updated_by'], ['id'])
    except:
        pass
    
    # Playlists table
    try:
        op.create_foreign_key('fk_playlists_created_by_users', 'playlists', 'users', ['created_by'], ['id'])
    except:
        pass
    
    try:
        op.create_foreign_key('fk_playlists_updated_by_users', 'playlists', 'users', ['updated_by'], ['id'])
    except:
        pass
    
    try:
        op.create_foreign_key('fk_playlists_curator_contacts', 'playlists', 'contacts', ['curator_id'], ['id'])
    except:
        pass
    
    # Outreach logs table
    try:
        op.create_foreign_key('fk_outreach_logs_contact', 'outreach_logs', 'contacts', ['contact_id'], ['id'])
    except:
        pass
    
    # Add check constraints for data integrity
    # Contacts table
    op.create_check_constraint('ck_contacts_follower_count', 'contacts', 'follower_count >= 0')
    op.create_check_constraint('ck_contacts_priority_score_range', 'contacts', 'priority_score >= 0 AND priority_score <= 10')
    op.create_check_constraint('ck_contacts_engagement_rate_range', 'contacts', 'engagement_rate >= 0 AND engagement_rate <= 100')
    
    # Playlists table
    op.create_check_constraint('ck_playlists_follower_count', 'playlists', 'follower_count >= 0')
    op.create_check_constraint('ck_playlists_track_count', 'playlists', 'track_count >= 0')
    op.create_check_constraint('ck_playlists_relevance_score_range', 'playlists', 'relevance_score >= 0 AND relevance_score <= 10')
    
    # Venues table
    op.create_check_constraint('ck_venues_capacity', 'venues', 'capacity >= 0')
    op.create_check_constraint('ck_venues_avg_attendance', 'venues', 'avg_attendance >= 0')
    
    # Add unique constraints where appropriate
    # Note: We can't add unique constraint on email without handling NULLs differently
    # Instead, we'll create a partial unique index for non-null emails
    op.create_index('ix_contacts_unique_email', 'contacts', ['email'], unique=True, postgresql_where=sa.text("email IS NOT NULL AND deleted_at IS NULL"))
    
    # Add full-text search indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contacts_full_text_search 
        ON contacts 
        USING gin(to_tsvector('english', COALESCE(full_name, '') || ' ' || COALESCE(bio, '') || ' ' || COALESCE(company, '')))
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_playlists_full_text_search 
        ON playlists 
        USING gin(to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '')))
    """)

def downgrade():
    # Drop indexes
    op.drop_index('ix_contacts_full_text_search', table_name='contacts')
    op.drop_index('ix_playlists_full_text_search', table_name='playlists')
    
    op.drop_index('ix_contacts_unique_email', table_name='contacts')
    
    op.drop_index('ix_contacts_not_deleted', table_name='contacts')
    op.drop_index('ix_playlists_not_deleted', table_name='playlists')
    
    op.drop_index('ix_contacts_platform_follower', table_name='contacts')
    op.drop_index('ix_contacts_type_score_verified', table_name='contacts')
    
    op.drop_index('ix_scraper_runs_started_at', table_name='scraper_runs')
    op.drop_index('ix_scraper_runs_status', table_name='scraper_runs')
    op.drop_index('ix_scraper_runs_scraper_name', table_name='scraper_runs')
    
    op.drop_index('ix_outreach_logs_sent_at', table_name='outreach_logs')
    op.drop_index('ix_outreach_logs_status', table_name='outreach_logs')
    op.drop_index('ix_outreach_logs_contact_id', table_name='outreach_logs')
    
    op.drop_index('ix_venues_genres', table_name='venues')
    op.drop_index('ix_venues_capacity', table_name='venues')
    op.drop_index('ix_venues_city', table_name='venues')
    
    op.drop_index('ix_playlists_relevance_score', table_name='playlists')
    op.drop_index('ix_playlists_is_active', table_name='playlists')
    op.drop_index('ix_playlists_genres', table_name='playlists')
    op.drop_index('ix_playlists_platform_followers', table_name='playlists')
    
    op.drop_index('ix_contacts_last_active', table_name='contacts')
    op.drop_index('ix_contacts_follower_count', table_name='contacts')
    op.drop_index('ix_contacts_genres', table_name='contacts')
    op.drop_index('ix_contacts_email_verified', table_name='contacts')
    op.drop_index('ix_contacts_type_priority', table_name='contacts')
    
    # Drop constraints
    op.drop_constraint('ck_contacts_follower_count', 'contacts', type_='check')
    op.drop_constraint('ck_contacts_priority_score_range', 'contacts', type_='check')
    op.drop_constraint('ck_contacts_engagement_rate_range', 'contacts', type_='check')
    
    op.drop_constraint('ck_playlists_follower_count', 'playlists', type_='check')
    op.drop_constraint('ck_playlists_track_count', 'playlists', type_='check')
    op.drop_constraint('ck_playlists_relevance_score_range', 'playlists', type_='check')
    
    op.drop_constraint('ck_venues_capacity', 'venues', type_='check')
    op.drop_constraint('ck_venues_avg_attendance', 'venues', type_='check')
    
    # Drop foreign key constraints
    op.drop_constraint('fk_outreach_logs_contact', 'outreach_logs', type_='foreignkey')
    op.drop_constraint('fk_playlists_curator_contacts', 'playlists', type_='foreignkey')
    op.drop_constraint('fk_playlists_updated_by_users', 'playlists', type_='foreignkey')
    op.drop_constraint('fk_playlists_created_by_users', 'playlists', type_='foreignkey')
    op.drop_constraint('fk_contacts_updated_by_users', 'contacts', type_='foreignkey')
    op.drop_constraint('fk_contacts_created_by_users', 'contacts', type_='foreignkey')