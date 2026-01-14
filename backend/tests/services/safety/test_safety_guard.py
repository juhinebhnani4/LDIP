"""Tests for SafetyGuard combined service.

Story 8-2: GPT-4o-mini Subtle Violation Detection (AC #1-4)

Tests for:
- Regex → LLM pipeline (regex blocks first)
- Regex pass → LLM check flow
- Combined SafetyCheckResult structure
- Feature flag disabling LLM check
- LLM failure fail-open behavior

CRITICAL: All tests use mocked OpenAI responses - never hit real API.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.safety import SafetyCheckResult
from app.services.safety.guardrail import GuardrailService
from app.services.safety.safety_guard import (
    SafetyGuard,
    get_safety_guard,
    reset_safety_guard,
)
from app.services.safety.subtle_detector import SubtleViolationDetector


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings with LLM enabled."""
    with patch("app.services.safety.safety_guard.get_settings") as mock:
        settings = MagicMock()
        settings.safety_llm_enabled = True
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_settings_llm_disabled():
    """Mock settings with LLM disabled."""
    with patch("app.services.safety.safety_guard.get_settings") as mock:
        settings = MagicMock()
        settings.safety_llm_enabled = False
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_guardrail():
    """Mock guardrail service for testing."""
    guardrail = MagicMock(spec=GuardrailService)
    return guardrail


@pytest.fixture
def mock_subtle_detector():
    """Mock subtle detector for testing."""
    detector = MagicMock(spec=SubtleViolationDetector)
    return detector


@pytest.fixture
def safety_guard(mock_settings, mock_guardrail, mock_subtle_detector):
    """Get SafetyGuard with mocked dependencies."""
    return SafetyGuard(
        guardrail_service=mock_guardrail,
        subtle_detector=mock_subtle_detector,
    )


# =============================================================================
# Story 8-2: Task 9.2 - Regex Blocks First Tests
# =============================================================================


