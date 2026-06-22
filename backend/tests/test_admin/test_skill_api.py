import io
import uuid
import zipfile

import pytest

from app.admin.models.skill import Skill, SkillStatus, SkillVisibility, SkillVisibleUser
from app.admin.services.skill_service import list_visible_skills_for_user


def _make_zip_bytes(name: str = "skill") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{name}/SKILL.md", "# Test Skill\n")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_usage_visibility_does_not_expand_for_admin_roles(db_session, seed_data):
    regular_user = seed_data["regular_user"]
    super_admin = seed_data["super_admin"]
    dept_admin = seed_data["dept_admin"]

    company_skill = Skill(
        name="usage-company-skill",
        description="visible to everyone",
        version="1.0.0",
        author_id=regular_user.id,
        department_id=None,
        visibility=SkillVisibility.COMPANY,
        status=SkillStatus.APPROVED,
        minio_bucket="test",
        minio_object_key="skills/company.zip",
        file_size=1,
    )
    private_skill = Skill(
        name="usage-private-skill",
        description="author only",
        version="1.0.0",
        author_id=regular_user.id,
        department_id=None,
        visibility=SkillVisibility.PRIVATE,
        status=SkillStatus.APPROVED,
        minio_bucket="test",
        minio_object_key="skills/private.zip",
        file_size=1,
    )
    specific_skill = Skill(
        name="usage-specific-skill",
        description="specific user only",
        version="1.0.0",
        author_id=regular_user.id,
        department_id=None,
        visibility=SkillVisibility.SPECIFIC_USERS,
        status=SkillStatus.APPROVED,
        minio_bucket="test",
        minio_object_key="skills/specific.zip",
        file_size=1,
    )
    db_session.add_all([company_skill, private_skill, specific_skill])
    await db_session.flush()
    db_session.add(SkillVisibleUser(skill_id=specific_skill.id, user_id=regular_user.id))
    await db_session.flush()

    super_admin_visible = await list_visible_skills_for_user(
        db_session,
        super_admin.id,
        super_admin.role.value,
        super_admin.department_id,
    )
    dept_admin_visible = await list_visible_skills_for_user(
        db_session,
        dept_admin.id,
        dept_admin.role.value,
        dept_admin.department_id,
    )

    assert "usage-company-skill" in super_admin_visible
    assert "usage-company-skill" in dept_admin_visible
    assert "usage-private-skill" not in super_admin_visible
    assert "usage-private-skill" not in dept_admin_visible
    assert "usage-specific-skill" not in super_admin_visible
    assert "usage-specific-skill" not in dept_admin_visible


