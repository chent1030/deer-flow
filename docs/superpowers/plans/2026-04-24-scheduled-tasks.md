# Scheduled Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users create cron-based scheduled tasks that run a custom agent with a specific skill, view execution results (full conversation history) in the frontend settings panel.

**Architecture:** APScheduler runs inside the Gateway process. On cron trigger, the executor calls LangGraph Server via `langgraph-sdk` (same path as frontend). Task and execution data stored in PostgreSQL. Frontend adds a "Scheduled Tasks" tab in the settings dialog.

**Tech Stack:** APScheduler 3.x, croniter, langgraph-sdk, SQLAlchemy (async), FastAPI, React 19, Next.js 16, TanStack Query, Shadcn UI

**Design spec:** `docs/superpowers/specs/2026-04-24-scheduled-tasks-design.md`

---

## File Structure

### Backend — New files

| File | Responsibility |
|------|---------------|
| `backend/packages/harness/deerflow/scheduler/__init__.py` | Package init |
| `backend/packages/harness/deerflow/scheduler/manager.py` | SchedulerManager singleton — wraps APScheduler, start/stop/register/remove jobs |
| `backend/packages/harness/deerflow/scheduler/executor.py` | Task executor — calls langgraph-sdk, records execution, replaces template variables |
| `backend/packages/harness/deerflow/scheduler/template_engine.py` | Template variable engine — built-in + custom variable rendering |
| `backend/app/admin/models/scheduled_task.py` | SQLAlchemy models: `ScheduledTask`, `TaskExecution` |
| `backend/app/admin/services/scheduler_service.py` | CRUD + toggle/trigger + list executions |
| `backend/app/gateway/routers/scheduler.py` | REST API endpoints (9 routes) |
| `backend/alembic/versions/d1e2f3a4b5c6_add_scheduled_tasks_tables.py` | Alembic migration |
| `backend/tests/test_scheduler.py` | Tests for template engine, service CRUD, executor logic |

### Backend — Modified files

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `apscheduler>=3.10` dependency |
| `backend/app/gateway/app.py` | Import scheduler router + init SchedulerManager in lifespan |

### Frontend — New files

| File | Responsibility |
|------|---------------|
| `frontend/src/core/scheduler/api.ts` | API client functions for scheduler endpoints |
| `frontend/src/core/scheduler/types.ts` | TypeScript types for ScheduledTask, TaskExecution |
| `frontend/src/core/scheduler/hooks.ts` | TanStack Query hooks for task CRUD and executions |
| `frontend/src/components/workspace/settings/scheduler-settings-page.tsx` | Main settings tab: task list + create/edit form |
| `frontend/src/components/workspace/settings/scheduler-execution-dialog.tsx` | Execution detail dialog: full conversation view |

### Frontend — Modified files

| File | Change |
|------|--------|
| `frontend/src/core/i18n/locales/types.ts` | Add `scheduler` section to `settings.sections` + scheduler i18n keys |
| `frontend/src/core/i18n/locales/en-US.ts` | English translations |
| `frontend/src/core/i18n/locales/zh-CN.ts` | Chinese translations |
| `frontend/src/components/workspace/settings/settings-dialog.tsx` | Add `scheduler` section + import + conditional render |

---

## Task 1: Add APScheduler dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add apscheduler to dependencies**

In `backend/pyproject.toml`, add `"apscheduler>=3.10"` to the `dependencies` list (after `"psycopg-binary>=3.3.3"`):

```toml
    "psycopg-binary>=3.3.3",
    "apscheduler>=3.10",
]
```

- [ ] **Step 2: Install the dependency**

Run: `cd backend && uv sync`
Expected: APScheduler installed successfully

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add apscheduler dependency for scheduled tasks"
```

---

## Task 2: Template variable engine

**Files:**
- Create: `backend/packages/harness/deerflow/scheduler/__init__.py`
- Create: `backend/packages/harness/deerflow/scheduler/template_engine.py`
- Create: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Create scheduler package init**

Create `backend/packages/harness/deerflow/scheduler/__init__.py`:

```python
```

(empty file)

- [ ] **Step 2: Write failing tests for template engine**

Create `backend/tests/test_scheduler.py`:

```python
import pytest

from deerflow.scheduler.template_engine import render_template


def test_builtin_date():
    result = render_template("今天是 {{date}}", {}, "testuser")
    assert "{{date}}" not in result
    assert len(result.split("-")) == 3


def test_builtin_datetime():
    result = render_template("时间 {{datetime}}", {}, "testuser")
    assert "{{datetime}}" not in result


def test_builtin_time():
    result = render_template("时间 {{time}}", {}, "testuser")
    assert "{{time}}" not in result


def test_builtin_day_of_week():
    result = render_template("星期 {{day_of_week}}", {}, "testuser")
    assert "{{day_of_week}}" not in result
    assert result.startswith("星期")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    assert result.split(" ")[1] in weekdays


def test_builtin_user_name():
    result = render_template("用户 {{user_name}} 你好", {}, "testuser")
    assert result == "用户 testuser 你好"


def test_custom_variable():
    result = render_template(
        "查询 {{report_type}} 情况",
        {"report_type": "销售"},
        "testuser",
    )
    assert result == "查询 销售 情况"


def test_custom_overrides_builtin():
    result = render_template(
        "用户 {{user_name}}",
        {"user_name": "自定义名"},
        "testuser",
    )
    assert result == "用户 自定义名"


def test_unmatched_variable_preserved():
    result = render_template("未知 {{unknown_var}} 保留", {}, "testuser")
    assert result == "未知 {{unknown_var}} 保留"


