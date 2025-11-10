"""Advanced intelligence and optimization API"""
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.enrichment.semantic_profile import SemanticProfiler, TextAnalyzer
from app.outreach.ab_tester import ABTester
from app.analytics.network_builder import CuratorNetworkBuilder
from app.integrations.audio_features import AudioFeatureAnalyzer
from app.ml.scoring_model import MLContactScorer

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

class SemanticAnalysisRequest(BaseModel):
    contact_ids: List[int]
    include_audio_analysis: bool = False

class ABTestRequest(BaseModel):
    campaign_name: str
    base_template: Dict[str, str]  # {'name': '', 'subject': '', 'body': ''}
    contact_ids: List[int]
    test_size: int = 150

class AudioMatchingRequest(BaseModel):
    artist_track_ids: List[str]
    playlist_ids: Optional[List[str]] = None
    top_k: int = 20

class MLScoringRequest(BaseModel):
    contact_ids: Optional[List[int]] = None
    retrain_model: bool = False

@router.post("/semantic-analysis")
async def run_semantic_analysis(
    request: Request,
    analysis_request: SemanticAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Run AI-powered semantic analysis on contacts"""
    
    profiler = SemanticProfiler()
    analyzer = TextAnalyzer()
    
    results = []
    
    # Get contacts
    from app.models.database import Contact
    contacts = db.query(Contact).filter(
        Contact.id.in_(analysis_request.contact_ids),
        Contact.deleted_at.is_(None)
    ).all()
    
    for contact in contacts:
        # Get playlist names if available
        playlist_names = []
        if contact.playlists:
            playlist_names = [p.name for p in contact.playlists[:5]]
        
        # Run semantic analysis
        semantic_profile = await profiler.analyze_curator_profile(
            contact.bio or "", playlist_names
        )
        
        # Calculate genre overlap if artist genres provided
        artist_genres = ["hip-hop", "rap"]  # Could be from request
        genre_overlap = analyzer.calculate_genre_overlap(
            semantic_profile.get('genre_preferences', []),
            artist_genres
        )
        
        # Extract contact intent
        intent_signals = analyzer.extract_contact_intent(contact.bio or "")
        
        # Update contact with semantic data
        contact.semantic_tags = {
            **semantic_profile,
            'genre_match_score': genre_overlap,
            'intent_signals': intent_signals,
            'analyzed_at': datetime.utcnow().isoformat()
        }
        
        results.append({
            'contact_id': contact.id,
            'semantic_profile': semantic_profile,
            'genre_overlap': genre_overlap,
            'intent_signals': intent_signals
        })
    
    db.commit()
    
    return {
        'status': 'completed',
        'analyzed_contacts': len(results),
        'results': results
    }

@router.post("/ab-test")
async def create_ab_test(
    request: Request,
    ab_request: ABTestRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create and launch A/B test campaign"""
    
    tester = ABTester(db)
    
    # Create template variants
    template_ids = tester.create_template_variants(
        ab_request.base_template,
        "outreach_campaign"
    )
    
    # Start A/B test
    campaign_id = tester.start_ab_test(
        ab_request.campaign_name,
        template_ids,
        ab_request.contact_ids,
        ab_request.test_size
    )
    
    return {
        'status': 'launched',
        'campaign_id': campaign_id,
        'template_variants': len(template_ids),
        'test_contacts': len(ab_request.contact_ids),
        'message': f'A/B test "{ab_request.campaign_name}" launched with {len(template_ids)} variants'
    }

@router.get("/ab-test/{campaign_id}/results")
async def get_ab_test_results(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get A/B test results and winner"""
    
    tester = ABTester(db)
    
    # Get winner
    winner_template_id = tester.get_winning_template(campaign_id)
    
    # Get performance data
    performance_data = tester.get_template_performance(30)
    
    return {
        'campaign_id': campaign_id,
        'winner_template_id': winner_template_id,
        'performance_data': performance_data,
        'status': 'completed' if winner_template_id else 'running'
    }

@router.post("/network-analysis")
async def analyze_curator_network(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Analyze curator relationship networks"""
    
    builder = CuratorNetworkBuilder(db)
    network_data = builder.build_curator_network()
    
    return {
        'status': 'completed',
        'network_analysis': network_data,
        'insights': {
            'total_curators': network_data['nodes'],
            'total_connections': network_data['edges'],
            'network_density': network_data['metrics']['density'],
            'top_influencers': network_data['top_influencers'][:5]
        }
    }

@router.post("/audio-matching")
async def find_audio_matches(
    request: Request,
    matching_request: AudioMatchingRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Find playlists with similar audio characteristics"""
    
    analyzer = AudioFeatureAnalyzer()
    
    # Create artist audio profile
    artist_profile = analyzer.create_artist_audio_profile(
        matching_request.artist_track_ids
    )
    
    if not artist_profile:
        return {'error': 'Could not analyze artist audio features'}
    
    # Get playlist profiles
    from app.models.database import Playlist
    
    if matching_request.playlist_ids:
        playlists = db.query(Playlist).filter(
            Playlist.platform_id.in_(matching_request.playlist_ids),
            Playlist.deleted_at.is_(None)
        ).all()
    else:
        playlists = db.query(Playlist).filter(
            Playlist.deleted_at.is_(None),
            Playlist.follower_count > 1000
        ).limit(200).all()
    
    # Analyze playlist audio profiles (simplified - would cache these)
    playlist_profiles = []
    for playlist in playlists[:50]:  # Limit for demo
        try:
            audio_profile = await analyzer.analyze_playlist_audio_profile(playlist.platform_id)
            if audio_profile:
                playlist_profiles.append({
                    'id': playlist.id,
                    'name': playlist.name,
                    'follower_count': playlist.follower_count,
                    'curator_name': playlist.curator.full_name if playlist.curator else None,
                    'audio_profile': audio_profile
                })
        except Exception:
            continue
    
    # Find similar playlists
    similar_playlists = analyzer.find_similar_playlists(
        artist_profile, 
        playlist_profiles,
        matching_request.top_k
    )
    
    return {
        'status': 'completed',
        'artist_profile': artist_profile,
        'analyzed_playlists': len(playlist_profiles),
        'similar_playlists': similar_playlists,
        'avg_similarity': sum(p['similarity_score'] for p in similar_playlists) / len(similar_playlists) if similar_playlists else 0
    }

@router.post("/ml-scoring")
async def ml_contact_scoring(
    request: Request,
    scoring_request: MLScoringRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Machine learning contact scoring and optimization"""
    
    scorer = MLContactScorer(db)
    
    # Retrain model if requested
    if scoring_request.retrain_model:
        training_result = scorer.train_model()
        
        if 'error' in training_result:
            return {
                'status': 'error',
                'message': training_result['error'],
                'samples': training_result.get('samples', 0)
            }
    
    # Rescore contacts
    rescoring_result = scorer.batch_rescore_contacts(scoring_request.contact_ids)
    
    # Get model insights
    model_insights = scorer.get_model_insights()
    
    return {
        'status': 'completed',
        'rescoring_result': rescoring_result,
        'model_insights': model_insights,
        'retrained': scoring_request.retrain_model
    }

@router.get("/optimization-suggestions")
async def get_optimization_suggestions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get AI-powered optimization suggestions"""
    
    # Analyze current performance
    from app.models.database import Contact, OutreachLog
    
    # Get recent performance metrics
    total_contacts = db.query(Contact).filter(Contact.deleted_at.is_(None)).count()
    
    recent_outreach = db.query(OutreachLog).filter(
        OutreachLog.sent_at >= datetime.utcnow() - timedelta(days=30)
    ).all()
    
    if recent_outreach:
        reply_rate = len([o for o in recent_outreach if o.status == 'replied']) / len(recent_outreach)
        open_rate = len([o for o in recent_outreach if o.status in ['opened', 'replied']]) / len(recent_outreach)
    else:
        reply_rate = 0
        open_rate = 0
    
    # Generate suggestions
    suggestions = []
    
    if reply_rate < 0.05:
        suggestions.append({
            'type': 'low_reply_rate',
            'priority': 'high',
            'suggestion': 'Consider running A/B tests on email templates to improve reply rates',
            'action': 'Create A/B test campaign with more personalized templates'
        })
    
    if open_rate < 0.20:
        suggestions.append({
            'type': 'low_open_rate',
            'priority': 'medium',
            'suggestion': 'Improve email subject lines and sender reputation',
            'action': 'Test different subject line styles and verify email deliverability'
        })
    
    # Check for contacts needing semantic analysis
    unanalyzed_contacts = db.query(Contact).filter(
        Contact.deleted_at.is_(None),
        Contact.semantic_tags.is_(None)
    ).count()
    
    if unanalyzed_contacts > 100:
        suggestions.append({
            'type': 'missing_semantic_analysis',
            'priority': 'medium',
            'suggestion': f'{unanalyzed_contacts} contacts lack semantic analysis',
            'action': 'Run semantic analysis to improve targeting accuracy'
        })
    
    return {
        'current_metrics': {
            'total_contacts': total_contacts,
            'recent_outreach_count': len(recent_outreach),
            'reply_rate': round(reply_rate * 100, 2),
            'open_rate': round(open_rate * 100, 2)
        },
        'suggestions': suggestions,
        'optimization_score': min(100, (reply_rate * 500) + (open_rate * 200))  # Simple score
    }

from datetime import datetime, timedelta
