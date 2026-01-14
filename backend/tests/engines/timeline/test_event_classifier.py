"""Tests for Event Classifier service.

Story 4-2: Event Classification
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engines.timeline.event_classifier import (
    ClassifierConfigurationError,
    EventClassifier,
    EventClassifierError,
    get_event_classifier,
)
from app.models.timeline import EventClassificationResult, EventType


class TestEventClassifierInit:
    """Tests for EventClassifier initialization."""

    def test_init_creates_instance(self) -> None:
        """Should create EventClassifier instance."""
        classifier = EventClassifier()
        assert classifier is not None
        assert classifier._model is None  # Lazy initialization

    def test_singleton_factory(self) -> None:
        """Should return singleton from factory."""
        # Clear cache
        get_event_classifier.cache_clear()

        classifier1 = get_event_classifier()
        classifier2 = get_event_classifier()

        assert classifier1 is classifier2

        # Clean up
        get_event_classifier.cache_clear()


class TestEventClassifierParsing:
    """Tests for response parsing logic."""

    def test_parse_valid_single_response(self) -> None:
        """Should parse valid single classification response."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.95,
            "secondary_types": [],
            "keywords_matched": ["filed", "petition"],
            "classification_reasoning": "Clear filing with 'filed' keyword",
        })

        result = classifier._parse_single_response(
            response_text=response_text,
            event_id="event-123",
        )

        assert result.event_id == "event-123"
        assert result.event_type == EventType.FILING
        assert result.classification_confidence == 0.95
        assert "filed" in result.keywords_matched
        assert result.classification_reasoning is not None

    def test_parse_unclassified_response(self) -> None:
        """Should parse unclassified event response."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "unclassified",
            "classification_confidence": 0.4,
            "secondary_types": [
                {"type": "hearing", "confidence": 0.3},
                {"type": "order", "confidence": 0.3},
            ],
            "keywords_matched": [],
            "classification_reasoning": "Insufficient context to classify",
        })

        result = classifier._parse_single_response(
            response_text=response_text,
            event_id="event-456",
        )

        assert result.event_type == EventType.UNCLASSIFIED
        assert result.classification_confidence == 0.4
        assert len(result.secondary_types) == 2

    def test_parse_low_confidence_becomes_unclassified(self) -> None:
        """Should set type to unclassified when confidence is below threshold."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.5,  # Below 0.7 threshold
            "secondary_types": [],
            "keywords_matched": [],
            "classification_reasoning": "Low confidence classification",
        })

        result = classifier._parse_single_response(
            response_text=response_text,
            event_id="event-789",
        )

        # Should be forced to unclassified due to low confidence
        assert result.event_type == EventType.UNCLASSIFIED

    def test_parse_invalid_json(self) -> None:
        """Should handle invalid JSON gracefully."""
        classifier = EventClassifier()
        response_text = "not valid json"

        result = classifier._parse_single_response(
            response_text=response_text,
            event_id="event-123",
        )

        assert result.event_type == EventType.UNCLASSIFIED
        assert result.classification_confidence == 0.0

    def test_parse_markdown_wrapped_json(self) -> None:
        """Should strip markdown code blocks."""
        classifier = EventClassifier()
        response_text = """```json
{
    "event_type": "notice",
    "classification_confidence": 0.85,
    "secondary_types": [],
    "keywords_matched": ["notice", "served"],
    "classification_reasoning": "Notice served"
}
```"""

        result = classifier._parse_single_response(
            response_text=response_text,
            event_id="event-123",
        )

        assert result.event_type == EventType.NOTICE
        assert result.classification_confidence == 0.85

    def test_parse_batch_response(self) -> None:
        """Should parse valid batch classification response."""
        classifier = EventClassifier()
        response_text = json.dumps([
            {
                "event_id": "event-1",
                "event_type": "filing",
                "classification_confidence": 0.95,
                "secondary_types": [],
                "keywords_matched": ["filed"],
                "classification_reasoning": "Clear filing",
            },
            {
                "event_id": "event-2",
                "event_type": "hearing",
                "classification_confidence": 0.88,
                "secondary_types": [],
                "keywords_matched": ["hearing"],
                "classification_reasoning": "Court hearing",
            },
        ])

        events = [
            {"event_id": "event-1"},
            {"event_id": "event-2"},
        ]

        results = classifier._parse_batch_response(
            response_text=response_text,
            events=events,
        )

        assert len(results) == 2
        assert results[0].event_type == EventType.FILING
        assert results[1].event_type == EventType.HEARING


