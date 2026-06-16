from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.admin.models import Base
from app.admin.models.agent_share import AgentShareRecord
from app.admin.models.user import User, UserRole, UserStatus
from app.admin.services.agent_share_service import share_agent_to_users


@dataclass
class FakePaths:
    base_dir: Path

    def user_agent_dir(self, user_id: str, agent_name: str) -> Path:
        return self.base_dir / "users" / user_id / "agents" / agent_name

    def agent_dir(self, agent_name: str) -> Path:
        return self.base_dir / "agents" / agent_name


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


async def _add_user(
    db: AsyncSession,
    username: str,
    *,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
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


def _write_agent(paths: FakePaths, user: User, name: str, *, description: str = "Source") -> None:
    agent_dir = paths.user_agent_dir(str(user.id), name)
    agent_dir.mkdir(parents=True)
    (agent_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "name": name,
                "description": description,
                "model": "test-model",
                "tool_groups": ["search"],
                "skills": ["research"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (agent_dir / "SOUL.md").write_text("source soul", encoding="utf-8")


@pytest.mark.asyncio
async def test_share_agent_copies_source_to_target_user(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = FakePaths(tmp_path)
    monkeypatch.setattr("app.admin.services.agent_share_service.get_paths", lambda: paths)
    owner = await _add_user(db_session, "owner")
    target = await _add_user(db_session, "target")
    _write_agent(paths, owner, "sales-agent")

    results = await share_agent_to_users(
        db_session,
        source_owner_id=owner.id,
        source_agent_name="sales-agent",
        target_user_ids=[target.id],
    )

    assert len(results) == 1
    assert results[0].status == "created"
    assert results[0].target_agent_name == "sales-agent"
    target_dir = paths.user_agent_dir(str(target.id), "sales-agent")
    assert (target_dir / "SOUL.md").read_text(encoding="utf-8") == "source soul"
    copied_config = yaml.safe_load((target_dir / "config.yaml").read_text(encoding="utf-8"))
    assert copied_config["name"] == "sales-agent"
    assert copied_config["model"] == "test-model"

    records = (await db_session.execute(select(AgentShareRecord))).scalars().all()
    assert len(records) == 1
    assert records[0].source_owner_id == owner.id
    assert records[0].target_user_id == target.id
    assert records[0].status == "created"


@pytest.mark.asyncio
async def test_share_agent_generates_copy_name_when_target_has_same_name(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = FakePaths(tmp_path)
    monkeypatch.setattr("app.admin.services.agent_share_service.get_paths", lambda: paths)
    owner = await _add_user(db_session, "owner")
    target = await _add_user(db_session, "target")
    _write_agent(paths, owner, "sales-agent")
    _write_agent(paths, target, "sales-agent", description="Existing")
    _write_agent(paths, target, "sales-agent-copy", description="Existing Copy")

    results = await share_agent_to_users(
        db_session,
        source_owner_id=owner.id,
        source_agent_name="sales-agent",
        target_user_ids=[target.id],
    )

    assert results[0].status == "created"
    assert results[0].target_agent_name == "sales-agent-copy-2"
    assert paths.user_agent_dir(str(target.id), "sales-agent-copy-2").exists()
    copied_config = yaml.safe_load(
        (paths.user_agent_dir(str(target.id), "sales-agent-copy-2") / "config.yaml").read_text(
            encoding="utf-8",
        )
    )
    assert copied_config["name"] == "sales-agent-copy-2"


@pytest.mark.asyncio
async def test_share_agent_records_self_share_as_failed(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = FakePaths(tmp_path)
    monkeypatch.setattr("app.admin.services.agent_share_service.get_paths", lambda: paths)
    owner = await _add_user(db_session, "owner")
    _write_agent(paths, owner, "sales-agent")

    results = await share_agent_to_users(
        db_session,
        source_owner_id=owner.id,
        source_agent_name="sales-agent",
        target_user_ids=[owner.id],
    )

    assert results[0].status == "failed"
    assert results[0].target_agent_name is None
    assert results[0].error_message == "不能将智能体分享给自己"
    records = (await db_session.execute(select(AgentShareRecord))).scalars().all()
    assert records[0].status == "failed"


@pytest.mark.asyncio
async def test_share_agent_continues_when_one_target_fails(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = FakePaths(tmp_path)
    monkeypatch.setattr("app.admin.services.agent_share_service.get_paths", lambda: paths)
    owner = await _add_user(db_session, "owner")
    active_target = await _add_user(db_session, "active")
    disabled_target = await _add_user(db_session, "disabled", status=UserStatus.DISABLED)
    _write_agent(paths, owner, "sales-agent")

    results = await share_agent_to_users(
        db_session,
        source_owner_id=owner.id,
        source_agent_name="sales-agent",
        target_user_ids=[disabled_target.id, active_target.id],
    )

    assert [r.status for r in results] == ["failed", "created"]
    assert paths.user_agent_dir(str(active_target.id), "sales-agent").exists()
    records = (await db_session.execute(select(AgentShareRecord))).scalars().all()
    assert len(records) == 2
