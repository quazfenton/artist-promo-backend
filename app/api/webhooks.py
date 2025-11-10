"""Webhook management API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import hmac
import hashlib
import json
from app.models.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.database_service import DatabaseService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class WebhookRequest(BaseModel):
    name: str
    url: HttpUrl
    events: List[str]
    secret: Optional[str] = None
    active: bool = True

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    active: Optional[bool] = None

class WebhookResponse(BaseModel):
    id: int
    name: str
    url: str
    events: List[str]
    active: bool
    created_at: datetime
    last_triggered: Optional[datetime]
    success_count: int
    failure_count: int

@router.post("/")
async def create_webhook(
    request: Request,
    webhook_data: WebhookRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new webhook"""
    
    # Validate events
    valid_events = [
        "contact.created", "contact.updated", "contact.deleted",
        "campaign.created", "campaign.sent", "campaign.completed",
        "scraper.completed", "export.completed"
    ]
    
    invalid_events = [event for event in webhook_data.events if event not in valid_events]
    if invalid_events:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid events: {invalid_events}. Valid events: {valid_events}"
        )
    
    # In real implementation, save to webhooks table
    webhook_id = 1  # Mock ID
    
    return {
        "status": "created",
        "webhook_id": webhook_id,
        "name": webhook_data.name,
        "url": str(webhook_data.url),
        "events": webhook_data.events,
        "message": "Webhook created successfully"
    }

@router.get("/", response_model=List[Dict])
async def get_webhooks(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get user's webhooks"""
    
    # Mock webhooks data
    webhooks = [
        {
            "id": 1,
            "name": "n8n Integration",
            "url": "https://n8n.example.com/webhook/artist-promo",
            "events": ["contact.created", "scraper.completed"],
            "active": True,
            "created_at": datetime.now(),
            "last_triggered": datetime.now(),
            "success_count": 45,
            "failure_count": 2
        },
        {
            "id": 2,
            "name": "Zapier Automation",
            "url": "https://hooks.zapier.com/hooks/catch/123456/abcdef/",
            "events": ["campaign.sent", "export.completed"],
            "active": False,
            "created_at": datetime.now(),
            "last_triggered": None,
            "success_count": 0,
            "failure_count": 0
        }
    ]
    
    if active_only:
        webhooks = [w for w in webhooks if w["active"]]
    
    return webhooks

@router.get("/{webhook_id}")
async def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get webhook details"""
    
    # Mock webhook data
    webhook = {
        "id": webhook_id,
        "name": "n8n Integration",
        "url": "https://n8n.example.com/webhook/artist-promo",
        "events": ["contact.created", "scraper.completed"],
        "active": True,
        "created_at": datetime.now(),
        "last_triggered": datetime.now(),
        "success_count": 45,
        "failure_count": 2,
        "recent_deliveries": [
            {
                "timestamp": datetime.now(),
                "event": "contact.created",
                "status": "success",
                "response_code": 200,
                "response_time": "150ms"
            },
            {
                "timestamp": datetime.now(),
                "event": "scraper.completed",
                "status": "failed",
                "response_code": 500,
                "response_time": "5000ms",
                "error": "Internal server error"
            }
        ]
    }
    
    return webhook

@router.put("/{webhook_id}")
async def update_webhook(
    webhook_id: int,
    request: Request,
    update_data: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update webhook"""
    
    # In real implementation, update webhook in database
    
    return {
        "status": "updated",
        "webhook_id": webhook_id,
        "message": "Webhook updated successfully"
    }

@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete webhook"""
    
    # In real implementation, soft delete webhook
    
    return {
        "status": "deleted",
        "webhook_id": webhook_id,
        "message": "Webhook deleted successfully"
    }

@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Test webhook delivery"""
    
    # In real implementation:
    # 1. Get webhook details
    # 2. Send test payload
    # 3. Return delivery status
    
    test_payload = {
        "event": "webhook.test",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "message": "This is a test webhook delivery",
            "webhook_id": webhook_id
        }
    }
    
    # Mock successful delivery
    return {
        "status": "delivered",
        "webhook_id": webhook_id,
        "test_payload": test_payload,
        "response_code": 200,
        "response_time": "145ms",
        "message": "Test webhook delivered successfully"
    }

@router.get("/{webhook_id}/deliveries")
async def get_webhook_deliveries(
    webhook_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get webhook delivery history"""
    
    # Mock delivery history
    deliveries = [
        {
            "id": f"del_{i}",
            "timestamp": datetime.now(),
            "event": "contact.created" if i % 2 == 0 else "scraper.completed",
            "status": "success" if i % 3 != 0 else "failed",
            "response_code": 200 if i % 3 != 0 else 500,
            "response_time": f"{150 + i * 10}ms",
            "payload_size": f"{1.2 + i * 0.1:.1f}KB"
        }
        for i in range(min(limit, 20))
    ]
    
    return {
        "webhook_id": webhook_id,
        "deliveries": deliveries,
        "total_deliveries": 156,
        "success_rate": 94.2
    }

@router.get("/events/available")
async def get_available_events(current_user: dict = Depends(get_current_user)):
    """Get list of available webhook events"""
    
    events = [
        {
            "name": "contact.created",
            "description": "Triggered when a new contact is created",
            "payload_example": {
                "event": "contact.created",
                "timestamp": "2024-11-10T12:00:00Z",
                "data": {
                    "contact_id": 123,
                    "full_name": "John Doe",
                    "email": "john@example.com",
                    "contact_type": "playlist_curator"
                }
            }
        },
        {
            "name": "contact.updated",
            "description": "Triggered when a contact is updated",
            "payload_example": {
                "event": "contact.updated",
                "timestamp": "2024-11-10T12:00:00Z",
                "data": {
                    "contact_id": 123,
                    "changes": ["priority_score", "verified"]
                }
            }
        },
        {
            "name": "scraper.completed",
            "description": "Triggered when a scraping task completes",
            "payload_example": {
                "event": "scraper.completed",
                "timestamp": "2024-11-10T12:00:00Z",
                "data": {
                    "task_id": "abc123",
                    "scraper_type": "spotify",
                    "results_count": 50,
                    "status": "completed"
                }
            }
        },
        {
            "name": "campaign.sent",
            "description": "Triggered when a campaign is sent",
            "payload_example": {
                "event": "campaign.sent",
                "timestamp": "2024-11-10T12:00:00Z",
                "data": {
                    "campaign_id": 456,
                    "emails_sent": 150,
                    "status": "completed"
                }
            }
        }
    ]
    
    return {"available_events": events}

def _sign_payload(payload: str, secret: str) -> str:
    """Generate webhook signature"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def _verify_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    expected_signature = _sign_payload(payload, secret)
    return hmac.compare_digest(signature, expected_signature)
