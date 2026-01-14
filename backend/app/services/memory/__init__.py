"""Memory services for session and cache management.

Story 7-1: Added SessionMemoryService and Redis client.
"""

from app.services.memory.redis_keys import (
    SESSION_TTL,
    CACHE_TTL,
    MATTER_MEMORY_TTL,
    EMBEDDING_CACHE_TTL,
    session_key,
    cache_key,
    matter_key,
    validate_key_access,
    extract_matter_id_from_key,
    session_pattern,
    cache_pattern,
    matter_pattern,
    embedding_cache_key,
)
from app.services.memory.redis_client import (
    get_redis_client,
    reset_redis_client,
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
    # Session memory service (Story 7-1)
    "MAX_SESSION_MESSAGES",
    "SessionMemoryService",
    "get_session_memory_service",
    "reset_session_memory_service",
]
