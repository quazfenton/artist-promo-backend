"""
Email canonicalization and domain reputation system
"""
import re
from collections import defaultdict
from time import time
from datetime import datetime, timedelta
from typing import Dict, List, Set
import dns.resolver

# Domain-level send limits to avoid burning domains
SEND_LIMITS = defaultdict(list)
DOMAIN_COOLDOWNS = {}

def canonicalize_email(email: str) -> str:
    """
    Normalize email aliases like press@, booking@, mgmt@ to a canonical form
    """
    if not email or '@' not in email:
        return email
    
    local, domain = email.lower().split('@', 1)
    
    # Common aliases that indicate the same type of contact
    aliases = {"press", "booking", "mgmt", "management", "contact", "info", "hello", "admin", "support"}
    
    if local in aliases:
        local = "official"
    elif local.startswith(('press-', 'booking-', 'mgmt-', 'contact-')):
        # Handle prefixes like press-artist@domain.com
        local = "official"
    
    return f"{local}@{domain}"

def can_send_to_domain(domain: str, max_per_day: int = 3) -> bool:
    """
    Check if we can send to a domain based on daily limits
    """
    now = time()
    # Clean old entries (older than 24 hours)
    SEND_LIMITS[domain] = [t for t in SEND_LIMITS[domain] if now - t < 86400]
    
    return len(SEND_LIMITS[domain]) < max_per_day

def log_domain_send(domain: str):
    """
    Log that we sent an email to a domain
    """
    SEND_LIMITS[domain].append(time())

def check_email_domain_reputation(email: str) -> Dict[str, any]:
    """
    Check domain reputation and role account status
    """
    if '@' not in email:
        return {"valid": False, "error": "Invalid email format"}
    
    local, domain = email.split('@', 1)
    
    # Check if it's a role account
    role_prefixes = {"info", "contact", "hello", "admin", "support", "press", "booking", "noreply"}
    is_role_account = local.lower() in role_prefixes
    
    # Check MX records
    has_mx = False
    try:
        import dns.resolver
        mx_records = dns.resolver.resolve(domain, 'MX')
        has_mx = len(mx_records) > 0
    except ImportError:
        # dns module not available
        has_mx = True  # Assume valid if we can't check
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        has_mx = False
    except Exception:
        # Other DNS errors
        has_mx = False
    
    # Check if domain is on any blocklists (simplified)
    is_blocked = False
    
    return {
        "has_mx": has_mx,
        "role_account": is_role_account,
        "is_blocked": is_blocked,
        "domain": domain
    }

def is_domain_on_cooldown(domain: str, cooldown_hours: int = 24) -> bool:
    """
    Check if domain is on cooldown
    """
    if domain not in DOMAIN_COOLDOWNS:
        return False
    
    cooldown_until = DOMAIN_COOLDOWNS[domain]
    return datetime.utcnow() < cooldown_until

def set_domain_cooldown(domain: str, hours: int = 24):
    """
    Set a domain on cooldown
    """
    cooldown_until = datetime.utcnow() + timedelta(hours=hours)
    DOMAIN_COOLDOWNS[domain] = cooldown_until

def get_domain_send_stats(domain: str) -> Dict[str, any]:
    """
    Get statistics for a domain
    """
    now = time()
    # Clean old entries
    SEND_LIMITS[domain] = [t for t in SEND_LIMITS[domain] if now - t < 86400]
    
    return {
        "sends_today": len(SEND_LIMITS[domain]),
        "max_daily": 3,  # Default
        "remaining_today": max(0, 3 - len(SEND_LIMITS[domain])),
        "cooldown_until": DOMAIN_COOLDOWNS.get(domain)
    }

# Email validation helpers
def is_role_account(email: str) -> bool:
    """
    Check if email is a role account
    """
    if '@' not in email:
        return False
    
    local, _ = email.split('@', 1)
    role_prefixes = {"info", "contact", "hello", "admin", "support", "press", "booking", "noreply"}
    return local.lower() in role_prefixes

def extract_domain(email: str) -> str:
    """
    Extract domain from email
    """
    if '@' not in email:
        return ""
    return email.split('@')[1].lower()

def is_business_email(email: str) -> bool:
    """
    Check if email is from a business domain (not consumer)
    """
    if '@' not in email:
        return False
    
    domain = extract_domain(email)
    consumer_domains = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
        'icloud.com', 'me.com', 'live.com', 'msn.com', 'ymail.com',
        'rocketmail.com', 'att.net', 'comcast.net', 'verizon.net'
    }
    
    return domain not in consumer_domains

def get_email_type(email: str) -> str:
    """
    Categorize email type
    """
    if is_role_account(email):
        return "role"
    elif is_business_email(email):
        return "business"
    else:
        return "consumer"