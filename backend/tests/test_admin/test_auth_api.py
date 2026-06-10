import pytest

from app.admin.config import JwtConfig

TEST_JWT_CONFIG = JwtConfig(
    secret_key="test-secret-key",
    access_token_expire_minutes=60,
    refresh_token_expire_days=7,
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
