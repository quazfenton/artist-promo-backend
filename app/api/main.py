"""
FastAPI application with n8n webhook integration
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
from datetime import datetime
import csv
import io
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Import our modules
from app.models.database import Base, Contact, Playlist, Venue, ContactType, Platform
from app.auth.models import User
from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
from app.scrapers.youtube_scraper import YouTubeChannelScraper
from app.scrapers.instagram_scraper import InstagramScraper
from app.scrapers.web_scraper import WebContactScraper
from app.utils.scoring import ContactScorer, VenueScorer, PlaylistScorer
from app.utils.email_validator import EmailValidator
from app.utils.database import get_active_records, create_indexes_if_not_exist
from app.services.database_service import DatabaseService
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.auth_middleware import get_current_user, verify_api_key, AuthMiddleware
from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.utils.error_handler import setup_error_handling_and_shutdown
from app.utils.config_validator import validate_startup_config
from app.utils.pipeline_orchestrator import get_pipeline_processor
from app.utils.search_and_ingestion import get_webhook_ingestor, get_search_index
from app.utils.confidence_calibration import get_confidence_decay_manager, get_source_trust_calibrator

# Initialize FastAPI app
app = FastAPI(
    title="Artist Promotion API",
    description="Serverless backend for hip-hop artist promotion",
    version="1.0.0"
)

# Setup error handling and graceful shutdown
setup_error_handling_and_shutdown(app)

# Validate configuration at startup
validate_startup_config()

# Add monitoring middleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.performance import PerformanceMiddleware
from app.monitoring.logging import LoggingMiddleware
from app.monitoring.metrics import MetricsMiddleware, metrics_endpoint
from app.monitoring.health_checks import router as health_router
from app.middleware.auth_middleware import AuthMiddleware

app.add_middleware(AuthMiddleware)  # Add auth middleware first
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PerformanceMiddleware, slow_request_threshold=1.0)
app.add_middleware(LoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(health_router)  # Add health check router

# Import and include all API routers
from app.api.contacts import router as contacts_router
from app.api.tasks import router as tasks_router
from app.api.search import router as search_router
from app.api.export import router as export_router
from app.api.campaigns import router as campaigns_router
from app.api.analytics import router as analytics_router
from app.api.webhooks import router as webhooks_router
from app.api.advanced_scrapers import router as advanced_scrapers_router
from app.api.intelligence import router as intelligence_router

app.include_router(contacts_router)
app.include_router(tasks_router)
app.include_router(search_router)
app.include_router(export_router)
app.include_router(campaigns_router)
app.include_router(analytics_router)
app.include_router(webhooks_router)
app.include_router(advanced_scrapers_router)
app.include_router(intelligence_router)
app.include_router(jobs_router)

# Add webhook ingestion endpoint
@app.post("/ingest")
async def ingest_webhook(payload: Dict[str, Any], request: Request):
    """Webhook endpoint for external signal ingestion"""
    try:
        from app.utils.search_and_ingestion import get_webhook_ingestor
        ingestor = get_webhook_ingestor()

        # Get source from headers or default to webhook
        source = request.headers.get("X-Source", "webhook")

        result = ingestor.ingest_payload(payload, source)
        return result

    except Exception as e:
        logger.error(f"Webhook ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")

# Add search endpoint
@app.post("/search/indexed")
async def search_indexed_contacts(query: str, current_user: dict = Depends(get_current_user)):
    """Search contacts in the local index"""
    try:
        from app.utils.search_and_ingestion import get_search_index
        search_idx = get_search_index()

        # Use the search methods available in the SearchIndex class
        results = {
            "emails": list(search_idx.search_email(query)),
            "names": list(search_idx.search_name(query)),
            "domains": list(search_idx.search_domain(query)),
            "artists": list(search_idx.search_artist(query)),
            "managers": list(search_idx.search_manager(query))
        }

        return {
            "query": query,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# Add metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return await metrics_endpoint()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Create performance indexes
create_indexes_if_not_exist(engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== REQUEST/RESPONSE MODELS ====================

class ScraperRequest(BaseModel):
    scraper_type: str = Field(..., description="Type of scraper: spotify, youtube, instagram, web")
    query: Optional[str] = Field(None, description="Search query")
    url: Optional[str] = Field(None, description="URL to scrape")
    min_followers: int = Field(500, description="Minimum follower count")
    max_results: int = Field(50, description="Maximum results to return")
    genre: str = Field("hip-hop", description="Genre filter")

class ContactResponse(BaseModel):
    id: int
    full_name: Optional[str]
    email: Optional[EmailStr]
    contact_type: str
    priority_score: float
    follower_count: int
    verified: bool

class ExportRequest(BaseModel):
    contact_type: Optional[str] = None
    min_score: float = 0.0
    limit: int = 1000


# ==================== SCRAPER ENDPOINTS ====================

@app.post("/scrape/spotify")
async def scrape_spotify(
    request: ScraperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Scrape Spotify playlists and curators (async via queue)
    """
    try:
        # Enqueue the scraping job
        from app.workers.queue_adapter import enqueue_job

        job_id = enqueue_job(
            job_type="scrape:spotify_playlist",
            params={
                "genre": request.genre,
                "min_followers": request.min_followers,
                "limit": request.max_results
            },
            source="api",
            priority=5,
            user_id=current_user.get("user_id")
        )

        return {
            "status": "queued",
            "scraper": "spotify",
            "job_id": job_id,
            "estimated_completion": "5-15 minutes",
            "message": "Scraping job queued successfully"
        }

    except Exception as e:
        logger.error(f"Spotify scrape queue error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue scraping job: {str(e)}")


