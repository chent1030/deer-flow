"""add_agent_share_records

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_share_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_agent_name", sa.String(100), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_agent_name", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.Enum("created", "failed", name="agentsharestatus", native_enum=False, length=8),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_share_records_source_owner_id", "agent_share_records", ["source_owner_id"])
    op.create_index("ix_agent_share_records_target_user_id", "agent_share_records", ["target_user_id"])
    op.create_index("ix_agent_share_records_created_at", "agent_share_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_share_records_created_at", table_name="agent_share_records")
    op.drop_index("ix_agent_share_records_target_user_id", table_name="agent_share_records")
    op.drop_index("ix_agent_share_records_source_owner_id", table_name="agent_share_records")
    op.drop_table("agent_share_records")
