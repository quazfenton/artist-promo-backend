"""
Outreach templates and message generation
"""
from typing import Dict, Any

def generate_outreach_message(contact: Dict[str, Any], cluster_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate personalized outreach message based on contact and cluster context
    """
    strategy = outreach_strategy(cluster_context)
    
    if strategy == "portfolio":
        return template_portfolio(contact, cluster_context)
    elif strategy == "network":
        return template_network(contact, cluster_context)
    else:
        return template_single(contact, cluster_context)

def outreach_strategy(cluster_context: Dict[str, Any]) -> str:
    """
    Select outreach strategy based on cluster characteristics
    """
    artist_count = cluster_context.get("artist_count", 0)
    
    if artist_count >= 5:
        return "portfolio"
    elif artist_count >= 2:
        return "network"
    else:
        return "single_artist"

def template_portfolio(contact: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
    """Template for portfolio managers (represent many artists)"""
    subject = f"Music Collaboration Opportunity"
    
    body = f"""
Hi {contact.get('name', 'there')},

I came across your roster while researching artists in this lane.

I've been following work around similar artists and noticed a consistent sound and rollout approach across your artists.

I'm working with an emerging artist who's gaining traction and would love to share a short private link if you're open to new music.

No mass pitch — just one track and context.

Best,
[Your Name]
"""
    
    return {"subject": subject, "body": body}

def template_network(contact: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
    """Template for network managers (2-4 artists)"""
    subject = f"Music Opportunity - {contact.get('name', 'Contact')}"
    
    body = f"""
Hey {contact.get('name', 'there')},

I found your work through artists like [similar artists].

I'm helping an artist with a similar audience profile and wanted to ask if you're open to hearing new material.

Happy to send a private link or EPK if useful.

Thanks for your time,
[Your Name]
"""
    
    return {"subject": subject, "body": body}

def template_single(contact: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
    """Template for single-artist or low-confidence contact"""
    subject = f"Inquiry - {contact.get('name', 'Contact')}"
    
    body = f"""
Hi {contact.get('name', 'there')},

I came across this contact while researching representation in this space.

Quick check before sending anything over — is this the right place for music submissions?

Thanks,
[Your Name]
"""
    
    return {"subject": subject, "body": body}