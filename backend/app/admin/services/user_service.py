import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.password import hash_password
from app.admin.models.user import User, UserRole, UserStatus


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: str,
    email: str,
    department_id: uuid.UUID | None,
    role: UserRole,
) -> User:
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        email=email,
        department_id=department_id,
        role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def list_users(
    db: AsyncSession,
    page: int,
    page_size: int,
    search: str | None = None,
    department_id: uuid.UUID | None = None,
    dept_ids: list[uuid.UUID] | None = None,
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)
    if search:
        condition = or_(User.username.ilike(f"%{search}%"), User.display_name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%"))
        query = query.where(condition)
        count_query = count_query.where(condition)
    if dept_ids:
        query = query.where(User.department_id.in_(dept_ids))
        count_query = count_query.where(User.department_id.in_(dept_ids))
    elif department_id:
        query = query.where(User.department_id == department_id)
        count_query = count_query.where(User.department_id == department_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())
    return users, total


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def update_user(
    db: AsyncSession,
    user: User,
    display_name: str | None,
    email: str | None,
    department_id: uuid.UUID | None,
    role: UserRole | None,
    clear_department: bool = False,
) -> User:
    if display_name is not None:
        user.display_name = display_name
    if email is not None:
        user.email = email
    if clear_department:
        user.department_id = None
    elif department_id is not None:
        user.department_id = department_id
    if role is not None:
        user.role = role
    db.add(user)
    await db.flush()
    return user


async def toggle_user_status(db: AsyncSession, user: User) -> User:
    if user.status == UserStatus.ACTIVE:
        user.status = UserStatus.DISABLED
    else:
        user.status = UserStatus.ACTIVE
    db.add(user)
    await db.flush()
    return user


async def reset_user_password(db: AsyncSession, user: User, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    db.add(user)
    await db.flush()
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await get_user(db, user_id)
    await db.delete(user)
    await db.flush()
