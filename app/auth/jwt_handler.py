"""JWT authentication handler"""
import jwt
from datetime import datetime, timedelta
from typing import Optional
import os
import redis
import uuid

class JWTHandler:
    def __init__(self):
        self.secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))  # minutes
        self.refresh_token_expire = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))  # days
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self):
        """Initialize Redis client for token blacklisting"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            return redis.from_url(redis_url)
        except (redis.ConnectionError, redis.TimeoutError, ValueError, redis.AuthenticationError) as e:
            logger.warning(f"Could not connect to Redis for JWT: {e}")
            return None

    def create_access_token(self, user_id: int, email: str, role: str = "user") -> str:
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire),
            "type": "access",
            "jti": str(uuid.uuid4())  # JWT ID for blacklisting
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int) -> str:
        jti = str(uuid.uuid4())
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire),
            "type": "refresh",
            "jti": jti
        }
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)

        # Store refresh token in Redis for blacklisting
        if self.redis_client:
            # Set expiration to match token expiration
            self.redis_client.setex(
                f"refresh_token:{jti}",
                timedelta(days=self.refresh_token_expire),
                str(user_id)
            )

        return token

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])

            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and self.redis_client:
                if self.redis_client.exists(f"blacklisted:{jti}"):
                    return None

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None

    def blacklist_token(self, token: str) -> bool:
        """Blacklist a JWT token by its JTI"""
        try:
            # Decode without verification to get JTI
            unverified_payload = jwt.decode(token, self.secret, algorithms=[self.algorithm], options={"verify_signature": False})
            jti = unverified_payload.get("jti")

            if jti and self.redis_client:
                # Calculate remaining time until token expiration
                exp = unverified_payload.get("exp")
                if exp:
                    remaining_time = exp - datetime.utcnow().timestamp()
                    if remaining_time > 0:
                        self.redis_client.setex(f"blacklisted:{jti}", int(remaining_time), "1")
                        return True
            return False
        except:
            return False

    def verify_refresh_token(self, token: str) -> Optional[dict]:
        """Verify refresh token and check if it's still valid in Redis"""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])

            # Check if refresh token exists in Redis
            jti = payload.get("jti")
            if jti and self.redis_client:
                if not self.redis_client.exists(f"refresh_token:{jti}"):
                    return None

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None

    def revoke_refresh_token(self, token: str) -> bool:
        """Revoke a refresh token by removing it from Redis"""
        try:
            # Decode without verification to get JTI
            unverified_payload = jwt.decode(token, self.secret, algorithms=[self.algorithm], options={"verify_signature": False})
            jti = unverified_payload.get("jti")

            if jti and self.redis_client:
                self.redis_client.delete(f"refresh_token:{jti}")
                return True
            return False
        except:
            return False

    def verify_api_key(self, api_key: str) -> bool:
        valid_keys = os.getenv("API_KEYS", "").split(",")
        return api_key in valid_keys

    def has_role(self, token_payload: dict, required_role: str) -> bool:
        """Check if user has required role"""
        user_role = token_payload.get("role", "user")
        role_hierarchy = {
            "admin": 3,
            "moderator": 2,
            "user": 1
        }

        required_level = role_hierarchy.get(required_role, 1)
        user_level = role_hierarchy.get(user_role, 1)

        return user_level >= required_level
