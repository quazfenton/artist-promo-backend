"""Configuration validation for the artist promotion backend"""
import os
import logging
from typing import List, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ConfigValidator:
    """Validate application configuration at startup"""
    
    @staticmethod
    def validate_database_url() -> Tuple[bool, str]:
        """Validate DATABASE_URL configuration"""
        db_url = os.getenv("DATABASE_URL", "")
        
        if not db_url:
            return False, "DATABASE_URL environment variable is not set"
        
        try:
            parsed = urlparse(db_url)
            if not parsed.scheme or not parsed.netloc:
                return False, f"Invalid DATABASE_URL format: {db_url}"
            
            # Check for required components based on database type
            if parsed.scheme.startswith('postgres'):
                if not parsed.username or not parsed.password:
                    logger.warning("PostgreSQL URL should include username and password")
            elif parsed.scheme == 'sqlite':
                # SQLite doesn't need username/password
                pass
            else:
                logger.warning(f"Unrecognized database scheme: {parsed.scheme}")
            
            return True, "Database URL is valid"
        except Exception as e:
            return False, f"Error parsing DATABASE_URL: {str(e)}"
    
    @staticmethod
    def validate_jwt_config() -> Tuple[bool, str]:
        """Validate JWT configuration"""
        jwt_secret = os.getenv("JWT_SECRET", "")
        
        if not jwt_secret or jwt_secret == "your-secret-key-change-in-production":
            return False, "JWT_SECRET is not properly configured"
        
        if len(jwt_secret) < 32:
            logger.warning("JWT_SECRET is shorter than recommended 32 characters")
        
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
    def validate_redis_config() -> Tuple[bool, str]:
        """Validate Redis configuration"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            parsed = urlparse(redis_url)
            if not parsed.scheme or parsed.scheme not in ['redis', 'rediss']:
                return False, f"Invalid Redis URL scheme: {parsed.scheme}"
            
            return True, "Redis configuration is valid"
        except Exception as e:
            return False, f"Error parsing REDIS_URL: {str(e)}"
    
    @staticmethod
    def validate_api_keys() -> Tuple[bool, str]:
        """Validate API key configuration"""
        api_keys_str = os.getenv("API_KEYS", "")
        
        if not api_keys_str:
            logger.warning("No API keys configured - n8n webhook authentication will fail")
            return True, "No API keys configured (warning only)"
        
        api_keys = [key.strip() for key in api_keys_str.split(",") if key.strip()]
        
        for key in api_keys:
            if len(key) < 16:
                logger.warning(f"API key {key[:8]}... is shorter than recommended 16 characters")
        
        return True, f"Found {len(api_keys)} API key(s)"
    
    @staticmethod
    def validate_rate_limits() -> Tuple[bool, str]:
        """Validate rate limiting configuration"""
        try:
            rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
            if rate_limit <= 0:
                return False, "RATE_LIMIT_PER_MINUTE must be positive"
        except ValueError:
            return False, "RATE_LIMIT_PER_MINUTE must be a valid integer"
        
        return True, "Rate limit configuration is valid"
    
    @staticmethod
    def validate_required_env_vars() -> List[Tuple[str, bool, str]]:
        """Validate all required environment variables"""
        results = []
        
        # Check if running in test mode
        if os.getenv("TESTING"):
            logger.info("Skipping configuration validation in test mode")
            return results
        
        checks = [
            ("DATABASE_URL", ConfigValidator.validate_database_url),
            ("JWT_SECRET", ConfigValidator.validate_jwt_config),
            ("REDIS_URL", ConfigValidator.validate_redis_config),
            ("API_KEYS", ConfigValidator.validate_api_keys),
            ("RATE_LIMIT_PER_MINUTE", ConfigValidator.validate_rate_limits),
        ]
        
        for var_name, check_func in checks:
            is_valid, message = check_func()
            results.append((var_name, is_valid, message))
            
            if not is_valid:
                logger.error(f"Configuration error for {var_name}: {message}")
            else:
                logger.info(f"Configuration OK for {var_name}: {message}")
        
        return results
    
    @classmethod
    def validate_all(cls) -> bool:
        """Validate all configuration and return True if all valid"""
        results = cls.validate_required_env_vars()
        
        all_valid = all(result[1] for result in results)
        
        if not all_valid:
            invalid_vars = [result[0] for result in results if not result[1]]
            logger.error(f"Configuration validation failed for: {', '.join(invalid_vars)}")
            return False
        
        logger.info("All configuration validation passed")
        return True

def validate_startup_config():
    """Validate configuration at application startup"""
    logger.info("Validating application configuration...")
    
    if not ConfigValidator.validate_all():
        raise RuntimeError("Configuration validation failed - please check the logs above")
    
    logger.info("Application configuration validation completed successfully")

if __name__ == "__main__":
    # Test the validator
    validate_startup_config()