class TestEventTypeClassification:
    """Tests for each event type classification."""

    def test_classify_filing_event(self) -> None:
        """Should classify filing events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.95,
            "secondary_types": [],
            "keywords_matched": ["filed", "petition", "submitted"],
            "classification_reasoning": "Document filed with court",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.FILING

    def test_classify_notice_event(self) -> None:
        """Should classify notice events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "notice",
            "classification_confidence": 0.90,
            "secondary_types": [],
            "keywords_matched": ["notice", "served", "issued"],
            "classification_reasoning": "Legal notice was served",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.NOTICE

    def test_classify_hearing_event(self) -> None:
        """Should classify hearing events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.88,
            "secondary_types": [],
            "keywords_matched": ["hearing", "arguments", "court"],
            "classification_reasoning": "Court hearing scheduled",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.HEARING

    def test_classify_order_event(self) -> None:
        """Should classify order events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "order",
            "classification_confidence": 0.92,
            "secondary_types": [],
            "keywords_matched": ["order", "judgment", "decree"],
            "classification_reasoning": "Court order passed",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.ORDER

    def test_classify_transaction_event(self) -> None:
        """Should classify transaction events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "transaction",
            "classification_confidence": 0.85,
            "secondary_types": [],
            "keywords_matched": ["paid", "payment", "Rs."],
            "classification_reasoning": "Financial transaction",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.TRANSACTION

    def test_classify_document_event(self) -> None:
        """Should classify document events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "document",
            "classification_confidence": 0.80,
            "secondary_types": [],
            "keywords_matched": ["executed", "signed", "agreement"],
            "classification_reasoning": "Document execution",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.DOCUMENT

    def test_classify_deadline_event(self) -> None:
        """Should classify deadline events correctly."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "deadline",
            "classification_confidence": 0.82,
            "secondary_types": [],
            "keywords_matched": ["limitation", "due date", "deadline"],
            "classification_reasoning": "Limitation period deadline",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.DEADLINE


class TestSecondaryTypes:
    """Tests for secondary event type handling."""

    def test_parse_secondary_types(self) -> None:
        """Should parse secondary types with confidence scores."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.75,
            "secondary_types": [
                {"type": "order", "confidence": 0.6},
                {"type": "filing", "confidence": 0.4},
            ],
            "keywords_matched": ["hearing", "order"],
            "classification_reasoning": "Hearing with possible order",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.HEARING
        assert len(result.secondary_types) == 2
        assert result.secondary_types[0].type == EventType.ORDER
        assert result.secondary_types[0].confidence == 0.6

    def test_invalid_secondary_type_ignored(self) -> None:
        """Should ignore invalid secondary types."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.85,
            "secondary_types": [
                {"type": "invalid_type", "confidence": 0.5},
                {"type": "notice", "confidence": 0.4},
            ],
            "keywords_matched": [],
            "classification_reasoning": "Filing event",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        # Invalid type should be filtered out
        assert len(result.secondary_types) == 1
        assert result.secondary_types[0].type == EventType.NOTICE


class TestEmptyContextHandling:
    """Tests for handling empty or missing context."""

    @pytest.mark.asyncio
    async def test_empty_context_returns_unclassified(self) -> None:
        """Should return unclassified for empty context."""
        classifier = EventClassifier()

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="",
            date_text="15/01/2024",
        )

        assert result.event_type == EventType.UNCLASSIFIED
        assert result.classification_confidence == 0.0
        assert "No context" in result.classification_reasoning

    @pytest.mark.asyncio
    async def test_whitespace_context_returns_unclassified(self) -> None:
        """Should return unclassified for whitespace-only context."""
        classifier = EventClassifier()

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="   \n\t   ",
            date_text="15/01/2024",
        )

        assert result.event_type == EventType.UNCLASSIFIED

    def test_sync_empty_context_returns_unclassified(self) -> None:
        """Should return unclassified synchronously for empty context."""
        classifier = EventClassifier()

        result = classifier.classify_event_sync(
            event_id="event-123",
            context_text="",
            date_text="15/01/2024",
        )

        assert result.event_type == EventType.UNCLASSIFIED


class TestClassificationWithMockedGemini:
    """Tests for classification with mocked Gemini."""

    @pytest.mark.asyncio
    async def test_classify_with_mocked_gemini(self) -> None:
        """Should classify event using mocked Gemini response."""
        classifier = EventClassifier()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.95,
            "secondary_types": [],
            "keywords_matched": ["filed", "petition"],
            "classification_reasoning": "Clear filing event",
        })

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        classifier._model = mock_model

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="The petitioner filed this writ petition on",
            date_text="15/01/2024",
        )

        assert result.event_type == EventType.FILING
        assert result.classification_confidence == 0.95

    def test_classify_sync_with_mocked_gemini(self) -> None:
        """Should classify event synchronously."""
        classifier = EventClassifier()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "event_type": "notice",
            "classification_confidence": 0.88,
            "secondary_types": [],
            "keywords_matched": ["notice", "served"],
            "classification_reasoning": "Notice was served",
        })

        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(return_value=mock_response)
        classifier._model = mock_model

        result = classifier.classify_event_sync(
            event_id="event-123",
            context_text="A demand notice was served on",
            date_text="10/02/2024",
        )

        assert result.event_type == EventType.NOTICE

    @pytest.mark.asyncio
    async def test_batch_classify_with_mocked_gemini(self) -> None:
        """Should classify batch of events using mocked Gemini."""
        classifier = EventClassifier()

        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "event_id": "event-1",
                "event_type": "filing",
                "classification_confidence": 0.95,
                "secondary_types": [],
                "keywords_matched": ["filed"],
                "classification_reasoning": "Filing event",
            },
            {
                "event_id": "event-2",
                "event_type": "hearing",
                "classification_confidence": 0.88,
                "secondary_types": [],
                "keywords_matched": ["hearing"],
                "classification_reasoning": "Hearing event",
            },
        ])

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        classifier._model = mock_model

        events = [
            {"event_id": "event-1", "date_text": "15/01/2024", "context": "filed petition"},
            {"event_id": "event-2", "date_text": "20/01/2024", "context": "hearing scheduled"},
        ]

        results = await classifier.classify_events_batch(events)

        assert len(results) == 2
        assert results[0].event_type == EventType.FILING
        assert results[1].event_type == EventType.HEARING


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_api_key(self) -> None:
        """Should raise error when API key is missing."""
        classifier = EventClassifier()
        classifier.api_key = None

        with pytest.raises(ClassifierConfigurationError):
            _ = classifier.model

    def test_invalid_event_type_fallback(self) -> None:
        """Should fall back to unclassified for invalid types."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "invalid_type",
            "classification_confidence": 0.85,
            "secondary_types": [],
            "keywords_matched": [],
            "classification_reasoning": "Unknown type",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.UNCLASSIFIED


