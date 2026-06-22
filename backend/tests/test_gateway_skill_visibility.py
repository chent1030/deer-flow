from pathlib import Path
from types import SimpleNamespace

import pytest

from deerflow.skills.types import Skill, SkillCategory


def _skill(name: str, category: SkillCategory) -> Skill:
    skill_dir = Path("skills") / category / name
    return Skill(
        name=name,
        description=f"{name} description",
        license=None,
        skill_dir=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        relative_path=Path(name),
        category=category,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_list_skills_hides_custom_skills_when_visibility_context_is_unavailable(monkeypatch):
    from app.gateway.routers import skills as skills_router

    storage = SimpleNamespace(
        load_skills=lambda enabled_only=True: [
            _skill("public-skill", SkillCategory.PUBLIC),
            _skill("custom-skill", SkillCategory.CUSTOM),
        ]
    )
    monkeypatch.setattr(
        skills_router,
        "get_or_new_skill_storage",
        lambda app_config: storage,
    )

    request = SimpleNamespace(
        state=SimpleNamespace(auth=None),
        app=SimpleNamespace(state=SimpleNamespace(admin_session_factory=None)),
    )

    response = await skills_router.list_skills(request, config=SimpleNamespace())

    assert [skill.name for skill in response.skills] == ["public-skill"]


@pytest.mark.asyncio
async def test_runtime_skill_names_keep_public_skills_when_admin_visibility_lookup_fails(monkeypatch):
    from app.gateway import skill_visibility

    storage = SimpleNamespace(
        load_skills=lambda enabled_only=True: [
            _skill("public-skill", SkillCategory.PUBLIC),
            _skill("custom-skill", SkillCategory.CUSTOM),
        ]
    )
    monkeypatch.setattr(
        skill_visibility,
        "get_or_new_skill_storage",
        lambda app_config: storage,
    )

    async def fail_visibility_lookup(request):
        raise RuntimeError("admin db unavailable")

    monkeypatch.setattr(
        skill_visibility,
        "load_visible_custom_skill_names_for_request",
        fail_visibility_lookup,
    )

    request = SimpleNamespace()

    names = await skill_visibility.load_visible_runtime_skill_names_for_request(request, SimpleNamespace())

    assert names == ["public-skill"]
