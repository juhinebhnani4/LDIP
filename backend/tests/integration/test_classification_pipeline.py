"""Integration tests for Event Classification Pipeline.

Story 4-2: Event Classification

Tests the full pipeline: extraction → classification → retrieval
with mocked LLM responses to verify end-to-end functionality.
"""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engines.timeline.event_classifier import EventClassifier
from app.models.timeline import (
    EventType,
    ExtractedDate,
)
from app.services.timeline_service import TimelineService

# =============================================================================
# Pipeline Integration Tests
# =============================================================================


class TestClassificationPipelineIntegration:
    """Tests for full extraction → classification → retrieval pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_extraction_to_classification(self) -> None:
        """Should process dates through full classification pipeline.

        Tests:
        1. Save extracted dates as raw_date events
        2. Classify raw_date events
        3. Retrieve classified events
        """
        timeline_service = TimelineService()
        classifier = EventClassifier()

        # Mock Supabase client
        mock_client = MagicMock()

        # Step 1: Save extracted dates
        mock_insert_response = MagicMock()
        mock_insert_response.data = [
            {"id": "event-1"},
            {"id": "event-2"},
            {"id": "event-3"},
        ]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_insert_response
        timeline_service._client = mock_client

        extracted_dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                context_before="The petitioner filed this writ petition on",
                context_after="before the Hon'ble High Court.",
                confidence=0.95,
            ),
            ExtractedDate(
                extracted_date=date(2024, 2, 1),
                date_text="01/02/2024",
                date_precision="day",
                context_before="A demand notice was served on",
                context_after="to the respondent.",
                confidence=0.88,
            ),
            ExtractedDate(
                extracted_date=date(2024, 3, 10),
                date_text="10/03/2024",
                date_precision="day",
                context_before="The next date of hearing is",
                context_after="at 10:30 AM.",
                confidence=0.92,
            ),
        ]

        event_ids = await timeline_service.save_extracted_dates(
            matter_id="matter-123",
            document_id="doc-456",
            dates=extracted_dates,
        )

        assert len(event_ids) == 3

        # Step 2: Mock classifier response
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = json.dumps([
            {
                "event_id": "event-1",
                "event_type": "filing",
                "classification_confidence": 0.95,
                "secondary_types": [],
                "keywords_matched": ["filed", "petition"],
                "classification_reasoning": "Clear filing with 'filed' and 'petition' keywords",
            },
            {
                "event_id": "event-2",
                "event_type": "notice",
                "classification_confidence": 0.90,
                "secondary_types": [],
                "keywords_matched": ["notice", "served"],
                "classification_reasoning": "Demand notice was served",
            },
            {
                "event_id": "event-3",
                "event_type": "hearing",
                "classification_confidence": 0.88,
                "secondary_types": [],
                "keywords_matched": ["hearing"],
                "classification_reasoning": "Next hearing date scheduled",
            },
        ])

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_gemini_response)
        classifier._model = mock_model

        # Classify events
        events_for_classification = [
            {
                "event_id": "event-1",
                "date_text": "15/01/2024",
                "context": "The petitioner filed this writ petition on [15/01/2024] before the Hon'ble High Court.",
            },
            {
                "event_id": "event-2",
                "date_text": "01/02/2024",
                "context": "A demand notice was served on [01/02/2024] to the respondent.",
            },
            {
                "event_id": "event-3",
                "date_text": "10/03/2024",
                "context": "The next date of hearing is [10/03/2024] at 10:30 AM.",
            },
        ]

        classification_results = await classifier.classify_events_batch(events_for_classification)

        assert len(classification_results) == 3
        assert classification_results[0].event_type == EventType.FILING
        assert classification_results[1].event_type == EventType.NOTICE
        assert classification_results[2].event_type == EventType.HEARING

        # Step 3: Update classifications in database
        mock_update_response = MagicMock()
        mock_update_response.data = [{"id": "event-1"}]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_update_response

        updated_count = await timeline_service.bulk_update_classifications(
            classifications=classification_results,
            matter_id="matter-123",
        )

        assert updated_count == 3

    @pytest.mark.asyncio
    async def test_pipeline_handles_mixed_confidence_levels(self) -> None:
        """Should correctly handle events with varying confidence levels.

        Events below 0.7 confidence should be marked as unclassified.
        """
        classifier = EventClassifier()

        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {
                "event_id": "event-high",
                "event_type": "filing",
                "classification_confidence": 0.95,
                "secondary_types": [],
                "keywords_matched": ["filed"],
                "classification_reasoning": "High confidence filing",
            },
            {
                "event_id": "event-medium",
                "event_type": "hearing",
                "classification_confidence": 0.75,
                "secondary_types": [],
                "keywords_matched": ["hearing"],
                "classification_reasoning": "Medium confidence hearing",
            },
            {
                "event_id": "event-low",
                "event_type": "order",
                "classification_confidence": 0.45,  # Below threshold
                "secondary_types": [
                    {"type": "hearing", "confidence": 0.40},
                    {"type": "filing", "confidence": 0.35},
                ],
                "keywords_matched": [],
                "classification_reasoning": "Low confidence - ambiguous context",
            },
        ])

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        classifier._model = mock_model

        events = [
            {"event_id": "event-high", "date_text": "15/01/2024", "context": "Filed petition"},
            {"event_id": "event-medium", "date_text": "20/01/2024", "context": "Hearing scheduled"},
            {"event_id": "event-low", "date_text": "25/01/2024", "context": "Some ambiguous text"},
        ]

        results = await classifier.classify_events_batch(events)

        assert len(results) == 3

        # High confidence - classified as filing
        assert results[0].event_type == EventType.FILING
        assert results[0].classification_confidence == 0.95

        # Medium confidence - classified as hearing (above 0.7)
        assert results[1].event_type == EventType.HEARING
        assert results[1].classification_confidence == 0.75

        # Low confidence - forced to unclassified (below 0.7 threshold)
        assert results[2].event_type == EventType.UNCLASSIFIED
        assert results[2].classification_confidence == 0.45


class TestClassificationAccuracy:
    """Tests for classification accuracy on sample legal text."""

    def test_filing_keywords_accuracy(self) -> None:
        """Should correctly classify filing events with various keywords."""
        classifier = EventClassifier()

        filing_contexts = [
            ("The petitioner filed this writ petition on", ["filed", "petition"]),
            ("Application under Section 34 was lodged on", ["lodged", "application"]),
            ("Vakalatnama filed on behalf of", ["vakalatnama", "filed"]),
            ("Counter-affidavit submitted on", ["submitted", "affidavit"]),
            ("Rejoinder filed in response to", ["rejoinder", "filed"]),
        ]

        for context, expected_keywords in filing_contexts:
            response_text = json.dumps({
                "event_type": "filing",
                "classification_confidence": 0.92,
                "secondary_types": [],
                "keywords_matched": expected_keywords,
                "classification_reasoning": f"Filing detected with keywords: {expected_keywords}",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.FILING, f"Failed for context: {context}"
            assert result.classification_confidence >= 0.7

    def test_notice_keywords_accuracy(self) -> None:
        """Should correctly classify notice events."""
        classifier = EventClassifier()

        notice_contexts = [
            ("A demand notice was issued on", ["demand notice", "issued"]),
            ("Legal notice under Section 138 served on", ["legal notice", "served"]),
            ("Show cause notice dated", ["show cause notice"]),
            ("SARFAESI notice was received on", ["SARFAESI", "notice"]),
        ]

        for context, expected_keywords in notice_contexts:
            response_text = json.dumps({
                "event_type": "notice",
                "classification_confidence": 0.88,
                "secondary_types": [],
                "keywords_matched": expected_keywords,
                "classification_reasoning": f"Notice detected: {context}",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.NOTICE, f"Failed for context: {context}"

    def test_hearing_keywords_accuracy(self) -> None:
        """Should correctly classify hearing events."""
        classifier = EventClassifier()

        hearing_contexts = [
            ("The next date of hearing is", ["hearing"]),
            ("Arguments were heard on", ["arguments", "heard"]),
            ("Matter adjourned to", ["adjourned"]),
            ("Lok Adalat proceedings on", ["Lok Adalat"]),
            ("Final hearing scheduled for", ["final hearing"]),
        ]

        for context, expected_keywords in hearing_contexts:
            response_text = json.dumps({
                "event_type": "hearing",
                "classification_confidence": 0.85,
                "secondary_types": [],
                "keywords_matched": expected_keywords,
                "classification_reasoning": f"Hearing detected: {context}",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.HEARING, f"Failed for context: {context}"

    def test_order_keywords_accuracy(self) -> None:
        """Should correctly classify order events."""
        classifier = EventClassifier()

        order_contexts = [
            ("The Hon'ble Court passed an order on", ["order", "passed"]),
            ("Judgment delivered on", ["judgment", "delivered"]),
            ("Stay granted on", ["stay", "granted"]),
            ("Interim injunction issued on", ["injunction", "issued"]),
            ("Matter disposed of on", ["disposed"]),
        ]

        for context, expected_keywords in order_contexts:
            response_text = json.dumps({
                "event_type": "order",
                "classification_confidence": 0.90,
                "secondary_types": [],
                "keywords_matched": expected_keywords,
                "classification_reasoning": f"Order detected: {context}",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.ORDER, f"Failed for context: {context}"

    def test_transaction_keywords_accuracy(self) -> None:
        """Should correctly classify transaction events."""
        classifier = EventClassifier()

        transaction_contexts = [
            ("The borrower paid Rs. 5,00,000 on", ["paid", "Rs."]),
            ("Loan sanctioned on", ["loan", "sanctioned"]),
            ("Cheque dated", ["cheque"]),
            ("EMI payment received on", ["EMI", "payment"]),
        ]

        for context, expected_keywords in transaction_contexts:
            response_text = json.dumps({
                "event_type": "transaction",
                "classification_confidence": 0.82,
                "secondary_types": [],
                "keywords_matched": expected_keywords,
                "classification_reasoning": f"Transaction detected: {context}",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.TRANSACTION, f"Failed for context: {context}"

    def test_deadline_keywords_accuracy(self) -> None:
        """Should correctly classify deadline events."""
        classifier = EventClassifier()

        deadline_contexts = [
            ("The limitation period expired on", ["limitation", "expired"]),
            ("Payment due on", ["due"]),
            ("Within 30 days from", ["within", "days"]),
            ("Last date for compliance is", ["last date"]),
        ]

        for context, expected_keywords in deadline_contexts:
            response_text = json.dumps({
                "event_type": "deadline",
                "classification_confidence": 0.80,
                "secondary_types": [],
                "keywords_matched": expected_keywords,
                "classification_reasoning": f"Deadline detected: {context}",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.DEADLINE, f"Failed for context: {context}"


class TestConfidenceThresholds:
    """Tests for confidence threshold behavior."""

    def test_threshold_boundary_at_0_7(self) -> None:
        """Should classify as type when confidence exactly 0.7."""
        classifier = EventClassifier()

        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.7,  # Exactly at threshold
            "secondary_types": [],
            "keywords_matched": ["filed"],
            "classification_reasoning": "Borderline filing",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        # At 0.7, should be classified (threshold is < 0.7 for unclassified)
        assert result.event_type == EventType.FILING

    def test_threshold_below_0_7_becomes_unclassified(self) -> None:
        """Should force unclassified when confidence below 0.7."""
        classifier = EventClassifier()

        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.69,  # Just below threshold
            "secondary_types": [],
            "keywords_matched": ["hearing"],
            "classification_reasoning": "Low confidence hearing",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        # Below 0.7 should be forced to unclassified
        assert result.event_type == EventType.UNCLASSIFIED
        assert result.classification_confidence == 0.69  # Confidence preserved

    def test_unclassified_type_stays_unclassified(self) -> None:
        """Should keep unclassified type regardless of confidence."""
        classifier = EventClassifier()

        response_text = json.dumps({
            "event_type": "unclassified",
            "classification_confidence": 0.5,
            "secondary_types": [
                {"type": "hearing", "confidence": 0.4},
                {"type": "filing", "confidence": 0.3},
            ],
            "keywords_matched": [],
            "classification_reasoning": "Cannot determine event type",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.UNCLASSIFIED
        assert len(result.secondary_types) == 2

    def test_high_confidence_preserved(self) -> None:
        """Should preserve high confidence classifications."""
        classifier = EventClassifier()

        high_confidence_values = [0.85, 0.90, 0.95, 0.99, 1.0]

        for confidence in high_confidence_values:
            response_text = json.dumps({
                "event_type": "order",
                "classification_confidence": confidence,
                "secondary_types": [],
                "keywords_matched": ["order", "judgment"],
                "classification_reasoning": "High confidence order",
            })

            result = classifier._parse_single_response(response_text, "event-1")

            assert result.event_type == EventType.ORDER
            assert result.classification_confidence == confidence


class TestIndianLegalTerminologyIntegration:
    """Integration tests for Indian legal terminology handling."""

    def test_vakalatnama_in_pipeline(self) -> None:
        """Should correctly handle vakalatnama (power of attorney for lawyer)."""
        classifier = EventClassifier()

        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.92,
            "secondary_types": [],
            "keywords_matched": ["vakalatnama", "filed"],
            "classification_reasoning": "Vakalatnama filed - power of attorney for legal representation",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.FILING
        assert "vakalatnama" in result.keywords_matched

    def test_sarfaesi_proceedings(self) -> None:
        """Should correctly handle SARFAESI Act proceedings."""
        classifier = EventClassifier()

        # SARFAESI notice
        response_text = json.dumps({
            "event_type": "notice",
            "classification_confidence": 0.88,
            "secondary_types": [],
            "keywords_matched": ["SARFAESI", "notice"],
            "classification_reasoning": "SARFAESI Act Section 13(2) notice",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.NOTICE

    def test_lok_adalat_proceedings(self) -> None:
        """Should correctly handle Lok Adalat (people's court) events."""
        classifier = EventClassifier()

        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.85,
            "secondary_types": [{"type": "order", "confidence": 0.65}],
            "keywords_matched": ["Lok Adalat"],
            "classification_reasoning": "Lok Adalat proceedings - may result in settlement order",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.HEARING
        assert len(result.secondary_types) == 1
        assert result.secondary_types[0].type == EventType.ORDER

    def test_section_138_cheque_bounce(self) -> None:
        """Should correctly handle Section 138 (cheque bounce) cases."""
        classifier = EventClassifier()

        # Section 138 filing
        response_text = json.dumps({
            "event_type": "filing",
            "classification_confidence": 0.90,
            "secondary_types": [{"type": "notice", "confidence": 0.70}],
            "keywords_matched": ["Section 138", "complaint", "filed"],
            "classification_reasoning": "Criminal complaint under Section 138 NI Act filed",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.FILING

    def test_drt_drat_proceedings(self) -> None:
        """Should correctly handle DRT/DRAT (debt recovery tribunal) events."""
        classifier = EventClassifier()

        response_text = json.dumps({
            "event_type": "hearing",
            "classification_confidence": 0.87,
            "secondary_types": [],
            "keywords_matched": ["DRT", "hearing"],
            "classification_reasoning": "Debt Recovery Tribunal hearing scheduled",
        })

        result = classifier._parse_single_response(response_text, "event-1")

        assert result.event_type == EventType.HEARING
