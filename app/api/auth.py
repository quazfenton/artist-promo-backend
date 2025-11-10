"""Authentication endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.auth.models import User
from app.auth.jwt_handler import JWTHandler
from app.models.database import get_db

router = APIRouter(prefix="/auth", tags=["authentication"])
jwt_handler = JWTHandler()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = User.hash_password(request.password)
    user = User(email=request.email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Generate tokens
    access_token = jwt_handler.create_access_token(user.id, user.email)
    refresh_token = jwt_handler.create_refresh_token(user.id)
    
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not user.verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    
    # Generate tokens
    access_token = jwt_handler.create_access_token(user.id, user.email)
    refresh_token = jwt_handler.create_refresh_token(user.id)
    
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    payload = jwt_handler.verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    
    # Generate new tokens
    access_token = jwt_handler.create_access_token(user.id, user.email)
    new_refresh_token = jwt_handler.create_refresh_token(user.id)
    
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)
