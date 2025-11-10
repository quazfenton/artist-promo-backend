"""Database utilities and mixins"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Type, Optional, List, Dict, Any
from app.models.audit import AuditLog
import json

class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    @classmethod
    def active_only(cls, query):
        """Filter to only active (non-deleted) records"""
        return query.filter(cls.deleted_at.is_(None))
    
    def soft_delete(self, user_id: Optional[int] = None):
        """Soft delete this record"""
        self.deleted_at = datetime.utcnow()
        if user_id and hasattr(self, 'updated_by'):
            self.updated_by = user_id
    
    def restore(self, user_id: Optional[int] = None):
        """Restore a soft-deleted record"""
        self.deleted_at = None
        if user_id and hasattr(self, 'updated_by'):
            self.updated_by = user_id
    
    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted"""
        return self.deleted_at is not None


class AuditLogger:
    """Audit logging utility"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_change(
        self,
        table_name: str,
        record_id: int,
        action: str,
        user_id: Optional[int] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        """Log a database change"""
        
        # Calculate changed fields
        changed_fields = []
        if old_values and new_values:
            for key in new_values:
                if key in old_values and old_values[key] != new_values[key]:
                    changed_fields.append(key)
        
        audit_log = AuditLog(
            table_name=table_name,
            record_id=record_id,
            action=action,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )
        
        self.db.add(audit_log)
        self.db.commit()


class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Basic URL validation"""
        import re
        pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def validate_follower_count(count: int) -> bool:
        """Validate follower count is reasonable"""
        return 0 <= count <= 1000000000  # 1 billion max
    
    @staticmethod
    def validate_priority_score(score: float) -> bool:
        """Validate priority score is in valid range"""
        return 0.0 <= score <= 100.0


def get_active_records(db: Session, model: Type, **filters):
    """Get only active (non-deleted) records"""
    query = db.query(model).filter(model.deleted_at.is_(None))
    
    for key, value in filters.items():
        if hasattr(model, key):
            query = query.filter(getattr(model, key) == value)
    
    return query


def bulk_soft_delete(db: Session, model: Type, record_ids: List[int], user_id: Optional[int] = None):
    """Soft delete multiple records"""
    update_data = {"deleted_at": datetime.utcnow()}
    if user_id:
        update_data["updated_by"] = user_id
    
    db.query(model).filter(model.id.in_(record_ids)).update(update_data)
    db.commit()


def create_indexes_if_not_exist(engine):
    """Create database indexes if they don't exist"""
    from sqlalchemy import text
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_contacts_active ON contacts(deleted_at, priority_score) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_playlists_active ON playlists(deleted_at, follower_count) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_lookup ON audit_logs(table_name, record_id, timestamp)",
    ]
    
    with engine.connect() as conn:
        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
                conn.commit()
            except Exception as e:
                print(f"Index creation failed: {e}")
                continue
