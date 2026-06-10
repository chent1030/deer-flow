from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from .department import Department
    from .user import User


class SkillVisibility(enum.StrEnum):
    COMPANY = "company"
    DEPARTMENT = "department"
    SPECIFIC_USERS = "specific_users"
    PRIVATE = "private"


class SkillStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Skill(Base, TimestampMixin, TenantMixin):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    visibility: Mapped[SkillVisibility] = mapped_column(Enum(SkillVisibility, native_enum=False, length=14), nullable=False, default=SkillVisibility.PRIVATE)
    status: Mapped[SkillStatus] = mapped_column(Enum(SkillStatus, native_enum=False, length=14), nullable=False, default=SkillStatus.PENDING_REVIEW)
    minio_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    author: Mapped[User] = relationship("User", foreign_keys=[author_id])
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewed_by])
    visible_users: Mapped[list[SkillVisibleUser]] = relationship(back_populates="skill", cascade="all, delete-orphan")
    visible_departments: Mapped[list[SkillVisibleDepartment]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class SkillVisibleUser(Base):
    __tablename__ = "skill_visible_users"

    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)

    skill: Mapped[Skill] = relationship(back_populates="visible_users")
    user: Mapped[User] = relationship()


class SkillVisibleDepartment(Base):
    __tablename__ = "skill_visible_departments"

    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"), primary_key=True)

    skill: Mapped[Skill] = relationship(back_populates="visible_departments")
    department: Mapped[Department] = relationship()