class TestRetryLogic:
    """Tests for rate limit retry behavior."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_429(self) -> None:
        """Should retry on 429 rate limit errors."""
        classifier = EventClassifier()

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Resource Exhausted")
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "event_type": "filing",
                "classification_confidence": 0.90,
                "secondary_types": [],
                "keywords_matched": ["filed"],
                "classification_reasoning": "Filing",
            })
            return mock_response

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        classifier._model = mock_model

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="The petition was filed on",
            date_text="15/01/2024",
        )

        assert call_count == 2  # Retried once
        assert result.event_type == EventType.FILING

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self) -> None:
        """Should return unclassified after max retries."""
        classifier = EventClassifier()

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("429 rate limit")

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        classifier._model = mock_model

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="Some context",
            date_text="15/01/2024",
        )

        assert call_count == 3  # MAX_RETRIES = 3
        assert result.event_type == EventType.UNCLASSIFIED

    @pytest.mark.asyncio
    async def test_no_retry_on_non_rate_limit_error(self) -> None:
        """Should not retry on non-rate-limit errors."""
        classifier = EventClassifier()

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("Some other error")

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        classifier._model = mock_model

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="Some context",
            date_text="15/01/2024",
        )

        assert call_count == 1  # No retry
        assert result.event_type == EventType.UNCLASSIFIED


class TestBatchClassification:
    """Tests for batch classification functionality."""

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self) -> None:
        """Should return empty list for empty batch."""
        classifier = EventClassifier()

        results = await classifier.classify_events_batch([])
        assert results == []

    def test_empty_batch_sync_returns_empty(self) -> None:
        """Should return empty list synchronously for empty batch."""
        classifier = EventClassifier()

        results = classifier.classify_events_batch_sync([])
        assert results == []

    @pytest.mark.asyncio
    async def test_large_batch_splits_correctly(self) -> None:
        """Should split large batches into smaller chunks."""
        classifier = EventClassifier()

        call_count = 0
        # Track which event_ids we've processed to return correct count per batch
        processed_events = []

        async def mock_generate(*args, **kwargs):
            nonlocal call_count, processed_events
            call_count += 1
            # Determine batch size from the call - first batch is 20, second is 5
            batch_start = len(processed_events)
            batch_size = 20 if batch_start == 0 else 5

            # Return results for the batch
            mock_response = MagicMock()
            mock_response.text = json.dumps([
                {
                    "event_id": f"event-{batch_start + i}",
                    "event_type": "filing",
                    "classification_confidence": 0.90,
                    "secondary_types": [],
                    "keywords_matched": [],
                    "classification_reasoning": "Filing",
                }
                for i in range(batch_size)
            ])
            processed_events.extend([f"event-{batch_start + i}" for i in range(batch_size)])
            return mock_response

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_generate
        classifier._model = mock_model

        # Create 25 events (should split into batches of 20 and 5)
        events = [
            {"event_id": f"event-{i}", "date_text": "15/01/2024", "context": "filed"}
            for i in range(25)
        ]

        results = await classifier.classify_events_batch(events)

        assert call_count == 2  # Split into 2 batches
        assert len(results) == 25


class TestIndianLegalTerminology:
    """Tests for Indian legal terminology handling."""

    def test_vakalatnama_classification(self) -> None:
        """Should recognize vakalatnama as filing."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.92,
            "secondary_types": [],
            "keywords_matched": ["vakalatnama", "filed"],
            "classification_reasoning": "Vakalatnama (power of attorney for lawyer) filed",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.FILING

    def test_lok_adalat_classification(self) -> None:
        """Should recognize Lok Adalat proceedings."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.88,
            "secondary_types": [{"type": "order", "confidence": 0.6}],
            "keywords_matched": ["Lok Adalat"],
            "classification_reasoning": "Lok Adalat (people's court) proceedings",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.HEARING

    def test_sarfaesi_notice_classification(self) -> None:
        """Should recognize SARFAESI notices."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "notice",
            "classification_confidence": 0.90,
            "secondary_types": [],
            "keywords_matched": ["SARFAESI", "notice"],
            "classification_reasoning": "SARFAESI Act recovery notice",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.NOTICE

    def test_section_138_classification(self) -> None:
        """Should recognize Section 138 (cheque bounce) cases."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.85,
            "secondary_types": [{"type": "notice", "confidence": 0.7}],
            "keywords_matched": ["Section 138", "filed"],
            "classification_reasoning": "Section 138 (cheque bounce) case filed",
        })

        result = classifier._parse_single_response(response_text, "event-1")
        assert result.event_type == EventType.FILING


class TestErrorPaths:
    """Tests for error handling and edge cases."""

    def test_partial_json_response(self) -> None:
        """Should handle truncated JSON gracefully."""
        classifier = EventClassifier()
        # Truncated JSON
        response_text = '{"event_type": "filing", "classification_con'

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.UNCLASSIFIED
        assert result.classification_confidence == 0.0

    def test_empty_response_text(self) -> None:
        """Should handle empty response text."""
        classifier = EventClassifier()
        response_text = ""

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.UNCLASSIFIED

    def test_null_response_fields(self) -> None:
        """Should handle null fields in response."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": None,
            "secondary_types": None,
            "keywords_matched": None,
            "classification_reasoning": None,
        })

        result = classifier._parse_single_response(response_text, "event-1")

        # Should handle gracefully with defaults (1.0 to trust LLM's event_type)
        assert result.event_type == EventType.FILING
        assert result.classification_confidence == 1.0  # Default when not provided

    def test_missing_required_fields(self) -> None:
        """Should handle missing required fields."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "notice",
            # Missing other fields
        })

        result = classifier._parse_single_response(response_text, "event-1")

        # Should still classify if event_type present
        assert result.event_type == EventType.NOTICE

    def test_batch_with_malformed_element(self) -> None:
        """Should handle batch with some malformed elements."""
        classifier = EventClassifier()
        response_text = json.dumps([
            {
                "event_id": "event-1",
                "event_type": "filing",
                "classification_confidence": 0.95,
                "secondary_types": [],
                "keywords_matched": ["filed"],
                "classification_reasoning": "Good result",
            },
            {
                # Malformed - missing event_type
                "event_id": "event-2",
                "classification_confidence": 0.8,
            },
        ])

        events = [
            {"event_id": "event-1"},
            {"event_id": "event-2"},
        ]

        results = classifier._parse_batch_response(response_text, events)

        assert len(results) == 2
        assert results[0].event_type == EventType.FILING
        # Second should fall back gracefully
        assert results[1].event_type == EventType.UNCLASSIFIED

    def test_unicode_in_response(self) -> None:
        """Should handle unicode characters in response."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.9,
            "secondary_types": [],
            "keywords_matched": ["याचिका", "दायर"],  # Hindi: petition, filed
            "classification_reasoning": "Hindi legal terms detected",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.FILING
        assert "याचिका" in result.keywords_matched

    def test_extra_unknown_fields_ignored(self) -> None:
        """Should ignore unknown fields in response."""
        classifier = EventClassifier()
        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.85,
            "secondary_types": [],
            "keywords_matched": [],
            "classification_reasoning": "Hearing",
            "unknown_field": "should be ignored",
            "another_unknown": 12345,
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.HEARING
        assert result.classification_confidence == 0.85

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self) -> None:
        """Should handle network timeouts gracefully."""
        import asyncio

        classifier = EventClassifier()

        async def mock_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("Connection timed out")

        mock_model = MagicMock()
        mock_model.generate_content_async = mock_timeout
        classifier._model = mock_model

        result = await classifier.classify_event(
            event_id="event-123",
            context_text="Some context",
            date_text="15/01/2024",
        )

        # Should return unclassified on timeout
        assert result.event_type == EventType.UNCLASSIFIED

    def test_batch_result_count_mismatch(self) -> None:
        """Should handle when LLM returns fewer results than events."""
        classifier = EventClassifier()
        # Only 1 result for 3 events
        response_text = json.dumps([
            {
                "event_id": "event-1",
                "event_type": "filing",
                "classification_confidence": 0.95,
                "secondary_types": [],
                "keywords_matched": ["filed"],
                "classification_reasoning": "Filing event",
            },
        ])

        events = [
            {"event_id": "event-1"},
            {"event_id": "event-2"},
            {"event_id": "event-3"},
        ]

        results = classifier._parse_batch_response(response_text, events)

        assert len(results) == 3  # Should pad to match events
        assert results[0].event_type == EventType.FILING
        assert results[1].event_type == EventType.UNCLASSIFIED
        assert results[2].event_type == EventType.UNCLASSIFIED
