import uuid

from pydantic import BaseModel, Field, field_validator

from app.admin.auth.password import validate_password_complexity
from app.admin.models.user import UserRole, UserStatus


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8)
    display_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(default="", max_length=255)
    department_id: uuid.UUID | None = None
    role: UserRole = UserRole.USER

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_complexity(value)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    clear_department: bool = False
    role: UserRole | None = None


class UserStatusUpdate(BaseModel):
    status: UserStatus


class UserPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_complexity(value)


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str
    department_id: str | None
    status: str
    created_at: str | None = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
