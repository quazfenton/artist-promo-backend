"""
Deezer Playlist & Artist Scraper

Scrapes Deezer for:
- Artist profiles
- Playlists
- Tracks
- Curator contacts

Features:
- Public API scraping (no auth required)
- Playlist extraction
- Artist profile scraping
- Contact info extraction
"""

from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from loguru import logger
from datetime import datetime
import re
from .base_scraper import BaseScraper


class DeezerScraper(BaseScraper):
    """Deezer scraper for playlist and artist discovery"""

    def __init__(self):
        super().__init__("deezer_scraper")
        self.base_url = "https://www.deezer.com"
        self.api_base = "https://api.deezer.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html;q=0.9",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def scrape_artist(self, artist_id: str) -> Optional[Dict]:
        """
        Scrape artist profile using Deezer API
        
        Args:
            artist_id: Deezer artist ID
            
        Returns:
            Artist profile data or None
        """
        try:
            logger.info(f"[{self.name}] Scraping artist: {artist_id}")
            
            # Use Deezer public API
            api_url = f"{self.api_base}/artist/{artist_id}"
            response = self.session.get(api_url, timeout=30)
            response.raise_for_status()
            
            artist_data = response.json()
            
            # Extract additional info from web profile
            web_data = self._scrape_artist_web_profile(artist_id)
            
            enriched_data = {
                "platform_id": str(artist_data.get('id')),
                "name": artist_data.get('name'),
                "platform": "deezer",
                "profile_url": artist_data.get('link'),
                "follower_count": artist_data.get('nb_fan', 0),
                "picture": artist_data.get('picture_xl'),
                "picture_small": artist_data.get('picture_small'),
                "picture_medium": artist_data.get('picture_medium'),
                "picture_big": artist_data.get('picture_big'),
                "tracklist": artist_data.get('tracklist'),
                "bio": web_data.get('bio', ''),
                "contact_info": web_data.get('contact_info', {}),
                "social_links": web_data.get('social_links', {}),
                "scraped_at": datetime.utcnow().isoformat(),
            }
            
            self.save_result(enriched_data)
            logger.info(f"[{self.name}] Saved artist: {enriched_data['name']}")
            
            return enriched_data
            
        except Exception as e:
            logger.error(f"[{self.name}] Artist scrape failed: {e}")
            return None

    def scrape_playlist(self, playlist_id: str) -> List[Dict]:
        """
        Scrape playlist using Deezer API
        
        Args:
            playlist_id: Deezer playlist ID
            
        Returns:
            List of tracks
        """
        try:
            logger.info(f"[{self.name}] Scraping playlist: {playlist_id}")
            
            # Get playlist info
            api_url = f"{self.api_base}/playlist/{playlist_id}"
            response = self.session.get(api_url, timeout=30)
            response.raise_for_status()
            
            playlist_data = response.json()
            
            # Extract tracks
            tracks = []
            tracks_data = playlist_data.get('tracks', {}).get('data', [])
            
            for track in tracks_data:
                artist = track.get('artist', {})
                album = track.get('album', {})
                
                track_data = {
                    "platform_id": str(track.get('id')),
                    "title": track.get('title'),
                    "artist": artist.get('name'),
                    "artist_id": str(artist.get('id')),
                    "album": album.get('title'),
                    "album_id": str(album.get('id')),
                    "duration": track.get('duration'),
                    "rank": track.get('rank'),
                    "explicit_lyrics": track.get('explicit_lyrics', False),
                    "preview": track.get('preview'),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                
                tracks.append(track_data)
            
            # Save playlist metadata
            playlist_meta = {
                "platform_id": str(playlist_data.get('id')),
                "name": playlist_data.get('title'),
                "platform": "deezer",
                "playlist_url": playlist_data.get('link'),
                "curator": playlist_data.get('creator', {}).get('name'),
                "curator_id": str(playlist_data.get('creator', {}).get('id')),
                "track_count": playlist_data.get('nb_tracks', 0),
                "fans": playlist_data.get('fans', 0),
                "public": playlist_data.get('public', True),
                "tracks": tracks,
                "scraped_at": datetime.utcnow().isoformat(),
            }
            
            self.save_result(playlist_meta)
            logger.info(f"[{self.name}] Saved playlist: {playlist_meta['name']} ({len(tracks)} tracks)")
            
            return tracks
            
        except Exception as e:
            logger.error(f"[{self.name}] Playlist scrape failed: {e}")
            return []

    def search_playlists(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for playlists by genre/keyword
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of playlists
        """
        try:
            logger.info(f"[{self.name}] Searching playlists: {query}")
            
            search_url = f"{self.api_base}/search/playlist?q={query}&limit={limit}"
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            playlists = []
            
            for playlist in data.get('data', []):
                playlist_data = {
                    "platform_id": str(playlist.get('id')),
                    "name": playlist.get('title'),
                    "platform": "deezer",
                    "playlist_url": playlist.get('link'),
                    "curator": playlist.get('creator', {}).get('name'),
                    "track_count": playlist.get('nb_tracks', 0),
                    "fans": playlist.get('fans', 0),
                    "picture": playlist.get('picture_xl'),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                
                playlists.append(playlist_data)
                self.save_result(playlist_data)
            
            logger.info(f"[{self.name}] Found {len(playlists)} playlists for '{query}'")
            return playlists
            
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}")
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
            logger.info(f"[{self.name}] Searching artists: {query}")
            
            search_url = f"{self.api_base}/search/artist?q={query}&limit={limit}"
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            artists = []
            
            for artist in data.get('data', []):
                artist_data = {
                    "platform_id": str(artist.get('id')),
                    "name": artist.get('name'),
                    "platform": "deezer",
                    "profile_url": artist.get('link'),
                    "follower_count": artist.get('nb_fan', 0),
                    "picture": artist.get('picture_xl'),
                    "radio": artist.get('radio', True),
                    "tracklist": artist.get('tracklist'),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                
                artists.append(artist_data)
                self.save_result(artist_data)
            
            logger.info(f"[{self.name}] Found {len(artists)} artists for '{query}'")
            return artists
            
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}")
            return []

    def _scrape_artist_web_profile(self, artist_id: str) -> Dict:
        """Scrape additional info from web profile"""
        web_data = {
            'bio': '',
            'contact_info': {},
            'social_links': {},
        }
        
        try:
            web_url = f"{self.base_url}/artist/{artist_id}"
            response = self.session.get(web_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract bio
            bio_elem = soup.find('meta', property='og:description')
            if bio_elem:
                web_data['bio'] = bio_elem.get('content', '')
            
            # Extract social links
            social_links = soup.find_all('a', class_='social-link')
            for link in social_links:
                href = link.get('href', '')
                if 'facebook.com' in href:
                    web_data['social_links']['facebook'] = href
                elif 'twitter.com' in href or 'x.com' in href:
                    web_data['social_links']['twitter'] = href
                elif 'instagram.com' in href:
                    web_data['social_links']['instagram'] = href
                elif 'youtube.com' in href:
                    web_data['social_links']['youtube'] = href
            
            # Extract contact info from bio
            if web_data['bio']:
                web_data['contact_info'] = self._extract_contact_info(web_data['bio'])
            
        except Exception as e:
            logger.warning(f"[{self.name}] Web profile scrape failed: {e}")
        
        return web_data

    def _extract_contact_info(self, bio: str) -> Dict[str, str]:
        """Extract contact information from bio"""
        contact = {}
        
        # Email patterns
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ]
        
        for pattern in email_patterns:
            emails = re.findall(pattern, bio, re.IGNORECASE)
            if emails:
                contact['email'] = emails[0]
                break
        
        # Website
        website_match = re.search(r'(https?://[^\s]+)', bio)
        if website_match:
            contact['website'] = website_match.group(1)
        
        return contact

    def get_artist_top_tracks(self, artist_id: str, limit: int = 10) -> List[Dict]:
        """
        Get artist's top tracks
        
        Args:
            artist_id: Deezer artist ID
            limit: Max tracks to return
            
        Returns:
            List of top tracks
        """
        try:
            logger.info(f"[{self.name}] Getting top tracks for artist: {artist_id}")
            
            api_url = f"{self.api_base}/artist/{artist_id}/top?limit={limit}"
            response = self.session.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            tracks = []
            
            for track in data.get('data', []):
                track_data = {
                    "platform_id": str(track.get('id')),
                    "title": track.get('title'),
                    "artist": track.get('artist', {}).get('name'),
                    "album": track.get('album', {}).get('title'),
                    "duration": track.get('duration'),
                    "rank": track.get('rank'),
                    "preview": track.get('preview'),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                tracks.append(track_data)
            
            return tracks
            
        except Exception as e:
            logger.error(f"[{self.name}] Top tracks fetch failed: {e}")
            return []

    def get_artist_albums(self, artist_id: str, limit: int = 10) -> List[Dict]:
        """
        Get artist's albums
        
        Args:
            artist_id: Deezer artist ID
            limit: Max albums to return
            
        Returns:
            List of albums
        """
        try:
            logger.info(f"[{self.name}] Getting albums for artist: {artist_id}")
            
            api_url = f"{self.api_base}/artist/{artist_id}/albums?limit={limit}"
            response = self.session.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            albums = []
            
            for album in data.get('data', []):
                album_data = {
                    "platform_id": str(album.get('id')),
                    "title": album.get('title'),
                    "artist": album.get('artist', {}).get('name'),
                    "release_date": album.get('release_date'),
                    "track_count": album.get('nb_tracks', 0),
                    "fans": album.get('fans', 0),
                    "cover": album.get('cover_xl'),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                albums.append(album_data)
            
            return albums
            
        except Exception as e:
            logger.error(f"[{self.name}] Albums fetch failed: {e}")
            return []
