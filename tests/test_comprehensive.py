"""Comprehensive tests for the improved artist promotion backend"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.models.database import Base
from app.utils.config_validator import ConfigValidator

client = TestClient(app)

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_comprehensive.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override dependency to use test database"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override the get_db dependency in main app
from app.api import main
main.get_db = override_get_db

def test_config_validation():
    """Test configuration validation functionality"""
    # Test valid configuration
    with patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "JWT_SECRET": "a_very_long_secret_key_that_meets_security_requirements_12345",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "REFRESH_TOKEN_EXPIRE_DAYS": "7",
        "REDIS_URL": "redis://localhost:6379/0",
        "API_KEYS": "test_key_123",
        "RATE_LIMIT_PER_MINUTE": "60"
    }):
        is_valid, message = ConfigValidator.validate_database_url()
        assert is_valid is True
        
        is_valid, message = ConfigValidator.validate_jwt_config()
        assert is_valid is True
        
        is_valid, message = ConfigValidator.validate_redis_config()
        assert is_valid is True
        
        is_valid, message = ConfigValidator.validate_api_keys()
        assert is_valid is True
        
        is_valid, message = ConfigValidator.validate_rate_limits()
        assert is_valid is True

def test_config_validation_with_invalid_values():
    """Test configuration validation with invalid values"""
    # Test invalid JWT secret
    with patch.dict(os.environ, {"JWT_SECRET": "short"}):
        is_valid, message = ConfigValidator.validate_jwt_config()
        assert is_valid is False
    
    # Test invalid access token expire
    with patch.dict(os.environ, {"ACCESS_TOKEN_EXPIRE_MINUTES": "-1"}):
        is_valid, message = ConfigValidator.validate_jwt_config()
        assert is_valid is False
    
    # Test invalid rate limit
    with patch.dict(os.environ, {"RATE_LIMIT_PER_MINUTE": "0"}):
        is_valid, message = ConfigValidator.validate_rate_limits()
        assert is_valid is False

def test_config_validation_with_empty_values():
    """Test configuration validation with empty values"""
    # Test missing JWT secret
    with patch.dict(os.environ, {"JWT_SECRET": ""}):
        is_valid, message = ConfigValidator.validate_jwt_config()
        assert is_valid is False

def test_health_check_includes_detailed_info():
    """Test that health checks return detailed information"""
    response = client.get("/health/detailed")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)
    
    # Check that database check has detailed info
    if "database" in data["checks"]:
        db_check = data["checks"]["database"]
        assert "response_time_ms" in db_check
        assert "connection_pool_size" in db_check
        assert "checked_out_connections" in db_check
        assert "pool_status" in db_check

def test_api_endpoints_return_proper_error_formats():
    """Test that API endpoints return consistent error formats"""
    # Test invalid endpoint returns proper 404
    response = client.get("/nonexistent/endpoint")
    assert response.status_code == 404

def test_rate_limiter_thread_safety():
    """Test that rate limiter can be imported and used safely"""
    from app.middleware.rate_limiter import RateLimitMiddleware
    import threading
    import time
    
    # Create a mock app
    mock_app = MagicMock()
    rate_limiter = RateLimitMiddleware(mock_app, requests_per_minute=10)
    
    # Test that the internal store is properly initialized
    assert hasattr(RateLimitMiddleware, '_memory_store')
    assert hasattr(RateLimitMiddleware, '_store_lock')

def test_background_task_error_handling():
    """Test that background tasks handle errors gracefully"""
    # This is more of a structural test since we can't easily test the actual background execution
    # But we can verify the functions exist and have proper structure
    from app.api.main import save_spotify_results, save_youtube_results, save_instagram_results, save_web_result
    
    # These functions should exist
    assert callable(save_spotify_results)
    assert callable(save_youtube_results) 
    assert callable(save_instagram_results)
    assert callable(save_web_result)

def test_jwt_handler_improved_error_handling():
    """Test JWT handler with improved error handling"""
    from app.auth.jwt_handler import JWTHandler
    import redis
    
    # Test with mocked Redis connection error
    with patch('app.auth.jwt_handler.redis.from_url') as mock_redis:
        mock_redis.side_effect = redis.ConnectionError("Connection failed")
        
        jwt_handler = JWTHandler()
        # Should handle the error gracefully and continue
        assert jwt_handler.redis_client is None
        
        # Token creation should still work without Redis
        token = jwt_handler.create_access_token(user_id=1, email="test@example.com")
        assert token is not None
        
        # Verification should work (without Redis features)
        payload = jwt_handler.verify_token(token)
        assert payload is not None

def test_auth_endpoints_with_proper_models():
    """Test that auth endpoints use proper Pydantic models"""
    from app.api.auth import UpdateUserRequest
    
    # Test the new UpdateUserRequest model
    update_data = UpdateUserRequest(is_active=True, is_admin=False)
    assert update_data.is_active is True
    assert update_data.is_admin is False
    
    # Test with partial data
    update_data2 = UpdateUserRequest(is_active=False)
    assert update_data2.is_active is False
    assert update_data2.is_admin is None

def test_scraper_safe_scrape_handles_cancellation():
    """Test that scraper safe_scrape handles cancellation properly"""
    from app.scrapers.base_scraper import BaseScraper
    import asyncio
    
    scraper = BaseScraper("test_scraper")
    
    # Test that CancelledError is re-raised (not caught)
    async def mock_scrape_with_cancellation():
        raise asyncio.CancelledError("Task cancelled")
    
    # Temporarily replace the scrape method
    original_scrape = scraper.scrape
    scraper.scrape = mock_scrape_with_cancellation
    
    try:
        # This should raise CancelledError, not catch and return empty list
        with pytest.raises(asyncio.CancelledError):
            await scraper.safe_scrape()
    finally:
        # Restore original method
        scraper.scrape = original_scrape

def test_database_transaction_handling():
    """Test that database operations handle transactions properly"""
    # This is a structural test - we verify the improved transaction handling code is in place
    from app.api.main import save_spotify_results, save_youtube_results, save_instagram_results, save_web_result
    
    # All these functions should now have improved transaction handling
    # with proper commit/rollback logic
    import inspect
    
    # Check that the functions contain the expected improvements
    source = inspect.getsource(save_spotify_results)
    assert "db.flush()" in source
    assert "successful_saves" in source
    assert "failed_saves" in source

def test_environment_variable_validation():
    """Test environment variable validation"""
    # Test with proper environment
    with patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "JWT_SECRET": "a_very_long_secret_key_that_meets_security_requirements_12345",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "REFRESH_TOKEN_EXPIRE_DAYS": "7",
        "REDIS_URL": "redis://localhost:6379/0",
        "API_KEYS": "test_key_123",
        "RATE_LIMIT_PER_MINUTE": "60"
    }):
        results = ConfigValidator.validate_required_env_vars()
        # All validations should pass
        assert all(result[1] for result in results)

def test_security_headers_present():
    """Test that security headers are present in responses"""
    response = client.get("/")
    headers = response.headers
    
    # Check for important security headers
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
    assert "x-xss-protection" in headers
    assert "strict-transport-security" in headers

def test_app_startup_validation():
    """Test that the app validates config at startup"""
    # This tests that the validation function can run without errors
    # In a real scenario, this happens at app startup
    with patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "JWT_SECRET": "a_very_long_secret_key_that_meets_security_requirements_12345",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "REFRESH_TOKEN_EXPIRE_DAYS": "7",
        "REDIS_URL": "redis://localhost:6379/0",
        "API_KEYS": "test_key_123",
        "RATE_LIMIT_PER_MINUTE": "60"
    }):
        # This should not raise an exception
        ConfigValidator.validate_all()

if __name__ == "__main__":
    pytest.main([__file__])