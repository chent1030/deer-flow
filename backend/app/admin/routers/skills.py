import io
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_current_user, get_db, require_role
from app.admin.minio import MinioClient
from app.admin.models.department import Department
from app.admin.models.skill import SkillStatus
from app.admin.models.user import User, UserRole
from app.admin.schemas.skill import SkillAutoReviewRequest, SkillListResponse, SkillResponse, SkillReviewRequest, SkillUpdate, SkillVisibilityUpdate, VisibleSkillsResponse
from app.admin.services import department_service, skill_service
from deerflow.client import DeerFlowClient

router = APIRouter(prefix="/api/admin/skills", tags=["admin-skills"])

SKILLS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "skills", "custom")


def _get_minio_client() -> MinioClient:
    from app.gateway.app import get_app

    app = get_app()
    return app.state.minio_client


def _extract_skill_to_custom(skill_name: str) -> None:
    skills_dir = os.path.join(os.path.dirname(SKILLS_ROOT), "custom")
    skill_path = os.path.join(skills_dir, skill_name)
    if os.path.exists(skill_path):
        shutil.rmtree(skill_path)


def _extract_zip_to_skills(zip_data: bytes, skill_name: str) -> None:
    skills_dir = SKILLS_ROOT
    skill_path = os.path.join(skills_dir, skill_name)
    if os.path.exists(skill_path):
        shutil.rmtree(skill_path)
    os.makedirs(skill_path, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        entries = zf.infolist()
        top_dirs = set()
        for e in entries:
            parts = e.filename.split("/")
            if len(parts) > 1:
                top_dirs.add(parts[0])
        if len(top_dirs) == 1 and list(top_dirs)[0].strip() == skill_name:
            for e in entries:
                if e.is_dir():
                    continue
                rel = e.filename
                parts = rel.split("/", 1)
                if len(parts) > 1:
                    target = os.path.join(skill_path, parts[1])
                else:
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(e) as src, open(target, "wb") as dst:
                    dst.write(src.read())
        else:
            zf.extractall(skill_path)


def _remove_skill_from_custom(skill_name: str) -> None:
    skill_path = os.path.join(SKILLS_ROOT, skill_name)
    if os.path.exists(skill_path):
        shutil.rmtree(skill_path)


def _build_skill_review_prompt(skill_name: str, zip_data: bytes) -> str:
    max_file_chars = 12000
    max_total_chars = 50000
    text_parts = [
        "请审核这个待提交的 DeerFlow skill 包。",
        "请重点检查：是否有 SKILL.md、是否遵循 skill 规范、脚本是否明显危险、路径是否异常、是否包含可执行工作流。",
        '请只返回 JSON：{"action":"approve|reject","comment":"审核意见"}。',
        f"Skill 名称：{skill_name}",
        "",
        "文件清单：",
    ]
    total_chars = sum(len(part) for part in text_parts)
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        entries = [entry for entry in zf.infolist() if not entry.is_dir()]
        for entry in entries[:200]:
            text_parts.append(f"- {entry.filename} ({entry.file_size} bytes)")
        text_parts.append("")
        text_parts.append("关键文本文件内容：")
        for entry in entries:
            suffix = Path(entry.filename).suffix.lower()
            name = Path(entry.filename).name.lower()
            if name != "skill.md" and suffix not in {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".sh"}:
                continue
            if entry.file_size > 256 * 1024:
                text_parts.append(f"\n--- {entry.filename} skipped: file too large ---")
                continue
            raw = zf.read(entry)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("utf-8", errors="replace")
            content = content[:max_file_chars]
            block = f"\n--- {entry.filename} ---\n{content}"
            if total_chars + len(block) > max_total_chars:
                text_parts.append("\n--- 其余文件因长度限制省略 ---")
                break
            text_parts.append(block)
            total_chars += len(block)
    return "\n".join(text_parts)


def _parse_auto_review_result(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auto review skill did not return valid JSON") from exc
    action = str(data.get("action", "")).strip().lower()
    comment = str(data.get("comment", "")).strip()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auto review result must contain action approve or reject")
    return action, comment[:1000]


async def _enrich_skills(db: AsyncSession, skills: list) -> dict:
    author_ids = {s.author_id for s in skills}
    dept_ids = {s.department_id for s in skills if s.department_id}
    user_map: dict = {}
    dept_map: dict = {}
    if author_ids:
        result = await db.execute(select(User).where(User.id.in_(author_ids)))
        for u in result.scalars().all():
            user_map[u.id] = u.display_name or u.username
    if dept_ids:
        result = await db.execute(select(Department).where(Department.id.in_(dept_ids)))
        for d in result.scalars().all():
            dept_map[d.id] = d.name
    return {"users": user_map, "depts": dept_map}


async def _enrich_one(db: AsyncSession, skill) -> dict:
    lookup = await _enrich_skills(db, [skill])
    return {
        "author_name": lookup["users"].get(skill.author_id),
        "department_name": lookup["depts"].get(skill.department_id) if skill.department_id else None,
    }


def _skill_to_response(skill, author_name=None, department_name=None, visible_user_ids=None, visible_department_ids=None) -> SkillResponse:
    return SkillResponse(
        id=str(skill.id),
        name=skill.name,
        description=skill.description,
        version=skill.version,
        author_id=str(skill.author_id),
        department_id=str(skill.department_id) if skill.department_id else None,
        visibility=skill.visibility.value,
        status=skill.status.value,
        file_size=skill.file_size,
        reviewed_by=str(skill.reviewed_by) if skill.reviewed_by else None,
        reviewed_at=skill.reviewed_at.isoformat() if skill.reviewed_at else None,
        review_comment=skill.review_comment,
        created_at=skill.created_at.isoformat() if skill.created_at else None,
        author_name=author_name,
        department_name=department_name,
        visible_user_ids=visible_user_ids or [],
        visible_department_ids=visible_department_ids or [],
    )


@router.get("", response_model=SkillListResponse)
async def list_skills(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: SkillStatus | None = Query(default=None, alias="status"),
    department_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == UserRole.SUPER_ADMIN:
        user_dept_ids = None
    elif user.department_id:
        user_dept_ids = await department_service.get_subtree_department_ids(db, user.department_id)
    else:
        user_dept_ids = []
    skills, total = await skill_service.list_skills(
        db,
        page,
        page_size,
        status_filter,
        department_id,
        user.id,
        user_dept_ids,
        user.role,
    )
    lookup = await _enrich_skills(db, skills)
    items = []
    for s in skills:
        visible_ids = await skill_service.get_visible_user_ids(db, s.id)
        visible_dept_ids = await skill_service.get_visible_department_ids(db, s.id)
        items.append(
            _skill_to_response(
                s,
                author_name=lookup["users"].get(s.author_id),
                department_name=lookup["depts"].get(s.department_id) if s.department_id else None,
                visible_user_ids=visible_ids,
                visible_department_ids=visible_dept_ids,
            )
        )
    return SkillListResponse(skills=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SkillResponse)
async def upload_skill(
    name: str = Form(...),
    version: str = Form(default="1.0.0"),
    description: str = Form(default=""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_data = await file.read()
    if not zipfile.is_zipfile(io.BytesIO(file_data)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a zip archive")
    minio_client = _get_minio_client()
    skill_id = uuid.uuid4()
    object_key = minio_client.build_skill_key(user.department_id, skill_id, f"{name}.zip")
    minio_client.upload(object_key, file_data)
    upload_result = await skill_service.upload_skill(
        db,
        name,
        description,
        version,
        user.id,
        user.role,
        user.department_id,
        minio_client.bucket,
        object_key,
        len(file_data),
    )
    skill = upload_result.skill
    if upload_result.replaced_existing:
        if upload_result.previous_minio_object_key and upload_result.previous_minio_object_key != object_key:
            try:
                minio_client.delete(upload_result.previous_minio_object_key)
            except Exception:
                pass
        if upload_result.was_approved:
            _remove_skill_from_custom(skill.name)
            try:
                from deerflow.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async

                await refresh_skills_system_prompt_cache_async()
            except Exception:
                pass
    enriched = await _enrich_one(db, skill)
    return _skill_to_response(skill, **enriched)


@router.get("/visible", response_model=VisibleSkillsResponse)
async def list_visible_skills(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    names = await skill_service.list_visible_skills_for_user(
        db,
        user.id,
        user.role.value,
        user.department_id,
    )
    return VisibleSkillsResponse(skill_names=names)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    await skill_service.check_skill_visibility(db, skill, user.id, user.role, user.department_id)
    visible_ids = await skill_service.get_visible_user_ids(db, skill.id)
    visible_dept_ids = await skill_service.get_visible_department_ids(db, skill.id)
    enriched = await _enrich_one(db, skill)
    return _skill_to_response(skill, visible_user_ids=visible_ids, visible_department_ids=visible_dept_ids, **enriched)


@router.get("/{skill_id}/download")
async def download_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if user.role != UserRole.SUPER_ADMIN and user.id != skill.author_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or super admin can download")
    minio_client = _get_minio_client()
    data = minio_client.download(skill.minio_object_key)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{skill.name}.zip"'},
    )


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: uuid.UUID,
    req: SkillUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.author_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or super admin can edit")
    was_approved = skill.status == SkillStatus.APPROVED
    old_name = skill.name
    changed = (
        (req.name is not None and req.name != skill.name)
        or (req.description is not None and req.description != skill.description)
        or (req.version is not None and req.version != skill.version)
    )
    updated = await skill_service.update_skill(db, skill, req.name, req.description, req.version)
    if was_approved and changed:
        _remove_skill_from_custom(old_name)
        try:
            from deerflow.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async

            await refresh_skills_system_prompt_cache_async()
        except Exception:
            pass
    enriched = await _enrich_one(db, updated)
    return _skill_to_response(updated, **enriched)


@router.put("/{skill_id}/visibility", response_model=SkillResponse)
async def set_visibility(
    skill_id: uuid.UUID,
    req: SkillVisibilityUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.author_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can set visibility")
    if skill.status != SkillStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visibility can only be set on approved skills")
    updated = await skill_service.set_visibility(db, skill, req.visibility, req.visible_user_ids, req.visible_department_ids)
    visible_ids = await skill_service.get_visible_user_ids(db, updated.id)
    visible_dept_ids = await skill_service.get_visible_department_ids(db, updated.id)
    enriched = await _enrich_one(db, updated)
    return _skill_to_response(updated, visible_user_ids=visible_ids, visible_department_ids=visible_dept_ids, **enriched)


@router.post("/{skill_id}/submit", response_model=SkillResponse)
async def submit_for_review(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.author_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can submit")
    updated = await skill_service.submit_for_review(db, skill)
    enriched = await _enrich_one(db, updated)
    return _skill_to_response(updated, **enriched)


@router.post("/{skill_id}/withdraw", response_model=SkillResponse)
async def withdraw_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.author_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can withdraw")
    updated = await skill_service.withdraw_skill(db, skill)
    enriched = await _enrich_one(db, updated)
    return _skill_to_response(updated, **enriched)


@router.post("/{skill_id}/review", response_model=SkillResponse)
async def review_skill(
    skill_id: uuid.UUID,
    req: SkillReviewRequest,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    updated = await skill_service.review_skill(db, skill, user.id, req.action, req.comment)
    if req.action == "approve":
        minio_client = _get_minio_client()
        zip_data = minio_client.download(updated.minio_object_key)
        _extract_zip_to_skills(zip_data, updated.name)
        try:
            from deerflow.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async

            await refresh_skills_system_prompt_cache_async()
        except Exception:
            pass
    return _skill_to_response(updated, **await _enrich_one(db, updated))


@router.post("/{skill_id}/auto-review", response_model=SkillResponse)
async def auto_review_skill(
    skill_id: uuid.UUID,
    req: SkillAutoReviewRequest,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.status != SkillStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill is not pending review")

    minio_client = _get_minio_client()
    zip_data = minio_client.download(skill.minio_object_key)
    prompt = _build_skill_review_prompt(skill.name, zip_data)
    try:
        raw_result = DeerFlowClient(
            available_skills={req.review_skill_name},
            username=user.username,
            plan_mode=False,
            thinking_enabled=True,
        ).chat(prompt, thread_id=f"skill-auto-review-{skill.id}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Auto review failed: {exc}") from exc

    action, comment = _parse_auto_review_result(raw_result)
    updated = await skill_service.review_skill(db, skill, user.id, action, comment)
    if action == "approve":
        _extract_zip_to_skills(zip_data, updated.name)
        try:
            from deerflow.agents.lead_agent.prompt import refresh_skills_system_prompt_cache_async

            await refresh_skills_system_prompt_cache_async()
        except Exception:
            pass
    return _skill_to_response(updated, **await _enrich_one(db, updated))


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = await skill_service.get_skill(db, skill_id)
    if skill.author_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or super admin can delete")
    deleted = await skill_service.delete_skill(db, skill_id)
    try:
        minio_client = _get_minio_client()
        minio_client.delete(deleted.minio_object_key)
    except Exception:
        pass
    if deleted.status.value == "approved":
        _remove_skill_from_custom(deleted.name)
    return {"message": "Skill deleted"}
