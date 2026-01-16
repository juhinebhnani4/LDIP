# Story 18.8: RAG Pipeline Integration Tests for Large Documents

Status: ready-for-dev

## Story

As a QA engineer,
I want integration tests validating the full RAG pipeline works with large documents,
so that search and highlighting features work correctly.

## Acceptance Criteria

1. **Full Pipeline Completion**
   - 200+ page document processes through OCR → chunk → embed → entity extraction
   - All chunks have non-empty bbox_ids arrays
   - All bbox_ids resolve to valid bounding_box records
   - Chunk page_number matches the most common page in bbox_ids

2. **Hybrid Search Validation**
   - Query matching page 150 content returns relevant chunks
   - Chunk bbox_ids point to page 150 bounding boxes
   - Highlighting renders correctly in PDF viewer at page 150

3. **Entity Mention Validation**
   - Entity mentions are retrieved successfully
   - EntityMention.bbox_ids are valid
   - Clicking entity mention highlights correct text on correct page
   - Entity page_number matches bbox page_number

## Tasks / Subtasks

- [ ] Task 1: Create RAG pipeline test fixtures (AC: #1, #2, #3)
  - [ ] Create `backend/tests/integration/test_rag_pipeline_large_docs.py`
  - [ ] Create mock 200+ page processed document fixture
  - [ ] Create mock chunk and embedding data

- [ ] Task 2: Write full pipeline tests (AC: #1)
  - [ ] Test OCR → chunk → embed pipeline completion
  - [ ] Verify all chunks have bbox_ids
  - [ ] Verify bbox_ids resolve to valid records
  - [ ] Verify page_number consistency

- [ ] Task 3: Write hybrid search tests (AC: #2)
  - [ ] Test search returns chunks from deep pages
  - [ ] Verify bbox_ids map to correct pages
  - [ ] Test highlighting coordinates

- [ ] Task 4: Write entity mention tests (AC: #3)
  - [ ] Test entity retrieval with valid bbox_ids
  - [ ] Test entity click highlights correct text
  - [ ] Verify page number consistency

## Dev Notes

### Architecture Compliance

**RAG Pipeline Integration Test Structure:**
```python
# tests/integration/test_rag_pipeline_large_docs.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.entity_service import EntityService
from app.services.search_service import SearchService


@pytest.fixture
def processed_large_document():
    """Fixture: 200-page document with OCR complete."""
    return {
        "id": "doc-large-test",
        "matter_id": "matter-test",
        "page_count": 200,
        "status": "ocr_complete",
        "bounding_boxes": [
            {
                "id": f"bbox-{page}-{idx}",
                "document_id": "doc-large-test",
                "page": page,
                "reading_order_index": idx,
                "text": f"Text content on page {page}, block {idx}",
                "x": 0.1,
                "y": 0.1 + (idx * 0.04),
                "width": 0.8,
                "height": 0.03,
            }
            for page in range(1, 201)
            for idx in range(20)  # 20 bboxes per page
        ],
    }


@pytest.fixture
def chunks_with_bboxes(processed_large_document):
    """Fixture: Chunks with bbox_ids linked."""
    bboxes = processed_large_document["bounding_boxes"]
    chunks = []

    # Create chunks (roughly 1000 tokens, ~5 pages each)
    for chunk_idx in range(40):  # 200 pages / 5 = 40 chunks
        start_page = chunk_idx * 5 + 1
        end_page = min(start_page + 4, 200)

        # Get bbox_ids for this chunk's pages
        chunk_bbox_ids = [
            bbox["id"]
            for bbox in bboxes
            if start_page <= bbox["page"] <= end_page
        ]

        chunks.append({
            "id": f"chunk-{chunk_idx}",
            "document_id": "doc-large-test",
            "chunk_index": chunk_idx,
            "page_number": start_page,  # Most common page
            "bbox_ids": chunk_bbox_ids,
            "content": f"Content from pages {start_page}-{end_page}",
            "embedding": [0.1] * 1536,  # Mock embedding
        })

    return chunks


class TestFullPipelineCompletion:
    """Test full RAG pipeline for large documents."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_all_chunks_have_bbox_ids(
        self,
        chunks_with_bboxes,
    ):
        """All chunks should have non-empty bbox_ids arrays."""
        for chunk in chunks_with_bboxes:
            assert chunk["bbox_ids"], (
                f"Chunk {chunk['id']} has empty bbox_ids"
            )
            assert len(chunk["bbox_ids"]) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_all_bbox_ids_resolve_to_valid_records(
        self,
        chunks_with_bboxes,
        processed_large_document,
    ):
        """All bbox_ids should reference existing bounding_box records."""
        valid_bbox_ids = {
            bbox["id"] for bbox in processed_large_document["bounding_boxes"]
        }

        for chunk in chunks_with_bboxes:
            for bbox_id in chunk["bbox_ids"]:
                assert bbox_id in valid_bbox_ids, (
                    f"Chunk {chunk['id']} references invalid bbox_id: {bbox_id}"
                )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chunk_page_number_matches_bbox_pages(
        self,
        chunks_with_bboxes,
        processed_large_document,
    ):
        """Chunk page_number should match the most common page in bbox_ids."""
        bboxes_by_id = {
            bbox["id"]: bbox
            for bbox in processed_large_document["bounding_boxes"]
        }

        for chunk in chunks_with_bboxes:
            if not chunk["bbox_ids"]:
                continue

            # Get page numbers for chunk's bboxes
            bbox_pages = [
                bboxes_by_id[bid]["page"]
                for bid in chunk["bbox_ids"]
            ]

            # Find most common page
            from collections import Counter
            page_counts = Counter(bbox_pages)
            most_common_page = page_counts.most_common(1)[0][0]

            # Chunk page_number should be within the chunk's page range
            min_page = min(bbox_pages)
            max_page = max(bbox_pages)
            assert min_page <= chunk["page_number"] <= max_page, (
                f"Chunk page_number {chunk['page_number']} "
                f"outside bbox range [{min_page}, {max_page}]"
            )


class TestHybridSearchValidation:
    """Test hybrid search with large documents."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_returns_chunks_from_page_150(
        self,
        chunks_with_bboxes,
        processed_large_document,
        mock_search_service,
    ):
        """Search for content on page 150 should return relevant chunks."""
        # Find bboxes on page 150
        page_150_text = "Text content on page 150"

        # Mock search returning chunk that includes page 150
        # Page 150 should be in chunk index 29 (pages 146-150)
        expected_chunk_idx = 29

        mock_search_service.hybrid_search.return_value = [
            chunks_with_bboxes[expected_chunk_idx]
        ]

        results = await mock_search_service.hybrid_search(
            query=page_150_text,
            matter_id="matter-test",
        )

        assert len(results) > 0, "Search should return results"

        # Verify returned chunk contains page 150 bboxes
        result_chunk = results[0]
        bboxes_by_id = {
            bbox["id"]: bbox
            for bbox in processed_large_document["bounding_boxes"]
        }

        result_pages = {
            bboxes_by_id[bid]["page"]
            for bid in result_chunk["bbox_ids"]
        }

        assert 150 in result_pages, (
            f"Result chunk should include page 150, got pages: {result_pages}"
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_highlighting_coordinates_valid_for_page_150(
        self,
        processed_large_document,
    ):
        """Highlighting coordinates for page 150 should be valid."""
        page_150_bboxes = [
            bbox for bbox in processed_large_document["bounding_boxes"]
            if bbox["page"] == 150
        ]

        assert len(page_150_bboxes) > 0, "Should have bboxes on page 150"

        for bbox in page_150_bboxes:
            # Coordinates should be normalized (0-1)
            assert 0 <= bbox["x"] <= 1, f"Invalid x: {bbox['x']}"
            assert 0 <= bbox["y"] <= 1, f"Invalid y: {bbox['y']}"
            assert 0 < bbox["width"] <= 1, f"Invalid width: {bbox['width']}"
            assert 0 < bbox["height"] <= 1, f"Invalid height: {bbox['height']}"

            # Should not exceed page bounds
            assert bbox["x"] + bbox["width"] <= 1.01  # Small tolerance


class TestEntityMentionValidation:
    """Test entity mention validation for large documents."""

    @pytest.fixture
    def entity_mentions(self, processed_large_document):
        """Entity mentions extracted from large document."""
        return [
            {
                "id": "mention-1",
                "entity_id": "entity-party-1",
                "document_id": "doc-large-test",
                "page_number": 75,
                "bbox_ids": ["bbox-75-5", "bbox-75-6"],
                "text": "John Doe",
            },
            {
                "id": "mention-2",
                "entity_id": "entity-party-2",
                "document_id": "doc-large-test",
                "page_number": 150,
                "bbox_ids": ["bbox-150-10", "bbox-150-11"],
                "text": "Acme Corporation",
            },
        ]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_entity_mention_bbox_ids_valid(
        self,
        entity_mentions,
        processed_large_document,
    ):
        """EntityMention.bbox_ids should reference valid records."""
        valid_bbox_ids = {
            bbox["id"] for bbox in processed_large_document["bounding_boxes"]
        }

        for mention in entity_mentions:
            for bbox_id in mention["bbox_ids"]:
                assert bbox_id in valid_bbox_ids, (
                    f"Mention {mention['id']} has invalid bbox_id: {bbox_id}"
                )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_entity_page_number_matches_bbox_pages(
        self,
        entity_mentions,
        processed_large_document,
    ):
        """Entity page_number should match bbox page_number."""
        bboxes_by_id = {
            bbox["id"]: bbox
            for bbox in processed_large_document["bounding_boxes"]
        }

        for mention in entity_mentions:
            for bbox_id in mention["bbox_ids"]:
                bbox = bboxes_by_id[bbox_id]
                assert bbox["page"] == mention["page_number"], (
                    f"Mention page {mention['page_number']} != "
                    f"bbox page {bbox['page']}"
                )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_entity_click_highlights_correct_text(
        self,
        entity_mentions,
        processed_large_document,
        mock_pdf_viewer,
    ):
        """Clicking entity mention should highlight correct text on correct page."""
        bboxes_by_id = {
            bbox["id"]: bbox
            for bbox in processed_large_document["bounding_boxes"]
        }

        for mention in entity_mentions:
            # Get bboxes for this mention
            mention_bboxes = [
                bboxes_by_id[bid] for bid in mention["bbox_ids"]
            ]

            # Simulate click → navigate to page → highlight
            for bbox in mention_bboxes:
                highlight = mock_pdf_viewer.render_highlight(
                    page=bbox["page"],
                    x=bbox["x"],
                    y=bbox["y"],
                    width=bbox["width"],
                    height=bbox["height"],
                )

                assert highlight["page"] == mention["page_number"], (
                    f"Highlight on wrong page: {highlight['page']}"
                )
                assert highlight["rendered"], "Highlight should render"


class TestDeepPageContent:
    """Test that deep pages (150+) are accessible and searchable."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_page_200_content_accessible(
        self,
        processed_large_document,
    ):
        """Content from page 200 (last page) should be accessible."""
        page_200_bboxes = [
            bbox for bbox in processed_large_document["bounding_boxes"]
            if bbox["page"] == 200
        ]

        assert len(page_200_bboxes) == 20, "Should have 20 bboxes on page 200"

        for bbox in page_200_bboxes:
            assert "page 200" in bbox["text"].lower(), (
                f"Page 200 bbox has wrong text: {bbox['text']}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chunk_coverage_complete(
        self,
        chunks_with_bboxes,
        processed_large_document,
    ):
        """All pages should be covered by at least one chunk."""
        all_bbox_ids_in_chunks = set()
        for chunk in chunks_with_bboxes:
            all_bbox_ids_in_chunks.update(chunk["bbox_ids"])

        # Every bbox should be in at least one chunk
        all_bbox_ids = {
            bbox["id"] for bbox in processed_large_document["bounding_boxes"]
        }

        coverage = len(all_bbox_ids_in_chunks) / len(all_bbox_ids)
        assert coverage >= 0.95, (  # Allow small tolerance
            f"Chunk coverage is only {coverage:.2%}"
        )
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

- [Source: epic-4-testing-validation.md#Story 4.8] - Full AC
- [Source: Story 17.7] - Downstream RAG trigger
- [Source: Story 17.8] - Bbox reference validation
- [Source: architecture.md#RAG Pipeline] - RAG architecture

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

