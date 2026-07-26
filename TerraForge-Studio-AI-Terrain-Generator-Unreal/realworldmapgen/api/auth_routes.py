"""
Authentication API routes
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None


async def get_current_user(authorization: Optional[str] = Header(None)):
    """Dependency to get current user from session token"""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "")

    from ..core.auth_manager import get_auth_manager
    auth = get_auth_manager()

    return auth.validate_session(token)


@router.post("/register")
async def register(request: RegisterRequest):
    """Register a new user"""
    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()
        user = auth.create_user(
            username=request.username,
            email=request.email,
            password=request.password
        )

        if not user:
            raise HTTPException(
                status_code=400,
                detail="Username already exists or registration failed"
            )

        logger.info(f"User registered: {request.username}")

        return {
            "success": True,
            "message": "User registered successfully",
            "user": user.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/login")
async def login(request: LoginRequest):
    """Login and get session token"""
    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()
        session = auth.authenticate(request.username, request.password)

        if not session:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        user = auth.get_user(session.user_id)

        logger.info(f"User logged in: {request.username}")

        return {
            "success": True,
            "message": "Login successful",
            "session": {
                "token": session.session_id,
                "expires_at": session.expires_at.isoformat(),
            },
            "user": user.to_dict() if user else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/logout")
async def logout(user = Depends(get_current_user), authorization: Optional[str] = Header(None)):
    """Logout current user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")

    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()
        auth.logout(token)

        return {
            "success": True,
            "message": "Logged out successfully"
        }
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/me")
async def get_current_user_info(user = Depends(get_current_user)):
    """Get current user information"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "user": user.to_dict()
    }


@router.get("/users")
async def list_users(user = Depends(get_current_user)):
    """List all users (admin only)"""
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()
        users = auth.list_users()

        return {
            "users": [u.to_dict() for u in users],
            "count": len(users)
        }
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user = Depends(get_current_user)
):
    """Update user (admin or self)"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    is_admin = current_user.role == "admin"

    # Can only update self unless admin
    if current_user.user_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")

    updates = request.model_dump(exclude_unset=True)

    # Role is an administrative field. Without this check a user could grant
    # themselves admin by PATCHing their own record, since the rule above
    # allows self-updates.
    if "role" in updates and not is_admin:
        raise HTTPException(status_code=403, detail="Only an admin can change roles")

    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()

        success = auth.update_user(user_id, updates)

        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "success": True,
            "message": "User updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user = Depends(get_current_user)
):
    """Delete user (admin only)"""
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()
        success = auth.delete_user(user_id)

        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "success": True,
            "message": "User deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sessions/cleanup")
async def cleanup_sessions(current_user = Depends(get_current_user)):
    """Cleanup expired sessions (admin only)"""
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from ..core.auth_manager import get_auth_manager

        auth = get_auth_manager()
        auth.cleanup_expired_sessions()

        return {
            "success": True,
            "message": "Expired sessions cleaned up"
        }
    except Exception as e:
        logger.error(f"Failed to cleanup sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

