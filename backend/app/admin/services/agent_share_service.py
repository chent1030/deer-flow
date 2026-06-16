from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models.agent_share import AgentShareRecord, AgentShareStatus
from app.admin.models.user import User, UserStatus
from deerflow.config.paths import get_paths


@dataclass(frozen=True)
class AgentShareResult:
    target_user_id: str
    target_username: str | None
    target_agent_name: str | None
    status: str
    error_message: str | None = None


def _next_copy_name(base_name: str, target_root: Path) -> str:
    if not (target_root / base_name).exists():
        return base_name
    first_copy = f"{base_name}-copy"
    if not (target_root / first_copy).exists():
        return first_copy
    index = 2
    while (target_root / f"{base_name}-copy-{index}").exists():
        index += 1
    return f"{base_name}-copy-{index}"


def _rewrite_config_name(agent_dir: Path, target_name: str) -> None:
    config_path = agent_dir / "config.yaml"
    if not config_path.exists():
        return
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if isinstance(data, dict):
        data["name"] = target_name
        config_path.write_text(
            yaml.safe_dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )


async def _record_result(
    db: AsyncSession,
    *,
    source_owner_id: uuid.UUID,
    source_agent_name: str,
    target_user_id: uuid.UUID,
    target_agent_name: str | None,
    status: AgentShareStatus,
    error_message: str | None,
) -> None:
    db.add(
        AgentShareRecord(
            source_owner_id=source_owner_id,
            source_agent_name=source_agent_name,
            target_user_id=target_user_id,
            target_agent_name=target_agent_name,
            status=status,
            error_message=error_message,
        )
    )
    await db.flush()


async def share_agent_to_users(
    db: AsyncSession,
    *,
    source_owner_id: uuid.UUID,
    source_agent_name: str,
    target_user_ids: list[uuid.UUID],
) -> list[AgentShareResult]:
    paths = get_paths()
    source_dir = paths.user_agent_dir(str(source_owner_id), source_agent_name)
    if not source_dir.exists():
        raise FileNotFoundError(f"智能体“{source_agent_name}”不存在")

    results: list[AgentShareResult] = []
    for target_user_id in target_user_ids:
        target_user = await db.get(User, target_user_id)
        target_username = target_user.username if target_user else None
        target_agent_name: str | None = None
        error_message: str | None = None

        try:
            if target_user is None:
                raise ValueError("目标用户不存在")
            if target_user.id == source_owner_id:
                raise ValueError("不能将智能体分享给自己")
            if target_user.status != UserStatus.ACTIVE:
                raise ValueError("目标用户已被禁用")

            target_root = paths.user_agent_dir(str(target_user.id), "__placeholder__").parent
            target_root.mkdir(parents=True, exist_ok=True)
            target_agent_name = _next_copy_name(source_agent_name, target_root)
            target_dir = target_root / target_agent_name
            shutil.copytree(source_dir, target_dir)
            _rewrite_config_name(target_dir, target_agent_name)
            await _record_result(
                db,
                source_owner_id=source_owner_id,
                source_agent_name=source_agent_name,
                target_user_id=target_user_id,
                target_agent_name=target_agent_name,
                status=AgentShareStatus.CREATED,
                error_message=None,
            )
            results.append(
                AgentShareResult(
                    target_user_id=str(target_user_id),
                    target_username=target_username,
                    target_agent_name=target_agent_name,
                    status=AgentShareStatus.CREATED.value,
                    error_message=None,
                )
            )
        except Exception as exc:
            error_message = str(exc)
            await _record_result(
                db,
                source_owner_id=source_owner_id,
                source_agent_name=source_agent_name,
                target_user_id=target_user_id,
                target_agent_name=target_agent_name,
                status=AgentShareStatus.FAILED,
                error_message=error_message,
            )
            results.append(
                AgentShareResult(
                    target_user_id=str(target_user_id),
                    target_username=target_username,
                    target_agent_name=target_agent_name,
                    status=AgentShareStatus.FAILED.value,
                    error_message=error_message,
                )
            )

    await db.commit()
    return results
