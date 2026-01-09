"""Authentication middleware"""
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt_handler import JWTHandler
from typing import Optional

security = HTTPBearer(auto_error=False)
jwt_handler = JWTHandler()

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = jwt_handler.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        return None

    payload = jwt_handler.verify_token(credentials.credentials)
    return payload

async def verify_api_key(request: Request):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if not jwt_handler.verify_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True

# Authentication middleware class to set user in request state
class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        # Get authorization header
        auth_header = request.headers.get("authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            payload = jwt_handler.verify_token(token)

            if payload:
                # Set user in request state
                request.state.user = payload

        await self.app(scope, receive, send)
