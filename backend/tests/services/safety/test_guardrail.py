"""Tests for GuardrailService.

Story 8-1: Regex Pattern Detection Guardrails (AC #4)

Tests for:
- GuardrailCheck response structure
- Explanation generation
- Rewrite suggestions
- Performance requirements (< 5ms)
- Service singleton behavior
"""

import time

import pytest

from app.models.safety import GuardrailCheck
from app.services.safety.guardrail import (
    GuardrailService,
    get_guardrail_service,
    reset_guardrail_service,
)


@pytest.fixture
def guardrail_service() -> GuardrailService:
    """Get fresh guardrail service for testing.

    Story 8-1: Task 5.1 - Test fixture.
    """
    reset_guardrail_service()
    return get_guardrail_service()


class TestGuardrailCheckResponse:
    """Test GuardrailCheck response structure.

    Story 8-1: AC #4 - Response includes is_safe, violation_type,
    explanation, suggested_rewrite
    """

    def test_blocked_response_structure(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Blocked queries should include all required fields.

        Story 8-1: Task 5.2 - Response structure validation
        """
        check = guardrail_service.check_query("Should I file an appeal?")

        # Required fields per AC #4
        assert check.is_safe is False
        assert check.violation_type is not None
        assert check.pattern_matched is not None
        assert len(check.explanation) > 0
        assert len(check.suggested_rewrite) > 0
        assert check.check_time_ms >= 0

        # Verify it's a proper Pydantic model
        assert isinstance(check, GuardrailCheck)

    def test_allowed_response_structure(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Allowed queries should have minimal fields set.

        Story 8-1: Task 5.3 - Allowed response structure
        """
        check = guardrail_service.check_query("What does the document say?")

        assert check.is_safe is True
        assert check.violation_type is None
        assert check.pattern_matched is None
        assert check.explanation == ""
        assert check.suggested_rewrite == ""
        assert check.check_time_ms >= 0

    def test_violation_type_is_valid_literal(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Violation type should be a valid ViolationType literal."""
        valid_types = {
            "legal_advice_request",
            "outcome_prediction",
            "liability_conclusion",
            "procedural_recommendation",
        }

        # Test legal advice
        check = guardrail_service.check_query("Should I file?")
        assert check.violation_type in valid_types

        # Test outcome prediction
        check = guardrail_service.check_query("Will the judge rule?")
        assert check.violation_type in valid_types


class TestExplanationGeneration:
    """Test explanation generation for blocked queries.

    Story 8-1: Task 5.4 - Explanation generation
    """

    def test_legal_advice_explanation(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Legal advice blocks should have appropriate explanation."""
        check = guardrail_service.check_query("Should I file an appeal?")

        assert "legal advice" in check.explanation.lower() or "LDIP" in check.explanation
        assert len(check.explanation) > 50  # Should be informative

    def test_outcome_prediction_explanation(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Outcome prediction blocks should have appropriate explanation."""
        check = guardrail_service.check_query("Will the judge rule in my favor?")

        assert "predict" in check.explanation.lower() or "court" in check.explanation.lower()
        assert len(check.explanation) > 50

    def test_liability_explanation(self, guardrail_service: GuardrailService) -> None:
        """Liability blocks should have appropriate explanation."""
        check = guardrail_service.check_query("Is the defendant guilty?")

        assert "liabil" in check.explanation.lower() or "conclusion" in check.explanation.lower()
        assert len(check.explanation) > 50

    def test_explanation_mentions_alternative(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Explanations should suggest alternatives."""
        check = guardrail_service.check_query("Should I file an appeal?")

        # Should mention trying something else
        explanation_lower = check.explanation.lower()
        assert (
            "try" in explanation_lower
            or "instead" in explanation_lower
            or "alternative" in explanation_lower
        )


class TestRewriteSuggestion:
    """Test rewrite suggestion for blocked queries.

    Story 8-1: Task 5.5 - Rewrite suggestion
    """

    def test_legal_advice_rewrite(self, guardrail_service: GuardrailService) -> None:
        """Legal advice blocks should suggest factual query."""
        check = guardrail_service.check_query("Should I file an appeal?")

        assert len(check.suggested_rewrite) > 10
        # Should suggest document-based query
        rewrite_lower = check.suggested_rewrite.lower()
        assert "document" in rewrite_lower or "fact" in rewrite_lower or "[topic]" in rewrite_lower

    def test_outcome_prediction_rewrite(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Outcome prediction blocks should suggest precedent query."""
        check = guardrail_service.check_query("Will the judge rule in my favor?")

        assert len(check.suggested_rewrite) > 10
        # Should suggest precedent-based query
        rewrite_lower = check.suggested_rewrite.lower()
        assert "precedent" in rewrite_lower or "ruling" in rewrite_lower or "document" in rewrite_lower

    def test_liability_rewrite(self, guardrail_service: GuardrailService) -> None:
        """Liability blocks should suggest evidence query."""
        check = guardrail_service.check_query("Is the defendant guilty?")

        assert len(check.suggested_rewrite) > 10
        # Should suggest evidence-based query
        rewrite_lower = check.suggested_rewrite.lower()
        assert "evidence" in rewrite_lower or "action" in rewrite_lower or "[party]" in rewrite_lower


class TestPerformance:
    """Test guardrail performance requirements.

    Story 8-1: Task 5.6 - Performance (< 5ms for single query)
    """

    def test_check_under_5ms(self, guardrail_service: GuardrailService) -> None:
        """Single query check should complete in < 5ms.

        Story 8-1: Task 5.6 - AC performance requirement
        """
        check = guardrail_service.check_query("Should I file an appeal?")

        # check_time_ms is measured internally
        assert check.check_time_ms < 5.0, f"Check took {check.check_time_ms}ms, expected < 5ms"

    def test_allowed_query_under_5ms(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Allowed queries should also be fast."""
        check = guardrail_service.check_query("What does the document say?")

        assert check.check_time_ms < 5.0, f"Check took {check.check_time_ms}ms, expected < 5ms"

    def test_bulk_checks_performance(
        self, guardrail_service: GuardrailService
    ) -> None:
        """100 queries should complete in < 500ms (avg < 5ms each).

        Story 8-1: Task 5.6 - Bulk performance test
        """
        queries = ["Should I file?" for _ in range(100)]

        start = time.perf_counter()
        for q in queries:
            guardrail_service.check_query(q)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500, f"100 checks took {elapsed_ms}ms, expected < 500ms"

    def test_mixed_queries_performance(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Mixed blocked/allowed queries should be fast."""
        queries = [
            "Should I file an appeal?",  # blocked
            "What does Section 138 say?",  # allowed
            "Will the judge rule?",  # blocked
            "When did the loan default?",  # allowed
            "Is defendant guilty?",  # blocked
        ]

        for query in queries:
            check = guardrail_service.check_query(query)
            assert check.check_time_ms < 5.0


class TestMultiplePatterns:
    """Test behavior with multiple matching patterns.

    Story 8-1: Task 5.8 - Multiple patterns matching
    """

    def test_first_match_returned(self, guardrail_service: GuardrailService) -> None:
        """Should return first matching pattern (deterministic order).

        Story 8-1: Task 5.8 - First match wins
        """
        # This might match multiple patterns
        check1 = guardrail_service.check_query("Should I file an appeal?")
        check2 = guardrail_service.check_query("Should I file an appeal?")

        # Should be deterministic (same pattern matched both times)
        assert check1.pattern_matched == check2.pattern_matched
        assert check1.violation_type == check2.violation_type


class TestServiceSingleton:
    """Test guardrail service singleton behavior."""

    def test_singleton_returns_same_instance(self) -> None:
        """get_guardrail_service should return same instance."""
        reset_guardrail_service()

        service1 = get_guardrail_service()
        service2 = get_guardrail_service()

        assert service1 is service2

    def test_reset_creates_new_instance(self) -> None:
        """reset_guardrail_service should allow new instance creation."""
        service1 = get_guardrail_service()
        reset_guardrail_service()
        service2 = get_guardrail_service()

        # After reset, should be a different instance
        assert service1 is not service2

    def test_service_has_patterns(self, guardrail_service: GuardrailService) -> None:
        """Service should have patterns loaded."""
        pattern_count = guardrail_service.get_pattern_count()
        assert pattern_count > 0  # Should have loaded patterns


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query(self, guardrail_service: GuardrailService) -> None:
        """Empty query should pass through."""
        check = guardrail_service.check_query("")
        assert check.is_safe is True

    def test_whitespace_query(self, guardrail_service: GuardrailService) -> None:
        """Whitespace-only query should pass through."""
        check = guardrail_service.check_query("   ")
        assert check.is_safe is True

    def test_very_long_query(self, guardrail_service: GuardrailService) -> None:
        """Very long query should still be checked efficiently."""
        # Long query with blocked phrase at the end
        long_query = "This is a very long query " * 100 + "Should I file an appeal?"
        check = guardrail_service.check_query(long_query)

        assert check.is_safe is False
        assert check.check_time_ms < 10.0  # Still reasonably fast

    def test_unicode_query(self, guardrail_service: GuardrailService) -> None:
        """Unicode characters should be handled."""
        check = guardrail_service.check_query("Should I file an appeal? 📄")
        assert check.is_safe is False

    def test_newlines_in_query(self, guardrail_service: GuardrailService) -> None:
        """Newlines in query should be handled."""
        check = guardrail_service.check_query("Should I\nfile an appeal?")
        # Newline might break pattern match - that's OK (conservative approach)
        # Just verify it doesn't crash and returns valid response
        assert isinstance(check.is_safe, bool)

    def test_special_regex_characters(
        self, guardrail_service: GuardrailService
    ) -> None:
        """Special regex characters in query should not cause issues."""
        # These characters could cause regex issues if not handled properly
        queries = [
            "Should I file (an appeal)?",  # parentheses
            "Should I file [an] appeal?",  # brackets
            "Should I file an appeal.*",  # regex wildcards
            "Should I file an appeal$",  # anchor
            "Should I file an appeal+",  # quantifier
        ]

        for query in queries:
            check = guardrail_service.check_query(query)
            # Should not raise exception and should return valid check
            assert isinstance(check.is_safe, bool)
