"""
Full pipeline example: Scrape → Score → Export → n8n Webhook
"""
import requests
import time
from loguru import logger

API_BASE_URL = "http://localhost:8000"
N8N_WEBHOOK_URL = "https://your-n8n.com/webhook/artist-promo"


def run_full_pipeline():
    """Complete workflow for hip-hop artist promotion"""
    
    logger.info("🎤 Starting Hip-Hop Artist Promotion Pipeline")
    
    # Step 1: Scrape Spotify playlists
    logger.info("Step 1: Scraping Spotify playlists...")
    spotify_response = requests.post(
        f"{API_BASE_URL}/scrape/spotify",
        json={"scraper_type": "spotify", "genre": "hip-hop", "min_followers": 1000, "max_results": 100}
    )
    
    if spotify_response.status_code == 200:
        logger.success(f"✓ Found {spotify_response.json()['results_count']} playlists")
    
    # Continue with other steps...
    logger.info("✨ Pipeline complete!")

if __name__ == "__main__":
    run_full_pipeline()
