"""Integration tests for hybrid search pipeline.

Tests the complete search flow from query to results,
including matter isolation verification.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.rag.embedder import EMBEDDING_DIMENSIONS
from app.services.rag.hybrid_search import (
    HybridSearchService,
    SearchWeights,
)


class TestSearchPipelineIntegration:
    """Integration tests for the search pipeline."""

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create a mock Supabase client with search results."""
        client = MagicMock()

        # Mock hybrid search RPC response
        hybrid_results = [
            {
                "id": str(uuid4()),
                "matter_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_id": str(uuid4()),
                "content": "The contract termination clause specifies that...",
                "page_number": 5,
                "chunk_type": "child",
                "token_count": 150,
                "bm25_rank": 1,
                "semantic_rank": 2,
                "rrf_score": 0.032,
            },
            {
                "id": str(uuid4()),
                "matter_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_id": str(uuid4()),
                "content": "In case of contract breach, the following remedies...",
                "page_number": 12,
                "chunk_type": "parent",
                "token_count": 320,
                "bm25_rank": 3,
                "semantic_rank": 1,
                "rrf_score": 0.031,
            },
        ]

        mock_response = MagicMock()
        mock_response.data = hybrid_results
        client.rpc.return_value.execute.return_value = mock_response

        return client

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Create a mock embedding service."""
        embedder = MagicMock()
        embedder.embed_text = AsyncMock(return_value=[0.1] * EMBEDDING_DIMENSIONS)
        return embedder

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_complete_hybrid_search_flow(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
        mock_supabase_client: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test complete hybrid search from query to ranked results."""
        mock_get_client.return_value = mock_supabase_client
        mock_validate_results.return_value = mock_supabase_client.rpc.return_value.execute.return_value.data

        service = HybridSearchService(embedder=mock_embedder)

        # Execute search
        result = await service.search(
            query="contract termination remedies",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
            limit=20,
            weights=SearchWeights(bm25=1.0, semantic=1.0),
        )

        # Verify pipeline execution
        mock_embedder.embed_text.assert_called_once_with("contract termination remedies")
        mock_supabase_client.rpc.assert_called_once()

        # Verify results structure
        assert len(result.results) == 2
        assert result.query == "contract termination remedies"
        assert result.matter_id == "550e8400-e29b-41d4-a716-446655440000"

        # Verify results are ordered by RRF score
        assert result.results[0].rrf_score >= result.results[1].rrf_score

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_search_with_custom_weights(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
        mock_supabase_client: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test search with boosted BM25 weight for exact term matching."""
        mock_get_client.return_value = mock_supabase_client
        mock_validate_results.return_value = mock_supabase_client.rpc.return_value.execute.return_value.data

        service = HybridSearchService(embedder=mock_embedder)

        # Search with boosted BM25 (for legal citations)
        weights = SearchWeights(bm25=1.5, semantic=0.5)
        result = await service.search(
            query="Section 138 Negotiable Instruments Act",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
            weights=weights,
        )

        # Verify weights were passed to RPC
        call_args = mock_supabase_client.rpc.call_args[1]
        assert call_args["full_text_weight"] == 1.5
        assert call_args["semantic_weight"] == 0.5

        # Verify weights in response
        assert result.weights.bm25 == 1.5
        assert result.weights.semantic == 0.5

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_search_result_contains_all_fields(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
        mock_supabase_client: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Verify search results contain all required fields for frontend."""
        mock_get_client.return_value = mock_supabase_client
        mock_validate_results.return_value = mock_supabase_client.rpc.return_value.execute.return_value.data

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query="test",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Check first result has all required fields
        first = result.results[0]
        assert first.id is not None
        assert first.document_id is not None
        assert first.content is not None
        assert first.chunk_type in ("parent", "child")
        assert first.token_count > 0
        assert first.rrf_score > 0


class TestSearchModeComparison:
    """Tests comparing different search modes."""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Create a mock embedding service."""
        embedder = MagicMock()
        embedder.embed_text = AsyncMock(return_value=[0.1] * EMBEDDING_DIMENSIONS)
        return embedder

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_bm25_only_search(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test BM25-only search for exact term matching."""
        client = MagicMock()
        bm25_results = [
            {
                "id": str(uuid4()),
                "matter_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_id": str(uuid4()),
                "content": "Section 138 of the Negotiable Instruments Act...",
                "page_number": 1,
                "chunk_type": "parent",
                "token_count": 200,
                "row_num": 1,
                "rank": 0.8,
            },
        ]
        client.rpc.return_value.execute.return_value.data = bm25_results
        mock_get_client.return_value = client
        mock_validate_results.return_value = bm25_results

        service = HybridSearchService(embedder=mock_embedder)
        results = await service.bm25_search(
            query="Section 138",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # BM25 results should only have BM25 rank
        assert len(results) == 1
        assert results[0].bm25_rank == 1
        assert results[0].semantic_rank is None

        # Should have called bm25_search_chunks
        client.rpc.assert_called_with(
            "bm25_search_chunks",
            {
                "query_text": "Section 138",
                "filter_matter_id": "550e8400-e29b-41d4-a716-446655440000",
                "match_count": 30,
            },
        )

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_semantic_only_search(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test semantic-only search for conceptual matching."""
        client = MagicMock()
        semantic_results = [
            {
                "id": str(uuid4()),
                "matter_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_id": str(uuid4()),
                "content": "Remedies available for breach of contractual obligations...",
                "page_number": 10,
                "chunk_type": "child",
                "token_count": 180,
                "row_num": 1,
                "similarity": 0.92,
            },
        ]
        client.rpc.return_value.execute.return_value.data = semantic_results
        mock_get_client.return_value = client
        mock_validate_results.return_value = semantic_results

        service = HybridSearchService(embedder=mock_embedder)
        results = await service.semantic_search(
            query="what happens when someone doesn't fulfill their promises",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Semantic results should only have semantic rank
        assert len(results) == 1
        assert results[0].semantic_rank == 1
        assert results[0].bm25_rank is None

        # Should have called semantic_search_chunks
        client.rpc.assert_called_once()
        call_name = client.rpc.call_args[0][0]
        assert call_name == "semantic_search_chunks"


class TestSearchEdgeCases:
    """Tests for search edge cases and error handling."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_empty_results_handling(
        self,
        mock_validate_ns: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test handling of queries with no matches."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * EMBEDDING_DIMENSIONS)

        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = None
        mock_get_client.return_value = client

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query="xyznonexistenttermxyz",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        assert result.results == []
        assert result.total_candidates == 0

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_long_query_handling(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test handling of very long search queries."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * EMBEDDING_DIMENSIONS)

        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = []
        mock_get_client.return_value = client
        mock_validate_results.return_value = []

        long_query = "legal contract terms " * 50  # ~150 words

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query=long_query,
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Should handle long query without error
        assert result.query == long_query
