"""Application settings and environment configuration."""
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "stride-super-secret-development-jwt-key-change-in-production-min-32-chars"
_DEFAULT_GITHUB_WEBHOOK_SECRET = "stride-github-webhook-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General App Config
    APP_NAME: str = "Stride"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # CORS: comma-separated origins, or "*" for all. Credentials are auto-disabled when "*" is used.
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # Database Config
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./stride_dev.db",
        description="Async database connection string (e.g. postgresql+asyncpg://... or sqlite+aiosqlite://...)",
    )
    DATABASE_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    # Set true when routing asyncpg through PgBouncer in transaction pooling mode.
    DB_DISABLE_PREPARED_CACHE: bool = False

    # Safety ceiling for task-heavy board/timeline aggregations (Kanban/Gantt/Calendar).
    MAX_VIEW_TASKS: int = 2000

    # Redis Config
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_USE_FAKE_IF_UNAVAILABLE: bool = True

    # Security & JWT Config
    JWT_SECRET_KEY: str = _DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # S3 Object Storage Config
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "stride-storage"
    S3_REGION: str = "us-east-1"

    # Integrations Config
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_WEBHOOK_SECRET: str = _DEFAULT_GITHUB_WEBHOOK_SECRET
    FIGMA_API_ACCESS_TOKEN: str | None = None

    # AI Pipeline Engine Config
    AI_GATE_STRICT_MODE: bool = True
    AI_DEFAULT_MODEL: str = "gemini-1.5-pro"

    # LLM providers for the 5-Gate pipeline. All optional: when no key is set (or every
    # provider fails / is rate-limited), the pipeline falls back to deterministic heuristics.
    # Providers are tried in LLM_PROVIDER_ORDER; each speaks the OpenAI-compatible API.
    LLM_ENABLED: bool = True
    LLM_TIMEOUT_SECONDS: float = 20.0
    LLM_PROVIDER_ORDER: str = "openrouter,groq,gemini"

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        """Refuse to boot in production with committed default secrets."""
        if self.ENVIRONMENT != "production":
            return self
        insecure: list[str] = []
        if self.JWT_SECRET_KEY == _DEFAULT_JWT_SECRET:
            insecure.append("JWT_SECRET_KEY")
        if self.GITHUB_WEBHOOK_SECRET == _DEFAULT_GITHUB_WEBHOOK_SECRET:
            insecure.append("GITHUB_WEBHOOK_SECRET")
        if self.S3_SECRET_KEY == "minioadmin":
            insecure.append("S3_SECRET_KEY")
        if insecure:
            raise ValueError(
                "Insecure default secret(s) may not be used in production: "
                + ", ".join(insecure)
            )
        return self


settings = Settings()