def test_multiple_variables():
    result = render_template(
        "{{user_name}} 在 {{date}} 查询 {{report_type}}",
        {"report_type": "库存"},
        "testuser",
    )
    assert "testuser" in result
    assert "库存" in result
    assert "{{" not in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deerflow.scheduler.template_engine'`

- [ ] **Step 4: Implement template engine**

Create `backend/packages/harness/deerflow/scheduler/template_engine.py`:

```python
import re
from datetime import datetime, timezone, timedelta

UTC8 = timezone(timedelta(hours=8))

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


def _builtin_vars(user_name: str) -> dict[str, str]:
    now = datetime.now(UTC8)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": WEEKDAYS_CN[now.weekday()],
        "user_name": user_name,
    }


def render_template(
    template: str,
    custom_variables: dict[str, str],
    user_name: str,
) -> str:
    variables = _builtin_vars(user_name)
    variables.update(custom_variables)

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return _TEMPLATE_RE.sub(_replace, template)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_scheduler.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/packages/harness/deerflow/scheduler/ backend/tests/test_scheduler.py
git commit -m "feat(scheduler): add template variable engine with built-in and custom variables"
```

---

## Task 3: SQLAlchemy models

**Files:**
- Create: `backend/app/admin/models/scheduled_task.py`
- Create: `backend/alembic/versions/d1e2f3a4b5c6_add_scheduled_tasks_tables.py`

- [ ] **Step 1: Create model file**

Create `backend/app/admin/models/scheduled_task.py`:

```python
import enum
import uuid

from sqlalchemy import String, Text, Boolean, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.admin.models.base import Base, TimestampMixin


class TaskStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ExecutionStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScheduledTask(Base, TimestampMixin):
    __tablename__ = "scheduled_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_description: Mapped[str] = mapped_column(Text, server_default="")
    agent_soul: Mapped[str] = mapped_column(Text, server_default="")
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_variables: Mapped[dict | None] = mapped_column(
        "json", nullable=True, default=dict,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), server_default=TaskStatus.ACTIVE.value,
    )
    last_execution_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    next_execution_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    executions: Mapped[list["TaskExecution"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), server_default=ExecutionStatus.RUNNING.value,
    )
    triggered_at: Mapped[str] = mapped_column(String(50), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    messages: Mapped[list | None] = mapped_column("json", nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column("json", nullable=True)

    task: Mapped["ScheduledTask"] = relationship(back_populates="executions")
```

Note: Uses `String(50)` for timestamps (ISO 8601 strings) consistent with the project's `now_utc8()` pattern which returns datetime strings.

- [ ] **Step 2: Create Alembic migration**

Create `backend/alembic/versions/d1e2f3a4b5c6_add_scheduled_tasks_tables.py`:

```python
"""add_scheduled_tasks_tables

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-04-24 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("agent_description", sa.Text(), server_default="", nullable=False),
        sa.Column("agent_soul", sa.Text(), server_default="", nullable=False),
        sa.Column("skill_name", sa.String(200), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("custom_variables", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "paused", "error", name="taskstatus"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("last_execution_at", sa.String(50), nullable=True),
        sa.Column("next_execution_at", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(50), nullable=True),
        sa.Column("updated_at", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scheduled_tasks_user_id", "scheduled_tasks", ["user_id"])

    op.create_table(
        "task_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "completed", "failed", "skipped", name="executionstatus"),
            server_default="running",
            nullable=False,
        ),
        sa.Column("triggered_at", sa.String(50), nullable=False),
        sa.Column("completed_at", sa.String(50), nullable=True),
        sa.Column("thread_id", sa.String(200), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["scheduled_tasks.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_task_executions_task_id", "task_executions", ["task_id"])


def downgrade() -> None:
    op.drop_table("task_executions")
    op.drop_table("scheduled_tasks")
    op.execute("DROP TYPE IF EXISTS executionstatus")
    op.execute("DROP TYPE IF EXISTS taskstatus")
```

- [ ] **Step 3: Run migration**

Run: `cd backend && uv run alembic upgrade head`
Expected: Migration applies successfully, both tables created

- [ ] **Step 4: Commit**

```bash
git add backend/app/admin/models/scheduled_task.py backend/alembic/versions/d1e2f3a4b5c6_add_scheduled_tasks_tables.py
git commit -m "feat(scheduler): add ScheduledTask and TaskExecution models with migration"
```

---

## Task 4: SchedulerManager

**Files:**
- Create: `backend/packages/harness/deerflow/scheduler/manager.py`
- Create: `backend/packages/harness/deerflow/scheduler/executor.py`

- [ ] **Step 1: Create SchedulerManager**

Create `backend/packages/harness/deerflow/scheduler/manager.py`:

```python
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter

logger = logging.getLogger(__name__)

UTC8 = timezone(timedelta(hours=8))


class SchedulerManager:
    _instance: "SchedulerManager | None" = None

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=UTC8)
        self._executor = None

    @classmethod
    def get_instance(cls) -> "SchedulerManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_executor(self, executor) -> None:
        self._executor = executor

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("APScheduler started")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")

    def register_task(self, task_id: str, cron_expression: str) -> None:
        self.remove_task(task_id)
        if self._executor is None:
            logger.error("Executor not set, cannot register task %s", task_id)
            return
        parts = cron_expression.split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
            timezone=UTC8,
        )
        self._scheduler.add_job(
            self._executor.execute_task,
            trigger=trigger,
            id=task_id,
            args=[task_id],
            max_instances=1,
            misfire_grace_time=60,
        )
        logger.info("Registered scheduled task %s with cron '%s'", task_id, cron_expression)

    def remove_task(self, task_id: str) -> None:
        try:
            self._scheduler.remove_job(task_id)
            logger.info("Removed scheduled task %s", task_id)
        except Exception:
            pass

    @staticmethod
    def compute_next_run(cron_expression: str) -> str | None:
        try:
            now = datetime.now(UTC8)
            cron = croniter(cron_expression, now)
            next_dt = cron.get_next(datetime)
            return next_dt.isoformat()
        except Exception:
            return None
```

