import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models.department import Department
from app.admin.models.user import User


async def create_department(db: AsyncSession, name: str, parent_id: uuid.UUID | None) -> Department:
    dept = Department(name=name, parent_id=parent_id)
    db.add(dept)
    await db.flush()
    return dept


async def get_all_departments(db: AsyncSession) -> list[Department]:
    result = await db.execute(select(Department).order_by(Department.name))
    return list(result.scalars().all())


async def get_subtree_department_ids(db: AsyncSession, dept_id: uuid.UUID) -> list[uuid.UUID]:
    all_depts = await get_all_departments(db)
    children_map: dict[uuid.UUID, list[uuid.UUID]] = {}
    for d in all_depts:
        if d.parent_id:
            children_map.setdefault(d.parent_id, []).append(d.id)
    result = [dept_id]
    queue = [dept_id]
    while queue:
        current = queue.pop(0)
        for child_id in children_map.get(current, []):
            result.append(child_id)
            queue.append(child_id)
    return result


async def get_member_counts(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(select(User.department_id, func.count(User.id)).group_by(User.department_id))
    return {str(row[0]): row[1] for row in result.all() if row[0] is not None}


def build_department_tree(departments: list[Department], member_counts: dict[str, int]) -> list[dict]:
    dept_map = {}
    for dept in departments:
        dept_map[str(dept.id)] = {
            "id": str(dept.id),
            "name": dept.name,
            "parent_id": str(dept.parent_id) if dept.parent_id else None,
            "created_at": dept.created_at.isoformat() if dept.created_at else None,
            "children": [],
            "member_count": member_counts.get(str(dept.id), 0),
        }
    tree = []
    for dept in departments:
        node = dept_map[str(dept.id)]
        if dept.parent_id and str(dept.parent_id) in dept_map:
            dept_map[str(dept.parent_id)]["children"].append(node)
        else:
            tree.append(node)
    return tree


async def get_department(db: AsyncSession, dept_id: uuid.UUID) -> Department:
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept


async def update_department(db: AsyncSession, dept: Department, name: str | None, parent_id: uuid.UUID | None) -> Department:
    if name is not None:
        dept.name = name
    if parent_id is not None:
        if parent_id == dept.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department cannot be its own parent")
        dept.parent_id = parent_id
    db.add(dept)
    await db.flush()
    return dept


async def delete_department(db: AsyncSession, dept_id: uuid.UUID) -> None:
    children_result = await db.execute(select(Department).where(Department.parent_id == dept_id))
    if children_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department has child departments")
    users_result = await db.execute(select(User).where(User.department_id == dept_id))
    if users_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department has users")
    dept = await get_department(db, dept_id)
    await db.delete(dept)
    await db.flush()
