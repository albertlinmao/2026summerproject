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
    # Demo auth endpoints require APP_ENV=development AND DEMO_AUTH_ENABLED=true
    # (research.md D4, T002). Safe default: off, so the dev branch is not live
    # just because APP_ENV defaults to development.
    DEMO_AUTH_ENABLED: bool = False
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    # Container-internal port; docker-compose.yml publishes it as 18081. A local
    # host run must override this (PORT=8080) because the Supabase stack's Kong
    # already binds host port 8000.
    PORT: int = 8000

    # Supabase
    # Kong is the stack's only HTTP entry point, published on host port 8000 by
    # supabase/docker-compose.yml (see supabase/.env). The Supabase CLI's 54321
    # is not in use.
    SUPABASE_URL: str = Field(default="http://localhost:8000", validation_alias="SUPABASE_URL")
    SUPABASE_ANON_KEY: str = Field(default="", validation_alias="SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    # Legacy/alternate name used by some .env files; fallback for the anon key
    SUPABASE_KEY: str = Field(default="", validation_alias="SUPABASE_KEY")

    # Database (Supabase PostgreSQL) - POSTGRES_PORT in supabase/.env
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/postgres", validation_alias="DATABASE_URL")

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