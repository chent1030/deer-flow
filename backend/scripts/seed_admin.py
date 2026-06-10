import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.admin.auth.password import hash_password
from app.admin.models.user import User, UserRole
from deerflow.config import get_app_config


async def seed():
    config = get_app_config().admin
    engine = create_async_engine(config.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == config.initial_super_admin.username))
        if result.scalar_one_or_none() is None:
            user = User(
                username=config.initial_super_admin.username,
                password_hash=hash_password(config.initial_super_admin.password),
                display_name="Super Admin",
                email=config.initial_super_admin.email,
                role=UserRole.SUPER_ADMIN,
            )
            db.add(user)
            await db.commit()
            print(f"Created super admin: {user.username}")
        else:
            print("Super admin already exists, skipping.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
