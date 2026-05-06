"""
SoundCloud Playlist & Artist Scraper

Scrapes SoundCloud for:
- Artist profiles
- Playlists
- Tracks
- Curator contacts

Features:
- OAuth2 authentication (optional)
- Public scraping (no auth required)
- Playlist extraction
- Artist profile scraping
- Contact info extraction from profiles
"""

from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from loguru import logger
from datetime import datetime
import re
from .base_scraper import BaseScraper


class SoundCloudScraper(BaseScraper):
    """SoundCloud scraper for artist and playlist discovery"""

    def __init__(self):
        super().__init__("soundcloud_scraper")
        self.base_url = "https://soundcloud.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def scrape_artist(self, artist_url: str) -> Optional[Dict]:
        """
        Scrape artist profile
        
        Args:
            artist_url: SoundCloud artist URL
            
        Returns:
            Artist profile data or None
        """
        try:
            logger.info(f"[{self.name}] Scraping artist: {artist_url}")
            
            response = self.session.get(artist_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract artist info
            artist_name = soup.find('meta', property='profile:title')
            artist_name = artist_name.get('content') if artist_name else None
            
            follower_count = soup.find('meta', property='profile:followers')
            follower_count = int(follower_count.get('content')) if follower_count else 0
            
            # Extract bio/description
            bio_elem = soup.find('meta', property='profile:description')
            bio = bio_elem.get('content') if bio_elem else ''
            
            # Extract contact info from bio
            contact_info = self._extract_contact_info(bio)
            
            # Extract social links
            social_links = self._extract_social_links(soup)
            
            # Extract tracks
            tracks = self._extract_tracks(soup)
            
            artist_data = {
                "platform_id": artist_url.split('/')[-1],
                "name": artist_name,
                "platform": "soundcloud",
                "profile_url": artist_url,
                "follower_count": follower_count,
                "bio": bio,
                "contact_info": contact_info,
                "social_links": social_links,
                "tracks": tracks,
                "scraped_at": datetime.utcnow().isoformat(),
            }
            
            if artist_data["name"]:
                self.save_result(artist_data)
                logger.info(f"[{self.name}] Saved artist: {artist_data['name']}")
            
            return artist_data
            
        except Exception as e:
            logger.error(f"[{self.name}] Artist scrape failed: {e}")
            return None

    def scrape_playlist(self, playlist_url: str) -> List[Dict]:
        """
        Scrape playlist for tracks and curators
        
        Args:
            playlist_url: SoundCloud playlist URL
            
        Returns:
            List of track data
        """
        try:
            logger.info(f"[{self.name}] Scraping playlist: {playlist_url}")
            
            response = self.session.get(playlist_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract playlist info
            playlist_title = soup.find('meta', property='playlist:title')
            playlist_title = playlist_title.get('content') if playlist_title else 'Unknown'
            
            # Extract curator info
            curator_elem = soup.find('meta', property='playlist:creator')
            curator = curator_elem.get('content') if curator_elem else None
            
            # Extract tracks
            tracks = self._extract_tracks(soup, is_playlist=True)
            
            playlist_data = {
                "platform_id": playlist_url.split('/')[-1],
                "name": playlist_title,
                "platform": "soundcloud",
                "playlist_url": playlist_url,
                "curator": curator,
                "track_count": len(tracks),
                "tracks": tracks,
                "scraped_at": datetime.utcnow().isoformat(),
            }
            
            self.save_result(playlist_data)
            logger.info(f"[{self.name}] Saved playlist: {playlist_title} ({len(tracks)} tracks)")
            
            return tracks
            
        except Exception as e:
            logger.error(f"[{self.name}] Playlist scrape failed: {e}")
            return []

    def search_artists(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for artists by genre/keyword
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of artist profiles
        """
        try:
            search_url = f"{self.base_url}/search/people?q={query}"
            logger.info(f"[{self.name}] Searching artists: {query}")
            
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            artists = []
            artist_cards = soup.find_all('li', class_='searchResult__item', limit=limit)
            
            for card in artist_cards:
                try:
                    name_elem = card.find('a', class_='searchResultTitle')
                    if not name_elem:
                        continue
                    
                    name = name_elem.get_text(strip=True)
                    url = self.base_url + name_elem.get('href', '')
                    
                    # Extract follower count
                    followers_elem = card.find('span', class_='sc-type-small')
                    followers_text = followers_elem.get_text(strip=True) if followers_elem else '0'
                    followers = self._parse_follower_count(followers_text)
                    
                    artist_data = {
                        "platform_id": url.split('/')[-1],
                        "name": name,
                        "platform": "soundcloud",
                        "profile_url": url,
                        "follower_count": followers,
                        "scraped_at": datetime.utcnow().isoformat(),
                    }
                    
                    artists.append(artist_data)
                    self.save_result(artist_data)
                    
                except Exception as e:
                    logger.warning(f"[{self.name}] Failed to parse artist card: {e}")
                    continue
            
            logger.info(f"[{self.name}] Found {len(artists)} artists for '{query}'")
            return artists
            
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}")
            return []

    def _extract_contact_info(self, bio: str) -> Dict[str, str]:
        """Extract contact information from bio"""
        contact = {}
        
        # Email patterns
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'\b[A-Za-z0-9._%+-]+\(at\)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'\b[A-Za-z0-9._%+-]+ AT [A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ]
        
        for pattern in email_patterns:
            emails = re.findall(pattern, bio, re.IGNORECASE)
            if emails:
                contact['email'] = emails[0].replace('(at)', '@').replace(' AT ', '@')
                break
        
        # Website
        website_match = re.search(r'(https?://[^\s]+)', bio)
        if website_match:
            contact['website'] = website_match.group(1)
        
        # Instagram
        ig_match = re.search(r'@(\w+)', bio)
        if ig_match:
            contact['instagram'] = ig_match.group(1)
        
        return contact

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media links"""
        social = {}
        
        # Look for social links in page
        social_patterns = {
            'instagram': r'instagram\.com/([^\s"\']+)',
            'twitter': r'twitter\.com/([^\s"\']+)',
            'facebook': r'facebook\.com/([^\s"\']+)',
            'youtube': r'youtube\.com/([^\s"\']+)',
        }
        
        page_text = str(soup)
        
        for platform, pattern in social_patterns.items():
            match = re.search(pattern, page_text)
            if match:
                social[platform] = match.group(1)
        
        return social

    def _extract_tracks(self, soup: BeautifulSoup, is_playlist: bool = False) -> List[Dict]:
        """Extract track information"""
        tracks = []
        
        track_elements = soup.find_all('li', class_='soundList__item', limit=50)
        
        for track_elem in track_elements:
            try:
                title_elem = track_elem.find('a', class_='soundTitle__title')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = self.base_url + title_elem.get('href', '')
                
                # Extract artist
                artist_elem = track_elem.find('a', class_='soundContext__username')
                artist = artist_elem.get_text(strip=True) if artist_elem else None
                
                # Extract play count
                plays_elem = track_elem.find('span', class_='sc-statistic--plays')
                plays_text = plays_elem.get_text(strip=True) if plays_elem else '0'
                plays = self._parse_count(plays_text)
                
                track_data = {
                    "platform_id": url.split('/')[-1],
                    "title": title,
                    "artist": artist,
                    "track_url": url,
                    "play_count": plays,
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                
                tracks.append(track_data)
                
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to parse track: {e}")
                continue
        
        return tracks

    def _parse_follower_count(self, text: str) -> int:
        """Parse follower count text to integer"""
        text = text.lower().replace(',', '')
        
        if 'k' in text:
            return int(float(text.replace('k', '')) * 1000)
        elif 'm' in text:
            return int(float(text.replace('m', '')) * 1000000)
        else:
            try:
                return int(text)
            except:
                return 0

    def _parse_count(self, text: str) -> int:
        """Parse count text to integer"""
        return self._parse_follower_count(text)