- [ ] **Step 2: Create TaskExecutor**

Create `backend/packages/harness/deerflow/scheduler/executor.py`:

```python
import logging
import uuid
from datetime import datetime, timezone, timedelta

from langgraph_sdk import get_client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin.models.scheduled_task import ScheduledTask, TaskExecution, ExecutionStatus
from app.admin.services.skill_service import list_visible_skills_for_user
from deerflow.config.agents_config import load_agent_config
from deerflow.config.paths import get_paths
from deerflow.scheduler.template_engine import render_template

logger = logging.getLogger(__name__)

UTC8 = timezone(timedelta(hours=8))
LANGGRAPH_URL = "http://localhost:2024"
EXECUTION_TIMEOUT = 600


def _now_iso() -> str:
    return datetime.now(UTC8).isoformat()


class TaskExecutor:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute_task(self, task_id_str: str) -> None:
        task_id = uuid.UUID(task_id_str)
        async with self._session_factory() as db:
            task = await db.get(ScheduledTask, task_id)
            if task is None:
                logger.error("Scheduled task %s not found", task_id)
                return

            running = await db.execute(
                select(TaskExecution).where(
                    TaskExecution.task_id == task_id,
                    TaskExecution.status == ExecutionStatus.RUNNING,
                )
            )
            if running.scalar_one_or_none() is not None:
                execution = TaskExecution(
                    task_id=task_id,
                    status=ExecutionStatus.SKIPPED,
                    triggered_at=_now_iso(),
                    completed_at=_now_iso(),
                    error_message="Previous execution still running",
                )
                db.add(execution)
                await db.commit()
                logger.info("Skipped task %s: previous execution still running", task_id)
                return

            execution = TaskExecution(
                task_id=task_id,
                status=ExecutionStatus.RUNNING,
                triggered_at=_now_iso(),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

        try:
            user = await self._get_user(db, task.user_id)
            custom_vars = task.custom_variables or {}
            user_name = user.username if user else "unknown"
            rendered_prompt = render_template(task.agent_soul, custom_vars, user_name)

            visible_skills = await list_visible_skills_for_user(
                db, task.user_id,
                user.role if user else "user",
                user.department_id if user else None,
            )

            agent_cfg = load_agent_config(task.agent_name)
            agent_model = agent_cfg.model if agent_cfg else None

            client = get_client(url=LANGGRAPH_URL)
            thread = await client.threads.create()
            thread_id = thread["thread_id"]

            config: dict = {
                "configurable": {
                    "agent_name": task.agent_name,
                    "visible_skills": visible_skills,
                },
            }
            if agent_model:
                config["configurable"]["model"] = agent_model

            run = await client.runs.wait(
                thread_id=thread_id,
                assistant_id="lead-agent",
                input={"messages": [{"role": "user", "content": rendered_prompt}]},
                config=config,
                timeout=EXECUTION_TIMEOUT,
            )

            state = await client.threads.get_state(thread_id)
            messages = state.get("values", {}).get("messages", [])

            token_usage = None
            if run and hasattr(run, "usage_metadata"):
                token_usage = run.usage_metadata

            async with self._session_factory() as db2:
                exec_obj = await db2.get(TaskExecution, execution.id)
                if exec_obj:
                    exec_obj.status = ExecutionStatus.COMPLETED
                    exec_obj.completed_at = _now_iso()
                    exec_obj.thread_id = thread_id
                    exec_obj.messages = messages
                    exec_obj.token_usage = token_usage
                    await db2.commit()

                task_obj = await db2.get(ScheduledTask, task_id)
                if task_obj:
                    task_obj.last_execution_at = _now_iso()
                    from deerflow.scheduler.manager import SchedulerManager
                    task_obj.next_execution_at = SchedulerManager.compute_next_run(task_obj.cron_expression)
                    task_obj.status = "active"
                    task_obj.error_message = None
                    await db2.commit()

            logger.info("Task %s executed successfully", task_id)

        except Exception as e:
            logger.exception("Task %s execution failed: %s", task_id, e)
            async with self._session_factory() as db3:
                exec_obj = await db3.get(TaskExecution, execution.id)
                if exec_obj:
                    exec_obj.status = ExecutionStatus.FAILED
                    exec_obj.completed_at = _now_iso()
                    exec_obj.error_message = str(e)[:2000]
                    await db3.commit()

                task_obj = await db3.get(ScheduledTask, task_id)
                if task_obj:
                    task_obj.error_message = str(e)[:2000]
                    await db3.commit()

    async def _get_user(self, db: AsyncSession, user_id: uuid.UUID):
        from app.admin.models.user import User
        return await db.get(User, user_id)
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/scheduler/manager.py backend/packages/harness/deerflow/scheduler/executor.py
git commit -m "feat(scheduler): add SchedulerManager and TaskExecutor"
```

---

## Task 5: Scheduler service (CRUD + toggle/trigger)

**Files:**
- Create: `backend/app/admin/services/scheduler_service.py`

- [ ] **Step 1: Implement scheduler service**

Create `backend/app/admin/services/scheduler_service.py`:

```python
import logging
import uuid
from datetime import datetime, timezone, timedelta

import yaml
from croniter import croniter
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models.scheduled_task import ScheduledTask, TaskExecution, TaskStatus, ExecutionStatus
from deerflow.config.paths import get_paths
from deerflow.scheduler.manager import SchedulerManager

logger = logging.getLogger(__name__)

UTC8 = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(UTC8).isoformat()


async def create_task(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    agent_description: str,
    agent_soul: str,
    skill_name: str,
    cron_expression: str,
    custom_variables: dict | None = None,
) -> ScheduledTask:
    if not croniter.is_valid(cron_expression):
        raise ValueError(f"Invalid cron expression: {cron_expression}")

    task_id = uuid.uuid4()
    agent_name = f"sched-{str(task_id)[:8]}"

    agent_dir = get_paths().agent_dir(agent_name)
    agent_dir.mkdir(parents=True, exist_ok=True)

    config_data: dict = {"name": agent_name, "description": agent_description}
    config_file = agent_dir / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

    soul_file = agent_dir / "SOUL.md"
    soul_file.write_text(agent_soul, encoding="utf-8")

    task = ScheduledTask(
        id=task_id,
        user_id=user_id,
        agent_name=agent_name,
        agent_description=agent_description,
        agent_soul=agent_soul,
        skill_name=skill_name,
        cron_expression=cron_expression,
        custom_variables=custom_variables or {},
        status=TaskStatus.ACTIVE,
        next_execution_at=SchedulerManager.compute_next_run(cron_expression),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    SchedulerManager.get_instance().register_task(str(task.id), cron_expression)
    logger.info("Created scheduled task %s for user %s", task.id, user_id)
    return task


async def update_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    agent_description: str | None = None,
    agent_soul: str | None = None,
    skill_name: str | None = None,
    cron_expression: str | None = None,
    custom_variables: dict | None = None,
) -> ScheduledTask:
    task = await db.get(ScheduledTask, task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Task not found or access denied")

    if agent_description is not None:
        task.agent_description = agent_description
    if agent_soul is not None:
        task.agent_soul = agent_soul
        agent_dir = get_paths().agent_dir(task.agent_name)
        soul_file = agent_dir / "SOUL.md"
        soul_file.write_text(agent_soul, encoding="utf-8")
    if skill_name is not None:
        task.skill_name = skill_name
    if cron_expression is not None:
        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression}")
        task.cron_expression = cron_expression
        task.next_execution_at = SchedulerManager.compute_next_run(cron_expression)
        SchedulerManager.get_instance().register_task(str(task.id), cron_expression)
    if custom_variables is not None:
        task.custom_variables = custom_variables

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID) -> None:
    task = await db.get(ScheduledTask, task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Task not found or access denied")

    SchedulerManager.get_instance().remove_task(str(task.id))

    import shutil
    agent_dir = get_paths().agent_dir(task.agent_name)
    if agent_dir.exists():
        shutil.rmtree(agent_dir)

    await db.delete(task)
    await db.commit()
    logger.info("Deleted scheduled task %s", task_id)


async def toggle_task(db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID) -> ScheduledTask:
    task = await db.get(ScheduledTask, task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Task not found or access denied")

    task.is_enabled = not task.is_enabled
    if task.is_enabled:
        task.status = TaskStatus.ACTIVE
        SchedulerManager.get_instance().register_task(str(task.id), task.cron_expression)
    else:
        task.status = TaskStatus.PAUSED
        SchedulerManager.get_instance().remove_task(str(task.id))

    await db.commit()
    await db.refresh(task)
    return task


async def trigger_task(db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID) -> TaskExecution:
    task = await db.get(ScheduledTask, task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Task not found or access denied")

    from deerflow.scheduler.executor import TaskExecutor
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(db.get_bind(), expire_on_commit=False)
    executor = TaskExecutor(session_factory)
    await executor.execute_task(str(task.id))

    result = await db.execute(
        select(TaskExecution)
        .where(TaskExecution.task_id == task_id)
        .order_by(TaskExecution.triggered_at.desc())
        .limit(1),
    )
    return result.scalar_one()


async def list_tasks(db: AsyncSession, user_id: uuid.UUID) -> list[ScheduledTask]:
    result = await db.execute(
        select(ScheduledTask)
        .where(ScheduledTask.user_id == user_id)
        .order_by(ScheduledTask.created_at.desc()),
    )
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID) -> ScheduledTask:
    task = await db.get(ScheduledTask, task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Task not found or access denied")
    return task


async def list_executions(
    db: AsyncSession,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[TaskExecution]:
    task = await db.get(ScheduledTask, task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Task not found or access denied")

    result = await db.execute(
        select(TaskExecution)
        .where(TaskExecution.task_id == task_id)
        .order_by(TaskExecution.triggered_at.desc())
        .limit(limit)
        .offset(offset),
    )
    return list(result.scalars().all())


async def get_execution(
    db: AsyncSession,
    execution_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TaskExecution:
    execution = await db.get(TaskExecution, execution_id)
    if execution is None:
        raise ValueError("Execution not found")
    task = await db.get(ScheduledTask, execution.task_id)
    if task is None or task.user_id != user_id:
        raise ValueError("Access denied")
    return execution


async def load_all_enabled_tasks(db: AsyncSession) -> list[ScheduledTask]:
    result = await db.execute(
        select(ScheduledTask).where(ScheduledTask.is_enabled == True),
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/admin/services/scheduler_service.py
git commit -m "feat(scheduler): add scheduler service with CRUD, toggle, trigger, and execution queries"
```

---

## Task 6: REST API router

**Files:**
- Create: `backend/app/gateway/routers/scheduler.py`

- [ ] **Step 1: Create scheduler router**

Create `backend/app/gateway/routers/scheduler.py`:

