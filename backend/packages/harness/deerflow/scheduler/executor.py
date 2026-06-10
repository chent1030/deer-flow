import logging
import uuid
from datetime import datetime, timedelta, timezone

from langgraph_sdk import get_client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin.models.scheduled_task import ExecutionStatus, ScheduledTask, TaskExecution
from app.admin.services.skill_service import list_visible_skills_for_user
from deerflow.config.agents_config import load_agent_config
from deerflow.scheduler.template_engine import render_template

logger = logging.getLogger(__name__)

UTC8 = timezone(timedelta(hours=8))
DEFAULT_LANGGRAPH_URL = "http://localhost:2024"
EXECUTION_TIMEOUT = 600


def _now_iso() -> str:
    return datetime.now(UTC8).isoformat()


class TaskExecutor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        langgraph_url: str = DEFAULT_LANGGRAPH_URL,
    ) -> None:
        self._session_factory = session_factory
        self._langgraph_url = langgraph_url

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
            from app.admin.models.user import User

            async with self._session_factory() as db:
                user = await db.get(User, task.user_id)
            custom_vars = task.custom_variables or {}
            user_name = user.username if user else "unknown"
            rendered_prompt = render_template(task.agent_soul, custom_vars, user_name)

            visible_skills = await list_visible_skills_for_user(
                db,
                task.user_id,
                user.role if user else "user",
                user.department_id if user else None,
            )

            agent_cfg = load_agent_config(task.agent_name, username=user_name if user else None)
            agent_model = agent_cfg.model if agent_cfg else None

            client = get_client(url=self._langgraph_url)
            thread = await client.threads.create()
            thread_id = thread["thread_id"]

            config: dict = {
                "configurable": {
                    "agent_name": task.agent_name,
                    "username": user_name,
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
