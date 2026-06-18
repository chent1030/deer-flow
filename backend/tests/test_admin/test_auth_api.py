from unittest.mock import MagicMock, patch

import pytest

from app.admin.config import AdminConfig, JwtConfig

TEST_JWT_CONFIG = JwtConfig(
    secret_key="test-secret-key",
    access_token_expire_minutes=60,
    refresh_token_expire_days=7,
)

TEST_ADMIN_CONFIG = AdminConfig(
    database_url="sqlite+aiosqlite:///:memory:",
    jwt=TEST_JWT_CONFIG,
)


@pytest.mark.asyncio
async def test_login_success(client, seed_data):
    resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "superadmin",
            "password": "admin123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_success_with_dict_admin_config(client, seed_data):
    admin_config = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "jwt": {
            "secret_key": "test-secret-key",
            "access_token_expire_minutes": 60,
            "refresh_token_expire_days": 7,
        },
    }
    mock_config = MagicMock()
    mock_config.admin = admin_config

    with patch("app.admin.deps.get_app_config", return_value=mock_config):
        resp = await client.post(
            "/api/admin/auth/login",
            json={
                "username": "superadmin",
                "password": "admin123",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_admin_session_cookie_resolves_as_gateway_user(client, seed_data, db_session):
    from types import SimpleNamespace

    from app.gateway.deps import get_admin_session_user_from_request

    class _SessionContext:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "superadmin",
            "password": "admin123",
        },
    )
    access_token = resp.json()["access_token"]
    request = SimpleNamespace(
        cookies={"access_token": access_token},
        app=SimpleNamespace(state=SimpleNamespace(admin_session_factory=lambda: _SessionContext(db_session))),
    )

    user = await get_admin_session_user_from_request(request)

    assert str(user.id) == str(seed_data["super_admin"].id)
    assert user.email == "super@example.com"
    assert user.system_role == "admin"


@pytest.mark.asyncio
async def test_regular_admin_session_cookie_can_use_gateway_thread_search(seed_data, db_session):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from langgraph.store.memory import InMemoryStore

    from app.admin.auth.jwt import create_access_token
    from app.gateway.auth_middleware import AuthMiddleware
    from app.gateway.routers import auth as gateway_auth
    from app.gateway.routers import threads
    from deerflow.persistence.thread_meta.memory import MemoryThreadMetaStore

    seed_data["regular_user"].email = ""
    db_session.add(seed_data["regular_user"])
    await db_session.flush()

    class _SessionContext:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    token = create_access_token(
        seed_data["regular_user"].id,
        seed_data["regular_user"].username,
        seed_data["regular_user"].role.value,
        seed_data["regular_user"].department_id,
        "default",
        TEST_JWT_CONFIG,
    )

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.state.admin_session_factory = lambda: _SessionContext(db_session)
    app.state.thread_store = MemoryThreadMetaStore(InMemoryStore())
    app.include_router(gateway_auth.router)
    app.include_router(threads.router)

    mock_config = MagicMock()
    mock_config.admin = TEST_ADMIN_CONFIG

    with patch("app.admin.deps.get_app_config", return_value=mock_config):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            c.cookies.set("access_token", token)

            me = await c.get("/api/v1/auth/me")
            assert me.status_code == 200, me.text
            assert me.json()["system_role"] == "user"
            assert me.json()["email"].endswith("@users.deerflow.local.cn")

            search = await c.post("/api/threads/search", json={"limit": 10})
            assert search.status_code == 200, search.text


@pytest.mark.asyncio
async def test_login_wrong_password(client, seed_data):
    resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "superadmin",
            "password": "wrong",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client, seed_data):
    resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "nobody",
            "password": "pass",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_disabled_user(client, seed_data, db_session):
    from sqlalchemy import select

    from app.admin.models.user import User

    result = await db_session.execute(select(User).where(User.username == "regularuser"))
    user = result.scalar_one()
    user.status = "disabled"
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "regularuser",
            "password": "user123",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_refresh_token(client, seed_data):
    login_resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "superadmin",
            "password": "admin123",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/admin/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token(client, seed_data):
    resp = await client.post(
        "/api/admin/auth/refresh",
        json={
            "refresh_token": "invalid-token",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token(client, seed_data):
    login_resp = await client.post(
        "/api/admin/auth/login",
        json={
            "username": "superadmin",
            "password": "admin123",
        },
    )
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/admin/auth/refresh",
        json={
            "refresh_token": access_token,
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client, auth_headers):
    resp = await client.get("/api/admin/auth/me", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "superadmin"
    assert data["role"] == "super_admin"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client):
    resp = await client.get("/api/admin/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    resp = await client.get(
        "/api/admin/auth/me",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client, auth_headers, db_session):
    from sqlalchemy import select

    from app.admin.auth.password import verify_password
    from app.admin.models.user import User

    resp = await client.put(
        "/api/admin/auth/me/password",
        headers=auth_headers["regular_user"],
        json={
            "old_password": "user123",
            "new_password": "Newpass123!",
        },
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(User).where(User.username == "regularuser"))
    user = result.scalar_one()
    assert verify_password("Newpass123!", user.password_hash)


@pytest.mark.asyncio
async def test_change_password_rejects_weak_password(client, auth_headers):
    resp = await client.put(
        "/api/admin/auth/me/password",
        headers=auth_headers["regular_user"],
        json={
            "old_password": "user123",
            "new_password": "newpass123",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_wrong_old(client, auth_headers):
    resp = await client.put(
        "/api/admin/auth/me/password",
        headers=auth_headers["regular_user"],
        json={
            "old_password": "wrong",
            "new_password": "Newpass123!",
        },
    )
    assert resp.status_code == 400
