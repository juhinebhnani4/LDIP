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
    cohere_api_key: str = ""  # For Cohere Rerank v3.5

    # Google Cloud
    google_cloud_project_id: str = ""
    google_cloud_location: str = "us"
    google_document_ai_processor_id: str = ""

    # Gemini Configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # GPT-4 Configuration (Story 5-2: Contradiction Detection)
    openai_comparison_model: str = "gpt-4-turbo-preview"  # or gpt-4o

    # OCR Validation Thresholds
    ocr_validation_gemini_threshold: float = 0.85  # Below this -> Gemini validation
    ocr_validation_human_threshold: float = 0.50   # Below this -> Human review
    ocr_validation_batch_size: int = 20            # Max words per Gemini request

    # OCR Quality Assessment Thresholds
    ocr_quality_good_threshold: float = 0.85       # Above this = Good
    ocr_quality_fair_threshold: float = 0.70       # Above this = Fair, below = Poor
    ocr_page_highlight_threshold: float = 0.60     # Pages below this are highlighted

    # Chunking Configuration (Parent-Child for RAG)
    chunk_parent_size: int = 1750       # Target: 1500-2000 tokens for context
    chunk_parent_overlap: int = 100     # 5-7% overlap for parent chunks
    chunk_child_size: int = 550         # Target: 400-700 tokens for retrieval
    chunk_child_overlap: int = 75       # 50-100 tokens (~14%) for child chunks
    chunk_min_size: int = 100           # Minimum viable chunk size

    # Citation Verification Configuration (Story 3-3)
    verification_batch_size: int = 10               # Citations to verify in parallel
    verification_rate_limit_delay: float = 0.5      # Delay between API calls (seconds)
    verification_min_similarity: float = 70.0       # Minimum similarity for VERIFIED status
    verification_section_search_top_k: int = 5      # Max section candidates to retrieve

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
