from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.admin.models.user import User, UserStatus

router = APIRouter(prefix="/api/users", tags=["users"])


class ShareUserResponse(BaseModel):
    id: str
    username: str
    display_name: str


class ShareUserListResponse(BaseModel):
    users: list[ShareUserResponse]


@router.get("/search", response_model=ShareUserListResponse)
async def search_share_users(
    request: Request,
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> ShareUserListResponse:
    session_factory = getattr(request.app.state, "admin_session_factory", None)
    if session_factory is None:
        return ShareUserListResponse(users=[])

    current_user = getattr(request.state, "user", None)
    current_user_id = None
    raw_current_user_id = getattr(current_user, "id", None) if current_user else None
    if raw_current_user_id:
        try:
            current_user_id = uuid.UUID(str(raw_current_user_id))
        except ValueError:
            current_user_id = None
    async with session_factory() as db:
        q = select(User).where(User.status == UserStatus.ACTIVE)
        if current_user_id is not None:
            q = q.where(User.id != current_user_id)
        if search:
            pattern = f"%{search}%"
            q = q.where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))
        q = q.order_by(User.username.asc()).limit(limit)
        result = await db.execute(q)
        users = list(result.scalars().all())

    return ShareUserListResponse(
        users=[
            ShareUserResponse(
                id=str(user.id),
                username=user.username,
                display_name=user.display_name,
            )
            for user in users
        ]
    )
