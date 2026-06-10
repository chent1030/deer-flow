from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from .department import Department


class UserRole(enum.StrEnum):
    SUPER_ADMIN = "super_admin"
    DEPT_ADMIN = "dept_admin"
    USER = "user"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False, length=11), nullable=False, default=UserRole.USER)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, native_enum=False, length=8), nullable=False, default=UserStatus.ACTIVE)

    department: Mapped[Department | None] = relationship("Department")
