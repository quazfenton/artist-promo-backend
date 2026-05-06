"""
Security Tests for Artist Promo Backend.

Tests for:
- CSRF protection
- Input validation
- Audit logging
- Configuration validation
- Authentication security

Run with: python -m pytest tests/test_security.py -v
"""

import pytest
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


# ==================== CSRF PROTECTION TESTS ====================

class TestCSRFProtection:
    """Test CSRF protection middleware"""

    @pytest.fixture
    def csrf_config(self):
        """Create CSRF configuration for testing"""
        from app.middleware.csrf import CSRFConfig
        return CSRFConfig(
            secret_key="test_secret_key_for_testing_only_1234567890",
            cookie_name="test_csrf_token",
            header_name="X-Test-CSRF-Token",
            token_lifetime_seconds=3600,
            exempt_paths={"/health", "/metrics"},
            exempt_methods={"GET", "HEAD", "OPTIONS"},
            allowed_origins=["http://localhost:3000"]
        )

    def test_token_generation(self, csrf_config):
        """Test CSRF token generation format"""
        from app.middleware.csrf import CSRFMiddleware
        from starlette.types import ASGIApp

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        token = middleware._generate_token()

        # Token should have format: timestamp_signature
        parts = token.split('_')
        assert len(parts) == 2
        assert len(parts[1]) == 32  # SHA256 truncated to 32 chars

        # Timestamp should be recent
        timestamp = int(parts[0])
        now = int(datetime.now().timestamp())
        assert abs(now - timestamp) < 5

    def test_tokens_match(self, csrf_config):
        """Test token matching"""
        from app.middleware.csrf import CSRFMiddleware
        from starlette.types import ASGIApp

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        token = middleware._generate_token()

        # Same token should match
        assert middleware._tokens_match(token, token) is True

        # Different tokens should not match
        token2 = middleware._generate_token()
        assert middleware._tokens_match(token, token2) is False

        # Empty tokens should not match
        assert middleware._tokens_match("", "") is False
        assert middleware._tokens_match(None, None) is False

    def test_token_expiration(self, csrf_config):
        """Test token expiration"""
        from app.middleware.csrf import CSRFMiddleware
        from starlette.types import ASGIApp
        import time

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config
        middleware.config.token_lifetime_seconds = 0  # Immediate expiration

        token = middleware._generate_token()
        time.sleep(0.1)  # Small delay to ensure expiration

        # Token should be expired
        assert middleware._tokens_match(token, token) is False

    def test_origin_validation_allowed(self, csrf_config):
        """Test origin validation with allowed origin"""
        from app.middleware.csrf import CSRFMiddleware
        from starlette.types import ASGIApp

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        mock_request = Mock()
        mock_request.headers = {"origin": "http://localhost:3000"}

        error = middleware._validate_origin(mock_request)
        assert error is None

    def test_origin_validation_blocked(self, csrf_config):
        """Test origin validation with disallowed origin"""
        from app.middleware.csrf import CSRFMiddleware
        from starlette.types import ASGIApp

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        mock_request = Mock()
        mock_request.headers = {"origin": "http://evil.com"}

        error = middleware._validate_origin(mock_request)
        assert error is not None
        assert "not in allowed origins" in error

    def test_localhost_exemption(self, csrf_config):
        """Test that localhost is allowed without origin header"""
        from app.middleware.csrf import CSRFMiddleware
        from starlette.types import ASGIApp

        middleware = CSRFMiddleware.__new__(CSRFMiddleware)
        middleware.config = csrf_config

        mock_request = Mock()
        mock_request.headers = {"host": "localhost:8000"}

        error = middleware._validate_origin(mock_request)
        assert error is None  # Should be allowed for development


# ==================== INPUT VALIDATION TESTS ====================

