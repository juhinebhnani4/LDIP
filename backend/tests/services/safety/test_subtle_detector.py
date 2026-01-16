"""Tests for SubtleViolationDetector.

Story 8-2: GPT-4o-mini Subtle Violation Detection (AC #1-4)

Tests for:
- Implicit conclusion detection (AC #1, #2)
- Contextual rewrite generation (AC #3)
- Safe query handling (AC #4)
- LLM timeout handling
- Cost tracking accuracy
- Mock OpenAI responses

CRITICAL: All tests use mocked OpenAI responses - never hit real API.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.safety.subtle_detector import (
    OpenAIConfigurationError,
    SubtleDetectorError,
    SubtleViolationDetector,
    get_subtle_violation_detector,
    reset_subtle_violation_detector,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings with API key."""
    with patch("app.services.safety.subtle_detector.get_settings") as mock:
        settings = MagicMock()
        settings.openai_api_key = "test-api-key"
        settings.openai_safety_model = "gpt-4o-mini"
        settings.safety_llm_timeout = 10.0
        mock.return_value = settings
        yield mock


@pytest.fixture
def detector(mock_settings):
    """Get fresh detector for testing."""
    reset_subtle_violation_detector()
    return SubtleViolationDetector()


@pytest.fixture
def mock_openai_blocked():
    """Mock OpenAI response for blocked query."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps({
        "is_safe": False,
        "violation_type": "implicit_conclusion_request",
        "explanation": "Query seeks implicit legal conclusion about contract breach",
        "suggested_rewrite": "What evidence exists regarding the defendant's contract performance?",
        "confidence": 0.95,
    })
    response.usage = MagicMock()
    response.usage.prompt_tokens = 150
    response.usage.completion_tokens = 50
    return response


@pytest.fixture
def mock_openai_allowed():
    """Mock OpenAI response for allowed query."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps({
        "is_safe": True,
        "violation_type": None,
        "explanation": "Query seeks factual information from documents",
        "suggested_rewrite": "",
        "confidence": 0.98,
    })
    response.usage = MagicMock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 30
    return response


# =============================================================================
# Story 8-2: Task 8.2-8.4 - Blocked Query Tests (AC #1-2)
# =============================================================================


@pytest.mark.asyncio
class TestImplicitConclusionBlocked:
    """Test GPT-4o-mini blocks implicit conclusion requests.

    Story 8-2: AC #2 - Implicit conclusion requests detected.
    """

    async def test_based_on_evidence_blocked(
        self, detector, mock_openai_blocked
    ) -> None:
        """Should block 'Based on this evidence, is it clear that...'

        Story 8-2: Task 8.2 - Test case
        """
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_blocked
            )

            check = await detector.detect_violation(
                "Based on this evidence, is it clear that the defendant breached the contract?"
            )

            assert check.is_safe is False
            assert check.violation_detected is True
            assert check.violation_type == "implicit_conclusion_request"
            assert len(check.explanation) > 0

    async def test_would_you_say_blocked(
        self, detector, mock_settings
    ) -> None:
        """Should block 'Would you say the defendant is...'

        Story 8-2: Task 8.3 - Test case
        """
        blocked_response = MagicMock()
        blocked_response.choices = [MagicMock()]
        blocked_response.choices[0].message.content = json.dumps({
            "is_safe": False,
            "violation_type": "indirect_outcome_seeking",
            "explanation": "Query directly seeks opinion on liability",
            "suggested_rewrite": "What documents mention damages and their causes?",
            "confidence": 0.98,
        })
        blocked_response.usage = MagicMock()
        blocked_response.usage.prompt_tokens = 150
        blocked_response.usage.completion_tokens = 50

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=blocked_response
            )

            check = await detector.detect_violation(
                "Would you say the defendant is liable for the damages?"
            )

            assert check.is_safe is False
            assert check.violation_type == "indirect_outcome_seeking"

    async def test_does_evidence_support_blocked(
        self, detector, mock_settings
    ) -> None:
        """Should block 'Does the evidence support a finding of...'

        Story 8-2: Task 8.4 - Test case
        """
        blocked_response = MagicMock()
        blocked_response.choices = [MagicMock()]
        blocked_response.choices[0].message.content = json.dumps({
            "is_safe": False,
            "violation_type": "implicit_conclusion_request",
            "explanation": "Query seeks legal conclusion about negligence",
            "suggested_rewrite": "What evidence is documented regarding the incident?",
            "confidence": 0.93,
        })
        blocked_response.usage = MagicMock()
        blocked_response.usage.prompt_tokens = 150
        blocked_response.usage.completion_tokens = 50

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=blocked_response
            )

            check = await detector.detect_violation(
                "Does the evidence support a finding of negligence?"
            )

            assert check.is_safe is False
            assert check.violation_type == "implicit_conclusion_request"


