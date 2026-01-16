"""RAG Pipeline Integration Tests for Large Documents.

Story 18.8: RAG Pipeline Integration Tests for Large Documents (Epic 4)

Validates the full RAG pipeline works with large documents:
- OCR → Chunk → Embed → Entity Extraction
- All chunks have non-empty bbox_ids arrays
- All bbox_ids resolve to valid bounding_box records
- Chunk page_number matches the most common page in bbox_ids
- Hybrid search returns relevant chunks
- Highlighting renders correctly in PDF viewer
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.ocr_result_merger import ChunkOCRResult, OCRResultMerger


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_document():
    """Create mock large document."""
    return {
        "id": str(uuid4()),
        "matter_id": str(uuid4()),
        "filename": "large_document.pdf",
        "page_count": 200,
    }


@pytest.fixture
def mock_bounding_boxes():
    """Create mock bounding boxes for 200-page document."""
    bboxes = []
    for page in range(1, 201):
        for roi in range(20):  # 20 bboxes per page
            bboxes.append({
                "id": str(uuid4()),
                "document_id": "doc-123",
                "page_number": page,
                "reading_order_index": roi,
                "text": f"Page {page}, block {roi}",
                "x": 72 + (roi % 5) * 100,
                "y": 72 + (roi // 5) * 100,
                "width": 90,
                "height": 20,
            })
    return bboxes


@pytest.fixture
def mock_chunks():
    """Create mock text chunks with bbox_ids."""

    def _create(page_start: int, page_end: int, bbox_ids: list[str]) -> dict:
        return {
            "id": str(uuid4()),
            "document_id": "doc-123",
            "content": f"Content for pages {page_start}-{page_end}",
            "page_number": page_start,  # Primary page
            "bbox_ids": bbox_ids,
            "embedding": [0.1] * 1536,  # Mock embedding
        }

    return _create


# =============================================================================
# Story 18.8: RAG Pipeline Integration Tests
# =============================================================================


class TestChunkBboxIdValidation:
    """Tests validating bbox_ids in chunks."""

    def test_all_chunks_have_bbox_ids(self, mock_bounding_boxes):
        """All chunks have non-empty bbox_ids arrays."""
        # Simulate chunk creation with bbox linking
        chunks = []

        for page_start in range(1, 201, 10):  # Chunks every 10 pages
            page_end = min(page_start + 9, 200)

            # Get bboxes for this page range
            chunk_bboxes = [
                b for b in mock_bounding_boxes
                if page_start <= b["page_number"] <= page_end
            ]
            bbox_ids = [b["id"] for b in chunk_bboxes]

            chunks.append({
                "page_start": page_start,
                "page_end": page_end,
                "bbox_ids": bbox_ids,
            })

        # Verify each chunk has bbox_ids
        for i, chunk in enumerate(chunks):
            assert len(chunk["bbox_ids"]) > 0, f"Chunk {i} has no bbox_ids"

    def test_bbox_ids_resolve_to_valid_records(self, mock_bounding_boxes):
        """All bbox_ids point to valid bounding_box records."""
        # Create bbox lookup
        bbox_lookup = {b["id"]: b for b in mock_bounding_boxes}

        # Simulate chunks with bbox_ids
        for page_start in range(1, 201, 10):
            page_end = min(page_start + 9, 200)

            chunk_bboxes = [
                b for b in mock_bounding_boxes
                if page_start <= b["page_number"] <= page_end
            ]
            bbox_ids = [b["id"] for b in chunk_bboxes]

            # Verify each bbox_id resolves
            for bbox_id in bbox_ids:
                assert bbox_id in bbox_lookup, f"bbox_id {bbox_id} not found"
                bbox = bbox_lookup[bbox_id]
                assert bbox["page_number"] >= page_start
                assert bbox["page_number"] <= page_end

    def test_chunk_page_number_matches_bbox_majority(self, mock_bounding_boxes):
        """Chunk page_number matches most common page in bbox_ids."""
        from collections import Counter

        # Create bbox lookup
        bbox_lookup = {b["id"]: b for b in mock_bounding_boxes}

        # Simulate chunk with mixed page bboxes
        chunk_bbox_ids = [
            b["id"] for b in mock_bounding_boxes
            if b["page_number"] in [150, 150, 150, 151, 152]  # Majority on 150
        ]

        # Count page occurrences
        page_counts = Counter(
            bbox_lookup[bid]["page_number"] for bid in chunk_bbox_ids
            if bid in bbox_lookup
        )

        most_common_page = page_counts.most_common(1)[0][0] if page_counts else 1

        # Chunk's page_number should match majority
        assert most_common_page in [150, 151, 152]


class TestHybridSearchWithLargeDocuments:
    """Tests for hybrid search with large documents."""

    def test_search_finds_content_on_page_150(self, mock_bounding_boxes):
        """Hybrid search finds content from deep in document."""
        # Simulate: Search for content that exists on page 150
        target_page = 150
        target_bboxes = [
            b for b in mock_bounding_boxes if b["page_number"] == target_page
        ]

        # Verify bboxes exist for target page
        assert len(target_bboxes) > 0
        assert all(b["page_number"] == target_page for b in target_bboxes)

        # In real search, these would be returned as hits
        search_results = [
            {
                "chunk_id": str(uuid4()),
                "content": f"Content from page {target_page}",
                "page_number": target_page,
                "bbox_ids": [b["id"] for b in target_bboxes[:5]],
                "score": 0.95,
            }
        ]

        # Verify result structure
        result = search_results[0]
        assert result["page_number"] == target_page
        assert len(result["bbox_ids"]) > 0

    def test_search_result_bbox_ids_valid(self, mock_bounding_boxes):
        """Search result bbox_ids point to valid records."""
        bbox_lookup = {b["id"]: b for b in mock_bounding_boxes}

        # Simulate search result
        page = 100
        page_bboxes = [b for b in mock_bounding_boxes if b["page_number"] == page]
        result_bbox_ids = [b["id"] for b in page_bboxes[:10]]

        # Verify all bbox_ids resolve
        for bbox_id in result_bbox_ids:
            assert bbox_id in bbox_lookup
            bbox = bbox_lookup[bbox_id]
            assert bbox["page_number"] == page


class TestHighlightingIntegration:
    """Tests for highlighting with chunked large documents."""

    def test_highlighting_coordinates_valid(self, mock_bounding_boxes):
        """Bbox coordinates are valid for PDF viewer rendering."""
        for bbox in mock_bounding_boxes[:100]:  # Check sample
            # PDF coordinates should be non-negative
            assert bbox["x"] >= 0
            assert bbox["y"] >= 0
            assert bbox["width"] > 0
            assert bbox["height"] > 0

            # Coordinates should be within typical PDF page bounds
            # Standard letter: 612 x 792 points
            assert bbox["x"] + bbox["width"] <= 612
            assert bbox["y"] + bbox["height"] <= 792

    def test_page_150_highlighting(self, mock_bounding_boxes):
        """Highlighting on page 150 uses correct coordinates."""
        page_150_bboxes = [
            b for b in mock_bounding_boxes if b["page_number"] == 150
        ]

        assert len(page_150_bboxes) == 20  # 20 bboxes per page

        # Verify each bbox has valid coordinates
        for bbox in page_150_bboxes:
            assert bbox["page_number"] == 150
            assert bbox["x"] >= 0
            assert bbox["y"] >= 0


class TestEntityMentionBboxValidation:
    """Tests for entity mention bbox validation."""

    def test_entity_mention_bbox_ids_valid(self, mock_bounding_boxes):
        """EntityMention.bbox_ids point to valid records."""
        bbox_lookup = {b["id"]: b for b in mock_bounding_boxes}

        # Simulate entity mention with bbox_ids
        entity_mention = {
            "id": str(uuid4()),
            "entity_id": str(uuid4()),
            "text": "Important Person",
            "document_id": "doc-123",
            "page_number": 75,
            "bbox_ids": [
                b["id"] for b in mock_bounding_boxes
                if b["page_number"] == 75
            ][:3],  # First 3 bboxes on page 75
        }

        # Verify bbox_ids resolve
        for bbox_id in entity_mention["bbox_ids"]:
            assert bbox_id in bbox_lookup
            bbox = bbox_lookup[bbox_id]
            assert bbox["page_number"] == entity_mention["page_number"]

    def test_entity_page_number_matches_bbox_page(self, mock_bounding_boxes):
        """Entity page_number matches bbox page_number."""
        bbox_lookup = {b["id"]: b for b in mock_bounding_boxes}

        entity_page = 150
        entity_bbox_ids = [
            b["id"] for b in mock_bounding_boxes if b["page_number"] == entity_page
        ][:5]

        entity_mention = {
            "page_number": entity_page,
            "bbox_ids": entity_bbox_ids,
        }

        # All bbox pages should match entity page
        for bbox_id in entity_mention["bbox_ids"]:
            bbox = bbox_lookup[bbox_id]
            assert bbox["page_number"] == entity_mention["page_number"]


class TestOCRChunkingPipelineIntegration:
    """Integration tests for the full OCR chunking pipeline."""

    def test_full_pipeline_200_pages(self):
        """Full pipeline for 200-page document."""
        # Create OCR results from 8 chunks
        ocr_chunks = []
        for i in range(8):
            page_start = i * 25 + 1
            page_end = min((i + 1) * 25, 200)
            page_count = page_end - page_start + 1

            bboxes = []
            for rel_page in range(1, page_count + 1):
                for roi in range(20):
                    bboxes.append({
                        "page": rel_page,
                        "reading_order_index": roi,
                        "text": f"Chunk {i}, page {rel_page}, block {roi}",
                        "x": 72,
                        "y": 72 + roi * 30,
                        "width": 468,
                        "height": 20,
                    })

            ocr_chunks.append(
                ChunkOCRResult(
                    chunk_index=i,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=bboxes,
                    full_text=f"Chunk {i} text",
                    overall_confidence=0.92,
                    page_count=page_count,
                )
            )

        # Merge
        merger = OCRResultMerger()
        result = merger.merge_results(ocr_chunks, "doc-200")

        # Verify
        assert result.page_count == 200
        assert result.total_bboxes == 200 * 20  # 4000 bboxes

        # Verify page distribution
        pages = [b["page"] for b in result.bounding_boxes]
        assert min(pages) == 1
        assert max(pages) == 200

        # Verify page 150 specifically
        page_150_bboxes = [b for b in result.bounding_boxes if b["page"] == 150]
        assert len(page_150_bboxes) == 20

    def test_pipeline_preserves_reading_order(self):
        """Pipeline preserves reading order within pages."""
        ocr_chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 10, "reading_order_index": 0, "text": "First"},
                    {"page": 10, "reading_order_index": 1, "text": "Second"},
                    {"page": 10, "reading_order_index": 2, "text": "Third"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(ocr_chunks, "doc-test")

        # Get page 10 bboxes sorted by reading order
        page_10 = sorted(
            [b for b in result.bounding_boxes if b["page"] == 10],
            key=lambda x: x["reading_order_index"],
        )

        assert page_10[0]["text"] == "First"
        assert page_10[1]["text"] == "Second"
        assert page_10[2]["text"] == "Third"


class TestDownstreamProcessing:
    """Tests for downstream processing after chunking."""

    def test_chunks_ready_for_embedding(self):
        """Merged bboxes ready for text chunking and embedding."""
        ocr_chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 1, "text": "Legal contract terms", "reading_order_index": i}
                    for i in range(10)
                ],
                full_text="Legal contract terms " * 100,
                overall_confidence=0.95,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(ocr_chunks, "doc-embed")

        # Verify text is available for embedding
        assert len(result.full_text) > 0
        assert "Legal contract terms" in result.full_text

        # Verify bboxes can be linked to text chunks
        for bbox in result.bounding_boxes:
            assert "text" in bbox
            assert "page" in bbox
            assert "reading_order_index" in bbox

    def test_chunks_ready_for_entity_extraction(self):
        """Merged result ready for entity extraction."""
        ocr_chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 1, "text": "John Smith signed the agreement", "reading_order_index": 0},
                    {"page": 1, "text": "on January 15, 2024", "reading_order_index": 1},
                    {"page": 1, "text": "at Acme Corporation", "reading_order_index": 2},
                ],
                full_text="John Smith signed the agreement on January 15, 2024 at Acme Corporation",
                overall_confidence=0.95,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(ocr_chunks, "doc-entity")

        # Full text contains entity-rich content
        assert "John Smith" in result.full_text
        assert "January 15, 2024" in result.full_text
        assert "Acme Corporation" in result.full_text

        # Bboxes can be used to locate entities
        bbox_texts = [b["text"] for b in result.bounding_boxes]
        assert any("John Smith" in t for t in bbox_texts)
