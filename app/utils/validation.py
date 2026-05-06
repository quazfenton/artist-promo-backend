"""
Input Validation Utilities for Artist Promo Backend.

Provides validation for:
- Email addresses
- URLs
- Social media handles
- Search queries
- Platform IDs
- Contact information

Usage:
    from app.utils.validation import validate_email, validate_url
"""

import re
from typing import Optional, List, Tuple
from datetime import datetime

from loguru import logger


# Validation patterns
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)
URL_PATTERN = re.compile(
    r'^https?://'
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
    r'localhost|'
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    r'(?::\d+)?'
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)
SPOTIFY_ID_PATTERN = re.compile(r'^[a-zA-Z0-9]{22}$')
YOUTUBE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{11}$')
INSTAGRAM_HANDLE_PATTERN = re.compile(r'^[a-zA-Z0-9._]{1,30}$')
TWITTER_HANDLE_PATTERN = re.compile(r'^[a-zA-Z0-9_]{1,15}$')
SEARCH_QUERY_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,]{1,200}$')


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.value = value
        logger.warning(f"Validation error | field={field} | value={value[:50] if value else None}... | message={message}")


def validate_email(email: str, field_name: str = "email") -> str:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated email address
        
    Raises:
        ValidationError: If email format is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, email)
    
    email = email.strip().lower()
    
    if len(email) > 254:
        raise ValidationError(f"{field_name} must be 254 characters or less", field_name, email)
    
    if not EMAIL_PATTERN.match(email):
        raise ValidationError(f"{field_name} is not a valid email address", field_name, email)
    
    # Check for disposable email domains
    disposable_domains = {
        'tempmail.com', 'throwaway.com', 'guerrillamail.com',
        'mailinator.com', '10minutemail.com'
    }
    domain = email.split('@')[1]
    if domain in disposable_domains:
        logger.warning(f"Disposable email detected: {email}")
        # Don't reject, just log
    
    return email


def validate_url(url: str, field_name: str = "url") -> str:
    """
    Validate URL format and scheme.
    
    Args:
        url: URL to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated URL
        
    Raises:
        ValidationError: If URL format is invalid or scheme is dangerous
    """
    if not url or not isinstance(url, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, url)
    
    url = url.strip()
    
    if len(url) > 2048:
        raise ValidationError(f"{field_name} must be 2048 characters or less", field_name, url)
    
    # Check for dangerous schemes
    dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:']
    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            raise ValidationError(
                f"{field_name} uses dangerous scheme",
                field_name,
                url[:100]
            )
    
    if not URL_PATTERN.match(url):
        raise ValidationError(f"{field_name} is not a valid URL", field_name, url)
    
    return url


def validate_spotify_id(spotify_id: str, field_name: str = "spotify_id") -> str:
    """
    Validate Spotify ID format (22 alphanumeric characters).
    
    Args:
        spotify_id: Spotify ID to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated Spotify ID
        
    Raises:
        ValidationError: If ID format is invalid
    """
    if not spotify_id or not isinstance(spotify_id, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, spotify_id)
    
    spotify_id = spotify_id.strip()
    
    if not SPOTIFY_ID_PATTERN.match(spotify_id):
        raise ValidationError(
            f"{field_name} must be 22 alphanumeric characters",
            field_name,
            spotify_id
        )
    
    return spotify_id


def validate_youtube_id(youtube_id: str, field_name: str = "youtube_id") -> str:
    """
    Validate YouTube video/channel ID format.
    
    Args:
        youtube_id: YouTube ID to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated YouTube ID
        
    Raises:
        ValidationError: If ID format is invalid
    """
    if not youtube_id or not isinstance(youtube_id, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, youtube_id)
    
    youtube_id = youtube_id.strip()
    
    if not YOUTUBE_ID_PATTERN.match(youtube_id):
        raise ValidationError(
            f"{field_name} must be 11 characters (letters, numbers, underscore, hyphen)",
            field_name,
            youtube_id
        )
    
    return youtube_id


def validate_instagram_handle(handle: str, field_name: str = "instagram_handle") -> str:
    """
    Validate Instagram handle format.
    
    Args:
        handle: Instagram handle to validate (with or without @)
        field_name: Name of field for error messages
        
    Returns:
        Validated handle (without @)
        
    Raises:
        ValidationError: If handle format is invalid
    """
    if not handle or not isinstance(handle, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, handle)
    
    # Remove @ if present
    handle = handle.strip().lstrip('@')
    
    if not INSTAGRAM_HANDLE_PATTERN.match(handle):
        raise ValidationError(
            f"{field_name} must be 1-30 characters (letters, numbers, dots, underscores)",
            field_name,
            handle
        )
    
    return handle


def validate_twitter_handle(handle: str, field_name: str = "twitter_handle") -> str:
    """
    Validate Twitter handle format.
    
    Args:
        handle: Twitter handle to validate (with or without @)
        field_name: Name of field for error messages
        
    Returns:
        Validated handle (without @)
        
    Raises:
        ValidationError: If handle format is invalid
    """
    if not handle or not isinstance(handle, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, handle)
    
    # Remove @ if present
    handle = handle.strip().lstrip('@')
    
    if not TWITTER_HANDLE_PATTERN.match(handle):
        raise ValidationError(
            f"{field_name} must be 1-15 characters (letters, numbers, underscores)",
            field_name,
            handle
        )
    
    return handle