@app.post("/scrape/youtube")
async def scrape_youtube(
    request: ScraperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Scrape YouTube channels for contact info (async via queue)
    """
    try:
        # Enqueue the scraping job
        from app.workers.queue_adapter import enqueue_job

        job_id = enqueue_job(
            job_type="scrape:youtube_channel",
            params={
                "query": request.query or "hip hop playlist",
                "max_results": request.max_results
            },
            source="api",
            priority=5,
            user_id=current_user.get("user_id")
        )

        return {
            "status": "queued",
            "scraper": "youtube",
            "job_id": job_id,
            "estimated_completion": "5-15 minutes",
            "message": "Scraping job queued successfully"
        }

    except Exception as e:
        logger.error(f"YouTube scrape queue error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue scraping job: {str(e)}")


@app.post("/scrape/instagram")
async def scrape_instagram(
    request: ScraperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Scrape Instagram profiles for contact info (async via queue)
    """
    try:
        # Enqueue the scraping job
        from app.workers.queue_adapter import enqueue_job

        # Extract username from URL if provided
        username = None
        if request.url:
            username = request.url.split('/')[-2] if '/' in request.url else request.url

        job_id = enqueue_job(
            job_type="scrape:instagram_profile",
            params={
                "username": username,
                "hashtag": request.query  # Using query field for hashtag
            },
            source="api",
            priority=5,
            user_id=current_user.get("user_id")
        )

        return {
            "status": "queued",
            "scraper": "instagram",
            "job_id": job_id,
            "estimated_completion": "5-15 minutes",
            "message": "Scraping job queued successfully"
        }

    except Exception as e:
        logger.error(f"Instagram scrape queue error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue scraping job: {str(e)}")


@app.post("/scrape/web")
async def scrape_web(
    request: ScraperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Scrape a website for contact info (async via queue)
    """
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required for web scraping")

    try:
        # Enqueue the scraping job
        from app.workers.queue_adapter import enqueue_job

        job_id = enqueue_job(
            job_type="scrape:web_contact",
            params={
                "url": request.url
            },
            source="api",
            priority=5,
            user_id=current_user.get("user_id")
        )

        return {
            "status": "queued",
            "scraper": "web",
            "job_id": job_id,
            "estimated_completion": "5-15 minutes",
            "message": "Scraping job queued successfully"
        }

    except Exception as e:
        logger.error(f"Web scrape queue error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue scraping job: {str(e)}")


# ==================== CONTACT ENDPOINTS ====================

@app.get("/contacts", response_model=List[ContactResponse])
async def get_contacts(
    request: Request,
    contact_type: Optional[str] = None,
    min_score: float = 0.0,
    verified_only: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get contacts from database with filters
    """
    # Use enhanced database service
    db_service = DatabaseService(db, current_user["user_id"], request)
    
    filters = {}
    if contact_type:
        filters["contact_type"] = contact_type
    if verified_only:
        filters["verified"] = True
    
    contacts = db_service.get_active_contacts(**filters)
    
    # Apply score filter and limit
    filtered_contacts = [
        c for c in contacts 
        if c.priority_score >= min_score
    ][:limit]
    
    return filtered_contacts


@app.post("/contacts/verify")
async def verify_contact_email(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Verify an email address
    """
    validator = EmailValidator()
    
    # Basic validation
    result = validator.advanced_validate(email)
    
    # Try enrichment
    enrichment = validator.enrich_with_hunter(email)
    
    # Update database if contact exists
    contact = db.query(Contact).filter(Contact.email == email).first()
    if contact:
        contact.email_verified = result["valid"]
        contact.last_verified_at = datetime.utcnow()
        db.commit()
    
    return {
        "email": email,
        "validation": result,
        "enrichment": enrichment
    }


@app.post("/contacts/score")
async def score_contacts(db: Session = Depends(get_db)):
    """
    Recalculate priority scores for all contacts
    """
    scorer = ContactScorer()
    
    contacts = db.query(Contact).all()
    updated_count = 0
    
    for contact in contacts:
        score = scorer.calculate_priority_score(
            follower_count=contact.follower_count,
            last_active=contact.last_active_at,
            engagement_rate=contact.engagement_rate,
            llm_quality_score=contact.llm_quality_score,
            contact_type=contact.contact_type.value if contact.contact_type else "playlist_curator"
        )
        
        contact.priority_score = score
        updated_count += 1
    
    db.commit()
    
    return {
        "status": "success",
        "updated_count": updated_count
    }


# ==================== EXPORT ENDPOINTS ====================

@app.post("/export/csv")
async def export_contacts_csv(
    request: ExportRequest,
    db: Session = Depends(get_db)
):
    """
    Export contacts to CSV
    """
    query = db.query(Contact)
    
    if request.contact_type:
        query = query.filter(Contact.contact_type == request.contact_type)
    
    query = query.filter(Contact.priority_score >= request.min_score)
    query = query.order_by(Contact.priority_score.desc())
    query = query.limit(request.limit)
    
    contacts = query.all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'ID', 'Name', 'Email', 'Type', 'Priority Score', 'Followers',
        'Instagram', 'Twitter', 'Company', 'Genres', 'Verified', 'Source URL'
    ])
    
    # Data
    for contact in contacts:
        writer.writerow([
            contact.id,
            contact.full_name,
            contact.email,
            contact.contact_type.value if contact.contact_type else '',
            round(contact.priority_score, 2),
            contact.follower_count,
            contact.instagram_handle,
            contact.twitter_handle,
            contact.company,
            ','.join(contact.genres) if contact.genres else '',
            'Yes' if contact.verified else 'No',
            contact.source_url
        ])
    
    # Prepare response
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=contacts_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        }
    )


# ==================== N8N WEBHOOK ENDPOINTS ====================

@app.post("/webhook/n8n/scrape")
async def n8n_scrape_webhook(
    payload: Dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key_valid: bool = Depends(verify_api_key)
):
    """
    n8n webhook endpoint for triggering scrapes
    
    Payload format:
    {
        "action": "scrape_spotify" | "scrape_youtube" | etc.,
        "params": {
            "query": "...",
            "genre": "...",
            ...
        }
    }
    """
    action = payload.get("action")
    params = payload.get("params", {})
    
    if action == "scrape_spotify":
        scraper = SpotifyPlaylistScraper()
        results = scraper.scrape(**params)
        background_tasks.add_task(save_spotify_results, results, db)
    
    elif action == "scrape_youtube":
        scraper = YouTubeChannelScraper()
        results = scraper.scrape(**params)
        background_tasks.add_task(save_youtube_results, results, db)
    
    elif action == "scrape_instagram":
        scraper = InstagramScraper()
        results = scraper.find_music_curators()
        background_tasks.add_task(save_instagram_results, results, db)
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    return {
        "status": "success",
        "action": action,
        "results_count": len(results) if 'results' in locals() else 0
    }


@app.post("/webhook/n8n/export")
async def n8n_export_webhook(
    payload: Dict,
    db: Session = Depends(get_db),
    api_key_valid: bool = Depends(verify_api_key)
):
    """
    n8n webhook for exporting contacts
    Returns JSON data for n8n to process
    """
    contact_type = payload.get("contact_type")
    min_score = payload.get("min_score", 0.0)
    limit = payload.get("limit", 1000)
    
    query = db.query(Contact)
    
    if contact_type:
        query = query.filter(Contact.contact_type == contact_type)
    
    query = query.filter(Contact.priority_score >= min_score)
    query = query.order_by(Contact.priority_score.desc())
    query = query.limit(limit)
    
    contacts = query.all()
    
    # Convert to dict
    contacts_data = [
        {
            "id": c.id,
            "name": c.full_name,
            "email": c.email,
            "type": c.contact_type.value if c.contact_type else None,
            "score": c.priority_score,
            "followers": c.follower_count,
            "instagram": c.instagram_handle,
            "twitter": c.twitter_handle,
            "verified": c.verified
        }
        for c in contacts
    ]
    
    return {
        "status": "success",
        "count": len(contacts_data),
        "contacts": contacts_data
    }


# ==================== BACKGROUND TASKS ====================

def save_spotify_results(results: List[Dict], db: Session):
    """Save Spotify scraper results to database"""
    scorer = PlaylistScorer()
    successful_saves = 0
    failed_saves = 0

    for result in results:
        try:
            # Check if playlist already exists
            existing = db.query(Playlist).filter(
                Playlist.platform_id == result.get('platform_id')
            ).first()

            if existing:
                continue

            # Create playlist record
            playlist = Playlist(
                platform_id=result.get('platform_id'),
                platform=Platform.SPOTIFY,
                name=result.get('name'),
                description=result.get('description'),
                follower_count=result.get('follower_count', 0),
                track_count=result.get('track_count', 0),
                owner_username=result.get('owner_username'),
                owner_url=result.get('owner_url'),
                playlist_url=result.get('playlist_url'),
                relevance_score=scorer.calculate_relevance_score(
                    follower_count=result.get('follower_count', 0),
                    last_updated=None,
                    is_editorial=False,
                    genres=None
                )
            )

            db.add(playlist)

            # Create or update curator contact
            curator_profile = result.get('curator_profile')
            if curator_profile:
                contact = db.query(Contact).filter(
                    Contact.username == curator_profile.get('username')
                ).first()

                if not contact:
                    contact = Contact(
                        username=curator_profile.get('username'),
                        full_name=curator_profile.get('display_name'),
                        contact_type=ContactType.PLAYLIST_CURATOR,
                        source_platform=Platform.SPOTIFY,
                        source_url=curator_profile.get('profile_url'),
                        follower_count=curator_profile.get('follower_count', 0)
                    )

                    db.add(contact)

            db.flush()  # Get IDs without committing the full transaction
            successful_saves += 1
            logger.info(f"Saved playlist: {result.get('name')}")

        except Exception as e:
            logger.error(f"Error saving Spotify result: {str(e)}")
            failed_saves += 1
            # Don't rollback the entire transaction, just skip this item
            db.rollback()  # Rollback just this item's changes

    # Commit all changes at the end
    try:
        db.commit()
        logger.info(f"Successfully saved {successful_saves} playlists, {failed_saves} failed")
    except Exception as e:
        logger.error(f"Error committing transaction: {str(e)}")
        db.rollback()


def save_youtube_results(results: List[Dict], db: Session):
    """Save YouTube scraper results"""
    scorer = ContactScorer()
    successful_saves = 0
    failed_saves = 0

    for result in results:
        try:
            # Check if contact exists
            existing = db.query(Contact).filter(
                Contact.source_url == result.get('channel_url')
            ).first()

            if existing:
                continue

            # Get primary email
            emails = result.get('emails', [])
            primary_email = emails[0] if emails else None

            contact = Contact(
                full_name=result.get('channel_name'),
                username=result.get('channel_id'),
                contact_type=ContactType.PLAYLIST_CURATOR,
                email=primary_email,
                bio=result.get('description'),
                source_platform=Platform.YOUTUBE,
                source_url=result.get('channel_url'),
                follower_count=result.get('subscriber_count', 0),
                priority_score=scorer.calculate_priority_score(
                    follower_count=result.get('subscriber_count', 0),
                    contact_type="playlist_curator"
                )
            )

            db.add(contact)
            db.flush()  # Get ID without committing full transaction
            successful_saves += 1
            logger.info(f"Saved YouTube contact: {result.get('channel_name')}")

        except Exception as e:
            logger.error(f"Error saving YouTube result: {str(e)}")
            failed_saves += 1
            db.rollback()  # Rollback just this item's changes

    # Commit all changes at the end
    try:
        db.commit()
        logger.info(f"Successfully saved {successful_saves} YouTube contacts, {failed_saves} failed")
    except Exception as e:
        logger.error(f"Error committing transaction: {str(e)}")
        db.rollback()


def save_instagram_results(results: List[Dict], db: Session):
    """Save Instagram scraper results"""
    scorer = ContactScorer()
    successful_saves = 0
    failed_saves = 0

    for result in results:
        try:
            # Check if contact exists
            existing = db.query(Contact).filter(
                Contact.instagram_handle == result.get('username')
            ).first()

            if existing:
                continue

            emails = result.get('emails', [])
            primary_email = emails[0] if emails else result.get('business_email')

            contact = Contact(
                full_name=result.get('full_name'),
                username=result.get('username'),
                instagram_handle=result.get('username'),
                contact_type=ContactType.INFLUENCER,
                email=primary_email,
                bio=result.get('bio'),
                source_platform=Platform.INSTAGRAM,
                source_url=result.get('profile_url'),
                follower_count=result.get('follower_count', 0),
                verified=result.get('is_verified', False),
                priority_score=scorer.calculate_priority_score(
                    follower_count=result.get('follower_count', 0),
                    contact_type="influencer"
                )
            )

            db.add(contact)
            db.flush()  # Get ID without committing full transaction
            successful_saves += 1
            logger.info(f"Saved Instagram contact: @{result.get('username')}")

        except Exception as e:
            logger.error(f"Error saving Instagram result: {str(e)}")
            failed_saves += 1
            db.rollback()  # Rollback just this item's changes

    # Commit all changes at the end
    try:
        db.commit()
        logger.info(f"Successfully saved {successful_saves} Instagram contacts, {failed_saves} failed")
    except Exception as e:
        logger.error(f"Error committing transaction: {str(e)}")
        db.rollback()


def save_web_result(result: Dict, db: Session):
    """Save web scraper results"""
    try:
        emails = result.get('emails', [])
        successful_saves = 0
        failed_saves = 0

        for email in emails:
            try:
                existing = db.query(Contact).filter(Contact.email == email).first()
                if not existing:
                    contact = Contact(
                        email=email,
                        website=result.get('url'),
                        source_url=result.get('url'),
                        contact_type=ContactType.PUBLICIST,  # Default, can be refined
                    )
                    db.add(contact)
                    successful_saves += 1
            except Exception as email_error:
                logger.error(f"Error saving email {email}: {str(email_error)}")
                failed_saves += 1
                # Continue with other emails even if one fails

        db.flush()  # Flush all additions
        db.commit()
        logger.info(f"Successfully saved {successful_saves} web contacts, {failed_saves} failed")
    except Exception as e:
        logger.error(f"Error saving web result: {str(e)}")
        db.rollback()


# ==================== HEALTH CHECK ====================

@app.get("/")
async def root():
    return {
        "app": "Artist Promotion API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
