from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from fastapi import Request

from app.admin.models.user import User
from app.admin.services import skill_service as admin_skill_service
from deerflow.config.app_config import AppConfig
from deerflow.skills.storage import get_or_new_skill_storage
from deerflow.skills.types import Skill, SkillCategory

logger = logging.getLogger(__name__)


def _request_user(request: Request):
    auth = getattr(request.state, "auth", None)
    user = getattr(auth, "user", None) if auth is not None else None
    return user or getattr(request.state, "user", None)


async def load_visible_custom_skill_names_for_request(request: Request) -> set[str]:
    """Return admin-approved custom skill names visible to the current user.

    Fail closed: when auth/admin visibility context is unavailable, custom skills
    are treated as not visible. Built-in public skills are handled separately.
    """

    user = _request_user(request)
    if user is None or user.id is None:
        return set()

    session_factory = getattr(getattr(request.app, "state", None), "admin_session_factory", None)
    if session_factory is None:
        logger.warning("Admin session factory unavailable while resolving skill visibility")
        return set()

    async with session_factory() as db:
        admin_user = await db.get(User, user.id)
        if admin_user is None:
            return set()
        visible_names = await admin_skill_service.list_visible_skills_for_user(
            db,
            admin_user.id,
            admin_user.role.value,
            admin_user.department_id,
        )
        return set(visible_names)


def filter_visible_skills(skills: Iterable[Skill], visible_custom_skill_names: set[str]) -> list[Skill]:
    return [skill for skill in skills if skill.category != SkillCategory.CUSTOM or skill.name in visible_custom_skill_names]


async def load_visible_runtime_skills_for_request(request: Request, app_config: AppConfig) -> list[Skill]:
    storage = get_or_new_skill_storage(app_config=app_config)
    skills = await asyncio.to_thread(storage.load_skills, enabled_only=True)
    try:
        visible_custom_names = await load_visible_custom_skill_names_for_request(request)
    except Exception:
        logger.exception("Failed to resolve custom skill visibility; hiding custom skills")
        visible_custom_names = set()
    return filter_visible_skills(skills, visible_custom_names)


async def load_visible_runtime_skill_names_for_request(request: Request, app_config: AppConfig) -> list[str]:
    skills = await load_visible_runtime_skills_for_request(request, app_config)
    return sorted({skill.name for skill in skills})