class TestInputValidation:
    """Test input validation utilities"""

    def test_validate_email_valid(self):
        """Test valid email validation"""
        from app.utils.validation import validate_email

        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user123@test.org",
        ]

        for email in valid_emails:
            result = validate_email(email)
            assert result == email.lower().strip()

    def test_validate_email_invalid(self):
        """Test invalid email validation"""
        from app.utils.validation import validate_email, ValidationError

        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "",
            None,
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                validate_email(email)

    def test_validate_url_valid(self):
        """Test valid URL validation"""
        from app.utils.validation import validate_url

        valid_urls = [
            "http://example.com",
            "https://example.com/path",
            "https://example.com:8080/path?query=value",
            "http://localhost:3000",
        ]

        for url in valid_urls:
            assert validate_url(url) == url

    def test_validate_url_dangerous_scheme(self):
        """Test dangerous URL scheme detection"""
        from app.utils.validation import validate_url, ValidationError

        dangerous_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
        ]

        for url in dangerous_urls:
            with pytest.raises(ValidationError):
                validate_url(url)

    def test_validate_spotify_id(self):
        """Test Spotify ID validation"""
        from app.utils.validation import validate_spotify_id, ValidationError

        # Valid Spotify IDs (22 alphanumeric chars)
        valid_ids = ["4cOdK2wGLETKBW3PvgPWqT", "37i9dQZF1DXcBWIGoYBM5M"]
        for spotify_id in valid_ids:
            assert validate_spotify_id(spotify_id) == spotify_id

        # Invalid IDs
        invalid_ids = ["too_short", "x" * 30, "", None]
        for spotify_id in invalid_ids:
            with pytest.raises(ValidationError):
                validate_spotify_id(spotify_id)

    def test_validate_instagram_handle(self):
        """Test Instagram handle validation"""
        from app.utils.validation import validate_instagram_handle, ValidationError

        # Valid handles
        valid_handles = ["username", "user.name", "user_name", "@username"]
        for handle in valid_handles:
            result = validate_instagram_handle(handle)
            assert result == handle.strip().lstrip('@')

        # Invalid handles (too long or invalid chars)
        invalid_handles = ["x" * 31, "user@name", ""]
        for handle in invalid_handles:
            with pytest.raises(ValidationError):
                validate_instagram_handle(handle)

    def test_validate_search_query_sql_injection(self):
        """Test SQL injection detection in search queries"""
        from app.utils.validation import validate_search_query, ValidationError

        sql_injections = [
            "test SELECT * FROM users",
            "test DROP TABLE users",
            "test UNION SELECT password",
            "test'; DELETE FROM users; --",
        ]

        for query in sql_injections:
            with pytest.raises(ValidationError):
                validate_search_query(query)

    def test_validate_follower_count(self):
        """Test follower count validation"""
        from app.utils.validation import validate_follower_count, ValidationError

        # Valid counts
        assert validate_follower_count(0) == 0
        assert validate_follower_count(1000) == 1000
        assert validate_follower_count(1000000) == 1000000

        # Invalid counts
        with pytest.raises(ValidationError):
            validate_follower_count(-1)
        with pytest.raises(ValidationError):
            validate_follower_count(100000001)
        with pytest.raises(ValidationError):
            validate_follower_count("not_a_number")

    def test_validate_priority_score(self):
        """Test priority score validation"""
        from app.utils.validation import validate_priority_score, ValidationError

        # Valid scores
        assert validate_priority_score(0) == 0
        assert validate_priority_score(50) == 50
        assert validate_priority_score(100) == 100

        # Invalid scores
        with pytest.raises(ValidationError):
            validate_priority_score(-1)
        with pytest.raises(ValidationError):
            validate_priority_score(101)

    def test_sanitize_html(self):
        """Test HTML sanitization"""
        from app.utils.validation import sanitize_html

        # Dangerous HTML should be removed
        dangerous_html = [
            '<script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            '<div onclick="alert(1)">Click</div>',
        ]

        for html in dangerous_html:
            result = sanitize_html(html)
            assert '<script' not in result.lower()
            assert 'onclick' not in result.lower()
            assert 'onerror' not in result.lower()


# ==================== CONFIGURATION VALIDATION TESTS ====================

