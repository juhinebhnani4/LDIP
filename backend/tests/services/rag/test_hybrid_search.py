"""Unit tests for the hybrid search service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag.hybrid_search import (
    HybridSearchResult,
    HybridSearchService,
    HybridSearchServiceError,
    SearchResult,
    SearchWeights,
)


class TestSearchWeights:
    """Tests for SearchWeights dataclass."""

    def test_default_weights(self) -> None:
        """Should have default weights of 1.0."""
        weights = SearchWeights()
        assert weights.bm25 == 1.0
        assert weights.semantic == 1.0

    def test_custom_weights(self) -> None:
        """Should accept custom weights."""
        weights = SearchWeights(bm25=1.5, semantic=0.5)
        assert weights.bm25 == 1.5
        assert weights.semantic == 0.5

    def test_validates_bm25_weight_range(self) -> None:
        """Should raise for bm25 weight outside 0-2 range."""
        with pytest.raises(ValueError, match="bm25 weight must be between"):
            SearchWeights(bm25=-0.1)

        with pytest.raises(ValueError, match="bm25 weight must be between"):
            SearchWeights(bm25=2.1)

    def test_validates_semantic_weight_range(self) -> None:
        """Should raise for semantic weight outside 0-2 range."""
        with pytest.raises(ValueError, match="semantic weight must be between"):
            SearchWeights(semantic=-0.1)

        with pytest.raises(ValueError, match="semantic weight must be between"):
            SearchWeights(semantic=2.1)

    def test_edge_weights(self) -> None:
        """Should accept edge case weights of 0 and 2."""
        weights = SearchWeights(bm25=0.0, semantic=2.0)
        assert weights.bm25 == 0.0
        assert weights.semantic == 2.0


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_creates_result(self) -> None:
        """Should create search result with all fields."""
        result = SearchResult(
            id="chunk-1",
            matter_id="matter-1",
            document_id="doc-1",
            content="Test content",
            page_number=5,
            chunk_type="child",
            token_count=100,
            bm25_rank=3,
            semantic_rank=5,
            rrf_score=0.025,
        )

        assert result.id == "chunk-1"
        assert result.content == "Test content"
        assert result.rrf_score == 0.025

    def test_nullable_ranks(self) -> None:
        """Should allow None for ranks."""
        result = SearchResult(
            id="chunk-1",
            matter_id="matter-1",
            document_id="doc-1",
            content="Test",
            page_number=None,
            chunk_type="parent",
            token_count=50,
            bm25_rank=None,
            semantic_rank=2,
            rrf_score=0.016,
        )

        assert result.bm25_rank is None
        assert result.semantic_rank == 2


class TestHybridSearchServiceInit:
    """Tests for HybridSearchService initialization."""

    @patch("app.services.rag.hybrid_search.get_embedding_service")
    def test_uses_default_embedder(self, mock_get_embedder: MagicMock) -> None:
        """Should use default embedding service if none provided."""
        mock_embedder = MagicMock()
        mock_get_embedder.return_value = mock_embedder

        service = HybridSearchService()

        assert service.embedder is mock_embedder

    def test_uses_provided_embedder(self) -> None:
        """Should use provided embedding service."""
        mock_embedder = MagicMock()

        service = HybridSearchService(embedder=mock_embedder)

        assert service.embedder is mock_embedder


class TestHybridSearchServiceSearch:
    """Tests for hybrid search method."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_executes_hybrid_search(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should execute hybrid search via RPC."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {
                "id": "chunk-1",
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "Test content",
                "page_number": 1,
                "chunk_type": "child",
                "token_count": 100,
                "bm25_rank": 2,
                "semantic_rank": 3,
                "rrf_score": 0.03,
            }
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        mock_validate_results.return_value = mock_rpc_response.data

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query="test query",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
            limit=20,
        )

        assert isinstance(result, HybridSearchResult)
        assert len(result.results) == 1
        assert result.results[0].id == "chunk-1"
        assert result.query == "test query"

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_validates_matter_id(
        self, mock_validate_ns: MagicMock
    ) -> None:
        """Should validate matter_id format."""
        mock_validate_ns.side_effect = ValueError("Invalid matter_id")

        mock_embedder = MagicMock()
        service = HybridSearchService(embedder=mock_embedder)

        with pytest.raises(HybridSearchServiceError) as exc_info:
            await service.search(
                query="test",
                matter_id="invalid",
            )

        assert exc_info.value.code == "INVALID_PARAMETER"

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_raises_when_no_client(
        self,
        mock_validate_ns: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should raise error when database client not configured."""
        mock_get_client.return_value = None

        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        service = HybridSearchService(embedder=mock_embedder)

        with pytest.raises(HybridSearchServiceError) as exc_info:
            await service.search(
                query="test",
                matter_id="550e8400-e29b-41d4-a716-446655440000",
            )

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_returns_empty_results(
        self,
        mock_validate_ns: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should handle empty search results."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = None
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query="no match query",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        assert result.results == []
        assert result.total_candidates == 0

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_uses_custom_weights(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should pass custom weights to RPC."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = []
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        mock_validate_results.return_value = []

        service = HybridSearchService(embedder=mock_embedder)

        custom_weights = SearchWeights(bm25=1.5, semantic=0.5)
        await service.search(
            query="test",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
            weights=custom_weights,
        )

        # Check RPC was called with custom weights
        mock_client.rpc.assert_called_once()
        call_args = mock_client.rpc.call_args[1]
        assert call_args["full_text_weight"] == 1.5
        assert call_args["semantic_weight"] == 0.5


class TestHybridSearchServiceBM25Search:
    """Tests for BM25-only search method."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_executes_bm25_search(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should execute BM25-only search via RPC."""
        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {
                "id": "chunk-1",
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "BM25 result",
                "page_number": 2,
                "chunk_type": "parent",
                "token_count": 150,
                "row_num": 1,
                "rank": 0.5,
            }
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        mock_validate_results.return_value = mock_rpc_response.data

        mock_embedder = MagicMock()
        service = HybridSearchService(embedder=mock_embedder)

        results = await service.bm25_search(
            query="Section 138",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
            limit=30,
        )

        assert len(results) == 1
        assert results[0].bm25_rank == 1
        assert results[0].semantic_rank is None

        # Should have called bm25_search_chunks RPC
        mock_client.rpc.assert_called_once_with(
            "bm25_search_chunks",
            {
                "query_text": "Section 138",
                "filter_matter_id": "550e8400-e29b-41d4-a716-446655440000",
                "match_count": 30,
            },
        )


class TestHybridSearchServiceSemanticSearch:
    """Tests for semantic-only search method."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_executes_semantic_search(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should execute semantic-only search via RPC."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {
                "id": "chunk-1",
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "Semantic result",
                "page_number": 3,
                "chunk_type": "child",
                "token_count": 80,
                "row_num": 1,
                "similarity": 0.95,
            }
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        mock_validate_results.return_value = mock_rpc_response.data

        service = HybridSearchService(embedder=mock_embedder)

        results = await service.semantic_search(
            query="contract breach remedies",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
            limit=30,
        )

        assert len(results) == 1
        assert results[0].semantic_rank == 1
        assert results[0].bm25_rank is None

        # Should have called semantic_search_chunks RPC
        mock_client.rpc.assert_called_once()
        call_args = mock_client.rpc.call_args[0]
        assert call_args[0] == "semantic_search_chunks"


class TestHybridSearchServiceErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_wraps_unexpected_errors(
        self,
        mock_validate_ns: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should wrap unexpected errors in HybridSearchServiceError."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(side_effect=RuntimeError("Unexpected"))

        mock_get_client.return_value = MagicMock()

        service = HybridSearchService(embedder=mock_embedder)

        with pytest.raises(HybridSearchServiceError) as exc_info:
            await service.search(
                query="test",
                matter_id="550e8400-e29b-41d4-a716-446655440000",
            )

        assert exc_info.value.code == "SEARCH_FAILED"
        assert exc_info.value.is_retryable is True