def validate_search_query(query: str, field_name: str = "query") -> str:
    """
    Validate and sanitize search query.
    
    Args:
        query: Search query to validate
        field_name: Name of field for error messages
        
    Returns:
        Sanitized search query
        
    Raises:
        ValidationError: If query is invalid or contains dangerous patterns
    """
    if not query or not isinstance(query, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, query)
    
    query = query.strip()
    
    if len(query) > 200:
        raise ValidationError(f"{field_name} must be 200 characters or less", field_name, query)
    
    if not SEARCH_QUERY_PATTERN.match(query):
        raise ValidationError(
            f"{field_name} contains invalid characters",
            field_name,
            query[:100]
        )
    
    # Check for SQL injection patterns
    sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', '--', ';']
    query_upper = query.upper()
    for pattern in sql_patterns:
        if pattern in query_upper:
            logger.warning(f"Potential SQL injection in search query: {query}")
            raise ValidationError(
                f"{field_name} contains invalid pattern",
                field_name,
                query
            )
    
    return query


def validate_follower_count(count: int, field_name: str = "follower_count", 
                           min_value: int = 0, max_value: int = 100000000) -> int:
    """
    Validate follower count is within reasonable range.
    
    Args:
        count: Follower count to validate
        field_name: Name of field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Validated follower count
        
    Raises:
        ValidationError: If count is outside valid range
    """
    try:
        count = int(count)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be an integer", field_name, str(count))
    
    if count < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}",
            field_name,
            str(count)
        )
    
    if count > max_value:
        raise ValidationError(
            f"{field_name} must be at most {max_value}",
            field_name,
            str(count)
        )
    
    return count


def validate_priority_score(score: float, field_name: str = "priority_score") -> float:
    """
    Validate priority score is between 0 and 100.
    
    Args:
        score: Priority score to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated priority score
        
    Raises:
        ValidationError: If score is outside valid range
    """
    try:
        score = float(score)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a number", field_name, str(score))
    
    if score < 0 or score > 100:
        raise ValidationError(
            f"{field_name} must be between 0 and 100",
            field_name,
            str(score)
        )
    
    return score


def validate_contact_type(contact_type: str, field_name: str = "contact_type") -> str:
    """
    Validate contact type is allowed.
    
    Args:
        contact_type: Contact type to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated contact type
        
    Raises:
        ValidationError: If contact type is not allowed
    """
    allowed_types = {
        'playlist_curator', 'publicist', 'manager', 'ar_rep',
        'venue_booker', 'journalist', 'influencer', 'label'
    }
    
    if not contact_type or not isinstance(contact_type, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, contact_type)
    
    contact_type = contact_type.strip().lower()
    
    if contact_type not in allowed_types:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(allowed_types)}",
            field_name,
            contact_type
        )
    
    return contact_type


def validate_platform(platform: str, field_name: str = "platform") -> str:
    """
    Validate platform name is allowed.
    
    Args:
        platform: Platform name to validate
        field_name: Name of field for error messages
        
    Returns:
        Validated platform name
        
    Raises:
        ValidationError: If platform is not allowed
    """
    allowed_platforms = {
        'spotify', 'apple_music', 'youtube', 'soundcloud',
        'instagram', 'twitter', 'linkedin', 'tiktok', 'website'
    }
    
    if not platform or not isinstance(platform, str):
        raise ValidationError(f"{field_name} must be a non-empty string", field_name, platform)
    
    platform = platform.strip().lower()
    
    if platform not in allowed_platforms:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(allowed_platforms)}",
            field_name,
            platform
        )
    
    return platform


def sanitize_html(text: str, max_length: int = 1000) -> str:
    """
    Sanitize HTML/text input to prevent XSS.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return ""
    
    text = text.strip()
    
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove potentially dangerous HTML tags
    dangerous_tags = ['<script', '<iframe', '<object', '<embed', '<form']
    text_lower = text.lower()
    for tag in dangerous_tags:
        if tag in text_lower:
            logger.warning(f"Dangerous HTML tag detected in input")
            text = re.sub(f'(?i){tag}.*?{tag.replace("<", "</")}>', '', text)
    
    # Remove event handlers
    event_handlers = ['onclick', 'onerror', 'onload', 'onmouseover', 'onfocus']
    for handler in event_handlers:
        text = re.sub(f'\\s*{handler}\\s*=\\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    
    return text


def validate_batch_ids(ids: List[str], field_name: str = "ids", 
                       max_count: int = 100) -> List[str]:
    """
    Validate batch of IDs for bulk operations.
    
    Args:
        ids: List of IDs to validate
        field_name: Name of field for error messages
        max_count: Maximum number of IDs allowed
        
    Returns:
        Validated list of IDs
        
    Raises:
        ValidationError: If batch is invalid
    """
    if not ids or not isinstance(ids, list):
        raise ValidationError(f"{field_name} must be a non-empty list", field_name, str(ids))
    
    if len(ids) > max_count:
        raise ValidationError(
            f"{field_name} must contain at most {max_count} items",
            field_name,
            f"list with {len(ids)} items"
        )
    
    # Validate each ID is a positive integer
    validated_ids = []
    for id_value in ids:
        try:
            id_int = int(id_value)
            if id_int <= 0:
                raise ValidationError(
                    f"{field_name} must contain positive integers",
                    field_name,
                    str(id_value)
                )
            validated_ids.append(id_int)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{field_name} must contain valid integers",
                field_name,
                str(id_value)
            )
    
    return validated_ids
