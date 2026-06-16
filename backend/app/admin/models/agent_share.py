from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class AgentShareStatus(enum.StrEnum):
    CREATED = "created"
    FAILED = "failed"


class AgentShareRecord(Base, TimestampMixin):
    __tablename__ = "agent_share_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    source_agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    target_agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[AgentShareStatus] = mapped_column(
        Enum(AgentShareStatus, native_enum=False, length=8),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_owner = relationship("User", foreign_keys=[source_owner_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
