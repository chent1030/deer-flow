from pydantic import BaseModel, Field


class MinioConfig(BaseModel):
    endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    access_key: str = Field(default="", description="MinIO access key")
    secret_key: str = Field(default="", description="MinIO secret key")
    bucket: str = Field(default="deerflow-skills", description="MinIO bucket name")
    secure: bool = Field(default=False, description="Use HTTPS")


class JwtConfig(BaseModel):
    secret_key: str = Field(default="change-me-in-production", description="JWT signing key")
    access_token_expire_minutes: int = Field(default=60, ge=1, description="Access token TTL")
    refresh_token_expire_days: int = Field(default=7, ge=1, description="Refresh token TTL")


class InitialSuperAdminConfig(BaseModel):
    username: str = Field(default="admin", description="Initial super admin username")
    password: str = Field(default="admin123", description="Initial super admin password")
    email: str = Field(default="admin@example.com", description="Initial super admin email")


class AdminConfig(BaseModel):
    database_url: str = Field(
        default="postgresql+asyncpg://deerflow:deerflow@localhost:5432/deerflow_admin",
        description="PostgreSQL connection URL",
    )
    minio: MinioConfig = Field(default_factory=MinioConfig)
    jwt: JwtConfig = Field(default_factory=JwtConfig)
    initial_super_admin: InitialSuperAdminConfig = Field(default_factory=InitialSuperAdminConfig)
