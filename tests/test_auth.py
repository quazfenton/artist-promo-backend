"""Authentication system tests for the artist promotion backend"""
import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import jwt

from app.auth.jwt_handler import JWTHandler
from app.auth.rbac import PERMISSIONS, get_user_permissions, require_permission, require_role
from app.middleware.auth_middleware import get_current_user

def test_jwt_handler_initialization():
    """Test JWT handler initialization"""
    jwt_handler = JWTHandler()
    
    assert jwt_handler.secret is not None
    assert jwt_handler.algorithm == "HS256"
    assert jwt_handler.access_token_expire >= 0
    assert jwt_handler.refresh_token_expire >= 0

def test_jwt_handler_with_env_vars():
    """Test JWT handler with environment variables"""
    # Mock environment variables
    with patch.dict(os.environ, {
        "JWT_SECRET": "test_secret_123",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "REFRESH_TOKEN_EXPIRE_DAYS": "14"
    }):
        jwt_handler = JWTHandler()
        
        assert jwt_handler.secret == "test_secret_123"
        assert jwt_handler.access_token_expire == 60
        assert jwt_handler.refresh_token_expire == 14

def test_create_access_token():
    """Test creating access tokens"""
    jwt_handler = JWTHandler()
    
    token = jwt_handler.create_access_token(user_id=1, email="test@example.com", role="user")
    
    assert token is not None
    assert isinstance(token, str)
    
    # Decode and verify the token
    decoded = jwt.decode(token, jwt_handler.secret, algorithms=[jwt_handler.algorithm])
    assert decoded["user_id"] == 1
    assert decoded["email"] == "test@example.com"
    assert decoded["role"] == "user"
    assert decoded["type"] == "access"
    assert "exp" in decoded
    assert "jti" in decoded

def test_create_refresh_token():
    """Test creating refresh tokens"""
    jwt_handler = JWTHandler()
    
    token = jwt_handler.create_refresh_token(user_id=1)
    
    assert token is not None
    assert isinstance(token, str)
    
    # Decode and verify the token
    decoded = jwt.decode(token, jwt_handler.secret, algorithms=[jwt_handler.algorithm])
    assert decoded["user_id"] == 1
    assert decoded["type"] == "refresh"
    assert "exp" in decoded
    assert "jti" in decoded

def test_verify_valid_token():
    """Test verifying a valid token"""
    jwt_handler = JWTHandler()
    
    token = jwt_handler.create_access_token(user_id=1, email="test@example.com", role="user")
    payload = jwt_handler.verify_token(token)
    
    assert payload is not None
    assert payload["user_id"] == 1
    assert payload["email"] == "test@example.com"
    assert payload["role"] == "user"

def test_verify_invalid_token():
    """Test verifying an invalid token"""
    jwt_handler = JWTHandler()
    
    payload = jwt_handler.verify_token("invalid_token_string")
    
    assert payload is None

def test_verify_expired_token():
    """Test verifying an expired token"""
    jwt_handler = JWTHandler()
    
    # Create a token with a past expiration time
    past_time = datetime.utcnow() - timedelta(minutes=1)
    payload = {
        "user_id": 1,
        "email": "test@example.com",
        "role": "user",
        "exp": past_time,
        "type": "access"
    }
    expired_token = jwt.encode(payload, jwt_handler.secret, algorithm=jwt_handler.algorithm)
    
    result = jwt_handler.verify_token(expired_token)
    
    assert result is None

def test_token_blacklisting():
    """Test token blacklisting functionality"""
    jwt_handler = JWTHandler()
    
    # Create a token
    token = jwt_handler.create_access_token(user_id=1, email="test@example.com", role="user")
    
    # Verify it works initially
    payload = jwt_handler.verify_token(token)
    assert payload is not None
    
    # Blacklist the token
    success = jwt_handler.blacklist_token(token)
    assert success is True
    
    # Verify it no longer works
    payload = jwt_handler.verify_token(token)
    assert payload is None

def test_refresh_token_verification():
    """Test refresh token verification"""
    jwt_handler = JWTHandler()
    
    refresh_token = jwt_handler.create_refresh_token(user_id=1)
    payload = jwt_handler.verify_refresh_token(refresh_token)
    
    assert payload is not None
    assert payload["user_id"] == 1
    assert payload["type"] == "refresh"

def test_refresh_token_revocation():
    """Test refresh token revocation"""
    jwt_handler = JWTHandler()
    
    refresh_token = jwt_handler.create_refresh_token(user_id=1)
    
    # Verify it works initially
    payload = jwt_handler.verify_refresh_token(refresh_token)
    assert payload is not None
    
    # Revoke the token
    success = jwt_handler.revoke_refresh_token(refresh_token)
    assert success is True
    
    # Verify it no longer works
    payload = jwt_handler.verify_refresh_token(refresh_token)
    assert payload is None

def test_api_key_verification():
    """Test API key verification"""
    jwt_handler = JWTHandler()
    
    # Mock environment variable for API keys
    with patch.dict(os.environ, {"API_KEYS": "key1,key2,key3"}):
        # Test valid API key
        assert jwt_handler.verify_api_key("key1") is True
        assert jwt_handler.verify_api_key("key2") is True
        assert jwt_handler.verify_api_key("key3") is True
        
        # Test invalid API key
        assert jwt_handler.verify_api_key("invalid_key") is False
        assert jwt_handler.verify_api_key("") is False