@pytest.mark.asyncio
class TestRegexBlocksFirst:
    """Test that regex violations block before LLM is called.

    Story 8-2: Task 9.2 - Regex → LLM pipeline
    """

    async def test_regex_blocks_without_llm_call(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """Regex violations should block before LLM is called."""
        # Configure guardrail to block
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=False,
            violation_type="legal_advice_request",
            pattern_matched="legal_advice_should_i",
            explanation="This query seeks legal advice...",
            suggested_rewrite="What does the document say about...",
            check_time_ms=2.5,
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query("Should I file an appeal?")

        # Should be blocked by regex
        assert result.is_safe is False
        assert result.blocked_by == "regex"
        assert result.violation_type == "legal_advice_request"

        # LLM should NOT have been called
        mock_subtle_detector.detect_violation.assert_not_called()

    async def test_regex_check_time_recorded(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """Regex check time should be recorded."""
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=False,
            violation_type="legal_advice_request",
            pattern_matched="test",
            explanation="Test",
            suggested_rewrite="Test",
            check_time_ms=3.5,
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query("Should I file?")

        assert result.regex_check_ms == 3.5
        assert result.llm_check_ms == 0.0  # LLM not called


# =============================================================================
# Story 8-2: Task 9.3 - Regex Pass → LLM Check Tests
# =============================================================================


@pytest.mark.asyncio
class TestRegexPassLLMCheck:
    """Test LLM check when regex passes.

    Story 8-2: Task 9.3 - Regex pass → LLM check flow
    """

    async def test_llm_called_after_regex_pass(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """LLM should be called when regex passes."""
        # Configure guardrail to pass
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=True,
            violation_type=None,
            pattern_matched=None,
            explanation="",
            suggested_rewrite="",
            check_time_ms=2.0,
        )

        # Configure LLM to block
        mock_subtle_detector.detect_violation = AsyncMock(
            return_value=MagicMock(
                is_safe=False,
                violation_detected=True,
                violation_type="implicit_conclusion_request",
                explanation="Query seeks implicit conclusion...",
                suggested_rewrite="What evidence exists...",
                confidence=0.95,
                llm_cost_usd=0.0003,
                check_time_ms=850.0,
            )
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query(
            "Based on this evidence, is it clear that..."
        )

        # Should be blocked by LLM
        assert result.is_safe is False
        assert result.blocked_by == "llm"
        assert result.violation_type == "implicit_conclusion_request"

        # LLM should have been called
        mock_subtle_detector.detect_violation.assert_called_once()

    async def test_safe_query_passes_both(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """Safe queries should pass both checks."""
        # Configure guardrail to pass
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=True,
            violation_type=None,
            pattern_matched=None,
            explanation="",
            suggested_rewrite="",
            check_time_ms=2.0,
        )

        # Configure LLM to pass
        mock_subtle_detector.detect_violation = AsyncMock(
            return_value=MagicMock(
                is_safe=True,
                violation_detected=False,
                violation_type=None,
                explanation="Query seeks factual information",
                suggested_rewrite="",
                confidence=0.98,
                llm_cost_usd=0.0002,
                check_time_ms=500.0,
            )
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query(
            "What does Section 138 of NI Act say?"
        )

        # Should pass both checks
        assert result.is_safe is True
        assert result.blocked_by is None
        assert result.regex_check_ms > 0
        assert result.llm_check_ms > 0
        assert result.llm_cost_usd > 0


# =============================================================================
# Story 8-2: Task 9.4 - SafetyCheckResult Structure Tests
# =============================================================================


@pytest.mark.asyncio
class TestSafetyCheckResultStructure:
    """Test SafetyCheckResult has all required fields.

    Story 8-2: Task 9.4 - Combined result structure
    """

    async def test_blocked_result_has_all_fields(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """Blocked result should have all required fields."""
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=False,
            violation_type="legal_advice_request",
            pattern_matched="test",
            explanation="Test explanation",
            suggested_rewrite="Test rewrite",
            check_time_ms=2.5,
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query("Should I file?")

        # Verify all fields
        assert isinstance(result, SafetyCheckResult)
        assert hasattr(result, "is_safe")
        assert hasattr(result, "blocked_by")
        assert hasattr(result, "violation_type")
        assert hasattr(result, "explanation")
        assert hasattr(result, "suggested_rewrite")
        assert hasattr(result, "regex_check_ms")
        assert hasattr(result, "llm_check_ms")
        assert hasattr(result, "llm_cost_usd")
        assert hasattr(result, "llm_check_failed")

    async def test_safe_result_has_all_fields(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """Safe result should have all required fields."""
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=True,
            violation_type=None,
            pattern_matched=None,
            explanation="",
            suggested_rewrite="",
            check_time_ms=2.0,
        )

        mock_subtle_detector.detect_violation = AsyncMock(
            return_value=MagicMock(
                is_safe=True,
                violation_detected=False,
                violation_type=None,
                explanation="",
                suggested_rewrite="",
                confidence=0.98,
                llm_cost_usd=0.0002,
                check_time_ms=500.0,
            )
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query("What documents exist?")

        assert result.is_safe is True
        assert result.blocked_by is None
        assert result.llm_check_failed is False


# =============================================================================
# Story 8-2: Task 9.5 - Feature Flag Tests
# =============================================================================


@pytest.mark.asyncio
class TestFeatureFlag:
    """Test LLM check feature flag.

    Story 8-2: Task 9.5 - Feature flag disabling LLM check
    """

    async def test_llm_disabled_skips_llm_check(
        self, mock_settings_llm_disabled, mock_guardrail, mock_subtle_detector
    ) -> None:
        """LLM check should be skipped when disabled."""
        # Configure guardrail to pass
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=True,
            violation_type=None,
            pattern_matched=None,
            explanation="",
            suggested_rewrite="",
            check_time_ms=2.0,
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query(
            "Based on this evidence, is it clear that..."
        )

        # Should pass (LLM disabled)
        assert result.is_safe is True
        assert result.blocked_by is None
        assert result.llm_check_ms == 0.0

        # LLM should NOT have been called
        mock_subtle_detector.detect_violation.assert_not_called()


# =============================================================================
# LLM Failure Tests
# =============================================================================


@pytest.mark.asyncio
class TestLLMFailure:
    """Test LLM failure handling (fail open).

    Story 8-2: Security requirement - fail open
    """

    async def test_llm_failure_fails_open(
        self, mock_settings, mock_guardrail, mock_subtle_detector
    ) -> None:
        """LLM failures should allow query (fail open)."""
        # Configure guardrail to pass
        mock_guardrail.check_query.return_value = MagicMock(
            is_safe=True,
            violation_type=None,
            pattern_matched=None,
            explanation="",
            suggested_rewrite="",
            check_time_ms=2.0,
        )

        # Configure LLM to fail
        mock_subtle_detector.detect_violation = AsyncMock(
            side_effect=Exception("LLM Error")
        )

        safety_guard = SafetyGuard(
            guardrail_service=mock_guardrail,
            subtle_detector=mock_subtle_detector,
        )

        result = await safety_guard.check_query("Some query")

        # Should pass (fail open)
        assert result.is_safe is True
        assert result.blocked_by is None
        assert result.llm_check_failed is True


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton factory behavior."""

    def test_singleton_returns_same_instance(self, mock_settings) -> None:
        """get_safety_guard should return same instance."""
        reset_safety_guard()

        with patch("app.services.safety.safety_guard.get_guardrail_service"):
            with patch("app.services.safety.safety_guard.get_subtle_violation_detector"):
                guard1 = get_safety_guard()
                guard2 = get_safety_guard()

                assert guard1 is guard2

    def test_reset_creates_new_instance(self, mock_settings) -> None:
        """reset_safety_guard should allow new instance creation."""
        with patch("app.services.safety.safety_guard.get_guardrail_service"):
            with patch("app.services.safety.safety_guard.get_subtle_violation_detector"):
                guard1 = get_safety_guard()
                reset_safety_guard()
                guard2 = get_safety_guard()

                assert guard1 is not guard2
