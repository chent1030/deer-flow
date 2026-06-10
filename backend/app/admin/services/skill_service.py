import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.admin.models.base import now_utc8
from app.admin.models.skill import Skill, SkillStatus, SkillVisibility, SkillVisibleDepartment, SkillVisibleUser
from app.admin.models.user import UserRole


@dataclass(frozen=True)
class SkillUploadResult:
    skill: Skill
    replaced_existing: bool
    previous_minio_object_key: str | None = None
    was_approved: bool = False


def bump_patch_version(version: str | None) -> str:
    if not version:
        return "1.0.1"
    parts = version.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        major, minor, patch = parts
        return f"{int(major)}.{int(minor)}.{int(patch) + 1}"
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        major, minor = parts
        return f"{int(major)}.{int(minor)}.1"
    return "1.0.1"


async def upload_skill(
    db: AsyncSession,
    name: str,
    description: str,
    version: str,
    author_id: uuid.UUID,
    author_role: UserRole,
    department_id: uuid.UUID | None,
    minio_bucket: str,
    minio_object_key: str,
    file_size: int,
) -> SkillUploadResult:
    existing = await db.execute(select(Skill).where(Skill.name == name))
    existing_skill = existing.scalar_one_or_none()
    if existing_skill:
        if existing_skill.author_id != author_id and author_role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or super admin can upload a new version")
        previous_minio_object_key = existing_skill.minio_object_key
        was_approved = existing_skill.status == SkillStatus.APPROVED
        existing_skill.description = description
        existing_skill.version = bump_patch_version(existing_skill.version)
        existing_skill.department_id = department_id
        existing_skill.status = SkillStatus.PENDING_REVIEW
        existing_skill.reviewed_by = None
        existing_skill.reviewed_at = None
        existing_skill.review_comment = None
        existing_skill.minio_bucket = minio_bucket
        existing_skill.minio_object_key = minio_object_key
        existing_skill.file_size = file_size
        db.add(existing_skill)
        await db.flush()
        return SkillUploadResult(existing_skill, replaced_existing=True, previous_minio_object_key=previous_minio_object_key, was_approved=was_approved)

    skill = Skill(
        name=name,
        description=description,
        version=version,
        author_id=author_id,
        department_id=department_id,
        visibility=SkillVisibility.PRIVATE,
        status=SkillStatus.PENDING_REVIEW,
        minio_bucket=minio_bucket,
        minio_object_key=minio_object_key,
        file_size=file_size,
    )
    db.add(skill)
    await db.flush()
    return SkillUploadResult(skill, replaced_existing=False)