def test_role_hierarchy():
    """Test role hierarchy functionality"""
    jwt_handler = JWTHandler()
    
    # Test admin role
    admin_payload = {"role": "admin"}
    assert jwt_handler.has_role(admin_payload, "user") is True
    assert jwt_handler.has_role(admin_payload, "moderator") is True
    assert jwt_handler.has_role(admin_payload, "admin") is True
    
    # Test moderator role
    mod_payload = {"role": "moderator"}
    assert jwt_handler.has_role(mod_payload, "user") is True
    assert jwt_handler.has_role(mod_payload, "moderator") is True
    assert jwt_handler.has_role(mod_payload, "admin") is False
    
    # Test user role
    user_payload = {"role": "user"}
    assert jwt_handler.has_role(user_payload, "user") is True
    assert jwt_handler.has_role(user_payload, "moderator") is False
    assert jwt_handler.has_role(user_payload, "admin") is False

def test_get_user_permissions():
    """Test getting user permissions"""
    # Test admin permissions
    admin_perms = get_user_permissions("admin")
    assert "read:all" in admin_perms
    assert "write:all" in admin_perms
    assert "delete:all" in admin_perms
    assert "manage:users" in admin_perms
    
    # Test moderator permissions
    mod_perms = get_user_permissions("moderator")
    assert "read:all" in mod_perms
    assert "write:all" in mod_perms
    assert "delete:own" in mod_perms
    assert "manage:content" in mod_perms
    
    # Test user permissions
    user_perms = get_user_permissions("user")
    assert "read:own" in user_perms
    assert "write:own" in user_perms
    assert "delete:own" in user_perms
    assert "read:public" in user_perms

def test_permission_checking():
    """Test permission checking functionality"""
    jwt_handler = JWTHandler()
    
    # Admin should have all permissions
    admin_payload = {"role": "admin"}
    assert jwt_handler.has_role(admin_payload, "admin") is True
    assert jwt_handler.has_role(admin_payload, "moderator") is True
    assert jwt_handler.has_role(admin_payload, "user") is True
    
    # User should only have user permissions
    user_payload = {"role": "user"}
    assert jwt_handler.has_role(user_payload, "user") is True
    assert jwt_handler.has_role(user_payload, "moderator") is False
    assert jwt_handler.has_role(user_payload, "admin") is False

def test_jwt_handler_with_mocked_redis():
    """Test JWT handler with mocked Redis for blacklisting"""
    with patch('app.auth.jwt_handler.redis') as mock_redis_module:
        # Mock the redis.from_url method
        mock_redis_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis_client
        
        jwt_handler = JWTHandler()
        
        # Verify Redis was initialized
        mock_redis_module.from_url.assert_called_once()
        
        # Test token creation still works
        token = jwt_handler.create_access_token(user_id=1, email="test@example.com", role="user")
        assert token is not None

def test_verify_token_with_blacklisted_token():
    """Test verifying a token that's been blacklisted in Redis"""
    with patch('app.auth.jwt_handler.redis') as mock_redis_module:
        # Mock the redis client
        mock_redis_client = MagicMock()
        mock_redis_client.exists.return_value = True  # Token is blacklisted
        mock_redis_module.from_url.return_value = mock_redis_client
        
        jwt_handler = JWTHandler()
        
        # Create a token
        token = jwt_handler.create_access_token(user_id=1, email="test@example.com", role="user")
        
        # Verify the token (should return None because it's blacklisted)
        result = jwt_handler.verify_token(token)
        assert result is None

def test_verify_token_with_nonexistent_redis():
    """Test JWT handler when Redis is not available"""
    with patch('app.auth.jwt_handler.redis') as mock_redis_module:
        # Simulate Redis connection failure
        mock_redis_module.from_url.side_effect = Exception("Redis connection failed")
        
        jwt_handler = JWTHandler()
        
        # Redis client should be None
        assert jwt_handler.redis_client is None
        
        # Token creation should still work
        token = jwt_handler.create_access_token(user_id=1, email="test@example.com", role="user")
        assert token is not None
        
        # Token verification should work (without blacklisting check)
        payload = jwt_handler.verify_token(token)
        assert payload is not None

def test_refresh_token_with_redis():
    """Test refresh token functionality with Redis"""
    with patch('app.auth.jwt_handler.redis') as mock_redis_module:
        mock_redis_client = MagicMock()
        mock_redis_client.exists.return_value = True  # Refresh token exists
        mock_redis_module.from_url.return_value = mock_redis_client
        
        jwt_handler = JWTHandler()
        
        # Create and verify refresh token
        refresh_token = jwt_handler.create_refresh_token(user_id=1)
        payload = jwt_handler.verify_refresh_token(refresh_token)
        
        # Should work normally
        assert payload is not None
        assert payload["user_id"] == 1

def test_refresh_token_revocation_with_redis():
    """Test refresh token revocation with Redis"""
    with patch('app.auth.jwt_handler.redis') as mock_redis_module:
        mock_redis_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis_client
        
        jwt_handler = JWTHandler()
        
        # Create a refresh token
        refresh_token = jwt_handler.create_refresh_token(user_id=1)
        
        # Revoke the token
        success = jwt_handler.revoke_refresh_token(refresh_token)
        
        # Should call Redis delete
        assert success is True
        mock_redis_client.delete.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__])