@pytest.mark.asyncio
async def test_upload_skill(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "my-skill", "version": "1.0.0", "description": "A test skill"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "my-skill"
    assert data["status"] == "pending_review"
    assert data["visibility"] == "private"


@pytest.mark.asyncio
async def test_upload_duplicate_skill_creates_new_version(client, auth_headers, seed_data):
    first = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "dup-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    assert first.status_code == 200

    resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "dup-skill", "version": "9.9.9"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == first.json()["id"]
    assert data["version"] == "1.0.1"
    assert data["status"] == "pending_review"


@pytest.mark.asyncio
async def test_upload_duplicate_skill_by_non_author_forbidden(client, auth_headers, seed_data):
    await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "owned-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["dept_admin"],
        data={"name": "owned-skill", "version": "2.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_skills_as_super_admin(client, auth_headers, seed_data):
    await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "list-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )

    resp = await client.get("/api/admin/skills", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_skills_as_regular_user(client, auth_headers, seed_data):
    await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "own-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )

    resp = await client.get("/api/admin/skills", headers=auth_headers["regular_user"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for s in data["skills"]:
        assert s["author_id"] == str(seed_data["regular_user"].id)


@pytest.mark.asyncio
async def test_get_skill_by_author(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "get-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.get(f"/api/admin/skills/{skill_id}", headers=auth_headers["regular_user"])
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-skill"


@pytest.mark.asyncio
async def test_get_skill_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/admin/skills/{fake_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_skill_by_author(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "update-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.put(
        f"/api/admin/skills/{skill_id}",
        headers=auth_headers["regular_user"],
        json={"name": "updated-skill", "description": "updated desc"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-skill"
    assert resp.json()["description"] == "updated desc"


@pytest.mark.asyncio
async def test_update_approved_skill_returns_to_pending_review(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "review-again-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]
    await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "approve", "comment": "approved"},
    )

    resp = await client.put(
        f"/api/admin/skills/{skill_id}",
        headers=auth_headers["regular_user"],
        json={"description": "changed after approval"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_review"
    assert data["review_comment"] is None
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None


@pytest.mark.asyncio
async def test_update_skill_by_non_author_forbidden(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "other-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.put(
        f"/api/admin/skills/{skill_id}",
        headers=auth_headers["dept_admin"],
        json={"name": "hacked"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_skill_by_super_admin(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "admin-update-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.put(
        f"/api/admin/skills/{skill_id}",
        headers=auth_headers["super_admin"],
        json={"name": "admin-updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "admin-updated"


@pytest.mark.asyncio
async def test_submit_for_review(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "submit-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.post(f"/api/admin/skills/{skill_id}/submit", headers=auth_headers["regular_user"])
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_withdraw_skill(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "withdraw-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.post(f"/api/admin/skills/{skill_id}/withdraw", headers=auth_headers["regular_user"])
    assert resp.status_code == 200
    assert resp.json()["status"] == "withdrawn"


@pytest.mark.asyncio
async def test_review_approve_skill(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "approve-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "approve", "comment": "Looks good"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["review_comment"] == "Looks good"


@pytest.mark.asyncio
async def test_review_reject_skill(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "reject-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "reject", "comment": "Not good enough"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["review_comment"] == "Not good enough"


@pytest.mark.asyncio
async def test_auto_review_skill(client, auth_headers, seed_data, monkeypatch):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "auto-review-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    class FakeClient:
        def __init__(
            self,
            *,
            available_skills=None,
            plan_mode=False,
            thinking_enabled=True,
        ):
            self.available_skills = available_skills
            self.plan_mode = plan_mode
            self.thinking_enabled = thinking_enabled

        def chat(self, message, thread_id=None):
            assert self.available_skills == {"skill-reviewer"}
            assert self.plan_mode is False
            assert self.thinking_enabled is True
            assert "auto-review-skill" in message
            return '{"action":"approve","comment":"自动审核通过"}'

    monkeypatch.setattr("app.admin.routers.skills.DeerFlowClient", FakeClient)

    resp = await client.post(
        f"/api/admin/skills/{skill_id}/auto-review",
        headers=auth_headers["super_admin"],
        json={"review_skill_name": "skill-reviewer"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["review_comment"] == "自动审核通过"


@pytest.mark.asyncio
async def test_review_by_non_admin_forbidden(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "review-forbid-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["regular_user"],
        json={"action": "approve"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_visibility_on_approved_skill(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "vis-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "approve"},
    )

    resp = await client.put(
        f"/api/admin/skills/{skill_id}/visibility",
        headers=auth_headers["regular_user"],
        json={"visibility": "company"},
    )
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "company"


@pytest.mark.asyncio
async def test_set_visibility_on_non_approved_forbidden(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "vis-nonapproved-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.put(
        f"/api/admin/skills/{skill_id}/visibility",
        headers=auth_headers["regular_user"],
        json={"visibility": "company"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_set_specific_users_visibility(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "specific-vis-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "approve"},
    )

    target_user_id = str(seed_data["dept_admin"].id)
    resp = await client.put(
        f"/api/admin/skills/{skill_id}/visibility",
        headers=auth_headers["regular_user"],
        json={"visibility": "specific_users", "visible_user_ids": [target_user_id]},
    )
    assert resp.status_code == 200
    assert target_user_id in resp.json()["visible_user_ids"]


@pytest.mark.asyncio
async def test_delete_skill_by_author(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "delete-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.delete(f"/api/admin/skills/{skill_id}", headers=auth_headers["regular_user"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_skill_by_super_admin(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "admin-delete-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.delete(f"/api/admin/skills/{skill_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_skill_by_non_author_forbidden(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "forbid-delete-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.delete(f"/api/admin/skills/{skill_id}", headers=auth_headers["dept_admin"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_skill(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "download-skill", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    resp = await client.get(f"/api/admin/skills/{skill_id}/download", headers=auth_headers["regular_user"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_download_approved_skill_with_non_ascii_name(client, auth_headers, seed_data):
    upload_resp = await client.post(
        "/api/admin/skills",
        headers=auth_headers["regular_user"],
        data={"name": "中文技能", "version": "1.0.0"},
        files={"file": ("skill.zip", _make_zip_bytes(), "application/zip")},
    )
    skill_id = upload_resp.json()["id"]

    review_resp = await client.post(
        f"/api/admin/skills/{skill_id}/review",
        headers=auth_headers["super_admin"],
        json={"action": "approve"},
    )
    assert review_resp.status_code == 200

    resp = await client.get(f"/api/admin/skills/{skill_id}/download", headers=auth_headers["super_admin"])

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "filename*=UTF-8" in resp.headers.get("content-disposition", "")
