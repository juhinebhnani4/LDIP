"""Redis key prefix utilities for Layer 3 of 4-layer matter isolation.

This module implements the Redis key prefix pattern that ensures:
1. No cross-matter cache collisions
2. No cross-matter session access
3. Clear key structure for debugging and auditing

Key Patterns:
- Session Memory (7-day TTL): session:{matter_id}:{user_id}:{key_type}
- Query Cache (1-hour TTL): cache:query:{matter_id}:{query_hash}
- Matter Memory: matter:{matter_id}:{key_type}

CRITICAL: All Redis operations MUST use these functions to generate keys.
Never construct Redis keys manually to prevent isolation bypasses.
"""

import re
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# TTL Constants
# =============================================================================

SESSION_TTL = 7 * 24 * 60 * 60  # 7 days in seconds
MAX_SESSION_LIFETIME = 30 * 24 * 60 * 60  # 30 days absolute maximum (Story 7-2)
CACHE_TTL = 60 * 60  # 1 hour in seconds
MATTER_MEMORY_TTL = None  # No expiration for matter memory
EMBEDDING_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds

# =============================================================================
# Key Type Definitions
# =============================================================================

SessionKeyType = Literal["messages", "entities", "context", "metadata"]
MatterKeyType = Literal["timeline", "entity_graph", "findings", "stats"]

# =============================================================================
# UUID Validation
# =============================================================================

# UUID v4 pattern for validation
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE
)


def _validate_uuid(value: str, name: str) -> None:
    """Validate that a value is a valid UUID.

    Args:
        value: The value to validate.
        name: Name of the parameter (for error messages).

    Raises:
        ValueError: If the value is not a valid UUID.
    """
    if not value or not UUID_PATTERN.match(value):
        logger.warning(
            "invalid_uuid_in_redis_key",
            parameter=name,
            value=value[:50] if value else None,  # Truncate for security
        )
        raise ValueError(f"Invalid UUID for {name}: potential injection attempt")


def _sanitize_key_component(value: str, name: str, max_length: int = 64) -> str:
    """Sanitize a key component to prevent injection attacks.

    Args:
        value: The value to sanitize.
        name: Name of the parameter (for error messages).
        max_length: Maximum allowed length.

    Returns:
        Sanitized value.

    Raises:
        ValueError: If the value contains invalid characters or is too long.
    """
    if not value:
        raise ValueError(f"{name} cannot be empty")

    if len(value) > max_length:
        raise ValueError(f"{name} exceeds maximum length of {max_length}")

    # Allow only alphanumeric, hyphens, and underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", value):
        logger.warning(
            "invalid_characters_in_redis_key",
            parameter=name,
            value=value[:50],
        )
        raise ValueError(f"Invalid characters in {name}: only alphanumeric, hyphens, and underscores allowed")

    return value


# =============================================================================
# Session Key Functions
# =============================================================================

def session_key(
    matter_id: str,
    user_id: str,
    key_type: SessionKeyType = "messages"
) -> str:
    """Generate a session memory Redis key with matter isolation.

    Session keys store user-specific conversation context within a matter.
    TTL: 7 days with auto-extend on access.

    Args:
        matter_id: The matter UUID.
        user_id: The user UUID.
        key_type: Type of session data (messages, entities, context, metadata).

    Returns:
        Redis key in format: session:{matter_id}:{user_id}:{key_type}

    Raises:
        ValueError: If any parameter is invalid.

    Example:
        >>> key = session_key("abc-123", "user-456", "messages")
        >>> key
        'session:abc-123:user-456:messages'
    """
    _validate_uuid(matter_id, "matter_id")
    _validate_uuid(user_id, "user_id")
    _sanitize_key_component(key_type, "key_type")

    return f"session:{matter_id}:{user_id}:{key_type}"


# =============================================================================
# Cache Key Functions
# =============================================================================

def cache_key(matter_id: str, query_hash: str) -> str:
    """Generate a query cache Redis key with matter isolation.

    Cache keys store LLM query results for fast retrieval.
    TTL: 1 hour, invalidated on document upload.

    Args:
        matter_id: The matter UUID.
        query_hash: SHA256 hash of the normalized query.

    Returns:
        Redis key in format: cache:query:{matter_id}:{query_hash}

    Raises:
        ValueError: If any parameter is invalid.

    Example:
        >>> key = cache_key("abc-123", "sha256hash...")
        >>> key
        'cache:query:abc-123:sha256hash...'
    """
    _validate_uuid(matter_id, "matter_id")

    # Query hash should be a hex string (SHA256 = 64 chars)
    if not query_hash or not re.match(r"^[a-f0-9]{32,64}$", query_hash, re.IGNORECASE):
        raise ValueError("query_hash must be a valid hex hash (32-64 characters)")

    return f"cache:query:{matter_id}:{query_hash}"


# =============================================================================
# Matter Key Functions
# =============================================================================