# =============================================================================
# Story 8-2: Task 8.5 - Safe Query Tests (AC #4)
# =============================================================================


@pytest.mark.asyncio
class TestFactualQueryAllowed:
    """Test GPT-4o-mini allows factual queries.

    Story 8-2: AC #4 - Safe queries pass through.
    """

    async def test_what_does_document_say_allowed(
        self, detector, mock_openai_allowed
    ) -> None:
        """Should allow 'What does the document say about...'

        Story 8-2: Task 8.5 - Test case
        """
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_allowed
            )

            check = await detector.detect_violation(
                "What does the document say about the payment terms?"
            )

            assert check.is_safe is True
            assert check.violation_detected is False
            assert check.violation_type is None

    async def test_when_did_event_occur_allowed(
        self, detector, mock_openai_allowed
    ) -> None:
        """Should allow timeline/date questions."""
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_allowed
            )

            check = await detector.detect_violation(
                "When did the incident occur according to the documents?"
            )

            assert check.is_safe is True

    async def test_list_entities_allowed(
        self, detector, mock_openai_allowed
    ) -> None:
        """Should allow entity extraction queries."""
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_allowed
            )

            check = await detector.detect_violation(
                "List all entities mentioned in the complaint"
            )

            assert check.is_safe is True


# =============================================================================
# Story 8-2: Task 8.6 - Contextual Rewrite Tests (AC #3)
# =============================================================================


@pytest.mark.asyncio
class TestContextualRewrite:
    """Test contextual rewrite generation.

    Story 8-2: AC #3 - Contextual rewrite suggested.
    """

    async def test_rewrite_generated_for_blocked(
        self, detector, mock_openai_blocked
    ) -> None:
        """Should generate contextual rewrite for blocked query.

        Story 8-2: Task 8.6 - Test case
        """
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_blocked
            )

            check = await detector.detect_violation(
                "Does the evidence support a finding of negligence?"
            )

            assert check.is_safe is False
            assert len(check.suggested_rewrite) > 0
            # Rewrite should reference evidence (preserving factual intent)
            assert "evidence" in check.suggested_rewrite.lower() or "defendant" in check.suggested_rewrite.lower()

    async def test_no_rewrite_for_allowed(
        self, detector, mock_openai_allowed
    ) -> None:
        """Safe queries should not have rewrites."""
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_allowed
            )

            check = await detector.detect_violation(
                "What does the document say about payment terms?"
            )

            assert check.is_safe is True
            assert check.suggested_rewrite == ""


# =============================================================================
# Story 8-2: Task 8.7-8.8 - Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
class TestTimeoutHandling:
    """Test LLM timeout handling.

    Story 8-2: Task 8.7 - Timeout handling
    """

    async def test_timeout_raises_error(self, detector, mock_settings) -> None:
        """Should raise error on timeout (caller decides fail-open behavior)."""
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=TimeoutError()
            )

            with pytest.raises(SubtleDetectorError):
                await detector.detect_violation("Some query")


