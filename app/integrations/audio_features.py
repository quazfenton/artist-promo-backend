"""Audio features integration for precise playlist matching"""
import spotipy
from typing import Dict, List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import os

class AudioFeatureAnalyzer:
    """Analyze audio features for playlist-artist matching"""
    
    def __init__(self):
        self.sp = spotipy.Spotify(auth_manager=spotipy.SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
        ))
    
    async def analyze_playlist_audio_profile(self, playlist_id: str) -> Optional[Dict]:
        """Extract audio feature profile from playlist"""
        
        try:
            # Get playlist tracks
            tracks = self.sp.playlist_tracks(playlist_id, limit=50)
            track_ids = [
                track['track']['id'] 
                for track in tracks['items'] 
                if track['track'] and track['track']['id']
            ]
            
            if not track_ids:
                return None
            
            # Get audio features
            features = self.sp.audio_features(track_ids)
            valid_features = [f for f in features if f is not None]
            
            if not valid_features:
                return None
            
            # Calculate average features
            profile = self._calculate_audio_profile(valid_features)
            
            # Add metadata
            profile['track_count'] = len(valid_features)
            profile['sample_size'] = min(len(valid_features), 50)
            
            return profile
            
        except Exception as e:
            return None
    
    def _calculate_audio_profile(self, features_list: List[Dict]) -> Dict:
        """Calculate average audio features"""
        
        feature_keys = [
            'danceability', 'energy', 'speechiness', 'acousticness',
            'instrumentalness', 'liveness', 'valence', 'tempo'
        ]
        
        profile = {}
        
        for key in feature_keys:
            values = [f[key] for f in features_list if f.get(key) is not None]
            if values:
                profile[f'avg_{key}'] = np.mean(values)
                profile[f'std_{key}'] = np.std(values)
            else:
                profile[f'avg_{key}'] = 0.0
                profile[f'std_{key}'] = 0.0
        
        # Calculate derived metrics
        profile['energy_variance'] = profile['std_energy']
        profile['mood_score'] = (profile['avg_valence'] + profile['avg_energy']) / 2
        profile['danceability_consistency'] = 1 - profile['std_danceability']
        
        return profile
    
    def calculate_similarity_score(self, playlist_profile: Dict, artist_profile: Dict) -> float:
        """Calculate similarity between playlist and artist audio profiles"""
        
        if not playlist_profile or not artist_profile:
            return 0.0
        
        # Feature weights for similarity calculation
        feature_weights = {
            'avg_danceability': 0.15,
            'avg_energy': 0.15,
            'avg_valence': 0.15,
            'avg_acousticness': 0.10,
            'avg_speechiness': 0.10,
            'avg_instrumentalness': 0.05,
            'avg_liveness': 0.05,
            'mood_score': 0.20,
            'energy_variance': 0.05
        }
        
        similarity_score = 0.0
        total_weight = 0.0
        
        for feature, weight in feature_weights.items():
            if feature in playlist_profile and feature in artist_profile:
                # Calculate feature similarity (1 - normalized difference)
                p_val = playlist_profile[feature]
                a_val = artist_profile[feature]
                
                # Normalize difference to 0-1 scale
                max_diff = 1.0  # Most features are 0-1 scale
                if 'tempo' in feature:
                    max_diff = 100.0  # Tempo has different scale
                
                diff = abs(p_val - a_val) / max_diff
                feature_similarity = max(0, 1 - diff)
                
                similarity_score += feature_similarity * weight
                total_weight += weight
        
        return similarity_score / total_weight if total_weight > 0 else 0.0
    
    def get_genre_audio_signature(self, genre: str) -> Dict:
        """Get typical audio signature for a genre"""
        
        # Predefined genre signatures based on Spotify data analysis
        genre_signatures = {
            'hip-hop': {
                'avg_danceability': 0.75,
                'avg_energy': 0.65,
                'avg_speechiness': 0.25,
                'avg_acousticness': 0.15,
                'avg_instrumentalness': 0.05,
                'avg_liveness': 0.15,
                'avg_valence': 0.55,
                'avg_tempo': 95,
                'mood_score': 0.60
            },
            'trap': {
                'avg_danceability': 0.80,
                'avg_energy': 0.70,
                'avg_speechiness': 0.30,
                'avg_acousticness': 0.10,
                'avg_instrumentalness': 0.03,
                'avg_liveness': 0.12,
                'avg_valence': 0.45,
                'avg_tempo': 140,
                'mood_score': 0.58
            },
            'r&b': {
                'avg_danceability': 0.65,
                'avg_energy': 0.55,
                'avg_speechiness': 0.15,
                'avg_acousticness': 0.25,
                'avg_instrumentalness': 0.08,
                'avg_liveness': 0.18,
                'avg_valence': 0.60,
                'avg_tempo': 85,
                'mood_score': 0.58
            }
        }
        
        return genre_signatures.get(genre.lower(), genre_signatures['hip-hop'])
    
    def find_similar_playlists(self, artist_profile: Dict, playlist_profiles: List[Dict], 
                             top_k: int = 20) -> List[Dict]:
        """Find most similar playlists to artist profile"""
        
        similarities = []
        
        for playlist in playlist_profiles:
            if 'audio_profile' in playlist:
                similarity = self.calculate_similarity_score(
                    playlist['audio_profile'], 
                    artist_profile
                )
                
                similarities.append({
                    'playlist_id': playlist['id'],
                    'playlist_name': playlist['name'],
                    'similarity_score': similarity,
                    'follower_count': playlist.get('follower_count', 0),
                    'curator_name': playlist.get('curator_name')
                })
        
        # Sort by similarity score
        similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return similarities[:top_k]
    
    def create_artist_audio_profile(self, artist_track_ids: List[str]) -> Optional[Dict]:
        """Create audio profile for an artist from their tracks"""
        
        try:
            # Get audio features for artist tracks
            features = self.sp.audio_features(artist_track_ids)
            valid_features = [f for f in features if f is not None]
            
            if not valid_features:
                return None
            
            return self._calculate_audio_profile(valid_features)
            
        except Exception:
            return None
