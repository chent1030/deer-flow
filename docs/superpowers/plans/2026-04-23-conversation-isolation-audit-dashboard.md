# 对话隔离、全量审计与管理面板仪表板 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现对话用户隔离、全量消息审计、管理面板对话统计图表、LangGraph 存储迁移到 PostgreSQL、用户画像独立

**Architecture:** 在 PostgreSQL 中建立 threads 和 thread_messages 审计表，Gateway 层实时双写消息记录。线程 CRUD 加认证和所有权校验。前端线程列表改为通过 Gateway 代理按用户过滤。Checkpointer 从 SQLite 迁移到 PostgreSQL。管理面板增加对话审计页面和 ECharts 统计图表。

**Tech Stack:** Python 3.12 + SQLAlchemy + Alembic (后端), React + Ant Design + ECharts (管理面板), Next.js + LangGraph SDK (前端), PostgreSQL (统一存储)

---

## Task 1: 配置 Checkpointer 迁移到 PostgreSQL

**Files:**
- Modify: `backend/packages/harness/pyproject.toml`
- Modify: `config.yaml`

- [ ] **Step 1: 添加 PostgreSQL checkpointer 依赖**

在 `backend/packages/harness/pyproject.toml` 的 dependencies 中添加 `langgraph-checkpoint-postgres`:

```toml
dependencies = [
    # ... existing deps ...
    "langgraph-checkpoint-sqlite>=3.0.3",
    "langgraph-checkpoint-postgres>=2.0.0",
]
```

- [ ] **Step 2: 安装依赖**

```bash
cd backend && uv sync
```

- [ ] **Step 3: 修改 config.yaml checkpointer 配置**

将 `config.yaml` 中的 checkpointer 从 sqlite 改为 postgres:

```yaml
checkpointer:
  type: postgres
  connection_string: postgresql+asyncpg://deerflow:deerflow@localhost:5432/deerflow_checkpoints
```

注意：checkpointer 使用独立的数据库 `deerflow_checkpoints`，与 admin 数据库 `deerflow_admin` 分开（LangGraph checkpointer 会自动创建表结构，避免与 admin migration 冲突）。

- [ ] **Step 4: 创建 checkpointer 数据库**

```bash
psql -U deerflow -h localhost -p 5432 -d postgres -c "CREATE DATABASE deerflow_checkpoints;" 2>/dev/null || true
```

- [ ] **Step 5: 验证 async_provider postgres 分支可用**

读取 `backend/packages/harness/deerflow/agents/checkpointer/async_provider.py` 确认已有 postgres 分支，`langgraph-checkpoint-postgres` 包导入路径为 `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver`。

同样检查 `backend/packages/harness/deerflow/runtime/store/async_provider.py` 的 postgres 分支，确认 store 也能用 postgres（`AsyncPostgresStore`）。

- [ ] **Step 6: 启动 Gateway 验证 checkpointer 连接**

```bash
cd backend && make gateway
```

查看日志确认无连接错误。

- [ ] **Step 7: Commit**

```bash
git add backend/packages/harness/pyproject.toml config.yaml backend/uv.lock
git commit -m "feat: migrate checkpointer from SQLite to PostgreSQL"
```

---

## Task 2: 创建 threads 和 thread_messages 数据模型 + Migration

**Files:**
- Create: `backend/app/admin/models/thread.py`
- Modify: `backend/app/admin/models/__init__.py`
- Create: `backend/alembic/versions/xxxx_add_threads_tables.py` (via autogenerate)

- [ ] **Step 1: 创建 Thread 模型**

创建 `backend/app/admin/models/thread.py`:

```python
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.admin.models.base import Base, TimestampMixin, now_utc8


class Thread(TimestampMixin, Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User", lazy="selectin")
    messages = relationship("ThreadMessage", back_populates="thread", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("idx_threads_user_id", "user_id"),
        Index("idx_threads_created_at", "created_at"),
        Index("idx_threads_status", "status"),
    )


class ThreadMessage(Base):
    __tablename__ = "thread_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc8)

    thread = relationship("Thread", back_populates="messages")

    __table_args__ = (
        Index("idx_thread_messages_thread_id", "thread_id"),
        Index("idx_thread_messages_created_at", "created_at"),
        Index("idx_thread_messages_role", "role"),
    )
```

- [ ] **Step 2: 更新 models __init__.py**

修改 `backend/app/admin/models/__init__.py` 添加新模型的导出:

```python
from app.admin.models.base import Base, TenantMixin, TimestampMixin
from app.admin.models.department import Department
from app.admin.models.skill import Skill, SkillStatus, SkillVisibility, SkillVisibleUser
from app.admin.models.thread import Thread, ThreadMessage
from app.admin.models.user import User, UserRole, UserStatus

__all__ = [
    "Base",
    "Department",
    "Skill",
    "SkillStatus",
    "SkillVisibility",
    "SkillVisibleUser",
    "TenantMixin",
    "Thread",
    "ThreadMessage",
    "TimestampMixin",
    "User",
    "UserRole",
    "UserStatus",
]
```