@pytest.mark.asyncio
class TestCostTracking:
    """Test LLM cost tracking.

    Story 8-2: Task 8.8 - Cost tracking
    """

    async def test_cost_tracked_for_blocked(
        self, detector, mock_openai_blocked
    ) -> None:
        """Should track LLM cost."""
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_blocked
            )

            check = await detector.detect_violation("Some query")

            # Cost should be calculated based on token usage
            assert check.llm_cost_usd >= 0.0
            # With 150 input + 50 output tokens for GPT-4o-mini
            # Expected: (150/1000 * 0.00015) + (50/1000 * 0.0006) = 0.0000525
            assert check.llm_cost_usd < 0.01  # Should be very low

    async def test_check_time_tracked(
        self, detector, mock_openai_blocked
    ) -> None:
        """Should track check time."""
        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_blocked
            )

            check = await detector.detect_violation("Some query")

            assert check.check_time_ms > 0.0


# =============================================================================
# Story 8-2: Task 8.9 - Mock Response Tests
# =============================================================================


@pytest.mark.asyncio
class TestMockOpenAIResponses:
    """Test with various mocked OpenAI responses.

    Story 8-2: Task 8.9 - Mock all OpenAI responses
    """

    async def test_invalid_json_response(self, detector, mock_settings) -> None:
        """Should handle invalid JSON response."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "not valid json"
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 30

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=response)

            with pytest.raises(SubtleDetectorError):
                await detector.detect_violation("Some query")

    async def test_missing_fields_response(self, detector, mock_settings) -> None:
        """Should handle response with missing fields gracefully."""
        # Response missing violation_type
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps({
            "is_safe": True,
            "explanation": "Query is safe",
            "confidence": 0.9,
        })
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 30

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=response)

            # Should not raise - graceful degradation
            check = await detector.detect_violation("Some query")
            assert check.is_safe is True


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test detector configuration."""

    def test_no_api_key_raises_error(self) -> None:
        """Should raise error if API key not configured."""
        with patch("app.services.safety.subtle_detector.get_settings") as mock:
            settings = MagicMock()
            settings.openai_api_key = ""
            settings.openai_safety_model = "gpt-4o-mini"
            settings.safety_llm_timeout = 10.0
            mock.return_value = settings

            detector = SubtleViolationDetector()

            with pytest.raises(OpenAIConfigurationError):
                _ = detector.client

    def test_model_name_from_settings(self, mock_settings) -> None:
        """Should use model name from settings."""
        detector = SubtleViolationDetector()
        assert detector.model_name == "gpt-4o-mini"


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton factory behavior."""

    def test_singleton_returns_same_instance(self, mock_settings) -> None:
        """get_subtle_violation_detector should return same instance."""
        reset_subtle_violation_detector()

        detector1 = get_subtle_violation_detector()
        detector2 = get_subtle_violation_detector()

        assert detector1 is detector2

    def test_reset_creates_new_instance(self, mock_settings) -> None:
        """reset_subtle_violation_detector should allow new instance creation."""
        detector1 = get_subtle_violation_detector()
        reset_subtle_violation_detector()
        detector2 = get_subtle_violation_detector()

        assert detector1 is not detector2


# =============================================================================
# M2 Fix: Retry Logic Tests
# =============================================================================


@pytest.mark.asyncio
class TestRetryLogic:
    """Test retry logic with exponential backoff.

    M2 Fix: Comprehensive retry logic test coverage.
    """

    async def test_retry_on_rate_limit(self, detector, mock_openai_allowed) -> None:
        """Should retry on 429 rate limit errors."""
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Error 429: Rate limit exceeded")
            return mock_openai_allowed

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = mock_create

            check = await detector.detect_violation("Test query")

            assert check.is_safe is True
            assert call_count == 3  # Retried twice before success

    async def test_retry_on_server_error(self, detector, mock_openai_allowed) -> None:
        """Should retry on 500/502/503/504 server errors."""
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Error 503: Service unavailable")
            return mock_openai_allowed

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = mock_create

            check = await detector.detect_violation("Test query")

            assert check.is_safe is True
            assert call_count == 2

    async def test_max_retries_exceeded(self, detector, mock_settings) -> None:
        """Should raise after MAX_RETRIES attempts."""
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("Error 429: Rate limit exceeded")

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = mock_create

            with pytest.raises(SubtleDetectorError) as exc_info:
                await detector.detect_violation("Test query")

            assert call_count == 3  # MAX_RETRIES
            assert "after 3 attempts" in str(exc_info.value)

    async def test_no_retry_on_non_retryable_error(
        self, detector, mock_settings
    ) -> None:
        """Should not retry on non-retryable errors (e.g., auth errors)."""
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("Invalid API key")

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = mock_create

            with pytest.raises(SubtleDetectorError):
                await detector.detect_violation("Test query")

            # Should fail fast without retrying
            assert call_count == 1

    async def test_retry_timeout_errors(self, detector, mock_openai_allowed) -> None:
        """Should retry on timeout errors."""
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError()
            return mock_openai_allowed

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = mock_create

            check = await detector.detect_violation("Test query")

            assert check.is_safe is True
            assert call_count == 2


# =============================================================================
# H1 Fix: ViolationType Validation Tests
# =============================================================================


@pytest.mark.asyncio
class TestViolationTypeValidation:
    """Test ViolationType validation on LLM responses.

    H1 Fix: Validates that invalid violation types are coerced to None.
    """

    async def test_invalid_violation_type_coerced_to_none(
        self, detector, mock_settings
    ) -> None:
        """Invalid violation_type from LLM should be coerced to None."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps({
            "is_safe": False,
            "violation_type": "unknown_invalid_type",  # Invalid type
            "explanation": "Some explanation",
            "suggested_rewrite": "Safe query here",
            "confidence": 0.9,
        })
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 30

        with patch.object(detector, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=response)

            check = await detector.detect_violation("Test query")

            # Invalid type should be coerced to None
            assert check.violation_type is None

    async def test_valid_violation_types_preserved(
        self, detector, mock_settings
    ) -> None:
        """Valid violation_type values should be preserved."""
        valid_types = [
            "implicit_conclusion_request",
            "indirect_outcome_seeking",
            "hypothetical_legal_advice",
        ]

        for violation_type in valid_types:
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = json.dumps({
                "is_safe": False,
                "violation_type": violation_type,
                "explanation": "Test",
                "suggested_rewrite": "Test",
                "confidence": 0.9,
            })
            response.usage = MagicMock()
            response.usage.prompt_tokens = 100
            response.usage.completion_tokens = 30

            with patch.object(detector, "_client") as mock_client:
                mock_client.chat.completions.create = AsyncMock(return_value=response)

                check = await detector.detect_violation("Test query")

                assert check.violation_type == violation_type


