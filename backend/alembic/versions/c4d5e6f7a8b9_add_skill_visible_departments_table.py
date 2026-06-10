"""add_skill_visible_departments_table

Revision ID: c4d5e6f7a8b9
Revises: aa26b9dc5720
Create Date: 2026-04-24 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "aa26b9dc5720"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_visible_departments",
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("skill_id", "department_id"),
    )


def downgrade() -> None:
    op.drop_table("skill_visible_departments")
