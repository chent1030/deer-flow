import logging
import uuid
from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin.auth.jwt import decode_token
from app.admin.auth.middleware import get_token_from_request
from app.admin.config import AdminConfig
from app.admin.models.user import User, UserRole, UserStatus
from deerflow.config import get_app_config

logger = logging.getLogger(__name__)


def _get_admin_config() -> AdminConfig:
    return get_app_config().admin


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from app.gateway.app import get_app

    app = get_app()
    session_factory: async_sessionmaker[AsyncSession] = app.state.admin_session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = await get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    config = _get_admin_config().jwt
    try:
        payload = decode_token(token, config.secret_key)
    except jwt.InvalidTokenError:
        logger.debug("Failed to decode JWT token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        logger.debug("Invalid UUID in token subject: %s", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return user


def require_role(*roles: UserRole):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker
