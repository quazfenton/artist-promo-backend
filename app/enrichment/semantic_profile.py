"""Semantic enrichment and contextual analytics"""
import openai
from typing import Dict, List, Optional
import json
import re
from app.monitoring.logging import log_info
import os

class SemanticProfiler:
    """AI-powered contact and playlist profiling"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def analyze_curator_profile(self, bio: str, playlist_names: List[str] = None) -> Dict:
        """Extract semantic insights from curator bio and playlists"""
        
        prompt = f"""
        Analyze this music curator profile and extract insights:
        
        Bio: {bio}
        Playlists: {', '.join(playlist_names or [])}
        
        Return JSON with:
        - mood_tags: [list of mood/vibe keywords]
        - promotion_style: "formal" | "casual" | "creative"
        - response_likelihood: 0.0-1.0 score
        - genre_preferences: [list of genres]
        - submission_preferences: "email" | "dm" | "form" | "unknown"
        - best_approach: brief strategy suggestion
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add confidence score
            result['confidence'] = self._calculate_confidence(bio, playlist_names)
            
            return result
            
        except Exception as e:
            log_info("Semantic analysis failed", error=str(e))
            return self._fallback_analysis(bio)
    
    def _calculate_confidence(self, bio: str, playlist_names: List[str] = None) -> float:
        """Calculate confidence in semantic analysis"""
        
        confidence = 0.5  # Base confidence
        
        # More text = higher confidence
        if len(bio) > 100:
            confidence += 0.2
        if len(bio) > 200:
            confidence += 0.1
        
        # Playlist context helps
        if playlist_names and len(playlist_names) > 3:
            confidence += 0.2
        
        # Music keywords boost confidence
        music_keywords = ['music', 'playlist', 'curator', 'artist', 'song', 'track']
        keyword_count = sum(1 for word in music_keywords if word in bio.lower())
        confidence += min(keyword_count * 0.05, 0.2)
        
        return min(confidence, 1.0)
    
    def _fallback_analysis(self, bio: str) -> Dict:
        """Fallback analysis without AI"""
        
        bio_lower = bio.lower()
        
        # Simple keyword-based analysis
        mood_tags = []
        if any(word in bio_lower for word in ['chill', 'relax', 'calm']):
            mood_tags.append('chill')
        if any(word in bio_lower for word in ['energy', 'hype', 'party']):
            mood_tags.append('energetic')
        if any(word in bio_lower for word in ['indie', 'underground', 'alternative']):
            mood_tags.append('indie')
        
        # Determine promotion style
        promotion_style = "casual"
        if any(word in bio_lower for word in ['professional', 'business', 'industry']):
            promotion_style = "formal"
        elif any(word in bio_lower for word in ['creative', 'art', 'unique']):
            promotion_style = "creative"
        
        # Response likelihood based on bio completeness
        response_likelihood = min(len(bio) / 200, 1.0) * 0.7
        
        return {
            'mood_tags': mood_tags,
            'promotion_style': promotion_style,
            'response_likelihood': response_likelihood,
            'genre_preferences': self._extract_genres(bio),
            'submission_preferences': self._detect_submission_method(bio),
            'best_approach': f"Use {promotion_style} tone, mention {mood_tags[0] if mood_tags else 'music'} style",
            'confidence': 0.6
        }
    
    def _extract_genres(self, bio: str) -> List[str]:
        """Extract genre mentions from bio"""
        
        genres = ['hip-hop', 'rap', 'trap', 'r&b', 'pop', 'rock', 'indie', 'electronic', 'jazz', 'country']
        found_genres = []
        
        bio_lower = bio.lower()
        for genre in genres:
            if genre in bio_lower:
                found_genres.append(genre)
        
        return found_genres
    
    def _detect_submission_method(self, bio: str) -> str:
        """Detect preferred submission method"""
        
        bio_lower = bio.lower()
        
        if 'email' in bio_lower or '@' in bio:
            return 'email'
        elif 'dm' in bio_lower or 'message' in bio_lower:
            return 'dm'
        elif 'form' in bio_lower or 'submit' in bio_lower:
            return 'form'
        else:
            return 'unknown'

class TextAnalyzer:
    """Advanced text analysis utilities"""
    
    @staticmethod
    def calculate_genre_overlap(curator_genres: List[str], artist_genres: List[str]) -> float:
        """Calculate genre similarity score"""
        
        if not curator_genres or not artist_genres:
            return 0.0
        
        # Direct matches
        direct_matches = len(set(curator_genres) & set(artist_genres))
        
        # Related genre matches (simplified)
        related_genres = {
            'hip-hop': ['rap', 'trap', 'r&b'],
            'rap': ['hip-hop', 'trap'],
            'trap': ['hip-hop', 'rap'],
            'r&b': ['hip-hop', 'soul', 'pop'],
            'electronic': ['edm', 'house', 'techno'],
            'indie': ['alternative', 'rock']
        }
        
        related_matches = 0
        for c_genre in curator_genres:
            for a_genre in artist_genres:
                if c_genre in related_genres.get(a_genre, []):
                    related_matches += 0.5
        
        total_score = (direct_matches + related_matches) / max(len(curator_genres), len(artist_genres))
        return min(total_score, 1.0)
    
    @staticmethod
    def extract_contact_intent(bio: str) -> Dict[str, float]:
        """Extract contact intent signals from bio"""
        
        intent_signals = {
            'open_to_submissions': 0.0,
            'professional_contact': 0.0,
            'active_curator': 0.0,
            'business_focused': 0.0
        }
        
        bio_lower = bio.lower()
        
        # Submission signals
        submission_keywords = ['submit', 'send music', 'demo', 'promo', 'submissions open']
        for keyword in submission_keywords:
            if keyword in bio_lower:
                intent_signals['open_to_submissions'] += 0.3
        
        # Professional signals
        professional_keywords = ['manager', 'agent', 'label', 'industry', 'business']
        for keyword in professional_keywords:
            if keyword in bio_lower:
                intent_signals['professional_contact'] += 0.25
        
        # Active curator signals
        curator_keywords = ['playlist', 'curator', 'music lover', 'discover', 'new music']
        for keyword in curator_keywords:
            if keyword in bio_lower:
                intent_signals['active_curator'] += 0.2
        
        # Business signals
        business_keywords = ['booking', 'press', 'contact', 'inquiries', 'business']
        for keyword in business_keywords:
            if keyword in bio_lower:
                intent_signals['business_focused'] += 0.2
        
        # Normalize scores
        for key in intent_signals:
            intent_signals[key] = min(intent_signals[key], 1.0)
        
        return intent_signals
