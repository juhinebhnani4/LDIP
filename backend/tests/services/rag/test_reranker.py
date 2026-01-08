"""Unit tests for the Cohere Rerank service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag.reranker import (
    CohereRerankService,
    CohereRerankServiceError,
    RerankResult,
    RerankResultItem,
    RERANK_MODEL,
    DEFAULT_TOP_N,
    RERANK_TIMEOUT_SECONDS,
    get_cohere_rerank_service,
)


class TestRerankResultItem:
    """Tests for RerankResultItem dataclass."""

    def test_creates_result_item(self) -> None:
        """Should create rerank result item with all fields."""
        item = RerankResultItem(
            index=2,
            relevance_score=0.987,
        )

        assert item.index == 2
        assert item.relevance_score == 0.987


class TestRerankResult:
    """Tests for RerankResult dataclass."""

    def test_creates_result(self) -> None:
        """Should create rerank result with all fields."""
        items = [
            RerankResultItem(index=2, relevance_score=0.95),
            RerankResultItem(index=0, relevance_score=0.82),
        ]
        result = RerankResult(
            results=items,
            query="contract termination",
            model="rerank-v3.5",
            rerank_used=True,
            fallback_reason=None,
        )

        assert len(result.results) == 2
        assert result.query == "contract termination"
        assert result.model == "rerank-v3.5"
        assert result.rerank_used is True
        assert result.fallback_reason is None

    def test_creates_fallback_result(self) -> None:
        """Should create fallback result when reranking fails."""
        result = RerankResult(
            results=[],
            query="test",
            model="rerank-v3.5",
            rerank_used=False,
            fallback_reason="Cohere API timeout after 10s",
        )

        assert result.rerank_used is False
        assert result.fallback_reason == "Cohere API timeout after 10s"


class TestCohereRerankServiceError:
    """Tests for CohereRerankServiceError exception."""

    def test_creates_error_with_defaults(self) -> None:
        """Should create error with default values."""
        error = CohereRerankServiceError(message="Test error")

        assert error.message == "Test error"
        assert error.code == "RERANK_ERROR"
        assert error.is_retryable is True

    def test_creates_error_with_custom_values(self) -> None:
        """Should create error with custom values."""
        error = CohereRerankServiceError(
            message="API key not configured",
            code="COHERE_NOT_CONFIGURED",
            is_retryable=False,
        )

        assert error.message == "API key not configured"
        assert error.code == "COHERE_NOT_CONFIGURED"
        assert error.is_retryable is False


class TestCohereRerankServiceInit:
    """Tests for CohereRerankService initialization."""

    @patch("app.services.rag.reranker.get_settings")
    def test_lazy_client_initialization(self, mock_get_settings: MagicMock) -> None:
        """Should not create client on init (lazy initialization)."""
        mock_settings = MagicMock()
        mock_settings.cohere_api_key = "test-key"
        mock_get_settings.return_value = mock_settings

        service = CohereRerankService()

        # Client should not be created yet
        assert service._client is None

    @patch("app.services.rag.reranker.get_settings")
    def test_raises_on_missing_api_key(self, mock_get_settings: MagicMock) -> None:
        """Should raise error when API key is not configured."""
        mock_settings = MagicMock()
        mock_settings.cohere_api_key = ""
        mock_get_settings.return_value = mock_settings

        service = CohereRerankService()

        with pytest.raises(CohereRerankServiceError) as exc_info:
            _ = service.client

        assert exc_info.value.code == "COHERE_NOT_CONFIGURED"
        assert exc_info.value.is_retryable is False


class TestCohereRerankServiceRerank:
    """Tests for the rerank method."""

    @pytest.mark.asyncio
    async def test_rerank_returns_sorted_results(self) -> None:
        """Test rerank returns results sorted by relevance_score."""
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=2, relevance_score=0.95),
            MagicMock(index=0, relevance_score=0.82),
            MagicMock(index=1, relevance_score=0.65),
        ]

        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            service = CohereRerankService()
            mock_client = MagicMock()
            mock_client.rerank.return_value = mock_response
            service._client = mock_client

            result = await service.rerank(
                query="contract termination",
                documents=["doc1", "doc2", "doc3"],
                top_n=3,
            )

        assert result.rerank_used is True
        assert len(result.results) == 3
        # First result should have highest score (original index 2)
        assert result.results[0].index == 2
        assert result.results[0].relevance_score == 0.95
        assert result.model == RERANK_MODEL

    @pytest.mark.asyncio
    async def test_rerank_empty_documents_returns_empty(self) -> None:
        """Test rerank with empty documents returns empty result."""
        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            service = CohereRerankService()

            result = await service.rerank(
                query="test",
                documents=[],
                top_n=3,
            )

        assert result.results == []
        assert result.rerank_used is True
        assert result.fallback_reason is None

    @pytest.mark.asyncio
    async def test_rerank_limits_top_n_to_doc_count(self) -> None:
        """Test rerank limits top_n to document count."""
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=0, relevance_score=0.9),
            MagicMock(index=1, relevance_score=0.8),
        ]

        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            service = CohereRerankService()
            mock_client = MagicMock()
            mock_client.rerank.return_value = mock_response
            service._client = mock_client

            # Request top_n=10 but only 2 documents
            result = await service.rerank(
                query="test",
                documents=["doc1", "doc2"],
                top_n=10,
            )

        # Should only return 2 results
        assert len(result.results) == 2

        # Verify rerank was called with min(top_n, doc_count)
        mock_client.rerank.assert_called_once()
        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["top_n"] == 2

    @pytest.mark.asyncio
    async def test_rerank_handles_cohere_error(self) -> None:
        """Test rerank raises CohereRerankServiceError on API error."""
        import cohere

        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            service = CohereRerankService()
            mock_client = MagicMock()
            mock_client.rerank.side_effect = cohere.CohereError("API error")
            service._client = mock_client

            with pytest.raises(CohereRerankServiceError) as exc_info:
                await service.rerank(
                    query="test",
                    documents=["doc1", "doc2"],
                    top_n=3,
                )

            assert exc_info.value.code == "COHERE_API_ERROR"
            assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_rerank_handles_timeout(self) -> None:
        """Test rerank raises CohereRerankServiceError on internal timeout.

        This tests the service's internal RERANK_TIMEOUT_SECONDS timeout,
        not an external asyncio.wait_for timeout.
        """
        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            # Patch the timeout to a very short value for testing
            with patch("app.services.rag.reranker.RERANK_TIMEOUT_SECONDS", 0.01):
                service = CohereRerankService()

                # Create a mock that sleeps longer than our patched timeout
                def slow_rerank(*args, **kwargs):
                    import time
                    time.sleep(0.1)  # Longer than patched 0.01s timeout
                    return MagicMock()

                mock_client = MagicMock()
                mock_client.rerank.side_effect = slow_rerank
                service._client = mock_client

                with pytest.raises(CohereRerankServiceError) as exc_info:
                    await service.rerank(
                        query="test",
                        documents=["doc1"],
                        top_n=1,
                    )

                # Verify error is from service's internal timeout handling
                assert exc_info.value.code == "COHERE_TIMEOUT"
                assert "timeout" in exc_info.value.message.lower()
                assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_rerank_uses_correct_model(self) -> None:
        """Test rerank uses the correct Cohere model."""
        mock_response = MagicMock()
        mock_response.results = []

        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            service = CohereRerankService()
            mock_client = MagicMock()
            mock_client.rerank.return_value = mock_response
            service._client = mock_client

            await service.rerank(
                query="test",
                documents=["doc1"],
                top_n=1,
            )

        # Verify model parameter
        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["model"] == "rerank-v3.5"
        assert call_kwargs["return_documents"] is False


class TestGetCohereRerankService:
    """Tests for the service factory function."""

    def test_returns_singleton(self) -> None:
        """Should return same instance on multiple calls."""
        # Reset the global instance for testing
        import app.services.rag.reranker as reranker_module
        reranker_module._rerank_service_instance = None

        with patch("app.services.rag.reranker.get_settings") as mock_settings:
            mock_settings.return_value.cohere_api_key = "test-key"

            service1 = get_cohere_rerank_service()
            service2 = get_cohere_rerank_service()

            assert service1 is service2

        # Clean up
        reranker_module._rerank_service_instance = None


class TestConstants:
    """Tests for module constants."""

    def test_rerank_model_is_latest(self) -> None:
        """Verify the correct Cohere model is used."""
        assert RERANK_MODEL == "rerank-v3.5"

    def test_default_top_n(self) -> None:
        """Verify default top_n is 3."""
        assert DEFAULT_TOP_N == 3

    def test_timeout_is_reasonable(self) -> None:
        """Verify timeout is set appropriately."""
        assert RERANK_TIMEOUT_SECONDS == 10