- [ ] **Step 3: 生成 Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_threads_and_thread_messages_tables"
```

检查生成的 migration 文件，确认包含 `threads` 和 `thread_messages` 表的 CREATE TABLE 以及索引。

- [ ] **Step 4: 执行 migration**

```bash
cd backend && uv run alembic upgrade head
```

- [ ] **Step 5: 验证表已创建**

```bash
psql -U deerflow -h localhost -p 5432 -d deerflow_admin -c "\dt threads; \dt thread_messages;"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/admin/models/thread.py backend/app/admin/models/__init__.py backend/alembic/
git commit -m "feat: add Thread and ThreadMessage models with migration"
```

---

## Task 3: 创建 Thread CRUD Service

**Files:**
- Create: `backend/app/admin/services/thread_service.py`

- [ ] **Step 1: 编写 thread_service.py**

创建 `backend/app/admin/services/thread_service.py`:

```python
import uuid
from datetime import datetime
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
    user_id: str,
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
    user_id: str,
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
    result = await db.execute(
        select(ThreadMessage)
        .where(ThreadMessage.thread_id == thread_id)
        .order_by(ThreadMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_thread_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    threads_q = select(func.count()).select_from(Thread).where(
        Thread.created_at >= start_date,
        Thread.created_at <= end_date,
    )
    threads_result = await db.execute(threads_q)
    total_threads = threads_result.scalar() or 0

    messages_q = select(func.count()).select_from(ThreadMessage).where(
        ThreadMessage.created_at >= start_date,
        ThreadMessage.created_at <= end_date,
    )
    messages_result = await db.execute(messages_q)
    total_messages = messages_result.scalar() or 0

    active_users_q = select(func.count(func.distinct(Thread.user_id))).select_from(Thread).where(
        Thread.created_at >= start_date,
        Thread.created_at <= end_date,
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
    q = (
        select(
            func.date_trunc("day", Thread.created_at).label("date"),
            func.count().label("thread_count"),
        )
        .where(Thread.created_at >= start_date, Thread.created_at <= end_date)
        .group_by(func.date_trunc("day", Thread.created_at))
        .order_by(func.date_trunc("day", Thread.created_at))
    )
    result = await db.execute(q)
    return [{"date": str(row.date.date()), "thread_count": row.thread_count} for row in result]


async def get_daily_message_stats(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    q = (
        select(
            func.date_trunc("day", ThreadMessage.created_at).label("date"),
            func.count().label("message_count"),
        )
        .where(ThreadMessage.created_at >= start_date, ThreadMessage.created_at <= end_date)
        .group_by(func.date_trunc("day", ThreadMessage.created_at))
        .order_by(func.date_trunc("day", ThreadMessage.created_at))
    )
    result = await db.execute(q)
    return [{"date": str(row.date.date()), "message_count": row.message_count} for row in result]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/admin/services/thread_service.py
git commit -m "feat: add thread_service with CRUD, message recording, and stats"
```

---

## Task 4: Thread CRUD 路由加认证 + 所有权校验

**Files:**
- Modify: `backend/app/gateway/routers/threads.py`

- [ ] **Step 1: 添加认证依赖到 thread router**

在 `threads.py` 顶部添加导入:

```python
from app.admin.deps import get_current_user, get_db
from app.admin.models.user import User, UserRole
from app.admin.services import thread_service
from sqlalchemy.ext.asyncio import AsyncSession
```

- [ ] **Step 2: 修改 create_thread 端点**

将 `create_thread` 函数签名改为:

```python
@router.post("", response_model=ThreadResponse)
async def create_thread(
    body: ThreadCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
```

在创建 LangGraph thread 之后、返回之前，调用 thread_service:

```python
    await thread_service.create_thread_record(
        db, thread_id=thread_id, user_id=str(current_user.id),
    )
```

- [ ] **Step 3: 修改 search_threads 端点**

将函数签名改为:

```python
@router.post("/search", response_model=list[ThreadResponse])
async def search_threads(
    body: ThreadSearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThreadResponse]:
```

在 Phase 3 (Filter → sort → paginate) 部分，添加用户过滤逻辑:

```python
    results = list(merged.values())

    if body.metadata:
        results = [r for r in results if all(r.metadata.get(k) == v for k, v in body.metadata.items())]

    if body.status:
        results = [r for r in results if r.status == body.status]

    if current_user.role.value != UserRole.SUPER_ADMIN.value:
        user_thread_ids_result = await db.execute(
            select(Thread.id).where(Thread.user_id == str(current_user.id))
        )
        user_thread_ids = {row[0] for row in user_thread_ids_result}
        results = [r for r in results if r.thread_id in user_thread_ids]

    results.sort(key=lambda r: r.updated_at, reverse=True)
    return results[body.offset : body.offset + body.limit]
```

需要在顶部添加 `from sqlalchemy import select` 和 `from app.admin.models.thread import Thread`。

- [ ] **Step 4: 修改 get_thread_state 和 get_thread_history 端点**

在 `get_thread_state` (PATCH `/{thread_id}/state`) 和 `get_thread_history` (POST `/{thread_id}/history`) 端点的函数签名中添加 `current_user: User = Depends(get_current_user)` 和 `db: AsyncSession = Depends(get_db)`。

在每个端点的开头添加所有权校验:

```python
    thread_record = await thread_service.get_thread(db, thread_id)
    if thread_record and str(thread_record.user_id) != str(current_user.id):
        if current_user.role.value != UserRole.SUPER_ADMIN.value:
            raise HTTPException(status_code=403, detail="无权访问此对话")
```

- [ ] **Step 5: 修改 delete_thread 端点**

```python
@router.delete("/{thread_id}", response_model=ThreadDeleteResponse)
async def delete_thread_data(
    thread_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadDeleteResponse:
```

在删除前校验所有权:

```python
    thread_record = await thread_service.get_thread(db, thread_id)
    if thread_record and str(thread_record.user_id) != str(current_user.id):
        if current_user.role.value != UserRole.SUPER_ADMIN.value:
            raise HTTPException(status_code=403, detail="无权删除此对话")
    if thread_record:
        await thread_service.soft_delete_thread(db, thread_id)
```

- [ ] **Step 6: 运行 lint**

```bash
cd backend && make lint
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/gateway/routers/threads.py
git commit -m "feat: add auth and ownership to thread CRUD endpoints"
```

---

## Task 5: Gateway start_run 消息审计双写

**Files:**
- Modify: `backend/app/gateway/services.py`

- [ ] **Step 1: 在 start_run 中添加消息审计**

在 `services.py` 的 `start_run` 函数中，找到 `if current_user is not None:` 代码块（约 line 308），在注入 username 和 visible_skills 之后，添加消息审计逻辑。

首先在文件顶部添加导入:

```python
from app.admin.services import thread_service as audit_thread_service
```

在 `current_user` 代码块的末尾（约 line 325 之后），添加创建 thread 记录的逻辑:

```python
    if current_user is not None:
        configurable = config.setdefault("configurable", {})
        configurable.setdefault("username", current_user.username)
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            from app.admin.services import skill_service as admin_skill_service

            async with async_sessionmaker(request.app.state.db_engine)() as db:
                visible_names = await admin_skill_service.list_visible_skills_for_user(
                    db,
                    current_user.id,
                    current_user.role.value,
                    current_user.department_id,
                )
                await audit_thread_service.create_thread_record(
                    db, thread_id=thread_id, user_id=str(current_user.id),
                )
                user_msg = _extract_last_human_message(graph_input)
                if user_msg:
                    await audit_thread_service.record_message(
                        db,
                        thread_id=thread_id,
                        role="user",
                        content=user_msg,
                    )
            configurable.setdefault("visible_skills", visible_names)
        except Exception:
            logger.debug("Failed to fetch visible_skills or record user message for thread %s", thread_id, exc_info=True)
```

- [ ] **Step 2: 添加消息提取辅助函数**

在 `services.py` 中 `normalize_input` 之后添加:

```python
def _extract_last_human_message(graph_input: dict) -> str | None:
    messages = graph_input.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                return " ".join(parts) if parts else None
    return None
```

- [ ] **Step 3: 在流完成后记录 assistant 回复**

在 `_sync_thread_title_after_run` 函数旁边，添加审计辅助函数:

```python
async def _record_assistant_message_audit(
    task: asyncio.Task,
    thread_id: str,
    request: Request,
) -> None:
    try:
        await task
    except Exception:
        return

    try:
        checkpointer = get_checkpointer(request)
        config = {"configurable": {"thread_id": thread_id}}
        ckpt_tuple = await checkpointer.aget_tuple(config)
        if not ckpt_tuple:
            return

        checkpoint = getattr(ckpt_tuple, "checkpoint", {}) or {}
        channel_values = checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])

        from sqlalchemy.ext.asyncio import async_sessionmaker
        async with async_sessionmaker(request.app.state.db_engine)() as db:
            last_ai_msg = None
            for msg in reversed(messages):
                role = ""
                content = ""
                raw = None
                if hasattr(msg, "type"):
                    role = msg.type
                    content = str(msg.content) if isinstance(msg.content, str) else str(msg.content)
                    raw = {"type": msg.type, "content": str(msg.content)}
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        raw["tool_calls"] = [
                            {"name": tc.get("name", ""), "args": tc.get("args", {})}
                            for tc in msg.tool_calls
                        ]
                elif isinstance(msg, dict):
                    role = msg.get("type", "")
                    content = str(msg.get("content", ""))
                    raw = msg
                else:
                    continue

                if role in ("ai", "assistant"):
                    last_ai_msg = (content, raw)
                    break

            if last_ai_msg:
                content, raw = last_ai_msg
                await audit_thread_service.record_message(
                    db,
                    thread_id=thread_id,
                    role="assistant",
                    content=content,
                    raw_content=raw,
                )

            title = channel_values.get("title")
            if title:
                await audit_thread_service.update_thread_title(db, thread_id, title)

    except Exception:
        logger.debug("Failed to record assistant message audit for thread %s", thread_id, exc_info=True)
```

- [ ] **Step 4: 在 start_run 中启动审计 task**

在 `start_run` 函数末尾（`asyncio.create_task(_sync_thread_title_after_run(...))` 之后）添加:

```python
    if current_user is not None and request.app.state.db_engine is not None:
        try:
            asyncio.create_task(_record_assistant_message_audit(task, thread_id, request))
        except Exception:
            pass
```

- [ ] **Step 5: 运行 lint**

```bash
cd backend && make lint
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/gateway/services.py
git commit -m "feat: add message audit dual-write in start_run"
```

---

## Task 6: Thread 审计 API（Admin 后端）

**Files:**
- Create: `backend/app/admin/schemas/thread.py`
- Create: `backend/app/admin/routers/audit_threads.py`
- Modify: `backend/app/gateway/app.py` (注册新路由)

- [ ] **Step 1: 创建 thread schemas**

创建 `backend/app/admin/schemas/thread.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ThreadAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    username: str | None = None
    display_name: str | None = None


class ThreadAuditListResponse(BaseModel):
    items: list[ThreadAuditResponse]
    total: int


class ThreadMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    role: str
    content: str | None
    raw_content: dict | None
    token_count: int | None
    created_at: datetime


class ThreadMessageListResponse(BaseModel):
    items: list[ThreadMessageResponse]
    total: int


class ThreadStatsResponse(BaseModel):
    total_threads: int
    total_messages: int
    active_users: int


class DailyStatsPoint(BaseModel):
    date: str
    thread_count: int


class DailyMessageStatsPoint(BaseModel):
    date: str
    message_count: int


class ThreadStatsChartResponse(BaseModel):
    thread_stats: list[DailyStatsPoint]
    message_stats: list[DailyMessageStatsPoint]
```

- [ ] **Step 2: 创建审计路由**

创建 `backend/app/admin/routers/audit_threads.py`:

```python
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_current_user, get_db, require_role
from app.admin.models.base import UTC8, now_utc8
from app.admin.models.thread import Thread, ThreadMessage
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
    q = select(Thread).where(Thread.status != "deleted")
    count_q = select(func.count()).select_from(Thread).where(Thread.status != "deleted")

    if user_id:
        q = q.where(Thread.user_id == user_id)
        count_q = count_q.where(Thread.user_id == user_id)

    if start_date or end_date:
        start, end = _parse_date_range(start_date, end_date)
        q = q.where(Thread.created_at >= start, Thread.created_at <= end)
        count_q = count_q.where(Thread.created_at >= start, Thread.created_at <= end)

    if search:
        q = q.where(Thread.title.ilike(f"%{search}%"))
        count_q = count_q.where(Thread.title.ilike(f"%{search}%"))

    q = q.order_by(Thread.updated_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(q)
    threads = list(result.scalars().all())

    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    items = []
    for t in threads:
        username = t.user.username if t.user else None
        display_name = t.user.display_name if t.user else None
        items.append(
            ThreadAuditResponse(
                id=t.id,
                user_id=t.user_id,
                title=t.title,
                status=t.status,
                message_count=t.message_count,
                created_at=t.created_at,
                updated_at=t.updated_at,
                username=username,
                display_name=display_name,
            )
        )

    return ThreadAuditListResponse(items=items, total=total)


@router.get("/stats", response_model=ThreadStatsResponse)
async def get_thread_stats_summary(
    start_date: str | None = None,
    end_date: str | None = None,
    quick: str | None = None,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    start, end = _parse_date_range(start_date, end_date, quick)
    return await thread_service.get_thread_stats(db, start, end)


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
    thread = await thread_service.get_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="对话不存在")

    offset = (page - 1) * page_size
    messages = await thread_service.get_thread_messages(db, thread_id, offset=offset, limit=page_size)

    count_q = select(func.count()).select_from(ThreadMessage).where(ThreadMessage.thread_id == thread_id)
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    return ThreadMessageListResponse(
        items=[ThreadMessageResponse.model_validate(m) for m in messages],
        total=total,
    )
```

- [ ] **Step 3: 注册路由**

在 `backend/app/gateway/app.py` 中找到路由注册位置，添加:

```python
from app.admin.routers import audit_threads
app.include_router(audit_threads.router)
```

- [ ] **Step 4: 运行 lint**

```bash
cd backend && make lint
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/admin/schemas/thread.py backend/app/admin/routers/audit_threads.py backend/app/gateway/app.py
git commit -m "feat: add thread audit API endpoints for admin panel"
```

---

## Task 7: 用户画像独立 (USER.md per-user)

**Files:**
- Modify: `backend/packages/harness/deerflow/config/paths.py`
- Modify: `backend/app/gateway/routers/agents.py`

- [ ] **Step 1: 在 paths.py 中添加 per-user profile 路径方法**

在 `paths.py` 的 `Paths` 类中，`user_md_file` 属性之后添加:

```python
    def user_profile_file(self, username: str) -> Path:
        return self.base_dir / "profiles" / _validate_username(username) / "USER.md"
```

注意：`_validate_username` 已在文件中定义（用于 `user_memory_file`）。

- [ ] **Step 2: 修改 agents.py 中的 user-profile 端点**

修改 `get_user_profile` 和 `update_user_profile` 端点，添加 `current_user` 依赖:

```python
from app.admin.deps import get_current_user
from app.admin.models.user import User


@router.get("/user-profile", response_model=UserProfileResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    try:
        paths = get_paths()
        user_md_path = paths.user_profile_file(current_user.username)
        if not user_md_path.exists():
            return UserProfileResponse(content=None)
        raw = user_md_path.read_text(encoding="utf-8").strip()
        return UserProfileResponse(content=raw or None)
    except Exception as e:
        logger.error(f"Failed to read user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read user profile: {str(e)}")


@router.put("/user-profile", response_model=UserProfileResponse)
async def update_user_profile(
    request: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    try:
        paths = get_paths()
        user_md_path = paths.user_profile_file(current_user.username)
        user_md_path.parent.mkdir(parents=True, exist_ok=True)
        user_md_path.write_text(request.content, encoding="utf-8")
        logger.info(f"Updated USER.md for user {current_user.username} at {user_md_path}")
        return UserProfileResponse(content=request.content or None)
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")
```

- [ ] **Step 3: 在 prompt.py 中注入 per-user 画像**

找到 `apply_prompt_template` 函数中 `_get_memory_context` 的调用位置。在 memory context 之后，添加用户画像加载:

```python
    user_profile = _load_user_profile(username)
```

添加辅助函数:

```python
def _load_user_profile(username: str | None) -> str:
    if not username:
        return ""
    try:
        paths = get_paths()
        user_md_path = paths.user_profile_file(username)
        if user_md_path.exists():
            content = user_md_path.read_text(encoding="utf-8").strip()
            if content:
                return f"<user-profile>\n{content}\n</user-profile>\n"
    except Exception:
        pass
    return ""
```

在 `apply_prompt_template` 的返回模板字符串中，在 memory_context 之后注入 `user_profile`。

- [ ] **Step 4: 运行 lint**

```bash
cd backend && make lint
```

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/config/paths.py backend/app/gateway/routers/agents.py backend/packages/harness/deerflow/agents/lead_agent/prompt.py
git commit -m "feat: per-user profile (USER.md) isolation"
```

---

## Task 8: 前端线程列表改为通过 Gateway 代理

**Files:**
- Modify: `frontend/src/core/threads/hooks.ts`
- Modify: `frontend/src/core/threads/types.ts`

- [ ] **Step 1: 添加 Gateway thread API 函数**

在 `frontend/src/core/threads/hooks.ts` 顶部添加一个通过 Gateway 获取线程列表的函数:

```typescript
async function fetchGatewayThreads(
  params: { limit?: number; offset?: number } = {},
): Promise<AgentThread[]> {
  const response = await fetch(`${getBackendBaseURL()}/api/threads/search`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch threads: ${response.status}`);
  }
  const data = await response.json();
  return data.map(
    (t: {
      thread_id: string;
      status: string;
      created_at: string;
      updated_at: string;
      metadata: Record<string, unknown>;
      values: { title?: string };
    }) =>
      ({
        thread_id: t.thread_id,
        status: t.status,
        created_at: t.created_at,
        updated_at: t.updated_at,
        metadata: t.metadata,
        values: t.values || {},
      }) as AgentThread,
  );
}
```

需要在顶部添加 `import { getBackendBaseURL } from "../config";`（如果尚未导入）。

- [ ] **Step 2: 修改 useThreads hook**

将 `useThreads` 的 queryFn 从调用 `apiClient.threads.search` 改为调用 `fetchGatewayThreads`:

```typescript
export function useThreads(
  params: { limit?: number; offset?: number } = {},
) {
  return useQuery<AgentThread[]>({
    queryKey: ["threads", "search", params],
    queryFn: async () => {
      return fetchGatewayThreads({
        limit: params.limit ?? 50,
        offset: params.offset ?? 0,
      });
    },
    refetchOnWindowFocus: false,
  });
}
```

- [ ] **Step 3: 运行 typecheck**

```bash
cd frontend && node_modules/.bin/tsc --noEmit -p tsconfig.json
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/threads/hooks.ts
git commit -m "feat: frontend thread list via Gateway with user isolation"
```

---

## Task 9: 管理面板 — Thread 审计 API 集成

**Files:**
- Create: `admin/src/api/threads.ts`
- Create: `admin/src/hooks/useThreads.ts`

- [ ] **Step 1: 创建 threads API**

创建 `admin/src/api/threads.ts`:

```typescript
import apiClient from './client';

export interface ThreadAuditItem {
  id: string;
  user_id: string;
  title: string | null;
  status: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  username: string | null;
  display_name: string | null;
}

export interface ThreadAuditListResponse {
  items: ThreadAuditItem[];
  total: number;
}

export interface ThreadMessageItem {
  id: string;
  thread_id: string;
  role: string;
  content: string | null;
  raw_content: Record<string, unknown> | null;
  token_count: number | null;
  created_at: string;
}

export interface ThreadMessageListResponse {
  items: ThreadMessageItem[];
  total: number;
}

export interface ThreadStatsResponse {
  total_threads: number;
  total_messages: number;
  active_users: number;
}

export interface DailyStatsPoint {
  date: string;
  thread_count: number;
}

export interface DailyMessageStatsPoint {
  date: string;
  message_count: number;
}

export interface ThreadStatsChartResponse {
  thread_stats: DailyStatsPoint[];
  message_stats: DailyMessageStatsPoint[];
}

export async function listAuditThreads(params: {
  page: number;
  page_size: number;
  user_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}): Promise<ThreadAuditListResponse> {
  const res = await apiClient.get('/api/admin/audit/threads', { params });
  return res.data;
}

export async function getThreadStats(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}): Promise<ThreadStatsResponse> {
  const res = await apiClient.get('/api/admin/audit/threads/stats', { params });
  return res.data;
}

export async function getThreadStatsChart(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}): Promise<ThreadStatsChartResponse> {
  const res = await apiClient.get('/api/admin/audit/threads/stats/chart', { params });
  return res.data;
}

export async function getThreadMessages(params: {
  thread_id: string;
  page: number;
  page_size: number;
}): Promise<ThreadMessageListResponse> {
  const res = await apiClient.get(`/api/admin/audit/threads/${params.thread_id}/messages`, {
    params: { page: params.page, page_size: params.page_size },
  });
  return res.data;
}
```

- [ ] **Step 2: 创建 hooks**

创建 `admin/src/hooks/useThreads.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import {
  getThreadStats,
  getThreadStatsChart,
  listAuditThreads,
  getThreadMessages,
} from '../api/threads';

export function useThreadStats(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}) {
  return useQuery({
    queryKey: ['threadStats', params],
    queryFn: () => getThreadStats(params),
  });
}

export function useThreadStatsChart(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}) {
  return useQuery({
    queryKey: ['threadStatsChart', params],
    queryFn: () => getThreadStatsChart(params),
  });
}

