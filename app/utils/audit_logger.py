"""
Audit Logging for Artist Promo Backend.

Provides comprehensive audit logging for:
- Authentication events
- Data access and modifications
- API calls with sensitive data
- Administrative actions
- Security events

Usage:
    from app.utils.audit_logger import audit_log, AuditAction
    
    @audit_log(action=AuditAction.CONTACT_CREATED)
    async def create_contact(...):
        ...
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum
from functools import wraps

from fastapi import Request
from loguru import logger


class AuditAction(str, Enum):
    """Audit action types"""
    # Authentication
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGE = "auth.password.change"
    TOKEN_REFRESH = "auth.token.refresh"
    
    # Contact Operations
    CONTACT_CREATED = "contact.created"
    CONTACT_UPDATED = "contact.updated"
    CONTACT_DELETED = "contact.deleted"
    CONTACT_VIEWED = "contact.viewed"
    CONTACT_EXPORTED = "contact.exported"
    CONTACT_VERIFIED = "contact.verified"
    
    # Playlist Operations
    PLAYLIST_CREATED = "playlist.created"
    PLAYLIST_UPDATED = "playlist.updated"
    PLAYLIST_DELETED = "playlist.deleted"
    
    # Scraping Operations
    SCRAPE_STARTED = "scrape.started"
    SCRAPE_COMPLETED = "scrape.completed"
    SCRAPE_FAILED = "scrape.failed"
    
    # Outreach Operations
    OUTREACH_SENT = "outreach.sent"
    OUTREACH_RESPONSE = "outreach.response"
    
    # Administrative
    USER_CREATED = "admin.user.created"
    USER_DELETED = "admin.user.deleted"
    CONFIG_CHANGED = "admin.config.changed"
    
    # Security Events
    RATE_LIMIT_EXCEEDED = "security.rate_limit"
    CSRF_FAILURE = "security.csrf.failure"
    INVALID_API_KEY = "security.api_key.invalid"
    SUSPICIOUS_ACTIVITY = "security.suspicious"


class AuditLogger:
    """
    Comprehensive audit logger with structured logging.
    
    Features:
    - Structured JSON logging for SIEM integration
    - Correlation IDs for request tracing
    - User context tracking
    - Sensitive data masking
    - Configurable log levels
    """
    
    def __init__(self, log_file: str = None, log_level: str = "INFO"):
        self.log_file = log_file or os.getenv("AUDIT_LOG_FILE", "logs/audit.log")
        self.log_level = log_level or os.getenv("AUDIT_LOG_LEVEL", "INFO")
        
        # Ensure log directory exists
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Configure audit logger
        self.audit_logger = logging.getLogger("artist_promo.audit")
        self.audit_logger.setLevel(getattr(logging, self.log_level))
        
        # Remove existing handlers
        self.audit_logger.handlers = []
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(self._create_formatter())
        self.audit_logger.addHandler(file_handler)
        
        # Add console handler for development
        if os.getenv("ENVIRONMENT", "production") == "development":
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(self._create_formatter())
            self.audit_logger.addHandler(console_handler)
    
    def _create_formatter(self) -> logging.Formatter:
        """Create JSON formatter for structured logging"""
        return logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def log(
        self,
        action: AuditAction,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
        success: bool = True
    ):
        """
        Log an audit event.
        
        Args:
            action: Audit action type
            user_id: User ID if authenticated
            user_email: User email if authenticated
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            details: Additional details (will be JSON encoded)
            ip_address: Client IP address
            user_agent: Client user agent
            correlation_id: Request correlation ID
            success: Whether the action was successful
        """
        # Mask sensitive data
        if details:
            details = self._mask_sensitive_data(details)
        
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action.value,
            "user": {
                "id": user_id,
                "email": self._mask_email(user_email) if user_email else None
            },
            "resource": {
                "type": resource_type,
                "id": resource_id
            },
            "context": {
                "ip_address": ip_address,
                "user_agent": user_agent,
                "correlation_id": correlation_id
            },
            "details": details,
            "success": success
        }
        
        # Log at appropriate level
        log_func = self.audit_logger.info if success else self.audit_logger.warning
        
        if not success and action in [
            AuditAction.LOGIN_FAILURE,
            AuditAction.CSRF_FAILURE,
            AuditAction.SUSPICIOUS_ACTIVITY
        ]:
            log_func = self.audit_logger.error
        
        log_func(json.dumps(log_entry))
    
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in audit logs"""
        sensitive_fields = {
            'password', 'token', 'secret', 'api_key', 'apikey',
            'authorization', 'access_token', 'refresh_token'
        }
        
        masked = {}
        for key, value in data.items():
            if key.lower() in sensitive_fields:
                masked[key] = "***REDACTED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            elif isinstance(value, str) and any(s in key.lower() for s in ['email', 'phone']):
                masked[key] = self._mask_value(value)
            else:
                masked[key] = value
        
        return masked
    
    def _mask_email(self, email: Optional[str]) -> Optional[str]:
        """Mask email for privacy"""
        if not email:
            return None
        
        parts = email.split('@')
        if len(parts) != 2:
            return "***REDACTED***"
        
        username = parts[0]
        domain = parts[1]
        
        # Show first 2 and last 2 characters of username
        if len(username) > 4:
            masked_username = f"{username[:2]}***{username[-2:]}"
        else:
            masked_username = "***"
        
        return f"{masked_username}@{domain}"
    
    def _mask_value(self, value: str) -> str:
        """Mask a sensitive value"""
        if not value:
            return "***REDACTED***"
        
        if len(value) > 10:
            return f"{value[:3]}***{value[-3:]}"
        return "***REDACTED***"


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_log(action: AuditAction, resource_type: str = None):
    """
    Decorator for audit logging of endpoints.
    
    Usage:
        @app.post("/contacts")
        @audit_log(action=AuditAction.CONTACT_CREATED, resource_type="contact")
        async def create_contact(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from arguments
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Get user info from kwargs if available
            user_id = kwargs.get('user_id')
            user_email = kwargs.get('user_email')
            
            # Get correlation ID
            correlation_id = None
            if request:
                correlation_id = request.headers.get('X-Correlation-ID')
                client_ip = request.client.host if request.client else None
                user_agent = request.headers.get('user-agent', '')
            else:
                client_ip = None
                user_agent = None
            
            audit = get_audit_logger()
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Log success
                resource_id = None
                if isinstance(result, dict) and 'id' in result:
                    resource_id = result.get('id')
                
                audit.log(
                    action=action,
                    user_id=user_id,
                    user_email=user_email,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    correlation_id=correlation_id,
                    success=True
                )
                
                return result
                
            except Exception as e:
                # Log failure
                audit.log(
                    action=action,
                    user_id=user_id,
                    user_email=user_email,
                    resource_type=resource_type,
                    details={"error": str(e)},
                    ip_address=client_ip,
                    user_agent=user_agent,
                    correlation_id=correlation_id,
                    success=False
                )
                raise
        
        return wrapper
    return decorator


def log_auth_event(
    action: AuditAction,
    user_email: str,
    success: bool,
    ip_address: str = None,
    details: Dict = None
):
    """Log authentication event"""
    audit = get_audit_logger()
    audit.log(
        action=action,
        user_email=user_email,
        success=success,
        ip_address=ip_address,
        details=details
    )


def log_security_event(
    action: AuditAction,
    ip_address: str,
    details: Dict = None,
    user_agent: str = None
):
    """Log security event"""
    audit = get_audit_logger()
    audit.log(
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        success=False
    )
