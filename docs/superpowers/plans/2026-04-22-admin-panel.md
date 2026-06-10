# DeerFlow 管理端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 DeerFlow 构建完整的管理端系统，包含 JWT 认证、RBAC 权限、用户/部门/Skill 管理、MinIO 文件存储。

**Architecture:** 后端在现有 FastAPI Gateway 中新增 `app/admin/` 模块，使用 SQLAlchemy 2.0 async 访问 PostgreSQL，MinIO 存储 Skill 文件。前端为独立 SPA（React + Vite + Ant Design），通过 nginx 反向代理统一入口。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, bcrypt, PyJWT, minio, PostgreSQL, MinIO, React, Vite, Ant Design, TanStack Query, Zustand, axios

**Design Spec:** `docs/superpowers/specs/2026-04-22-admin-panel-design.md`

---

## File Map

### Backend — 新建文件

```
backend/app/admin/
├── __init__.py
├── config.py                          # AdminConfig Pydantic model, 从 config.yaml 加载
├── auth/
│   ├── __init__.py
│   ├── jwt.py                         # create_access_token, create_refresh_token, decode_token
│   ├── password.py                    # hash_password, verify_password (bcrypt)
│   └── middleware.py                  # get_current_user dependency
├── models/
│   ├── __init__.py
│   ├── base.py                        # Base, TimestampMixin, TenantMixin, UserRole, UserStatus, SkillVisibility, SkillStatus
│   ├── department.py                  # Department ORM model
│   ├── user.py                        # User ORM model
│   └── skill.py                       # Skill, SkillVisibleUser ORM models
├── schemas/
│   ├── __init__.py
│   ├── auth.py                        # LoginRequest, TokenResponse, RefreshRequest, UserInfoResponse, ChangePasswordRequest
│   ├── user.py                        # UserCreate, UserUpdate, UserStatusUpdate, UserResponse, UserListResponse
│   ├── department.py                  # DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentTreeResponse
│   └── skill.py                       # SkillUpload, SkillUpdate, SkillVisibilityUpdate, SkillReviewRequest, SkillResponse, SkillListResponse, SkillSubmitRequest, SkillWithdrawRequest
├── routers/
│   ├── __init__.py
│   ├── auth.py                        # POST /login, POST /logout, POST /refresh, GET /me, PUT /me/password
│   ├── users.py                       # GET /, POST /, GET /{id}, PUT /{id}, PUT /{id}/status, DELETE /{id}
│   ├── departments.py                 # GET /, POST /, GET /{id}, PUT /{id}, DELETE /{id}
│   └── skills.py                      # GET /, POST /, GET /{id}, GET /{id}/download, PUT /{id}, PUT /{id}/visibility, POST /{id}/submit, POST /{id}/withdraw, POST /{id}/review, DELETE /{id}
├── services/
│   ├── __init__.py
│   ├── user_service.py                # create_user, list_users, get_user, update_user, toggle_user_status, delete_user
│   ├── department_service.py          # create_department, get_department_tree, get_department, update_department, delete_department
│   └── skill_service.py              # upload_skill, list_skills, get_skill, download_skill, update_skill, set_visibility, submit_for_review, withdraw_skill, review_skill, delete_skill
├── deps.py                            # get_db, get_current_user, require_role, get_admin_config, get_minio_client
└── minio.py                           # MinioClient wrapper: upload, download_presigned, delete, ensure_bucket

backend/alembic/
├── env.py
├── script.py.mako
└── versions/
    └── 001_initial_admin_schema.py

backend/alembic.ini

backend/scripts/seed_admin.py          # 创建初始超级管理员
```

### Backend — 修改文件

```
backend/pyproject.toml                 # 新增依赖
backend/packages/harness/deerflow/config/app_config.py  # AdminConfig 字段
config.example.yaml                    # admin 配置段
backend/app/gateway/app.py             # 注册 admin routers, 初始化 DB + MinIO
```

### Frontend — 新建文件

```
admin/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.ts
├── postcss.config.js
├── index.html
├── public/
│   └── favicon.ico
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── vite-env.d.ts
    ├── types/
    │   └── index.ts                   # UserRole, UserStatus, SkillVisibility, SkillStatus, User, Department, Skill, PaginatedResponse
    ├── api/
    │   ├── client.ts                  # axios 实例 + JWT 拦截器
    │   ├── auth.ts                    # login, logout, refresh, getMe, changePassword
    │   ├── users.ts                   # listUsers, createUser, getUser, updateUser, toggleStatus, deleteUser
    │   ├── departments.ts             # getDepartmentTree, createDepartment, getDepartment, updateDepartment, deleteDepartment
    │   └── skills.ts                  # listSkills, uploadSkill, getSkill, downloadSkill, updateSkill, setVisibility, submitSkill, withdrawSkill, reviewSkill, deleteSkill
    ├── stores/
    │   └── auth.ts                    # Zustand: token, user, login, logout, refreshUser
    ├── hooks/
    │   ├── useUsers.ts                # TanStack Query hooks for users
    │   ├── useDepartments.ts          # TanStack Query hooks for departments
    │   └── useSkills.ts               # TanStack Query hooks for skills
    ├── components/
    │   ├── AuthGuard.tsx               # 路由守卫
    │   └── RoleGuard.tsx               # 角色守卫
    ├── layouts/
    │   └── AdminLayout.tsx             # ProLayout + 侧边栏菜单
    └── pages/
        ├── login/
        │   └── LoginPage.tsx
        ├── dashboard/
        │   └── DashboardPage.tsx
        ├── users/
        │   ├── UserListPage.tsx
        │   └── UserFormModal.tsx
        ├── departments/
        │   ├── DepartmentPage.tsx
        │   └── DepartmentForm.tsx
        └── skills/
            ├── SkillListPage.tsx
            ├── SkillUploadModal.tsx
            └── SkillReviewModal.tsx
```

### Tests — 新建文件

```
backend/tests/test_admin/
├── __init__.py
├── conftest.py                        # async db fixture, test client, seed data
├── test_auth_api.py                   # 登录/登出/刷新/个人信息/修改密码
├── test_user_api.py                   # 用户 CRUD + 权限检查
├── test_department_api.py             # 部门 CRUD + 权限检查
└── test_skill_api.py                  # Skill 上传/审核/可见性/权限检查
```

