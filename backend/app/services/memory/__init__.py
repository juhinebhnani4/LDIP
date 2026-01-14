"""Memory services for session and cache management.

Story 7-1: Added SessionMemoryService and Redis client.
Story 7-2: Added MatterMemoryRepository for archived sessions.
Story 7-3: Added MatterMemoryService for full matter memory.
Story 7-4: Added Key Findings and Research Notes support.
Story 7-5: Added Query Cache for LLM response caching.
"""

from app.models.memory import (
    ArchivedSession,
    CachedEntity,
    CachedQueryResult,
    EntityGraphCache,
    EntityRelationship,
    FindingEvidence,
    FindingType,
    KeyFinding,
    KeyFindings,
    QueryHistory,
    QueryHistoryEntry,
    ResearchNote,
    ResearchNotes,
    TimelineCache,
    TimelineCacheEntry,
)
from app.services.memory.matter import (
    ARCHIVED_SESSION_TYPE,
    ENTITY_GRAPH_TYPE,
    KEY_FINDINGS_KEY,
    KEY_FINDINGS_TYPE,
    QUERY_HISTORY_KEY,
    QUERY_HISTORY_TYPE,
    RESEARCH_NOTES_KEY,
    RESEARCH_NOTES_TYPE,
    TIMELINE_CACHE_TYPE,
    MatterMemoryRepository,
    get_matter_memory_repository,
    is_cache_stale,
    reset_matter_memory_repository,
)
from app.services.memory.matter_service import (
    MatterMemoryService,
    get_matter_memory_service,
    reset_matter_memory_service,
)
from app.services.memory.redis_client import (
    get_redis_client,
    reset_redis_client,
)
from app.services.memory.redis_keys import (
    CACHE_TTL,
    EMBEDDING_CACHE_TTL,
    MATTER_MEMORY_TTL,
    MAX_SESSION_LIFETIME,
    SESSION_TTL,
    cache_key,
    cache_pattern,
    embedding_cache_key,
    extract_matter_id_from_key,
    matter_key,
    matter_pattern,
    session_key,
    session_pattern,
    validate_key_access,
)
from app.services.memory.session import (
    MAX_SESSION_MESSAGES,
    SessionMemoryService,
    get_session_memory_service,
    reset_session_memory_service,
)

# Story 7-5: Query Cache
from app.services.memory.query_cache import (
    QueryCacheRepository,
    get_query_cache_repository,
    reset_query_cache_repository,
)
from app.services.memory.query_cache_service import (
    QueryCacheService,
    get_query_cache_service,
    reset_query_cache_service,
)
from app.services.memory.query_normalizer import (
    QueryNormalizer,
    get_query_normalizer,
    reset_query_normalizer,
)

__all__ = [
    # Redis key utilities
    "SESSION_TTL",
    "MAX_SESSION_LIFETIME",
    "CACHE_TTL",
    "MATTER_MEMORY_TTL",
    "EMBEDDING_CACHE_TTL",
    "session_key",
    "cache_key",
    "matter_key",
    "validate_key_access",
    "extract_matter_id_from_key",
    "session_pattern",
    "cache_pattern",
    "matter_pattern",
    "embedding_cache_key",
    # Redis client (Story 7-1)
    "get_redis_client",
    "reset_redis_client",
    # Session memory service (Story 7-1, 7-2)
    "MAX_SESSION_MESSAGES",
    "SessionMemoryService",
    "get_session_memory_service",
    "reset_session_memory_service",
    # Matter memory repository (Story 7-2, 7-3, 7-4)
    "ARCHIVED_SESSION_TYPE",
    "QUERY_HISTORY_TYPE",
    "QUERY_HISTORY_KEY",
    "TIMELINE_CACHE_TYPE",
    "ENTITY_GRAPH_TYPE",
    "KEY_FINDINGS_TYPE",
    "KEY_FINDINGS_KEY",
    "RESEARCH_NOTES_TYPE",
    "RESEARCH_NOTES_KEY",
    "ArchivedSession",
    "MatterMemoryRepository",
    "get_matter_memory_repository",
    "reset_matter_memory_repository",
    "is_cache_stale",
    # Matter memory service (Story 7-3, 7-4)
    "MatterMemoryService",
    "get_matter_memory_service",
    "reset_matter_memory_service",
    # Matter memory models (Story 7-3)
    "QueryHistoryEntry",
    "QueryHistory",
    "TimelineCacheEntry",
    "TimelineCache",
    "CachedEntity",
    "EntityRelationship",
    "EntityGraphCache",
    # Key Findings and Research Notes models (Story 7-4)
    "FindingType",
    "FindingEvidence",
    "KeyFinding",
    "KeyFindings",
    "ResearchNote",
    "ResearchNotes",
    # Query Cache (Story 7-5)
    "CachedQueryResult",
    "QueryNormalizer",
    "get_query_normalizer",
    "reset_query_normalizer",
    "QueryCacheRepository",
    "get_query_cache_repository",
    "reset_query_cache_repository",
    "QueryCacheService",
    "get_query_cache_service",
    "reset_query_cache_service",
]
