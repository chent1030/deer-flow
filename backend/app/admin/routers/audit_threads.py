import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_db, require_role
from app.admin.models.base import now_utc8
from app.admin.models.user import User, UserRole
from app.admin.schemas.thread import (
    DailyMessageStatsPoint,
    DailyStatsPoint,
    ThreadAuditListResponse,
    ThreadAuditResponse,
    ThreadMessageListResponse,
    ThreadMessageResponse,
    ThreadStatsChartResponse,
    ThreadStatsResponse,
)
from app.admin.services import thread_service

router = APIRouter(prefix="/api/admin/audit/threads", tags=["audit-threads"])
logger = logging.getLogger(__name__)


def _parse_date_range(
    start_date: str | None = None,
    end_date: str | None = None,
    quick: str | None = None,
) -> tuple[datetime, datetime]:
    now = now_utc8()
    if quick:
        mapping = {
            "7d": timedelta(days=7),
            "last_week": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "6m": timedelta(days=180),
            "1y": timedelta(days=365),
        }
        delta = mapping.get(quick, timedelta(days=7))
        return now - delta, now
    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else now - timedelta(days=7)
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) if end_date else now
    return start, end


@router.get("", response_model=ThreadAuditListResponse)
async def list_audit_threads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    start = end = None
    if start_date or end_date:
        start, end = _parse_date_range(start_date, end_date)

    records, total = await thread_service.list_audit_threads(
        db,
        offset=offset,
        limit=page_size,
        user_id=user_id,
        start_date=start,
        end_date=end,
        search=search,
    )

    return ThreadAuditListResponse(
        items=[ThreadAuditResponse.model_validate(record) for record in records],
        total=total,
    )


@router.get("/stats", response_model=ThreadStatsResponse)
async def get_thread_stats_summary(
    start_date: str | None = None,
    end_date: str | None = None,
    quick: str | None = None,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    start, end = _parse_date_range(start_date, end_date, quick)
    data = await thread_service.get_thread_stats(db, start, end)
    return ThreadStatsResponse(**data)


@router.get("/stats/chart", response_model=ThreadStatsChartResponse)
async def get_thread_stats_chart(
    start_date: str | None = None,
    end_date: str | None = None,
    quick: str | None = None,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    start, end = _parse_date_range(start_date, end_date, quick)
    thread_stats = await thread_service.get_daily_thread_stats(db, start, end)
    message_stats = await thread_service.get_daily_message_stats(db, start, end)
    return ThreadStatsChartResponse(
        thread_stats=[DailyStatsPoint(**s) for s in thread_stats],
        message_stats=[DailyMessageStatsPoint(**s) for s in message_stats],
    )


@router.get("/{thread_id}/messages", response_model=ThreadMessageListResponse)
async def get_audit_thread_messages(
    thread_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if not await thread_service.audit_thread_exists(db, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")

    offset = (page - 1) * page_size
    messages, total = await thread_service.get_audit_thread_messages(db, thread_id, offset=offset, limit=page_size)

    return ThreadMessageListResponse(
        items=[ThreadMessageResponse.model_validate(m) for m in messages],
        total=total,
    )
