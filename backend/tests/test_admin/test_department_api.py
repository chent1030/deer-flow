import uuid

import pytest


@pytest.mark.asyncio
async def test_list_departments(client, auth_headers):
    resp = await client.get("/api/admin/departments", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["departments"]) >= 1


@pytest.mark.asyncio
async def test_list_departments_dept_admin(client, auth_headers):
    resp = await client.get("/api/admin/departments", headers=auth_headers["dept_admin"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_departments_regular_user_forbidden(client, auth_headers):
    resp = await client.get("/api/admin/departments", headers=auth_headers["regular_user"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_department(client, auth_headers):
    resp = await client.post(
        "/api/admin/departments",
        headers=auth_headers["super_admin"],
        json={
            "name": "Marketing",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Marketing"
    assert data["parent_id"] is None


@pytest.mark.asyncio
async def test_create_department_with_parent(client, auth_headers, seed_data):
    parent_id = str(seed_data["department"].id)
    resp = await client.post(
        "/api/admin/departments",
        headers=auth_headers["super_admin"],
        json={
            "name": "Backend Team",
            "parent_id": parent_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_create_department_dept_admin_forbidden(client, auth_headers):
    resp = await client.post(
        "/api/admin/departments",
        headers=auth_headers["dept_admin"],
        json={
            "name": "Should Fail",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_department(client, auth_headers, seed_data):
    dept_id = str(seed_data["department"].id)
    resp = await client.get(f"/api/admin/departments/{dept_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 200
    assert resp.json()["name"] == "Engineering"


@pytest.mark.asyncio
async def test_get_department_dept_admin_own(client, auth_headers, seed_data):
    dept_id = str(seed_data["department"].id)
    resp = await client.get(f"/api/admin/departments/{dept_id}", headers=auth_headers["dept_admin"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_department_dept_admin_other_forbidden(client, auth_headers, db_session):
    from app.admin.models.department import Department

    other = Department(name="OtherDept")
    db_session.add(other)
    await db_session.flush()

    resp = await client.get(f"/api/admin/departments/{other.id}", headers=auth_headers["dept_admin"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_department_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/admin/departments/{fake_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_department(client, auth_headers, seed_data):
    dept_id = str(seed_data["department"].id)
    resp = await client.put(
        f"/api/admin/departments/{dept_id}",
        headers=auth_headers["super_admin"],
        json={
            "name": "Engineering Updated",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Engineering Updated"


@pytest.mark.asyncio
async def test_update_department_dept_admin_forbidden(client, auth_headers, seed_data):
    dept_id = str(seed_data["department"].id)
    resp = await client.put(
        f"/api/admin/departments/{dept_id}",
        headers=auth_headers["dept_admin"],
        json={
            "name": "Should Fail",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_department_with_users_forbidden(client, auth_headers, seed_data):
    dept_id = str(seed_data["department"].id)
    resp = await client.delete(f"/api/admin/departments/{dept_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_empty_department(client, auth_headers, db_session):
    from app.admin.models.department import Department

    empty = Department(name="Empty")
    db_session.add(empty)
    await db_session.flush()

    resp = await client.delete(f"/api/admin/departments/{empty.id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_department_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/admin/departments/{fake_id}", headers=auth_headers["super_admin"])
    assert resp.status_code == 404
