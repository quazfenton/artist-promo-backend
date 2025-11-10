"""Advanced scraper API endpoints"""
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.middleware.auth_middleware import get_current_user
from app.tasks.scraper_tasks import celery_app

router = APIRouter(prefix="/advanced-scrapers", tags=["advanced-scrapers"])

class OSSPlatformRequest(BaseModel):
    query: str
    platforms: List[str] = ["twitter", "instagram", "tiktok"]
    max_per_platform: int = 25

class AdvancedMarketingRequest(BaseModel):
    artist_name: str
    genre: str = "hip-hop"
    strategies: List[str] = ["musicbrainz", "linkedin", "youtube", "team_pages", "press_kits"]

class NicheDiscoveryRequest(BaseModel):
    genre: str = "hip-hop"
    city: str = "New York"
    strategies: List[str] = ["reddit", "podcasts", "venues", "radio", "pr_firms"]

@router.post("/oss-platforms")
async def scrape_oss_platforms(
    request: Request,
    scraper_request: OSSPlatformRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Scrape contacts using OSS platform alternatives (Nitter, Proxigram, etc.)"""
    
    # Queue background task
    task = scrape_oss_platforms_task.delay(
        scraper_request.dict(),
        current_user["user_id"]
    )
    
    return {
        "status": "queued",
        "task_id": task.id,
        "message": f"OSS platform scraping queued for query: {scraper_request.query}",
        "platforms": scraper_request.platforms
    }

@router.post("/advanced-marketing")
async def scrape_advanced_marketing(
    request: Request,
    scraper_request: AdvancedMarketingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Advanced marketing contact discovery (MusicBrainz, LinkedIn, etc.)"""
    
    # Queue background task
    task = scrape_advanced_marketing_task.delay(
        scraper_request.dict(),
        current_user["user_id"]
    )
    
    return {
        "status": "queued",
        "task_id": task.id,
        "message": f"Advanced marketing discovery queued for artist: {scraper_request.artist_name}",
        "strategies": scraper_request.strategies
    }

@router.post("/niche-discovery")
async def scrape_niche_discovery(
    request: Request,
    scraper_request: NicheDiscoveryRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Niche contact discovery (Reddit, podcasts, venues, etc.)"""
    
    # Queue background task
    task = scrape_niche_discovery_task.delay(
        scraper_request.dict(),
        current_user["user_id"]
    )
    
    return {
        "status": "queued",
        "task_id": task.id,
        "message": f"Niche discovery queued for {scraper_request.genre} in {scraper_request.city}",
        "strategies": scraper_request.strategies
    }

@router.get("/strategies")
async def get_available_strategies(current_user: dict = Depends(get_current_user)):
    """Get all available advanced scraping strategies"""
    
    strategies = {
        "oss_platforms": {
            "description": "Privacy-focused alternatives to major platforms",
            "platforms": {
                "twitter": "Nitter instances for Twitter/X bio scraping",
                "instagram": "Proxigram instances for Instagram business contacts",
                "tiktok": "ProxiTok instances for TikTok creator contacts"
            }
        },
        "advanced_marketing": {
            "description": "Professional music industry contact discovery",
            "strategies": {
                "musicbrainz": "Manager credits from MusicBrainz/Discogs releases",
                "linkedin": "Targeted LinkedIn search for A&R, managers, publicists",
                "youtube": "YouTube About page business email extraction",
                "team_pages": "Artist official website team page scraping",
                "press_kits": "Press kit PDF contact extraction"
            }
        },
        "niche_discovery": {
            "description": "Specialized and niche contact sources",
            "strategies": {
                "reddit": "Reddit/Discord submission posts and curator contacts",
                "podcasts": "Podcast guest manager/publicist mentions",
                "venues": "Venue booking page manager contact scraping",
                "radio": "Radio station playlist manager contacts",
                "pr_firms": "PR firm client lists and case studies"
            }
        }
    }
    
    return {"available_strategies": strategies}

@router.get("/presets")
async def get_scraping_presets(current_user: dict = Depends(get_current_user)):
    """Get predefined scraping presets for different use cases"""
    
    presets = {
        "hip_hop_comprehensive": {
            "name": "Hip-Hop Comprehensive Discovery",
            "description": "Complete contact discovery for hip-hop artists",
            "oss_platforms": {
                "query": "hip hop curator booking press",
                "platforms": ["twitter", "instagram", "tiktok"]
            },
            "advanced_marketing": {
                "genre": "hip-hop",
                "strategies": ["musicbrainz", "linkedin", "youtube", "team_pages"]
            },
            "niche_discovery": {
                "genre": "hip-hop",
                "strategies": ["reddit", "podcasts", "venues", "radio"]
            }
        },
        "playlist_curator_focus": {
            "name": "Playlist Curator Focused",
            "description": "Target playlist curators specifically",
            "oss_platforms": {
                "query": "playlist curator submissions",
                "platforms": ["twitter", "instagram"]
            },
            "advanced_marketing": {
                "strategies": ["youtube", "team_pages"]
            },
            "niche_discovery": {
                "strategies": ["reddit", "radio"]
            }
        },
        "press_and_media": {
            "name": "Press & Media Contacts",
            "description": "Focus on press, media, and publicity contacts",
            "oss_platforms": {
                "query": "music press publicist media",
                "platforms": ["twitter"]
            },
            "advanced_marketing": {
                "strategies": ["linkedin", "press_kits"]
            },
            "niche_discovery": {
                "strategies": ["podcasts", "pr_firms"]
            }
        },
        "local_market_penetration": {
            "name": "Local Market Penetration",
            "description": "Target local venues, radio, and media",
            "niche_discovery": {
                "strategies": ["venues", "radio", "podcasts"]
            }
        }
    }
    
    return {"presets": presets}

@router.post("/run-preset/{preset_name}")
async def run_scraping_preset(
    preset_name: str,
    request: Request,
    artist_name: Optional[str] = None,
    city: Optional[str] = None,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Run a predefined scraping preset"""
    
    # Get preset configuration
    presets_response = await get_scraping_presets(current_user)
    presets = presets_response["presets"]
    
    if preset_name not in presets:
        return {"error": f"Preset '{preset_name}' not found"}
    
    preset = presets[preset_name]
    task_ids = []
    
    # Launch OSS platform scraping if configured
    if "oss_platforms" in preset:
        oss_config = preset["oss_platforms"]
        task = scrape_oss_platforms_task.delay(oss_config, current_user["user_id"])
        task_ids.append({"type": "oss_platforms", "task_id": task.id})
    
    # Launch advanced marketing if configured
    if "advanced_marketing" in preset:
        marketing_config = preset["advanced_marketing"]
        if artist_name:
            marketing_config["artist_name"] = artist_name
        
        if "artist_name" in marketing_config:
            task = scrape_advanced_marketing_task.delay(marketing_config, current_user["user_id"])
            task_ids.append({"type": "advanced_marketing", "task_id": task.id})
    
    # Launch niche discovery if configured
    if "niche_discovery" in preset:
        niche_config = preset["niche_discovery"]
        if city:
            niche_config["city"] = city
        
        task = scrape_niche_discovery_task.delay(niche_config, current_user["user_id"])
        task_ids.append({"type": "niche_discovery", "task_id": task.id})
    
    return {
        "status": "queued",
        "preset_name": preset_name,
        "preset_description": preset["description"],
        "tasks": task_ids,
        "message": f"Preset '{preset_name}' launched with {len(task_ids)} scraping tasks"
    }

# Celery tasks for background processing
@celery_app.task(bind=True, max_retries=3)
def scrape_oss_platforms_task(self, request_data: Dict, user_id: int):
    """Background task for OSS platform scraping"""
    
    try:
        from app.scrapers.oss_alternatives import LibreRedirectScraper
        
        self.update_state(state='PROGRESS', meta={'status': 'Starting OSS platform scraping'})
        
        scraper = LibreRedirectScraper()
        results = scraper.scrape_all_platforms(
            request_data["query"],
            request_data.get("max_per_platform", 25)
        )
        
        # Save results to database
        # (Implementation would save to contacts table)
        
        total_contacts = sum(len(platform_results) for platform_results in results.values())
        
        return {
            'status': 'completed',
            'results': results,
            'total_contacts': total_contacts,
            'platforms_scraped': list(results.keys())
        }
        
    except Exception as e:
        self.retry(countdown=60, exc=e)

@celery_app.task(bind=True, max_retries=3)
def scrape_advanced_marketing_task(self, request_data: Dict, user_id: int):
    """Background task for advanced marketing discovery"""
    
    try:
        from app.scrapers.advanced_marketing import AdvancedMarketingScraper
        
        self.update_state(state='PROGRESS', meta={'status': 'Starting advanced marketing discovery'})
        
        scraper = AdvancedMarketingScraper()
        results = scraper.comprehensive_contact_discovery(
            request_data["artist_name"],
            request_data.get("genre", "hip-hop")
        )
        
        # Save results to database
        # (Implementation would save to contacts table)
        
        total_contacts = sum(len(strategy_results) for strategy_results in results.values())
        
        return {
            'status': 'completed',
            'results': results,
            'total_contacts': total_contacts,
            'artist_name': request_data["artist_name"],
            'strategies_used': list(results.keys())
        }
        
    except Exception as e:
        self.retry(countdown=60, exc=e)

@celery_app.task(bind=True, max_retries=3)
def scrape_niche_discovery_task(self, request_data: Dict, user_id: int):
    """Background task for niche discovery"""
    
    try:
        from app.scrapers.niche_discovery import NicheDiscoveryScraper
        
        self.update_state(state='PROGRESS', meta={'status': 'Starting niche discovery'})
        
        scraper = NicheDiscoveryScraper()
        results = scraper.comprehensive_niche_discovery(
            request_data.get("genre", "hip-hop"),
            request_data.get("city", "New York")
        )
        
        # Save results to database
        # (Implementation would save to contacts table)
        
        total_contacts = sum(len(strategy_results) for strategy_results in results.values())
        
        return {
            'status': 'completed',
            'results': results,
            'total_contacts': total_contacts,
            'genre': request_data.get("genre", "hip-hop"),
            'city': request_data.get("city", "New York"),
            'strategies_used': list(results.keys())
        }
        
    except Exception as e:
        self.retry(countdown=60, exc=e)
