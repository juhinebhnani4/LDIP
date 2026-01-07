"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "LDIP Backend"
    debug: bool = False
    api_version: str = "v1"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""  # anon key for client operations
    supabase_service_key: str = ""  # service role key for admin operations
    supabase_jwt_secret: str = ""  # JWT secret for local token validation

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # LLM API Keys
    openai_api_key: str = ""
    google_api_key: str = ""

    # Google Cloud
    google_cloud_project_id: str = ""
    google_cloud_location: str = "us"
    google_document_ai_processor_id: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_configured(self) -> bool:
        """Check if essential configuration is present."""
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
