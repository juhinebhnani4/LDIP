"""Query normalization utilities for consistent cache key generation.

Story 7-5: AC #1 - query_hash is SHA256 of normalized query text.

Query normalization ensures that semantically equivalent queries
produce the same cache key, improving cache hit rate.

Normalization steps:
1. Lowercase
2. Collapse whitespace (multiple spaces to single)
3. Trim leading/trailing whitespace
4. Remove non-essential punctuation
5. Generate SHA256 hash
"""

import hashlib
import re

import structlog

logger = structlog.get_logger(__name__)


class QueryNormalizer:
    """Normalize queries for consistent cache key generation.

    Story 7-5: Task 1.2 / Task 3 - Query normalization utility.

    Ensures semantically equivalent queries like:
    - "What is SARFAESI?"
    - "what is sarfaesi?"
    - "What   is   SARFAESI  ?"

    All produce the same cache key.
    """

    # Characters to keep during normalization (alphanumeric + semantic punctuation)
    # Keeps: letters, numbers, whitespace, ? . , ' " -
    # Strips: @ # $ % ^ & * ( ) = + [ ] { } | \ ; : < > / ~
    _ALLOWED_CHARS_PATTERN = re.compile(r"[^\w\s\?\.\,\'\"\-]")

    def normalize(self, query: str) -> str:
        """Normalize query for consistent hashing.

        Story 7-5: Task 3.1-3.3 - Query normalization.

        Steps:
        1. Lowercase (case insensitive matching)
        2. Collapse multiple whitespace to single space
        3. Strip leading/trailing whitespace
        4. Remove non-essential punctuation

        Args:
            query: Original user query.

        Returns:
            Normalized query string.

        Example:
            >>> normalizer = QueryNormalizer()
            >>> normalizer.normalize("What   is SARFAESI?")
            'what is sarfaesi?'
        """
        if not query:
            return ""

        # Step 1: Lowercase
        normalized = query.lower()

        # Step 2: Collapse whitespace (multiple spaces/tabs/newlines to single space)
        normalized = re.sub(r"\s+", " ", normalized)

        # Step 3: Strip leading/trailing whitespace
        normalized = normalized.strip()

        # Step 4: Remove non-essential punctuation
        # Keep alphanumeric, basic punctuation for semantic meaning
        normalized = self._ALLOWED_CHARS_PATTERN.sub("", normalized)

        return normalized

    def hash(self, query: str) -> str:
        """Generate SHA256 hash of normalized query.

        Story 7-5: Task 3.4 - SHA256 hashing.

        Args:
            query: Original user query (will be normalized first).

        Returns:
            64-character lowercase hexadecimal SHA256 hash.

        Example:
            >>> normalizer = QueryNormalizer()
            >>> hash1 = normalizer.hash("What is SARFAESI?")
            >>> hash2 = normalizer.hash("what is sarfaesi?")
            >>> hash1 == hash2  # Same after normalization
            True
            >>> len(hash1)
            64
        """
        normalized = self.normalize(query)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def normalize_and_hash(self, query: str) -> tuple[str, str]:
        """Normalize query and return both normalized form and hash.

        Convenience method that returns both values in one call,
        avoiding duplicate normalization.

        Args:
            query: Original user query.

        Returns:
            Tuple of (normalized_query, query_hash).

        Example:
            >>> normalizer = QueryNormalizer()
            >>> normalized, hash_val = normalizer.normalize_and_hash("What is SARFAESI?")
            >>> normalized
            'what is sarfaesi?'
            >>> len(hash_val)
            64
        """
        normalized = self.normalize(query)
        query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return normalized, query_hash


# Singleton instance for convenience
_query_normalizer: QueryNormalizer | None = None


def get_query_normalizer() -> QueryNormalizer:
    """Get singleton QueryNormalizer instance.

    Returns:
        QueryNormalizer instance.
    """
    global _query_normalizer
    if _query_normalizer is None:
        _query_normalizer = QueryNormalizer()
    return _query_normalizer


def reset_query_normalizer() -> None:
    """Reset singleton (for testing)."""
    global _query_normalizer
    _query_normalizer = None
