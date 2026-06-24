from unittest.mock import patch

import pytest

from deerflow.persistence.models.run_event import RunEventRow
from deerflow.persistence.run.model import RunRow
from deerflow.persistence.thread_meta.model import ThreadMetaRow


@pytest.mark.asyncio
async def test_list_audit_threads_reads_runtime_thread_metadata(client, auth_headers, seed_data, db_session):
    user = seed_data["regular_user"]
    db_session.add(
        ThreadMetaRow(
            thread_id="runtime-thread-1",
            assistant_id="agent",
            user_id=str(user.id),
            display_name="Excel 分析",
            status="idle",
        )
    )
    db_session.add(
        RunRow(
            run_id="run-1",
            thread_id="runtime-thread-1",
            assistant_id="agent",
            user_id=str(user.id),
            status="success",
            message_count=4,
            first_human_message="分析这个 Excel",
            last_ai_message="分析完成",
        )
    )
    await db_session.flush()

    resp = await client.get(
        "/api/admin/audit/threads",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 20},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "runtime-thread-1"
    assert data["items"][0]["title"] == "Excel 分析"
    assert data["items"][0]["message_count"] == 4
    assert data["items"][0]["username"] == user.username


@pytest.mark.asyncio
async def test_get_thread_stats_reads_runtime_runs(client, auth_headers, seed_data, db_session):
    user = seed_data["regular_user"]
    db_session.add_all(
        [
            ThreadMetaRow(thread_id="runtime-thread-1", user_id=str(user.id), display_name="A", status="idle"),
            ThreadMetaRow(thread_id="runtime-thread-2", user_id=str(user.id), display_name="B", status="busy"),
            RunRow(run_id="run-1", thread_id="runtime-thread-1", user_id=str(user.id), status="success", message_count=3),
            RunRow(run_id="run-2", thread_id="runtime-thread-1", user_id=str(user.id), status="success", message_count=2),
            RunRow(run_id="run-3", thread_id="runtime-thread-2", user_id=str(user.id), status="error", message_count=1),
        ]
    )
    await db_session.flush()

    resp = await client.get(
        "/api/admin/audit/threads/stats",
        headers=auth_headers["super_admin"],
        params={"quick": "7d"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_threads"] == 2
    assert data["total_messages"] == 6
    assert data["active_users"] == 1


@pytest.mark.asyncio
async def test_get_thread_messages_builds_audit_messages_from_runtime_runs(client, auth_headers, seed_data, db_session):
    user = seed_data["regular_user"]
    db_session.add(ThreadMetaRow(thread_id="runtime-thread-1", user_id=str(user.id), display_name="A", status="idle"))
    db_session.add(
        RunRow(
            run_id="run-1",
            thread_id="runtime-thread-1",
            user_id=str(user.id),
            status="success",
            message_count=2,
            first_human_message="你好",
            last_ai_message="你好，有什么可以帮你？",
            total_tokens=12,
        )
    )
    await db_session.flush()

    resp = await client.get(
        "/api/admin/audit/threads/runtime-thread-1/messages",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 50},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert [item["role"] for item in data["items"]] == ["user", "assistant"]
    assert data["items"][0]["content"] == "你好"
    assert data["items"][1]["content"] == "你好，有什么可以帮你？"


@pytest.mark.asyncio
async def test_get_thread_messages_prefers_full_runtime_events(client, auth_headers, seed_data, db_session):
    user = seed_data["regular_user"]
    db_session.add(ThreadMetaRow(thread_id="runtime-thread-1", user_id=str(user.id), display_name="A", status="idle"))
    db_session.add(RunRow(run_id="run-1", thread_id="runtime-thread-1", user_id=str(user.id), status="success", message_count=4))
    db_session.add_all(
        [
            RunEventRow(
                thread_id="runtime-thread-1",
                run_id="run-1",
                user_id=str(user.id),
                event_type="llm.human.input",
                category="message",
                content='{"type": "human", "content": "第一轮问题"}',
                event_metadata={"content_is_json": True, "content_is_dict": True},
                seq=1,
            ),
            RunEventRow(
                thread_id="runtime-thread-1",
                run_id="run-1",
                user_id=str(user.id),
                event_type="llm.ai.response",
                category="message",
                content='{"type": "ai", "content": "第一轮回答"}',
                event_metadata={"content_is_json": True, "content_is_dict": True, "usage": {"total_tokens": 9}},
                seq=2,
            ),
            RunEventRow(
                thread_id="runtime-thread-1",
                run_id="run-1",
                user_id=str(user.id),
                event_type="llm.tool.result",
                category="message",
                content='{"type": "tool", "content": "工具结果"}',
                event_metadata={"content_is_json": True, "content_is_dict": True},
                seq=3,
            ),
        ]
    )
    await db_session.flush()

    resp = await client.get(
        "/api/admin/audit/threads/runtime-thread-1/messages",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 50},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert [item["role"] for item in data["items"]] == ["user", "assistant", "tool"]
    assert [item["content"] for item in data["items"]] == ["第一轮问题", "第一轮回答", "工具结果"]
    assert data["items"][1]["token_count"] == 9
    assert data["items"][1]["raw_content"]["event_type"] == "llm.ai.response"


@pytest.mark.asyncio
async def test_get_thread_stats_chart_reads_runtime_sources(client, auth_headers, seed_data, db_session):
    user = seed_data["regular_user"]
    db_session.add(ThreadMetaRow(thread_id="runtime-thread-1", user_id=str(user.id), display_name="A", status="idle"))
    db_session.add(RunRow(run_id="run-1", thread_id="runtime-thread-1", user_id=str(user.id), status="success", message_count=5))
    await db_session.flush()

    resp = await client.get(
        "/api/admin/audit/threads/stats/chart",
        headers=auth_headers["super_admin"],
        params={"quick": "7d"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert sum(item["thread_count"] for item in data["thread_stats"]) == 1
    assert sum(item["message_count"] for item in data["message_stats"]) == 5


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
