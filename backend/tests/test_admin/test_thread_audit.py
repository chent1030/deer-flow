from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_list_audit_threads_empty(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_audit_threads_forbidden_for_dept_admin(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["dept_admin"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_threads_forbidden_for_regular_user(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["regular_user"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_thread_stats(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads/stats",
        headers=auth_headers["super_admin"],
        params={"quick": "7d"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_threads" in data
    assert "total_messages" in data
    assert "active_users" in data


@pytest.mark.asyncio
async def test_get_thread_stats_chart(client, auth_headers, seed_data):
    with (
        patch(
            "app.admin.services.thread_service.get_daily_thread_stats",
            return_value=[],
        ),
        patch(
            "app.admin.services.thread_service.get_daily_message_stats",
            return_value=[],
        ),
    ):
        resp = await client.get(
            "/api/admin/audit/threads/stats/chart",
            headers=auth_headers["super_admin"],
            params={"quick": "7d"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "thread_stats" in data
    assert "message_stats" in data


@pytest.mark.asyncio
async def test_get_thread_messages_not_found(client, auth_headers, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads/nonexistent-thread-id/messages",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 50},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_thread_stats_unauthorized(client, seed_data):
    resp = await client.get(
        "/api/admin/audit/threads/stats",
        params={"quick": "7d"},
    )
    assert resp.status_code == 401
