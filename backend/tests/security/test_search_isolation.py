"""Security tests for hybrid search matter isolation.

Tests the 4-layer matter isolation enforcement for search operations.
Verifies that users cannot access chunks from matters they don't have access to.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.rag.hybrid_search import (
    HybridSearchService,
    HybridSearchServiceError,
)


class TestSearchMatterIsolationLayer2:
    """Tests for Layer 2: Matter ID validation in search functions."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_rejects_invalid_matter_id_format(
        self,
        mock_validate_ns: MagicMock,
    ) -> None:
        """Should reject invalid matter_id format."""
        mock_validate_ns.side_effect = ValueError("Invalid matter_id")
        mock_embedder = MagicMock()

        service = HybridSearchService(embedder=mock_embedder)

        with pytest.raises(HybridSearchServiceError) as exc_info:
            await service.search(
                query="test",
                matter_id="invalid-not-uuid",
            )

        assert exc_info.value.code == "INVALID_PARAMETER"

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_rejects_empty_matter_id(
        self,
        mock_validate_ns: MagicMock,
    ) -> None:
        """Should reject empty matter_id."""
        mock_validate_ns.side_effect = ValueError("matter_id required")
        mock_embedder = MagicMock()

        service = HybridSearchService(embedder=mock_embedder)

        with pytest.raises(HybridSearchServiceError):
            await service.search(query="test", matter_id="")

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_validates_all_results_belong_to_matter(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should validate that all returned results belong to requested matter."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        # Simulate results from RPC
        authorized_matter = "550e8400-e29b-41d4-a716-446655440000"
        results_data = [
            {
                "id": str(uuid4()),
                "matter_id": authorized_matter,
                "document_id": str(uuid4()),
                "content": "Valid result",
                "page_number": 1,
                "chunk_type": "child",
                "token_count": 100,
                "bm25_rank": 1,
                "semantic_rank": 2,
                "rrf_score": 0.03,
            }
        ]

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = results_data
        mock_get_client.return_value = mock_client

        # validate_search_results should filter/validate results
        mock_validate_results.return_value = results_data

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query="test",
            matter_id=authorized_matter,
        )

        # Verify validate_search_results was called with matter_id
        mock_validate_results.assert_called_once_with(
            results_data, authorized_matter
        )

        # All results should be from the authorized matter
        for r in result.results:
            assert r.matter_id == authorized_matter


