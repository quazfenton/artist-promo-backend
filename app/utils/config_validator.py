"""
Configuration validator for the enhanced pipeline system
"""
import os
import re
from typing import Dict, List, Tuple, Optional
import logging
from urllib.parse import urlparse
import dns.resolver
import redis
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class ConfigValidator:
    """Validate all configuration settings for the pipeline system"""
    
    @staticmethod
    def validate_database_config() -> Tuple[bool, str]:
        """Validate database configuration"""
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            return False, "DATABASE_URL environment variable not set"
        
        try:
            # Parse the URL to check format
            parsed = urlparse(database_url)
            
            if not parsed.scheme or not parsed.netloc:
                return False, f"Invalid DATABASE_URL format: {database_url}"
            
            # Test database connection
            engine = create_engine(database_url, connect_args={"connect_timeout": 10})
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            
            return True, "Database configuration is valid"
            
        except SQLAlchemyError as e:
            return False, f"Database connection failed: {str(e)}"
        except Exception as e:
            return False, f"Database validation error: {str(e)}"
    
    @staticmethod
    def validate_redis_config() -> Tuple[bool, str]:
        """Validate Redis configuration"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            parsed = urlparse(redis_url)
            if not parsed.scheme or parsed.scheme not in ["redis", "rediss"]:
                return False, f"Invalid Redis URL scheme: {parsed.scheme}"
            
            # Test Redis connection
            r = redis.from_url(redis_url, socket_connect_timeout=10)
            r.ping()
            
            return True, "Redis configuration is valid"
            
        except redis.ConnectionError as e:
            return False, f"Redis connection failed: {str(e)}"
        except Exception as e:
            return False, f"Redis validation error: {str(e)}"
    
    @staticmethod
    def validate_jwt_config() -> Tuple[bool, str]:
        """Validate JWT configuration"""
        jwt_secret = os.getenv("JWT_SECRET")
        
        if not jwt_secret:
            return False, "JWT_SECRET environment variable not set"
        
        if len(jwt_secret) < 32:
            return False, "JWT_SECRET should be at least 32 characters long for security"
        
        # Validate token expiration settings
        try:
            access_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
            if access_expire <= 0:
                return False, "ACCESS_TOKEN_EXPIRE_MINUTES must be positive"
        except ValueError:
            return False, "ACCESS_TOKEN_EXPIRE_MINUTES must be a valid integer"
        
        try:
            refresh_expire = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
            if refresh_expire <= 0:
                return False, "REFRESH_TOKEN_EXPIRE_DAYS must be positive"
        except ValueError:
            return False, "REFRESH_TOKEN_EXPIRE_DAYS must be a valid integer"
        
        return True, "JWT configuration is valid"
    
    @staticmethod
    def validate_rate_limit_config() -> Tuple[bool, str]:
        """Validate rate limiting configuration"""
        try:
            rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
            if rate_limit <= 0:
                return False, "RATE_LIMIT_PER_MINUTE must be positive"
        except ValueError:
            return False, "RATE_LIMIT_PER_MINUTE must be a valid integer"
        
        try:
            burst_limit = int(os.getenv("RATE_LIMIT_BURST", "10"))
            if burst_limit <= 0:
                return False, "RATE_LIMIT_BURST must be positive"
        except ValueError:
            return False, "RATE_LIMIT_BURST must be a valid integer"
        
        return True, "Rate limit configuration is valid"
    
    @staticmethod
    def validate_scraper_configs() -> Tuple[bool, str]:
        """Validate scraper-specific configurations"""
        required_configs = [
            "SPOTIFY_CLIENT_ID",
            "SPOTIFY_CLIENT_SECRET",
            "YOUTUBE_API_KEY",
            "INSTAGRAM_USERNAME",
            "INSTAGRAM_PASSWORD"
        ]
        
        missing_configs = []
        for config in required_configs:
            if not os.getenv(config):
                missing_configs.append(config)
        
        if missing_configs:
            logger.warning(f"Missing scraper configurations: {missing_configs}. Some scrapers may not work.")
            return True, f"Missing optional scraper configs: {missing_configs}"
        
        return True, "Scraper configurations are valid"
    
    @staticmethod
    def validate_email_configs() -> Tuple[bool, str]:
        """Validate email-related configurations"""
        email_configs = {
            "SMTP_SERVER": os.getenv("SMTP_SERVER"),
            "SMTP_PORT": os.getenv("SMTP_PORT"),
            "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
            "SENDER_EMAIL": os.getenv("SENDER_EMAIL")
        }
        
        # Check if all required email configs are present
        required_email_configs = ["SMTP_SERVER", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SENDER_EMAIL"]
        missing_email_configs = [config for config in required_email_configs if not email_configs[config]]
        
        if missing_email_configs:
            logger.warning(f"Missing email configurations: {missing_email_configs}. Email features will be disabled.")
            return True, f"Missing optional email configs: {missing_email_configs}"
        
        # Validate SMTP port
        try:
            smtp_port = int(email_configs["SMTP_PORT"])
            if not (1 <= smtp_port <= 65535):
                return False, "SMTP_PORT must be between 1 and 65535"
        except ValueError:
            return False, "SMTP_PORT must be a valid integer"
        
        # Validate email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email_configs["SENDER_EMAIL"]):
            return False, "SENDER_EMAIL must be a valid email address"
        
        return True, "Email configurations are valid"
    
    @staticmethod
    def validate_api_keys() -> Tuple[bool, str]:
        """Validate API keys configuration"""
        api_keys_str = os.getenv("API_KEYS")
        
        if not api_keys_str:
            logger.warning("API_KEYS environment variable not set. API authentication will be disabled.")
            return True, "API authentication disabled (no API keys set)"
        
        api_keys = [key.strip() for key in api_keys_str.split(",") if key.strip()]
        
        if len(api_keys) == 0:
            return True, "API authentication disabled (no valid API keys found)"
        
        # Validate key lengths
        invalid_keys = [key for key in api_keys if len(key) < 16]
        if invalid_keys:
            logger.warning(f"Some API keys are shorter than recommended 16 characters: {invalid_keys[:3]}...")
        
        return True, f"Found {len(api_keys)} API key(s)"
    
    @staticmethod
    def validate_domain_reputation_configs() -> Tuple[bool, str]:
        """Validate domain reputation service configurations"""
        hunter_api_key = os.getenv("HUNTER_API_KEY")
        neverbounce_api_key = os.getenv("NEVERBOUNCE_API_KEY")
        
        services_configured = 0
        if hunter_api_key:
            services_configured += 1
        if neverbounce_api_key:
            services_configured += 1
        
        if services_configured == 0:
            logger.warning("No domain reputation services configured. Email validation will be basic only.")
            return True, "No domain reputation services configured (basic validation only)"
        
        return True, f"Configured {services_configured} domain reputation service(s)"
    
    @staticmethod
    def validate_external_apis() -> Tuple[bool, str]:
        """Validate external API access"""
        validation_results = []
        
        # Validate Spotify API access
        spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
        spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if spotify_client_id and spotify_client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=spotify_client_id,
                    client_secret=spotify_client_secret
                )
                sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                # Test with a simple lookup
                sp.search(q="test", type="track", limit=1)
                validation_results.append("Spotify API: accessible")
            except Exception as e:
                validation_results.append(f"Spotify API: error - {str(e)}")
        else:
            validation_results.append("Spotify API: not configured")
        
        # Validate YouTube API access
        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if youtube_api_key:
            try:
                from googleapiclient.discovery import build
                youtube = build('youtube', 'v3', developerKey=youtube_api_key)
                # Test with a simple search
                youtube.search().list(
                    q="test",
                    part="snippet",
                    type="video",
                    maxResults=1
                ).execute()
                validation_results.append("YouTube API: accessible")
            except Exception as e:
                validation_results.append(f"YouTube API: error - {str(e)}")
        else:
            validation_results.append("YouTube API: not configured")
        
        return True, f"External API validation: {', '.join(validation_results)}"
    
    @staticmethod
    def validate_all_configs() -> Dict[str, Tuple[bool, str]]:
        """Validate all configuration settings"""
        validators = {
            "database": ConfigValidator.validate_database_config,
            "redis": ConfigValidator.validate_redis_config,
            "jwt": ConfigValidator.validate_jwt_config,
            "rate_limit": ConfigValidator.validate_rate_limit_config,
            "scraper": ConfigValidator.validate_scraper_configs,
            "email": ConfigValidator.validate_email_configs,
            "api_keys": ConfigValidator.validate_api_keys,
            "domain_reputation": ConfigValidator.validate_domain_reputation_configs,
            "external_apis": ConfigValidator.validate_external_apis
        }
        
        results = {}
        for name, validator in validators.items():
            try:
                results[name] = validator()
            except Exception as e:
                results[name] = (False, f"Validation error: {str(e)}")
        
        return results
    
    @staticmethod
    def check_config_health() -> Tuple[bool, Dict[str, str]]:
        """Check overall configuration health"""
        validation_results = ConfigValidator.validate_all_configs()
        
        all_valid = all(result[0] for result in validation_results.values())
        
        summary = {}
        for config_name, (is_valid, message) in validation_results.items():
            status = "✓" if is_valid else "✗"
            summary[config_name] = f"{status} {message}"
        
        if all_valid:
            return True, {
                "status": "healthy",
                "message": "All configurations are valid",
                "details": summary
            }
        else:
            # Separate critical and warning issues
            critical_issues = []
            warnings = []
            
            for config_name, (is_valid, message) in validation_results.items():
                if not is_valid and any(keyword in message.lower() for keyword in ["database", "redis", "connection", "invalid"]):
                    critical_issues.append(f"{config_name}: {message}")
                elif not is_valid:
                    critical_issues.append(f"{config_name}: {message}")
                elif "missing" in message.lower() or "not set" in message.lower():
                    warnings.append(f"{config_name}: {message}")
            
            status = "critical" if critical_issues else "warnings"
            message = f"Configuration has {len(critical_issues)} critical issues and {len(warnings)} warnings"
            
            return False, {
                "status": status,
                "message": message,
                "critical_issues": critical_issues,
                "warnings": warnings,
                "details": summary
            }

def validate_startup_config():
    """Validate configuration at application startup"""
    logger.info("Validating application configuration...")
    
    health_ok, health_report = ConfigValidator.check_config_health()
    
    if not health_ok:
        critical_issues = health_report.get("critical_issues", [])
        if critical_issues:
            logger.error("CRITICAL CONFIGURATION ERRORS DETECTED:")
            for issue in critical_issues:
                logger.error(f"  - {issue}")
            logger.error("Application cannot start with critical configuration errors.")
            raise RuntimeError(f"Configuration validation failed: {critical_issues}")
    
    # Log warnings but allow startup
    warnings = health_report.get("warnings", [])
    if warnings:
        logger.warning("CONFIGURATION WARNINGS (non-critical):")
        for warning in warnings:
            logger.warning(f"  - {warning}")
        logger.warning("Application will start but some features may be limited.")
    
    logger.info("Configuration validation completed")
    logger.info(f"Overall status: {health_report['status']}")
    
    return health_ok, health_report

# Example usage
if __name__ == "__main__":
    try:
        is_healthy, report = validate_startup_config()
        print(f"Configuration Health: {report['status']}")
        print(f"Message: {report['message']}")
        
        if report.get('critical_issues'):
            print(f"Critical Issues: {len(report['critical_issues'])}")
            for issue in report['critical_issues']:
                print(f"  - {issue}")
        
        if report.get('warnings'):
            print(f"Warnings: {len(report['warnings'])}")
            for warning in report['warnings']:
                print(f"  - {warning}")
                
    except RuntimeError as e:
        print(f"Startup validation failed: {e}")
        exit(1)