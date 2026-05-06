"""
Email Outreach Automation

Automates email outreach to curators, labels, and artists with:
- Personalized email templates
- A/B testing support
- Follow-up scheduling
- Response tracking
- Unsubscribe handling
- SMTP integration
"""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from loguru import logger
from app.models.database import SessionLocal, Contact
from app.models.staging import StagingContact
from sqlalchemy import select


class EmailStatus(str, Enum):
    """Email delivery status"""
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    REPLIED = "replied"


@dataclass
class EmailTemplate:
    """Email template with personalization"""
    name: str
    subject: str
    body: str
    variables: List[str] = field(default_factory=list)
    ab_variant: str = "A"  # A or B for A/B testing
    
    def render(self, variables: Dict[str, str]) -> str:
        """Render template with variables"""
        rendered_subject = self.subject
        rendered_body = self.body
        
        for key, value in variables.items():
            rendered_subject = rendered_subject.replace(f"{{{{{key}}}}}", value)
            rendered_body = rendered_body.replace(f"{{{{{key}}}}}", value)
        
        return rendered_subject, rendered_body


@dataclass
class EmailCampaign:
    """Email outreach campaign"""
    id: str
    name: str
    template: EmailTemplate
    recipients: List[str]
    status: EmailStatus = EmailStatus.DRAFT
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    stats: Dict[str, int] = field(default_factory=dict)


class EmailOutreachAutomation:
    """
    Automated email outreach system
    
    Features:
    - SMTP integration
    - Template personalization
    - A/B testing
    - Follow-up scheduling
    - Response tracking
    - Unsubscribe handling
    """
    
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: str = "Artist Promo"
    ):
        """
        Initialize email outreach automation
        
        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_email: Sender email address
            from_name: Sender name
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email or os.getenv("SMTP_FROM_EMAIL")
        self.from_name = from_name
        
        self.templates: Dict[str, EmailTemplate] = {}
        self.campaigns: Dict[str, EmailCampaign] = {}
        
        self._load_default_templates()
        logger.info("Email outreach automation initialized")
    
    def _load_default_templates(self):
        """Load default email templates"""
        
        # Template 1: Initial Outreach
        self.templates["initial_outreach"] = EmailTemplate(
            name="Initial Outreach",
            subject="Loving your playlist: {{playlist_name}}",
            body="""Hi {{curator_name}},

I hope this email finds you well!

My name is {{artist_name}}, and I've been following your playlist "{{playlist_name}}" for a while now. I absolutely love the curation - especially tracks like {{sample_track}}.

I'm reaching out because I just released a new track that I think would fit perfectly with the vibe of your playlist. It's a {{genre}} track with influences from {{influences}}.

Here's the link to check it out:
{{track_link}}

If you like it and think it would work for your playlist, I'd be incredibly grateful for the support. If not, no worries at all - I'll continue enjoying your playlist as a fan!

Thanks so much for your time and for supporting independent artists.

Best regards,
{{artist_name}}
{{artist_contact}}

---
To unsubscribe from future emails, click here: {{unsubscribe_link}}
""",
            variables=[
                "curator_name", "playlist_name", "artist_name", 
                "sample_track", "genre", "influences", "track_link",
                "artist_contact", "unsubscribe_link"
            ]
        )
        
        # Template 2: Follow-up
        self.templates["follow_up"] = EmailTemplate(
            name="Follow-up",
            subject="Re: {{playlist_name}} - Quick follow-up",
            body="""Hi {{curator_name}},

Just wanted to quickly follow up on my previous email about my track "{{track_name}}".

I know you probably get tons of submissions, so I'll keep this brief. I genuinely believe this track would resonate with your audience based on the amazing curation you've done with "{{playlist_name}}".

If you have a moment to give it a listen, here's the link again:
{{track_link}}

Either way, keep up the great work with the playlist!

Cheers,
{{artist_name}}