```python
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_current_user, get_db
from app.admin.models.user import User
from app.admin.services import scheduler_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class TaskCreateRequest(BaseModel):
    agent_description: str = Field(default="", description="Agent description / task name")
    agent_soul: str = Field(default="", description="SOUL.md content (prompt with {{variables}})")
    skill_name: str = Field(..., description="Skill to bind")
    cron_expression: str = Field(..., description="Cron expression (5 fields)")
    custom_variables: dict[str, str] | None = Field(default=None, description="Custom template variables")


class TaskUpdateRequest(BaseModel):
    agent_description: str | None = None
    agent_soul: str | None = None
    skill_name: str | None = None
    cron_expression: str | None = None
    custom_variables: dict[str, str] | None = None


class TaskResponse(BaseModel):
    id: str
    agent_name: str
    agent_description: str
    agent_soul: str
    skill_name: str
    cron_expression: str
    custom_variables: dict | None
    is_enabled: bool
    status: str
    last_execution_at: str | None
    next_execution_at: str | None
    error_message: str | None


class ExecutionResponse(BaseModel):
    id: str
    task_id: str
    status: str
    triggered_at: str
    completed_at: str | None
    thread_id: str | None
    messages: list | None
    error_message: str | None
    token_usage: dict | None


def _task_to_response(task) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        agent_name=task.agent_name,
        agent_description=task.agent_description,
        agent_soul=task.agent_soul,
        skill_name=task.skill_name,
        cron_expression=task.cron_expression,
        custom_variables=task.custom_variables,
        is_enabled=task.is_enabled,
        status=task.status.value if hasattr(task.status, "value") else task.status,
        last_execution_at=task.last_execution_at,
        next_execution_at=task.next_execution_at,
        error_message=task.error_message,
    )


def _exec_to_response(exec_obj) -> ExecutionResponse:
    return ExecutionResponse(
        id=str(exec_obj.id),
        task_id=str(exec_obj.task_id),
        status=exec_obj.status.value if hasattr(exec_obj.status, "value") else exec_obj.status,
        triggered_at=exec_obj.triggered_at,
        completed_at=exec_obj.completed_at,
        thread_id=exec_obj.thread_id,
        messages=exec_obj.messages,
        error_message=exec_obj.error_message,
        token_usage=exec_obj.token_usage,
    )


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await scheduler_service.list_tasks(db, user.id)
    return [_task_to_response(t) for t in tasks]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    request: TaskCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await scheduler_service.create_task(
            db,
            user.id,
            agent_description=request.agent_description,
            agent_soul=request.agent_soul,
            skill_name=request.skill_name,
            cron_expression=request.cron_expression,
            custom_variables=request.custom_variables,
        )
        return _task_to_response(task)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await scheduler_service.get_task(db, uuid.UUID(task_id), user.id)
        return _task_to_response(task)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await scheduler_service.update_task(
            db, uuid.UUID(task_id), user.id,
            agent_description=request.agent_description,
            agent_soul=request.agent_soul,
            skill_name=request.skill_name,
            cron_expression=request.cron_expression,
            custom_variables=request.custom_variables,
        )
        return _task_to_response(task)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await scheduler_service.delete_task(db, uuid.UUID(task_id), user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/toggle", response_model=TaskResponse)
async def toggle_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await scheduler_service.toggle_task(db, uuid.UUID(task_id), user.id)
        return _task_to_response(task)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/tasks/{task_id}/trigger", response_model=ExecutionResponse)
async def trigger_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        execution = await scheduler_service.trigger_task(db, uuid.UUID(task_id), user.id)
        return _exec_to_response(execution)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/tasks/{task_id}/executions", response_model=list[ExecutionResponse])
async def list_executions(
    task_id: str,
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        executions = await scheduler_service.list_executions(
            db, uuid.UUID(task_id), user.id, limit=limit, offset=offset,
        )
        return [_exec_to_response(e) for e in executions]
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/tasks/{task_id}/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    task_id: str,
    execution_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        execution = await scheduler_service.get_execution(
            db, uuid.UUID(execution_id), user.id,
        )
        return _exec_to_response(execution)
    except ValueError:
        raise HTTPException(status_code=404, detail="Execution not found")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/gateway/routers/scheduler.py
git commit -m "feat(scheduler): add REST API router with 9 endpoints"
```

---

## Task 7: Integrate into Gateway app

**Files:**
- Modify: `backend/app/gateway/app.py`

- [ ] **Step 1: Add scheduler router import and include**

In `backend/app/gateway/app.py`:

Add import at line 27 (after `from app.gateway.routers import (` block), add `scheduler` to the import list:

```python
from app.gateway.routers import (
    agents,
    artifacts,
    assistants_compat,
    channels,
    mcp,
    memory,
    models,
    runs,
    scheduler,
    skills,
    suggestions,
    thread_runs,
    threads,
    uploads,
)
```

Add router registration after line 227 (after `app.include_router(admin_audit_threads.router)`):

```python
    # Scheduler API
    app.include_router(scheduler.router)
```

- [ ] **Step 2: Add APScheduler init to lifespan**

In the `lifespan` function, after the channel service start block (after line 76) and before `yield` (line 78), add:

```python
        # Initialize scheduler
        from deerflow.scheduler.manager import SchedulerManager
        from deerflow.scheduler.executor import TaskExecutor
        from app.admin.services.scheduler_service import load_all_enabled_tasks

        sched_mgr = SchedulerManager.get_instance()
        executor = TaskExecutor(app.state.admin_session_factory)
        sched_mgr.set_executor(executor)
        sched_mgr.start()

        # Load existing enabled tasks
        async with app.state.admin_session_factory() as db:
            enabled_tasks = await load_all_enabled_tasks(db)
        for t in enabled_tasks:
            sched_mgr.register_task(str(t.id), t.cron_expression)
        logger.info("Scheduler loaded %d enabled tasks", len(enabled_tasks))
```

In the shutdown block (before `await stop_channel_service()`, around line 82), add:

