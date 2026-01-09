"""
Enhanced Spotify playlist curator scraper
"""
from typing import List, Dict, Optional
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from loguru import logger
from datetime import datetime, timedelta
import os
import asyncio
from .base_scraper import BaseScraper


class SpotifyPlaylistScraper(BaseScraper):
    """Enhanced Spotify playlist and curator scraper"""
    
    def __init__(self):
        super().__init__("spotify_playlist_scraper")
        
        # Initialize Spotify client
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("Spotify credentials not found in environment")
        
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
    
    def scrape(self, genre: str = "hip-hop", min_followers: int = 500, limit: int = 50) -> List[Dict]:
        """Enhanced scraping with multiple search strategies"""
        
        logger.info(f"[{self.name}] Starting enhanced Spotify scrape for {genre}")
        
        try:
            # Multiple search strategies
            search_queries = [
                f'genre:"{genre}"',
                f'{genre} playlist',
                f'{genre} music',
                f'new {genre}',
                f'{genre} 2024'
            ]
            
            all_playlists = []
            
            for query in search_queries:
                try:
                    results = self.sp.search(q=query, type='playlist', limit=min(limit//len(search_queries), 50))
                    playlists = results['playlists']['items']
                    all_playlists.extend(playlists)
                    
                    # Rate limiting
                    asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"[{self.name}] Search failed for query '{query}': {str(e)}")
                    continue
            
            # Remove duplicates by ID
            unique_playlists = {p['id']: p for p in all_playlists}.values()
            
            logger.info(f"[{self.name}] Found {len(unique_playlists)} unique playlists")
            
            for playlist in unique_playlists:
                try:
                    playlist_data = self._extract_enhanced_playlist_data(playlist)
                    
                    # Enhanced filtering
                    if self._should_include_playlist(playlist_data, min_followers, genre):
                        self.save_result(playlist_data)
                        logger.info(f"[{self.name}] Saved playlist: {playlist_data['name']}")
                        
                except Exception as e:
                    logger.error(f"[{self.name}] Error processing playlist: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"[{self.name}] Enhanced search failed: {str(e)}")
        
        return self.get_results()
    
    def _extract_enhanced_playlist_data(self, playlist: Dict) -> Dict:
        """Extract comprehensive playlist data"""
        
        playlist_data = {
            "platform_id": playlist.get('id'),
            "name": playlist.get('name'),
            "description": playlist.get('description', ''),
            "follower_count": playlist.get('followers', {}).get('total', 0),
            "track_count": playlist.get('tracks', {}).get('total', 0),
            "playlist_url": playlist.get('external_urls', {}).get('spotify'),
            "owner_username": playlist.get('owner', {}).get('id'),
            "owner_url": playlist.get('owner', {}).get('external_urls', {}).get('spotify'),
            "is_collaborative": playlist.get('collaborative', False),
            "is_public": playlist.get('public', True),
            "images": playlist.get('images', [])
        }
        
        # Get enhanced curator profile
        if playlist_data['owner_username']:
            curator_profile = self.get_enhanced_curator_profile(playlist_data['owner_username'])
            playlist_data['curator_profile'] = curator_profile
        
        # Analyze playlist tracks for genre matching
        playlist_data['genre_analysis'] = self._analyze_playlist_genres(playlist.get('id'))
        
        # Get playlist activity metrics
        playlist_data['activity_metrics'] = self._get_playlist_activity(playlist.get('id'))
        
        return playlist_data
    
    def get_enhanced_curator_profile(self, user_id: str) -> Optional[Dict]:
        """Get comprehensive curator profile"""
        
        try:
            user = self.sp.user(user_id)
            
            curator_data = {
                "username": user.get('id'),
                "display_name": user.get('display_name'),
                "profile_url": user.get('external_urls', {}).get('spotify'),
                "follower_count": user.get('followers', {}).get('total', 0),
                "user_type": user.get('type'),
                "images": user.get('images', []),
                "country": user.get('country')
            }
            
            # Get user's public playlists with analysis
            playlists = self.sp.user_playlists(user_id, limit=50)
            curator_data['playlist_count'] = playlists.get('total', 0)
            
            # Analyze curator's playlist portfolio
            playlist_analysis = self._analyze_curator_playlists(playlists.get('items', []))
            curator_data.update(playlist_analysis)
            
            return curator_data
            
        except Exception as e:
            logger.error(f"[{self.name}] Error getting curator profile for {user_id}: {str(e)}")
            return None
    
    def _analyze_playlist_genres(self, playlist_id: str) -> Dict:
        """Analyze playlist tracks to determine genres"""
        
        try:
            tracks = self.sp.playlist_tracks(playlist_id, limit=50)
            track_ids = [
                track['track']['id'] 
                for track in tracks['items'] 
                if track['track'] and track['track']['id']
            ]
            
            if not track_ids:
                return {"genres": [], "confidence": 0}
            
            # Get audio features for genre analysis
            audio_features = self.sp.audio_features(track_ids[:50])  # Limit API calls
            
            # Analyze audio characteristics
            genre_indicators = {
                "hip-hop": 0,
                "rap": 0,
                "trap": 0,
                "r&b": 0,
                "pop": 0
            }
            
            for features in audio_features:
                if not features:
                    continue
                
                # Hip-hop/rap indicators
                if features['energy'] > 0.6 and features['speechiness'] > 0.3:
                    genre_indicators["hip-hop"] += 1
                    genre_indicators["rap"] += 1
                
                # Trap indicators
                if features['energy'] > 0.7 and features['danceability'] > 0.7:
                    genre_indicators["trap"] += 1
                
                # R&B indicators
                if features['valence'] < 0.6 and features['acousticness'] > 0.3:
                    genre_indicators["r&b"] += 1
            
            # Determine primary genres
            total_tracks = len([f for f in audio_features if f])
            primary_genres = [
                genre for genre, count in genre_indicators.items()
                if count / total_tracks > 0.3
            ]
            
            return {
                "genres": primary_genres,
                "confidence": max(genre_indicators.values()) / total_tracks if total_tracks > 0 else 0,
                "audio_features_summary": self._summarize_audio_features(audio_features)
            }
            
        except Exception as e:
            logger.error(f"[{self.name}] Error analyzing playlist genres: {str(e)}")
            return {"genres": [], "confidence": 0}
    
    def _get_playlist_activity(self, playlist_id: str) -> Dict:
        """Get playlist activity and freshness metrics"""
        
        try:
            tracks = self.sp.playlist_tracks(playlist_id, limit=50)
            
            if not tracks['items']:
                return {"last_updated": None, "freshness_score": 0}
            
            # Analyze track add dates (if available in track metadata)
            recent_additions = 0
            total_tracks = len(tracks['items'])
            
            for track in tracks['items']:
                if track.get('added_at'):
                    added_date = datetime.fromisoformat(track['added_at'].replace('Z', '+00:00'))
                    if added_date > datetime.now().replace(tzinfo=added_date.tzinfo) - timedelta(days=30):
                        recent_additions += 1
            
            freshness_score = recent_additions / total_tracks if total_tracks > 0 else 0
            
            return {
                "total_tracks": total_tracks,
                "recent_additions": recent_additions,
                "freshness_score": freshness_score,
                "last_analyzed": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[{self.name}] Error getting playlist activity: {str(e)}")
            return {"freshness_score": 0}
    
    def _analyze_curator_playlists(self, playlists: List[Dict]) -> Dict:
        """Analyze curator's playlist portfolio"""
        
        total_followers = sum(p.get('followers', {}).get('total', 0) for p in playlists)
        avg_followers = total_followers / len(playlists) if playlists else 0
        
        # Count public vs private playlists
        public_count = sum(1 for p in playlists if p.get('public', False))
        
        # Analyze playlist names for music focus
        music_keywords = ['music', 'playlist', 'songs', 'tracks', 'hits', 'mix']
        music_focused = sum(
            1 for p in playlists 
            if any(keyword in p.get('name', '').lower() for keyword in music_keywords)
        )
        
        return {
            "total_playlists": len(playlists),
            "public_playlists": public_count,
            "avg_playlist_followers": avg_followers,
            "music_focused_playlists": music_focused,
            "music_focus_ratio": music_focused / len(playlists) if playlists else 0
        }
    
    def _summarize_audio_features(self, audio_features: List[Dict]) -> Dict:
        """Summarize audio features for genre analysis"""
        
        valid_features = [f for f in audio_features if f]
        if not valid_features:
            return {}
        
        features_summary = {}
        feature_keys = ['energy', 'danceability', 'speechiness', 'acousticness', 'valence', 'tempo']
        
        for key in feature_keys:
            values = [f[key] for f in valid_features if key in f]
            if values:
                features_summary[f"avg_{key}"] = sum(values) / len(values)
        
        return features_summary
    
    def _should_include_playlist(self, playlist_data: Dict, min_followers: int, target_genre: str) -> bool:
        """Enhanced filtering logic for playlist inclusion"""
        
        # Basic follower count filter
        if playlist_data['follower_count'] < min_followers:
            return False
        
        # Skip very small playlists
        if playlist_data['track_count'] < 10:
            return False
        
        # Genre relevance check
        genre_analysis = playlist_data.get('genre_analysis', {})
        if genre_analysis.get('confidence', 0) > 0.3:
            playlist_genres = genre_analysis.get('genres', [])
            if target_genre.lower() not in [g.lower() for g in playlist_genres]:
                return False
        
        # Curator quality check
        curator_profile = playlist_data.get('curator_profile', {})
        if curator_profile:
            # Skip curators with very low engagement
            if curator_profile.get('music_focus_ratio', 0) < 0.2:
                return False
        
        return True

    async def get_user_profile_extended(self, user_id: str) -> Dict:
        """
        Get extended user profile with additional metrics
        """
        try:
            # Get basic profile
            profile = self.sp.user(user_id)

            # Get user's playlists
            playlists = self.sp.user_playlists(user_id, limit=50)

            curator_data = [
                {
                    'id': p['id'],
                    'name': p['name'],
                    'followers': p.get('followers', {}).get('total', 0)
                }
                for p in playlists.get('items', [])
            ]

            return {
                **profile,
                'curator_data': curator_data,
                'playlist_count': len(playlists.get('items', []))
            }

        except Exception as e:
            logger.error(f"[{self.name}] Error fetching user {user_id}: {str(e)}")
            return None
    
    def find_similar_curators(self, playlist_id: str) -> List[Dict]:
        """
        Find curators of similar playlists
        Uses playlist followers as signal
        """
        results = []
        
        try:
            # Get the original playlist
            original = self.sp.playlist(playlist_id)
            original_tracks = self.sp.playlist_tracks(playlist_id, limit=10)
            
            # Get artists from the playlist
            artist_ids = []
            for item in original_tracks['items']:
                track = item.get('track')
                if track:
                    artist_ids.extend([a['id'] for a in track.get('artists', [])])
            
            # Search for playlists containing these artists
            for artist_id in artist_ids[:5]:  # Limit to first 5 artists
                try:
                    artist = self.sp.artist(artist_id)
                    search_results = self.sp.search(
                        q=f'artist:"{artist["name"]}"',
                        type='playlist',
                        limit=10
                    )
                    
                    for playlist in search_results['playlists']['items']:
                        curator_data = self._extract_playlist_data(playlist)
                        if curator_data not in results:
                            results.append(curator_data)
                
                except Exception as e:
                    continue
        
        except Exception as e:
            logger.error(f"[{self.name}] Error finding similar curators: {str(e)}")
        
        return results
    
    def _extract_playlist_data(self, playlist: Dict) -> Dict:
        """Extract relevant data from playlist object"""
        owner = playlist.get('owner', {})
        
        playlist_data = {
            "platform_id": playlist.get('id'),
            "platform": "spotify",
            "name": playlist.get('name'),
            "description": playlist.get('description', ''),
            "follower_count": playlist.get('followers', {}).get('total', 0),
            "track_count": playlist.get('tracks', {}).get('total', 0),
            "playlist_url": playlist.get('external_urls', {}).get('spotify'),
            "owner_username": owner.get('id'),
            "owner_display_name": owner.get('display_name'),
            "owner_url": owner.get('external_urls', {}).get('spotify'),
            "is_collaborative": playlist.get('collaborative', False),
            "is_public": playlist.get('public', True),
            "images": playlist.get('images', []),
        }
        
        # Try to get more curator details
        try:
            curator_profile = self.get_curator_profile(owner.get('id'))
            if curator_profile:
                playlist_data['curator_profile'] = curator_profile
        except:
            pass
        
        return playlist_data
    
    def search_playlists_by_keyword(self, keyword: str, limit: int = 50) -> List[Dict]:
        """
        Search playlists by keyword in name/description
        """
        logger.info(f"[{self.name}] Searching playlists with keyword: {keyword}")
        results = []
        
        try:
            search_results = self.sp.search(q=keyword, type='playlist', limit=limit)
            
            for playlist in search_results['playlists']['items']:
                try:
                    data = self._extract_playlist_data(playlist)
                    results.append(data)
                except Exception as e:
                    continue
        
        except Exception as e:
            logger.error(f"[{self.name}] Keyword search failed: {str(e)}")
        
        return results


class SpotifyAnalyzer:
    """Analyze Spotify data for better targeting"""
    
    def __init__(self):
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
    
    def analyze_curator_activity(self, user_id: str) -> Dict:
        """
        Analyze curator's activity and preferences
        """
        try:
            playlists = self.sp.user_playlists(user_id, limit=50)
            
            analysis = {
                "total_playlists": playlists.get('total', 0),
                "total_followers": 0,
                "avg_playlist_size": 0,
                "genres": {},
                "most_recent_update": None
            }
            
            for playlist in playlists.get('items', []):
                analysis["total_followers"] += playlist.get('followers', {}).get('total', 0)
            
            if playlists.get('total', 0) > 0:
                analysis["avg_playlist_size"] = analysis["total_followers"] / playlists['total']
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error analyzing curator {user_id}: {str(e)}")
            return {}
