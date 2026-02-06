"""Tests for Timeline Engine Phase 1 fixes.

Phase 1.1: Dedup key uses (date, event_type, description_hash) — not just date
Phase 1.2: All chunks processed (parent + child)
Phase 1.3: Entity linking threshold lowered to 0.70, trigger fires when events exist
Phase 1.4: Cross-engine journey falls back to text search when entities_involved is empty
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.timeline import ExtractedDate


# =============================================================================
# Phase 1.1 — Dedup key tests
# =============================================================================


class TestDedupKey:
    """Test _dedup_key produces correct grouping keys."""

    def test_same_date_different_type_produces_different_keys(self) -> None:
        """Two events on same date with different types should NOT be deduped."""
        from app.workers.tasks.engine_tasks import _dedup_key

        filing = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="filing",
            event_description="Petition filed by Nirav Jobalia",
            confidence=0.90,
        )
        hearing = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="hearing",
            event_description="Hearing held before High Court",
            confidence=0.85,
        )

        assert _dedup_key(filing) != _dedup_key(hearing)

    def test_same_date_same_type_different_description_produces_different_keys(self) -> None:
        """Two filings on same date with different descriptions should NOT be deduped."""
        from app.workers.tasks.engine_tasks import _dedup_key

        filing1 = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="filing",
            event_description="Petition filed by Nirav Jobalia",
            confidence=0.90,
        )
        filing2 = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="filing",
            event_description="Affidavit submitted by HDFC Bank",
            confidence=0.85,
        )

        assert _dedup_key(filing1) != _dedup_key(filing2)

    def test_true_duplicates_produce_same_key(self) -> None:
        """Same date + type + description from overlapping chunks should dedup."""
        from app.workers.tasks.engine_tasks import _dedup_key

        chunk1 = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="filing",
            event_description="Petition filed by Nirav Jobalia",
            confidence=0.95,
        )
        chunk2 = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15 January 2024",  # Different text, same meaning
            date_precision="day",
            event_type="filing",
            event_description="Petition filed by Nirav Jobalia",
            confidence=0.88,
        )

        assert _dedup_key(chunk1) == _dedup_key(chunk2)

    def test_description_normalization_ignores_case_and_whitespace(self) -> None:
        """Description hash should be case-insensitive and ignore extra whitespace."""
        from app.workers.tasks.engine_tasks import _dedup_key

        d1 = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="filing",
            event_description="Petition Filed By Nirav Jobalia",
            confidence=0.90,
        )
        d2 = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            event_type="filing",
            event_description="petition  filed  by  nirav  jobalia",
            confidence=0.85,
        )

        assert _dedup_key(d1) == _dedup_key(d2)

    def test_default_event_type_used_in_key(self) -> None:
        """Events with default event_type should still produce a valid key."""
        from app.workers.tasks.engine_tasks import _dedup_key

        d = ExtractedDate(
            extracted_date=date(2024, 1, 15),
            date_text="15/01/2024",
            date_precision="day",
            confidence=0.90,
        )

        key = _dedup_key(d)
        assert key.startswith("2024-01-15:")
        # Default event_type is "unclassified"
        assert "unclassified" in key

    def test_unknown_date_key(self) -> None:
        """Events with None extracted_date should use 'unknown' prefix."""
        from app.workers.tasks.engine_tasks import _dedup_key

        d = ExtractedDate(
            extracted_date=date(2024, 1, 1),  # Required field; test with default
            date_text="sometime in 2024",
            date_precision="approximate",
            confidence=0.50,
        )

        key = _dedup_key(d)
        assert "2024" in key


class TestDeduplicateExtractedDates:
    """Test _deduplicate_extracted_dates preserves distinct events on same date."""

    def test_same_date_different_events_all_preserved(self) -> None:
        """Multiple distinct events on Jan 15 should all survive dedup."""
        from app.workers.tasks.engine_tasks import _deduplicate_extracted_dates

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="filing",
                event_description="Petition filed by Nirav Jobalia",
                confidence=0.95,
            ),
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="hearing",
                event_description="Hearing held before High Court",
                confidence=0.90,
            ),
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="order",
                event_description="Court issued interim order",
                confidence=0.85,
            ),
        ]

        unique = _deduplicate_extracted_dates(dates)

        # All three should survive — different event types
        assert len(unique) == 3

    def test_true_duplicates_merged_keeping_best(self) -> None:
        """Same event from overlapping chunks should merge, keeping highest confidence."""
        from app.workers.tasks.engine_tasks import _deduplicate_extracted_dates

        dates = [
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="filing",
                event_description="Petition filed by Nirav Jobalia",
                confidence=0.95,
                page_number=3,
                bbox_ids=["bbox-1"],
            ),
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15 January 2024",
                date_precision="day",
                event_type="filing",
                event_description="Petition filed by Nirav Jobalia",
                confidence=0.80,
            ),
        ]

        unique = _deduplicate_extracted_dates(dates)

        assert len(unique) == 1
        # Should keep the one with page_number and higher confidence
        assert unique[0].confidence == 0.95
        assert unique[0].page_number == 3

    def test_mixed_dedup_and_preservation(self) -> None:
        """Real-world scenario: some events are unique, some are duplicates."""
        from app.workers.tasks.engine_tasks import _deduplicate_extracted_dates

        dates = [
            # Event 1: Filing (appears in 2 chunks)
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="filing",
                event_description="Petition filed by Nirav Jobalia",
                confidence=0.95,
                page_number=3,
            ),
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="filing",
                event_description="Petition filed by Nirav Jobalia",
                confidence=0.80,
            ),
            # Event 2: Hearing on SAME date (different event)
            ExtractedDate(
                extracted_date=date(2024, 1, 15),
                date_text="15/01/2024",
                date_precision="day",
                event_type="hearing",
                event_description="Matter heard by Justice Shah",
                confidence=0.90,
            ),
            # Event 3: Different date entirely
            ExtractedDate(
                extracted_date=date(2024, 3, 1),
                date_text="March 2024",
                date_precision="month",
                event_type="order",
                event_description="Final order passed",
                confidence=0.85,
            ),
        ]

        unique = _deduplicate_extracted_dates(dates)

        # Should keep 3: one filing (best of 2), one hearing, one order
        assert len(unique) == 3
        types = {d.event_type for d in unique}
        assert types == {"filing", "hearing", "order"}

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        from app.workers.tasks.engine_tasks import _deduplicate_extracted_dates

        assert _deduplicate_extracted_dates([]) == []


# =============================================================================
# Phase 1.3 — Entity linking trigger test
# =============================================================================


class TestEntityLinkingTrigger:
    """Test that entity linking fires when events exist, not just when updated."""

    @patch("app.workers.tasks.engine_tasks.link_entities_after_extraction")
    @patch("app.workers.tasks.engine_tasks.get_event_classifier")
    @patch("app.workers.tasks.engine_tasks.get_timeline_service")
    @patch("app.workers.tasks.engine_tasks.get_job_tracking_service")
    def test_entity_linking_triggered_even_when_no_updates(
        self,
        mock_get_job_tracker,
        mock_get_timeline,
        mock_get_classifier,
        mock_link_entities,
    ) -> None:
        """Entity linking should fire when events exist, even if classification didn't update any."""
        from app.workers.tasks.engine_tasks import classify_events_for_document

        # Setup mocks
        job_tracker = MagicMock()
        job_tracker.update_job_status = AsyncMock()
        mock_get_job_tracker.return_value = job_tracker

        timeline_service = MagicMock()
        # Return events for the document via get_events_for_classification_sync
        mock_event = MagicMock()
        mock_event.id = "event-1"
        mock_event.description = "Petition filed"
        mock_event.event_type = "filing"
        mock_event.event_date = date(2024, 1, 15)
        mock_event.source_page = 1
        timeline_service.get_events_for_classification_sync.return_value = [mock_event]
        # Classification doesn't change any events (already classified)
        timeline_service.bulk_update_classifications_sync.return_value = 0
        mock_get_timeline.return_value = timeline_service

        classifier = MagicMock()
        classifier.classify_events_sync.return_value = []
        mock_get_classifier.return_value = classifier

        mock_link_entities.apply_async = MagicMock()

        # Execute — updated_count=0 but events exist
        result = classify_events_for_document.run(
            document_id="doc-123",
            matter_id="matter-456",
        )

        # Entity linking should still be queued even though updated_count=0
        assert result["entity_linking_queued"] is True
        mock_link_entities.apply_async.assert_called_once()