```python
        # Stop scheduler
        from deerflow.scheduler.manager import SchedulerManager
        SchedulerManager.get_instance().stop()
```

- [ ] **Step 3: Run lint**

Run: `cd backend && uv run ruff check app/gateway/app.py`
Expected: No errors (fix any issues)

- [ ] **Step 4: Commit**

```bash
git add backend/app/gateway/app.py
git commit -m "feat(scheduler): integrate SchedulerManager into Gateway lifespan"
```

---

## Task 8: Backend tests

**Files:**
- Modify: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Add service-layer tests**

Append to `backend/tests/test_scheduler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from deerflow.scheduler.manager import SchedulerManager

UTC8 = timezone(timedelta(hours=8))


class TestSchedulerManager:
    def test_singleton(self):
        mgr1 = SchedulerManager.get_instance()
        mgr2 = SchedulerManager.get_instance()
        assert mgr1 is mgr2

    def test_compute_next_run_valid(self):
        result = SchedulerManager.compute_next_run("0 9 * * *")
        assert result is not None

    def test_compute_next_run_invalid(self):
        result = SchedulerManager.compute_next_run("invalid")
        assert result is None

    def test_register_and_remove_task(self):
        mgr = SchedulerManager()
        mock_executor = MagicMock()
        mock_executor.execute_task = AsyncMock()
        mgr.set_executor(mock_executor)
        mgr.start()
        mgr.register_task("test-task-id", "0 9 * * *")
        mgr.remove_task("test-task-id")
        mgr.stop()


class TestTemplateEngineExtended:
    def test_empty_template(self):
        from deerflow.scheduler.template_engine import render_template
        result = render_template("", {}, "user")
        assert result == ""

    def test_no_variables(self):
        from deerflow.scheduler.template_engine import render_template
        result = render_template("plain text", {}, "user")
        assert result == "plain text"

    def test_empty_custom_variables(self):
        from deerflow.scheduler.template_engine import render_template
        result = render_template("hello {{user_name}}", {}, "alice")
        assert result == "hello alice"

    def test_multiple_same_variable(self):
        from deerflow.scheduler.template_engine import render_template
        result = render_template("{{user_name}} says hi to {{user_name}}", {}, "bob")
        assert result == "bob says hi to bob"
```

- [ ] **Step 2: Run all scheduler tests**

Run: `cd backend && uv run pytest tests/test_scheduler.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run backend lint**

Run: `cd backend && make lint`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_scheduler.py
git commit -m "test(scheduler): add SchedulerManager and template engine tests"
```

---

## Task 9: Frontend types and API client

**Files:**
- Create: `frontend/src/core/scheduler/types.ts`
- Create: `frontend/src/core/scheduler/api.ts`
- Create: `frontend/src/core/scheduler/hooks.ts`

- [ ] **Step 1: Create TypeScript types**

Create `frontend/src/core/scheduler/types.ts`:

```typescript
export type TaskStatus = "active" | "paused" | "error";
export type ExecutionStatus = "running" | "completed" | "failed" | "skipped";

export interface ScheduledTask {
  id: string;
  agent_name: string;
  agent_description: string;
  agent_soul: string;
  skill_name: string;
  cron_expression: string;
  custom_variables: Record<string, string> | null;
  is_enabled: boolean;
  status: TaskStatus;
  last_execution_at: string | null;
  next_execution_at: string | null;
  error_message: string | null;
}

export interface TaskExecution {
  id: string;
  task_id: string;
  status: ExecutionStatus;
  triggered_at: string;
  completed_at: string | null;
  thread_id: string | null;
  messages: ChatMessage[] | null;
  error_message: string | null;
  token_usage: Record<string, unknown> | null;
}

export interface ChatMessage {
  type: string;
  content: string | ContentBlock[];
  name?: string;
  id?: string;
  additional_kwargs?: Record<string, unknown>;
}

export interface ContentBlock {
  type: string;
  text?: string;
  [key: string]: unknown;
}

export interface TaskCreateRequest {
  agent_description: string;
  agent_soul: string;
  skill_name: string;
  cron_expression: string;
  custom_variables?: Record<string, string>;
}

export interface TaskUpdateRequest {
  agent_description?: string;
  agent_soul?: string;
  skill_name?: string;
  cron_expression?: string;
  custom_variables?: Record<string, string>;
}
```

- [ ] **Step 2: Create API client**

Create `frontend/src/core/scheduler/api.ts`:

```typescript
import { authFetch } from "@/core/api";
import type {
  ScheduledTask,
  TaskExecution,
  TaskCreateRequest,
  TaskUpdateRequest,
} from "./types";

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json();
}

export async function listTasks(): Promise<ScheduledTask[]> {
  return parseJson<ScheduledTask[]>(await authFetch("/api/scheduler/tasks"));
}

export async function createTask(req: TaskCreateRequest): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(
    await authFetch("/api/scheduler/tasks", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  );
}

export async function getTask(taskId: string): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(await authFetch(`/api/scheduler/tasks/${taskId}`));
}

export async function updateTask(
  taskId: string,
  req: TaskUpdateRequest,
): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(
    await authFetch(`/api/scheduler/tasks/${taskId}`, {
      method: "PUT",
      body: JSON.stringify(req),
    }),
  );
}

export async function deleteTask(taskId: string): Promise<void> {
  const res = await authFetch(`/api/scheduler/tasks/${taskId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(res.statusText);
}

export async function toggleTask(taskId: string): Promise<ScheduledTask> {
  return parseJson<ScheduledTask>(
    await authFetch(`/api/scheduler/tasks/${taskId}/toggle`, { method: "POST" }),
  );
}

