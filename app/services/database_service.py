"""Enhanced database service with validation and audit logging"""
from sqlalchemy.orm import Session
from typing import Type, Optional, Dict, Any, List
from datetime import datetime
from app.utils.database import AuditLogger, DataValidator, SoftDeleteMixin
from app.models.database import Contact, Playlist, User
from app.models.audit import DataValidationError
from fastapi import Request
import uuid

class DatabaseService:
    """Enhanced database operations with audit logging and validation"""
    
    def __init__(self, db: Session, user_id: Optional[int] = None, request: Optional[Request] = None):
        self.db = db
        self.user_id = user_id
        self.audit_logger = AuditLogger(db)
        self.request_id = str(uuid.uuid4())[:8]
        self.ip_address = request.client.host if request else None
        self.user_agent = request.headers.get("user-agent") if request else None
    
    def create_contact(self, contact_data: Dict[str, Any]) -> Contact:
        """Create a new contact with validation and audit logging"""
        
        # Validate data
        self._validate_contact_data(contact_data)
        
        # Set audit fields
        contact_data['created_by'] = self.user_id
        contact_data['updated_by'] = self.user_id
        
        # Create contact
        contact = Contact(**contact_data)
        self.db.add(contact)
        self.db.flush()  # Get ID without committing
        
        # Log creation
        self.audit_logger.log_change(
            table_name="contacts",
            record_id=contact.id,
            action="INSERT",
            user_id=self.user_id,
            new_values=contact_data,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            request_id=self.request_id
        )
        
        self.db.commit()
        return contact
    
    def update_contact(self, contact_id: int, update_data: Dict[str, Any]) -> Contact:
        """Update contact with validation and audit logging"""
        
        contact = self.db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.deleted_at.is_(None)
        ).first()
        
        if not contact:
            raise ValueError(f"Contact {contact_id} not found or deleted")
        
        # Store old values for audit
        old_values = {
            key: getattr(contact, key) 
            for key in update_data.keys() 
            if hasattr(contact, key)
        }
        
        # Validate new data
        self._validate_contact_data(update_data, is_update=True)
        
        # Update fields
        update_data['updated_by'] = self.user_id
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            if hasattr(contact, key):
                setattr(contact, key, value)
        
        # Log update
        self.audit_logger.log_change(
            table_name="contacts",
            record_id=contact.id,
            action="UPDATE",
            user_id=self.user_id,
            old_values=old_values,
            new_values=update_data,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            request_id=self.request_id
        )
        
        self.db.commit()
        return contact
    
    def soft_delete_contact(self, contact_id: int) -> bool:
        """Soft delete a contact"""
        
        contact = self.db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.deleted_at.is_(None)
        ).first()
        
        if not contact:
            return False
        
        # Soft delete
        contact.soft_delete(self.user_id)
        
        # Log deletion
        self.audit_logger.log_change(
            table_name="contacts",
            record_id=contact.id,
            action="DELETE",
            user_id=self.user_id,
            old_values={"deleted_at": None},
            new_values={"deleted_at": contact.deleted_at.isoformat()},
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            request_id=self.request_id
        )
        
        self.db.commit()
        return True
    
    def get_active_contacts(self, **filters) -> List[Contact]:
        """Get active contacts with filters"""
        query = self.db.query(Contact).filter(Contact.deleted_at.is_(None))
        
        for key, value in filters.items():
            if hasattr(Contact, key) and value is not None:
                query = query.filter(getattr(Contact, key) == value)
        
        return query.all()
    
    def bulk_update_scores(self, score_updates: List[Dict[str, Any]]) -> int:
        """Bulk update priority scores"""
        updated_count = 0
        
        for update in score_updates:
            contact_id = update.get('contact_id')
            new_score = update.get('priority_score')
            
            if not contact_id or new_score is None:
                continue
            
            contact = self.db.query(Contact).filter(
                Contact.id == contact_id,
                Contact.deleted_at.is_(None)
            ).first()
            
            if contact:
                old_score = contact.priority_score
                contact.priority_score = new_score
                contact.updated_by = self.user_id
                contact.updated_at = datetime.utcnow()
                updated_count += 1
                
                # Log score update
                self.audit_logger.log_change(
                    table_name="contacts",
                    record_id=contact.id,
                    action="UPDATE",
                    user_id=self.user_id,
                    old_values={"priority_score": old_score},
                    new_values={"priority_score": new_score},
                    ip_address=self.ip_address,
                    user_agent=self.user_agent,
                    request_id=self.request_id
                )
        
        self.db.commit()
        return updated_count
    
    def _validate_contact_data(self, data: Dict[str, Any], is_update: bool = False):
        """Validate contact data"""
        errors = []
        
        # Email validation
        if 'email' in data and data['email']:
            if not DataValidator.validate_email(data['email']):
                errors.append("Invalid email format")
        
        # URL validation
        for url_field in ['website', 'source_url', 'linkedin_url']:
            if url_field in data and data[url_field]:
                if not DataValidator.validate_url(data[url_field]):
                    errors.append(f"Invalid {url_field} format")
        
        # Follower count validation
        if 'follower_count' in data:
            if not DataValidator.validate_follower_count(data['follower_count']):
                errors.append("Invalid follower count")
        
        # Priority score validation
        if 'priority_score' in data:
            if not DataValidator.validate_priority_score(data['priority_score']):
                errors.append("Priority score must be between 0 and 100")
        
        # Log validation errors
        if errors:
            for error in errors:
                validation_error = DataValidationError(
                    table_name="contacts",
                    field_name="multiple" if len(errors) > 1 else "unknown",
                    error_type="validation_failed",
                    error_message=error,
                    invalid_value=str(data)
                )
                self.db.add(validation_error)
            
            self.db.commit()
            raise ValueError(f"Validation failed: {', '.join(errors)}")
    
    def get_audit_trail(self, table_name: str, record_id: int) -> List[Dict]:
        """Get audit trail for a record"""
        from app.models.audit import AuditLog
        
        logs = self.db.query(AuditLog).filter(
            AuditLog.table_name == table_name,
            AuditLog.record_id == record_id
        ).order_by(AuditLog.timestamp.desc()).all()
        
        return [
            {
                "timestamp": log.timestamp,
                "action": log.action,
                "user_id": log.user_id,
                "changed_fields": log.changed_fields,
                "old_values": log.old_values,
                "new_values": log.new_values
            }
            for log in logs
        ]
