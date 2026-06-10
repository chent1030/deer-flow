import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.admin.config import JwtConfig


def create_access_token(user_id: uuid.UUID, username: str, role: str, department_id: uuid.UUID | None, tenant_id: str, config: JwtConfig) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=config.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "department_id": str(department_id) if department_id else None,
        "tenant_id": tenant_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, config.secret_key, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID, config: JwtConfig) -> str:
    expire = datetime.now(UTC) + timedelta(days=config.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, config.secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict:
    return jwt.decode(token, secret_key, algorithms=["HS256"])
