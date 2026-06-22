from datetime import timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.admin.auth.password import hash_password
from app.admin.models import Base
from app.admin.models.scheduled_task import ExecutionStatus, ScheduledTask, TaskExecution, TaskStatus
from app.admin.models.user import User, UserRole, UserStatus
from app.admin.services import scheduler_service
from app.gateway.routers.scheduler import TaskCreateRequest
from deerflow.config.agents_config import load_agent_config
from deerflow.config.paths import Paths
from deerflow.scheduler.executor import TaskExecutor
from deerflow.scheduler.manager import SchedulerManager
from deerflow.scheduler.template_engine import render_template

UTC8 = timezone(timedelta(hours=8))


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


def test_task_create_request_does_not_require_skill_name():
    request = TaskCreateRequest(
        agent_description="daily report",
        agent_soul="Summarize today's work",
        cron_expression="0 9 * * *",
    )

    assert request.skill_name == ""


def test_scheduler_status_enums_bind_database_values():
    dialect = postgresql.dialect()
    task_processor = ScheduledTask.__table__.c.status.type.bind_processor(dialect)
    execution_processor = TaskExecution.__table__.c.status.type.bind_processor(dialect)

    assert task_processor(TaskStatus.ACTIVE) == "active"
    assert execution_processor(ExecutionStatus.RUNNING) == "running"


@pytest.mark.asyncio
async def test_task_executor_loads_scheduled_agent_by_user_id(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            username="schedule-user",
            password_hash=hash_password("UserPass123!"),
            display_name="Schedule User",
            email="schedule@example.com",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.flush()
        task = ScheduledTask(
            user_id=user.id,
            agent_name="sched-test",
            agent_description="daily report",
            agent_soul="Hello {{user_name}}",
            cron_expression="0 9 * * *",
            custom_variables={},
            status=TaskStatus.ACTIVE,
        )
        session.add(task)
        await session.commit()
        task_id = str(task.id)
        user_id = str(user.id)

    captured: dict[str, str | None] = {}

    def fake_load_agent_config(name: str, *, user_id: str | None = None):
        captured["agent_name"] = name
        captured["user_id"] = user_id
        return SimpleNamespace(model=None)

    async def fake_list_visible_skills(db, requested_user_id, role, department_id):
        captured["visible_user_id"] = str(requested_user_id)
        return ["visible-skill"]

    class FakeThreads:
        async def create(self):
            return {"thread_id": "thread-1"}

        async def get_state(self, thread_id):
            return {"values": {"messages": []}}

    class FakeRuns:
        async def wait(self, **kwargs):
            captured["config_user"] = kwargs["config"]["configurable"]["username"]
            captured["config_skills"] = ",".join(kwargs["config"]["configurable"]["visible_skills"])
            return SimpleNamespace()

    class FakeClient:
        threads = FakeThreads()
        runs = FakeRuns()

    monkeypatch.setattr("deerflow.scheduler.executor.load_agent_config", fake_load_agent_config)
    monkeypatch.setattr("deerflow.scheduler.executor.list_visible_skills_for_user", fake_list_visible_skills)
    monkeypatch.setattr("deerflow.scheduler.executor.get_client", lambda url: FakeClient())

    executor = TaskExecutor(session_factory)
    await executor.execute_task(task_id)

    assert captured["agent_name"] == "sched-test"
    assert captured["user_id"] == user_id
    assert captured["visible_user_id"] == user_id
    assert captured["config_user"] == "schedule-user"
    assert captured["config_skills"] == "visible-skill"

    async with session_factory() as session:
        result = await session.execute(select(TaskExecution).where(TaskExecution.task_id == task.id))
        execution = result.scalar_one()
        assert execution.status == ExecutionStatus.COMPLETED

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_task_writes_agent_under_user_id(tmp_path, monkeypatch):
    paths = Paths(base_dir=tmp_path)
    monkeypatch.setattr("app.admin.services.scheduler_service.get_paths", lambda: paths)
    monkeypatch.setattr("deerflow.config.agents_config.get_paths", lambda: paths)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            username="schedule-user",
            password_hash=hash_password("UserPass123!"),
            display_name="Schedule User",
            email="schedule@example.com",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.flush()
        user_id = str(user.id)

        task = await scheduler_service.create_task(
            session,
            user.id,
            agent_description="daily report",
            agent_soul="Hello",
            cron_expression="0 9 * * *",
        )

    expected_dir = paths.user_agent_dir(user_id, task.agent_name)
    legacy_dir = paths.user_agent_dir("schedule-user", task.agent_name)

    assert expected_dir.exists()
    assert not legacy_dir.exists()
    assert load_agent_config(task.agent_name, user_id=user_id).name == task.agent_name

    await engine.dispose()


@pytest.mark.asyncio
async def test_task_executor_falls_back_to_legacy_username_agent_dir(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            username="legacy-schedule-user",
            password_hash=hash_password("UserPass123!"),
            display_name="Legacy Schedule User",
            email="legacy-schedule@example.com",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.flush()
        task = ScheduledTask(
            user_id=user.id,
            agent_name="sched-legacy",
            agent_description="daily report",
            agent_soul="Hello {{user_name}}",
            cron_expression="0 9 * * *",
            custom_variables={},
            status=TaskStatus.ACTIVE,
        )
        session.add(task)
        await session.commit()
        task_id = str(task.id)
        user_id = str(user.id)

    attempted_user_ids: list[str | None] = []

    async def fake_list_visible_skills(db, requested_user_id, role, department_id):
        return []

    class FakeThreads:
        async def create(self):
            return {"thread_id": "thread-legacy"}

        async def get_state(self, thread_id):
            return {"values": {"messages": []}}

    class FakeRuns:
        async def wait(self, **kwargs):
            return SimpleNamespace()

    class FakeClient:
        threads = FakeThreads()
        runs = FakeRuns()

    def fake_load_agent_config(name: str, *, user_id: str | None = None):
        attempted_user_ids.append(user_id)
        if user_id == attempted_user_ids[0]:
            raise FileNotFoundError("missing user-id path")
        return SimpleNamespace(model=None)

    monkeypatch.setattr("deerflow.scheduler.executor.load_agent_config", fake_load_agent_config)
    monkeypatch.setattr("deerflow.scheduler.executor.list_visible_skills_for_user", fake_list_visible_skills)
    monkeypatch.setattr("deerflow.scheduler.executor.get_client", lambda url: FakeClient())

    executor = TaskExecutor(session_factory)
    await executor.execute_task(task_id)

    assert attempted_user_ids == [user_id, "legacy-schedule-user"]

    await engine.dispose()


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

    @pytest.mark.asyncio
    async def test_register_and_remove_task(self):
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
        result = render_template("", {}, "user")
        assert result == ""

    def test_no_variables(self):
        result = render_template("plain text", {}, "user")
        assert result == "plain text"

    def test_empty_custom_variables(self):
        result = render_template("hello {{user_name}}", {}, "alice")
        assert result == "hello alice"

    def test_multiple_same_variable(self):
        result = render_template("{{user_name}} says hi to {{user_name}}", {}, "bob")
        assert result == "bob says hi to bob"