async def list_skills(
    db: AsyncSession,
    page: int,
    page_size: int,
    status_filter: SkillStatus | None = None,
    filter_department_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    user_department_ids: list[uuid.UUID] | None = None,
    role: UserRole = UserRole.USER,
) -> tuple[list[Skill], int]:
    query = select(Skill).options(selectinload(Skill.author))
    count_query = select(func.count()).select_from(Skill)

    if role == UserRole.SUPER_ADMIN:
        if filter_department_id:
            query = query.where(Skill.department_id == filter_department_id)
            count_query = count_query.where(Skill.department_id == filter_department_id)
    else:
        conditions = [Skill.author_id == user_id]
        conditions.append(Skill.visibility == SkillVisibility.COMPANY)
        if user_department_ids:
            dept_exists = exists(
                select(SkillVisibleDepartment).where(
                    SkillVisibleDepartment.skill_id == Skill.id,
                    SkillVisibleDepartment.department_id.in_(user_department_ids),
                )
            )
            conditions.append(and_(Skill.visibility == SkillVisibility.DEPARTMENT, dept_exists))
        user_exists = exists(
            select(SkillVisibleUser).where(
                SkillVisibleUser.skill_id == Skill.id,
                SkillVisibleUser.user_id == user_id,
            )
        )
        conditions.append(and_(Skill.visibility == SkillVisibility.SPECIFIC_USERS, user_exists))
        condition = or_(*conditions)
        query = query.where(condition)
        count_query = count_query.where(condition)

    if status_filter:
        query = query.where(Skill.status == status_filter)
        count_query = count_query.where(Skill.status == status_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(Skill.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    skills = list(result.scalars().all())
    return skills, total


async def get_skill(db: AsyncSession, skill_id: uuid.UUID) -> Skill:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


async def check_skill_visibility(
    db: AsyncSession,
    skill: Skill,
    user_id: uuid.UUID,
    role: UserRole,
    department_id: uuid.UUID | None,
) -> None:
    if role == UserRole.SUPER_ADMIN:
        return
    if skill.author_id == user_id:
        return
    if skill.visibility == SkillVisibility.COMPANY:
        return
    if skill.visibility == SkillVisibility.DEPARTMENT:
        visible_dept_ids = await get_visible_department_ids(db, skill.id)
        if department_id and str(department_id) in visible_dept_ids:
            return
    if skill.visibility == SkillVisibility.SPECIFIC_USERS:
        result = await db.execute(
            select(SkillVisibleUser).where(
                SkillVisibleUser.skill_id == skill.id,
                SkillVisibleUser.user_id == user_id,
            )
        )
        if result.scalar_one_or_none():
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this skill")


async def update_skill(
    db: AsyncSession,
    skill: Skill,
    name: str | None,
    description: str | None,
    version: str | None,
) -> Skill:
    changed = False
    if name is not None:
        changed = changed or skill.name != name
        skill.name = name
    if description is not None:
        changed = changed or skill.description != description
        skill.description = description
    if version is not None:
        changed = changed or skill.version != version
        skill.version = version
    if changed:
        skill.status = SkillStatus.PENDING_REVIEW
        skill.reviewed_by = None
        skill.reviewed_at = None
        skill.review_comment = None
    db.add(skill)
    await db.flush()
    return skill


async def set_visibility(
    db: AsyncSession,
    skill: Skill,
    visibility: SkillVisibility,
    visible_user_ids: list[uuid.UUID],
    visible_department_ids: list[uuid.UUID] | None = None,
) -> Skill:
    skill.visibility = visibility
    await db.execute(SkillVisibleUser.__table__.delete().where(SkillVisibleUser.skill_id == skill.id))
    await db.execute(SkillVisibleDepartment.__table__.delete().where(SkillVisibleDepartment.skill_id == skill.id))
    if visibility == SkillVisibility.SPECIFIC_USERS and visible_user_ids:
        for uid in visible_user_ids:
            db.add(SkillVisibleUser(skill_id=skill.id, user_id=uid))
    if visibility == SkillVisibility.DEPARTMENT and visible_department_ids:
        for did in visible_department_ids:
            db.add(SkillVisibleDepartment(skill_id=skill.id, department_id=did))
    db.add(skill)
    await db.flush()
    return skill


async def submit_for_review(db: AsyncSession, skill: Skill) -> Skill:
    if skill.status not in (SkillStatus.WITHDRAWN, SkillStatus.PENDING_REVIEW, SkillStatus.REJECTED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill must be withdrawn or rejected to resubmit")
    skill.status = SkillStatus.PENDING_REVIEW
    db.add(skill)
    await db.flush()
    return skill


async def withdraw_skill(db: AsyncSession, skill: Skill) -> Skill:
    if skill.status != SkillStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending review skills can be withdrawn")
    skill.status = SkillStatus.WITHDRAWN
    db.add(skill)
    await db.flush()
    return skill


async def review_skill(
    db: AsyncSession,
    skill: Skill,
    reviewer_id: uuid.UUID,
    action: str,
    comment: str,
) -> Skill:
    if skill.status != SkillStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill is not pending review")
    if action == "approve":
        skill.status = SkillStatus.APPROVED
    elif action == "reject":
        skill.status = SkillStatus.REJECTED
    skill.reviewed_by = reviewer_id
    skill.reviewed_at = now_utc8()
    skill.review_comment = comment
    db.add(skill)
    await db.flush()
    return skill


async def delete_skill(db: AsyncSession, skill_id: uuid.UUID) -> Skill:
    skill = await get_skill(db, skill_id)
    await db.execute(SkillVisibleUser.__table__.delete().where(SkillVisibleUser.skill_id == skill.id))
    await db.execute(SkillVisibleDepartment.__table__.delete().where(SkillVisibleDepartment.skill_id == skill.id))
    await db.delete(skill)
    await db.flush()
    return skill


async def get_visible_user_ids(db: AsyncSession, skill_id: uuid.UUID) -> list[str]:
    result = await db.execute(select(SkillVisibleUser.user_id).where(SkillVisibleUser.skill_id == skill_id))
    return [str(row[0]) for row in result.all()]


async def get_visible_department_ids(db: AsyncSession, skill_id: uuid.UUID) -> list[str]:
    result = await db.execute(select(SkillVisibleDepartment.department_id).where(SkillVisibleDepartment.skill_id == skill_id))
    return [str(row[0]) for row in result.all()]


async def list_visible_skills_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_role: str,
    department_id: uuid.UUID | None,
) -> list[str]:
    query = select(Skill).where(Skill.status == SkillStatus.APPROVED)
    skills_result = await db.execute(query)
    all_skills = list(skills_result.scalars().all())

    skill_dept_ids_map: dict[str, set[str]] = {}
    dept_visibility_skills = [s for s in all_skills if s.visibility == SkillVisibility.DEPARTMENT]
    if dept_visibility_skills:
        result = await db.execute(select(SkillVisibleDepartment).where(SkillVisibleDepartment.skill_id.in_([s.id for s in dept_visibility_skills])))
        for row in result.scalars().all():
            skill_dept_ids_map.setdefault(str(row.skill_id), set()).add(str(row.department_id))

    visible_names = []
    for skill in all_skills:
        if skill.visibility == SkillVisibility.COMPANY:
            visible_names.append(skill.name)
        elif skill.visibility == SkillVisibility.DEPARTMENT:
            if user_role in ("super_admin", "dept_admin"):
                visible_names.append(skill.name)
                continue
            visible_depts = skill_dept_ids_map.get(str(skill.id), set())
            if department_id and str(department_id) in visible_depts:
                visible_names.append(skill.name)
        elif skill.visibility == SkillVisibility.SPECIFIC_USERS:
            if user_role == "super_admin":
                visible_names.append(skill.name)
                continue
            result = await db.execute(
                select(SkillVisibleUser).where(
                    SkillVisibleUser.skill_id == skill.id,
                    SkillVisibleUser.user_id == user_id,
                )
            )
            if result.scalar_one_or_none():
                visible_names.append(skill.name)
        elif skill.visibility == SkillVisibility.PRIVATE:
            if skill.author_id == user_id or user_role == "super_admin":
                visible_names.append(skill.name)

    return visible_names
