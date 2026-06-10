import enum
import uuid

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.admin.models.base import Base, TimestampMixin


class TaskStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ExecutionStatus(enum.StrEnum):
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
        JSON,
        nullable=True,
        default=dict,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        server_default=TaskStatus.ACTIVE.value,
    )
    last_execution_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    next_execution_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    executions: Mapped[list["TaskExecution"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("scheduled_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus),
        server_default=ExecutionStatus.RUNNING.value,
    )
    triggered_at: Mapped[str] = mapped_column(String(50), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    messages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    task: Mapped["ScheduledTask"] = relationship(back_populates="executions")