def matter_key(matter_id: str, key_type: MatterKeyType) -> str:
    """Generate a matter-level Redis key with isolation.

    Matter keys store shared matter data (timeline cache, entity graph, etc.).
    No TTL - persists until explicitly deleted.

    Args:
        matter_id: The matter UUID.
        key_type: Type of matter data (timeline, entity_graph, findings, stats).

    Returns:
        Redis key in format: matter:{matter_id}:{key_type}

    Raises:
        ValueError: If any parameter is invalid.

    Example:
        >>> key = matter_key("abc-123", "timeline")
        >>> key
        'matter:abc-123:timeline'
    """
    _validate_uuid(matter_id, "matter_id")
    _sanitize_key_component(key_type, "key_type")

    return f"matter:{matter_id}:{key_type}"


# =============================================================================
# Key Validation Functions
# =============================================================================

def validate_key_access(key: str, authorized_matter_id: str) -> bool:
    """Validate that a Redis key belongs to the authorized matter.

    This is a defense-in-depth check to prevent cross-matter access
    even if a key is somehow constructed incorrectly.

    Args:
        key: The Redis key to validate.
        authorized_matter_id: The matter ID the user is authorized for.

    Returns:
        True if the key belongs to the authorized matter, False otherwise.

    Example:
        >>> validate_key_access("session:abc-123:user:messages", "abc-123")
        True
        >>> validate_key_access("session:xyz-789:user:messages", "abc-123")
        False
    """
    _validate_uuid(authorized_matter_id, "authorized_matter_id")

    # Extract matter_id from key based on key type
    key_matter_id = extract_matter_id_from_key(key)

    if key_matter_id is None:
        logger.warning(
            "could_not_extract_matter_id_from_key",
            key=key[:100],  # Truncate for security
        )
        return False

    is_valid = key_matter_id == authorized_matter_id

    if not is_valid:
        logger.warning(
            "cross_matter_key_access_attempt",
            key=key[:100],
            authorized_matter_id=authorized_matter_id,
            key_matter_id=key_matter_id,
        )

    return is_valid


def extract_matter_id_from_key(key: str) -> str | None:
    """Extract the matter_id from a Redis key.

    Args:
        key: The Redis key to parse.

    Returns:
        The matter_id if found, None otherwise.

    Example:
        >>> extract_matter_id_from_key("session:abc-123:user-456:messages")
        'abc-123'
        >>> extract_matter_id_from_key("cache:query:xyz-789:hash123")
        'xyz-789'
    """
    if not key:
        return None

    parts = key.split(":")

    # session:{matter_id}:{user_id}:{key_type}
    if key.startswith("session:") and len(parts) >= 4:
        return parts[1]

    # cache:query:{matter_id}:{query_hash}
    if key.startswith("cache:query:") and len(parts) >= 4:
        return parts[2]

    # matter:{matter_id}:{key_type}
    if key.startswith("matter:") and len(parts) >= 3:
        return parts[1]

    return None


# =============================================================================
# Bulk Key Pattern Functions (for invalidation)
# =============================================================================

def session_pattern(matter_id: str, user_id: str | None = None) -> str:
    """Generate a Redis SCAN pattern for session keys.

    Args:
        matter_id: The matter UUID.
        user_id: Optional user UUID to filter by.

    Returns:
        Redis pattern for SCAN command.

    Example:
        >>> session_pattern("abc-123")
        'session:abc-123:*'
        >>> session_pattern("abc-123", "user-456")
        'session:abc-123:user-456:*'
    """
    _validate_uuid(matter_id, "matter_id")

    if user_id:
        _validate_uuid(user_id, "user_id")
        return f"session:{matter_id}:{user_id}:*"

    return f"session:{matter_id}:*"


def cache_pattern(matter_id: str) -> str:
    """Generate a Redis SCAN pattern for cache keys.

    Use this pattern to invalidate all cache entries for a matter
    (e.g., when new documents are uploaded).

    Args:
        matter_id: The matter UUID.

    Returns:
        Redis pattern for SCAN command.

    Example:
        >>> cache_pattern("abc-123")
        'cache:query:abc-123:*'
    """
    _validate_uuid(matter_id, "matter_id")
    return f"cache:query:{matter_id}:*"


def matter_pattern(matter_id: str) -> str:
    """Generate a Redis SCAN pattern for matter keys.

    Args:
        matter_id: The matter UUID.

    Returns:
        Redis pattern for SCAN command.

    Example:
        >>> matter_pattern("abc-123")
        'matter:abc-123:*'
    """
    _validate_uuid(matter_id, "matter_id")
    return f"matter:{matter_id}:*"


# =============================================================================
# Embedding Cache Key Functions
# =============================================================================

def embedding_cache_key(text_hash: str) -> str:
    """Generate a Redis key for cached embeddings.

    Embedding cache keys store OpenAI embeddings to avoid re-generating
    for the same text content.
    TTL: 24 hours.

    Args:
        text_hash: SHA256 hash of the text content.

    Returns:
        Redis key in format: embedding:{text_hash}

    Raises:
        ValueError: If text_hash is invalid.

    Example:
        >>> key = embedding_cache_key("a1b2c3d4...")
        >>> key
        'embedding:a1b2c3d4...'
    """
    # Text hash should be a hex string (SHA256 = 64 chars)
    if not text_hash or not re.match(r"^[a-f0-9]{32,64}$", text_hash, re.IGNORECASE):
        raise ValueError("text_hash must be a valid hex hash (32-64 characters)")

    return f"embedding:{text_hash}"
