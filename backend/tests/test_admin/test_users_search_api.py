from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware

from app.admin.models import Base
from app.admin.models.user import User, UserRole, UserStatus
from app.gateway.routers import users as users_router


@dataclass
class StubUserMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, user_id: str) -> None:
        super().__init__(app)
        self.user_id = user_id

    async def dispatch(self, request: Request, call_next):
        request.state.user = SimpleNamespace(id=self.user_id)
        return await call_next(request)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _add_user(db: AsyncSession, username: str, *, status: UserStatus = UserStatus.ACTIVE) -> User:
    user = User(
        username=username,
        password_hash="hash",
        display_name=username.title(),
        email=f"{username}@example.test",
        role=UserRole.USER,
        status=status,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_search_share_users_excludes_current_user(db_session: AsyncSession):
    current = await _add_user(db_session, "current")
    alice = await _add_user(db_session, "alice")
    await _add_user(db_session, "disabled", status=UserStatus.DISABLED)
    await db_session.commit()

    app = FastAPI()
    app.add_middleware(StubUserMiddleware, user_id=str(current.id))
    app.include_router(users_router.router)
    app.state.admin_session_factory = async_sessionmaker(db_session.bind, expire_on_commit=False)

    with TestClient(app) as client:
        resp = client.get("/api/users/search", params={"search": "a"})

    assert resp.status_code == 200
    data = resp.json()
    assert all(item["username"] != current.username for item in data["users"])
    assert any(item["username"] == alice.username for item in data["users"])
    assert all(item["username"] != "disabled" for item in data["users"])
