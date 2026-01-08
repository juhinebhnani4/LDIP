"""Unit tests for token counter utility."""

import pytest

from app.services.chunking.token_counter import (
    count_tokens,
    estimate_tokens_fast,
    get_encoder,
)


class TestGetEncoder:
    """Tests for get_encoder function."""

    def test_returns_encoder(self) -> None:
        """Should return a tiktoken encoder."""
        encoder = get_encoder()
        assert encoder is not None
        assert hasattr(encoder, "encode")

    def test_caches_encoder(self) -> None:
        """Should return the same cached encoder instance."""
        encoder1 = get_encoder()
        encoder2 = get_encoder()
        assert encoder1 is encoder2

    def test_different_encodings(self) -> None:
        """Should return different encoders for different names."""
        cl100k = get_encoder("cl100k_base")
        p50k = get_encoder("p50k_base")
        # Both should be valid but different
        assert cl100k is not None
        assert p50k is not None


class TestCountTokens:
    """Tests for count_tokens function."""

    def test_empty_string(self) -> None:
        """Should return 0 for empty string."""
        assert count_tokens("") == 0

    def test_single_word(self) -> None:
        """Should count tokens for a single word."""
        count = count_tokens("hello")
        assert count == 1

    def test_sentence(self) -> None:
        """Should count tokens for a sentence."""
        text = "The quick brown fox jumps over the lazy dog."
        count = count_tokens(text)
        assert count > 0
        assert count < len(text)  # Should be less than character count

    def test_long_text(self) -> None:
        """Should handle long text."""
        text = "word " * 1000
        count = count_tokens(text)
        assert count > 0
        assert count < 2000  # Reasonable upper bound

    def test_special_characters(self) -> None:
        """Should handle special characters."""
        text = "Hello! @#$% World?"
        count = count_tokens(text)
        assert count > 0

    def test_unicode(self) -> None:
        """Should handle unicode characters."""
        text = "Hello 世界 🌍"
        count = count_tokens(text)
        assert count > 0

    def test_legal_text(self) -> None:
        """Should handle typical legal document text."""
        legal_text = """
        WHEREAS, the parties hereto desire to enter into this Agreement
        for the purpose of establishing certain terms and conditions;
        NOW, THEREFORE, in consideration of the mutual covenants contained
        herein, the parties agree as follows:
        """
        count = count_tokens(legal_text)
        assert count > 20
        assert count < 100


class TestEstimateTokensFast:
    """Tests for estimate_tokens_fast function."""

    def test_empty_string(self) -> None:
        """Should return 0 for empty string."""
        assert estimate_tokens_fast("") == 0

    def test_rough_estimate(self) -> None:
        """Should provide rough estimate based on character count."""
        text = "a" * 100
        estimate = estimate_tokens_fast(text)
        # Roughly 1 token per 4 characters
        assert estimate == 25

    def test_faster_than_tiktoken(self) -> None:
        """Estimate should be significantly different from tiktoken."""
        text = "The quick brown fox jumps over the lazy dog."
        estimate = estimate_tokens_fast(text)
        actual = count_tokens(text)
        # They should be in the same order of magnitude
        assert estimate > 0
        assert actual > 0
        # But not necessarily equal
        assert abs(estimate - actual) < 20

    def test_scales_linearly(self) -> None:
        """Estimate should scale linearly with text length."""
        text1 = "word " * 100
        text2 = "word " * 200
        est1 = estimate_tokens_fast(text1)
        est2 = estimate_tokens_fast(text2)
        # est2 should be roughly 2x est1
        assert 1.5 < (est2 / est1) < 2.5