### Deployment — 修改文件

```
Makefile                               # admin-install, admin-dev, admin-build, db-migrate, db-seed
docker/docker-compose-dev.yaml         # 新增 postgres + minio 服务
scripts/serve.sh                       # nginx 新增 /admin 路由 (or nginx config template)
```

---

## Task 1: 后端依赖与配置扩展

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `config.example.yaml`
- Create: `backend/app/admin/__init__.py`
- Create: `backend/app/admin/config.py`

- [ ] **Step 1: 添加后端依赖到 pyproject.toml**

在 `backend/pyproject.toml` 的 `dependencies` 列表末尾添加：

```toml
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "bcrypt>=4.0",
    "PyJWT>=2.10",
    "minio>=7.2",
```

- [ ] **Step 2: 安装新依赖**

Run: `cd backend && uv sync`
Expected: 成功安装所有新包

- [ ] **Step 3: 创建 admin 模块 `__init__.py`**

创建 `backend/app/admin/__init__.py`，内容为空文件。

- [ ] **Step 4: 创建 AdminConfig**

创建 `backend/app/admin/config.py`：

```python
from pydantic import BaseModel, Field


class MinioConfig(BaseModel):
    endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    access_key: str = Field(default="", description="MinIO access key")
    secret_key: str = Field(default="", description="MinIO secret key")
    bucket: str = Field(default="deerflow-skills", description="MinIO bucket name")
    secure: bool = Field(default=False, description="Use HTTPS")


class JwtConfig(BaseModel):
    secret_key: str = Field(default="change-me-in-production", description="JWT signing key")
    access_token_expire_minutes: int = Field(default=60, ge=1, description="Access token TTL")
    refresh_token_expire_days: int = Field(default=7, ge=1, description="Refresh token TTL")


class InitialSuperAdminConfig(BaseModel):
    username: str = Field(default="admin", description="Initial super admin username")
    password: str = Field(default="admin123", description="Initial super admin password")
    email: str = Field(default="admin@example.com", description="Initial super admin email")


class AdminConfig(BaseModel):
    database_url: str = Field(
        default="postgresql+asyncpg://deerflow:deerflow@localhost:5432/deerflow_admin",
        description="PostgreSQL connection URL",
    )
    minio: MinioConfig = Field(default_factory=MinioConfig)
    jwt: JwtConfig = Field(default_factory=JwtConfig)
    initial_super_admin: InitialSuperAdminConfig = Field(default_factory=InitialSuperAdminConfig)
```

- [ ] **Step 5: 在 config.example.yaml 末尾添加 admin 配置段**

在 `config.example.yaml` 末尾添加：

```yaml
# ============================================================================
# Admin Panel Configuration
# ============================================================================
admin:
  # PostgreSQL connection URL for the admin system
  database_url: postgresql+asyncpg://deerflow:deerflow@localhost:5432/deerflow_admin

  # MinIO object storage for skill files
  minio:
    endpoint: localhost:9000
    access_key: $MINIO_ACCESS_KEY
    secret_key: $MINIO_SECRET_KEY
    bucket: deerflow-skills
    secure: false

  # JWT authentication settings
  jwt:
    secret_key: $JWT_SECRET_KEY
    access_token_expire_minutes: 60
    refresh_token_expire_days: 7

  # Initial super admin account (created on first seed)
  initial_super_admin:
    username: admin
    password: $ADMIN_INITIAL_PASSWORD
    email: admin@example.com
```

同时更新 `config_version` 值加 1。

- [ ] **Step 6: 在 app_config.py 中加载 AdminConfig**

在 `backend/packages/harness/deerflow/config/app_config.py` 中：
- 导入 `AdminConfig`
- 在 `AppConfig` 类中添加 `admin: AdminConfig = Field(default_factory=AdminConfig)`
- 在 `from_file()` 方法中添加 admin 段的加载逻辑（与 summarization 类似）

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/admin/ config.example.yaml backend/packages/harness/deerflow/config/app_config.py
git commit -m "feat(admin): add admin config and backend dependencies"
```

---

## Task 2: 数据库模型与 Alembic 迁移

**Files:**
- Create: `backend/app/admin/models/__init__.py`
- Create: `backend/app/admin/models/base.py`
- Create: `backend/app/admin/models/department.py`
- Create: `backend/app/admin/models/user.py`
- Create: `backend/app/admin/models/skill.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/001_initial_admin_schema.py`

- [ ] **Step 1: 创建 base model**

创建 `backend/app/admin/models/base.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
```

- [ ] **Step 2: 创建 department model**

创建 `backend/app/admin/models/department.py`：

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, TenantMixin


class Department(Base, TimestampMixin, TenantMixin):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )

    parent: Mapped[Optional["Department"]] = relationship(
        "Department", remote_side=[id], backref="children"
    )
```

- [ ] **Step 3: 创建 user model**

创建 `backend/app/admin/models/user.py`：

```python
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, TenantMixin


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    DEPT_ADMIN = "dept_admin"
    USER = "user"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)

    department: Mapped[Optional["Department"]] = relationship("Department")
```

- [ ] **Step 4: 创建 skill models**

创建 `backend/app/admin/models/skill.py`：

```python
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, TenantMixin


class SkillVisibility(str, enum.Enum):
    COMPANY = "company"
    DEPARTMENT = "department"
    SPECIFIC_USERS = "specific_users"
    PRIVATE = "private"


class SkillStatus(str, enum.Enum):
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
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    visibility: Mapped[SkillVisibility] = mapped_column(
        Enum(SkillVisibility), nullable=False, default=SkillVisibility.PRIVATE
    )
    status: Mapped[SkillStatus] = mapped_column(
        Enum(SkillStatus), nullable=False, default=SkillStatus.PENDING_REVIEW
    )
    minio_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])
    visible_users: Mapped[list["SkillVisibleUser"]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class SkillVisibleUser(Base):
    __tablename__ = "skill_visible_users"

    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)

    skill: Mapped["Skill"] = relationship(back_populates="visible_users")
    user: Mapped["User"] = relationship()
```

- [ ] **Step 5: 创建 models `__init__.py`**

创建 `backend/app/admin/models/__init__.py`：

