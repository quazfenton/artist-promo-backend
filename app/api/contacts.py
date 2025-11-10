"""Enhanced contact management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from app.models.database import get_db, ContactType
from app.services.database_service import DatabaseService
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/contacts", tags=["contacts"])

class ContactCreateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_type: ContactType
    company: Optional[str] = None
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    website: Optional[str] = None
    bio: Optional[str] = None
    follower_count: int = 0

class ContactUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    website: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    priority_score: Optional[float] = None

class BulkScoreUpdate(BaseModel):
    updates: List[Dict[str, any]]  # [{"contact_id": 1, "priority_score": 85.5}]

@router.post("/")
async def create_contact(
    request: Request,
    contact_data: ContactCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new contact with validation and audit logging"""
    
    db_service = DatabaseService(db, current_user["user_id"], request)
    
    try:
        contact = db_service.create_contact(contact_data.dict(exclude_unset=True))
        return {
            "status": "success",
            "contact_id": contact.id,
            "message": "Contact created successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create contact")

@router.put("/{contact_id}")
async def update_contact(
    contact_id: int,
    request: Request,
    update_data: ContactUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update contact with validation and audit logging"""
    
    db_service = DatabaseService(db, current_user["user_id"], request)
    
    try:
        contact = db_service.update_contact(contact_id, update_data.dict(exclude_unset=True))
        return {
            "status": "success",
            "contact_id": contact.id,
            "message": "Contact updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update contact")

@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Soft delete a contact"""
    
    db_service = DatabaseService(db, current_user["user_id"], request)
    
    success = db_service.soft_delete_contact(contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {
        "status": "success",
        "message": "Contact deleted successfully"
    }

@router.post("/bulk-score-update")
async def bulk_update_scores(
    request: Request,
    score_data: BulkScoreUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Bulk update contact priority scores"""
    
    db_service = DatabaseService(db, current_user["user_id"], request)
    
    updated_count = db_service.bulk_update_scores(score_data.updates)
    
    return {
        "status": "success",
        "updated_count": updated_count,
        "message": f"Updated {updated_count} contact scores"
    }

@router.get("/{contact_id}/audit")
async def get_contact_audit_trail(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get audit trail for a contact"""
    
    db_service = DatabaseService(db, current_user["user_id"])
    audit_trail = db_service.get_audit_trail("contacts", contact_id)
    
    return {
        "contact_id": contact_id,
        "audit_trail": audit_trail
    }

@router.post("/deduplicate")
async def deduplicate_contacts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Find and merge duplicate contacts"""
    
    # Simple email-based deduplication
    from sqlalchemy import func
    from app.models.database import Contact
    
    duplicates = db.query(Contact.email, func.count(Contact.id).label('count')).filter(
        Contact.email.isnot(None),
        Contact.deleted_at.is_(None)
    ).group_by(Contact.email).having(func.count(Contact.id) > 1).all()
    
    db_service = DatabaseService(db, current_user["user_id"], request)
    merged_count = 0
    
    for email, count in duplicates:
        contacts = db.query(Contact).filter(
            Contact.email == email,
            Contact.deleted_at.is_(None)
        ).order_by(Contact.priority_score.desc()).all()
        
        # Keep the highest scoring contact, soft delete others
        primary_contact = contacts[0]
        for duplicate in contacts[1:]:
            db_service.soft_delete_contact(duplicate.id)
            merged_count += 1
    
    return {
        "status": "success",
        "duplicates_found": len(duplicates),
        "contacts_merged": merged_count
    }
