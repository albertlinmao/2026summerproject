from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Support running from backend/ or the repo root (root .env fallback)
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Artistic Swimming Analytics API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Supabase
    SUPABASE_URL: str = Field(default="http://localhost:54321", validation_alias="SUPABASE_URL")
    SUPABASE_ANON_KEY: str = Field(default="", validation_alias="SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    # Legacy/alternate name used by some .env files; fallback for the anon key
    SUPABASE_KEY: str = Field(default="", validation_alias="SUPABASE_KEY")

    # Database (Supabase PostgreSQL)
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:54322/postgres", validation_alias="DATABASE_URL")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    # JWT / Multi-Tenant User Service API
    USER_SERVICE_URL: str = Field(default="http://localhost:8001", validation_alias="USER_SERVICE_URL")
    USER_SERVICE_JWT_SECRET: str = Field(default="", validation_alias="USER_SERVICE_JWT_SECRET")
    USER_SERVICE_JWT_ALGORITHM: str = Field(default="RS256", validation_alias="USER_SERVICE_JWT_ALGORITHM")
    USER_SERVICE_JWKS_URL: str = Field(default="", validation_alias="USER_SERVICE_JWKS_URL")

    # CORS
    CORS_ORIGINS: List[str] = Field(
        # Accept both hostnames - browsers may treat localhost and 127.0.0.1
        # as different origins depending on which URL the SPA is opened from.
        default=["http://localhost:4200", "http://127.0.0.1:4200", "http://localhost:8081", "http://127.0.0.1:8081", "http://localhost"],
        validation_alias="CORS_ORIGINS"
    )

    # OpenAI
    OPENAI_API_KEY: str = Field(default="", validation_alias="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview", validation_alias="OPENAI_MODEL")

    # Video Upload
    MAX_VIDEO_SIZE_MB: int = Field(default=500, validation_alias="MAX_VIDEO_SIZE_MB")
    ALLOWED_VIDEO_MIME_TYPES: List[str] = Field(
        default=["video/mp4", "video/quicktime", "video/x-msvideo"],
        validation_alias="ALLOWED_VIDEO_MIME_TYPES"
    )
    VIDEO_RETENTION_DAYS: int = Field(default=90, validation_alias="VIDEO_RETENTION_DAYS")

    # File Storage
    SWIM_MEETS_PATH: str = Field(default="./swim-meets", validation_alias="SWIM_MEETS_PATH")

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, validation_alias="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")

    @property
    def max_video_size_bytes(self) -> int:
        return self.MAX_VIDEO_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()