import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_db, require_role
from app.admin.models.user import User, UserRole
from app.admin.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentTreeResponse,
    DepartmentUpdate,
)
from app.admin.schemas.user import UserListResponse
from app.admin.services import department_service, user_service

router = APIRouter(prefix="/api/admin/departments", tags=["admin-departments"])


@router.get("", response_model=DepartmentTreeResponse)
async def list_departments(
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    departments = await department_service.get_all_departments(db)
    member_counts = await department_service.get_member_counts(db)
    tree = department_service.build_department_tree(departments, member_counts)
    return DepartmentTreeResponse(departments=tree)


@router.post("", response_model=DepartmentResponse)
async def create_department(
    req: DepartmentCreate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    dept = await department_service.create_department(db, req.name, req.parent_id)
    return DepartmentResponse(
        id=str(dept.id),
        name=dept.name,
        parent_id=str(dept.parent_id) if dept.parent_id else None,
        created_at=dept.created_at.isoformat() if dept.created_at else None,
    )


@router.get("/{dept_id}", response_model=DepartmentResponse)
async def get_department(
    dept_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if user.role == UserRole.DEPT_ADMIN and user.department_id != dept_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access other department")
    dept = await department_service.get_department(db, dept_id)
    return DepartmentResponse(
        id=str(dept.id),
        name=dept.name,
        parent_id=str(dept.parent_id) if dept.parent_id else None,
        created_at=dept.created_at.isoformat() if dept.created_at else None,
    )


@router.get("/{dept_id}/users", response_model=UserListResponse)
async def list_department_users(
    dept_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.DEPT_ADMIN and current_user.department_id != dept_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access other department")
    users, total = await user_service.list_users(db, page, page_size, department_id=dept_id)
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


def _user_to_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role.value,
        "department_id": str(user.department_id) if user.department_id else None,
        "status": user.status.value,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(
    dept_id: uuid.UUID,
    req: DepartmentUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    dept = await department_service.get_department(db, dept_id)
    updated = await department_service.update_department(db, dept, req.name, req.parent_id)
    return DepartmentResponse(
        id=str(updated.id),
        name=updated.name,
        parent_id=str(updated.parent_id) if updated.parent_id else None,
        created_at=updated.created_at.isoformat() if updated.created_at else None,
    )


@router.delete("/{dept_id}")
async def delete_department(
    dept_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await department_service.delete_department(db, dept_id)
    return {"message": "Department deleted"}