```python
from .base import Base
from .department import Department
from .user import User, UserRole, UserStatus
from .skill import Skill, SkillVisibleUser, SkillVisibility, SkillStatus

__all__ = [
    "Base", "Department", "User", "UserRole", "UserStatus",
    "Skill", "SkillVisibleUser", "SkillVisibility", "SkillStatus",
]
```

- [ ] **Step 6: 初始化 Alembic**

Run: `cd backend && uv run alembic init alembic`
Expected: 生成 `alembic/` 目录和 `alembic.ini`

- [ ] **Step 7: 配置 alembic/env.py**

修改生成的 `backend/alembic/env.py`，关键改动：
- 导入 `app.admin.models` 中的 `Base` 和所有模型
- 设置 `target_metadata = Base.metadata`
- 配置 async engine 从 `get_app_config().admin.database_url` 获取
- 使用 `run_async_migrations` 替换同步 `run_migrations`

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.admin.models import Base  # noqa: F401 — ensure all models are registered
from deerflow.config import get_app_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return get_app_config().admin.database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: 修改 alembic.ini 中的 sqlalchemy.url**

将 `backend/alembic.ini` 中的 `sqlalchemy.url` 行改为占位值（env.py 会覆盖）：

```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```

- [ ] **Step 9: 生成初始迁移**

Run: `cd backend && uv run alembic revision --autogenerate -m "initial_admin_schema"`
Expected: 生成包含 departments, users, skills, skill_visible_users 四张表的迁移文件

- [ ] **Step 10: 检查迁移文件**

打开生成的迁移文件，确认包含：
- `departments` 表：id, name, parent_id, tenant_id, created_at, updated_at
- `users` 表：id, username, password_hash, display_name, email, department_id, role, status, tenant_id, created_at, updated_at
- `skills` 表：id, name, description, version, author_id, department_id, visibility, status, minio_bucket, minio_object_key, file_size, reviewed_by, reviewed_at, review_comment, tenant_id, created_at, updated_at
- `skill_visible_users` 表：skill_id, user_id（联合主键）
- 所有外键约束正确

- [ ] **Step 11: Commit**

```bash
git add backend/app/admin/models/ backend/alembic/ backend/alembic.ini
git commit -m "feat(admin): add database models and alembic migration setup"
```

---

## Task 3: 认证模块（JWT + bcrypt + 中间件）

**Files:**
- Create: `backend/app/admin/auth/__init__.py`
- Create: `backend/app/admin/auth/password.py`
- Create: `backend/app/admin/auth/jwt.py`
- Create: `backend/app/admin/auth/middleware.py`
- Create: `backend/app/admin/deps.py`

- [ ] **Step 1: 创建密码工具**

创建 `backend/app/admin/auth/password.py`：

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
```

- [ ] **Step 2: 创建 JWT 工具**

创建 `backend/app/admin/auth/jwt.py`：

```python
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.admin.config import JwtConfig


def create_access_token(user_id: uuid.UUID, username: str, role: str, department_id: uuid.UUID | None, tenant_id: str, config: JwtConfig) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "department_id": str(department_id) if department_id else None,
        "tenant_id": tenant_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, config.secret_key, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID, config: JwtConfig) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=config.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, config.secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict:
    return jwt.decode(token, secret_key, algorithms=["HS256"])
```

- [ ] **Step 3: 创建认证中间件**

创建 `backend/app/admin/auth/middleware.py`：

```python
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.jwt import decode_token
from app.admin.models.user import User, UserRole, UserStatus
from deerflow.config import get_app_config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> User:
    config = get_app_config().admin.jwt
    try:
        payload = decode_token(token, config.secret_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return _UserHolder(user_id=user_id, role=payload.get("role"), department_id=payload.get("department_id"))


class _UserHolder:
    """Placeholder user resolved from JWT. Actual DB lookup happens in require_role or per-request."""
    def __init__(self, user_id: str, role: str | None, department_id: str | None):
        self.id = uuid.UUID(user_id)
        self.role = UserRole(role) if role else UserRole.USER
        self.department_id = uuid.UUID(department_id) if department_id else None
```

注意：这里先用轻量的 JWT payload 解析。完整的 DB 查询用户在 `deps.py` 的 `get_current_user` 中实现，因为需要 `AsyncSession`。

- [ ] **Step 4: 创建 deps.py 依赖注入**

创建 `backend/app/admin/deps.py`：

```python
import uuid
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.admin.auth.jwt import decode_token
from app.admin.config import AdminConfig
from app.admin.models.user import User, UserRole, UserStatus
from deerflow.config import get_app_config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login")


def _get_admin_config() -> AdminConfig:
    return get_app_config().admin


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from app.gateway.app import get_app

    app = get_app()
    session_factory: async_sessionmaker[AsyncSession] = app.state.admin_session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    config = _get_admin_config().jwt
    try:
        payload = decode_token(token, config.secret_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return user


def require_role(*roles: UserRole):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _checker
```

- [ ] **Step 5: 创建 auth 子模块 `__init__.py`**

空文件。

- [ ] **Step 6: 编写密码工具测试**

创建 `backend/tests/test_admin/__init__.py`（空文件）。

创建 `backend/tests/test_admin/test_password.py`：

```python
from app.admin.auth.password import hash_password, verify_password


def test_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True


def test_wrong_password():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_different_hashes():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1) is True
    assert verify_password("same", h2) is True
```

- [ ] **Step 7: 运行测试**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_admin/test_password.py -v`
Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/admin/auth/ backend/app/admin/deps.py backend/tests/test_admin/
git commit -m "feat(admin): add JWT auth, password hashing, and dependency injection"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `backend/app/admin/schemas/__init__.py`
- Create: `backend/app/admin/schemas/auth.py`
- Create: `backend/app/admin/schemas/user.py`
- Create: `backend/app/admin/schemas/department.py`
- Create: `backend/app/admin/schemas/skill.py`

- [ ] **Step 1: 创建 auth schemas**

创建 `backend/app/admin/schemas/__init__.py`（空文件）。

创建 `backend/app/admin/schemas/auth.py`：

```python
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfoResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str
    department_id: str | None = None
    status: str

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)
```

- [ ] **Step 2: 创建 user schemas**

创建 `backend/app/admin/schemas/user.py`：

```python
import uuid
from pydantic import BaseModel, Field

from app.admin.models.user import UserRole, UserStatus


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(default="", max_length=255)
    department_id: uuid.UUID | None = None
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    role: UserRole | None = None


class UserStatusUpdate(BaseModel):
    status: UserStatus


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str
    department_id: str | None
    status: str
    created_at: str | None = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 3: 创建 department schemas**

创建 `backend/app/admin/schemas/department.py`：

```python
import uuid
from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    parent_id: uuid.UUID | None = None


class DepartmentResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None
    created_at: str | None = None
    children: list["DepartmentResponse"] = []
    member_count: int = 0

    class Config:
        from_attributes = True


class DepartmentTreeResponse(BaseModel):
    departments: list[DepartmentResponse]
```

- [ ] **Step 4: 创建 skill schemas**

创建 `backend/app/admin/schemas/skill.py`：

```python
import uuid
from pydantic import BaseModel, Field

from app.admin.models.skill import SkillStatus, SkillVisibility


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    version: str | None = Field(default=None, max_length=20)


class SkillVisibilityUpdate(BaseModel):
    visibility: SkillVisibility
    visible_user_ids: list[uuid.UUID] = Field(default_factory=list)


class SkillReviewRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject)$")
    comment: str = Field(default="", max_length=1000)


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    version: str
    author_id: str
    department_id: str | None
    visibility: str
    status: str
    file_size: int
    reviewed_by: str | None
    reviewed_at: str | None
    review_comment: str | None
    created_at: str | None
    author_name: str | None = None
    department_name: str | None = None
    visible_user_ids: list[str] = []

    class Config:
        from_attributes = True


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/admin/schemas/
git commit -m "feat(admin): add Pydantic request/response schemas"
```

---

## Task 5: MinIO 客户端封装

**Files:**
- Create: `backend/app/admin/minio.py`

- [ ] **Step 1: 创建 MinIO 客户端**

创建 `backend/app/admin/minio.py`：

```python
import io
import logging
import uuid
from urllib.parse import quote

