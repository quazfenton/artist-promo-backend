"""Celery tasks for background scraping"""
from celery import Celery
from typing import Dict, List
import os
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import asyncio

# Initialize Celery
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("scraper_tasks", broker=redis_url, backend=redis_url)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery_app.task(bind=True, max_retries=3)
def scrape_spotify_task(self, genre: str, min_followers: int = 500, limit: int = 50, user_id: int = None):
    """Background Spotify scraping task"""
    
    try:
        from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
        from app.api.main import save_spotify_results
        
        # Update task status
        self.update_state(state='PROGRESS', meta={'status': 'Starting Spotify scrape'})
        
        scraper = SpotifyPlaylistScraper()
        results = scraper.scrape(genre=genre, min_followers=min_followers, limit=limit)
        
        # Save to database
        db = SessionLocal()
        try:
            save_spotify_results(results, db)
            db.close()
        except Exception as e:
            db.rollback()
            db.close()
            raise
        
        logger.info(f"Spotify scrape completed: {len(results)} results")
        
        return {
            'status': 'completed',
            'results_count': len(results),
            'scraper_stats': scraper.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Spotify scrape failed: {str(e)}")
        self.retry(countdown=60, exc=e)

@celery_app.task(bind=True, max_retries=3)
def scrape_youtube_task(self, query: str, max_results: int = 50, user_id: int = None):
    """Background YouTube scraping task"""
    
    try:
        from app.scrapers.youtube_scraper import YouTubeChannelScraper
        from app.api.main import save_youtube_results
        
        self.update_state(state='PROGRESS', meta={'status': 'Starting YouTube scrape'})
        
        scraper = YouTubeChannelScraper()
        results = scraper.scrape(query=query, max_results=max_results)
        
        # Save to database
        db = SessionLocal()
        try:
            save_youtube_results(results, db)
            db.close()
        except Exception as e:
            db.rollback()
            db.close()
            raise
        
        logger.info(f"YouTube scrape completed: {len(results)} results")
        
        return {
            'status': 'completed',
            'results_count': len(results),
            'scraper_stats': scraper.get_stats()
        }
        
    except Exception as e:
        logger.error(f"YouTube scrape failed: {str(e)}")
        self.retry(countdown=60, exc=e)

@celery_app.task(bind=True, max_retries=3)
def scrape_instagram_task(self, hashtag: str = None, username: str = None, user_id: int = None):
    """Background Instagram scraping task"""
    
    try:
        from app.scrapers.instagram_scraper import InstagramScraper
        from app.api.main import save_instagram_results
        
        self.update_state(state='PROGRESS', meta={'status': 'Starting Instagram scrape'})
        
        scraper = InstagramScraper()
        
        if username:
            results = [scraper.scrape_profile(username)]
        else:
            results = scraper.find_music_curators()
        
        # Save to database
        db = SessionLocal()
        try:
            save_instagram_results(results, db)
            db.close()
        except Exception as e:
            db.rollback()
            db.close()
            raise
        
        logger.info(f"Instagram scrape completed: {len(results)} results")
        
        return {
            'status': 'completed',
            'results_count': len(results),
            'scraper_stats': scraper.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Instagram scrape failed: {str(e)}")
        self.retry(countdown=60, exc=e)

@celery_app.task(bind=True)
def scrape_web_task(self, url: str, user_id: int = None):
    """Background web scraping task"""
    
    try:
        from app.scrapers.web_scraper import WebContactScraper
        from app.api.main import save_web_result
        
        self.update_state(state='PROGRESS', meta={'status': f'Scraping {url}'})
        
        scraper = WebContactScraper()
        result = scraper.scrape(url)
        
        if result:
            # Save to database
            db = SessionLocal()
            try:
                save_web_result(result, db)
                db.close()
            except Exception as e:
                db.rollback()
                db.close()
                raise
        
        logger.info(f"Web scrape completed: {url}")
        
        return {
            'status': 'completed',
            'result': result,
            'scraper_stats': scraper.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Web scrape failed for {url}: {str(e)}")
        raise

@celery_app.task
def bulk_score_update_task(score_updates: List[Dict], user_id: int = None):
    """Background bulk score update task"""
    
    try:
        from app.services.database_service import DatabaseService
        
        db = SessionLocal()
        db_service = DatabaseService(db, user_id)
        
        updated_count = db_service.bulk_update_scores(score_updates)
        db.close()
        
        logger.info(f"Bulk score update completed: {updated_count} contacts updated")
        
        return {
            'status': 'completed',
            'updated_count': updated_count
        }
        
    except Exception as e:
        logger.error(f"Bulk score update failed: {str(e)}")
        raise

@celery_app.task
def scheduled_scrape_task():
    """Scheduled scraping task - runs daily"""
    
    try:
        # Queue multiple scraping tasks
        scrape_spotify_task.delay("hip-hop", min_followers=1000, limit=100)
        scrape_youtube_task.delay("hip hop playlist curator", max_results=50)
        scrape_instagram_task.delay(hashtag="hiphop")
        
        logger.info("Scheduled scraping tasks queued")
        
        return {'status': 'scheduled_tasks_queued'}
        
    except Exception as e:
        logger.error(f"Scheduled scraping failed: {str(e)}")
        raise

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'app.tasks.scraper_tasks.scrape_spotify_task': {'queue': 'scraping'},
        'app.tasks.scraper_tasks.scrape_youtube_task': {'queue': 'scraping'},
        'app.tasks.scraper_tasks.scrape_instagram_task': {'queue': 'scraping'},
        'app.tasks.scraper_tasks.scrape_web_task': {'queue': 'scraping'},
        'app.tasks.scraper_tasks.bulk_score_update_task': {'queue': 'processing'},
    },
    beat_schedule={
        'daily-scrape': {
            'task': 'app.tasks.scraper_tasks.scheduled_scrape_task',
            'schedule': 86400.0,  # 24 hours
        },
    },
)