export async function triggerTask(taskId: string): Promise<TaskExecution> {
  return parseJson<TaskExecution>(
    await authFetch(`/api/scheduler/tasks/${taskId}/trigger`, { method: "POST" }),
  );
}

export async function listExecutions(
  taskId: string,
  limit = 20,
  offset = 0,
): Promise<TaskExecution[]> {
  return parseJson<TaskExecution[]>(
    await authFetch(
      `/api/scheduler/tasks/${taskId}/executions?limit=${limit}&offset=${offset}`,
    ),
  );
}

export async function getExecution(
  taskId: string,
  executionId: string,
): Promise<TaskExecution> {
  return parseJson<TaskExecution>(
    await authFetch(`/api/scheduler/tasks/${taskId}/executions/${executionId}`),
  );
}
```

- [ ] **Step 3: Create TanStack Query hooks**

Create `frontend/src/core/scheduler/hooks.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import type { TaskCreateRequest, TaskUpdateRequest } from "./types";

const TASKS_KEY = ["scheduler", "tasks"];

export function useScheduledTasks() {
  return useQuery({ queryKey: TASKS_KEY, queryFn: api.listTasks });
}

export function useTaskExecutions(taskId: string | null) {
  return useQuery({
    queryKey: [...TASKS_KEY, taskId, "executions"],
    queryFn: () => api.listExecutions(taskId!),
    enabled: !!taskId,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: TaskCreateRequest) => api.createTask(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...req }: { id: string } & TaskUpdateRequest) =>
      api.updateTask(id, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useToggleTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.toggleTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useTriggerTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.triggerTask(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/scheduler/
git commit -m "feat(scheduler): add frontend types, API client, and TanStack Query hooks"
```

---

## Task 10: i18n translations

**Files:**
- Modify: `frontend/src/core/i18n/locales/types.ts`
- Modify: `frontend/src/core/i18n/locales/en-US.ts`
- Modify: `frontend/src/core/i18n/locales/zh-CN.ts`

- [ ] **Step 1: Add type definitions**

In `frontend/src/core/i18n/locales/types.ts`, add `scheduler: string;` to the `sections` object (after `about: string;`):

```typescript
    sections: {
      appearance: string;
      memory: string;
      tools: string;
      skills: string;
      notification: string;
      about: string;
      scheduler: string;
    };
```

Also add a new `scheduler` section to the root locale type (at the same level as `settings`). Find the closing of the `settings` block and add after it. Look for the pattern and add:

```typescript
  scheduler: {
    title: string;
    description: string;
    createTask: string;
    editTask: string;
    deleteTask: string;
    deleteConfirm: string;
    deleteConfirmDescription: string;
    toggleEnable: string;
    toggleDisable: string;
    triggerNow: string;
    triggering: string;
    noTasks: string;
    taskName: string;
    taskNamePlaceholder: string;
    prompt: string;
    promptPlaceholder: string;
    skill: string;
    skillPlaceholder: string;
    cronExpression: string;
    cronPlaceholder: string;
    cronPreview: string;
    customVariables: string;
    addVariable: string;
    variableKey: string;
    variableValue: string;
    preview: string;
    save: string;
    cancel: string;
    status: string;
    lastExecution: string;
    nextExecution: string;
    noExecution: string;
    executionHistory: string;
    executionDetail: string;
    viewDetail: string;
    noExecutions: string;
    duration: string;
    messages: string;
  };
```

- [ ] **Step 2: Add English translations**

In `frontend/src/core/i18n/locales/en-US.ts`, add `scheduler: "Scheduled Tasks",` to the `settings.sections` object, and add the full `scheduler` translation block:

```typescript
    sections: {
      appearance: "Appearance",
      memory: "Memory",
      tools: "Tools",
      skills: "Skills",
      notification: "Notification",
      about: "About",
      scheduler: "Scheduled Tasks",
    },
```

At the root level of the locale object, add:

```typescript
  scheduler: {
    title: "Scheduled Tasks",
    description: "Create and manage cron-based scheduled tasks that automatically run agents with specific skills.",
    createTask: "New Task",
    editTask: "Edit Task",
    deleteTask: "Delete",
    deleteConfirm: "Delete this task?",
    deleteConfirmDescription: "This will delete the task and its associated agent. All execution history will be lost.",
    toggleEnable: "Enable",
    toggleDisable: "Disable",
    triggerNow: "Run Now",
    triggering: "Running...",
    noTasks: "No scheduled tasks yet.",
    taskName: "Task Name",
    taskNamePlaceholder: "Brief description of this task",
    prompt: "Prompt",
    promptPlaceholder: "Enter the prompt template. Use {{variable}} syntax for dynamic values.",
    skill: "Skill",
    skillPlaceholder: "Select a skill",
    cronExpression: "Cron Schedule",
    cronPlaceholder: "0 9 * * *",
    cronPreview: "Schedule preview",
    customVariables: "Custom Variables",
    addVariable: "Add Variable",
    variableKey: "Key",
    variableValue: "Value",
    preview: "Preview",
    save: "Save",
    cancel: "Cancel",
    status: "Status",
    lastExecution: "Last Run",
    nextExecution: "Next Run",
    noExecution: "-",
    executionHistory: "Execution History",
    executionDetail: "Execution Detail",
    viewDetail: "View",
    noExecutions: "No executions yet.",
    duration: "Duration",
    messages: "Messages",
  },
```

- [ ] **Step 3: Add Chinese translations**

In `frontend/src/core/i18n/locales/zh-CN.ts`, add `scheduler: "定时任务",` to the `settings.sections` object, and add:

```typescript
  scheduler: {
    title: "定时任务",
    description: "创建和管理基于 Cron 的定时任务，自动运行 Agent 执行指定技能。",
    createTask: "新建任务",
    editTask: "编辑任务",
    deleteTask: "删除",
    deleteConfirm: "确认删除此任务？",
    deleteConfirmDescription: "将同时删除关联的 Agent 及所有执行历史记录，此操作不可撤销。",
    toggleEnable: "启用",
    toggleDisable: "停用",
    triggerNow: "立即执行",
    triggering: "执行中...",
    noTasks: "暂无定时任务。",
    taskName: "任务名称",
    taskNamePlaceholder: "简要描述此任务",
    prompt: "提示词",
    promptPlaceholder: "输入提示词模板，使用 {{变量}} 语法插入动态值。",
    skill: "技能",
    skillPlaceholder: "选择技能",
    cronExpression: "Cron 调度",
    cronPlaceholder: "0 9 * * *",
    cronPreview: "调度预览",
    customVariables: "自定义变量",
    addVariable: "添加变量",
    variableKey: "键名",
    variableValue: "值",
    preview: "预览",
    save: "保存",
    cancel: "取消",
    status: "状态",
    lastExecution: "上次执行",
    nextExecution: "下次执行",
    noExecution: "-",
    executionHistory: "执行历史",
    executionDetail: "执行详情",
    viewDetail: "查看",
    noExecutions: "暂无执行记录。",
    duration: "耗时",
    messages: "消息",
  },
```

- [ ] **Step 4: Run typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/core/i18n/
git commit -m "feat(scheduler): add i18n translations for scheduled tasks (en-US, zh-CN)"
```

---

## Task 11: Settings dialog — add scheduler section

**Files:**
- Modify: `frontend/src/components/workspace/settings/settings-dialog.tsx`

- [ ] **Step 1: Update imports**

At the top of `settings-dialog.tsx`, add `ClockIcon` to the lucide-react import:

```typescript
import {
  BellIcon,
  ClockIcon,
  InfoIcon,
  BrainIcon,
  PaletteIcon,
  SparklesIcon,
  WrenchIcon,
} from "lucide-react";
```

Add the new page import:

```typescript
import { SchedulerSettingsPage } from "@/components/workspace/settings/scheduler-settings-page";
```

- [ ] **Step 2: Update SettingsSection type**

Change the type to include `"scheduler"`:

```typescript
type SettingsSection =
  | "appearance"
  | "memory"
  | "tools"
  | "skills"
  | "notification"
  | "scheduler";
```

- [ ] **Step 3: Add section to the sections array**

After the skills entry in the `sections` array, add:

```typescript
      { id: "scheduler", label: t.settings.sections.scheduler, icon: ClockIcon },
```

- [ ] **Step 4: Add conditional render**

After the notification render block, add:

```typescript
              {activeSection === "scheduler" && <SchedulerSettingsPage />}
```

- [ ] **Step 5: Update useMemo deps**

Add `t.settings.sections.scheduler` to the useMemo dependency array.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workspace/settings/settings-dialog.tsx
git commit -m "feat(scheduler): add scheduler tab to settings dialog"
```

---

## Task 12: Scheduler settings page component

**Files:**
- Create: `frontend/src/components/workspace/settings/scheduler-settings-page.tsx`

- [ ] **Step 1: Create the main settings page**

Create `frontend/src/components/workspace/settings/scheduler-settings-page.tsx`:

This is a large component that includes:
- Task list view with status badges
- Create/edit form with prompt textarea, skill selector, cron input with presets and human-readable preview, custom variables editor
- Execution history list (expandable per task)
- Delete confirmation dialog

The component uses Shadcn UI components (`Button`, `Input`, `Textarea`, `Select`, `Badge`, `Table`, `Dialog`, `Collapsible`) and TanStack Query hooks from `@/core/scheduler/hooks`.

Key features:
- Cron presets: "每小时" (`0 * * * *`), "每天 9:00" (`0 9 * * *`), "每周一 9:00" (`0 9 * * 1`), "每月1号" (`0 9 1 * *`)
- Cron human-readable preview using `cronstrue` (install via `pnpm add cronstrue`)
- Template variable preview: renders `{{variable}}` with current values
- Status badges: active=green, paused=yellow, error=red
- Execution status badges: running=blue spinner, completed=green, failed=red, skipped=gray

Install cronstrue first:
```bash
cd frontend && pnpm add cronstrue
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workspace/settings/scheduler-settings-page.tsx frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat(scheduler): add scheduler settings page with task CRUD, cron presets, and execution history"
```

---

## Task 13: Execution detail dialog

**Files:**
- Create: `frontend/src/components/workspace/settings/scheduler-execution-dialog.tsx`

- [ ] **Step 1: Create execution detail dialog**

Create `frontend/src/components/workspace/settings/scheduler-execution-dialog.tsx`:

This dialog displays the full conversation from a `TaskExecution`. It receives the `messages` array and renders each message using a simplified version of the chat message components:

- Human messages: right-aligned bubble
- AI messages: left-aligned bubble with markdown rendering (reuse `MarkdownContent` from `@/components/workspace/messages`)
- Tool messages: collapsible chain-of-thought block (simplified, showing tool name and result)

Uses Shadcn `Dialog` for the container, `ScrollArea` for the message list.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workspace/settings/scheduler-execution-dialog.tsx
git commit -m "feat(scheduler): add execution detail dialog with chat message rendering"
```

---

## Task 14: Verify and polish

**Files:**
- All modified files

- [ ] **Step 1: Run backend lint and tests**

Run: `cd backend && make lint && make test`
Expected: All pass

- [ ] **Step 2: Run frontend lint and typecheck**

Run: `cd frontend && pnpm lint && pnpm typecheck`
Expected: All pass

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(scheduler): address lint and typecheck issues"
```
