"""Rate limiting middleware with Redis backend"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
import redis
import os
from typing import Optional

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = None, window_size: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute or int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))
        self.window_size = window_size  # in seconds
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Initialize Redis client for rate limiting"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            return redis.from_url(redis_url)
        except Exception as e:
            print(f"Warning: Could not connect to Redis for rate limiting: {e}")
            # Fallback to in-memory storage if Redis is unavailable
            return None

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        endpoint = request.url.path

        # Use Redis for distributed rate limiting, fallback to in-memory
        if self.redis_client:
            is_allowed = self._check_rate_limit_redis(client_ip, endpoint)
        else:
            is_allowed = self._check_rate_limit_memory(client_ip, endpoint)

        if not is_allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        response = await call_next(request)
        return response

    def _check_rate_limit_redis(self, client_ip: str, endpoint: str) -> bool:
        """Check rate limit using Redis"""
        try:
            # Create a key for this IP and endpoint
            key = f"rate_limit:{client_ip}:{endpoint}"

            # Use Redis time-based window
            pipe = self.redis_client.pipeline()

            # Remove expired entries (older than window_size seconds)
            pipe.zremrangebyscore(key, 0, time.time() - self.window_size)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(time.time()): time.time()})

            # Set expiration for the key
            pipe.expire(key, self.window_size)

            results = pipe.execute()
            current_requests = results[1]  # zcard result

            # Check if limit exceeded
            return current_requests < self.rpm

        except Exception as e:
            # If Redis fails, allow the request but log the error
            print(f"Redis rate limit error: {e}")
            return True

    def _check_rate_limit_memory(self, client_ip: str, endpoint: str) -> bool:
        """Check rate limit using in-memory storage (fallback)"""
        # For in-memory implementation, we'll use a simple counter
        # This won't work across multiple instances but serves as fallback
        current_time = time.time()
        key = f"{client_ip}:{endpoint}"

        # Use a thread-safe approach with locks
        import threading
        if not hasattr(RateLimitMiddleware, '_memory_store'):
            RateLimitMiddleware._memory_store = {}
            RateLimitMiddleware._store_lock = threading.RLock()

        with RateLimitMiddleware._store_lock:
            # Clean old entries
            if key in RateLimitMiddleware._memory_store:
                old_requests = RateLimitMiddleware._memory_store[key]
                # Remove requests older than window_size seconds
                RateLimitMiddleware._memory_store[key] = [
                    req_time for req_time in old_requests
                    if current_time - req_time < self.window_size
                ]
            else:
                RateLimitMiddleware._memory_store[key] = []

            # Check if limit exceeded
            current_requests = len(RateLimitMiddleware._memory_store[key])

            if current_requests < self.rpm:
                # Add current request
                RateLimitMiddleware._memory_store[key].append(current_time)
                return True
            else:
                return False

# Advanced rate limiter with different limits for different endpoints
class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_limit: int = 60, limits: dict = None):
        super().__init__(app)
        self.default_limit = default_limit
        self.limits = limits or {}
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Initialize Redis client for rate limiting"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            return redis.from_url(redis_url)
        except Exception as e:
            print(f"Warning: Could not connect to Redis for rate limiting: {e}")
            return None

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        endpoint = request.url.path

        # Determine rate limit for this endpoint
        limit = self.limits.get(endpoint, self.default_limit)

        # Use Redis for distributed rate limiting
        if self.redis_client:
            is_allowed = self._check_rate_limit_redis(client_ip, endpoint, limit)
        else:
            is_allowed = self._check_rate_limit_memory(client_ip, endpoint, limit)

        if not is_allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        response = await call_next(request)
        return response

    def _check_rate_limit_redis(self, client_ip: str, endpoint: str, limit: int) -> bool:
        """Check rate limit using Redis with custom limit"""
        try:
            # Create a key for this IP and endpoint
            key = f"rate_limit:{client_ip}:{endpoint}"

            # Use Redis time-based window
            pipe = self.redis_client.pipeline()

            # Remove expired entries (older than 60 seconds)
            pipe.zremrangebyscore(key, 0, time.time() - 60)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(time.time()): time.time()})

            # Set expiration for the key
            pipe.expire(key, 60)

            results = pipe.execute()
            current_requests = results[1]  # zcard result

            # Check if limit exceeded
            return current_requests < limit

        except Exception as e:
            # If Redis fails, allow the request but log the error
            print(f"Redis rate limit error: {e}")
            return True

    def _check_rate_limit_memory(self, client_ip: str, endpoint: str, limit: int) -> bool:
        """Check rate limit using in-memory storage (fallback)"""
        current_time = time.time()
        key = f"{client_ip}:{endpoint}"

        # Use a thread-safe approach with locks
        import threading
        if not hasattr(AdvancedRateLimitMiddleware, '_memory_store'):
            AdvancedRateLimitMiddleware._memory_store = {}
            AdvancedRateLimitMiddleware._store_lock = threading.RLock()

        with AdvancedRateLimitMiddleware._store_lock:
            # Clean old entries
            if key in AdvancedRateLimitMiddleware._memory_store:
                old_requests = AdvancedRateLimitMiddleware._memory_store[key]
                # Remove requests older than 60 seconds
                AdvancedRateLimitMiddleware._memory_store[key] = [
                    req_time for req_time in old_requests
                    if current_time - req_time < 60
                ]
            else:
                AdvancedRateLimitMiddleware._memory_store[key] = []

            # Check if limit exceeded
            current_requests = len(AdvancedRateLimitMiddleware._memory_store[key])

            if current_requests < limit:
                # Add current request
                AdvancedRateLimitMiddleware._memory_store[key].append(current_time)
                return True
            else:
                return False
