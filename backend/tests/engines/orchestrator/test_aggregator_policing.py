"""Tests for aggregator integration with language policing.

Story 8-3: Language Policing Integration (AC #7)

Test Categories:
- Async aggregation with policing
- Policing metadata in result
- Error handling (fail-open)
- Policing disabled scenarios
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.orchestrator.aggregator import (
    ResultAggregator,
)
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    OrchestratorResult,
)
from app.models.safety import LanguagePolicingResult


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.language_policing_enabled = True
    settings.policing_llm_enabled = False  # Regex only for integration tests
    settings.openai_safety_model = "gpt-4o-mini"
    settings.openai_api_key = "test-api-key"
    settings.policing_llm_timeout = 10.0
    return settings


@pytest.fixture
def sample_engine_results() -> list[EngineExecutionResult]:
    """Sample engine results for testing."""
    return [
        EngineExecutionResult(
            engine=EngineType.RAG,
            success=True,
            data={
                "results": [
                    {
                        "document_id": "doc-1",
                        "chunk_id": "chunk-1",
                        "content": "The defendant violated Section 138 of the NI Act.",
                        "relevance_score": 0.95,
                    }
                ],
                "total_candidates": 1,
            },
            execution_time_ms=150,
            confidence=0.9,
        ),
        EngineExecutionResult(
            engine=EngineType.CITATION,
            success=True,
            data={
                "total_acts": 1,
                "total_citations": 3,
                "acts": [
                    {"act_name": "NI Act", "citation_count": 3}
                ],
            },
            execution_time_ms=100,
            confidence=0.95,
        ),
    ]


@pytest.fixture
def aggregator_with_policing(mock_settings):
    """Get aggregator with policing enabled."""
    with patch(
        "app.engines.orchestrator.aggregator.get_settings",
        return_value=mock_settings
    ), patch(
        "app.services.safety.language_police.get_settings",
        return_value=mock_settings
    ):
        return ResultAggregator()


class TestAsyncAggregationWithPolicing:
    """Test async aggregation with language policing."""

    @pytest.mark.asyncio
    async def test_policing_applied_to_unified_response(
        self, aggregator_with_policing, sample_engine_results, mock_settings
    ) -> None:
        """Unified response should be policed during async aggregation."""
        # Mock the language police to return sanitized text
        mock_policing_result = LanguagePolicingResult(
            original_text="The defendant violated Section 138.",
            sanitized_text="The defendant affected by Section 138.",
            replacements_made=[],
            quotes_preserved=[],
            llm_policing_applied=False,
            sanitization_time_ms=2.5,
            llm_cost_usd=0.0,
        )

        with patch(
            "app.engines.orchestrator.aggregator.get_settings",
            return_value=mock_settings
        ), patch.object(
            aggregator_with_policing,
            "_language_police",
            new=MagicMock(
                police_output=AsyncMock(return_value=mock_policing_result)
            ),
        ):
            result = await aggregator_with_policing.aggregate_results_async(
                matter_id="matter-123",
                query="What are the citations?",
                results=sample_engine_results,
                wall_clock_time_ms=200,
            )

            # Check policing was applied
            assert result.policing_metadata.get("policing_applied") is True

    @pytest.mark.asyncio
    async def test_policing_metadata_populated(
        self, aggregator_with_policing, sample_engine_results, mock_settings
    ) -> None:
        """Policing metadata should be populated in result."""
        from app.models.safety import QuotePreservation, ReplacementRecord

        mock_policing_result = LanguagePolicingResult(
            original_text="Original text.",
            sanitized_text="Sanitized text.",
            replacements_made=[
                ReplacementRecord(
                    original_phrase="violated",
                    replacement_phrase="affected by",
                    position_start=0,
                    position_end=8,
                    rule_id="test_rule",
                )
            ],  # 1 replacement
            quotes_preserved=[
                QuotePreservation(
                    quoted_text='"quote 1"',
                    start_pos=10,
                    end_pos=20,
                ),
                QuotePreservation(
                    quoted_text='"quote 2"',
                    start_pos=30,
                    end_pos=40,
                ),
            ],  # 2 quotes
            llm_policing_applied=False,
            sanitization_time_ms=3.5,
            llm_cost_usd=0.0,
        )

        with patch(
            "app.engines.orchestrator.aggregator.get_settings",
            return_value=mock_settings
        ), patch.object(
            aggregator_with_policing,
            "_language_police",
            new=MagicMock(
                police_output=AsyncMock(return_value=mock_policing_result)
            ),
        ):
            result = await aggregator_with_policing.aggregate_results_async(
                matter_id="matter-123",
                query="Test query",
                results=sample_engine_results,
                wall_clock_time_ms=200,
            )

            assert result.policing_metadata["policing_applied"] is True
            assert result.policing_metadata["replacements_count"] == 1
            assert result.policing_metadata["quotes_preserved_count"] == 2
            assert result.policing_metadata["sanitization_time_ms"] > 0


class TestPolicingDisabled:
    """Test behavior when policing is disabled."""

    @pytest.mark.asyncio
    async def test_no_policing_when_disabled(
        self, sample_engine_results
    ) -> None:
        """No policing should occur when disabled."""
        mock_settings = MagicMock()
        mock_settings.language_policing_enabled = False

        with patch(
            "app.engines.orchestrator.aggregator.get_settings",
            return_value=mock_settings
        ):
            aggregator = ResultAggregator()
            result = await aggregator.aggregate_results_async(
                matter_id="matter-123",
                query="Test query",
                results=sample_engine_results,
                wall_clock_time_ms=200,
            )

            # No policing metadata when disabled
            assert result.policing_metadata == {}


class TestSyncVsAsync:
    """Test sync vs async aggregation behavior."""

    def test_sync_aggregation_no_policing(
        self, aggregator_with_policing, sample_engine_results
    ) -> None:
        """Sync aggregation should NOT apply policing."""
        result = aggregator_with_policing.aggregate_results(
            matter_id="matter-123",
            query="Test query",
            results=sample_engine_results,
            wall_clock_time_ms=200,
        )

        # Sync method doesn't apply policing
        assert result.policing_metadata == {}

    @pytest.mark.asyncio
    async def test_async_aggregation_applies_policing(
        self, aggregator_with_policing, sample_engine_results, mock_settings
    ) -> None:
        """Async aggregation should apply policing."""
        mock_policing_result = LanguagePolicingResult(
            original_text="Test",
            sanitized_text="Test",
            replacements_made=[],
            quotes_preserved=[],
            llm_policing_applied=False,
            sanitization_time_ms=1.0,
            llm_cost_usd=0.0,
        )

        with patch(
            "app.engines.orchestrator.aggregator.get_settings",
            return_value=mock_settings
        ), patch.object(
            aggregator_with_policing,
            "_language_police",
            new=MagicMock(
                police_output=AsyncMock(return_value=mock_policing_result)
            ),
        ):
            result = await aggregator_with_policing.aggregate_results_async(
                matter_id="matter-123",
                query="Test query",
                results=sample_engine_results,
                wall_clock_time_ms=200,
            )

            assert result.policing_metadata.get("policing_applied") is True


class TestErrorHandling:
    """Test error handling (fail-open behavior)."""

    @pytest.mark.asyncio
    async def test_policing_error_does_not_block_result(
        self, aggregator_with_policing, sample_engine_results, mock_settings
    ) -> None:
        """Policing errors should not block the result."""
        with patch(
            "app.engines.orchestrator.aggregator.get_settings",
            return_value=mock_settings
        ), patch.object(
            aggregator_with_policing,
            "_language_police",
            new=MagicMock(
                police_output=AsyncMock(side_effect=Exception("LLM error"))
            ),
        ):
            # Should NOT raise - should return result with error metadata
            result = await aggregator_with_policing.aggregate_results_async(
                matter_id="matter-123",
                query="Test query",
                results=sample_engine_results,
                wall_clock_time_ms=200,
            )

            assert result.matter_id == "matter-123"
            assert result.policing_metadata.get("policing_applied") is False
            assert "error" in result.policing_metadata


class TestEmptyResponse:
    """Test handling of empty unified response."""

    @pytest.mark.asyncio
    async def test_empty_response_skips_policing(
        self, aggregator_with_policing, mock_settings
    ) -> None:
        """Empty unified response should skip policing."""
        # All engines failed - empty response
        failed_results = [
            EngineExecutionResult(
                engine=EngineType.RAG,
                success=False,
                error="Test error",
                execution_time_ms=100,
            ),
        ]

        with patch(
            "app.engines.orchestrator.aggregator.get_settings",
            return_value=mock_settings
        ):
            result = await aggregator_with_policing.aggregate_results_async(
                matter_id="matter-123",
                query="Test query",
                results=failed_results,
                wall_clock_time_ms=100,
            )

            # Should have response about failed engines
            assert "error" in result.unified_response.lower()


class TestOrchestratorResultModel:
    """Test OrchestratorResult model fields."""

    def test_policing_metadata_field_exists(self) -> None:
        """OrchestratorResult should have policing_metadata field."""
        result = OrchestratorResult(
            matter_id="test",
            query="test",
        )

        assert hasattr(result, "policing_metadata")
        assert result.policing_metadata == {}

    def test_policing_metadata_accepts_dict(self) -> None:
        """policing_metadata should accept dict values."""
        metadata = {
            "policing_applied": True,
            "replacements_count": 3,
            "quotes_preserved_count": 1,
        }

        result = OrchestratorResult(
            matter_id="test",
            query="test",
            policing_metadata=metadata,
        )

        assert result.policing_metadata == metadata
