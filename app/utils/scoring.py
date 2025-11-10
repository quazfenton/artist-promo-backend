"""
Contact and playlist scoring algorithms
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import os
import math


class ContactScorer:
    """Calculate priority scores for contacts"""
    
    def __init__(self):
        self.weight_followers = float(os.getenv("WEIGHT_FOLLOWERS", 0.4))
        self.weight_recency = float(os.getenv("WEIGHT_RECENCY", 0.3))
        self.weight_engagement = float(os.getenv("WEIGHT_ENGAGEMENT", 0.2))
        self.weight_llm_quality = float(os.getenv("WEIGHT_LLM_QUALITY", 0.1))
    
    def calculate_priority_score(
        self,
        follower_count: int = 0,
        last_active: Optional[datetime] = None,
        engagement_rate: float = 0.0,
        llm_quality_score: Optional[float] = None,
        contact_type: str = "playlist_curator"
    ) -> float:
        """
        Calculate overall priority score (0-100)
        
        Formula:
        Score = 0.4*(Followers normalized) + 
                0.3*(Recency factor) + 
                0.2*(Engagement) +
                0.1*(LLM Quality)
        """
        
        # Normalize followers (log scale for better distribution)
        follower_score = self._normalize_followers(follower_count)
        
        # Calculate recency score
        recency_score = self._calculate_recency_score(last_active)
        
        # Engagement score (already 0-1, just scale to 0-100)
        engagement_score = min(engagement_rate * 100, 100)
        
        # LLM quality score (0-100)
        llm_score = llm_quality_score if llm_quality_score else 50.0
        
        # Weighted average
        total_score = (
            self.weight_followers * follower_score +
            self.weight_recency * recency_score +
            self.weight_engagement * engagement_score +
            self.weight_llm_quality * llm_score
        )
        
        # Apply contact type multiplier
        type_multipliers = {
            "playlist_curator": 1.0,
            "ar_rep": 1.2,
            "publicist": 1.1,
            "manager": 1.15,
            "venue_booker": 0.9,
            "journalist": 1.05
        }
        multiplier = type_multipliers.get(contact_type, 1.0)
        
        return min(total_score * multiplier, 100.0)
    
    def _normalize_followers(self, count: int, max_reference: int = 1000000) -> float:
        """
        Normalize follower count using log scale
        Returns 0-100
        """
        if count <= 0:
            return 0.0
        
        # Use log scale for better distribution
        # 1K followers = ~30, 10K = ~40, 100K = ~60, 1M = ~100
        normalized = (math.log10(count + 1) / math.log10(max_reference)) * 100
        return min(normalized, 100.0)
    
    def _calculate_recency_score(self, last_active: Optional[datetime]) -> float:
        """
        Calculate recency score based on last activity
        Returns 0-100
        """
        if not last_active:
            return 50.0  # Default mid-score if unknown
        
        days_ago = (datetime.utcnow() - last_active).days
        
        if days_ago <= 7:
            return 100.0
        elif days_ago <= 30:
            return 80.0
        elif days_ago <= 60:
            return 60.0
        elif days_ago <= 90:
            return 40.0
        elif days_ago <= 180:
            return 20.0
        else:
            return 10.0
    
    def calculate_match_score(
        self,
        contact_genres: list,
        artist_genres: list,
        contact_bio: str = "",
        artist_description: str = ""
    ) -> float:
        """
        Calculate genre/style match score
        Returns 0-1
        """
        if not contact_genres or not artist_genres:
            return 0.5
        
        # Normalize genres to lowercase
        contact_genres = [g.lower() for g in contact_genres]
        artist_genres = [g.lower() for g in artist_genres]
        
        # Calculate genre overlap
        overlap = set(contact_genres) & set(artist_genres)
        max_possible = max(len(contact_genres), len(artist_genres))
        
        if max_possible == 0:
            return 0.5
        
        genre_score = len(overlap) / max_possible
        
        # TODO: Add LLM-based semantic matching for bios
        # For now, simple keyword matching
        bio_score = self._simple_text_match(contact_bio, artist_description)
        
        # Weighted average
        return (0.7 * genre_score) + (0.3 * bio_score)
    
    def _simple_text_match(self, text1: str, text2: str) -> float:
        """Simple keyword overlap between two texts"""
        if not text1 or not text2:
            return 0.5
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        overlap = words1 & words2
        total = words1 | words2
        
        if len(total) == 0:
            return 0.5
        
        return len(overlap) / len(total)


class VenueScorer:
    """Calculate scores for venues"""
    
    def calculate_venue_score(
        self,
        capacity: Optional[int] = None,
        event_frequency: int = 0,
        genres: list = None,
        artist_genres: list = None,
        avg_attendance: Optional[int] = None
    ) -> float:
        """
        Calculate venue booking priority score
        Returns 0-100
        """
        
        # Capacity score (prefer 100-500 for emerging artists)
        capacity_score = self._score_capacity(capacity)
        
        # Activity score (events per month)
        activity_score = min((event_frequency / 10) * 100, 100)
        
        # Genre match
        genre_score = 50.0
        if genres and artist_genres:
            genre_overlap = set(g.lower() for g in genres) & set(g.lower() for g in artist_genres)
            genre_score = (len(genre_overlap) / len(artist_genres)) * 100 if artist_genres else 50.0
        
        # Attendance score
        attendance_score = self._score_attendance(avg_attendance)
        
        # Weighted average
        total = (
            0.3 * capacity_score +
            0.3 * activity_score +
            0.2 * genre_score +
            0.2 * attendance_score
        )
        
        return min(total, 100.0)
    
    def _score_capacity(self, capacity: Optional[int]) -> float:
        """Score venue capacity (0-100)"""
        if not capacity:
            return 50.0
        
        # Optimal range: 100-500 for emerging artists
        if 100 <= capacity <= 500:
            return 100.0
        elif 50 <= capacity < 100:
            return 80.0
        elif 500 < capacity <= 1000:
            return 70.0
        elif capacity < 50:
            return 60.0
        else:
            return 40.0
    
    def _score_attendance(self, avg_attendance: Optional[int]) -> float:
        """Score average attendance (0-100)"""
        if not avg_attendance:
            return 50.0
        
        # Log scale for attendance
        if avg_attendance <= 0:
            return 0.0
        
        normalized = (math.log10(avg_attendance + 1) / math.log10(1000)) * 100
        return min(normalized, 100.0)


class PlaylistScorer:
    """Calculate relevance scores for playlists"""
    
    def calculate_relevance_score(
        self,
        follower_count: int,
        last_updated: Optional[datetime],
        is_editorial: bool,
        genres: list = None,
        artist_genres: list = None
    ) -> float:
        """
        Calculate playlist relevance score
        Returns 0-100
        """
        
        # Follower score (log scale)
        follower_score = min((math.log10(follower_count + 1) / 6) * 100, 100)
        
        # Recency score
        recency_score = self._playlist_recency_score(last_updated)
        
        # Editorial bonus
        editorial_bonus = 20 if is_editorial else 0
        
        # Genre match
        genre_score = 0
        if genres and artist_genres:
            overlap = set(g.lower() for g in genres) & set(g.lower() for g in artist_genres)
            genre_score = (len(overlap) / len(artist_genres)) * 30 if artist_genres else 0
        
        total = follower_score * 0.4 + recency_score * 0.3 + genre_score + editorial_bonus
        
        return min(total, 100.0)
    
    def _playlist_recency_score(self, last_updated: Optional[datetime]) -> float:
        """Score playlist update recency (0-30)"""
        if not last_updated:
            return 15.0
        
        days_ago = (datetime.utcnow() - last_updated).days
        
        if days_ago <= 7:
            return 30.0
        elif days_ago <= 30:
            return 25.0
        elif days_ago <= 60:
            return 15.0
        else:
            return 5.0