# =============================================================================
# H2 Fix: Input Sanitization Tests
# =============================================================================


class TestInputSanitization:
    """Test input sanitization for prompt injection prevention.

    H2 Fix: Validates query sanitization before LLM call.
    """

    def test_sanitize_triple_quotes(self, mock_settings) -> None:
        """Triple quotes should be replaced."""
        detector = SubtleViolationDetector()
        query = 'Test """injection""" query'
        sanitized = detector._sanitize_query(query)

        assert '"""' not in sanitized
        assert '"injection"' in sanitized

    def test_sanitize_triple_single_quotes(self, mock_settings) -> None:
        """Triple single quotes should be replaced."""
        detector = SubtleViolationDetector()
        query = "Test '''injection''' query"
        sanitized = detector._sanitize_query(query)

        assert "'''" not in sanitized
        assert "'injection'" in sanitized

    def test_truncate_long_query(self, mock_settings) -> None:
        """Excessively long queries should be truncated."""
        detector = SubtleViolationDetector()
        query = "A" * 3000  # Longer than 2000 char limit
        sanitized = detector._sanitize_query(query)

        assert len(sanitized) == 2000

    def test_normal_query_unchanged(self, mock_settings) -> None:
        """Normal queries should pass through unchanged."""
        detector = SubtleViolationDetector()
        query = "What does the document say about payment terms?"
        sanitized = detector._sanitize_query(query)

        assert sanitized == query
