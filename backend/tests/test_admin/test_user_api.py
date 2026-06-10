import uuid

import pytest


@pytest.mark.asyncio
async def test_list_users_as_super_admin(client, auth_headers, seed_data):
    resp = await client.get("/api/admin/users", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["users"]) == 3


@pytest.mark.asyncio
async def test_list_users_as_dept_admin(client, auth_headers):
    resp = await client.get("/api/admin/users", headers=auth_headers["dept_admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_users_as_regular_user(client, auth_headers):
    resp = await client.get("/api/admin/users", headers=auth_headers["regular_user"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_with_search(client, auth_headers):
    resp = await client.get("/api/admin/users", headers=auth_headers["super_admin"], params={"search": "super"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["users"][0]["username"] == "superadmin"


@pytest.mark.asyncio
async def test_create_user_as_super_admin(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/admin/users",
        headers=auth_headers["super_admin"],
        json={
            "username": "newuser",
            "password": "Newpass123!",
            "display_name": "New User",
            "email": "new@example.com",
            "department_id": str(seed_data["department"].id),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_create_user_with_role(client, auth_headers, seed_data):
    resp = await client.post(
        "/api/admin/users",
        headers=auth_headers["super_admin"],
        json={
            "username": "newdeptadmin",
            "password": "Newpass123!",
            "display_name": "New Dept Admin",
            "email": "newdept@example.com",
            "department_id": str(seed_data["department"].id),
            "role": "dept_admin",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "dept_admin"


@pytest.mark.asyncio
async def test_create_user_as_dept_admin_forced_role(client, auth_headers):
    resp = await client.post(
        "/api/admin/users",
        headers=auth_headers["dept_admin"],
        json={
            "username": "deptuser",
            "password": "Newpass123!",
            "display_name": "Dept User",
            "email": "deptuser@example.com",
            "role": "super_admin",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


@pytest.mark.asyncio
async def test_create_duplicate_user(client, auth_headers):
    resp = await client.post(
        "/api/admin/users",
        headers=auth_headers["super_admin"],
        json={
            "username": "superadmin",
            "password": "Newpass123!",
            "display_name": "Duplicate",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_rejects_weak_password(client, auth_headers):
    resp = await client.post(
        "/api/admin/users",
        headers=auth_headers["super_admin"],
        json={
            "username": "weakpassuser",
            "password": "newpass123",
            "display_name": "Weak Password",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_user(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.get(f"/api/admin/users/{uid}", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    assert resp.json()["username"] == "regularuser"


@pytest.mark.asyncio
async def test_get_user_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/admin/users/{fake_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_dept_admin_other_department(client, auth_headers, seed_data, db_session):
    from app.admin.models.department import Department

    other_dept = Department(name="Other")
    db_session.add(other_dept)
    await db_session.flush()

    uid = seed_data["regular_user"].id
    resp = await client.get(f"/api/admin/users/{uid}", headers=auth_headers["dept_admin"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.put(
        f"/api/admin/users/{uid}",
        headers=auth_headers["super_admin"],
        json={
            "display_name": "Updated Name",
            "email": "updated@example.com",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Updated Name"
    assert data["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_update_user_role(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.put(
        f"/api/admin/users/{uid}",
        headers=auth_headers["super_admin"],
        json={
            "role": "dept_admin",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "dept_admin"


@pytest.mark.asyncio
async def test_super_admin_can_reset_any_user_password(client, auth_headers, seed_data, db_session):
    from sqlalchemy import select

    from app.admin.auth.password import verify_password
    from app.admin.models.user import User

    uid = seed_data["dept_admin"].id
    resp = await client.put(
        f"/api/admin/users/{uid}/password",
        headers=auth_headers["super_admin"],
        json={"new_password": "Resetpass123!"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(User).where(User.id == uid))
    user = result.scalar_one()
    assert verify_password("Resetpass123!", user.password_hash)


@pytest.mark.asyncio
async def test_dept_admin_can_reset_department_regular_user_password(client, auth_headers, seed_data, db_session):
    from sqlalchemy import select

    from app.admin.auth.password import hash_password, verify_password
    from app.admin.models.user import User, UserRole

    target = User(
        username="deptregular",
        password_hash=hash_password("Oldpass123!"),
        display_name="Dept Regular",
        email="deptregular@example.com",
        role=UserRole.USER,
        department_id=seed_data["department"].id,
    )
    db_session.add(target)
    await db_session.flush()

    resp = await client.put(
        f"/api/admin/users/{target.id}/password",
        headers=auth_headers["dept_admin"],
        json={"new_password": "Deptreset123!"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(User).where(User.id == target.id))
    user = result.scalar_one()
    assert verify_password("Deptreset123!", user.password_hash)


@pytest.mark.asyncio
async def test_dept_admin_can_reset_own_password_from_user_management(client, auth_headers, seed_data, db_session):
    from sqlalchemy import select

    from app.admin.auth.password import verify_password
    from app.admin.models.user import User

    resp = await client.put(
        f"/api/admin/users/{seed_data['dept_admin'].id}/password",
        headers=auth_headers["dept_admin"],
        json={"new_password": "Ownreset123!"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(User).where(User.id == seed_data["dept_admin"].id))
    user = result.scalar_one()
    assert verify_password("Ownreset123!", user.password_hash)


@pytest.mark.asyncio
async def test_dept_admin_cannot_reset_other_department_admin_password(client, auth_headers, seed_data, db_session):
    from app.admin.auth.password import hash_password
    from app.admin.models.user import User, UserRole

    other_admin = User(
        username="otherdeptadmin",
        password_hash=hash_password("Oldpass123!"),
        display_name="Other Dept Admin",
        email="otherdeptadmin@example.com",
        role=UserRole.DEPT_ADMIN,
        department_id=seed_data["department"].id,
    )
    db_session.add(other_admin)
    await db_session.flush()

    resp = await client.put(
        f"/api/admin/users/{other_admin.id}/password",
        headers=auth_headers["dept_admin"],
        json={"new_password": "Blocked123!"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dept_admin_cannot_reset_user_outside_department(client, auth_headers, seed_data):
    resp = await client.put(
        f"/api/admin/users/{seed_data['regular_user'].id}/password",
        headers=auth_headers["dept_admin"],
        json={"new_password": "Blocked123!"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_reset_user_password(client, auth_headers, seed_data):
    resp = await client.put(
        f"/api/admin/users/{seed_data['regular_user'].id}/password",
        headers=auth_headers["regular_user"],
        json={"new_password": "Blocked123!"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_toggle_user_status(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.put(
        f"/api/admin/users/{uid}/status",
        headers=auth_headers["super_admin"],
        json={
            "status": "disabled",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_toggle_user_status_dept_admin_forbidden(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.put(
        f"/api/admin/users/{uid}/status",
        headers=auth_headers["dept_admin"],
        json={
            "status": "disabled",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_user(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.delete(f"/api/admin/users/{uid}", headers=auth_headers["super_admin"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_user_dept_admin_forbidden(client, auth_headers, seed_data):
    uid = seed_data["regular_user"].id
    resp = await client.delete(f"/api/admin/users/{uid}", headers=auth_headers["dept_admin"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_regular_forbidden(client, auth_headers, seed_data):
    uid = seed_data["super_admin"].id
    resp = await client.delete(f"/api/admin/users/{uid}", headers=auth_headers["regular_user"])
    assert resp.status_code == 403
