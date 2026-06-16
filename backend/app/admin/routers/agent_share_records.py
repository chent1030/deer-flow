from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.admin.deps import get_db, require_role
from app.admin.models.agent_share import AgentShareRecord
from app.admin.models.user import User, UserRole
from app.admin.schemas.agent_share import AgentShareRecordListResponse, AgentShareRecordResponse

router = APIRouter(prefix="/api/admin/agent-share-records", tags=["agent-share-records"])


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _to_response(record: AgentShareRecord) -> AgentShareRecordResponse:
    source_owner = getattr(record, "source_owner", None)
    target_user = getattr(record, "target_user", None)
    return AgentShareRecordResponse(
        id=str(record.id),
        source_owner_id=str(record.source_owner_id),
        source_owner_username=getattr(source_owner, "username", None),
        source_owner_display_name=getattr(source_owner, "display_name", None),
        source_agent_name=record.source_agent_name,
        target_user_id=str(record.target_user_id),
        target_username=getattr(target_user, "username", None),
        target_display_name=getattr(target_user, "display_name", None),
        target_agent_name=record.target_agent_name,
        status=record.status.value if hasattr(record.status, "value") else str(record.status),
        error_message=record.error_message,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.get("", response_model=AgentShareRecordListResponse)
async def list_agent_share_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source_owner_id: uuid.UUID | None = Query(default=None),
    target_user_id: uuid.UUID | None = Query(default=None),
    source_agent_name: str | None = Query(default=None),
    target_agent_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    q = select(AgentShareRecord).options(joinedload(AgentShareRecord.source_owner), joinedload(AgentShareRecord.target_user))
    count_q = select(func.count()).select_from(AgentShareRecord)

    if source_owner_id is not None:
        q = q.where(AgentShareRecord.source_owner_id == source_owner_id)
        count_q = count_q.where(AgentShareRecord.source_owner_id == source_owner_id)
    if target_user_id is not None:
        q = q.where(AgentShareRecord.target_user_id == target_user_id)
        count_q = count_q.where(AgentShareRecord.target_user_id == target_user_id)
    if source_agent_name:
        q = q.where(AgentShareRecord.source_agent_name.ilike(f"%{source_agent_name}%"))
        count_q = count_q.where(AgentShareRecord.source_agent_name.ilike(f"%{source_agent_name}%"))
    if target_agent_name:
        q = q.where(AgentShareRecord.target_agent_name.ilike(f"%{target_agent_name}%"))
        count_q = count_q.where(AgentShareRecord.target_agent_name.ilike(f"%{target_agent_name}%"))
    if status:
        q = q.where(AgentShareRecord.status == status)
        count_q = count_q.where(AgentShareRecord.status == status)

    created_from_dt = _parse_time(created_from)
    created_to_dt = _parse_time(created_to)
    if created_from_dt is not None:
        q = q.where(AgentShareRecord.created_at >= created_from_dt)
        count_q = count_q.where(AgentShareRecord.created_at >= created_from_dt)
    if created_to_dt is not None:
        q = q.where(AgentShareRecord.created_at <= created_to_dt)
        count_q = count_q.where(AgentShareRecord.created_at <= created_to_dt)

    offset = (page - 1) * page_size
    q = q.order_by(AgentShareRecord.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(q)
    records = list(result.scalars().all())
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    return AgentShareRecordListResponse(
        items=[_to_response(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )
