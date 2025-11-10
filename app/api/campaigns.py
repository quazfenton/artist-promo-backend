"""Campaign management API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.database import get_db, Contact
from app.middleware.auth_middleware import get_current_user
from app.services.database_service import DatabaseService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# Campaign models (would normally be in models/database.py)
Base = declarative_base()

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft")  # draft, active, paused, completed
    
    # Email template
    subject_template = Column(String(500), nullable=False)
    body_template = Column(Text, nullable=False)
    
    # Targeting
    target_filters = Column(JSON, nullable=True)
    contact_ids = Column(JSON, nullable=True)  # Specific contact IDs
    
    # Metrics
    total_contacts = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_replied = Column(Integer, default=0)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    subject_template: str
    body_template: str
    target_filters: Optional[Dict[str, Any]] = {}
    contact_ids: Optional[List[int]] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    status: Optional[str] = None

class CampaignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    total_contacts: int
    emails_sent: int
    open_rate: float
    reply_rate: float
    created_at: datetime

@router.post("/", response_model=Dict)
async def create_campaign(
    request: Request,
    campaign_data: CampaignRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new email campaign"""
    
    db_service = DatabaseService(db, current_user["user_id"], request)
    
    # Calculate target contacts
    target_count = _count_target_contacts(db, campaign_data.target_filters, campaign_data.contact_ids)
    
    # Create campaign (simplified - would use proper model)
    campaign_dict = {
        "name": campaign_data.name,
        "description": campaign_data.description,
        "subject_template": campaign_data.subject_template,
        "body_template": campaign_data.body_template,
        "target_filters": campaign_data.target_filters,
        "contact_ids": campaign_data.contact_ids,
        "total_contacts": target_count,
        "created_by": current_user["user_id"]
    }
    
    # In real implementation, save to campaigns table
    campaign_id = 1  # Mock ID
    
    return {
        "status": "created",
        "campaign_id": campaign_id,
        "name": campaign_data.name,
        "target_contacts": target_count,
        "message": "Campaign created successfully"
    }

@router.get("/", response_model=List[Dict])
async def get_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get user's campaigns"""
    
    # Mock campaigns data
    campaigns = [
        {
            "id": 1,
            "name": "Hip-Hop Curator Outreach Q4",
            "description": "Targeting high-priority playlist curators",
            "status": "active",
            "total_contacts": 150,
            "emails_sent": 120,
            "emails_opened": 45,
            "emails_replied": 12,
            "open_rate": 37.5,
            "reply_rate": 10.0,
            "created_at": datetime.now()
        },
        {
            "id": 2,
            "name": "New Release Promotion",
            "description": "Promoting latest single to music blogs",
            "status": "draft",
            "total_contacts": 75,
            "emails_sent": 0,
            "emails_opened": 0,
            "emails_replied": 0,
            "open_rate": 0.0,
            "reply_rate": 0.0,
            "created_at": datetime.now()
        }
    ]
    
    if status:
        campaigns = [c for c in campaigns if c["status"] == status]
    
    return campaigns[:limit]

@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get campaign details"""
    
    # Mock campaign data
    campaign = {
        "id": campaign_id,
        "name": "Hip-Hop Curator Outreach Q4",
        "description": "Targeting high-priority playlist curators for new album promotion",
        "status": "active",
        "subject_template": "New Hip-Hop Release: {{artist_name}} - {{track_title}}",
        "body_template": """Hi {{contact_name}},

I hope this email finds you well. I'm reaching out regarding a new hip-hop release that would be perfect for your {{playlist_name}} playlist.

{{artist_name}} just dropped "{{track_title}}" - a fresh take on {{genre}} that's been gaining traction with {{follower_count}}+ followers.

Track details:
- Artist: {{artist_name}}
- Title: {{track_title}}
- Genre: {{genre}}
- Spotify: {{spotify_link}}

Would you be interested in considering this for your playlist? I'd be happy to send over the track and any additional materials.

Best regards,
{{sender_name}}""",
        "target_filters": {
            "contact_type": "playlist_curator",
            "min_score": 70,
            "min_followers": 1000
        },
        "total_contacts": 150,
        "emails_sent": 120,
        "emails_opened": 45,
        "emails_replied": 12,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    return campaign

@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    request: Request,
    update_data: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update campaign"""
    
    # In real implementation, update campaign in database
    
    return {
        "status": "updated",
        "campaign_id": campaign_id,
        "message": "Campaign updated successfully"
    }

@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Send campaign emails"""
    
    # In real implementation:
    # 1. Get campaign details
    # 2. Get target contacts
    # 3. Queue email sending tasks
    # 4. Update campaign status
    
    return {
        "status": "queued",
        "campaign_id": campaign_id,
        "message": "Campaign emails queued for sending",
        "estimated_completion": "30-60 minutes"
    }

@router.get("/{campaign_id}/analytics")
async def get_campaign_analytics(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed campaign analytics"""
    
    # Mock analytics data
    analytics = {
        "campaign_id": campaign_id,
        "overview": {
            "total_contacts": 150,
            "emails_sent": 120,
            "emails_delivered": 118,
            "emails_opened": 45,
            "emails_clicked": 15,
            "emails_replied": 12,
            "emails_bounced": 2,
            "open_rate": 38.1,
            "click_rate": 12.7,
            "reply_rate": 10.2,
            "bounce_rate": 1.7
        },
        "timeline": [
            {"date": "2024-11-01", "sent": 30, "opened": 12, "replied": 3},
            {"date": "2024-11-02", "sent": 40, "opened": 15, "replied": 4},
            {"date": "2024-11-03", "sent": 50, "opened": 18, "replied": 5}
        ],
        "top_performers": [
            {"contact_name": "DJ MixMaster", "opened": True, "replied": True, "score": 95},
            {"contact_name": "Playlist Pro", "opened": True, "replied": False, "score": 88}
        ],
        "engagement_by_platform": {
            "spotify": {"sent": 60, "opened": 25, "replied": 8},
            "instagram": {"sent": 40, "opened": 15, "replied": 3},
            "youtube": {"sent": 20, "opened": 5, "replied": 1}
        }
    }
    
    return analytics

@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete campaign"""
    
    # In real implementation, soft delete campaign
    
    return {
        "status": "deleted",
        "campaign_id": campaign_id,
        "message": "Campaign deleted successfully"
    }

def _count_target_contacts(db: Session, filters: Dict[str, Any], contact_ids: Optional[List[int]]) -> int:
    """Count contacts matching campaign criteria"""
    
    if contact_ids:
        return len(contact_ids)
    
    query = db.query(Contact).filter(Contact.deleted_at.is_(None))
    
    if filters.get("contact_type"):
        query = query.filter(Contact.contact_type == filters["contact_type"])
    
    if filters.get("min_score"):
        query = query.filter(Contact.priority_score >= filters["min_score"])
    
    if filters.get("min_followers"):
        query = query.filter(Contact.follower_count >= filters["min_followers"])
    
    if filters.get("verified_only"):
        query = query.filter(Contact.verified == True)
    
    return query.count()
