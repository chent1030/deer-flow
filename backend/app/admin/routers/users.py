import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_db, require_role
from app.admin.models.user import User, UserRole
from app.admin.schemas.user import UserCreate, UserListResponse, UserPasswordReset, UserResponse, UserStatusUpdate, UserUpdate
from app.admin.services import department_service, user_service

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role.value,
        department_id=str(user.department_id) if user.department_id else None,
        status=user.status.value,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.DEPT_ADMIN and current_user.department_id:
        dept_ids = await department_service.get_subtree_department_ids(db, current_user.department_id)
        users, total = await user_service.list_users(db, page, page_size, search, dept_ids=dept_ids)
    elif current_user.role == UserRole.DEPT_ADMIN:
        users, total = await user_service.list_users(db, page, page_size, search)
    else:
        users, total = await user_service.list_users(db, page, page_size, search, department_id)
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserResponse)
async def create_user(
    req: UserCreate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    department_id = req.department_id
    role = req.role
    if current_user.role == UserRole.DEPT_ADMIN:
        department_id = current_user.department_id
        role = UserRole.USER
    user = await user_service.create_user(db, req.username, req.password, req.display_name, req.email, department_id, role)
    return _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if current_user.role == UserRole.DEPT_ADMIN and user.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access user in other department")
    return _user_to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    req: UserUpdate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if current_user.role == UserRole.DEPT_ADMIN and user.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update user in other department")
    department_id = req.department_id
    role = req.role
    if current_user.role == UserRole.DEPT_ADMIN:
        department_id = current_user.department_id
        role = None
    if req.clear_department and current_user.role == UserRole.SUPER_ADMIN:
        department_id = None
    updated = await user_service.update_user(db, user, req.display_name, req.email, department_id, role, req.clear_department and current_user.role == UserRole.SUPER_ADMIN)
    return _user_to_response(updated)


@router.put("/{user_id}/status", response_model=UserResponse)
async def toggle_user_status(
    user_id: uuid.UUID,
    req: UserStatusUpdate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    await user_service.toggle_user_status(db, user)
    return _user_to_response(user)


@router.put("/{user_id}/password")
async def reset_user_password(
    user_id: uuid.UUID,
    req: UserPasswordReset,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if current_user.role == UserRole.DEPT_ADMIN:
        is_self = user.id == current_user.id
        if not is_self and user.role != UserRole.USER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department admin can only reset regular user passwords")
        if not is_self and (not current_user.department_id or user.department_id != current_user.department_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot reset user password outside your department")
    await user_service.reset_user_password(db, user, req.new_password)
    return {"message": "Password reset successfully"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await user_service.delete_user(db, user_id)
    return {"message": "User deleted"}