from minio import Minio
from minio.error import S3Error

from app.admin.config import MinioConfig

logger = logging.getLogger(__name__)


class MinioClient:
    def __init__(self, config: MinioConfig):
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        self._bucket = config.bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Created MinIO bucket: %s", self._bucket)

    def upload(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put_object(
            self._bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get_presigned_url(self, object_key: str, expires_hours: int = 1) -> str:
        from datetime import timedelta
        return self._client.presigned_get_object(self._bucket, object_key, expires=timedelta(hours=expires_hours))

    def delete(self, object_key: str) -> None:
        self._client.remove_object(self._bucket, object_key)

    @property
    def bucket(self) -> str:
        return self._bucket

    def build_skill_key(self, department_id: uuid.UUID | None, skill_id: uuid.UUID, filename: str) -> str:
        dept = str(department_id) if department_id else "global"
        return f"skills/{dept}/{skill_id}/{filename}"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/admin/minio.py
git commit -m "feat(admin): add MinIO client wrapper"
```

---

## Task 6: Auth API 路由

**Files:**
- Create: `backend/app/admin/routers/__init__.py`（空文件）
- Create: `backend/app/admin/routers/auth.py`

- [ ] **Step 1: 创建 auth router**

创建 `backend/app/admin/routers/auth.py`：

```python
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.admin.auth.password import verify_password, hash_password
from app.admin.deps import get_db, get_current_user
from app.admin.models.user import User, UserRole, UserStatus
from app.admin.schemas.auth import (
    ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse, UserInfoResponse,
)
from deerflow.config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


def _user_to_response(user: User) -> UserInfoResponse:
    return UserInfoResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role.value,
        department_id=str(user.department_id) if user.department_id else None,
        status=user.status.value,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    config = get_app_config().admin.jwt
    access = create_access_token(user.id, user.username, user.role.value, user.department_id, user.tenant_id, config)
    refresh = create_refresh_token(user.id, config)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    config = get_app_config().admin.jwt
    try:
        payload = decode_token(req.refresh_token, config.secret_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not available")
    access = create_access_token(user.id, user.username, user.role.value, user.department_id, user.tenant_id, config)
    refresh_token = create_refresh_token(user.id, config)
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.get("/me", response_model=UserInfoResponse)
async def get_me(user: User = Depends(get_current_user)):
    return _user_to_response(user)


@router.put("/me/password")
async def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")
    user.password_hash = hash_password(req.new_password)
    db.add(user)
    await db.flush()
    return {"message": "Password changed successfully"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/admin/routers/
git commit -m "feat(admin): add auth router (login/refresh/me/password)"
```

---

## Task 7: Department API

**Files:**
- Create: `backend/app/admin/services/__init__.py`（空文件）
- Create: `backend/app/admin/services/department_service.py`
- Create: `backend/app/admin/routers/departments.py`

- [ ] **Step 1: 创建 department service**

创建 `backend/app/admin/services/department_service.py`，实现以下函数：
- `create_department(db, name, parent_id) -> Department`
- `get_department_tree(db) -> list[Department]` — 查询所有部门，在内存中组装树形结构
- `get_department(db, dept_id) -> Department`
- `update_department(db, dept, name, parent_id) -> Department`
- `delete_department(db, dept_id)` — 检查是否有子部门或用户，有则拒绝

每个函数包含完整的 SQLAlchemy 查询逻辑。

- [ ] **Step 2: 创建 department router**

创建 `backend/app/admin/routers/departments.py`，实现设计文档中的 5 个端点：

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/admin/departments` | super_admin, dept_admin |
| POST | `/api/admin/departments` | super_admin |
| GET | `/api/admin/departments/{id}` | super_admin, dept_admin(本部门) |
| PUT | `/api/admin/departments/{id}` | super_admin |
| DELETE | `/api/admin/departments/{id}` | super_admin |

使用 `deps.require_role(UserRole.SUPER_ADMIN)` 和 `deps.require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)` 做权限控制。dept_admin 访问详情时需校验 `user.department_id == dept_id`。

- [ ] **Step 3: Commit**

```bash
git add backend/app/admin/services/department_service.py backend/app/admin/routers/departments.py
git commit -m "feat(admin): add department service and router"
```

---

## Task 8: User API

**Files:**
- Create: `backend/app/admin/services/user_service.py`
- Create: `backend/app/admin/routers/users.py`

- [ ] **Step 1: 创建 user service**

创建 `backend/app/admin/services/user_service.py`，实现以下函数：
- `create_user(db, username, password, display_name, email, department_id, role) -> User` — 密码 bcrypt 哈希后存储
- `list_users(db, page, page_size, search, department_id) -> (list[User], int)` — 分页 + 搜索 + 部门筛选
- `get_user(db, user_id) -> User`
- `update_user(db, user, display_name, email, department_id, role) -> User`
- `toggle_user_status(db, user) -> User` — active ↔ disabled 切换
- `delete_user(db, user_id)` — 硬删除

- [ ] **Step 2: 创建 user router**

创建 `backend/app/admin/routers/users.py`，实现设计文档中的 6 个端点：

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/admin/users` | super_admin, dept_admin |
| POST | `/api/admin/users` | super_admin, dept_admin(仅本部门) |
| GET | `/api/admin/users/{id}` | super_admin, dept_admin(本部门) |
| PUT | `/api/admin/users/{id}` | super_admin, dept_admin(本部门) |
| PUT | `/api/admin/users/{id}/status` | super_admin |
| DELETE | `/api/admin/users/{id}` | super_admin |

dept_admin 创建用户时 `department_id` 强制为自己部门。list_users 时 dept_admin 只能看本部门。

- [ ] **Step 3: Commit**

```bash
git add backend/app/admin/services/user_service.py backend/app/admin/routers/users.py
git commit -m "feat(admin): add user service and router"
```

---

## Task 9: Skill API

**Files:**
- Create: `backend/app/admin/services/skill_service.py`
- Create: `backend/app/admin/routers/skills.py`

- [ ] **Step 1: 创建 skill service**

创建 `backend/app/admin/services/skill_service.py`，实现以下函数：
- `upload_skill(db, minio_client, name, description, version, author_id, department_id, file_data, filename) -> Skill` — 上传文件到 MinIO，创建 DB 记录，status=pending_review
- `list_skills(db, page, page_size, status, department_id, user_id, role) -> (list[Skill], int)` — 按角色过滤可见范围
- `get_skill(db, skill_id, user_id, role, department_id) -> Skill` — 按可见性规则校验
- `download_skill(minio_client, skill) -> str` — 返回预签名 URL
- `update_skill(db, skill, name, description, version) -> Skill`
- `set_visibility(db, skill, visibility, visible_user_ids) -> Skill` — 清理旧关联 + 写新关联
- `submit_for_review(db, skill) -> Skill` — withdrawn → pending_review
- `withdraw_skill(db, skill) -> Skill` — pending_review → withdrawn
- `review_skill(db, skill, reviewer_id, action, comment) -> Skill` — approve/reject
- `delete_skill(db, minio_client, skill)` — 删除 MinIO 对象 + DB 记录

- [ ] **Step 2: 创建 skill router**

创建 `backend/app/admin/routers/skills.py`，实现设计文档中的 10 个端点。文件上传使用 `UploadFile`。关键权限逻辑：

- `GET /`：按角色过滤列表（super_admin 看全部，dept_admin 看本部门，user 看自己的）
- `POST /`：接收 multipart form data（file + metadata），返回 pending_review 状态
- `POST /{id}/review`：仅 super_admin
- `PUT /{id}/visibility`：仅作者且已 approved
- `DELETE /{id}`：作者本人或 super_admin

- [ ] **Step 3: Commit**

```bash
git add backend/app/admin/services/skill_service.py backend/app/admin/routers/skills.py
git commit -m "feat(admin): add skill service, router with review and visibility"
```

---

## Task 10: Gateway 集成 + 种子脚本

**Files:**
- Modify: `backend/app/gateway/app.py`
- Create: `backend/scripts/seed_admin.py`

- [ ] **Step 1: 在 gateway/app.py 中注册 admin 模块**

在 `backend/app/gateway/app.py` 的 `create_app()` 函数中：

1. 在 lifespan 中初始化 SQLAlchemy AsyncEngine 和 session factory：
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
admin_config = get_app_config().admin
engine = create_async_engine(admin_config.database_url)
app.state.admin_session_factory = async_sessionmaker(engine, expire_on_commit=False)
```

2. 在 lifespan 中初始化 MinIO client：
```python
from app.admin.minio import MinioClient
app.state.minio_client = MinioClient(admin_config.minio)
```

3. 注册 admin routers：
```python
from app.admin.routers import auth as admin_auth
from app.admin.routers import users as admin_users
from app.admin.routers import departments as admin_depts
from app.admin.routers import skills as admin_skills
app.include_router(admin_auth.router)
app.include_router(admin_users.router)
app.include_router(admin_depts.router)
app.include_router(admin_skills.router)
```

- [ ] **Step 2: 创建种子脚本**

创建 `backend/scripts/seed_admin.py`：

```python
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.admin.auth.password import hash_password
from app.admin.models.user import User, UserRole
from deerflow.config import get_app_config


async def seed():
    config = get_app_config().admin
    engine = create_async_engine(config.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == config.initial_super_admin.username))
        if result.scalar_one_or_none() is None:
            user = User(
                username=config.initial_super_admin.username,
                password_hash=hash_password(config.initial_super_admin.password),
                display_name="Super Admin",
                email=config.initial_super_admin.email,
                role=UserRole.SUPER_ADMIN,
            )
            db.add(user)
            await db.commit()
            print(f"Created super admin: {user.username}")
        else:
            print("Super admin already exists, skipping.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/gateway/app.py backend/scripts/seed_admin.py
git commit -m "feat(admin): integrate admin module into gateway, add seed script"
```

---

## Task 11: 后端 API 集成测试

**Files:**
- Create: `backend/tests/test_admin/conftest.py`
- Create: `backend/tests/test_admin/test_auth_api.py`
- Create: `backend/tests/test_admin/test_user_api.py`
- Create: `backend/tests/test_admin/test_department_api.py`
- Create: `backend/tests/test_admin/test_skill_api.py`

- [ ] **Step 1: 创建测试 conftest**

创建 `backend/tests/test_admin/conftest.py`：
- 使用 SQLite async 内存数据库（`aiosqlite`）替代 PostgreSQL
- 创建表 `Base.metadata.create_all()`
- 提供异步 `AsyncClient` fixture
- 提供种子数据 fixture：一个 super_admin、一个 dept_admin（带部门）、一个普通 user
- 提供 auth_headers fixture 用于生成各角色 JWT

需要临时添加 `aiosqlite` 到 dev dependencies：

在 `backend/pyproject.toml` 的 `dev` dependency group 中添加 `"aiosqlite>=0.20"`。

- [ ] **Step 2: 编写 auth API 测试**

创建 `backend/tests/test_admin/test_auth_api.py`，覆盖：
- `test_login_success` — 正确密码返回 token
- `test_login_wrong_password` — 401
- `test_login_disabled_user` — 403
- `test_refresh_token` — refresh 换新 access_token
- `test_get_me` — 返回当前用户信息
- `test_change_password` — 修改密码后旧密码失效

- [ ] **Step 3: 编写 user API 测试**

创建 `backend/tests/test_admin/test_user_api.py`，覆盖：
- `test_create_user_as_super_admin`
- `test_create_user_as_dept_admin_only_own_dept`
- `test_list_users_as_super_admin_sees_all`
- `test_list_users_as_dept_admin_sees_own_dept_only`
- `test_toggle_user_status`
- `test_delete_user`
- `test_unauthorized_user_cannot_create`

- [ ] **Step 4: 编写 department API 测试**

创建 `backend/tests/test_admin/test_department_api.py`，覆盖：
- `test_create_department`
- `test_get_department_tree` — 验证树形结构
- `test_update_department`
- `test_delete_department_with_users_fails`
- `test_delete_department_succeeds_when_empty`
- `test_dept_admin_cannot_create`

- [ ] **Step 5: 编写 skill API 测试**

创建 `backend/tests/test_admin/test_skill_api.py`，覆盖：
- `test_upload_skill_returns_pending_review`
- `test_review_approve`
- `test_review_reject`
- `test_withdraw_and_resubmit`
- `test_set_visibility_company`
- `test_set_visibility_specific_users`
- `test_visibility_rules` — company 对所有人可见，department 仅同部门，private 仅作者
- `test_only_author_can_edit`
- `test_only_super_admin_can_review`

- [ ] **Step 6: 运行全部测试**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_admin/ -v`
Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
git add backend/tests/test_admin/ backend/pyproject.toml
git commit -m "test(admin): add integration tests for auth, user, department, skill APIs"
```

---

## Task 12: 前端项目脚手架

**Files:**
- Create: `admin/` 整个目录结构

- [ ] **Step 1: 初始化 Vite + React + TypeScript 项目**

Run: `pnpm create vite admin --template react-ts`

- [ ] **Step 2: 安装依赖**

Run: `cd admin && pnpm add antd @ant-design/icons @ant-design/pro-components @tanstack/react-query axios zustand react-router-dom && pnpm add -D tailwindcss @tailwindcss/vite`

- [ ] **Step 3: 配置 Tailwind**

修改 `admin/vite.config.ts`，添加 tailwindcss 插件。

创建 `admin/src/index.css`：
```css
@import "tailwindcss";
```

- [ ] **Step 4: 配置 Vite proxy**

在 `admin/vite.config.ts` 中添加开发代理：
```typescript
server: {
  port: 3002,
  proxy: {
    '/api': {
      target: 'http://localhost:8001',
      changeOrigin: true,
    },
  },
}
```

- [ ] **Step 5: 创建 TypeScript 类型**

创建 `admin/src/types/index.ts`，定义所有后端对应的类型：
- `UserRole`, `UserStatus`, `SkillVisibility`, `SkillStatus` 枚举
- `User`, `Department`, `Skill` 接口
- `PaginatedResponse<T>` 泛型接口
- `LoginRequest`, `TokenResponse` 等

- [ ] **Step 6: 验证开发服务器启动**

Run: `cd admin && pnpm dev`
Expected: 访问 `http://localhost:3002` 看到 Vite 默认页面

- [ ] **Step 7: Commit**

```bash
git add admin/
git commit -m "feat(admin): scaffold frontend SPA with Vite, React, Ant Design"
```

---

## Task 13: 前端 API 层与状态管理

**Files:**
- Create: `admin/src/api/client.ts`
- Create: `admin/src/api/auth.ts`
- Create: `admin/src/api/users.ts`
- Create: `admin/src/api/departments.ts`
- Create: `admin/src/api/skills.ts`
- Create: `admin/src/stores/auth.ts`

- [ ] **Step 1: 创建 axios client**

创建 `admin/src/api/client.ts`：
- 创建 axios 实例，baseURL 为空（走 proxy）
- 请求拦截器：从 localStorage 读取 access_token 添加 Authorization header
- 响应拦截器：捕获 401，自动调用 refresh API，成功则重试原请求，失败则清除状态跳转 `/login`

- [ ] **Step 2: 创建 auth API**

创建 `admin/src/api/auth.ts`：封装 `login`, `logout`, `refresh`, `getMe`, `changePassword` 函数。

- [ ] **Step 3: 创建 users API**

创建 `admin/src/api/users.ts`：封装 `listUsers`, `createUser`, `getUser`, `updateUser`, `toggleUserStatus`, `deleteUser` 函数。

- [ ] **Step 4: 创建 departments API**

创建 `admin/src/api/departments.ts`：封装 `getDepartmentTree`, `createDepartment`, `getDepartment`, `updateDepartment`, `deleteDepartment` 函数。

- [ ] **Step 5: 创建 skills API**

创建 `admin/src/api/skills.ts`：封装 `listSkills`, `uploadSkill`（FormData）, `getSkill`, `downloadSkill`, `updateSkill`, `setVisibility`, `submitSkill`, `withdrawSkill`, `reviewSkill`, `deleteSkill` 函数。

- [ ] **Step 6: 创建 Zustand auth store**

创建 `admin/src/stores/auth.ts`：
- state: `token`, `refreshToken`, `user` (UserInfoResponse | null)
- actions: `login(username, password)`, `logout()`, `refreshUser()`, `initialize()`（从 localStorage 恢复）
- login 成功后存 localStorage，logout 清除

- [ ] **Step 7: Commit**

```bash
git add admin/src/api/ admin/src/stores/
git commit -m "feat(admin-frontend): add API layer and auth state management"
```

---

## Task 14: 前端路由、布局与权限守卫

**Files:**
- Create: `admin/src/App.tsx`（覆盖）
- Create: `admin/src/main.tsx`（覆盖）
- Create: `admin/src/components/AuthGuard.tsx`
- Create: `admin/src/components/RoleGuard.tsx`
- Create: `admin/src/layouts/AdminLayout.tsx`
- Create: `admin/src/pages/login/LoginPage.tsx`
- Create: `admin/src/pages/dashboard/DashboardPage.tsx`

- [ ] **Step 1: 创建 AuthGuard**

创建 `admin/src/components/AuthGuard.tsx`：
- 检查 auth store 中是否有 user
- 无则 redirect 到 `/login`
- 有则渲染 children

- [ ] **Step 2: 创建 RoleGuard**

创建 `admin/src/components/RoleGuard.tsx`：
- 接收 `roles` prop 和 `children`
- 检查当前用户角色是否在 roles 列表中
- 不匹配则渲染空或 403 提示

- [ ] **Step 3: 创建 AdminLayout**

创建 `admin/src/layouts/AdminLayout.tsx`：
- 使用 Ant Design `Layout` + `Menu`
- 侧边栏菜单项根据 `user.role` 动态渲染：
  - super_admin: Dashboard, 用户管理, 部门管理, Skill 管理, Skill 审核
  - dept_admin: Dashboard, 用户管理, Skill 管理
  - user: Dashboard, Skill 管理
- 顶部右侧显示用户名 + 登出按钮
- Outlet 渲染子路由

- [ ] **Step 4: 创建 LoginPage**

创建 `admin/src/pages/login/LoginPage.tsx`：
- 居中卡片，用户名 + 密码表单
- 使用 Ant Design `Form`, `Input`, `Button`
- 提交调用 auth store 的 login，成功跳转 `/admin/dashboard`

- [ ] **Step 5: 创建 DashboardPage**

创建 `admin/src/pages/dashboard/DashboardPage.tsx`：
- 简单的统计卡片：用户总数、部门总数、待审核 Skill 数、已发布 Skill 数
- 使用 Ant Design `Card`, `Statistic`, `Row`, `Col`
- 调用各 list API 获取 total 数据

- [ ] **Step 6: 配置路由**

修改 `admin/src/App.tsx`：
```tsx
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<AuthGuard><AdminLayout /></AuthGuard>}>
            <Route index element={<Navigate to="dashboard" />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="users" element={<RoleGuard roles={[UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]}><UserListPage /></RoleGuard>} />
            <Route path="departments" element={<RoleGuard roles={[UserRole.SUPER_ADMIN]}><DepartmentPage /></RoleGuard>} />
            <Route path="skills" element={<SkillListPage />} />
            <Route path="skills/review" element={<RoleGuard roles={[UserRole.SUPER_ADMIN]}><SkillListPage showReview /></RoleGuard>} />
          </Route>
          <Route path="*" element={<Navigate to="/admin" />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

修改 `admin/src/main.tsx`：渲染 `<App />` 并初始化 auth store。

- [ ] **Step 7: 验证前端启动**

Run: `cd admin && pnpm dev`
Expected: 访问 `http://localhost:3002` 自动跳转登录页，输入后可进入 dashboard（需后端运行）

- [ ] **Step 8: Commit**

```bash
git add admin/src/
git commit -m "feat(admin-frontend): add routing, layout, auth guard, login page"
```

---

## Task 15: 前端用户管理页

**Files:**
- Create: `admin/src/hooks/useUsers.ts`
- Create: `admin/src/pages/users/UserListPage.tsx`
- Create: `admin/src/pages/users/UserFormModal.tsx`

- [ ] **Step 1: 创建用户 hooks**

创建 `admin/src/hooks/useUsers.ts`：
- `useUsers(page, pageSize, search, departmentId)` — TanStack Query
- `useCreateUser()` — mutation + cache invalidation
- `useUpdateUser()` — mutation + cache invalidation
- `useToggleUserStatus()` — mutation
- `useDeleteUser()` — mutation + cache invalidation

- [ ] **Step 2: 创建用户列表页**

创建 `admin/src/pages/users/UserListPage.tsx`：
- Ant Design `ProTable`（或 `Table`），列：用户名、显示名、角色、部门、状态、操作
- 顶部搜索框 + 部门筛选下拉
- 操作列：编辑、启用/禁用、删除（按角色显示）
- 点击"新建用户"打开 `UserFormModal`

- [ ] **Step 3: 创建用户表单弹窗**

创建 `admin/src/pages/users/UserFormModal.tsx`：
- Ant Design `Modal` + `Form`
- 字段：用户名（新建时必填）、密码（新建时必填）、显示名、邮箱、部门（下拉）、角色（下拉）
- dept_admin 时部门选择锁定为本部门，角色只能选 user
- 提交调用对应 mutation

- [ ] **Step 4: Commit**

```bash
git add admin/src/hooks/useUsers.ts admin/src/pages/users/
git commit -m "feat(admin-frontend): add user management page"
```

---

## Task 16: 前端部门管理页

**Files:**
- Create: `admin/src/hooks/useDepartments.ts`
- Create: `admin/src/pages/departments/DepartmentPage.tsx`
- Create: `admin/src/pages/departments/DepartmentForm.tsx`

- [ ] **Step 1: 创建部门 hooks**

创建 `admin/src/hooks/useDepartments.ts`：
- `useDepartmentTree()` — TanStack Query
- `useCreateDepartment()` — mutation
- `useUpdateDepartment()` — mutation
- `useDeleteDepartment()` — mutation

- [ ] **Step 2: 创建部门管理页**

创建 `admin/src/pages/departments/DepartmentPage.tsx`：
- Ant Design `Tree` 组件展示部门树
- 每个节点右侧操作按钮：编辑、新增子部门、删除
- 删除前 confirm，如有用户则提示先转移

- [ ] **Step 3: 创建部门表单**

创建 `admin/src/pages/departments/DepartmentForm.tsx`：
- Modal + Form
- 字段：部门名称、上级部门（TreeSelect）

- [ ] **Step 4: Commit**

```bash
git add admin/src/hooks/useDepartments.ts admin/src/pages/departments/
git commit -m "feat(admin-frontend): add department management page"
```

---

## Task 17: 前端 Skill 管理页

**Files:**
- Create: `admin/src/hooks/useSkills.ts`
- Create: `admin/src/pages/skills/SkillListPage.tsx`
- Create: `admin/src/pages/skills/SkillUploadModal.tsx`
- Create: `admin/src/pages/skills/SkillReviewModal.tsx`

- [ ] **Step 1: 创建 Skill hooks**

创建 `admin/src/hooks/useSkills.ts`：
- `useSkills(page, pageSize, status, departmentId)` — TanStack Query
- `useUploadSkill()` — mutation (FormData)
- `useUpdateSkill()` — mutation
- `useSetVisibility()` — mutation
- `useSubmitSkill()` — mutation
- `useWithdrawSkill()` — mutation
- `useReviewSkill()` — mutation
- `useDeleteSkill()` — mutation

- [ ] **Step 2: 创建 Skill 列表页**

创建 `admin/src/pages/skills/SkillListPage.tsx`：
- 标签页（Ant Design `Tabs`）：全部 / 待审核 / 已通过 / 已驳回 / 已撤回
- 表格列：名称、版本、作者、部门、可见性、状态、上传时间、操作
- 操作按钮按状态和角色显示：
  - pending_review：作者可撤回；super_admin 可审核
  - approved：作者可设置可见性
  - rejected/withdrawn：作者可重新提交或编辑
  - 所有：super_admin 可删除
- 支持接收 `showReview` prop，进入审核模式（仅 super_admin 可见）

- [ ] **Step 3: 创建上传弹窗**

创建 `admin/src/pages/skills/SkillUploadModal.tsx`：
- 文件拖拽上传区域（Ant Design `Upload.Dragger`）
- 表单：名称、描述、版本、可见性（可选，默认 private）
- 提交构建 FormData 调用 uploadSkill API

- [ ] **Step 4: 创建审核弹窗**

创建 `admin/src/pages/skills/SkillReviewModal.tsx`：
- 显示 Skill 详情（名称、描述、版本、文件大小、作者）
- 审核操作：通过 / 驳回（Radio）
- 审核意见（TextArea）
- 提交调用 reviewSkill API

- [ ] **Step 5: Commit**

```bash
git add admin/src/hooks/useSkills.ts admin/src/pages/skills/
git commit -m "feat(admin-frontend): add skill management and review pages"
```

---

## Task 18: 部署集成（Docker + nginx + Makefile）

**Files:**
- Modify: `docker/docker-compose-dev.yaml`
- Modify: `Makefile`
- Modify: nginx 配置模板（在 `scripts/` 中查找 nginx template）

- [ ] **Step 1: Docker Compose 新增服务**

在 `docker/docker-compose-dev.yaml` 中添加 PostgreSQL 和 MinIO 服务（参见设计文档 4.2 节）。

- [ ] **Step 2: Makefile 新增命令**

在 `Makefile` 中添加：

```makefile
admin-install:
	@cd admin && pnpm install

admin-dev:
	@cd admin && pnpm dev

admin-build:
	@cd admin && pnpm build

db-migrate:
	@cd backend && PYTHONPATH=. uv run alembic upgrade head

db-seed:
	@cd backend && PYTHONPATH=. uv run python scripts/seed_admin.py
```

同时更新 `install` 目标，加入 `admin-install`。

- [ ] **Step 3: nginx 配置更新**

在 nginx 配置模板中添加 `/admin` 路由：
```
location /admin {
    alias /path/to/admin/dist;
    try_files $uri $uri/ /admin/index.html;
}
```

生产环境 serve 静态文件，开发环境 proxy 到 `localhost:3002`。

- [ ] **Step 4: 更新 AGENTS.md**

在 `AGENTS.md` 中添加管理端相关命令说明。

- [ ] **Step 5: Commit**

```bash
git add docker/docker-compose-dev.yaml Makefile scripts/ docs/superpowers/
git commit -m "feat(admin): add Docker, nginx, Makefile integration"
```

---

## Task 19: 端到端验证

- [ ] **Step 1: 启动依赖服务**

Run: `cd docker && docker compose -f docker-compose-dev.yaml up -d postgres minio`
Expected: PostgreSQL (5432) 和 MinIO (9000) 运行

- [ ] **Step 2: 执行数据库迁移**

Run: `cd backend && PYTHONPATH=. uv run alembic upgrade head`
Expected: 创建 4 张表

- [ ] **Step 3: 创建初始管理员**

Run: `cd backend && PYTHONPATH=. uv run python scripts/seed_admin.py`
Expected: `Created super admin: admin`

- [ ] **Step 4: 运行全部后端测试**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_admin/ -v`
Expected: 全部通过

- [ ] **Step 5: 启动后端服务**

Run: `cd backend && make gateway`
Expected: Gateway 启动，admin routers 注册成功

- [ ] **Step 6: 验证 API**

Run: `curl -X POST http://localhost:8001/api/admin/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'`
Expected: 返回 access_token 和 refresh_token

- [ ] **Step 7: 启动前端开发服务器**

Run: `cd admin && pnpm dev`
Expected: 访问 `http://localhost:3002` 看到登录页

- [ ] **Step 8: 登录验证**

在浏览器中用 admin / admin123 登录，验证 dashboard 显示统计数据，各菜单可访问。

- [ ] **Step 9: 最终 Commit**

```bash
git add -A
git commit -m "chore(admin): final e2e verification"
```

---

## 自检

1. **Spec 覆盖**：逐项对照设计文档 — 认证 API ✓、用户 CRUD ✓、部门 CRUD ✓、Skill 上传/审核/可见性 ✓、MinIO ✓、PostgreSQL ✓、JWT ✓、前端 SPA ✓、Docker ✓、nginx ✓、Makefile ✓
2. **占位符扫描**：无 TBD/TODO/待定内容
3. **类型一致性**：所有 models/schemas/routers 中的枚举值和字段名一致
