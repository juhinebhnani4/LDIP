"""Tests for Query Normalizer.

Story 7-5: Query Cache Redis Storage
Task 5.1: Unit tests for QueryNormalizer
"""

import pytest

from app.services.memory.query_normalizer import (
    QueryNormalizer,
    get_query_normalizer,
    reset_query_normalizer,
)


@pytest.fixture
def normalizer() -> QueryNormalizer:
    """Create a fresh QueryNormalizer for testing."""
    reset_query_normalizer()
    return QueryNormalizer()


class TestQueryNormalization:
    """Tests for query normalization (Task 5.1)."""

    def test_normalize_lowercase(self, normalizer: QueryNormalizer) -> None:
        """Should convert to lowercase."""
        result = normalizer.normalize("What is SARFAESI?")
        assert result == "what is sarfaesi?"

    def test_normalize_mixed_case(self, normalizer: QueryNormalizer) -> None:
        """Should handle mixed case strings."""
        result = normalizer.normalize("WhAt Is SaRfAeSi?")
        assert result == "what is sarfaesi?"

    def test_normalize_whitespace_collapse(self, normalizer: QueryNormalizer) -> None:
        """Should collapse multiple whitespace to single space."""
        result = normalizer.normalize("what   is    sarfaesi?")
        assert result == "what is sarfaesi?"

    def test_normalize_tab_collapse(self, normalizer: QueryNormalizer) -> None:
        """Should collapse tabs to single space."""
        result = normalizer.normalize("what\tis\t\tsarfaesi?")
        assert result == "what is sarfaesi?"

    def test_normalize_newline_collapse(self, normalizer: QueryNormalizer) -> None:
        """Should collapse newlines to single space."""
        result = normalizer.normalize("what\nis\n\nsarfaesi?")
        assert result == "what is sarfaesi?"

    def test_normalize_mixed_whitespace(self, normalizer: QueryNormalizer) -> None:
        """Should collapse mixed whitespace types."""
        result = normalizer.normalize("what \t\n  is\n\t sarfaesi?")
        assert result == "what is sarfaesi?"

    def test_normalize_trim_leading(self, normalizer: QueryNormalizer) -> None:
        """Should strip leading whitespace."""
        result = normalizer.normalize("   what is sarfaesi?")
        assert result == "what is sarfaesi?"

    def test_normalize_trim_trailing(self, normalizer: QueryNormalizer) -> None:
        """Should strip trailing whitespace."""
        result = normalizer.normalize("what is sarfaesi?   ")
        assert result == "what is sarfaesi?"

    def test_normalize_trim_both(self, normalizer: QueryNormalizer) -> None:
        """Should strip both leading and trailing whitespace."""
        result = normalizer.normalize("   what is sarfaesi?   ")
        assert result == "what is sarfaesi?"

    def test_normalize_punctuation_preserved_question(self, normalizer: QueryNormalizer) -> None:
        """Should preserve question marks."""
        result = normalizer.normalize("what is sarfaesi?")
        assert "?" in result

    def test_normalize_punctuation_preserved_period(self, normalizer: QueryNormalizer) -> None:
        """Should preserve periods."""
        result = normalizer.normalize("Dr. Smith mentioned SARFAESI.")
        assert "." in result

    def test_normalize_punctuation_preserved_comma(self, normalizer: QueryNormalizer) -> None:
        """Should preserve commas."""
        result = normalizer.normalize("banks, lenders, and NBFCs")
        assert "," in result

    def test_normalize_punctuation_preserved_quotes(self, normalizer: QueryNormalizer) -> None:
        """Should preserve quotes for semantic meaning."""
        result = normalizer.normalize("what does 'secured creditor' mean?")
        assert "'" in result

    def test_normalize_punctuation_preserved_hyphen(self, normalizer: QueryNormalizer) -> None:
        """Should preserve hyphens."""
        result = normalizer.normalize("cross-border transactions")
        assert "-" in result

    def test_normalize_special_chars_stripped(self, normalizer: QueryNormalizer) -> None:
        """Should strip special characters like @ # $ % etc."""
        result = normalizer.normalize("what @#$% is sarfaesi?")
        # Special chars removed, spaces collapsed
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result

    def test_normalize_empty_string(self, normalizer: QueryNormalizer) -> None:
        """Should handle empty string."""
        result = normalizer.normalize("")
        assert result == ""

    def test_normalize_only_whitespace(self, normalizer: QueryNormalizer) -> None:
        """Should handle string with only whitespace."""
        result = normalizer.normalize("   \t\n   ")
        assert result == ""


