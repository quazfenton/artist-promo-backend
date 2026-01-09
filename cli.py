#!/usr/bin/env python3
"""
CLI tool for running scrapers and exporting data
"""
import click
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.models.database import Base
from app.scrapers.spotify_scraper import SpotifyPlaylistScraper
from app.scrapers.youtube_scraper import YouTubeChannelScraper
from app.scrapers.instagram_scraper import InstagramScraper
from app.scrapers.web_scraper import WebContactScraper
from app.utils.scoring import ContactScorer
from app.api.main import save_spotify_results, save_youtube_results, save_instagram_results

# Setup database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


@click.group()
def cli():
    """Artist Promotion CLI Tool"""
    pass


@cli.command()
@click.option('--genre', default='hip-hop', help='Genre to search for')
@click.option('--min-followers', default=500, help='Minimum follower count')
@click.option('--limit', default=50, help='Max results')
def scrape_spotify(genre, min_followers, limit):
    """Scrape Spotify playlists for curators"""
    logger.info(f"Starting Spotify scrape: genre={genre}, min_followers={min_followers}")
    
    try:
        scraper = SpotifyPlaylistScraper()
        results = scraper.scrape(genre=genre, min_followers=min_followers, limit=limit)
        
        logger.info(f"Found {len(results)} playlists")
        
        # Save to database
        db = SessionLocal()
        save_spotify_results(results, db)
        db.close()
        
        logger.success(f"Saved {len(results)} playlists to database")
    
    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")


@cli.command()
@click.option('--query', default='hip hop playlist', help='Search query')
@click.option('--limit', default=50, help='Max results')
def scrape_youtube(query, limit):
    """Scrape YouTube channels for contact info"""
    logger.info(f"Starting YouTube scrape: query={query}")
    
    try:
        scraper = YouTubeChannelScraper()
        results = scraper.scrape(query=query, max_results=limit)
        
        logger.info(f"Found {len(results)} channels")
        
        # Save to database
        db = SessionLocal()
        save_youtube_results(results, db)
        db.close()
        
        logger.success(f"Saved {len(results)} channels to database")
    
    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")


@cli.command()
@click.option('--hashtag', default='hiphop', help='Hashtag to scrape')
@click.option('--limit', default=100, help='Max posts to process')
def scrape_instagram(hashtag, limit):
    """Scrape Instagram profiles from hashtag"""
    logger.info(f"Starting Instagram scrape: #{hashtag}")
    
    try:
        scraper = InstagramScraper()
        results = scraper.scrape(hashtag=hashtag, max_posts=limit)
        
        logger.info(f"Found {len(results)} profiles")
        
        # Save to database
        db = SessionLocal()
        save_instagram_results(results, db)
        db.close()
        
        logger.success(f"Saved {len(results)} profiles to database")
    
    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")


@cli.command()
@click.argument('url')
def scrape_web(url):
    """Scrape a website for contact info"""
    logger.info(f"Scraping: {url}")
    
    try:
        scraper = WebContactScraper()
        result = scraper.scrape(url)
        
        if result:
            logger.info(f"Found {len(result.get('emails', []))} emails")
            logger.info(f"Emails: {', '.join(result.get('emails', []))}")
        else:
            logger.warning("No results found")
    
    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")


@cli.command()
def score_all():
    """Recalculate priority scores for all contacts"""
    logger.info("Recalculating scores...")
    
    try:
        from app.models.database import Contact
        
        db = SessionLocal()
        scorer = ContactScorer()
        
        contacts = db.query(Contact).all()
        
        for contact in contacts:
            score = scorer.calculate_priority_score(
                follower_count=contact.follower_count,
                last_active=contact.last_active_at,
                engagement_rate=contact.engagement_rate,
                llm_quality_score=contact.llm_quality_score,
                contact_type=contact.contact_type.value if contact.contact_type else "playlist_curator"
            )
            contact.priority_score = score
        
        db.commit()
        db.close()
        
        logger.success(f"Updated scores for {len(contacts)} contacts")
    
    except Exception as e:
        logger.error(f"Scoring failed: {str(e)}")


