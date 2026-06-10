import logging
from datetime import datetime, timedelta, timezone

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
