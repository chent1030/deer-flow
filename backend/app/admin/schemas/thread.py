from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ThreadAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    username: str | None = None
    display_name: str | None = None


class ThreadAuditListResponse(BaseModel):
    items: list[ThreadAuditResponse]
    total: int


class ThreadMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    role: str
    content: str | None
    raw_content: dict | None
    token_count: int | None
    created_at: datetime


class ThreadMessageListResponse(BaseModel):
    items: list[ThreadMessageResponse]
    total: int


class ThreadStatsResponse(BaseModel):
    total_threads: int
    total_messages: int
    active_users: int


class DailyStatsPoint(BaseModel):
    date: str
    thread_count: int


class DailyMessageStatsPoint(BaseModel):
    date: str
    message_count: int


class ThreadStatsChartResponse(BaseModel):
    thread_stats: list[DailyStatsPoint]
    message_stats: list[DailyMessageStatsPoint]
