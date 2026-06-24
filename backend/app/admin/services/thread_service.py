from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import String, cast, exists, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models.base import now_utc8
from app.admin.models.thread import Thread, ThreadMessage
from app.admin.models.user import User, UserRole
from deerflow.persistence.models.run_event import RunEventRow
from deerflow.persistence.run.model import RunRow
from deerflow.persistence.thread_meta.model import ThreadMetaRow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditThreadRecord:
    id: str
    user_id: str
    title: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    username: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class AuditMessageRecord:
    id: str
    thread_id: str
    role: str
    content: str | None
    raw_content: dict | None
    token_count: int | None
    created_at: datetime


def _legacy_thread_is_not_runtime():
    return ~exists(select(1).select_from(ThreadMetaRow).where(ThreadMetaRow.thread_id == Thread.id))


def _legacy_message_is_not_runtime():
    return ~exists(select(1).select_from(ThreadMetaRow).where(ThreadMetaRow.thread_id == ThreadMessage.thread_id))


def _day_expr(db: AsyncSession, column):
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        return func.date(column)
    return func.date_trunc("day", column)


def _date_key(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def _message_role(event_type: str, content) -> str:
    if isinstance(content, dict):
        msg_type = content.get("type")
        if msg_type == "human":
            return "user"
        if msg_type == "ai":
            return "assistant"
        if msg_type == "tool":
            return "tool"
    if "human" in event_type:
        return "user"
    if "ai" in event_type:
        return "assistant"
    if "tool" in event_type:
        return "tool"
    return "system"


def _decode_event_content(raw: str, metadata: dict | None):
    metadata = metadata or {}
    if metadata.get("content_is_json") or metadata.get("content_is_dict"):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw
    return raw


def _content_text(content) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        value = content.get("content")
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return _content_text(value)
        text = content.get("text")
        if isinstance(text, str):
            return text
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _content_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts) if parts else None
    return str(content)


def _event_token_count(metadata: dict | None) -> int | None:
    usage = (metadata or {}).get("usage")
    if not isinstance(usage, dict):
        return None
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if isinstance(input_tokens, int) or isinstance(output_tokens, int):
        return (input_tokens or 0) + (output_tokens or 0)
    return None


async def _load_user_names(db: AsyncSession, user_ids: list[str]) -> dict[str, tuple[str | None, str | None]]:
    uuids = [uid for uid in (_safe_uuid(v) for v in user_ids) if uid is not None]
    if not uuids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(uuids)))
    return {str(user.id): (user.username, user.display_name) for user in result.scalars().all()}


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


async def audit_thread_exists(db: AsyncSession, thread_id: str) -> bool:
    runtime = await db.get(ThreadMetaRow, thread_id)
    if runtime is not None and runtime.status != "deleted":
        return True
    legacy = await db.get(Thread, thread_id)
    return legacy is not None and legacy.status != "deleted"


