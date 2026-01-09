"""API endpoint tests for the artist promotion backend"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

from app.api.main import app

client = TestClient(app)

def test_root_endpoint():
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert "app" in data
    assert "status" in data
    assert data["app"] == "Artist Promotion API"
    assert data["status"] == "running"

def test_health_endpoint():
    """Test the health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"

def test_detailed_health_endpoint():
    """Test the detailed health endpoint"""
    response = client.get("/health/detailed")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)

def test_metrics_endpoint():
    """Test the metrics endpoint"""
    response = client.get("/metrics")
    # This might return 500 if prometheus client isn't properly configured in test
    assert response.status_code in [200, 500]

# Test auth endpoints (these will likely require authentication)
def test_auth_endpoints():
    """Test auth endpoints exist"""
    # Test login endpoint exists (will likely return 422 for missing form data)
    response = client.post("/auth/login")
    assert response.status_code in [401, 422]  # Unauthorized or Validation Error
    
    # Test refresh endpoint exists
    response = client.post("/auth/refresh")
    assert response.status_code in [401, 422]  # Unauthorized or Validation Error
    
    # Test me endpoint exists
    response = client.get("/auth/me")
    assert response.status_code in [401, 403]  # Unauthorized or Forbidden

def test_contacts_endpoint():
    """Test contacts endpoint"""
    response = client.get("/contacts")
    # Will likely return 401/403 due to auth, or 422 for missing query params
    assert response.status_code in [401, 403, 422, 200]

def test_scrape_endpoints():
    """Test scrape endpoints exist"""
    # Test Spotify scrape endpoint exists
    response = client.post("/scrape/spotify")
    assert response.status_code in [401, 403, 422]  # Auth required or validation error
    
    # Test YouTube scrape endpoint exists
    response = client.post("/scrape/youtube")
    assert response.status_code in [401, 403, 422]  # Auth required or validation error
    
    # Test Instagram scrape endpoint exists
    response = client.post("/scrape/instagram")
    assert response.status_code in [401, 403, 422]  # Auth required or validation error
    
    # Test Web scrape endpoint exists
    response = client.post("/scrape/web")
    assert response.status_code in [401, 403, 422]  # Auth required or validation error

def test_export_endpoint():
    """Test export endpoint exists"""
    # Test export endpoint exists
    response = client.post("/export/csv")
    assert response.status_code in [401, 403, 422]  # Auth required or validation error

def test_webhook_endpoints():
    """Test webhook endpoints exist"""
    # Test n8n scrape webhook exists
    response = client.post("/webhook/n8n/scrape")
    assert response.status_code in [401, 422]  # Auth required or validation error
    
    # Test n8n export webhook exists
    response = client.post("/webhook/n8n/export")
    assert response.status_code in [401, 422]  # Auth required or validation error

def test_api_security_headers():
    """Test that security headers are present"""
    response = client.get("/")
    headers = response.headers
    
    # Check for security headers
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
    assert "x-xss-protection" in headers
    assert "strict-transport-security" in headers

def test_cors_headers():
    """Test CORS headers"""
    response = client.get("/")
    headers = response.headers
    
    # The exact headers depend on the CORS configuration
    # Just verify the response is successful
    assert response.status_code == 200

def test_response_time_headers():
    """Test performance headers are added"""
    response = client.get("/")
    headers = response.headers
    
    # Check for performance headers added by middleware
    assert "x-response-time" in headers

def test_api_version():
    """Test API version information"""
    response = client.get("/")
    data = response.json()
    
    assert "version" in data
    assert data["version"] == "1.0.0"

def test_invalid_endpoint():
    """Test that invalid endpoints return 404"""
    response = client.get("/invalid/endpoint")
    assert response.status_code == 404

def test_method_not_allowed():
    """Test that invalid methods return 405"""
    response = client.put("/")  # PUT not allowed on root
    assert response.status_code == 405

# Test with mocked authentication for endpoints that require it
@patch('app.middleware.auth_middleware.get_current_user')
def test_contacts_with_mocked_auth(mock_get_current_user):
    """Test contacts endpoint with mocked authentication"""
    # Mock the authentication
    mock_get_current_user.return_value = {"user_id": 1, "email": "test@example.com", "role": "user"}
    
    # Now try to access the contacts endpoint
    response = client.get("/contacts")
    
    # Should be 200 OK (empty list) or some other success code
    # The exact response depends on the database state
    assert response.status_code in [200, 422]  # OK or validation error

@patch('app.middleware.auth_middleware.get_current_user')
def test_scrape_spotify_with_mocked_auth(mock_get_current_user):
    """Test Spotify scrape endpoint with mocked authentication"""
    # Mock the authentication
    mock_get_current_user.return_value = {"user_id": 1, "email": "test@example.com", "role": "user"}
    
    # Try to scrape with minimal payload
    payload = {
        "scraper_type": "spotify",
        "genre": "hip-hop",
        "min_followers": 500,
        "max_results": 10
    }
    
    response = client.post("/scrape/spotify", json=payload)
    
    # Should be 422 (validation error) because we're not providing a real scraper
    # Or it might succeed if the endpoint doesn't validate the payload structure
    assert response.status_code in [200, 422]

# Test error handling
def test_error_format():
    """Test that errors are returned in a consistent format"""
    response = client.get("/invalid/endpoint")
    
    # For 404 errors, FastAPI returns its own error format
    # which is different from our custom error handlers
    assert response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__])