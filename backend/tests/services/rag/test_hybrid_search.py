"""Unit tests for the hybrid search service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag.hybrid_search import (
    HybridSearchResult,
    HybridSearchService,
    HybridSearchServiceError,
    RerankedSearchResult,
    RerankedSearchResultItem,
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
            bbox_ids=["bbox-1", "bbox-2"],
            chunk_type="child",
            token_count=100,
            bm25_rank=3,
            semantic_rank=5,
            rrf_score=0.025,
        )

        assert result.id == "chunk-1"
        assert result.content == "Test content"
        assert result.rrf_score == 0.025
        assert result.bbox_ids == ["bbox-1", "bbox-2"]

    def test_nullable_ranks(self) -> None:
        """Should allow None for ranks and bbox_ids."""
        result = SearchResult(
            id="chunk-1",
            matter_id="matter-1",
            document_id="doc-1",
            content="Test",
            page_number=None,
            bbox_ids=None,
            chunk_type="parent",
            token_count=50,
            bm25_rank=None,
            semantic_rank=2,
            rrf_score=0.016,
        )

        assert result.bm25_rank is None
        assert result.semantic_rank == 2
        assert result.bbox_ids is None


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
        # RPC is called as rpc("function_name", {params_dict})
        rpc_params = mock_client.rpc.call_args[0][1]  # Second positional arg
        assert rpc_params["full_text_weight"] == 1.5
        assert rpc_params["semantic_weight"] == 0.5


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


class TestRRFScoreCalculation:
    """Tests for Reciprocal Rank Fusion (RRF) score calculation.

    RRF formula: score = sum(1 / (k + rank)) * weight for each ranking
    Where k is the smoothing constant (default 60) and rank is 1-indexed.
    """

    def test_rrf_formula_with_both_ranks(self) -> None:
        """Verify RRF calculation when result appears in both BM25 and semantic."""
        # Given: k=60, bm25_rank=1, semantic_rank=2, weights=1.0 each
        k = 60
        bm25_rank = 1
        semantic_rank = 2
        bm25_weight = 1.0
        semantic_weight = 1.0

        # Formula: 1/(k+bm25_rank)*bm25_weight + 1/(k+semantic_rank)*semantic_weight
        expected_score = (
            1.0 / (k + bm25_rank) * bm25_weight +
            1.0 / (k + semantic_rank) * semantic_weight
        )

        # Expected: 1/61 * 1.0 + 1/62 * 1.0 = 0.01639 + 0.01613 = 0.03252
        assert abs(expected_score - 0.03252) < 0.0001

    def test_rrf_formula_bm25_only(self) -> None:
        """Verify RRF calculation when result only appears in BM25."""
        # Given: k=60, bm25_rank=5, no semantic rank
        k = 60
        bm25_rank = 5
        bm25_weight = 1.0

        # Formula: 1/(k+bm25_rank)*bm25_weight + 0 (no semantic match)
        expected_score = 1.0 / (k + bm25_rank) * bm25_weight

        # Expected: 1/65 * 1.0 = 0.01538
        assert abs(expected_score - 0.01538) < 0.0001

    def test_rrf_formula_semantic_only(self) -> None:
        """Verify RRF calculation when result only appears in semantic."""
        # Given: k=60, semantic_rank=3, no bm25 rank
        k = 60
        semantic_rank = 3
        semantic_weight = 1.0

        # Formula: 0 + 1/(k+semantic_rank)*semantic_weight
        expected_score = 1.0 / (k + semantic_rank) * semantic_weight

        # Expected: 1/63 * 1.0 = 0.01587
        assert abs(expected_score - 0.01587) < 0.0001

    def test_rrf_formula_with_custom_weights(self) -> None:
        """Verify RRF calculation with custom weights (boosted BM25)."""
        # Given: k=60, bm25_rank=1, semantic_rank=1, bm25_weight=1.5, semantic_weight=0.5
        k = 60
        bm25_rank = 1
        semantic_rank = 1
        bm25_weight = 1.5
        semantic_weight = 0.5

        # Formula with weights
        expected_score = (
            1.0 / (k + bm25_rank) * bm25_weight +
            1.0 / (k + semantic_rank) * semantic_weight
        )

        # Expected: 1/61 * 1.5 + 1/61 * 0.5 = 0.02459 + 0.00820 = 0.03279
        assert abs(expected_score - 0.03279) < 0.0001

    def test_higher_rank_produces_lower_score(self) -> None:
        """Verify that higher ranks (worse positions) produce lower scores."""
        k = 60

        # Rank 1 should score higher than rank 10
        score_rank_1 = 1.0 / (k + 1)  # 0.01639
        score_rank_10 = 1.0 / (k + 10)  # 0.01429

        assert score_rank_1 > score_rank_10

    def test_rrf_scores_are_additive(self) -> None:
        """Verify that appearing in both rankings produces higher score."""
        k = 60
        rank = 5

        # Score with only BM25
        bm25_only = 1.0 / (k + rank)

        # Score with only semantic
        semantic_only = 1.0 / (k + rank)

        # Score with both (same rank in each)
        both = bm25_only + semantic_only

        assert both > bm25_only
        assert both > semantic_only
        assert both == bm25_only + semantic_only


class TestRerankedSearchResultItem:
    """Tests for RerankedSearchResultItem dataclass."""

    def test_creates_reranked_result_item(self) -> None:
        """Should create reranked result item with all fields."""
        item = RerankedSearchResultItem(
            id="chunk-1",
            matter_id="matter-1",
            document_id="doc-1",
            content="Test content",
            page_number=5,
            bbox_ids=["bbox-1"],
            chunk_type="child",
            token_count=100,
            bm25_rank=2,
            semantic_rank=3,
            rrf_score=0.032,
            relevance_score=0.987,
        )

        assert item.id == "chunk-1"
        assert item.relevance_score == 0.987
        assert item.rrf_score == 0.032
        assert item.bbox_ids == ["bbox-1"]

    def test_nullable_relevance_score(self) -> None:
        """Should allow None for relevance_score (fallback case)."""
        item = RerankedSearchResultItem(
            id="chunk-1",
            matter_id="matter-1",
            document_id="doc-1",
            content="Test",
            page_number=None,
            bbox_ids=None,
            chunk_type="parent",
            token_count=50,
            bm25_rank=1,
            semantic_rank=None,
            rrf_score=0.016,
            relevance_score=None,  # Fallback case
        )

        assert item.relevance_score is None
        assert item.bbox_ids is None


class TestRerankedSearchResult:
    """Tests for RerankedSearchResult dataclass."""

    def test_creates_reranked_result(self) -> None:
        """Should create reranked result with all fields."""
        items = [
            RerankedSearchResultItem(
                id="chunk-1",
                matter_id="matter-1",
                document_id="doc-1",
                content="Test",
                page_number=1,
                bbox_ids=["bbox-1"],
                chunk_type="child",
                token_count=100,
                bm25_rank=1,
                semantic_rank=2,
                rrf_score=0.03,
                relevance_score=0.95,
            )
        ]
        result = RerankedSearchResult(
            results=items,
            query="test query",
            matter_id="matter-1",
            weights=SearchWeights(),
            total_candidates=20,
            rerank_used=True,
            fallback_reason=None,
        )

        assert len(result.results) == 1
        assert result.query == "test query"
        assert result.rerank_used is True
        assert result.fallback_reason is None

    def test_creates_fallback_result(self) -> None:
        """Should create fallback result when reranking fails."""
        result = RerankedSearchResult(
            results=[],
            query="test",
            matter_id="matter-1",
            weights=SearchWeights(),
            total_candidates=20,
            rerank_used=False,
            fallback_reason="Cohere API error: rate limited",
        )

        assert result.rerank_used is False
        assert "rate limited" in result.fallback_reason


class TestHybridSearchServiceSearchWithRerank:
    """Tests for search_with_rerank method."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_search_with_rerank_success(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should execute search with reranking and return results."""
        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        # Mock hybrid search RPC response
        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {
                "id": f"chunk-{i}",
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": f"Content {i}",
                "page_number": i,
                "chunk_type": "child",
                "token_count": 100 + i,
                "bm25_rank": i + 1,
                "semantic_rank": i + 2,
                "rrf_score": 0.03 - (i * 0.001),
            }
            for i in range(3)
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client
        mock_validate_results.return_value = mock_rpc_response.data

        # Mock reranker
        mock_rerank_result = MagicMock()
        mock_rerank_result.results = [
            MagicMock(index=2, relevance_score=0.95),
            MagicMock(index=0, relevance_score=0.82),
            MagicMock(index=1, relevance_score=0.65),
        ]

        with patch("app.services.rag.reranker.get_cohere_rerank_service") as mock_rerank_svc:
            mock_reranker = MagicMock()
            mock_reranker.rerank = AsyncMock(return_value=MagicMock(
                results=[
                    MagicMock(index=2, relevance_score=0.95),
                    MagicMock(index=0, relevance_score=0.82),
                ],
            ))
            mock_rerank_svc.return_value = mock_reranker

            service = HybridSearchService(embedder=mock_embedder)
            result = await service.search_with_rerank(
                query="test query",
                matter_id="550e8400-e29b-41d4-a716-446655440000",
                hybrid_limit=20,
                rerank_top_n=2,
            )

        assert isinstance(result, RerankedSearchResult)
        assert result.rerank_used is True
        assert result.fallback_reason is None
        # Should have 2 reranked results
        assert len(result.results) == 2
        # First result should have highest relevance (chunk-2)
        assert result.results[0].id == "chunk-2"
        assert result.results[0].relevance_score == 0.95

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_search_with_rerank_fallback(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should fallback to RRF results when Cohere fails."""
        from app.services.rag.reranker import CohereRerankServiceError

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        # Mock hybrid search response
        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {
                "id": "chunk-0",
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "RRF top result",
                "page_number": 1,
                "chunk_type": "child",
                "token_count": 100,
                "bm25_rank": 1,
                "semantic_rank": 1,
                "rrf_score": 0.033,
            },
            {
                "id": "chunk-1",
                "matter_id": "matter-1",
                "document_id": "doc-1",
                "content": "RRF second result",
                "page_number": 2,
                "chunk_type": "child",
                "token_count": 100,
                "bm25_rank": 2,
                "semantic_rank": 2,
                "rrf_score": 0.032,
            },
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client
        mock_validate_results.return_value = mock_rpc_response.data

        # Mock reranker to raise error
        with patch("app.services.rag.reranker.get_cohere_rerank_service") as mock_rerank_svc:
            mock_reranker = MagicMock()
            mock_reranker.rerank = AsyncMock(side_effect=CohereRerankServiceError(
                message="Cohere API timeout",
                code="COHERE_TIMEOUT",
            ))
            mock_rerank_svc.return_value = mock_reranker

            service = HybridSearchService(embedder=mock_embedder)
            result = await service.search_with_rerank(
                query="test query",
                matter_id="550e8400-e29b-41d4-a716-446655440000",
                hybrid_limit=20,
                rerank_top_n=2,
            )

        # Should return RRF results with fallback
        assert isinstance(result, RerankedSearchResult)
        assert result.rerank_used is False
        assert result.fallback_reason == "Cohere API timeout"
        assert len(result.results) == 2
        # Results should be in RRF order (not reranked)
        assert result.results[0].id == "chunk-0"
        assert result.results[0].rrf_score == 0.033
        # Relevance scores should be None (no reranking)
        assert result.results[0].relevance_score is None
        assert result.results[1].relevance_score is None

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_search_with_rerank_empty_results(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should handle empty hybrid search results gracefully."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = None  # No results
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search_with_rerank(
            query="no match query",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        assert result.results == []
        assert result.total_candidates == 0
        assert result.rerank_used is False
        assert "No hybrid search results" in result.fallback_reason
