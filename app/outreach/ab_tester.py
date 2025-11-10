"""Autonomous A/B testing outreach engine"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
import random
from app.monitoring.logging import log_info

Base = declarative_base()

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    variant = Column(String(1), nullable=False)  # A, B, C
    campaign_type = Column(String(100), nullable=False)
    
    # Performance metrics
    sent_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    replied_count = Column(Integer, default=0)
    
    # Calculated rates
    open_rate = Column(Float, default=0.0)
    click_rate = Column(Float, default=0.0)
    reply_rate = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    confidence_score = Column(Float, default=0.0)

class ABTestCampaign(Base):
    __tablename__ = "ab_test_campaigns"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Test configuration
    template_ids = Column(String(255), nullable=False)  # Comma-separated
    test_size_per_variant = Column(Integer, default=50)
    
    # Status
    status = Column(String(50), default="running")  # running, completed, paused
    winner_template_id = Column(Integer, nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class ABTester:
    """Autonomous A/B testing system"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_template_variants(self, base_template: Dict, campaign_type: str) -> List[int]:
        """Create A/B/C variants of email template"""
        
        variants = self._generate_variants(base_template)
        template_ids = []
        
        for i, variant in enumerate(variants):
            template = EmailTemplate(
                name=f"{base_template['name']}_variant_{chr(65+i)}",
                subject=variant['subject'],
                body=variant['body'],
                variant=chr(65+i),  # A, B, C
                campaign_type=campaign_type
            )
            
            self.db.add(template)
            self.db.flush()
            template_ids.append(template.id)
        
        self.db.commit()
        return template_ids
    
    def _generate_variants(self, base_template: Dict) -> List[Dict]:
        """Generate template variants with different approaches"""
        
        base_subject = base_template['subject']
        base_body = base_template['body']
        
        variants = [
            # Variant A: Original (control)
            {
                'subject': base_subject,
                'body': base_body
            },
            
            # Variant B: More personal/casual
            {
                'subject': self._make_casual(base_subject),
                'body': self._make_casual(base_body)
            },
            
            # Variant C: More professional/direct
            {
                'subject': self._make_professional(base_subject),
                'body': self._make_professional(base_body)
            }
        ]
        
        return variants
    
    def _make_casual(self, text: str) -> str:
        """Make text more casual/personal"""
        
        replacements = {
            'Dear': 'Hey',
            'I am writing to': "I'm reaching out because",
            'Please consider': 'Would love if you could check out',
            'Thank you for your time': 'Thanks so much!',
            'Best regards': 'Cheers',
            'Sincerely': 'Best'
        }
        
        result = text
        for formal, casual in replacements.items():
            result = result.replace(formal, casual)
        
        return result
    
    def _make_professional(self, text: str) -> str:
        """Make text more professional/direct"""
        
        replacements = {
            'Hey': 'Dear',
            "I'm reaching out": 'I am contacting you',
            'Would love': 'I would appreciate',
            'Thanks!': 'Thank you for your consideration',
            'Cheers': 'Best regards'
        }
        
        result = text
        for casual, professional in replacements.items():
            result = result.replace(casual, professional)
        
        return result
    
    def start_ab_test(self, campaign_name: str, template_ids: List[int], 
                     contact_list: List[int], test_size: int = 150) -> int:
        """Start A/B test campaign"""
        
        # Create campaign record
        campaign = ABTestCampaign(
            name=campaign_name,
            template_ids=','.join(map(str, template_ids)),
            test_size_per_variant=test_size // len(template_ids)
        )
        
        self.db.add(campaign)
        self.db.flush()
        
        # Randomly assign contacts to variants
        random.shuffle(contact_list)
        variant_size = len(contact_list) // len(template_ids)
        
        for i, template_id in enumerate(template_ids):
            start_idx = i * variant_size
            end_idx = start_idx + variant_size if i < len(template_ids) - 1 else len(contact_list)
            
            variant_contacts = contact_list[start_idx:end_idx]
            
            # Queue emails for this variant
            self._queue_variant_emails(template_id, variant_contacts, campaign.id)
        
        self.db.commit()
        log_info(f"Started A/B test campaign: {campaign_name}", campaign_id=campaign.id)
        
        return campaign.id
    
    def _queue_variant_emails(self, template_id: int, contact_ids: List[int], campaign_id: int):
        """Queue emails for a specific variant"""
        
        # This would integrate with your email sending system
        # For now, just update the sent count
        template = self.db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if template:
            template.sent_count += len(contact_ids)
            template.last_used = datetime.utcnow()
    
    def record_email_event(self, template_id: int, event_type: str):
        """Record email engagement event (open, click, reply)"""
        
        template = self.db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            return
        
        if event_type == 'open':
            template.opened_count += 1
        elif event_type == 'click':
            template.clicked_count += 1
        elif event_type == 'reply':
            template.replied_count += 1
        
        # Recalculate rates
        if template.sent_count > 0:
            template.open_rate = template.opened_count / template.sent_count
            template.click_rate = template.clicked_count / template.sent_count
            template.reply_rate = template.replied_count / template.sent_count
        
        # Update confidence score
        template.confidence_score = self._calculate_confidence(template)
        
        self.db.commit()
    
    def _calculate_confidence(self, template: EmailTemplate) -> float:
        """Calculate statistical confidence in template performance"""
        
        # Simple confidence based on sample size and performance
        min_sample_size = 30
        
        if template.sent_count < min_sample_size:
            return template.sent_count / min_sample_size * 0.5
        
        # Higher reply rate = higher confidence
        performance_score = (template.reply_rate * 0.6 + 
                           template.open_rate * 0.3 + 
                           template.click_rate * 0.1)
        
        # Sample size factor
        sample_factor = min(template.sent_count / 100, 1.0)
        
        return performance_score * sample_factor
    
    def get_winning_template(self, campaign_id: int) -> Optional[int]:
        """Determine winning template for campaign"""
        
        campaign = self.db.query(ABTestCampaign).filter(ABTestCampaign.id == campaign_id).first()
        if not campaign:
            return None
        
        template_ids = [int(tid) for tid in campaign.template_ids.split(',')]
        templates = self.db.query(EmailTemplate).filter(EmailTemplate.id.in_(template_ids)).all()
        
        # Find template with highest confidence-weighted performance
        best_template = None
        best_score = 0
        
        for template in templates:
            # Weighted score: reply_rate * confidence
            score = template.reply_rate * template.confidence_score
            
            if score > best_score and template.sent_count >= 20:  # Minimum sample
                best_score = score
                best_template = template
        
        if best_template:
            campaign.winner_template_id = best_template.id
            campaign.status = "completed"
            campaign.completed_at = datetime.utcnow()
            self.db.commit()
            
            log_info(f"A/B test winner determined", 
                    campaign_id=campaign_id, 
                    winner_template_id=best_template.id,
                    winner_reply_rate=best_template.reply_rate)
        
        return best_template.id if best_template else None
    
    def get_template_performance(self, days: int = 30) -> List[Dict]:
        """Get template performance analytics"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        templates = self.db.query(EmailTemplate).filter(
            EmailTemplate.last_used >= cutoff_date,
            EmailTemplate.sent_count > 0
        ).order_by(EmailTemplate.reply_rate.desc()).all()
        
        performance_data = []
        for template in templates:
            performance_data.append({
                'template_id': template.id,
                'name': template.name,
                'variant': template.variant,
                'campaign_type': template.campaign_type,
                'sent_count': template.sent_count,
                'open_rate': round(template.open_rate * 100, 2),
                'click_rate': round(template.click_rate * 100, 2),
                'reply_rate': round(template.reply_rate * 100, 2),
                'confidence_score': round(template.confidence_score, 3),
                'last_used': template.last_used.isoformat() if template.last_used else None
            })
        
        return performance_data
