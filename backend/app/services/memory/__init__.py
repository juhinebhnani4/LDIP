"""Memory services for session and cache management."""

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

__all__ = [
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
]
