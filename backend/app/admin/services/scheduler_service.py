import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone

import yaml
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models.scheduled_task import ScheduledTask, TaskExecution, TaskStatus
from app.admin.models.user import User
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
    user = await db.get(User, user_id)
    username = user.username if user else str(user_id)

    agent_dir = get_paths().user_agent_dir(username, agent_name)
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
        user = await db.get(User, user_id)
        username = user.username if user else str(user_id)
        agent_dir = get_paths().user_agent_dir(username, task.agent_name)
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

    user = await db.get(User, user_id)
    username = user.username if user else str(user_id)
    agent_dir = get_paths().user_agent_dir(username, task.agent_name)
    if agent_dir.exists():
        import platform

        if platform.system() == "Windows":
            import stat

            def _make_writable(func, path, _exc_info):
                os.chmod(path, stat.S_IWRITE)
                func(path)

            shutil.rmtree(agent_dir, onexc=_make_writable)
        else:
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

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from deerflow.scheduler.executor import TaskExecutor

    session_factory = async_sessionmaker(db.get_bind(), expire_on_commit=False)
    executor = TaskExecutor(session_factory)
    await executor.execute_task(str(task.id))

    result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == task_id).order_by(TaskExecution.triggered_at.desc()).limit(1),
    )
    return result.scalar_one()


async def list_tasks(db: AsyncSession, user_id: uuid.UUID) -> list[ScheduledTask]:
    result = await db.execute(
        select(ScheduledTask).where(ScheduledTask.user_id == user_id).order_by(ScheduledTask.created_at.desc()),
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
        select(TaskExecution).where(TaskExecution.task_id == task_id).order_by(TaskExecution.triggered_at.desc()).limit(limit).offset(offset),
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
        select(ScheduledTask).where(ScheduledTask.is_enabled == True),  # noqa: E712
    )
    return list(result.scalars().all())
