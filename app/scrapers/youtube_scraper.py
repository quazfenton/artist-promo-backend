"""
YouTube channel email extractor
Extracts business emails from About pages
"""
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from loguru import logger
import os
import re
from .base_scraper import BaseScraper


class YouTubeChannelScraper(BaseScraper):
    """Scrape YouTube channels for contact info"""
    
    def __init__(self):
        super().__init__("youtube_channel_scraper")
        
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YouTube API key not found")
        
        self.youtube = build('youtube', 'v3', developerKey=api_key)
    
    def scrape(self, query: str = "hip hop playlist", max_results: int = 50) -> List[Dict]:
        """
        Search for channels and extract contact info
        """
        logger.info(f"[{self.name}] Searching for: {query}")
        
        try:
            # Search for channels
            search_response = self.youtube.search().list(
                q=query,
                type='channel',
                part='id,snippet',
                maxResults=min(max_results, 50),
                order='relevance'
            ).execute()
            
            for item in search_response.get('items', []):
                channel_id = item['id']['channelId']
                try:
                    channel_data = self.scrape_channel(channel_id)
                    if channel_data:
                        self.save_result(channel_data)
                except Exception as e:
                    logger.error(f"[{self.name}] Error processing channel {channel_id}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {str(e)}")
        
        return self.get_results()
    
    def scrape_channel(self, channel_id: str) -> Optional[Dict]:
        """
        Scrape a specific channel for contact info
        """
        try:
            # Get channel details
            channel_response = self.youtube.channels().list(
                id=channel_id,
                part='snippet,statistics,contentDetails,brandingSettings'
            ).execute()
            
            if not channel_response.get('items'):
                return None
            
            channel = channel_response['items'][0]
            snippet = channel['snippet']
            statistics = channel['statistics']
            branding = channel.get('brandingSettings', {})
            
            # Extract emails from description
            description = snippet.get('description', '')
            emails = self.extract_emails(description)
            
            # Get channel custom URL if available
            custom_url = snippet.get('customUrl', '')
            
            channel_data = {
                "channel_id": channel_id,
                "channel_name": snippet.get('title'),
                "description": description,
                "custom_url": custom_url,
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "subscriber_count": int(statistics.get('subscriberCount', 0)),
                "video_count": int(statistics.get('videoCount', 0)),
                "view_count": int(statistics.get('viewCount', 0)),
                "emails": emails,
                "country": snippet.get('country'),
                "published_at": snippet.get('publishedAt'),
                "thumbnails": snippet.get('thumbnails', {}),
                "keywords": branding.get('channel', {}).get('keywords', '').split(),
            }
            
            # Try to extract more contact info from "About" section
            # Note: YouTube API doesn't directly expose the About page business email
            # This would require scraping the actual page
            
            return channel_data
        
        except Exception as e:
            logger.error(f"[{self.name}] Error scraping channel {channel_id}: {str(e)}")
            return None
    
    def scrape_channel_about_page(self, channel_id: str) -> Optional[Dict]:
        """
        Scrape the About page HTML to extract business email
        (YouTube API doesn't expose this directly)
        """
        try:
            url = f"https://www.youtube.com/channel/{channel_id}/about"
            response = self.fetch_page(url)
            
            if not response:
                return None
            
            soup = self.parse_html(response.text)
            
            # Look for email in various places
            emails = []
            
            # Method 1: Look in "View Email Address" button
            email_buttons = soup.find_all('a', href=re.compile(r'mailto:'))
            for button in email_buttons:
                email = button['href'].replace('mailto:', '')
                emails.append(email)
            
            # Method 2: Parse JavaScript data
            script_tags = soup.find_all('script')
            for script in script_tags:
                if 'ytInitialData' in script.text:
                    # Extract email from ytInitialData JSON
                    email_matches = re.findall(
                        r'"label":"Business email","content":"([^"]+)"',
                        script.text
                    )
                    emails.extend(email_matches)
            
            # Method 3: Look in description text
            description_div = soup.find('div', {'id': 'description'})
            if description_div:
                emails.extend(self.extract_emails(description_div.text))
            
            return {
                "channel_id": channel_id,
                "emails": list(set(emails)),
                "source": "about_page"
            }
        
        except Exception as e:
            logger.error(f"[{self.name}] Error scraping about page for {channel_id}: {str(e)}")
            return None
    
    def find_hip_hop_curators(self, min_subscribers: int = 10000) -> List[Dict]:
        """
        Find hip-hop focused channels/curators
        """
        search_terms = [
            "hip hop playlist",
            "rap music channel",
            "hip hop curator",
            "underground rap",
            "new rap music",
            "hip hop weekly"
        ]
        
        all_results = []
        
        for term in search_terms:
            try:
                results = self.scrape(query=term, max_results=10)
                
                # Filter by subscribers
                filtered = [
                    r for r in results
                    if r.get('subscriber_count', 0) >= min_subscribers
                ]
                
                all_results.extend(filtered)
                logger.info(f"[{self.name}] Found {len(filtered)} channels for '{term}'")
            
            except Exception as e:
                logger.error(f"[{self.name}] Error searching '{term}': {str(e)}")
                continue
        
        # Remove duplicates
        seen = set()
        unique_results = []
        for result in all_results:
            channel_id = result.get('channel_id')
            if channel_id not in seen:
                seen.add(channel_id)
                unique_results.append(result)
        
        return unique_results
