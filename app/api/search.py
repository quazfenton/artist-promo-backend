"""Advanced search and filtering API"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
from typing import List, Optional, Dict, Any
from app.models.database import get_db, Contact, Playlist, ContactType, Platform
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = {}
    sort_by: str = "priority_score"
    sort_order: str = "desc"
    limit: int = 100
    offset: int = 0

class SearchResponse(BaseModel):
    total: int
    results: List[Dict]
    facets: Dict[str, List[Dict]]

@router.post("/contacts", response_model=SearchResponse)
async def search_contacts(
    search_request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Advanced contact search with filters and facets"""
    
    query = db.query(Contact).filter(Contact.deleted_at.is_(None))
    
    # Text search
    if search_request.query:
        search_term = f"%{search_request.query}%"
        query = query.filter(
            or_(
                Contact.full_name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.company.ilike(search_term),
                Contact.bio.ilike(search_term)
            )
        )
    
    # Apply filters
    filters = search_request.filters
    if filters.get("contact_type"):
        query = query.filter(Contact.contact_type == filters["contact_type"])
    
    if filters.get("min_score"):
        query = query.filter(Contact.priority_score >= filters["min_score"])
    
    if filters.get("max_score"):
        query = query.filter(Contact.priority_score <= filters["max_score"])
    
    if filters.get("min_followers"):
        query = query.filter(Contact.follower_count >= filters["min_followers"])
    
    if filters.get("verified_only"):
        query = query.filter(Contact.verified == True)
    
    if filters.get("platform"):
        query = query.filter(Contact.source_platform == filters["platform"])
    
    if filters.get("genres"):
        genre_list = filters["genres"] if isinstance(filters["genres"], list) else [filters["genres"]]
        for genre in genre_list:
            query = query.filter(Contact.genres.contains([genre]))
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(Contact, search_request.sort_by, Contact.priority_score)
    if search_request.sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    results = query.offset(search_request.offset).limit(search_request.limit).all()
    
    # Generate facets
    facets = _generate_contact_facets(db, search_request.query, filters)
    
    # Convert results to dict
    results_data = [
        {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "contact_type": c.contact_type.value if c.contact_type else None,
            "priority_score": c.priority_score,
            "follower_count": c.follower_count,
            "company": c.company,
            "verified": c.verified,
            "source_platform": c.source_platform.value if c.source_platform else None
        }
        for c in results
    ]
    
    return SearchResponse(
        total=total,
        results=results_data,
        facets=facets
    )

@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get search suggestions for autocomplete"""
    
    search_term = f"%{q}%"
    
    # Get name suggestions
    name_suggestions = db.query(Contact.full_name).filter(
        and_(
            Contact.full_name.ilike(search_term),
            Contact.deleted_at.is_(None),
            Contact.full_name.isnot(None)
        )
    ).distinct().limit(5).all()
    
    # Get company suggestions
    company_suggestions = db.query(Contact.company).filter(
        and_(
            Contact.company.ilike(search_term),
            Contact.deleted_at.is_(None),
            Contact.company.isnot(None)
        )
    ).distinct().limit(5).all()
    
    return {
        "names": [name[0] for name in name_suggestions],
        "companies": [company[0] for company in company_suggestions]
    }

def _generate_contact_facets(db: Session, query: str, filters: Dict) -> Dict[str, List[Dict]]:
    """Generate facets for search results"""
    
    base_query = db.query(Contact).filter(Contact.deleted_at.is_(None))
    
    # Apply text search to facet queries
    if query:
        search_term = f"%{query}%"
        base_query = base_query.filter(
            or_(
                Contact.full_name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.company.ilike(search_term)
            )
        )
    
    facets = {}
    
    # Contact type facet
    contact_type_facet = db.query(
        Contact.contact_type,
        func.count(Contact.id).label('count')
    ).filter(Contact.deleted_at.is_(None)).group_by(Contact.contact_type).all()
    
    facets["contact_types"] = [
        {"value": ct[0].value if ct[0] else "unknown", "count": ct[1]}
        for ct in contact_type_facet
    ]
    
    # Platform facet
    platform_facet = db.query(
        Contact.source_platform,
        func.count(Contact.id).label('count')
    ).filter(Contact.deleted_at.is_(None)).group_by(Contact.source_platform).all()
    
    facets["platforms"] = [
        {"value": pf[0].value if pf[0] else "unknown", "count": pf[1]}
        for pf in platform_facet
    ]
    
    # Score ranges
    facets["score_ranges"] = [
        {"value": "90-100", "count": base_query.filter(Contact.priority_score >= 90).count()},
        {"value": "80-89", "count": base_query.filter(and_(Contact.priority_score >= 80, Contact.priority_score < 90)).count()},
        {"value": "70-79", "count": base_query.filter(and_(Contact.priority_score >= 70, Contact.priority_score < 80)).count()},
        {"value": "60-69", "count": base_query.filter(and_(Contact.priority_score >= 60, Contact.priority_score < 70)).count()},
        {"value": "0-59", "count": base_query.filter(Contact.priority_score < 60).count()}
    ]
    
    return facets
