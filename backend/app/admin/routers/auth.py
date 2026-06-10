import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.admin.auth.password import hash_password, verify_password
from app.admin.deps import get_current_user, get_db
from app.admin.models.user import User, UserStatus
from app.admin.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserInfoResponse,
)
from deerflow.config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


def _user_to_response(user: User) -> UserInfoResponse:
    return UserInfoResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role.value,
        department_id=str(user.department_id) if user.department_id else None,
        status=user.status.value,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    config = get_app_config().admin.jwt
    access = create_access_token(user.id, user.username, user.role.value, user.department_id, user.tenant_id, config)
    refresh = create_refresh_token(user.id, config)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    config = get_app_config().admin.jwt
    try:
        payload = decode_token(req.refresh_token, config.secret_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not available")
    access = create_access_token(user.id, user.username, user.role.value, user.department_id, user.tenant_id, config)
    refresh_token = create_refresh_token(user.id, config)
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.get("/me", response_model=UserInfoResponse)
async def get_me(user: User = Depends(get_current_user)):
    return _user_to_response(user)


@router.put("/me/password")
async def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")
    user.password_hash = hash_password(req.new_password)
    db.add(user)
    await db.flush()
    return {"message": "Password changed successfully"}
