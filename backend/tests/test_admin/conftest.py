import asyncio
import io
import zipfile
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.admin.auth.jwt import create_access_token
from app.admin.auth.password import hash_password
from app.admin.config import AdminConfig, JwtConfig
from app.admin.deps import get_db
from app.admin.models import Base
from app.admin.models.department import Department
from app.admin.models.user import User, UserRole, UserStatus
from app.admin.routers import audit_threads as admin_audit_threads
from app.admin.routers import auth as admin_auth
from app.admin.routers import departments as admin_depts
from app.admin.routers import skills as admin_skills
from app.admin.routers import users as admin_users

TEST_JWT_CONFIG = JwtConfig(
    secret_key="test-secret-key",
    access_token_expire_minutes=60,
    refresh_token_expire_days=7,
)

TEST_ADMIN_CONFIG = AdminConfig(
    database_url="sqlite+aiosqlite:///:memory:",
    jwt=TEST_JWT_CONFIG,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    dept = Department(name="Engineering")
    db_session.add(dept)
    await db_session.flush()

    super_admin = User(
        username="superadmin",
        password_hash=hash_password("admin123"),
        display_name="Super Admin",
        email="super@example.com",
        role=UserRole.SUPER_ADMIN,
        status=UserStatus.ACTIVE,
        department_id=dept.id,
    )
    dept_admin = User(
        username="deptadmin",
        password_hash=hash_password("admin123"),
        display_name="Dept Admin",
        email="dept@example.com",
        role=UserRole.DEPT_ADMIN,
        status=UserStatus.ACTIVE,
        department_id=dept.id,
    )
    regular_user = User(
        username="regularuser",
        password_hash=hash_password("user123"),
        display_name="Regular User",
        email="user@example.com",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db_session.add_all([super_admin, dept_admin, regular_user])
    await db_session.flush()

    return {
        "super_admin": super_admin,
        "dept_admin": dept_admin,
        "regular_user": regular_user,
        "department": dept,
    }


def _make_auth_headers(user: User) -> dict:
    token = create_access_token(
        user.id,
        user.username,
        user.role.value,
        user.department_id,
        "default",
        TEST_JWT_CONFIG,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def auth_headers(seed_data):
    return {
        "super_admin": _make_auth_headers(seed_data["super_admin"]),
        "dept_admin": _make_auth_headers(seed_data["dept_admin"]),
        "regular_user": _make_auth_headers(seed_data["regular_user"]),
    }


def _make_valid_zip_bytes(name: str = "skill") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{name}/SKILL.md", "# Test Skill\n")
    return buf.getvalue()


def _make_mock_minio():
    m = MagicMock()
    m.bucket = "test-bucket"
    m.build_skill_key.return_value = "skills/test/skill/file.zip"
    m.upload.return_value = None
    m.get_presigned_url.return_value = "http://minio.local/test-bucket/skills/test/skill/file.zip"
    m.download.return_value = _make_valid_zip_bytes()
    m.delete.return_value = None
    return m


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, seed_data) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(admin_auth.router)
    app.include_router(admin_users.router)
    app.include_router(admin_depts.router)
    app.include_router(admin_skills.router)
    app.include_router(admin_audit_threads.router)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    mock_minio = _make_mock_minio()

    mock_config = MagicMock()
    mock_config.admin = TEST_ADMIN_CONFIG

    with (
        patch("app.admin.deps.get_app_config", return_value=mock_config),
        patch("app.admin.routers.auth.get_app_config", return_value=mock_config),
        patch("app.admin.routers.skills._get_minio_client", return_value=mock_minio),
        patch("app.admin.routers.skills._extract_zip_to_skills"),
        patch("app.admin.routers.skills._remove_skill_from_custom"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()
