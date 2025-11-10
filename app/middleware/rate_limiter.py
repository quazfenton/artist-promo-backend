"""Rate limiting middleware"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict, deque
import os

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = None):
        super().__init__(app)
        self.rpm = requests_per_minute or int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))
        self.requests = defaultdict(deque)
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()
        
        # Clean old requests
        minute_ago = now - 60
        while self.requests[client_ip] and self.requests[client_ip][0] < minute_ago:
            self.requests[client_ip].popleft()
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.rpm:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Add current request
        self.requests[client_ip].append(now)
        
        response = await call_next(request)
        return response
