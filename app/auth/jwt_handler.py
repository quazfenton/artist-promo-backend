"""JWT authentication handler"""
import jwt
from datetime import datetime, timedelta
from typing import Optional
import os

class JWTHandler:
    def __init__(self):
        self.secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire = 30  # minutes
        self.refresh_token_expire = 7  # days
    
    def create_access_token(self, user_id: int, email: str) -> str:
        payload = {
            "user_id": user_id,
            "email": email,
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire),
            "type": "access"
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: int) -> str:
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire),
            "type": "refresh"
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    def verify_api_key(self, api_key: str) -> bool:
        valid_keys = os.getenv("API_KEYS", "").split(",")
        return api_key in valid_keys
