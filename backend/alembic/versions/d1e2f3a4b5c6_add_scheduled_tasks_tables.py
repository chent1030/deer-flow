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
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
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
