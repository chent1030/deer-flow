from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

UTC8 = timezone(timedelta(hours=8))


def now_utc8() -> datetime:
    return datetime.now(UTC8).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc8)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc8, onupdate=now_utc8)


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
