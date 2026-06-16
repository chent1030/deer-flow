from __future__ import annotations

import pytest

from app.admin.models.agent_share import AgentShareRecord, AgentShareStatus


@pytest.mark.asyncio
async def test_list_agent_share_records(client, auth_headers, seed_data, db_session):
    db_session.add(
        AgentShareRecord(
            source_owner_id=seed_data["super_admin"].id,
            source_agent_name="sales-agent",
            target_user_id=seed_data["regular_user"].id,
            target_agent_name="sales-agent-copy",
            status=AgentShareStatus.CREATED,
        )
    )
    await db_session.flush()

    resp = await client.get(
        "/api/admin/agent-share-records",
        headers=auth_headers["super_admin"],
        params={"page": 1, "page_size": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["source_agent_name"] == "sales-agent"
    assert data["items"][0]["target_agent_name"] == "sales-agent-copy"
    assert data["items"][0]["source_owner_username"] == "superadmin"
    assert data["items"][0]["target_username"] == "regularuser"