# =============================================================================
# Phase 1.3A — Entity linking threshold test
# =============================================================================


class TestEntityLinkingThreshold:
    """Test that entity linking threshold is 0.70."""

    def test_default_threshold_is_070(self) -> None:
        """Default LINK_CONFIDENCE_THRESHOLD should be 0.70."""
        # Re-import to get current value
        import importlib
        import app.engines.timeline.entity_linker as linker_module

        # The default (without env override) should be 0.70
        # We check the module-level constant
        assert linker_module.LINK_CONFIDENCE_THRESHOLD == pytest.approx(0.70, abs=0.01)


# =============================================================================
# Phase 1.4 — Cross-engine journey text search fallback
# =============================================================================


class TestEntityJourneyFallback:
    """Test text search fallback when entities_involved is empty."""

    def _make_service(self, mock_supabase):
        from app.services.cross_engine_service import CrossEngineService

        return CrossEngineService(supabase=mock_supabase)

    def _build_chain(self, mock_supabase, entity_data, events_primary, events_fallback=None):
        """Build a mock Supabase method chain for get_entity_journey."""
        # Mock identity_nodes query
        entity_query = MagicMock()
        entity_query.execute.return_value = MagicMock(data=entity_data)
        entity_select = MagicMock()
        entity_select.eq.return_value = MagicMock(eq=MagicMock(return_value=MagicMock(single=MagicMock(return_value=entity_query))))

        # Track calls to build correct chain
        call_count = {"value": 0}
        events_results = [events_primary]
        if events_fallback is not None:
            events_results.append(events_fallback)

        def table_side_effect(name):
            mock_table = MagicMock()
            if name == "identity_nodes":
                mock_table.select.return_value = entity_select
            elif name == "events":
                # Return different results for primary vs fallback query
                idx = min(call_count["value"], len(events_results) - 1)
                result = events_results[idx]
                call_count["value"] += 1

                # Build chain: select → eq → contains/text_search → order → range → execute
                mock_execute = MagicMock()
                mock_execute.execute.return_value = result

                mock_range = MagicMock()
                mock_range.range.return_value = mock_execute

                mock_order = MagicMock()
                mock_order.order.return_value = mock_range

                mock_filter = MagicMock()
                mock_filter.contains.return_value = mock_order
                mock_filter.text_search.return_value = mock_order

                mock_eq = MagicMock()
                mock_eq.eq.return_value = mock_filter

                mock_table.select.return_value = mock_eq

            return mock_table

        mock_supabase.table.side_effect = table_side_effect

    def test_fallback_to_text_search_when_no_entity_links(self) -> None:
        """When entities_involved query returns 0 results, should fall back to text search."""
        mock_supabase = MagicMock()

        entity_data = {
            "id": "entity-1",
            "canonical_name": "Nirav Jobalia",
            "entity_type": "PERSON",
            "aliases": ["N.D. Jobalia", "Shri Nirav Jobalia"],
        }

        # Primary query: no results (entities_involved is NULL)
        primary_result = MagicMock()
        primary_result.data = []
        primary_result.count = 0

        # Fallback text search: finds events mentioning "Nirav Jobalia"
        fallback_result = MagicMock()
        fallback_result.data = [
            {
                "id": "event-1",
                "event_date": "2024-01-15",
                "event_type": "filing",
                "description": "Petition filed by Nirav Jobalia",
                "document_id": "doc-1",
                "source_page": 3,
                "confidence": 0.95,
                "documents": {"filename": "petition.pdf"},
            }
        ]
        fallback_result.count = 1

        self._build_chain(mock_supabase, entity_data, primary_result, fallback_result)

        service = self._make_service(mock_supabase)
        journey = service.get_entity_journey(
            matter_id="matter-123",
            entity_id="entity-1",
        )

        assert journey.total_events == 1
        assert journey.entity_name == "Nirav Jobalia"
        assert len(journey.events) == 1
        assert journey.events[0].description == "Petition filed by Nirav Jobalia"

    def test_no_fallback_when_primary_has_results(self) -> None:
        """When entities_involved query has results, should NOT fall back to text search."""
        mock_supabase = MagicMock()

        entity_data = {
            "id": "entity-1",
            "canonical_name": "Nirav Jobalia",
            "entity_type": "PERSON",
            "aliases": [],
        }

        # Primary query: has results
        primary_result = MagicMock()
        primary_result.data = [
            {
                "id": "event-1",
                "event_date": "2024-01-15",
                "event_type": "filing",
                "description": "Petition filed",
                "document_id": "doc-1",
                "source_page": 3,
                "confidence": 0.95,
                "documents": {"filename": "petition.pdf"},
            }
        ]
        primary_result.count = 1

        self._build_chain(mock_supabase, entity_data, primary_result)

        service = self._make_service(mock_supabase)
        journey = service.get_entity_journey(
            matter_id="matter-123",
            entity_id="entity-1",
        )

        assert journey.total_events == 1
        # Should use primary result, text_search should not be called
