import uuid

from pydantic import BaseModel, Field

from app.admin.models.skill import SkillVisibility


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    version: str | None = Field(default=None, max_length=20)


class SkillVisibilityUpdate(BaseModel):
    visibility: SkillVisibility
    visible_user_ids: list[uuid.UUID] = Field(default_factory=list)
    visible_department_ids: list[uuid.UUID] = Field(default_factory=list)


class SkillReviewRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject)$")
    comment: str = Field(default="", max_length=1000)


class SkillAutoReviewRequest(BaseModel):
    review_skill_name: str = Field(default="skill-reviewer", min_length=1, max_length=100)


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    version: str
    author_id: str
    department_id: str | None
    visibility: str
    status: str
    file_size: int
    reviewed_by: str | None
    reviewed_at: str | None
    review_comment: str | None
    created_at: str | None
    author_name: str | None = None
    department_name: str | None = None
    visible_user_ids: list[str] = []
    visible_department_ids: list[str] = []

    class Config:
        from_attributes = True


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int
    page: int
    page_size: int


class VisibleSkillsResponse(BaseModel):
    skill_names: list[str]
