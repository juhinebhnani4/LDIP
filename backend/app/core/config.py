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
    gemini_model: str = "gemini-2.5-flash"  # Valid models: gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-pro

    # GPT-4 Configuration (Story 5-2: Contradiction Detection)
    openai_comparison_model: str = "gpt-4-turbo-preview"  # or gpt-4o

    # Model Routing for Contradiction Detection (Cost Optimization)
    # Two-tier approach: Gemini Flash screens first, GPT-4 only for uncertain/contradictions
    contradiction_model_routing_enabled: bool = True  # Enable two-tier routing
    contradiction_screening_model: str = "gemini-2.0-flash"  # Fast/cheap for initial screening
    contradiction_screening_confidence_threshold: float = 0.85  # Below this -> escalate to GPT-4
    contradiction_escalate_results: list[str] = ["contradiction", "uncertain"]  # Results to escalate

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

    # Entity Extraction Performance Configuration
    entity_extraction_use_batch: bool = True        # Use mega-batch extraction (5 chunks/call)
    entity_extraction_batch_size: int = 5           # Chunks per mega-batch API call
    entity_extraction_concurrent_limit: int = 5     # Max concurrent API calls
    entity_extraction_rate_delay: float = 0.3       # Delay between batches (seconds)

    # Citation Verification Configuration (Story 3-3)
    verification_batch_size: int = 10               # Citations to verify in parallel
    verification_rate_limit_delay: float = 0.5      # Delay between API calls (seconds)
    verification_min_similarity: float = 70.0       # Minimum similarity for VERIFIED status
    verification_section_search_top_k: int = 5      # Max section candidates to retrieve

    # LLM Rate Limiting Configuration (Application-level throttling)
    # Prevents hitting provider rate limits (429 errors) with concurrent workers
    # Gemini rate limits (conservative for free tier ~60 RPM)
    gemini_max_concurrent_requests: int = 3         # Max parallel Gemini API calls
    gemini_min_request_delay: float = 0.2           # Min seconds between requests
    gemini_requests_per_minute: int = 60            # Target RPM (for monitoring)
    # OpenAI rate limits (tier 1 ~500 RPM)
    openai_max_concurrent_requests: int = 5         # Max parallel OpenAI API calls
    openai_min_request_delay: float = 0.1           # Min seconds between requests
    openai_requests_per_minute: int = 500           # Target RPM (for monitoring)

    # Finding Verification Thresholds (Story 8-4: ADR-004 Tiered Verification)
    # Controls when attorney verification is optional, suggested, or required
    # > verification_threshold_optional: verification is optional (informational only)
    # > verification_threshold_suggested: verification is suggested (warning shown on export)
    # <= verification_threshold_suggested: verification is required (export blocked)
    verification_threshold_optional: float = 90.0   # > 90% confidence = optional verification
    verification_threshold_suggested: float = 70.0  # > 70% confidence = suggested verification
    verification_export_block_below: float = 70.0   # < 70% unverified = blocks export

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

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

    # Chunk Recovery Configuration (Story 4.3 - Pipeline Improvements)
    chunk_stale_threshold_seconds: int = 90   # Chunks in "processing" > this are stale
    chunk_recovery_enabled: bool = True       # Master switch for automatic chunk recovery
    chunk_max_recovery_retries: int = 3       # Max times a chunk can be auto-recovered

    # Admin Configuration (Story 14.17)
    admin_emails: str = ""  # Comma-separated list of admin emails (ADMIN_EMAILS env var)
    rate_limit_admin: int = 10  # Admin operations rate limit (per minute)

    # Table Extraction Configuration (RAG Production Gaps - Feature 1)
    table_extraction_enabled: bool = True  # Master switch for table extraction
    table_detection_confidence_threshold: float = 0.70  # Min confidence to include table

    # Evaluation Framework Configuration (RAG Production Gaps - Feature 2)
    auto_evaluation_enabled: bool = False  # Auto-evaluate after ingestion (cost warning)
    openai_evaluation_model: str = "gpt-4"  # Model for RAGAS evaluation
    evaluation_batch_size: int = 10  # Golden dataset items per batch

    # Inspector Mode Configuration (RAG Production Gaps - Feature 3)
    inspector_enabled: bool = True  # Enable search inspector endpoints

    # ==========================================================================
    # India Code Integration (Act Validation and Auto-Fetching)
    # ==========================================================================

    # Feature flags
    india_code_enabled: bool = True                    # Master switch for India Code integration
    india_code_auto_fetch_enabled: bool = True         # Auto-fetch PDFs from India Code
    act_validation_enabled: bool = True                # Enable garbage detection/validation

    # Rate limiting for India Code requests
    india_code_request_delay: float = 2.0              # Seconds between requests
    india_code_max_requests_per_minute: int = 5        # Rate limit (be polite to gov site)
    india_code_request_timeout: float = 30.0           # HTTP timeout for India Code requests

    # Validation task configuration
    validation_max_acts_per_task: int = 50             # Max acts to validate per Celery task
    validation_max_fetch_per_task: int = 5             # Max acts to fetch per Celery task
    validation_task_retry_delay: int = 60              # Seconds between task retries
    validation_task_max_retries: int = 3               # Max retry attempts for tasks

    # Act name validation thresholds
    act_name_min_length: int = 5                       # Minimum valid act name length
    act_name_max_length: int = 150                     # Maximum valid act name length
    validation_garbage_base_confidence: float = 0.5    # Base confidence for garbage detection
    validation_garbage_increment: float = 0.1          # Confidence increment per pattern match
    validation_known_act_confidence: float = 0.95      # Confidence for known acts
    validation_unknown_act_confidence: float = 0.5     # Confidence for unknown acts

    # Act cache settings
    act_cache_url_expiry_seconds: int = 86400          # Signed URL expiration (24 hours)
    act_cache_storage_prefix: str = "global/acts"      # Storage path prefix for cached acts

    # Circuit breaker (for resilience)
    india_code_circuit_breaker_enabled: bool = True    # Enable circuit breaker pattern
    india_code_circuit_breaker_threshold: int = 5      # Failures before circuit opens
    india_code_circuit_breaker_timeout: int = 300      # Seconds before trying again

    # ==========================================================================
    # File Upload Configuration (Story 2.5: File Size Validation)
    # ==========================================================================
    file_size_max_mb: int = 50               # Maximum file size in MB (per file)
    file_size_enforcement: str = "enforce"   # "enforce"=reject, "warn"=log only
    file_size_soft_launch_until: str = ""    # ISO date for soft-launch end

    # ==========================================================================
    # WebSocket Configuration (Real-time Streaming)
    # ==========================================================================
    websocket_ping_interval: int = 30                  # Seconds between server pings
    websocket_max_connections_per_matter: int = 100    # Max connections per matter
    websocket_heartbeat_timeout: int = 60              # Seconds before considering connection dead

    @property
    def is_configured(self) -> bool:
        """Check if essential configuration is present."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def is_gemini_configured(self) -> bool:
        """Check if Gemini API is configured for entity extraction."""
        return bool(self.gemini_api_key)

    @property
    def is_openai_configured(self) -> bool:
        """Check if OpenAI API is configured for embeddings and LLM."""
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
