"""Machine learning contact scoring system"""
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.database import Contact, OutreachLog
from datetime import datetime, timedelta
import os

class MLContactScorer:
    """Machine learning-based contact scoring"""
    
    def __init__(self, db: Session):
        self.db = db
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'follower_count', 'engagement_rate', 'days_since_last_active',
            'bio_length', 'has_email', 'is_verified', 'platform_score',
            'genre_match_score', 'semantic_confidence', 'response_likelihood'
        ]
        self.model_path = 'models/contact_scorer.pkl'
        self.scaler_path = 'models/contact_scaler.pkl'
    
    def prepare_training_data(self) -> pd.DataFrame:
        """Prepare training data from historical outreach results"""
        
        # Get contacts with outreach history
        query = """
        SELECT 
            c.id,
            c.follower_count,
            c.engagement_rate,
            EXTRACT(DAYS FROM (NOW() - c.last_active_at)) as days_since_last_active,
            LENGTH(c.bio) as bio_length,
            CASE WHEN c.email IS NOT NULL THEN 1 ELSE 0 END as has_email,
            CASE WHEN c.verified THEN 1 ELSE 0 END as is_verified,
            c.priority_score as platform_score,
            COALESCE(c.semantic_tags->>'genre_match_score', '0')::float as genre_match_score,
            COALESCE(c.semantic_tags->>'confidence', '0.5')::float as semantic_confidence,
            COALESCE(c.semantic_tags->>'response_likelihood', '0.5')::float as response_likelihood,
            -- Target variable: success rate
            CASE 
                WHEN COUNT(ol.id) > 0 THEN 
                    COUNT(CASE WHEN ol.status = 'replied' THEN 1 END)::float / COUNT(ol.id)
                ELSE 0 
            END as success_rate
        FROM contacts c
        LEFT JOIN outreach_logs ol ON c.id = ol.contact_id
        WHERE c.deleted_at IS NULL
        GROUP BY c.id
        HAVING COUNT(ol.id) >= 3  -- Minimum outreach attempts for reliable data
        """
        
        df = pd.read_sql(query, self.db.bind)
        
        # Fill missing values
        df = df.fillna({
            'days_since_last_active': 30,
            'bio_length': 0,
            'engagement_rate': 0.02,
            'genre_match_score': 0.5,
            'semantic_confidence': 0.5,
            'response_likelihood': 0.5
        })
        
        return df
    
    def train_model(self) -> Dict:
        """Train the ML scoring model"""
        
        # Prepare data
        df = self.prepare_training_data()
        
        if len(df) < 50:  # Minimum samples needed
            return {'error': 'Insufficient training data', 'samples': len(df)}
        
        # Features and target
        X = df[self.feature_columns]
        y = df['success_rate']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        # Feature importance
        feature_importance = dict(zip(
            self.feature_columns,
            self.model.feature_importances_
        ))
        
        # Save model
        os.makedirs('models', exist_ok=True)
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        
        return {
            'status': 'success',
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'train_r2': round(train_score, 3),
            'test_r2': round(test_score, 3),
            'feature_importance': {k: round(v, 3) for k, v in feature_importance.items()}
        }
    
    def load_model(self) -> bool:
        """Load trained model from disk"""
        
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                return True
        except Exception:
            pass
        
        return False
    
    def predict_success_score(self, contact_features: Dict) -> float:
        """Predict success score for a contact"""
        
        if not self.model:
            if not self.load_model():
                # Fallback to rule-based scoring
                return self._fallback_scoring(contact_features)
        
        try:
            # Prepare features
            feature_vector = []
            for col in self.feature_columns:
                value = contact_features.get(col, 0)
                
                # Handle special cases
                if col == 'days_since_last_active' and value is None:
                    value = 30
                elif col in ['semantic_confidence', 'response_likelihood'] and value is None:
                    value = 0.5
                
                feature_vector.append(float(value))
            
            # Scale and predict
            X = np.array(feature_vector).reshape(1, -1)
            X_scaled = self.scaler.transform(X)
            
            prediction = self.model.predict(X_scaled)[0]
            
            # Convert to 0-100 scale and clamp
            score = max(0, min(100, prediction * 100))
            
            return score
            
        except Exception:
            return self._fallback_scoring(contact_features)
    
    def _fallback_scoring(self, features: Dict) -> float:
        """Fallback rule-based scoring when ML model unavailable"""
        
        score = 50.0  # Base score
        
        # Follower count factor
        followers = features.get('follower_count', 0)
        if followers > 10000:
            score += 15
        elif followers > 1000:
            score += 10
        elif followers > 100:
            score += 5
        
        # Engagement rate
        engagement = features.get('engagement_rate', 0)
        score += min(engagement * 500, 20)  # Max 20 points
        
        # Email availability
        if features.get('has_email', 0):
            score += 10
        
        # Verification status
        if features.get('is_verified', 0):
            score += 5
        
        # Semantic factors
        response_likelihood = features.get('response_likelihood', 0.5)
        score += response_likelihood * 20
        
        return max(0, min(100, score))
    
    def batch_rescore_contacts(self, contact_ids: Optional[List[int]] = None) -> Dict:
        """Rescore contacts using ML model"""
        
        if contact_ids:
            contacts = self.db.query(Contact).filter(
                Contact.id.in_(contact_ids),
                Contact.deleted_at.is_(None)
            ).all()
        else:
            contacts = self.db.query(Contact).filter(
                Contact.deleted_at.is_(None)
            ).all()
        
        updated_count = 0
        
        for contact in contacts:
            # Prepare features
            features = self._extract_contact_features(contact)
            
            # Predict new score
            new_score = self.predict_success_score(features)
            
            # Update if significantly different
            if abs(contact.priority_score - new_score) > 5:
                contact.priority_score = new_score
                updated_count += 1
        
        self.db.commit()
        
        return {
            'status': 'success',
            'total_contacts': len(contacts),
            'updated_count': updated_count
        }
    
    def _extract_contact_features(self, contact: Contact) -> Dict:
        """Extract features from contact record"""
        
        # Calculate days since last active
        days_since_active = 30  # Default
        if contact.last_active_at:
            days_since_active = (datetime.utcnow() - contact.last_active_at).days
        
        # Parse semantic tags
        semantic_tags = contact.semantic_tags or {}
        
        return {
            'follower_count': contact.follower_count or 0,
            'engagement_rate': contact.engagement_rate or 0.02,
            'days_since_last_active': days_since_active,
            'bio_length': len(contact.bio or ''),
            'has_email': 1 if contact.email else 0,
            'is_verified': 1 if contact.verified else 0,
            'platform_score': contact.priority_score or 50,
            'genre_match_score': semantic_tags.get('genre_match_score', 0.5),
            'semantic_confidence': semantic_tags.get('confidence', 0.5),
            'response_likelihood': semantic_tags.get('response_likelihood', 0.5)
        }
    
    def get_model_insights(self) -> Dict:
        """Get insights about the current model"""
        
        if not self.model:
            return {'error': 'No model loaded'}
        
        # Feature importance
        importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        
        # Model metadata
        return {
            'model_type': 'RandomForestRegressor',
            'n_estimators': self.model.n_estimators,
            'feature_importance': {k: round(v, 3) for k, v in importance.items()},
            'top_features': sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5],
            'model_file': self.model_path,
            'last_trained': datetime.fromtimestamp(os.path.getmtime(self.model_path)).isoformat() if os.path.exists(self.model_path) else None
        }