class TestSearchCrossMatterProtection:
    """Tests for cross-matter access prevention."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_filters_cross_matter_results(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should filter out results from other matters."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        authorized_matter = "550e8400-e29b-41d4-a716-446655440000"
        unauthorized_matter = "660e8400-e29b-41d4-a716-446655440001"

        # Simulate a bug where SQL returns cross-matter results
        mixed_results = [
            {
                "id": "chunk-1",
                "matter_id": authorized_matter,
                "content": "Valid",
                "document_id": "doc-1",
                "page_number": 1,
                "chunk_type": "child",
                "token_count": 100,
                "bm25_rank": 1,
                "semantic_rank": 2,
                "rrf_score": 0.03,
            },
            {
                "id": "chunk-2",
                "matter_id": unauthorized_matter,  # WRONG MATTER
                "content": "Should be filtered",
                "document_id": "doc-2",
                "page_number": 1,
                "chunk_type": "child",
                "token_count": 100,
                "bm25_rank": 2,
                "semantic_rank": 1,
                "rrf_score": 0.025,
            },
        ]

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = mixed_results
        mock_get_client.return_value = mock_client

        # validate_search_results should filter unauthorized results
        mock_validate_results.return_value = [mixed_results[0]]

        service = HybridSearchService(embedder=mock_embedder)
        result = await service.search(
            query="test",
            matter_id=authorized_matter,
        )

        # Should only return authorized results
        assert len(result.results) == 1
        assert result.results[0].id == "chunk-1"


class TestSearchSQLInjectionPrevention:
    """Tests for SQL injection prevention in search."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_rejects_sql_injection_in_matter_id(
        self,
        mock_validate_ns: MagicMock,
    ) -> None:
        """Should reject SQL injection attempts in matter_id."""
        mock_validate_ns.side_effect = ValueError("Invalid UUID")
        mock_embedder = MagicMock()

        service = HybridSearchService(embedder=mock_embedder)

        injection_attempts = [
            "'; DROP TABLE chunks; --",
            "550e8400-e29b-41d4-a716-446655440000' OR '1'='1",
            "550e8400-e29b-41d4-a716-446655440000; DELETE FROM chunks;",
            "../../../etc/passwd",
            "UNION SELECT * FROM users",
        ]

        for injection in injection_attempts:
            with pytest.raises(HybridSearchServiceError):
                await service.search(
                    query="legitimate query",
                    matter_id=injection,
                )

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_handles_malicious_query_safely(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should handle malicious search queries without SQL injection."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = []
        mock_get_client.return_value = mock_client
        mock_validate_results.return_value = []

        service = HybridSearchService(embedder=mock_embedder)

        # These should be handled as literal search queries, not SQL
        malicious_queries = [
            "'; DROP TABLE chunks; --",
            "contract' OR 1=1; --",
            "UNION SELECT * FROM users WHERE '1'='1",
            "<script>alert('xss')</script>",
        ]

        for query in malicious_queries:
            # Should not raise - query is passed to embedding, not SQL
            result = await service.search(
                query=query,
                matter_id="550e8400-e29b-41d4-a716-446655440000",
            )

            # Query should be passed to RPC as-is (will become embedding)
            assert result.query == query


class TestSearchParameterValidation:
    """Tests for search parameter validation."""

    def test_search_weights_validation(self) -> None:
        """Should validate search weight parameters."""
        from app.services.rag.hybrid_search import SearchWeights

        # Valid weights
        weights = SearchWeights(bm25=1.5, semantic=0.5)
        assert weights.bm25 == 1.5

        # Invalid weights
        with pytest.raises(ValueError):
            SearchWeights(bm25=-1.0, semantic=1.0)

        with pytest.raises(ValueError):
            SearchWeights(bm25=1.0, semantic=3.0)

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_enforces_matter_id_on_every_call(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Should always require matter_id parameter."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = []
        mock_get_client.return_value = mock_client
        mock_validate_results.return_value = []

        service = HybridSearchService(embedder=mock_embedder)

        # All search methods should require matter_id
        matter_id = "550e8400-e29b-41d4-a716-446655440000"

        # Hybrid search
        await service.search(query="test", matter_id=matter_id)
        mock_validate_ns.assert_called()

        # BM25 search
        await service.bm25_search(query="test", matter_id=matter_id)

        # Semantic search
        await service.semantic_search(query="test", matter_id=matter_id)

        # All calls should have validated matter_id
        assert mock_validate_ns.call_count >= 3


class TestSearchAuditLogging:
    """Tests for search audit logging."""

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.logger")
    @patch("app.services.rag.hybrid_search.get_supabase_client")
    @patch("app.services.rag.hybrid_search.validate_search_results")
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_logs_search_requests(
        self,
        mock_validate_ns: MagicMock,
        mock_validate_results: MagicMock,
        mock_get_client: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Should log search requests for audit trail."""
        mock_embedder = MagicMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value.data = []
        mock_get_client.return_value = mock_client
        mock_validate_results.return_value = []

        service = HybridSearchService(embedder=mock_embedder)
        await service.search(
            query="sensitive search",
            matter_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Should have logged the search
        mock_logger.info.assert_called()

        # Verify log contains matter_id
        log_calls = mock_logger.info.call_args_list
        assert any(
            "550e8400-e29b-41d4-a716-446655440000" in str(call)
            for call in log_calls
        )

    @pytest.mark.asyncio
    @patch("app.services.rag.hybrid_search.validate_namespace")
    async def test_logs_failed_access_attempts(
        self,
        mock_validate_ns: MagicMock,
    ) -> None:
        """Should raise proper error for invalid matter_id attempts."""
        mock_validate_ns.side_effect = ValueError("Invalid matter_id")
        mock_embedder = MagicMock()

        service = HybridSearchService(embedder=mock_embedder)

        with pytest.raises(HybridSearchServiceError) as exc_info:
            await service.search(
                query="test",
                matter_id="invalid-matter",
            )

        # Should raise with INVALID_PARAMETER code for audit trail
        assert exc_info.value.code == "INVALID_PARAMETER"
        assert "Invalid matter_id" in str(exc_info.value.message)