@cli.command()
@click.option('--type', 'contact_type', help='Filter by contact type')
@click.option('--min-score', default=0.0, help='Minimum score')
@click.option('--output', default='exports/contacts.csv', help='Output file')
def export_csv(contact_type, min_score, output):
    """Export contacts to CSV"""
    logger.info(f"Exporting contacts: type={contact_type}, min_score={min_score}")
    
    try:
        from app.models.database import Contact
        import csv
        
        db = SessionLocal()
        query = db.query(Contact)
        
        if contact_type:
            query = query.filter(Contact.contact_type == contact_type)
        
        query = query.filter(Contact.priority_score >= min_score)
        query = query.order_by(Contact.priority_score.desc())
        
        contacts = query.all()
        
        # Write CSV
        with open(output, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            writer.writerow([
                'ID', 'Name', 'Email', 'Type', 'Priority Score', 'Followers',
                'Instagram', 'Twitter', 'Company', 'Genres', 'Verified', 'Source URL'
            ])
            
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
        
        db.close()
        
        logger.success(f"Exported {len(contacts)} contacts to {output}")
    
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")


@cli.command()
def stats():
    """Show database statistics"""
    try:
        from app.models.database import Contact, Playlist, Venue

        db = SessionLocal()

        total_contacts = db.query(Contact).count()
        verified_contacts = db.query(Contact).filter(Contact.verified == True).count()
        total_playlists = db.query(Playlist).count()
        total_venues = db.query(Venue).count()

        click.echo("\n📊 Database Statistics\n")
        click.echo(f"Total Contacts: {total_contacts}")
        click.echo(f"Verified Contacts: {verified_contacts}")
        click.echo(f"Total Playlists: {total_playlists}")
        click.echo(f"Total Venues: {total_venues}")

        # Top curators by score
        top_contacts = db.query(Contact).order_by(Contact.priority_score.desc()).limit(10).all()

        click.echo("\n🏆 Top 10 Contacts by Priority Score\n")
        for i, contact in enumerate(top_contacts, 1):
            click.echo(f"{i}. {contact.full_name or contact.username} - Score: {contact.priority_score:.1f} - Followers: {contact.follower_count}")

        db.close()

    except Exception as e:
        logger.error(f"Stats failed: {str(e)}")


@cli.command()
@click.argument('worker_type', type=click.Choice(['scrape', 'normalize', 'enrich', 'graph', 'outreach']))
@click.option('--concurrency', default=1, help='Number of concurrent worker processes')
def start_worker(worker_type, concurrency):
    """Start a worker process"""
    click.echo(f"Starting {worker_type} worker with concurrency: {concurrency}")

    if worker_type == "scrape":
        from app.workers.scrape_worker import ScrapeWorker
        import asyncio

        async def run_worker():
            worker = ScrapeWorker()
            await worker.run()

        asyncio.run(run_worker())

    elif worker_type == "normalize":
        from app.workers.signal_normalizer_worker import SignalNormalizerWorker
        import asyncio

        async def run_worker():
            worker = SignalNormalizerWorker()
            await worker.run()

        asyncio.run(run_worker())

    elif worker_type == "enrich":
        from app.workers.entity_resolver_worker import EntityResolverEnrichmentWorker
        import asyncio

        async def run_worker():
            worker = EntityResolverEnrichmentWorker()
            await worker.run()

        asyncio.run(run_worker())

    elif worker_type == "graph":
        from app.workers.graph_cluster_worker import GraphBuilderClusterWorker
        import asyncio

        async def run_worker():
            worker = GraphBuilderClusterWorker()
            await worker.run()

        asyncio.run(run_worker())

    elif worker_type == "outreach":
        from app.workers.outreach_worker import OutreachWorker
        import asyncio

        async def run_worker():
            worker = OutreachWorker()
            await worker.run()

        asyncio.run(run_worker())

    else:
        click.echo(f"Unknown worker type: {worker_type}")
        click.echo("Available workers: scrape, normalize, enrich, graph, outreach")


if __name__ == '__main__':
    cli()
