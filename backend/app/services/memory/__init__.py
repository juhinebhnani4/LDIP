"""Memory services for session and cache management.

Story 7-1: Added SessionMemoryService and Redis client.
Story 7-2: Added MatterMemoryRepository for archived sessions.
"""

from app.models.memory import ArchivedSession
from app.services.memory.matter import (
    ARCHIVED_SESSION_TYPE,
    MatterMemoryRepository,
    get_matter_memory_repository,
    reset_matter_memory_repository,
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
    # Matter memory repository (Story 7-2)
    "ARCHIVED_SESSION_TYPE",
    "ArchivedSession",
    "MatterMemoryRepository",
    "get_matter_memory_repository",
    "reset_matter_memory_repository",
]