async def list_audit_threads(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 50,
    user_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
) -> tuple[list[AuditThreadRecord], int]:
    run_counts = (
        select(
            RunRow.thread_id.label("thread_id"),
            func.coalesce(func.sum(RunRow.message_count), 0).label("message_count"),
            func.max(RunRow.updated_at).label("last_run_at"),
        )
        .group_by(RunRow.thread_id)
        .subquery()
    )

    runtime_q = (
        select(
            ThreadMetaRow.thread_id.label("id"),
            ThreadMetaRow.user_id.label("user_id"),
            ThreadMetaRow.display_name.label("title"),
            ThreadMetaRow.status.label("status"),
            func.coalesce(run_counts.c.message_count, 0).label("message_count"),
            ThreadMetaRow.created_at.label("created_at"),
            func.coalesce(run_counts.c.last_run_at, ThreadMetaRow.updated_at).label("updated_at"),
        )
        .outerjoin(run_counts, run_counts.c.thread_id == ThreadMetaRow.thread_id)
        .where(ThreadMetaRow.status != "deleted")
    )
    legacy_q = (
        select(
            Thread.id.label("id"),
            cast(Thread.user_id, String).label("user_id"),
            Thread.title.label("title"),
            Thread.status.label("status"),
            Thread.message_count.label("message_count"),
            Thread.created_at.label("created_at"),
            Thread.updated_at.label("updated_at"),
        )
        .where(Thread.status != "deleted", _legacy_thread_is_not_runtime())
    )

    if user_id:
        runtime_q = runtime_q.where(ThreadMetaRow.user_id == user_id)
        uid = _safe_uuid(user_id)
        legacy_q = legacy_q.where(Thread.user_id == uid) if uid else legacy_q.where(False)
    if start_date is not None:
        runtime_q = runtime_q.where(ThreadMetaRow.created_at >= start_date)
        legacy_q = legacy_q.where(Thread.created_at >= start_date)
    if end_date is not None:
        runtime_q = runtime_q.where(ThreadMetaRow.created_at <= end_date)
        legacy_q = legacy_q.where(Thread.created_at <= end_date)
    if search:
        pattern = f"%{search}%"
        runtime_q = runtime_q.where(ThreadMetaRow.display_name.ilike(pattern))
        legacy_q = legacy_q.where(Thread.title.ilike(pattern))

    combined = union_all(runtime_q, legacy_q).subquery()
    total_result = await db.execute(select(func.count()).select_from(combined))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(combined)
        .order_by(combined.c.updated_at.desc(), combined.c.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.mappings().all()
    users = await _load_user_names(db, [str(row["user_id"]) for row in rows if row["user_id"]])
    records = []
    for row in rows:
        row_user_id = str(row["user_id"] or "")
        username, display_name = users.get(row_user_id, (None, None))
        records.append(
            AuditThreadRecord(
                id=str(row["id"]),
                user_id=row_user_id,
                title=row["title"],
                status=str(row["status"]),
                message_count=int(row["message_count"] or 0),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                username=username,
                display_name=display_name,
            )
        )
    return records, total


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


async def get_audit_thread_messages(
    db: AsyncSession,
    thread_id: str,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[AuditMessageRecord | ThreadMessage], int]:
    runtime = await db.get(ThreadMetaRow, thread_id)
    if runtime is None:
        result = await db.execute(
            select(ThreadMessage)
            .where(ThreadMessage.thread_id == thread_id)
            .order_by(ThreadMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        count_result = await db.execute(select(func.count()).select_from(ThreadMessage).where(ThreadMessage.thread_id == thread_id))
        return list(result.scalars().all()), count_result.scalar() or 0

    records: list[AuditMessageRecord] = []
    events_result = await db.execute(
        select(RunEventRow)
        .where(RunEventRow.thread_id == thread_id, RunEventRow.category == "message")
        .order_by(RunEventRow.seq.asc())
    )
    for event in events_result.scalars().all():
        content = _decode_event_content(event.content, event.event_metadata)
        raw_content = {
            "run_id": event.run_id,
            "event_type": event.event_type,
            "seq": event.seq,
            "metadata": event.event_metadata or {},
            "content": content,
        }
        records.append(
            AuditMessageRecord(
                id=str(event.id),
                thread_id=thread_id,
                role=_message_role(event.event_type, content),
                content=_content_text(content),
                raw_content=raw_content,
                token_count=_event_token_count(event.event_metadata),
                created_at=event.created_at,
            )
        )
    if records:
        return records[offset : offset + limit], len(records)

    result = await db.execute(select(RunRow).where(RunRow.thread_id == thread_id).order_by(RunRow.created_at.asc(), RunRow.run_id.asc()))
    for run in result.scalars().all():
        if run.first_human_message:
            records.append(
                AuditMessageRecord(
                    id=f"{run.run_id}:user",
                    thread_id=thread_id,
                    role="user",
                    content=run.first_human_message,
                    raw_content={"run_id": run.run_id, "status": run.status},
                    token_count=None,
                    created_at=run.created_at,
                )
            )
        if run.last_ai_message:
            records.append(
                AuditMessageRecord(
                    id=f"{run.run_id}:assistant",
                    thread_id=thread_id,
                    role="assistant",
                    content=run.last_ai_message,
                    raw_content={"run_id": run.run_id, "status": run.status},
                    token_count=run.total_tokens or None,
                    created_at=run.updated_at,
                )
            )
    return records[offset : offset + limit], len(records)


async def get_thread_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    runtime_threads_q = (
        select(func.count())
        .select_from(ThreadMetaRow)
        .where(
            ThreadMetaRow.status != "deleted",
            ThreadMetaRow.created_at >= start_date,
            ThreadMetaRow.created_at <= end_date,
        )
    )
    runtime_threads_result = await db.execute(runtime_threads_q)
    runtime_threads = runtime_threads_result.scalar() or 0

    legacy_threads_q = (
        select(func.count())
        .select_from(Thread)
        .where(
            Thread.status != "deleted",
            _legacy_thread_is_not_runtime(),
            Thread.created_at >= start_date,
            Thread.created_at <= end_date,
        )
    )
    legacy_threads_result = await db.execute(legacy_threads_q)
    legacy_threads = legacy_threads_result.scalar() or 0

    runtime_messages_q = (
        select(func.coalesce(func.sum(RunRow.message_count), 0))
        .select_from(RunRow)
        .where(
            RunRow.created_at >= start_date,
            RunRow.created_at <= end_date,
        )
    )
    runtime_messages_result = await db.execute(runtime_messages_q)
    runtime_messages = runtime_messages_result.scalar() or 0

    legacy_messages_q = (
        select(func.count())
        .select_from(ThreadMessage)
        .where(
            _legacy_message_is_not_runtime(),
            ThreadMessage.created_at >= start_date,
            ThreadMessage.created_at <= end_date,
        )
    )
    legacy_messages_result = await db.execute(legacy_messages_q)
    legacy_messages = legacy_messages_result.scalar() or 0

    runtime_users_q = select(ThreadMetaRow.user_id.label("user_id")).where(
        ThreadMetaRow.status != "deleted",
        ThreadMetaRow.user_id.is_not(None),
        ThreadMetaRow.created_at >= start_date,
        ThreadMetaRow.created_at <= end_date,
    )
    legacy_users_q = (
        select(cast(Thread.user_id, String).label("user_id"))
        .where(
            Thread.status != "deleted",
            _legacy_thread_is_not_runtime(),
            Thread.created_at >= start_date,
            Thread.created_at <= end_date,
        )
    )
    users_subq = union_all(runtime_users_q, legacy_users_q).subquery()
    active_users_result = await db.execute(select(func.count(func.distinct(users_subq.c.user_id))).select_from(users_subq))
    active_users = active_users_result.scalar() or 0

    return {
        "total_threads": int(runtime_threads) + int(legacy_threads),
        "total_messages": int(runtime_messages) + int(legacy_messages),
        "active_users": active_users,
    }


async def get_daily_thread_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    runtime_day = _day_expr(db, ThreadMetaRow.created_at).label("date")
    legacy_day = _day_expr(db, Thread.created_at).label("date")
    runtime_q = (
        select(runtime_day, func.count().label("thread_count"))
        .where(ThreadMetaRow.status != "deleted", ThreadMetaRow.created_at >= start_date, ThreadMetaRow.created_at <= end_date)
        .group_by(runtime_day)
    )
    legacy_q = (
        select(legacy_day, func.count().label("thread_count"))
        .where(Thread.status != "deleted", _legacy_thread_is_not_runtime(), Thread.created_at >= start_date, Thread.created_at <= end_date)
        .group_by(legacy_day)
    )
    totals: dict[str, int] = {}
    for query in (runtime_q, legacy_q):
        result = await db.execute(query)
        for row in result:
            key = _date_key(row.date)
            totals[key] = totals.get(key, 0) + int(row.thread_count or 0)
    return [{"date": key, "thread_count": totals[key]} for key in sorted(totals)]


async def get_daily_message_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    runtime_day = _day_expr(db, RunRow.created_at).label("date")
    legacy_day = _day_expr(db, ThreadMessage.created_at).label("date")
    runtime_q = (
        select(runtime_day, func.coalesce(func.sum(RunRow.message_count), 0).label("message_count"))
        .where(RunRow.created_at >= start_date, RunRow.created_at <= end_date)
        .group_by(runtime_day)
    )
    legacy_q = (
        select(legacy_day, func.count().label("message_count"))
        .where(_legacy_message_is_not_runtime(), ThreadMessage.created_at >= start_date, ThreadMessage.created_at <= end_date)
        .group_by(legacy_day)
    )
    totals: dict[str, int] = {}
    for query in (runtime_q, legacy_q):
        result = await db.execute(query)
        for row in result:
            key = _date_key(row.date)
            totals[key] = totals.get(key, 0) + int(row.message_count or 0)
    return [{"date": key, "message_count": totals[key]} for key in sorted(totals)]
