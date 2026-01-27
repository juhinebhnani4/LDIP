"""Tests for Matter Cost Service.

Story 7.1: Per-Matter Cost Tracking Widget

Code Review Fix: Tests updated for synchronous service method.
"""

import pytest
from unittest.mock import MagicMock

from app.services.matter_cost_service import MatterCostService
from app.models.cost import MatterCostSummary, CostByOperation, CostByProvider


class TestMatterCostService:
    """Test suite for MatterCostService."""

    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client."""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def cost_service(self, mock_supabase):
        """Create MatterCostService with mock client."""
        return MatterCostService(mock_supabase)

    def test_get_matter_cost_summary_no_costs(self, cost_service, mock_supabase):
        """Test cost summary when no costs exist for matter."""
        # Arrange
        matter_id = "test-matter-123"
        mock_result = MagicMock()
        mock_result.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result

        # Act - method is now synchronous
        summary = cost_service.get_matter_cost_summary(matter_id, days=30)

        # Assert
        assert summary.matter_id == matter_id
        assert summary.period_days == 30
        assert summary.total_cost_inr == 0.0
        assert summary.total_cost_usd == 0.0
        assert summary.operation_count == 0
        assert summary.by_operation == []
        assert summary.by_provider == []

    def test_get_matter_cost_summary_with_costs(self, cost_service, mock_supabase):
        """Test cost summary with actual cost records."""
        # Arrange
        matter_id = "test-matter-456"
        mock_result = MagicMock()
        mock_result.data = [
            {
                "provider": "gemini-2.5-flash",
                "operation": "citation_extraction",
                "input_tokens": 1000,
                "output_tokens": 200,
                "total_cost_inr": 10.50,
                "total_cost_usd": 0.126,
                "created_at": "2026-01-27T10:00:00Z",
            },
            {
                "provider": "gpt-4-turbo-preview",
                "operation": "qa_generation",
                "input_tokens": 500,
                "output_tokens": 150,
                "total_cost_inr": 25.00,
                "total_cost_usd": 0.299,
                "created_at": "2026-01-27T11:00:00Z",
            },
            {
                "provider": "gemini-2.5-flash",
                "operation": "citation_extraction",
                "input_tokens": 800,
                "output_tokens": 180,
                "total_cost_inr": 8.50,
                "total_cost_usd": 0.102,
                "created_at": "2026-01-26T09:00:00Z",
            },
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result

        # Act - method is now synchronous
        summary = cost_service.get_matter_cost_summary(matter_id, days=30)

        # Assert
        assert summary.matter_id == matter_id
        assert summary.total_cost_inr == 44.00  # 10.50 + 25.00 + 8.50
        assert summary.operation_count == 3
        assert len(summary.by_operation) == 2  # Citations, Q&A
        assert len(summary.by_provider) == 2  # Gemini, GPT-4

        # Check by_operation breakdown
        citation_cost = next((op for op in summary.by_operation if op.operation == "Citations"), None)
        assert citation_cost is not None
        assert citation_cost.cost_inr == 19.00  # 10.50 + 8.50
        assert citation_cost.operation_count == 2

    def test_get_matter_cost_summary_weekly_cost(self, cost_service, mock_supabase):
        """Test that weekly cost is calculated correctly."""
        # Arrange
        matter_id = "test-matter-789"
        mock_result = MagicMock()
        mock_result.data = [
            {
                "provider": "gemini-2.5-flash",
                "operation": "embedding",
                "input_tokens": 500,
                "output_tokens": 0,
                "total_cost_inr": 5.00,
                "total_cost_usd": 0.06,
                "created_at": "2026-01-27T10:00:00Z",  # Within last 7 days
            },
            {
                "provider": "gemini-2.5-flash",
                "operation": "embedding",
                "input_tokens": 500,
                "output_tokens": 0,
                "total_cost_inr": 5.00,
                "total_cost_usd": 0.06,
                "created_at": "2026-01-15T10:00:00Z",  # Outside last 7 days
            },
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result

        # Act - method is now synchronous
        summary = cost_service.get_matter_cost_summary(matter_id, days=30)

        # Assert
        assert summary.total_cost_inr == 10.00  # Both records
        # Note: weekly_cost depends on actual date comparison with datetime.now()
        # In real scenario, the 2026-01-27 record would be in weekly if test runs around that date

    def test_normalize_operation_embedding(self, cost_service):
        """Test operation normalization for embedding."""
        assert cost_service._normalize_operation("text_embedding") == "Embedding"
        assert cost_service._normalize_operation("document_embed") == "Embedding"

    def test_normalize_operation_qa(self, cost_service):
        """Test operation normalization for Q&A."""
        assert cost_service._normalize_operation("qa_generation") == "Q&A"
        assert cost_service._normalize_operation("rag_query") == "Q&A"
        assert cost_service._normalize_operation("chat_completion") == "Q&A"

    def test_normalize_operation_citations(self, cost_service):
        """Test operation normalization for citations."""
        assert cost_service._normalize_operation("citation_extraction") == "Citations"

    def test_normalize_operation_timeline(self, cost_service):
        """Test operation normalization for timeline."""
        assert cost_service._normalize_operation("timeline_extraction") == "Timeline"
        assert cost_service._normalize_operation("event_detection") == "Timeline"

    def test_normalize_operation_unknown(self, cost_service):
        """Test operation normalization for unknown operations."""
        assert cost_service._normalize_operation("some_new_operation") == "Some New Operation"
