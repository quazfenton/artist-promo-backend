"""
Configuration Validation for Artist Promo Backend.

Validates all configuration at startup to fail fast on misconfiguration.

Usage:
    from app.utils.config_validator import validate_config
    
    validate_config()  # Call at startup
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from loguru import logger


class ConfigValidationError(Exception):
    """Configuration validation error"""
    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.value = value
        logger.error(f"Configuration error | field={field} | value={value[:50] if value else None}... | message={message}")


class ConfigValidator:
    """
    Comprehensive configuration validator.
    
    Validates:
    - Required environment variables
    - Database configuration
    - Security settings
    - API keys
    - Rate limiting parameters
    - Feature flags
    """
    
    REQUIRED_VARS = [
        'DATABASE_URL',
        'SECRET_KEY',
    ]
    
    OPTIONAL_VARS = [
        'REDIS_URL',
        'JWT_SECRET',
        'SPOTIFY_CLIENT_ID',
        'SPOTIFY_CLIENT_SECRET',
        'YOUTUBE_API_KEY',
        'INSTAGRAM_USERNAME',
        'INSTAGRAM_PASSWORD',
        'HUNTER_API_KEY',
        'NEVERBOUNCE_API_KEY',
        'OPENAI_API_KEY',
        'SENTRY_DSN',
    ]
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> bool:
        """
        Run all validations.
        
        Returns:
            True if all critical validations pass
            
        Raises:
            ConfigValidationError: If critical validation fails
        """
        logger.info("Starting configuration validation...")
        
        # Validate required variables
        self._validate_required_vars()
        
        # Validate security configuration
        self._validate_security_config()
        
        # Validate database configuration
        self._validate_database_config()
        
        # Validate API keys
        self._validate_api_keys()
        
        # Validate rate limiting
        self._validate_rate_limiting()
        
        # Validate feature flags
        self._validate_feature_flags()
        
        # Log results
        if self.errors:
            logger.error(f"Configuration validation failed with {len(self.errors)} error(s)")
            for error in self.errors:
                logger.error(f"  - {error}")
            raise ConfigValidationError(
                f"Configuration validation failed: {', '.join(self.errors[:3])}",
                "configuration",
                "multiple fields"
            )
        
        if self.warnings:
            logger.warning(f"Configuration has {len(self.warnings)} warning(s)")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        logger.info("Configuration validation passed")
        return True
    
    def _validate_required_vars(self):
        """Validate required environment variables"""
        for var in self.REQUIRED_VARS:
            value = os.getenv(var)
            if not value:
                self.errors.append(f"Required environment variable {var} is not set")
            elif value.startswith("changeme") or value == "your-secret-key":
                self.errors.append(f"Environment variable {var} has default/placeholder value")
    
    def _validate_security_config(self):
        """Validate security configuration"""
        # Validate SECRET_KEY
        secret_key = os.getenv("SECRET_KEY")
        if secret_key:
            if len(secret_key) < 32:
                self.errors.append("SECRET_KEY must be at least 32 characters")
            if secret_key in ["mysecretkey", "testsecret", "development"]:
                self.warnings.append("SECRET_KEY appears to be weak")
        
        # Validate JWT_SECRET
        jwt_secret = os.getenv("JWT_SECRET")
        if jwt_secret and len(jwt_secret) < 32:
            self.errors.append("JWT_SECRET must be at least 32 characters")
        
        # Validate JWT expiration
        try:
            access_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
            if access_expire < 5 or access_expire > 1440:
                self.warnings.append("ACCESS_TOKEN_EXPIRE_MINUTES should be between 5 and 1440")
        except ValueError:
            self.errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer")
        
        # Validate allowed origins
        allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
        if allowed_origins:
            origins = [o.strip() for o in allowed_origins.split(",")]
            for origin in origins:
                if origin == "*":
                    self.warnings.append("CORS allowed_origins is set to '*' - this is insecure for production")
                elif not origin.startswith(("http://", "https://")):
                    self.errors.append(f"Invalid CORS origin: {origin} (must start with http:// or https://)")
    
    def _validate_database_config(self):
        """Validate database configuration"""
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Check for SQLite in production
            if database_url.startswith("sqlite") and os.getenv("ENVIRONMENT") == "production":
                self.warnings.append("SQLite is not recommended for production use")
            
            # Validate PostgreSQL URL format
            if database_url.startswith("postgresql"):
                if not re.match(r'^postgresql://[^:]+:[^@]+@[^/]+/.+', database_url):
                    self.warnings.append("PostgreSQL URL format may be incorrect")
        
        # Validate pool size
        try:
            pool_size = int(os.getenv("DATABASE_POOL_SIZE", "5"))
            if pool_size < 1 or pool_size > 100:
                self.warnings.append("DATABASE_POOL_SIZE should be between 1 and 100")
        except ValueError:
            self.errors.append("DATABASE_POOL_SIZE must be an integer")
    
    def _validate_api_keys(self):
        """Validate API keys format"""
        # Spotify credentials
        spotify_id = os.getenv("SPOTIFY_CLIENT_ID")
        spotify_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if (spotify_id and not spotify_secret) or (spotify_secret and not spotify_id):
            self.warnings.append("Both SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET should be set")
        
        # YouTube API key
        youtube_key = os.getenv("YOUTUBE_API_KEY")
        if youtube_key and not youtube_key.startswith("AIza"):
            self.warnings.append("YOUTUBE_API_KEY format appears incorrect (should start with 'AIza')")
        
        # Hunter API key
        hunter_key = os.getenv("HUNTER_API_KEY")
        if hunter_key and len(hunter_key) < 10:
            self.warnings.append("HUNTER_API_KEY appears too short")
        
        # OpenAI API key
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and not openai_key.startswith("sk-"):
            self.warnings.append("OPENAI_API_KEY format appears incorrect (should start with 'sk-')")
    
    def _validate_rate_limiting(self):
        """Validate rate limiting configuration"""
        try:
            rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
            if rate_limit < 1 or rate_limit > 1000:
                self.warnings.append("RATE_LIMIT_PER_MINUTE should be between 1 and 1000")
        except ValueError:
            self.errors.append("RATE_LIMIT_PER_MINUTE must be an integer")
        
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url and not redis_url.startswith("redis://"):
                self.warnings.append("REDIS_URL format may be incorrect")
        except Exception:
            pass
    
    def _validate_feature_flags(self):
        """Validate feature flags"""
        boolean_flags = [
            'ENABLE_RATE_LIMITING',
            'ENABLE_AUDIT_LOGGING',
            'ENABLE_EMAIL_VERIFICATION',
            'DEBUG',
        ]
        
        for flag in boolean_flags:
            value = os.getenv(flag)
            if value and value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                self.warnings.append(f"{flag} should be 'true' or 'false', got: {value}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        return {
            "valid": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


# Import datetime for summary
from datetime import datetime


# Global validator instance
_validator: Optional[ConfigValidator] = None


def get_validator() -> ConfigValidator:
    """Get or create validator instance"""
    global _validator
    if _validator is None:
        _validator = ConfigValidator()
    return _validator


def validate_config() -> bool:
    """
    Validate configuration at startup.
    
    Returns:
        True if validation passes
        
    Raises:
        ConfigValidationError: If validation fails
    """
    validator = get_validator()
    return validator.validate_all()


def get_config_summary() -> Dict[str, Any]:
    """Get configuration validation summary"""
    validator = get_validator()
    return validator.get_summary()


def check_database_url() -> str:
    """
    Validate and return database URL.
    
    Returns:
        Database URL if valid
        
    Raises:
        ConfigValidationError: If database URL is invalid
    """
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        raise ConfigValidationError(
            "DATABASE_URL environment variable is required",
            "DATABASE_URL"
        )
    
    # Validate format
    if database_url.startswith("postgresql"):
        if "@" not in database_url:
            raise ConfigValidationError(
                "DATABASE_URL must include credentials (user:password@host)",
                "DATABASE_URL",
                database_url[:50]
            )
    
    return database_url


def check_secret_key() -> str:
    """
    Validate and return secret key.
    
    Returns:
        Secret key if valid
        
    Raises:
        ConfigValidationError: If secret key is invalid
    """
    secret_key = os.getenv("SECRET_KEY")
    
    if not secret_key:
        raise ConfigValidationError(
            "SECRET_KEY environment variable is required",
            "SECRET_KEY"
        )
    
    if len(secret_key) < 32:
        raise ConfigValidationError(
            "SECRET_KEY must be at least 32 characters long",
            "SECRET_KEY",
            f"{len(secret_key)} characters"
        )
    
    return secret_key
