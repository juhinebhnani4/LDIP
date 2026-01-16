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
    gemini_model: str = "gemini-3-flash"

    # GPT-4 Configuration (Story 5-2: Contradiction Detection)
    openai_comparison_model: str = "gpt-4-turbo-preview"  # or gpt-4o

    # GPT-3.5 Configuration (Story 6-1: Query Intent Classification)
    openai_intent_model: str = "gpt-3.5-turbo"  # Cost-sensitive classification

    # GPT-4o-mini Configuration (Story 8-2: Subtle Violation Detection)
    openai_safety_model: str = "gpt-4o-mini"  # 200x cheaper than GPT-4 for input
    safety_llm_timeout: float = 10.0  # Hard timeout for safety LLM calls (seconds)
    safety_llm_enabled: bool = True  # Feature flag to enable/disable LLM safety check

    # Language Policing Configuration (Story 8-3: Output Sanitization)
    language_policing_enabled: bool = True  # Master switch for language policing
    policing_llm_enabled: bool = True  # Feature flag to enable/disable LLM polish
    policing_llm_timeout: float = 10.0  # Hard timeout for policing LLM calls (seconds)

    # GPT-4o-mini Cost Tracking (M2 fix: configurable pricing for Stories 8-2, 8-3)
    safety_llm_input_cost_per_1k: float = 0.00015  # $0.00015 per 1K input tokens
    safety_llm_output_cost_per_1k: float = 0.0006  # $0.0006 per 1K output tokens

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

    # Finding Verification Thresholds (Story 8-4: ADR-004 Tiered Verification)
    # Controls when attorney verification is optional, suggested, or required
    # > verification_threshold_optional: verification is optional (informational only)
    # > verification_threshold_suggested: verification is suggested (warning shown on export)
    # <= verification_threshold_suggested: verification is required (export blocked)
    verification_threshold_optional: float = 90.0   # > 90% confidence = optional verification
    verification_threshold_suggested: float = 70.0  # > 70% confidence = suggested verification
    verification_export_block_below: float = 70.0   # < 70% unverified = blocks export

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Axiom Logging (Story 13.1)
    axiom_token: str = ""  # AXIOM_TOKEN env var
    axiom_dataset: str = "ldip-logs"  # AXIOM_DATASET env var

    # Rate Limiting (Story 13.3)
    rate_limit_default: int = 100  # requests per minute (standard CRUD endpoints)
    rate_limit_critical: int = 30  # LLM/chat/export endpoints (expensive)
    rate_limit_search: int = 60    # search endpoints (vector operations)
    rate_limit_readonly: int = 120  # read-only dashboard/stats endpoints
    rate_limit_health: int = 300   # health/monitoring endpoints (high frequency)
    rate_limit_export: int = 20    # export generation (CPU-intensive)

    # Engine Orchestrator Configuration (Story 6-2)
    # Engine confidence weights for overall score calculation (higher = more influence)
    orchestrator_weight_citation: float = 1.0   # Citation engine weight
    orchestrator_weight_timeline: float = 1.0   # Timeline engine weight
    orchestrator_weight_contradiction: float = 1.2  # Contradiction engine (slightly higher)
    orchestrator_weight_rag: float = 0.8        # RAG engine (slightly lower - general search)

    # RAG adapter configuration
    rag_search_limit: int = 20     # Candidates to retrieve before reranking
    rag_rerank_top_n: int = 5      # Results to return after reranking
    timeline_default_page_size: int = 50  # Default timeline events per page

    # Memory System Configuration (Story 7 - Epic 7 Code Review Fixes)
    session_max_messages: int = 20          # Max messages in sliding window (session.py)
    session_max_entities: int = 50          # Max entities tracked for pronoun resolution
    archived_session_max_messages: int = 10 # Max messages stored in archived session
    query_history_max_entries: int = 500    # Max query history entries per matter (JSONB limit)
    query_history_default_limit: int = 100  # Default entries returned from get_query_history
    archived_session_query_limit: int = 10  # Default archived sessions to return

    # Job Recovery Configuration (Stale Job Detection)
    job_stale_timeout_minutes: int = 30     # Jobs in PROCESSING for > this are considered stale
    job_recovery_scan_interval: int = 5     # Minutes between recovery scans (Celery beat)
    job_max_recovery_retries: int = 3       # Max times a stale job can be auto-recovered
    job_recovery_enabled: bool = True       # Master switch for automatic job recovery

    @property
    def is_configured(self) -> bool:
        """Check if essential configuration is present."""
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
