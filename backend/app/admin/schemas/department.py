import uuid

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    parent_id: uuid.UUID | None = None


class DepartmentResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None
    created_at: str | None = None
    children: list["DepartmentResponse"] = []
    member_count: int = 0

    class Config:
        from_attributes = True


class DepartmentTreeResponse(BaseModel):
    departments: list[DepartmentResponse]
