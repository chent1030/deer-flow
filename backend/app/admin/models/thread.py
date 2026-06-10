from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, now_utc8


class Thread(TimestampMixin, Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User", lazy="selectin")
    messages = relationship("ThreadMessage", back_populates="thread", cascade="all, delete-orphan", lazy="noload")

    __table_args__ = (
        Index("idx_threads_user_id", "user_id"),
        Index("idx_threads_created_at", "created_at"),
        Index("idx_threads_status", "status"),
    )


class ThreadMessage(Base):
    __tablename__ = "thread_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_utc8)

    thread = relationship("Thread", back_populates="messages")

    __table_args__ = (
        Index("idx_thread_messages_thread_id", "thread_id"),
        Index("idx_thread_messages_created_at", "created_at"),
        Index("idx_thread_messages_role", "role"),
    )
