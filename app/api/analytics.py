"""Analytics and reporting API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.models.database import get_db, Contact, Playlist, ContactType, Platform
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/dashboard")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get main dashboard statistics"""
    
    # Total counts
    total_contacts = db.query(Contact).filter(Contact.deleted_at.is_(None)).count()
    verified_contacts = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.verified == True)
    ).count()
    high_priority = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.priority_score >= 80)
    ).count()
    
    # Recent additions (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_contacts = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.created_at >= week_ago)
    ).count()
    
    # Platform breakdown
    platform_stats = db.query(
        Contact.source_platform,
        func.count(Contact.id).label('count')
    ).filter(Contact.deleted_at.is_(None)).group_by(Contact.source_platform).all()
    
    platform_breakdown = {
        platform[0].value if platform[0] else "unknown": platform[1]
        for platform in platform_stats
    }
    
    # Contact type breakdown
    type_stats = db.query(
        Contact.contact_type,
        func.count(Contact.id).label('count')
    ).filter(Contact.deleted_at.is_(None)).group_by(Contact.contact_type).all()
    
    type_breakdown = {
        contact_type[0].value if contact_type[0] else "unknown": contact_type[1]
        for contact_type in type_stats
    }
    
    # Score distribution
    score_ranges = [
        ("90-100", db.query(Contact).filter(and_(Contact.deleted_at.is_(None), Contact.priority_score >= 90)).count()),
        ("80-89", db.query(Contact).filter(and_(Contact.deleted_at.is_(None), Contact.priority_score >= 80, Contact.priority_score < 90)).count()),
        ("70-79", db.query(Contact).filter(and_(Contact.deleted_at.is_(None), Contact.priority_score >= 70, Contact.priority_score < 80)).count()),
        ("60-69", db.query(Contact).filter(and_(Contact.deleted_at.is_(None), Contact.priority_score >= 60, Contact.priority_score < 70)).count()),
        ("0-59", db.query(Contact).filter(and_(Contact.deleted_at.is_(None), Contact.priority_score < 60)).count())
    ]
    
    return {
        "totals": {
            "total_contacts": total_contacts,
            "verified_contacts": verified_contacts,
            "high_priority_contacts": high_priority,
            "recent_additions": recent_contacts,
            "verification_rate": (verified_contacts / total_contacts * 100) if total_contacts > 0 else 0
        },
        "breakdowns": {
            "by_platform": platform_breakdown,
            "by_type": type_breakdown,
            "by_score_range": dict(score_ranges)
        },
        "growth": {
            "contacts_this_week": recent_contacts,
            "growth_rate": _calculate_growth_rate(db)
        }
    }

@router.get("/contacts/trends")
async def get_contact_trends(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get contact growth trends over time"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily contact additions
    daily_stats = db.query(
        func.date(Contact.created_at).label('date'),
        func.count(Contact.id).label('count')
    ).filter(
        and_(
            Contact.deleted_at.is_(None),
            Contact.created_at >= start_date
        )
    ).group_by(func.date(Contact.created_at)).order_by('date').all()
    
    # Platform trends
    platform_trends = db.query(
        func.date(Contact.created_at).label('date'),
        Contact.source_platform,
        func.count(Contact.id).label('count')
    ).filter(
        and_(
            Contact.deleted_at.is_(None),
            Contact.created_at >= start_date
        )
    ).group_by(func.date(Contact.created_at), Contact.source_platform).all()
    
    # Format platform trends
    platform_data = {}
    for date, platform, count in platform_trends:
        platform_name = platform.value if platform else "unknown"
        if platform_name not in platform_data:
            platform_data[platform_name] = []
        platform_data[platform_name].append({
            "date": date.isoformat(),
            "count": count
        })
    
    return {
        "daily_additions": [
            {"date": stat[0].isoformat(), "count": stat[1]}
            for stat in daily_stats
        ],
        "platform_trends": platform_data,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "days": days
        }
    }