export function useAuditThreads(params: {
  page: number;
  page_size: number;
  user_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: ['auditThreads', params],
    queryFn: () => listAuditThreads(params),
  });
}

export function useThreadMessages(params: {
  thread_id: string;
  page: number;
  page_size: number;
}) {
  return useQuery({
    queryKey: ['threadMessages', params],
    queryFn: () => getThreadMessages(params),
    enabled: !!params.thread_id,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add admin/src/api/threads.ts admin/src/hooks/useThreads.ts
git commit -m "feat: admin panel thread audit API and hooks"
```

---

## Task 10: 管理面板 — 仪表板对话统计图表

**Files:**
- Modify: `admin/src/pages/dashboard/DashboardPage.tsx`
- Modify: `admin/package.json` (安装 echarts)

- [ ] **Step 1: 安装 ECharts**

```bash
cd admin && pnpm add echarts echarts-for-react
```

- [ ] **Step 2: 重写 DashboardPage**

重写 `admin/src/pages/dashboard/DashboardPage.tsx`，保留原有统计卡片，新增对话统计模块:

```tsx
import { useState, useEffect } from 'react';
import { Card, Col, Row, Statistic, Button, Space, DatePicker } from 'antd';
import {
  UserOutlined,
  ApartmentOutlined,
  RobotOutlined,
  AuditOutlined,
  MessageOutlined,
  ChatOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useAuthStore } from '../../stores/auth';
import { listUsers } from '../../api/users';
import { getDepartmentTree } from '../../api/departments';
import { listSkills } from '../../api/skills';
import { getThreadStats, getThreadStatsChart } from '../../api/threads';
import { SkillStatus } from '../../types';
import type { ThreadStatsResponse, ThreadStatsChartResponse } from '../../api/threads';
import dayjs, { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

const QUICK_FILTERS = [
  { key: '7d', label: '7天内' },
  { key: 'last_week', label: '上周' },
  { key: '1m', label: '一个月内' },
  { key: '6m', label: '半年' },
  { key: '1y', label: '一年' },
];

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState({ users: 0, departments: 0, pendingSkills: 0, approvedSkills: 0 });
  const [threadStats, setThreadStats] = useState<ThreadStatsResponse | null>(null);
  const [chartData, setChartData] = useState<ThreadStatsChartResponse | null>(null);
  const [activeQuick, setActiveQuick] = useState('7d');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);

  const loadBasicStats = async () => {
    try {
      const [usersRes, deptsRes, pendingRes, approvedRes] = await Promise.all([
        listUsers({ page: 1, page_size: 1 }),
        getDepartmentTree(),
        listSkills({ page: 1, page_size: 1, status: SkillStatus.PENDING_REVIEW }),
        listSkills({ page: 1, page_size: 1, status: SkillStatus.APPROVED }),
      ]);
      setStats({
        users: usersRes.total,
        departments: deptsRes.departments.length,
        pendingSkills: pendingRes.total,
        approvedSkills: approvedRes.total,
      });
    } catch {}
  };

  const loadThreadStats = async (quick?: string, start?: string, end?: string) => {
    try {
      const params: { quick?: string; start_date?: string; end_date?: string } = {};
      if (quick) params.quick = quick;
      if (start) params.start_date = start;
      if (end) params.end_date = end;
      const [ts, chart] = await Promise.all([
        getThreadStats(params),
        getThreadStatsChart(params),
      ]);
      setThreadStats(ts);
      setChartData(chart);
    } catch {}
  };

  useEffect(() => {
    loadBasicStats();
    loadThreadStats('7d');
  }, []);

  const handleQuickFilter = (key: string) => {
    setActiveQuick(key);
    setDateRange(null);
    loadThreadStats(key);
  };

  const handleDateRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    if (dates && dates[0] && dates[1]) {
      const range: [Dayjs, Dayjs] = [dates[0], dates[1]];
      setDateRange(range);
      setActiveQuick('');
      loadThreadStats(undefined, range[0].format('YYYY-MM-DD'), range[1].format('YYYY-MM-DD'));
    }
  };

  const allDates = chartData
    ? [...new Set([
          ...chartData.thread_stats.map((s) => s.date),
          ...chartData.message_stats.map((s) => s.date),
        ])].sort()
    : [];

  const threadCountMap = Object.fromEntries(
    (chartData?.thread_stats ?? []).map((s) => [s.date, s.thread_count]),
  );
  const messageCountMap = Object.fromEntries(
    (chartData?.message_stats ?? []).map((s) => [s.date, s.message_count]),
  );

  const chartOption = chartData
    ? {
        tooltip: { trigger: 'axis' as const },
        legend: { data: ['对话数', '消息数'] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
          type: 'category' as const,
          data: allDates,
        },
        yAxis: [
          { type: 'value' as const, name: '对话数' },
          { type: 'value' as const, name: '消息数' },
        ],
        series: [
          {
            name: '对话数',
            type: 'bar' as const,
            data: allDates.map((d) => threadCountMap[d] ?? 0),
          },
          {
            name: '消息数',
            type: 'line' as const,
            yAxisIndex: 1,
            data: allDates.map((d) => messageCountMap[d] ?? 0),
          },
        ],
      }
    : null;

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>欢迎，{user?.display_name || user?.username}</h2>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="用户总数" value={stats.users} prefix={<UserOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="部门数" value={stats.departments} prefix={<ApartmentOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="待审核 Skill" value={stats.pendingSkills} prefix={<AuditOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已发布 Skill" value={stats.approvedSkills} prefix={<RobotOutlined />} /></Card>
        </Col>
      </Row>

      <Card title="对话统计" style={{ marginBottom: 24 }}>
        <Space style={{ marginBottom: 16 }} wrap>
          {QUICK_FILTERS.map((f) => (
            <Button
              key={f.key}
              type={activeQuick === f.key ? 'primary' : 'default'}
              onClick={() => handleQuickFilter(f.key)}
            >
              {f.label}
            </Button>
          ))}
          <RangePicker onChange={handleDateRangeChange} value={dateRange} />
        </Space>

        {threadStats && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Statistic title="总对话数" value={threadStats.total_threads} prefix={<ChatOutlined />} />
            </Col>
            <Col span={8}>
              <Statistic title="总消息数" value={threadStats.total_messages} prefix={<MessageOutlined />} />
            </Col>
            <Col span={8}>
              <Statistic title="活跃用户" value={threadStats.active_users} prefix={<TeamOutlined />} />
            </Col>
          </Row>
        )}

        {chartOption && (
          <ReactECharts option={chartOption} style={{ height: 350 }} />
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: 检查 dayjs 依赖**

如果 admin 项目没有 dayjs，需要安装:

```bash
cd admin && pnpm add dayjs
```

- [ ] **Step 4: 运行 typecheck**

```bash
cd admin && node_modules/.bin/tsc --noEmit -p tsconfig.json
```

- [ ] **Step 5: Commit**

```bash
git add admin/src/pages/dashboard/DashboardPage.tsx admin/package.json admin/pnpm-lock.yaml
git commit -m "feat: admin dashboard thread statistics with ECharts"
```

---

## Task 11: 管理面板 — 对话审计页面

**Files:**
- Create: `admin/src/pages/threads/ThreadListPage.tsx`
- Modify: `admin/src/App.tsx` (添加路由)
- Modify: `admin/src/layouts/AdminLayout.tsx` (添加菜单项)

- [ ] **Step 1: 创建对话审计列表页面**

创建 `admin/src/pages/threads/ThreadListPage.tsx`:

```tsx
import { useState } from 'react';
import { Table, Input, Button, Space, DatePicker, Tag, Drawer, Typography, message } from 'antd';
import { SearchOutlined, EyeOutlined } from '@ant-design/icons';
import { useAuditThreads, useThreadMessages } from '../../hooks/useThreads';
import type { ThreadAuditItem } from '../../api/threads';
import dayjs, { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

export default function ThreadListPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);

  const { data, isLoading } = useAuditThreads({
    page,
    page_size: pageSize,
    search: search || undefined,
    start_date: dateRange?.[0]?.format('YYYY-MM-DD'),
    end_date: dateRange?.[1]?.format('YYYY-MM-DD'),
  });

  const { data: messagesData, isLoading: messagesLoading } = useThreadMessages({
    thread_id: selectedThread || '',
    page: 1,
    page_size: 200,
  });

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string | null) => text || '（无标题）',
    },
    {
      title: '所属用户',
      key: 'user',
      render: (_: unknown, record: ThreadAuditItem) =>
        record.display_name || record.username || '-',
    },
    {
      title: '消息数',
      dataIndex: 'message_count',
      key: 'message_count',
      width: 100,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const colorMap: Record<string, string> = { active: 'green', archived: 'orange', deleted: 'red' };
        const labelMap: Record<string, string> = { active: '活跃', archived: '已归档', deleted: '已删除' };
        return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '最后活跃',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: ThreadAuditItem) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => setSelectedThread(record.id)}
        >
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>对话审计</h2>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索对话标题"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 250 }}
          allowClear
        />
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              setDateRange([dates[0], dates[1]]);
            } else {
              setDateRange(null);
            }
            setPage(1);
          }}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={data?.items || []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: data?.total || 0,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      <Drawer
        title="消息记录"
        width={640}
        open={!!selectedThread}
        onClose={() => setSelectedThread(null)}
        loading={messagesLoading}
      >
        {messagesData?.items.map((msg) => (
          <div
            key={msg.id}
            style={{
              marginBottom: 12,
              padding: '8px 12px',
              borderRadius: 8,
              background: msg.role === 'user' ? '#e6f7ff' : '#f6ffed',
              borderLeft: `3px solid ${msg.role === 'user' ? '#1890ff' : '#52c41a'}`,
            }}
          >
            <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>
              {msg.role === 'user' ? '用户' : msg.role === 'assistant' ? 'AI 助手' : msg.role}
              {' · '}
              {dayjs(msg.created_at).format('YYYY-MM-DD HH:mm:ss')}
            </div>
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {msg.content || '（无文本内容）'}
            </div>
            {msg.raw_content?.tool_calls && (
              <div style={{ marginTop: 4, fontSize: 12, color: '#666' }}>
                <strong>工具调用:</strong>{' '}
                {(msg.raw_content.tool_calls as Array<{ name: string }>).map((tc) => tc.name).join(', ')}
              </div>
            )}
          </div>
        ))}
      </Drawer>
    </div>
  );
}
```

- [ ] **Step 2: 添加路由**

修改 `admin/src/App.tsx`，在路由中添加:

```tsx
import ThreadListPage from './pages/threads/ThreadListPage';

// 在 <Route path="departments" ... /> 之后添加:
<Route path="threads" element={<RoleGuard roles={[UserRole.SUPER_ADMIN]}><ThreadListPage /></RoleGuard>} />
```

- [ ] **Step 3: 添加侧边栏菜单项**

修改 `admin/src/layouts/AdminLayout.tsx`，在 imports 中添加:

```tsx
import { MessageOutlined } from '@ant-design/icons';
```

在 menuItems 中 departments 菜单项之后添加:

```tsx
  if (user?.role === UserRole.SUPER_ADMIN) {
    menuItems!.push({
      key: '/admin/threads',
      icon: <MessageOutlined />,
      label: '对话审计',
    });
  }
```

注意：这个 block 可以和 departments 的 `if` 合并。

- [ ] **Step 4: 运行 typecheck**

```bash
cd admin && node_modules/.bin/tsc --noEmit -p tsconfig.json
```

- [ ] **Step 5: Commit**

```bash
git add admin/src/pages/threads/ admin/src/App.tsx admin/src/layouts/AdminLayout.tsx
git commit -m "feat: admin thread audit page with message viewer"
```

---

## Task 12: 后端测试 — Thread Service 和审计 API

**Files:**
- Create: `backend/tests/test_admin/test_thread_audit.py`
- Modify: `backend/tests/test_admin/conftest.py` (注册新路由)

- [ ] **Step 1: 在 conftest 中注册审计路由**

在 `conftest.py` 的 `client` fixture 中，添加路由注册:

```python
from app.admin.routers import audit_threads as admin_audit_threads

# 在 app.include_router(admin_skills.router) 之后添加:
app.include_router(admin_audit_threads.router)
```

- [ ] **Step 2: 编写审计 API 测试**

创建 `backend/tests/test_admin/test_thread_audit.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_list_audit_threads_empty(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_audit_threads_forbidden_for_dept_admin(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["dept_admin"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_threads_forbidden_for_regular_user(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["regular_user"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_thread_stats(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads/stats",
        headers=auth_headers["super_admin"],
        params={"quick": "7d"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_threads" in data
    assert "total_messages" in data
    assert "active_users" in data


@pytest.mark.asyncio
async def test_get_thread_stats_chart(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads/stats/chart",
        headers=auth_headers["super_admin"],
        params={"quick": "7d"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "thread_stats" in data
    assert "message_stats" in data


@pytest.mark.asyncio
async def test_get_thread_messages_not_found(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads/nonexistent-thread-id/messages",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 50},
    )
    assert resp.status_code == 404
```

- [ ] **Step 3: 运行测试**

```bash
cd backend && uv run pytest tests/test_admin/test_thread_audit.py -v
```

所有测试应通过。

- [ ] **Step 4: 运行全部 admin 测试确认无回归**

```bash
cd backend && uv run pytest tests/test_admin/ -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_admin/test_thread_audit.py backend/tests/test_admin/conftest.py
git commit -m "test: add thread audit API tests"
```

---

## Task 13: 集成验证 + Lint

**Files:** (无新增，验证已有改动)

- [ ] **Step 1: 运行后端 lint**

```bash
cd backend && make lint
```

- [ ] **Step 2: 运行后端全部 admin 测试**

```bash
cd backend && uv run pytest tests/test_admin/ -v
```

- [ ] **Step 3: 运行前端 typecheck**

```bash
cd frontend && node_modules/.bin/tsc --noEmit -p tsconfig.json
```

- [ ] **Step 4: 运行管理面板 typecheck**

```bash
cd admin && node_modules/.bin/tsc --noEmit -p tsconfig.json
```

- [ ] **Step 5: 运行后端内存 + prompt 测试确认无回归**

```bash
cd backend && uv run pytest tests/test_memory_prompt_injection.py tests/test_harness_boundary.py -v
```

- [ ] **Step 6: Final commit（如有 lint 自动修复）**

```bash
cd backend && uvx ruff check --fix . && uvx ruff format .
git add -A && git commit -m "chore: lint and format fixes" || echo "No changes needed"
```
