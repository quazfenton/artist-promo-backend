"""
CSRF Protection Middleware for Artist Promo Backend.

Implements OWASP recommended CSRF protection with:
- Double-submit cookie pattern
- Origin/Referer validation
- Token expiration
- Exempt paths for APIs

Usage:
    from app.middleware.csrf import CSRFMiddleware
    
    app.add_middleware(CSRFMiddleware)
"""

import os
import secrets
import hashlib
import hmac
import logging
from typing import Optional, Set, List
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CSRFConfig:
    """CSRF protection configuration"""

    def __init__(
        self,
        secret_key: str = None,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        token_lifetime_seconds: int = 3600,
        exempt_paths: Set[str] = None,
        exempt_methods: Set[str] = None,
        validate_origin: bool = True,
        allowed_origins: List[str] = None,
    ):
        self.secret_key = secret_key or os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.token_lifetime_seconds = token_lifetime_seconds
        self.exempt_paths = exempt_paths or {
            "/health", "/metrics", "/docs", "/redoc", "/openapi.json",
            "/webhook/n8n/scrape", "/webhook/n8n/export", "/ingest"
        }
        self.exempt_methods = exempt_methods or {"GET", "HEAD", "OPTIONS"}
        self.validate_origin = validate_origin
        self.allowed_origins = allowed_origins or []


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware implementing defense in depth.
    
    Combines:
    1. Double-submit cookie pattern
    2. Origin/Referer header validation
    3. Token expiration
    """

    def __init__(self, app: ASGIApp, config: CSRFConfig = None):
        super().__init__(app)
        self.config = config or CSRFConfig()
        self.csrf_logger = logging.getLogger("artist_promo.csrf")

    async def dispatch(self, request: Request, call_next):
        """Process CSRF protection for each request"""
        path = request.url.path
        method = request.method

        # Skip CSRF protection for exempt paths
        if any(path.startswith(exempt) for exempt in self.config.exempt_paths):
            self.csrf_logger.debug(f"CSRF exempt path: {path}")
            return await call_next(request)

        # Skip CSRF protection for safe methods
        if method in self.config.exempt_methods:
            response = await call_next(request)
            # Set CSRF cookie for GET requests
            if not request.cookies.get(self.config.cookie_name):
                token = self._generate_token()
                response.set_cookie(
                    self.config.cookie_name,
                    token,
                    max_age=self.config.token_lifetime_seconds,
                    httponly=False,
                    samesite="lax",
                    secure=request.url.scheme == "https",
                    path="/"
                )
            return response

        # Validate CSRF for state-changing requests
        is_valid, error = await self._validate_csrf(request)

        if not is_valid:
            self.csrf_logger.warning(
                f"CSRF validation failed | path={path} | method={method} | reason={error}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": 403,
                        "message": "CSRF validation failed",
                        "detail": error,
                        "type": "CSRFError"
                    }
                }
            )

        self.csrf_logger.debug(f"CSRF validation passed | path={path} | method={method}")
        response = await call_next(request)

        # Ensure CSRF cookie is set
        if not request.cookies.get(self.config.cookie_name):
            token = self._generate_token()
            response.set_cookie(
                self.config.cookie_name,
                token,
                max_age=self.config.token_lifetime_seconds,
                httponly=False,
                samesite="lax",
                secure=request.url.scheme == "https",
                path="/"
            )

        return response

    async def _validate_csrf(self, request: Request) -> tuple:
        """Validate CSRF token and origin"""
        # Get CSRF token from header
        csrf_token = request.headers.get(self.config.header_name)
        if not csrf_token:
            return False, f"Missing CSRF token in {self.config.header_name} header"

        # Get CSRF token from cookie
        cookie_token = request.cookies.get(self.config.cookie_name)
        if not cookie_token:
            return False, "Missing CSRF cookie"

        # Validate token matches (Double-Submit pattern)
        if not self._tokens_match(csrf_token, cookie_token):
            return False, "CSRF token mismatch"

        # Validate origin/referer headers
        if self.config.validate_origin:
            origin_error = self._validate_origin(request)
            if origin_error:
                return False, origin_error

        return True, ""

    def _generate_token(self) -> str:
        """Generate CSRF token with timestamp and HMAC signature"""
        timestamp = int(datetime.now().timestamp())
        message = f"{timestamp}"
        signature = hmac.new(
            self.config.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        return f"{timestamp}_{signature}"

    def _tokens_match(self, token: str, cookie_token: str) -> bool:
        """Validate tokens match and are not expired"""
        if not token or not cookie_token:
            return False

        # Tokens must match exactly
        if not hmac.compare_digest(token, cookie_token):
            return False

        # Check token expiration
        try:
            timestamp_str = token.split("_")[0]
            timestamp = int(timestamp_str)
            token_age = datetime.now().timestamp() - timestamp

            if token_age > self.config.token_lifetime_seconds:
                logger.info(f"CSRF token expired (age: {token_age}s)")
                return False
            return True
        except (ValueError, IndexError):
            logger.warning("Invalid CSRF token format")
            return False

    def _validate_origin(self, request: Request) -> Optional[str]:
        """Validate Origin and Referer headers"""
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        host = request.headers.get("host", "")

        # Validate against allowed origins
        if self.config.allowed_origins:
            if origin and origin not in self.config.allowed_origins:
                return f"Origin {origin} not in allowed origins"

            if not origin and referer:
                referer_parts = referer.split("/")
                if len(referer_parts) >= 3:
                    referer_origin = f"{referer_parts[0]}//{referer_parts[2]}"
                    if referer_origin not in self.config.allowed_origins:
                        return f"Referer origin {referer_origin} not in allowed origins"

        # Check referer matches host for same-origin
        if not origin and referer:
            if host and host not in referer:
                return "Referer header does not match host"

        # Allow localhost/127.0.0.1 for development
        if not origin and not referer:
            if "localhost" not in host and "127.0.0.1" not in host:
                return "Missing Origin and Referer headers"

        return None
