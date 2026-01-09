"""
Audit trail system for tracking all changes to database records
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import json
from typing import Dict, Any, Optional

Base = declarative_base()

class AuditLog(Base):
    """Audit log table to track all changes to database records"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Entity being audited
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    
    # Action performed
    action = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    action_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # User who performed action
    action_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # IP address and user agent (for security tracking)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Old and new values
    old_values = Column(JSON, nullable=True)  # Values before change
    new_values = Column(JSON, nullable=True)  # Values after change
    changed_fields = Column(JSON, nullable=True)  # List of changed field names
    
    # Additional context
    context = Column(JSON, nullable=True)  # Additional context like request ID, etc.

class AuditMixin:
    """Mixin class to add audit functionality to models"""
    
    def to_dict(self):
        """Convert model instance to dictionary"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
    
    def get_changed_fields(self, old_instance, new_instance):
        """Compare two instances and return changed fields"""
        old_dict = old_instance.to_dict() if hasattr(old_instance, 'to_dict') else old_instance.__dict__
        new_dict = new_instance.to_dict() if hasattr(new_instance, 'to_dict') else new_instance.__dict__
        
        changed_fields = []
        for key, old_val in old_dict.items():
            new_val = new_dict.get(key)
            if old_val != new_val:
                changed_fields.append(key)
        
        return changed_fields

def create_audit_log(
    db: Session,
    table_name: str,
    record_id: int,
    action: str,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    action_by: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
):
    """Create an audit log entry"""
    changed_fields = None
    if old_values and new_values:
        changed_fields = [
            key for key in set(old_values.keys()) | set(new_values.keys())
            if old_values.get(key) != new_values.get(key)
        ]
    
    audit_log = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action.upper(),
        action_by=action_by,
        ip_address=ip_address,
        user_agent=user_agent,
        old_values=old_values,
        new_values=new_values,
        changed_fields=changed_fields,
        context=context
    )
    
    db.add(audit_log)
    db.flush()  # Get the ID without committing

def audit_changes(db: Session, instance, action: str, user_id: Optional[int] = None, 
                 ip_address: Optional[str] = None, user_agent: Optional[str] = None):
    """Generic function to audit changes to any model instance"""
    table_name = instance.__tablename__
    record_id = instance.id
    
    if action.upper() == 'INSERT':
        new_values = instance.to_dict() if hasattr(instance, 'to_dict') else {c.name: getattr(instance, c.name) for c in instance.__table__.columns}
        create_audit_log(
            db, table_name, record_id, action, 
            new_values=new_values,
            action_by=user_id, ip_address=ip_address, user_agent=user_agent
        )
    elif action.upper() == 'UPDATE':
        # For updates, we need to get the old values somehow
        # This would typically be done by storing the original values before the update
        new_values = instance.to_dict() if hasattr(instance, 'to_dict') else {c.name: getattr(instance, c.name) for c in instance.__table__.columns}
        create_audit_log(
            db, table_name, record_id, action,
            new_values=new_values,
            action_by=user_id, ip_address=ip_address, user_agent=user_agent
        )
    elif action.upper() == 'DELETE':
        old_values = instance.to_dict() if hasattr(instance, 'to_dict') else {c.name: getattr(instance, c.name) for c in instance.__table__.columns}
        create_audit_log(
            db, table_name, record_id, action,
            old_values=old_values,
            action_by=user_id, ip_address=ip_address, user_agent=user_agent
        )

# Example of how to use the audit system with SQLAlchemy events
from sqlalchemy import event
from sqlalchemy.orm import object_session

def setup_audit_trail():
    """Setup audit trail for all models"""
    
    @event.listens_for(Session, 'before_commit')
    def capture_changes(session):
        """Capture changes before committing"""
        for obj in session.dirty:
            if hasattr(obj, '__tablename__') and hasattr(obj, 'id'):
                # Get the original values for comparison
                attr_state = session.identity_map._modified_event(obj, True)
                
                # Get old values from the database
                old_values = {}
                new_values = {}
                
                for attr in object_session(obj).__mapper__.column_attrs:
                    hist = object_session(obj).attrs.get_history(attr.key, True)
                    if hist.has_changes():
                        old_values[attr.key] = hist.deleted[0] if hist.deleted else None
                        new_values[attr.key] = hist.added[0] if hist.added else getattr(obj, attr.key)
                
                if old_values and new_values:
                    create_audit_log(
                        session,
                        obj.__tablename__,
                        obj.id,
                        'UPDATE',
                        old_values=old_values,
                        new_values=new_values
                    )
        
        for obj in session.new:
            if hasattr(obj, '__tablename__') and hasattr(obj, 'id'):
                new_values = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
                create_audit_log(
                    session,
                    obj.__tablename__,
                    obj.id,
                    'INSERT',
                    new_values=new_values
                )
        
        for obj in session.deleted:
            if hasattr(obj, '__tablename__') and hasattr(obj, 'id'):
                old_values = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
                create_audit_log(
                    session,
                    obj.__tablename__,
                    obj.id,
                    'DELETE',
                    old_values=old_values
                )

# Migration for audit logs table (if not already created)
def create_audit_tables(engine):
    """Create audit tables if they don't exist"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Example usage
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Create an example engine and session
    engine = create_engine("sqlite:///./test.db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Example of creating an audit log
    db = SessionLocal()
    try:
        create_audit_log(
            db,
            table_name="contacts",
            record_id=1,
            action="INSERT",
            new_values={"name": "John Doe", "email": "john@example.com"},
            action_by=1
        )
        db.commit()
    finally:
        db.close()