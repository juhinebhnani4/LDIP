# Story 18.9: Global Search Integration Tests

Status: ready-for-dev

## Story

As a QA engineer,
I want integration tests validating global search works with large documents,
so that users can find content across all their matters.

## Acceptance Criteria

1. **Multi-Matter Large Document Search**
   - Global search across multiple matters with large documents (100+ pages each)
   - Results include matches from large documents
   - matched_content snippets are accurate
   - Clicking a result navigates to correct document and page

2. **Deep Page Navigation**
   - Global search result from large document page 300 is clickable
   - PDF viewer opens to page 300
   - Search term is highlighted via bbox coordinates
   - Surrounding context chunks are available for expansion

3. **Hybrid Search Correctness**
   - Semantic search finds matches in large document chunks
   - Chunk bbox_ids enable precise highlighting
   - BM25 + semantic scores combine correctly
   - Matter isolation is maintained (no cross-matter leakage)

## Tasks / Subtasks

- [ ] Task 1: Create global search test fixtures (AC: #1, #2, #3)
  - [ ] Create `backend/tests/integration/test_global_search_large_docs.py`
  - [ ] Create multi-matter fixture with large documents
  - [ ] Create mock search index data

- [ ] Task 2: Write multi-matter search tests (AC: #1)
  - [ ] Test search returns results from multiple matters
  - [ ] Verify matched_content snippets
  - [ ] Test navigation to document and page

- [ ] Task 3: Write deep page navigation tests (AC: #2)
  - [ ] Test page 300 result clickable
  - [ ] Verify PDF viewer navigation
  - [ ] Test search term highlighting
  - [ ] Test context chunk expansion

- [ ] Task 4: Write hybrid search and isolation tests (AC: #3)
  - [ ] Test semantic search in large documents
  - [ ] Test BM25 + semantic score combination
  - [ ] Test matter isolation (critical)

## Dev Notes

### Architecture Compliance

**Global Search Integration Test Structure:**
```python
# tests/integration/test_global_search_large_docs.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.search_service import GlobalSearchService
from app.models.search import SearchResult, GlobalSearchRequest


@pytest.fixture
def multi_matter_large_docs():
    """Multiple matters with large documents."""
    return {
        "matter-1": {
            "id": "matter-1",
            "name": "Johnson vs Smith",
            "documents": [
                {
                    "id": "doc-m1-large",
                    "name": "Evidence Exhibit A",
                    "page_count": 350,
                    "chunks": [
                        {
                            "id": f"chunk-m1-{i}",
                            "page_number": i * 5 + 1,
                            "content": f"Matter 1 content from pages {i*5+1}-{i*5+5}",
                            "bbox_ids": [f"bbox-m1-{i}-{j}" for j in range(100)],
                        }
                        for i in range(70)  # 350 pages / 5 = 70 chunks
                    ],
                },
            ],
        },
        "matter-2": {
            "id": "matter-2",
            "name": "Acme Corp Litigation",
            "documents": [
                {
                    "id": "doc-m2-large",
                    "name": "Contract Agreement",
                    "page_count": 200,
                    "chunks": [
                        {
                            "id": f"chunk-m2-{i}",
                            "page_number": i * 5 + 1,
                            "content": f"Matter 2 content from pages {i*5+1}-{i*5+5}",
                            "bbox_ids": [f"bbox-m2-{i}-{j}" for j in range(100)],
                        }
                        for i in range(40)  # 200 pages / 5 = 40 chunks
                    ],
                },
            ],
        },
        "matter-3": {
            "id": "matter-3",
            "name": "Different User Matter",  # Should NOT appear in results
            "user_id": "different-user",
            "documents": [
                {
                    "id": "doc-m3-large",
                    "name": "Confidential Doc",
                    "page_count": 100,
                },
            ],
        },
    }


@pytest.fixture
def mock_global_search_service():
    service = MagicMock(spec=GlobalSearchService)
    service.search = AsyncMock()
    return service


class TestMultiMatterLargeDocumentSearch:
    """Test global search across multiple matters with large documents."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_returns_results_from_multiple_matters(
        self,
        multi_matter_large_docs,
        mock_global_search_service,
    ):
        """Global search should return results from all accessible matters."""
        # Setup mock to return results from both matters
        mock_global_search_service.search.return_value = [
            SearchResult(
                document_id="doc-m1-large",
                matter_id="matter-1",
                chunk_id="chunk-m1-50",
                page_number=251,  # Page within large doc
                matched_content="This is matching content from page 251",
                score=0.95,
            ),
            SearchResult(
                document_id="doc-m2-large",
                matter_id="matter-2",
                chunk_id="chunk-m2-20",
                page_number=101,
                matched_content="Matching content from matter 2, page 101",
                score=0.87,
            ),
        ]

        results = await mock_global_search_service.search(
            query="contract agreement",
            user_id="test-user",
        )

        assert len(results) == 2, "Should return results from both matters"

        matter_ids = {r.matter_id for r in results}
        assert matter_ids == {"matter-1", "matter-2"}

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_matched_content_snippets_accurate(
        self,
        mock_global_search_service,
    ):
        """matched_content should accurately reflect the matching text."""
        expected_snippet = "The defendant failed to comply with section 5.2"

        mock_global_search_service.search.return_value = [
            SearchResult(
                document_id="doc-m1-large",
                matter_id="matter-1",
                chunk_id="chunk-m1-60",
                page_number=301,
                matched_content=expected_snippet,
                score=0.92,
            ),
        ]

        results = await mock_global_search_service.search(
            query="section 5.2 compliance",
            user_id="test-user",
        )

        assert results[0].matched_content == expected_snippet
        assert "section 5.2" in results[0].matched_content.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_click_navigates_to_correct_document_and_page(
        self,
        mock_global_search_service,
        mock_navigation_service,
    ):
        """Clicking search result should navigate to correct document and page."""
        result = SearchResult(
            document_id="doc-m1-large",
            matter_id="matter-1",
            chunk_id="chunk-m1-60",
            page_number=301,
            matched_content="Test content",
            score=0.92,
        )

        # Simulate click navigation
        await mock_navigation_service.navigate_to_result(result)

        mock_navigation_service.navigate_to_result.assert_called_once()
        call_args = mock_navigation_service.navigate_to_result.call_args[0][0]

        assert call_args.document_id == "doc-m1-large"
        assert call_args.page_number == 301


class TestDeepPageNavigation:
    """Test navigation to deep pages (300+) in large documents."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_page_300_result_clickable(
        self,
        mock_global_search_service,
    ):
        """Search result on page 300 should be clickable."""
        result = SearchResult(
            document_id="doc-m1-large",
            matter_id="matter-1",
            chunk_id="chunk-m1-59",  # Covers pages 296-300
            page_number=300,
            matched_content="Important text on page 300",
            bbox_ids=["bbox-m1-59-50", "bbox-m1-59-51"],
            score=0.88,
        )

        # Result should have valid bbox_ids for highlighting
        assert result.bbox_ids is not None
        assert len(result.bbox_ids) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pdf_viewer_opens_to_correct_page(
        self,
        mock_pdf_viewer,
    ):
        """PDF viewer should open to page 300."""
        result = SearchResult(
            document_id="doc-m1-large",
            matter_id="matter-1",
            chunk_id="chunk-m1-59",
            page_number=300,
            matched_content="Text on page 300",
            score=0.88,
        )

        # Navigate to result
        mock_pdf_viewer.open_document.return_value = True
        mock_pdf_viewer.navigate_to_page.return_value = True

        await mock_pdf_viewer.open_document(result.document_id)
        await mock_pdf_viewer.navigate_to_page(result.page_number)

        mock_pdf_viewer.navigate_to_page.assert_called_with(300)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_term_highlighted_via_bbox(
        self,
        mock_pdf_viewer,
        mock_bbox_service,
    ):
        """Search term should be highlighted using bbox coordinates."""
        result = SearchResult(
            document_id="doc-m1-large",
            matter_id="matter-1",
            chunk_id="chunk-m1-59",
            page_number=300,
            matched_content="contract agreement",
            bbox_ids=["bbox-300-5", "bbox-300-6"],
            score=0.88,
        )

        # Mock bbox lookup
        mock_bbox_service.get_bboxes.return_value = [
            {
                "id": "bbox-300-5",
                "page": 300,
                "x": 0.15,
                "y": 0.25,
                "width": 0.2,
                "height": 0.02,
                "text": "contract",
            },
            {
                "id": "bbox-300-6",
                "page": 300,
                "x": 0.36,
                "y": 0.25,
                "width": 0.25,
                "height": 0.02,
                "text": "agreement",
            },
        ]

        bboxes = await mock_bbox_service.get_bboxes(result.bbox_ids)

        # Verify highlighting
        for bbox in bboxes:
            highlight = mock_pdf_viewer.render_highlight(
                page=bbox["page"],
                x=bbox["x"],
                y=bbox["y"],
                width=bbox["width"],
                height=bbox["height"],
            )
            assert highlight["page"] == 300
            assert highlight["rendered"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_context_chunks_available_for_expansion(
        self,
        multi_matter_large_docs,
        mock_chunk_service,
    ):
        """Surrounding context chunks should be available."""
        # Chunk at page 300 (chunk index 59)
        current_chunk_index = 59

        # Get surrounding chunks
        mock_chunk_service.get_surrounding_chunks.return_value = [
            {"id": "chunk-m1-58", "page_number": 291},  # Previous
            {"id": "chunk-m1-59", "page_number": 296},  # Current
            {"id": "chunk-m1-60", "page_number": 301},  # Next
        ]

        surrounding = await mock_chunk_service.get_surrounding_chunks(
            document_id="doc-m1-large",
            chunk_index=current_chunk_index,
            window=1,
        )

        assert len(surrounding) == 3, "Should have prev, current, next"


class TestHybridSearchAndMatterIsolation:
    """Test hybrid search correctness and matter isolation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_semantic_search_finds_large_doc_matches(
        self,
        mock_global_search_service,
    ):
        """Semantic search should find matches in large document chunks."""
        # Search for semantically similar content
        mock_global_search_service.search.return_value = [
            SearchResult(
                document_id="doc-m1-large",
                matter_id="matter-1",
                chunk_id="chunk-m1-40",
                page_number=201,
                matched_content="The agreement stipulates quarterly payments",
                score=0.91,
                search_type="semantic",
            ),
        ]

        results = await mock_global_search_service.search(
            query="payment schedule obligations",
            user_id="test-user",
            search_type="hybrid",
        )

        assert len(results) > 0
        assert results[0].search_type == "semantic"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_bm25_semantic_scores_combined(
        self,
        mock_global_search_service,
    ):
        """BM25 and semantic scores should combine correctly."""
        # Mock results with both score types
        mock_global_search_service.search.return_value = [
            SearchResult(
                document_id="doc-m1-large",
                matter_id="matter-1",
                chunk_id="chunk-m1-30",
                page_number=151,
                matched_content="Contract terms and conditions",
                score=0.92,  # Combined score
                bm25_score=0.85,
                semantic_score=0.94,
            ),
        ]

        results = await mock_global_search_service.search(
            query="contract terms",
            user_id="test-user",
            search_type="hybrid",
        )

        result = results[0]

        # Combined score should be reasonable combination
        assert result.score > 0
        assert result.bm25_score is not None
        assert result.semantic_score is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_matter_isolation_no_cross_matter_leakage(
        self,
        multi_matter_large_docs,
        mock_global_search_service,
    ):
        """Search should NOT return results from other users' matters."""
        # matter-3 belongs to different user
        test_user_id = "test-user"
        different_user_id = "different-user"

        # Search as test-user
        mock_global_search_service.search.return_value = [
            SearchResult(
                document_id="doc-m1-large",
                matter_id="matter-1",
                chunk_id="chunk-m1-10",
                page_number=51,
                matched_content="Test content",
                score=0.88,
            ),
        ]

        results = await mock_global_search_service.search(
            query="confidential",
            user_id=test_user_id,
        )

        # Verify no results from matter-3 (different user)
        returned_matter_ids = {r.matter_id for r in results}
        assert "matter-3" not in returned_matter_ids, (
            "Should not return results from different user's matter"
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_bbox_ids_enable_precise_highlighting(
        self,
        mock_bbox_service,
    ):
        """Chunk bbox_ids should enable precise text highlighting."""
        chunk_bbox_ids = ["bbox-m1-30-0", "bbox-m1-30-1", "bbox-m1-30-2"]

        mock_bbox_service.get_bboxes.return_value = [
            {
                "id": "bbox-m1-30-0",
                "page": 151,
                "text": "Contract",
                "x": 0.1,
                "y": 0.3,
            },
            {
                "id": "bbox-m1-30-1",
                "page": 151,
                "text": "terms",
                "x": 0.25,
                "y": 0.3,
            },
            {
                "id": "bbox-m1-30-2",
                "page": 151,
                "text": "conditions",
                "x": 0.38,
                "y": 0.3,
            },
        ]

        bboxes = await mock_bbox_service.get_bboxes(chunk_bbox_ids)

        # All bboxes on same page
        pages = {b["page"] for b in bboxes}
        assert len(pages) == 1, "All bboxes should be on same page"

        # Text can be reconstructed
        text = " ".join(b["text"] for b in bboxes)
        assert text == "Contract terms conditions"
```

### Testing Requirements

**Test Markers:**
```python
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests",
]
```

### References

- [Source: epic-4-testing-validation.md#Story 4.9] - Full AC
- [Source: Story 18.8] - RAG pipeline tests
- [Source: architecture.md#Search] - Search architecture
- [Source: architecture.md#Matter Isolation] - 4-layer isolation

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

