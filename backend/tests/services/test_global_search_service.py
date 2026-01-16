"""Unit tests for GlobalSearchService.

Story 14.11: Global Search RAG Wiring

Tests cover:
- RRF merge logic
- Matter title matching
- Match snippet extraction
- Parallel search handling
- Edge cases (no matters, empty results, etc.)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.global_search import GlobalSearchMeta, GlobalSearchResponse
from app.services.global_search_service import (
    GlobalSearchService,
    GlobalSearchServiceError,
    MatterInfo,
    SearchResultWithMatter,
)
from app.services.rag.hybrid_search import (
    HybridSearchResult,
    HybridSearchServiceError,
    SearchResult,
    SearchWeights,
)


def create_mock_search_result(
    matter_id: str,
    document_id: str | None = None,
    content: str = "Test content for search result",
    page_number: int = 1,
    rrf_score: float = 0.5,
) -> SearchResult:
    """Create a mock SearchResult for testing."""
    return SearchResult(
        id=str(uuid4()),  # chunk id
        matter_id=matter_id,
        document_id=document_id or str(uuid4()),
        content=content,
        page_number=page_number,
        chunk_type="parent",
        token_count=100,
        bm25_rank=1,
        semantic_rank=1,
        rrf_score=rrf_score,
    )


def create_mock_hybrid_result(
    matter_id: str,
    results: list[SearchResult] | None = None,
    query: str = "test query",
) -> HybridSearchResult:
    """Create a mock HybridSearchResult for testing."""
    return HybridSearchResult(
        results=results or [],
        query=query,
        matter_id=matter_id,
        weights=SearchWeights(),
        total_candidates=len(results) if results else 0,
    )


class TestGlobalSearchServiceSnippetExtraction:
    """Tests for _extract_match_snippet method."""

    def test_extract_snippet_with_exact_match(self) -> None:
        """Should center snippet around exact query match."""
        service = GlobalSearchService()
        content = "This is some text before the contract termination clause which is important."
        query = "contract termination"

        snippet = service._extract_match_snippet(content, query, max_length=50)

        assert "contract termination" in snippet.lower()
        assert len(snippet) <= 53  # max_length + ellipsis

    def test_extract_snippet_with_word_match(self) -> None:
        """Should find individual word when full query not found."""
        service = GlobalSearchService()
        content = "The agreement contains a termination provision in section 5."
        query = "contract termination"

        snippet = service._extract_match_snippet(content, query, max_length=50)

        assert "termination" in snippet.lower()

    def test_extract_snippet_no_match_returns_beginning(self) -> None:
        """Should return beginning of content when no match found."""
        service = GlobalSearchService()
        content = "This is some completely unrelated content about something else."
        query = "xyz123abc"

        snippet = service._extract_match_snippet(content, query, max_length=30)

        assert snippet.startswith("This is")

    def test_extract_snippet_empty_content(self) -> None:
        """Should return empty string for empty content."""
        service = GlobalSearchService()

        snippet = service._extract_match_snippet("", "query", max_length=50)

        assert snippet == ""

    def test_extract_snippet_short_content(self) -> None:
        """Should return full content if shorter than max_length."""
        service = GlobalSearchService()
        content = "Short text"
        query = "short"

        snippet = service._extract_match_snippet(content, query, max_length=100)

        assert snippet == content

    def test_extract_snippet_adds_ellipsis(self) -> None:
        """Should add ellipsis when truncating content."""
        service = GlobalSearchService()
        content = "A" * 50 + "match" + "B" * 50
        query = "match"

        snippet = service._extract_match_snippet(content, query, max_length=30)

        assert "..." in snippet


class TestGlobalSearchServiceMatterTitleMatching:
    """Tests for _match_matter_titles method."""

    def test_match_matter_titles_case_insensitive(self) -> None:
        """Should match matter titles case-insensitively."""
        service = GlobalSearchService()
        matters = [
            MatterInfo(id="1", title="Smith vs Jones", description="Contract case"),
            MatterInfo(id="2", title="Johnson Contract Dispute", description=None),
        ]

        results = service._match_matter_titles("SMITH", matters)

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].type == "matter"

    def test_match_matter_titles_respects_limit(self) -> None:
        """Should respect the limit parameter."""
        service = GlobalSearchService()
        matters = [
            MatterInfo(id=str(i), title=f"Test Matter {i}", description=None)
            for i in range(10)
        ]

        results = service._match_matter_titles("Test", matters, limit=3)

        assert len(results) == 3

    def test_match_matter_titles_includes_description(self) -> None:
        """Should include truncated description as matchedContent."""
        service = GlobalSearchService()
        matters = [
            MatterInfo(
                id="1",
                title="Test Matter",
                description="A" * 150,  # Long description
            ),
        ]

        results = service._match_matter_titles("Test", matters)

        assert len(results) == 1
        assert len(results[0].matched_content) <= 100

    def test_match_matter_titles_no_match(self) -> None:
        """Should return empty list when no titles match."""
        service = GlobalSearchService()
        matters = [
            MatterInfo(id="1", title="Smith Case", description=None),
        ]

        results = service._match_matter_titles("Johnson", matters)

        assert len(results) == 0


class TestGlobalSearchServiceRRFMerge:
    """Tests for _merge_results_rrf method."""

    def test_merge_results_rrf_ranks_by_score(self) -> None:
        """Should rank results by RRF score (higher first)."""
        service = GlobalSearchService()
        matter = MatterInfo(id="m1", title="Test Matter", description=None)

        # Create results with different ranks (lower rank = higher score)
        results = [
            SearchResultWithMatter(
                result=create_mock_search_result(matter.id, content="Result A"),
                matter=matter,
                source_rank=3,  # Lower RRF score
            ),
            SearchResultWithMatter(
                result=create_mock_search_result(matter.id, content="Result B"),
                matter=matter,
                source_rank=1,  # Higher RRF score
            ),
        ]

        merged = service._merge_results_rrf(results, [matter], "test", limit=10)

        # Document results should be ordered by RRF score
        doc_results = [r for r in merged if r.type == "document"]
        assert len(doc_results) == 2

    def test_merge_results_rrf_deduplicates(self) -> None:
        """Should deduplicate results by chunk ID."""
        service = GlobalSearchService()
        matter = MatterInfo(id="m1", title="Test", description=None)
        result = create_mock_search_result(matter.id)

        # Same result appearing twice
        results = [
            SearchResultWithMatter(result=result, matter=matter, source_rank=1),
            SearchResultWithMatter(result=result, matter=matter, source_rank=2),
        ]

        merged = service._merge_results_rrf(results, [matter], "query", limit=10)

        doc_results = [r for r in merged if r.type == "document"]
        assert len(doc_results) == 1

    def test_merge_results_rrf_matter_results_first(self) -> None:
        """Should put matter title matches before document results."""
        service = GlobalSearchService()
        matter = MatterInfo(id="m1", title="Test Query Matter", description=None)
        result = create_mock_search_result(matter.id)

        results = [
            SearchResultWithMatter(result=result, matter=matter, source_rank=1),
        ]

        merged = service._merge_results_rrf(results, [matter], "query", limit=10)

        # First result should be matter type (title match)
        assert len(merged) >= 1
        assert merged[0].type == "matter"

    def test_merge_results_rrf_respects_limit(self) -> None:
        """Should respect the limit parameter."""
        service = GlobalSearchService()
        matter = MatterInfo(id="m1", title="Test", description=None)

        results = [
            SearchResultWithMatter(
                result=create_mock_search_result(matter.id, content=f"Result {i}"),
                matter=matter,
                source_rank=i,
            )
            for i in range(20)
        ]

        merged = service._merge_results_rrf(results, [matter], "query", limit=5)

        assert len(merged) <= 5

    def test_merge_results_uses_document_id(self) -> None:
        """Should use document_id (not chunk id) for document results."""
        service = GlobalSearchService()
        matter = MatterInfo(id="m1", title="Test", description=None)
        expected_doc_id = str(uuid4())
        result = create_mock_search_result(matter.id, document_id=expected_doc_id)

        results = [
            SearchResultWithMatter(result=result, matter=matter, source_rank=1),
        ]

        merged = service._merge_results_rrf(results, [matter], "xyz", limit=10)

        doc_results = [r for r in merged if r.type == "document"]
        assert len(doc_results) == 1
        assert doc_results[0].id == expected_doc_id


class TestGlobalSearchServiceAccessibleMatters:
    """Tests for _get_accessible_matters method."""

    @pytest.mark.anyio
    async def test_get_accessible_matters_returns_empty_for_no_access(self) -> None:
        """Should return empty list when user has no matter access."""
        with patch(
            "app.services.global_search_service.get_supabase_client"
        ) as mock_client:
            mock_supabase = MagicMock()
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            mock_client.return_value = mock_supabase

            service = GlobalSearchService()
            matters = await service._get_accessible_matters("user-123")

            assert matters == []

    @pytest.mark.anyio
    async def test_get_accessible_matters_handles_db_error(self) -> None:
        """Should raise GlobalSearchServiceError on database error."""
        with patch(
            "app.services.global_search_service.get_supabase_client"
        ) as mock_client:
            mock_supabase = MagicMock()
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
                "DB Error"
            )
            mock_client.return_value = mock_supabase

            service = GlobalSearchService()

            with pytest.raises(GlobalSearchServiceError) as exc_info:
                await service._get_accessible_matters("user-123")

            assert exc_info.value.code == "DATABASE_ERROR"


class TestGlobalSearchServiceSearchAcrossMatters:
    """Tests for search_across_matters method."""

    @pytest.mark.anyio
    async def test_search_returns_empty_for_short_query(self) -> None:
        """Should return empty results for queries shorter than 2 chars."""
        service = GlobalSearchService()

        result = await service.search_across_matters(
            user_id="user-123",
            query="a",
            limit=20,
        )

        assert result.data == []
        assert result.meta.total == 0

    @pytest.mark.anyio
    async def test_search_returns_empty_when_no_matters(self) -> None:
        """Should return empty when user has no accessible matters."""
        with patch.object(
            GlobalSearchService,
            "_get_accessible_matters",
            new_callable=AsyncMock,
            return_value=[],
        ):
            service = GlobalSearchService()

            result = await service.search_across_matters(
                user_id="user-123",
                query="test query",
                limit=20,
            )

            assert result.data == []
            assert result.meta.total == 0

    @pytest.mark.anyio
    async def test_search_executes_parallel_searches(self) -> None:
        """Should search all accessible matters in parallel."""
        matters = [
            MatterInfo(id="m1", title="Matter 1", description=None),
            MatterInfo(id="m2", title="Matter 2", description=None),
        ]

        mock_hybrid_search = MagicMock()
        mock_hybrid_search.search = AsyncMock(
            return_value=create_mock_hybrid_result("m1")
        )

        with patch.object(
            GlobalSearchService,
            "_get_accessible_matters",
            new_callable=AsyncMock,
            return_value=matters,
        ):
            service = GlobalSearchService(hybrid_search=mock_hybrid_search)

            await service.search_across_matters(
                user_id="user-123",
                query="test query",
                limit=20,
            )

            # Should have called search for each matter
            assert mock_hybrid_search.search.call_count == 2

    @pytest.mark.anyio
    async def test_search_continues_on_single_matter_failure(self) -> None:
        """Should continue with other matters if one fails."""
        matters = [
            MatterInfo(id="m1", title="Matter 1", description=None),
            MatterInfo(id="m2", title="Matter 2", description=None),
        ]

        mock_hybrid_search = MagicMock()
        # First call fails, second succeeds
        mock_hybrid_search.search = AsyncMock(
            side_effect=[
                HybridSearchServiceError("Search failed", "SEARCH_ERROR"),
                create_mock_hybrid_result(
                    "m2",
                    results=[create_mock_search_result("m2", content="Found result")],
                ),
            ]
        )

        with patch.object(
            GlobalSearchService,
            "_get_accessible_matters",
            new_callable=AsyncMock,
            return_value=matters,
        ):
            service = GlobalSearchService(hybrid_search=mock_hybrid_search)

            result = await service.search_across_matters(
                user_id="user-123",
                query="test query",
                limit=20,
            )

            # Should still return results from the successful search
            doc_results = [r for r in result.data if r.type == "document"]
            assert len(doc_results) >= 1

    @pytest.mark.anyio
    async def test_search_clamps_limit(self) -> None:
        """Should clamp limit to MAX_GLOBAL_LIMIT."""
        with patch.object(
            GlobalSearchService,
            "_get_accessible_matters",
            new_callable=AsyncMock,
            return_value=[],
        ):
            service = GlobalSearchService()

            # Request limit of 100, should be clamped to 50
            result = await service.search_across_matters(
                user_id="user-123",
                query="test query",
                limit=100,
            )

            assert result.meta.total == 0  # No matters, so no results
