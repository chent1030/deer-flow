from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware

from app.admin.deps import get_db
from app.admin.models import Base
from app.admin.models.agent_share import AgentShareRecord
from app.admin.models.user import User, UserRole, UserStatus
from app.gateway.routers import agents
from deerflow.config.agents_api_config import AgentsApiConfig, get_agents_api_config, set_agents_api_config


@dataclass
class FakePaths:
    base_dir: Path

    def user_agent_dir(self, user_id: str, agent_name: str) -> Path:
        return self.base_dir / "users" / user_id / "agents" / agent_name

    def agent_dir(self, agent_name: str) -> Path:
        return self.base_dir / "agents" / agent_name


class StubUserMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, user_id: str) -> None:
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


async def _add_user(db: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        password_hash="hash",
        display_name=username.title(),
        email=f"{username}@example.test",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    return user


def _write_agent(paths: FakePaths, user: User, name: str) -> None:
    agent_dir = paths.user_agent_dir(str(user.id), name)
    agent_dir.mkdir(parents=True)
    (agent_dir / "config.yaml").write_text(
        yaml.safe_dump({"name": name, "description": "Source"}, allow_unicode=True),
        encoding="utf-8",
    )
    (agent_dir / "SOUL.md").write_text("source soul", encoding="utf-8")


@pytest.mark.asyncio
async def test_share_endpoint_copies_agent_and_returns_result(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _add_user(db_session, "owner")
    target = await _add_user(db_session, "target")
    await db_session.commit()
    paths = FakePaths(tmp_path)
    _write_agent(paths, owner, "sales-agent")

    async def override_get_db():
        yield db_session

    app = FastAPI()
    app.add_middleware(StubUserMiddleware, user_id=str(owner.id))
    app.include_router(agents.router)
    app.dependency_overrides[get_db] = override_get_db
    previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
    monkeypatch.setattr("app.admin.services.agent_share_service.get_paths", lambda: paths)
    monkeypatch.setattr(agents, "get_paths", lambda: paths)
    set_agents_api_config(AgentsApiConfig(enabled=True))
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/sales-agent/share",
                json={"user_ids": [str(target.id)]},
            )
    finally:
        set_agents_api_config(previous_config)

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["status"] == "created"
    assert data["results"][0]["target_agent_name"] == "sales-agent"
    assert paths.user_agent_dir(str(target.id), "sales-agent").exists()
    records = (await db_session.execute(select(AgentShareRecord))).scalars().all()
    assert len(records) == 1