---
To unsubscribe: {{unsubscribe_link}}
""",
            variables=[
                "curator_name", "playlist_name", "track_name", "track_link",
                "artist_name", "unsubscribe_link"
            ]
        )
        
        # Template 3: Thank You
        self.templates["thank_you"] = EmailTemplate(
            name="Thank You",
            subject="Thank you for the support! 🙏",
            body="""Hi {{curator_name}},

I just noticed that you added "{{track_name}}" to "{{playlist_name}}" - thank you so much!

Your support means the world to independent artists like me. Playlists like yours are what help us reach new listeners and grow our audience.

If there's anything I can do to support your playlist in return (sharing, promoting, etc.), please don't hesitate to let me know.

Thanks again, and keep up the amazing curation work!

Best,
{{artist_name}}
""",
            variables=[
                "curator_name", "track_name", "playlist_name", "artist_name"
            ]
        )
        
        logger.info(f"Loaded {len(self.templates)} default email templates")
    
    def create_campaign(
        self,
        name: str,
        template_name: str,
        recipients: List[str],
        scheduled_at: Optional[datetime] = None
    ) -> EmailCampaign:
        """
        Create email campaign
        
        Args:
            name: Campaign name
            template_name: Template to use
            recipients: List of recipient emails
            scheduled_at: When to send (None = immediately)
            
        Returns:
            Created campaign
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        campaign = EmailCampaign(
            id=f"campaign_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name=name,
            template=self.templates[template_name],
            recipients=recipients,
            scheduled_at=scheduled_at,
            status=EmailStatus.DRAFT if scheduled_at else EmailStatus.QUEUED,
            stats={
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "bounced": 0,
                "replied": 0,
                "unsubscribed": 0,
            }
        )
        
        self.campaigns[campaign.id] = campaign
        logger.info(f"Created campaign: {name} ({len(recipients)} recipients)")
        
        return campaign
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        variables: Optional[Dict[str, str]] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send single email
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body (HTML supported)
            variables: Template variables
            attachments: List of file paths to attach
            
        Returns:
            True if sent successfully
        """
        if not self.smtp_user or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            
            # Add plain text and HTML versions
            msg.attach(MIMEText(body, "html"))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    try:
                        with open(file_path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={os.path.basename(file_path)}"
                            )
                            msg.attach(part)
                    except Exception as e:
                        logger.warning(f"Failed to attach {file_path}: {e}")
            
            # Send email
            async with asyncio.Lock():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._send_email_sync,
                    to_email,
                    msg
                )
            
            logger.info(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def _send_email_sync(self, to_email: str, msg: MIMEMultipart):
        """Synchronous email sending (for executor)"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
    
    async def send_campaign(self, campaign_id: str) -> Dict[str, int]:
        """
        Send email campaign
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Campaign statistics
        """
        if campaign_id not in self.campaigns:
            raise ValueError(f"Campaign '{campaign_id}' not found")
        
        campaign = self.campaigns[campaign_id]
        campaign.status = EmailStatus.SENT
        campaign.sent_at = datetime.utcnow()
        
        stats = {
            "sent": 0,
            "failed": 0,
        }
        
        for recipient in campaign.recipients:
            # Get contact data for personalization
            contact_data = await self._get_contact_data(recipient)
            
            # Render template
            variables = contact_data or {}
            variables["unsubscribe_link"] = f"{os.getenv('APP_URL')}/unsubscribe?email={recipient}"
            
            subject, body = campaign.template.render(variables)
            
            # Send email
            success = await self.send_email(
                to_email=recipient,
                subject=subject,
                body=body,
                variables=variables
            )
            
            if success:
                stats["sent"] += 1
                campaign.stats["sent"] += 1
            else:
                stats["failed"] += 1
                campaign.stats["bounced"] += 1
            
            # Rate limiting - wait between emails
            await asyncio.sleep(1)
        
        logger.info(f"Campaign {campaign.name} completed: {stats}")
        return stats
    
    async def _get_contact_data(self, email: str) -> Optional[Dict[str, str]]:
        """Get contact data from database for personalization"""
        try:
            db = SessionLocal()
            
            # Try to find contact by email
            contact = db.query(Contact).filter(Contact.email == email).first()
            
            if contact:
                return {
                    "curator_name": contact.name.split()[0] if contact.name else "there",
                    "playlist_name": contact.metadata.get("playlist_name", "your playlist") if contact.metadata else "your playlist",
                    "artist_name": os.getenv("ARTIST_NAME", "Artist"),
                    "genre": os.getenv("ARTIST_GENRE", "music"),
                    "track_link": os.getenv("TRACK_LINK", "#"),
                    "artist_contact": os.getenv("ARTIST_EMAIL", ""),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get contact data: {e}")
            return None
        finally:
            db.close()
    
    async def schedule_follow_up(
        self,
        campaign_id: str,
        days_after: int = 7,
        template_name: str = "follow_up"
    ):
        """
        Schedule follow-up campaign
        
        Args:
            campaign_id: Original campaign ID
            days_after: Days after original campaign
            template_name: Template to use for follow-up
        """
        if campaign_id not in self.campaigns:
            raise ValueError(f"Campaign '{campaign_id}' not found")
        
        original = self.campaigns[campaign_id]
        scheduled_date = (original.sent_at or datetime.utcnow()) + timedelta(days=days_after)
        
        follow_up = self.create_campaign(
            name=f"{original.name} - Follow-up",
            template_name=template_name,
            recipients=original.recipients,
            scheduled_at=scheduled_date
        )
        
        logger.info(f"Scheduled follow-up campaign for {scheduled_date}")
        return follow_up.id
    
    def track_response(
        self,
        campaign_id: str,
        email: str,
        action: str,
        metadata: Optional[Dict] = None
    ):
        """
        Track email response
        
        Args:
            campaign_id: Campaign ID
            email: Recipient email
            action: Action type (opened, clicked, replied, unsubscribed)
            metadata: Additional metadata
        """
        if campaign_id not in self.campaigns:
            return
        
        campaign = self.campaigns[campaign_id]
        
        if action == "opened":
            campaign.stats["opened"] += 1
        elif action == "clicked":
            campaign.stats["clicked"] += 1
        elif action == "replied":
            campaign.stats["replied"] += 1
        elif action == "unsubscribed":
            campaign.stats["unsubscribed"] += 1
        elif action == "bounced":
            campaign.stats["bounced"] += 1
        
        logger.info(f"Tracked {action} for {email} in campaign {campaign_id}")
    
    def get_campaign_stats(self, campaign_id: str) -> Optional[Dict]:
        """Get campaign statistics"""
        if campaign_id not in self.campaigns:
            return None
        
        campaign = self.campaigns[campaign_id]
        
        return {
            "name": campaign.name,
            "status": campaign.status.value,
            "recipients": len(campaign.recipients),
            "sent": campaign.stats.get("sent", 0),
            "opened": campaign.stats.get("opened", 0),
            "clicked": campaign.stats.get("clicked", 0),
            "replied": campaign.stats.get("replied", 0),
            "bounced": campaign.stats.get("bounced", 0),
            "unsubscribed": campaign.stats.get("unsubscribed", 0),
            "open_rate": f"{(campaign.stats.get('opened', 0) / len(campaign.recipients) * 100):.1f}%" if campaign.recipients else "0%",
            "reply_rate": f"{(campaign.stats.get('replied', 0) / len(campaign.recipients) * 100):.1f}%" if campaign.recipients else "0%",
        }


# Global instance
_email_automation: Optional[EmailOutreachAutomation] = None


def get_email_automation() -> EmailOutreachAutomation:
    """Get or create email automation instance"""
    global _email_automation
    if _email_automation is None:
        _email_automation = EmailOutreachAutomation(
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            from_email=os.getenv("SMTP_FROM_EMAIL"),
            from_name=os.getenv("SMTP_FROM_NAME", "Artist Promo")
        )
    return _email_automation
