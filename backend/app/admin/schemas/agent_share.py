from __future__ import annotations

from pydantic import BaseModel


class AgentShareRecordResponse(BaseModel):
    id: str
    source_owner_id: str
    source_owner_username: str | None = None
    source_owner_display_name: str | None = None
    source_agent_name: str
    target_user_id: str
    target_username: str | None = None
    target_display_name: str | None = None
    target_agent_name: str | None = None
    status: str
    error_message: str | None = None
    created_at: str | None = None


class AgentShareRecordListResponse(BaseModel):
    items: list[AgentShareRecordResponse]
    total: int
    page: int
    page_size: int