class TestConfigurationValidation:
    """Test configuration validation"""

    def test_validate_required_vars_missing(self):
        """Test missing required variables"""
        from app.utils.config_validator import ConfigValidator, ConfigValidationError

        with patch.dict(os.environ, {}, clear=True):
            validator = ConfigValidator()
            with pytest.raises(ConfigValidationError):
                validator._validate_required_vars()

    def test_validate_secret_key_length(self):
        """Test secret key length validation"""
        from app.utils.config_validator import ConfigValidator

        with patch.dict(os.environ, {"SECRET_KEY": "short"}):
            validator = ConfigValidator()
            validator._validate_security_config()
            assert any("32 characters" in error for error in validator.errors)

    def test_validate_secret_key_valid(self):
        """Test valid secret key"""
        from app.utils.config_validator import ConfigValidator

        secret = "x" * 64  # 64 character secret
        with patch.dict(os.environ, {"SECRET_KEY": secret, "DATABASE_URL": "sqlite:///test.db"}):
            validator = ConfigValidator()
            validator._validate_security_config()
            assert not any("SECRET_KEY" in error for error in validator.errors)

    def test_validate_cors_wildcard_warning(self):
        """Test CORS wildcard warning"""
        from app.utils.config_validator import ConfigValidator

        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "*"}):
            validator = ConfigValidator()
            validator._validate_security_config()
            assert any("wildcard" in warning.lower() for warning in validator.warnings)

    def test_validate_database_sqlite_production_warning(self):
        """Test SQLite in production warning"""
        from app.utils.config_validator import ConfigValidator

        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///test.db",
            "ENVIRONMENT": "production"
        }):
            validator = ConfigValidator()
            validator._validate_database_config()
            assert any("SQLite" in warning for warning in validator.warnings)


# ==================== AUDIT LOGGING TESTS ====================

class TestAuditLogging:
    """Test audit logging"""

    @pytest.fixture
    def audit_logger(self):
        """Create audit logger with temp file"""
        from app.utils.audit_logger import AuditLogger

        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            logger = AuditLogger(log_file=f.name)
            yield logger
            os.unlink(f.name)

    def test_audit_log_creation(self, audit_logger):
        """Test audit log entry creation"""
        from app.utils.audit_logger import AuditAction

        audit_logger.log(
            action=AuditAction.LOGIN_SUCCESS,
            user_id=1,
            user_email="user@example.com",
            success=True
        )

        # Check log file exists and has content
        assert os.path.exists(audit_logger.log_file)
        with open(audit_logger.log_file, 'r') as f:
            content = f.read()
            assert "auth.login.success" in content
            assert "user@example.com" in content

    def test_audit_email_masking(self, audit_logger):
        """Test email masking in audit logs"""
        from app.utils.audit_logger import AuditAction

        audit_logger.log(
            action=AuditAction.LOGIN_SUCCESS,
            user_email="testuser@example.com",
            success=True
        )

        with open(audit_logger.log_file, 'r') as f:
            content = f.read()
            # Email should be masked
            assert "te***er@example.com" in content or "***REDACTED***" in content

    def test_audit_sensitive_data_masking(self, audit_logger):
        """Test sensitive data masking"""
        from app.utils.audit_logger import AuditAction

        audit_logger.log(
            action=AuditAction.LOGIN_SUCCESS,
            details={
                "password": "secret123",
                "token": "abc123",
                "normal_field": "visible"
            },
            success=True
        )

        with open(audit_logger.log_file, 'r') as f:
            content = f.read()
            assert "***REDACTED***" in content
            assert "secret123" not in content


# ==================== INTEGRATION TESTS ====================

class TestSecurityIntegration:
    """Test security features integration"""

    def test_validation_in_api_endpoint(self):
        """Test validation is applied in API context"""
        from app.utils.validation import validate_email, validate_search_query, ValidationError

        # Simulate API input
        try:
            validate_email("invalid-email")
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected

        try:
            validate_search_query("SELECT * FROM users")
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected

    def test_config_validation_at_startup(self):
        """Test configuration validation simulating startup"""
        from app.utils.config_validator import validate_config, ConfigValidationError

        # Test with minimal valid config
        with patch.dict(os.environ, {
            "SECRET_KEY": "x" * 64,
            "DATABASE_URL": "sqlite:///test.db"
        }):
            # Should not raise
            result = validate_config()
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
