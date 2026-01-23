"""Tests for maintenance Celery tasks."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.workers.tasks.maintenance_tasks import (
    sync_citation_statuses_with_resolutions,
)


# Patch path for the module where get_service_client is imported inside function
SERVICE_CLIENT_PATCH = "app.services.supabase.client.get_service_client"


def create_mock_client(
    resolutions_data: list[dict] | None = None,
    citations_data: list[dict] | None = None,
    update_data: list[dict] | None = None,
    citation_query_error: Exception | None = None,
) -> MagicMock:
    """Create a mock Supabase client with proper query chain setup."""
    mock_client = MagicMock()

    # Track which table is being accessed
    table_calls = {"act_resolutions": 0, "citations": 0}

    def table_side_effect(table_name: str) -> MagicMock:
        table_calls[table_name] = table_calls.get(table_name, 0) + 1
        mock_table = MagicMock()

        if table_name == "act_resolutions":
            # Chain: select().not_.is_().in_().execute()
            mock_chain = MagicMock()
            mock_table.select.return_value = mock_chain
            mock_chain.not_ = MagicMock()
            mock_chain.not_.is_.return_value = mock_chain
            mock_chain.in_.return_value = mock_chain
            mock_response = MagicMock()
            mock_response.data = resolutions_data or []
            mock_chain.execute.return_value = mock_response

        elif table_name == "citations":
            # Handle both select and update operations
            # Chain for select: select().eq().eq().execute()
            mock_select_chain = MagicMock()
            mock_table.select.return_value = mock_select_chain
            mock_select_chain.eq.return_value = mock_select_chain

            if citation_query_error:
                mock_select_chain.execute.side_effect = citation_query_error
            else:
                mock_select_response = MagicMock()
                mock_select_response.data = citations_data or []
                mock_select_chain.execute.return_value = mock_select_response

            # Chain for update: update().in_().execute()
            mock_update_chain = MagicMock()
            mock_table.update.return_value = mock_update_chain
            mock_update_chain.in_.return_value = mock_update_chain
            mock_update_response = MagicMock()
            mock_update_response.data = update_data or []
            mock_update_chain.execute.return_value = mock_update_response

        return mock_table

    mock_client.table.side_effect = table_side_effect
    return mock_client


class TestSyncCitationStatusesWithResolutions:
    """Tests for sync_citation_statuses_with_resolutions maintenance task."""

    def test_updates_act_unavailable_to_pending_when_act_available(self) -> None:
        """Should update citation status when matching act_resolution has document."""
        # Use TORTS Act which normalizes to special_court_trial_of_offences_relating_to_transactions_in_securities_act_1992
        mock_client = create_mock_client(
            resolutions_data=[
                {
                    "matter_id": "matter-123",
                    "act_name_normalized": "special_court_trial_of_offences_relating_to_transactions_in_securities_act_1992",
                    "act_document_id": "doc-456",
                }
            ],
            citations_data=[
                {"id": "cit-1", "act_name": "TORTS Act"},  # Should match (abbreviation)
                {"id": "cit-2", "act_name": "Companies Act"},  # Should NOT match
            ],
            update_data=[{"id": "cit-1"}],
        )

        with patch(SERVICE_CLIENT_PATCH, return_value=mock_client):
            result = sync_citation_statuses_with_resolutions()

            assert result["matters_checked"] == 1
            assert result["citations_updated"] == 1
            assert result["act_unavailable_to_pending"] == 1
            assert len(result["errors"]) == 0

    def test_handles_case_insensitive_matching(self) -> None:
        """Should match citations regardless of case variations."""
        mock_client = create_mock_client(
            resolutions_data=[
                {
                    "matter_id": "matter-123",
                    "act_name_normalized": "negotiable_instruments_act_1881",
                    "act_document_id": "doc-789",
                }
            ],
            citations_data=[
                {"id": "cit-1", "act_name": "NI Act"},  # Abbreviation
                {"id": "cit-2", "act_name": "NEGOTIABLE INSTRUMENTS ACT, 1881"},
                {"id": "cit-3", "act_name": "negotiable instruments act"},
            ],
            update_data=[{"id": "cit-1"}, {"id": "cit-2"}, {"id": "cit-3"}],
        )

        with patch(SERVICE_CLIENT_PATCH, return_value=mock_client):
            result = sync_citation_statuses_with_resolutions()

            # All 3 citations should be updated
            assert result["citations_updated"] == 3

    def test_skips_matters_with_no_act_unavailable_citations(self) -> None:
        """Should skip matters where all citations already have correct status."""
        mock_client = create_mock_client(
            resolutions_data=[
                {
                    "matter_id": "matter-123",
                    "act_name_normalized": "torts_act",
                    "act_document_id": "doc-456",
                }
            ],
            citations_data=[],  # No citations with act_unavailable status
        )

        with patch(SERVICE_CLIENT_PATCH, return_value=mock_client):
            result = sync_citation_statuses_with_resolutions()

            assert result["matters_checked"] == 1
            assert result["citations_updated"] == 0

    def test_returns_early_when_no_available_resolutions(self) -> None:
        """Should return early when no act_resolutions have documents."""
        mock_client = create_mock_client(resolutions_data=[])

        with patch(SERVICE_CLIENT_PATCH, return_value=mock_client):
            result = sync_citation_statuses_with_resolutions()

            assert result["matters_checked"] == 0
            assert result["citations_updated"] == 0

    def test_handles_database_client_not_configured(self) -> None:
        """Should return error when database client is None."""
        with patch(SERVICE_CLIENT_PATCH, return_value=None):
            result = sync_citation_statuses_with_resolutions()

            assert "error" in result
            assert result["error"] == "Database client not configured"

    def test_continues_on_matter_error(self) -> None:
        """Should continue processing other matters when one fails."""
        # This test needs a more sophisticated mock that fails on first matter
        mock_client = MagicMock()

        # Track calls to determine which matter we're on
        matter_call_count = {"count": 0}

        def table_side_effect(table_name: str) -> MagicMock:
            mock_table = MagicMock()

            if table_name == "act_resolutions":
                mock_chain = MagicMock()
                mock_table.select.return_value = mock_chain
                mock_chain.not_ = MagicMock()
                mock_chain.not_.is_.return_value = mock_chain
                mock_chain.in_.return_value = mock_chain
                mock_response = MagicMock()
                mock_response.data = [
                    {
                        "matter_id": "matter-1",
                        "act_name_normalized": "act_a",
                        "act_document_id": "doc-1",
                    },
                    {
                        "matter_id": "matter-2",
                        "act_name_normalized": "act_b",
                        "act_document_id": "doc-2",
                    },
                ]
                mock_chain.execute.return_value = mock_response

            elif table_name == "citations":
                mock_select_chain = MagicMock()
                mock_table.select.return_value = mock_select_chain
                mock_select_chain.eq.return_value = mock_select_chain

                matter_call_count["count"] += 1
                if matter_call_count["count"] == 1:
                    # First matter fails
                    mock_select_chain.execute.side_effect = Exception("Database error")
                else:
                    # Second matter succeeds
                    mock_select_response = MagicMock()
                    mock_select_response.data = [{"id": "cit-2", "act_name": "Act B"}]
                    mock_select_chain.execute.return_value = mock_select_response
                    mock_select_chain.execute.side_effect = None

                    mock_update_chain = MagicMock()
                    mock_table.update.return_value = mock_update_chain
                    mock_update_chain.in_.return_value = mock_update_chain
                    mock_update_response = MagicMock()
                    mock_update_response.data = [{"id": "cit-2"}]
                    mock_update_chain.execute.return_value = mock_update_response

            return mock_table

        mock_client.table.side_effect = table_side_effect

        with patch(SERVICE_CLIENT_PATCH, return_value=mock_client):
            result = sync_citation_statuses_with_resolutions()

            # Should have processed both matters
            assert result["matters_checked"] == 2
            # One error recorded
            assert len(result["errors"]) == 1
            # Second matter should still have succeeded
            assert result["citations_updated"] == 1