class TestQueryHashing:
    """Tests for query hashing (Task 5.1)."""

    def test_hash_is_sha256(self, normalizer: QueryNormalizer) -> None:
        """Hash should be 64-char hex string (SHA256)."""
        hash_val = normalizer.hash("test query")
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_hash_consistency_same_query(self, normalizer: QueryNormalizer) -> None:
        """Same query should produce same hash."""
        hash1 = normalizer.hash("What is SARFAESI?")
        hash2 = normalizer.hash("What is SARFAESI?")
        assert hash1 == hash2

    def test_hash_consistency_different_case(self, normalizer: QueryNormalizer) -> None:
        """Same query with different case should produce same hash."""
        hash1 = normalizer.hash("What is SARFAESI?")
        hash2 = normalizer.hash("what is sarfaesi?")
        assert hash1 == hash2

    def test_hash_consistency_different_whitespace(self, normalizer: QueryNormalizer) -> None:
        """Same query with different whitespace should produce same hash."""
        hash1 = normalizer.hash("what is sarfaesi?")
        hash2 = normalizer.hash("what   is    sarfaesi?")
        assert hash1 == hash2

    def test_hash_consistency_leading_trailing_space(self, normalizer: QueryNormalizer) -> None:
        """Same query with leading/trailing space should produce same hash."""
        hash1 = normalizer.hash("what is sarfaesi?")
        hash2 = normalizer.hash("  what is sarfaesi?  ")
        assert hash1 == hash2

    def test_hash_different_queries(self, normalizer: QueryNormalizer) -> None:
        """Different queries should produce different hashes."""
        hash1 = normalizer.hash("what is sarfaesi?")
        hash2 = normalizer.hash("who is the defendant?")
        assert hash1 != hash2

    def test_hash_empty_string(self, normalizer: QueryNormalizer) -> None:
        """Empty string should produce valid hash."""
        hash_val = normalizer.hash("")
        assert len(hash_val) == 64

    def test_hash_unicode(self, normalizer: QueryNormalizer) -> None:
        """Should handle unicode characters."""
        hash_val = normalizer.hash("what is सरफेसी?")  # Hindi script
        assert len(hash_val) == 64


class TestNormalizeAndHash:
    """Tests for combined normalize_and_hash method."""

    def test_normalize_and_hash_returns_tuple(self, normalizer: QueryNormalizer) -> None:
        """Should return tuple of (normalized, hash)."""
        result = normalizer.normalize_and_hash("What is SARFAESI?")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_normalize_and_hash_normalized_value(self, normalizer: QueryNormalizer) -> None:
        """Should return correct normalized value."""
        normalized, _ = normalizer.normalize_and_hash("What is SARFAESI?")
        assert normalized == "what is sarfaesi?"

    def test_normalize_and_hash_hash_value(self, normalizer: QueryNormalizer) -> None:
        """Should return valid hash value."""
        _, hash_val = normalizer.normalize_and_hash("What is SARFAESI?")
        assert len(hash_val) == 64

    def test_normalize_and_hash_consistency(self, normalizer: QueryNormalizer) -> None:
        """Combined method should produce same result as separate calls."""
        query = "What is SARFAESI?"
        normalized1, hash1 = normalizer.normalize_and_hash(query)
        normalized2 = normalizer.normalize(query)
        hash2 = normalizer.hash(query)

        assert normalized1 == normalized2
        assert hash1 == hash2


class TestSingletonPattern:
    """Tests for singleton factory pattern."""

    def test_get_query_normalizer_returns_instance(self) -> None:
        """Factory should return QueryNormalizer instance."""
        reset_query_normalizer()
        normalizer = get_query_normalizer()
        assert isinstance(normalizer, QueryNormalizer)

    def test_get_query_normalizer_returns_same_instance(self) -> None:
        """Factory should return same instance on repeated calls."""
        reset_query_normalizer()
        normalizer1 = get_query_normalizer()
        normalizer2 = get_query_normalizer()
        assert normalizer1 is normalizer2

    def test_reset_creates_new_instance(self) -> None:
        """Reset should cause new instance on next call."""
        reset_query_normalizer()
        normalizer1 = get_query_normalizer()
        reset_query_normalizer()
        normalizer2 = get_query_normalizer()
        assert normalizer1 is not normalizer2
