"""Role-based access control utilities"""
from fastapi import HTTPException, Depends
from typing import List, Optional
from app.middleware.auth_middleware import get_current_user
from app.auth.jwt_handler import JWTHandler

# Define permissions for different roles
PERMISSIONS = {
    "admin": [
        "read:all", "write:all", "delete:all", 
        "manage:users", "manage:settings", "manage:api_keys"
    ],
    "moderator": [
        "read:all", "write:all", "delete:own",
        "manage:content", "moderate:comments"
    ],
    "user": [
        "read:own", "write:own", "delete:own",
        "read:public"
    ]
}

def get_user_permissions(role: str) -> List[str]:
    """Get permissions for a given role"""
    return PERMISSIONS.get(role, PERMISSIONS["user"])

def require_permission(permission: str):
    """Dependency to check if user has required permission"""
    async def check_permission(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get user role
        user_role = current_user.get("role", "user")
        user_permissions = get_user_permissions(user_role)
        
        # Check if user has the required permission
        if permission not in user_permissions and f"{permission.split(':')[0]}:all" not in user_permissions:
            raise HTTPException(
                status_code=403, 
                detail=f"Permission '{permission}' required"
            )
        
        return current_user
    
    return check_permission

def require_role(required_role: str):
    """Dependency to check if user has required role"""
    async def check_role(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        jwt_handler = JWTHandler()
        if not jwt_handler.has_role(current_user, required_role):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{required_role}' required"
            )
        
        return current_user
    
    return check_role

def is_admin(current_user: dict = Depends(get_current_user)):
    """Check if user is admin"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return current_user.get("role") == "admin"

def is_moderator_or_admin(current_user: dict = Depends(get_current_user)):
    """Check if user is moderator or admin"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role = current_user.get("role", "user")
    return role in ["admin", "moderator"]

def can_access_resource(current_user: dict, resource_owner_id: int) -> bool:
    """Check if user can access a resource (owns it or has admin rights)"""
    if not current_user:
        return False
    
    user_id = current_user.get("user_id")
    user_role = current_user.get("role", "user")
    
    # Admins can access all resources
    if user_role == "admin":
        return True
    
    # Users can access their own resources
    return user_id == resource_owner_id