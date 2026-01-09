"""Authentication API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os

from app.models.database import User
from app.auth.jwt_handler import JWTHandler
from app.auth.rbac import is_admin, get_current_user
from app.utils.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

# Request/Response models
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    email: str
    role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserRegistrationRequest(BaseModel):
    email: str
    password: str
    role: str = "user"

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

# Initialize JWT handler
jwt_handler = JWTHandler()

@router.post("/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """User login endpoint"""
    db = next(get_db())

    try:
        # Find user by email
        user = db.query(User).filter(User.email == form_data.username).first()

        if not user or not user.verify_password(form_data.password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="Account is deactivated"
            )

        # Create tokens
        access_token = jwt_handler.create_access_token(
            user_id=user.id,
            email=user.email,
            role=getattr(user, 'role', 'user')
        )

        refresh_token = jwt_handler.create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": jwt_handler.access_token_expire * 60,  # seconds
            "user_id": user.id,
            "email": user.email,
            "role": getattr(user, 'role', 'user')
        }

    finally:
        db.close()

@router.post("/auth/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    payload = jwt_handler.verify_refresh_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

    # Fetch user details from DB to create new access token
    db = next(get_db())
    try:
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="User account invalid or deactivated"
            )

        # Create new access token with fresh user data
        access_token = jwt_handler.create_access_token(
            user_id=user.id,
            email=user.email,
            role=getattr(user, 'role', 'user')
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": jwt_handler.access_token_expire * 60  # seconds
        }
    finally:
        db.close()

@router.post("/auth/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """Logout endpoint - blacklist current token"""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = auth_header[7:]  # Remove "Bearer " prefix

    # Blacklist the access token
    success = jwt_handler.blacklist_token(token)

    if not success:
        raise HTTPException(status_code=500, detail="Could not logout")

    return {"message": "Successfully logged out"}

@router.post("/auth/logout-all")
async def logout_all(request: Request, refresh_token: RefreshTokenRequest, current_user: dict = Depends(get_current_user)):
    """Logout from all devices - revoke refresh token"""
    success = jwt_handler.revoke_refresh_token(refresh_token.refresh_token)

    if not success:
        raise HTTPException(status_code=500, detail="Could not logout from all devices")

    return {"message": "Logged out from all devices"}

@router.post("/auth/register")
async def register(registration_data: UserRegistrationRequest, current_user: dict = Depends(get_current_user)):
    """Admin-only endpoint to register new users"""
    # Check if current user is admin
    if not jwt_handler.has_role(current_user, "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = next(get_db())

    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == registration_data.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create new user
        user = User(
            email=registration_data.email,
            hashed_password=User.hash_password(registration_data.password)
        )

        # Only set role if current user is admin and role is specified
        if jwt_handler.has_role(current_user, "admin") and hasattr(registration_data, 'role'):
            setattr(user, 'role', getattr(registration_data, 'role', 'user'))

        db.add(user)
        db.commit()
        db.refresh(user)

        return {"message": "User registered successfully", "user_id": user.id}

    finally:
        db.close()

@router.put("/auth/change-password")
async def change_password(
    password_change: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    user_id = current_user.get("user_id")

    # Get user from DB
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.verify_password(password_change.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Update password
    user.hashed_password = User.hash_password(password_change.new_password)
    user.updated_at = datetime.utcnow()

    db.commit()

    return {"message": "Password changed successfully"}

@router.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "user_id": current_user.get("user_id"),
        "email": current_user.get("email"),
        "role": current_user.get("role", "user"),
        "exp": current_user.get("exp")
    }

@router.get("/auth/users")
async def list_users(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin-only endpoint to list all users"""
    if not jwt_handler.has_role(current_user, "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    users = db.query(User).all()

    return [{
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "is_admin": getattr(user, 'is_admin', False),
        "created_at": user.created_at
    } for user in users]

@router.patch("/auth/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: UpdateUserRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin-only endpoint to update user"""
    if not jwt_handler.has_role(current_user, "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update allowed fields
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    if update_data.is_admin is not None and jwt_handler.has_role(current_user, "admin"):
        user.is_admin = update_data.is_admin

    db.commit()

    return {"message": "User updated successfully"}