"""Add audit fields and soft delete support

Revision ID: 002
Revises: 001
Create Date: 2024-11-10 01:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    # Add audit fields to contacts table
    op.add_column('contacts', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('contacts', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('contacts', sa.Column('updated_by', sa.Integer(), nullable=True))
    
    # Add foreign key constraints
    op.create_foreign_key('fk_contacts_created_by', 'contacts', 'users', ['created_by'], ['id'])
    op.create_foreign_key('fk_contacts_updated_by', 'contacts', 'users', ['updated_by'], ['id'])
    
    # Add audit fields to playlists table
    op.add_column('playlists', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('playlists', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('playlists', sa.Column('updated_by', sa.Integer(), nullable=True))
    
    # Add foreign key constraints for playlists
    op.create_foreign_key('fk_playlists_created_by', 'playlists', 'users', ['created_by'], ['id'])
    op.create_foreign_key('fk_playlists_updated_by', 'playlists', 'users', ['updated_by'], ['id'])
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_table_name', 'audit_logs', ['table_name'], unique=False)
    op.create_index('ix_audit_logs_record_id', 'audit_logs', ['record_id'], unique=False)
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'], unique=False)
    
    # Create data_validation_errors table
    op.create_table('data_validation_errors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=True),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('invalid_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add performance indexes
    op.create_index('idx_contacts_active', 'contacts', ['deleted_at', 'priority_score'], unique=False)
    op.create_index('idx_playlists_active', 'playlists', ['deleted_at', 'follower_count'], unique=False)
    op.create_index('idx_contact_search', 'contacts', ['full_name', 'email', 'company'], unique=False)
    op.create_index('idx_playlist_search', 'playlists', ['name', 'owner_username'], unique=False)

def downgrade():
    # Drop indexes
    op.drop_index('idx_playlist_search', table_name='playlists')
    op.drop_index('idx_contact_search', table_name='contacts')
    op.drop_index('idx_playlists_active', table_name='playlists')
    op.drop_index('idx_contacts_active', table_name='contacts')
    
    # Drop tables
    op.drop_table('data_validation_errors')
    op.drop_index('ix_audit_logs_timestamp', table_name='audit_logs')
    op.drop_index('ix_audit_logs_record_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_table_name', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    # Drop foreign key constraints
    op.drop_constraint('fk_playlists_updated_by', 'playlists', type_='foreignkey')
    op.drop_constraint('fk_playlists_created_by', 'playlists', type_='foreignkey')
    op.drop_constraint('fk_contacts_updated_by', 'contacts', type_='foreignkey')
    op.drop_constraint('fk_contacts_created_by', 'contacts', type_='foreignkey')
    
    # Drop audit columns
    op.drop_column('playlists', 'updated_by')
    op.drop_column('playlists', 'created_by')
    op.drop_column('playlists', 'deleted_at')
    op.drop_column('contacts', 'updated_by')
    op.drop_column('contacts', 'created_by')
    op.drop_column('contacts', 'deleted_at')
