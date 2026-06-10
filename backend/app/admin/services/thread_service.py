from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models.base import now_utc8
from app.admin.models.thread import Thread, ThreadMessage
from app.admin.models.user import UserRole

logger = logging.getLogger(__name__)


async def create_thread_record(
    db: AsyncSession,
    thread_id: str,
    user_id: uuid.UUID,
    title: str | None = None,
) -> Thread:
    existing = await db.get(Thread, thread_id)
    if existing:
        return existing
    thread = Thread(
        id=thread_id,
        user_id=user_id,
        title=title,
        status="active",
        message_count=0,
    )
    db.add(thread)
    await db.flush()
    return thread


async def get_thread(db: AsyncSession, thread_id: str) -> Thread | None:
    return await db.get(Thread, thread_id)


async def list_threads_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_role: str,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Thread], int]:
    base_q = select(Thread).where(Thread.status != "deleted")
    count_q = select(func.count()).select_from(Thread).where(Thread.status != "deleted")

    if user_role != UserRole.SUPER_ADMIN.value:
        base_q = base_q.where(Thread.user_id == user_id)
        count_q = count_q.where(Thread.user_id == user_id)

    base_q = base_q.order_by(Thread.updated_at.desc()).offset(offset).limit(limit)

    result = await db.execute(base_q)
    threads = list(result.scalars().all())

    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    return threads, total


async def soft_delete_thread(db: AsyncSession, thread_id: str) -> Thread | None:
    thread = await db.get(Thread, thread_id)
    if thread is None:
        return None
    thread.status = "deleted"
    await db.flush()
    return thread


async def update_thread_title(db: AsyncSession, thread_id: str, title: str) -> Thread | None:
    thread = await db.get(Thread, thread_id)
    if thread is None:
        return None
    thread.title = title
    await db.flush()
    return thread


async def record_message(
    db: AsyncSession,
    thread_id: str,
    role: str,
    content: str | None,
    raw_content: dict | None = None,
    token_count: int | None = None,
) -> ThreadMessage:
    msg = ThreadMessage(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        role=role,
        content=content,
        raw_content=raw_content,
        token_count=token_count,
    )
    db.add(msg)
    thread = await db.get(Thread, thread_id)
    if thread:
        thread.message_count = (thread.message_count or 0) + 1
        thread.updated_at = now_utc8()
    await db.flush()
    return msg


async def get_thread_messages(
    db: AsyncSession,
    thread_id: str,
    offset: int = 0,
    limit: int = 100,
) -> list[ThreadMessage]:
    result = await db.execute(select(ThreadMessage).where(ThreadMessage.thread_id == thread_id).order_by(ThreadMessage.created_at.asc()).offset(offset).limit(limit))
    return list(result.scalars().all())


async def get_thread_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    threads_q = (
        select(func.count())
        .select_from(Thread)
        .where(
            Thread.created_at >= start_date,
            Thread.created_at <= end_date,
        )
    )
    threads_result = await db.execute(threads_q)
    total_threads = threads_result.scalar() or 0

    messages_q = (
        select(func.count())
        .select_from(ThreadMessage)
        .where(
            ThreadMessage.created_at >= start_date,
            ThreadMessage.created_at <= end_date,
        )
    )
    messages_result = await db.execute(messages_q)
    total_messages = messages_result.scalar() or 0

    active_users_q = (
        select(func.count(func.distinct(Thread.user_id)))
        .select_from(Thread)
        .where(
            Thread.created_at >= start_date,
            Thread.created_at <= end_date,
        )
    )
    active_users_result = await db.execute(active_users_q)
    active_users = active_users_result.scalar() or 0

    return {
        "total_threads": total_threads,
        "total_messages": total_messages,
        "active_users": active_users,
    }


async def get_daily_thread_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    day_trunc = func.date_trunc("day", Thread.created_at).label("date")
    q = select(day_trunc, func.count().label("thread_count")).where(Thread.created_at >= start_date, Thread.created_at <= end_date).group_by(day_trunc).order_by(day_trunc)
    result = await db.execute(q)
    return [{"date": str(row.date.date()), "thread_count": row.thread_count} for row in result]


async def get_daily_message_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    day_trunc = func.date_trunc("day", ThreadMessage.created_at).label("date")
    q = select(day_trunc, func.count().label("message_count")).where(ThreadMessage.created_at >= start_date, ThreadMessage.created_at <= end_date).group_by(day_trunc).order_by(day_trunc)
    result = await db.execute(q)
    return [{"date": str(row.date.date()), "message_count": row.message_count} for row in result]