@router.get("/quality")
async def get_quality_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get data quality metrics"""
    
    total_contacts = db.query(Contact).filter(Contact.deleted_at.is_(None)).count()
    
    # Completeness metrics
    with_email = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.email.isnot(None))
    ).count()
    
    with_name = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.full_name.isnot(None))
    ).count()
    
    with_company = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.company.isnot(None))
    ).count()
    
    with_social = db.query(Contact).filter(
        and_(
            Contact.deleted_at.is_(None),
            or_(
                Contact.instagram_handle.isnot(None),
                Contact.twitter_handle.isnot(None)
            )
        )
    ).count()
    
    # Score distribution
    avg_score = db.query(func.avg(Contact.priority_score)).filter(
        Contact.deleted_at.is_(None)
    ).scalar() or 0
    
    high_quality = db.query(Contact).filter(
        and_(Contact.deleted_at.is_(None), Contact.priority_score >= 80)
    ).count()
    
    return {
        "completeness": {
            "total_contacts": total_contacts,
            "email_completeness": (with_email / total_contacts * 100) if total_contacts > 0 else 0,
            "name_completeness": (with_name / total_contacts * 100) if total_contacts > 0 else 0,
            "company_completeness": (with_company / total_contacts * 100) if total_contacts > 0 else 0,
            "social_completeness": (with_social / total_contacts * 100) if total_contacts > 0 else 0
        },
        "quality_scores": {
            "average_score": round(avg_score, 2),
            "high_quality_contacts": high_quality,
            "high_quality_percentage": (high_quality / total_contacts * 100) if total_contacts > 0 else 0
        },
        "verification": {
            "verified_contacts": db.query(Contact).filter(
                and_(Contact.deleted_at.is_(None), Contact.verified == True)
            ).count(),
            "verification_rate": (db.query(Contact).filter(
                and_(Contact.deleted_at.is_(None), Contact.verified == True)
            ).count() / total_contacts * 100) if total_contacts > 0 else 0
        }
    }

@router.get("/top-performers")
async def get_top_performers(
    limit: int = Query(20, ge=5, le=100),
    metric: str = Query("priority_score", regex="^(priority_score|follower_count)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get top performing contacts"""
    
    order_column = getattr(Contact, metric)
    
    top_contacts = db.query(Contact).filter(
        Contact.deleted_at.is_(None)
    ).order_by(order_column.desc()).limit(limit).all()
    
    results = []
    for contact in top_contacts:
        results.append({
            "id": contact.id,
            "full_name": contact.full_name,
            "email": contact.email,
            "contact_type": contact.contact_type.value if contact.contact_type else None,
            "priority_score": contact.priority_score,
            "follower_count": contact.follower_count,
            "company": contact.company,
            "source_platform": contact.source_platform.value if contact.source_platform else None,
            "verified": contact.verified
        })
    
    return {
        "metric": metric,
        "limit": limit,
        "top_performers": results
    }

@router.get("/export-stats")
async def get_export_statistics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get export and usage statistics"""
    
    # Mock export statistics (in real implementation, track from audit logs)
    return {
        "recent_exports": [
            {
                "date": "2024-11-09",
                "format": "csv",
                "records": 150,
                "user": "user@example.com"
            },
            {
                "date": "2024-11-08",
                "format": "excel",
                "records": 75,
                "user": "user@example.com"
            }
        ],
        "export_summary": {
            "total_exports": 25,
            "total_records_exported": 3750,
            "most_popular_format": "csv",
            "average_export_size": 150
        },
        "api_usage": {
            "total_api_calls": 1250,
            "calls_this_week": 180,
            "most_used_endpoint": "/search/contacts",
            "average_response_time": "245ms"
        }
    }

def _calculate_growth_rate(db: Session) -> float:
    """Calculate week-over-week growth rate"""
    
    now = datetime.utcnow()
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)
    
    this_week_count = db.query(Contact).filter(
        and_(
            Contact.deleted_at.is_(None),
            Contact.created_at >= this_week_start
        )
    ).count()
    
    last_week_count = db.query(Contact).filter(
        and_(
            Contact.deleted_at.is_(None),
            Contact.created_at >= last_week_start,
            Contact.created_at < this_week_start
        )
    ).count()
    
    if last_week_count == 0:
        return 100.0 if this_week_count > 0 else 0.0
    
    return ((this_week_count - last_week_count) / last_week_count) * 100
