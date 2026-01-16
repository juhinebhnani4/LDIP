# Story 18.4: Integration Tests with Sample Documents

Status: ready-for-dev

## Story

As a QA engineer,
I want integration tests with real sample documents,
so that the full pipeline is validated end-to-end.

## Acceptance Criteria

1. **Sample Document Processing**
   - Sample PDFs of 50, 100, 200, and 422 pages process successfully
   - OCR completes without errors for each document size
   - Bounding box count matches expected (~20 per page)
   - All page numbers are absolute and in valid range

2. **Downstream Processing Validation**
   - Chunking task completes successfully after OCR
   - Embedding task processes all chunks
   - Entity extraction identifies entities across pages

3. **Citation Highlighting Tests (PRE-MORTEM)**
   - Citation highlighting works correctly on processed documents
   - Correct text is highlighted on correct page
   - Navigation to page N shows expected content
   - Cross-chunk boundary citations work (page 25 to page 26)

4. **Viewer Coordinate Validation**
   - Highlighting coordinates are valid for PDF viewer
   - Bounding boxes render at correct positions
   - Multi-page document navigation works

## Tasks / Subtasks

- [ ] Task 1: Create sample PDF fixtures (AC: #1)
  - [ ] Create or source 50-page sample PDF
  - [ ] Create or source 100-page sample PDF
  - [ ] Create or source 200-page sample PDF
  - [ ] Create or source 422-page sample PDF (matches original failure)
  - [ ] Store in `backend/tests/fixtures/large_pdfs/`

- [ ] Task 2: Write full pipeline integration tests (AC: #1, #2)
  - [ ] Create `backend/tests/integration/test_large_document_pipeline.py`
  - [ ] Test OCR → chunk → embed → entity extraction pipeline
  - [ ] Verify bounding box counts per document
  - [ ] Verify page number ranges

- [ ] Task 3: Write citation highlighting tests (AC: #3)
  - [ ] Test citation on single chunk
  - [ ] Test citation spanning chunk boundary (pages 25-26)
  - [ ] Test citation in last chunk
  - [ ] Verify bbox coordinates map to correct page

- [ ] Task 4: Write viewer coordinate tests (AC: #4)
  - [ ] Test bbox coordinates are within page bounds
  - [ ] Test normalized coordinates (0-1 range)
  - [ ] Test page navigation with highlighting

## Dev Notes

### Architecture Compliance

**Integration Test Structure:**
```python
# tests/integration/test_large_document_pipeline.py
import pytest
from pathlib import Path

from app.services.pdf_chunker import PDFChunker
from app.services.ocr_chunk_service import OCRChunkService
from app.services.ocr_result_merger import OCRResultMerger


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "large_pdfs"


@pytest.fixture
def sample_50_page_pdf():
    """50-page sample PDF for testing."""
    return FIXTURES_DIR / "sample_50_pages.pdf"


@pytest.fixture
def sample_100_page_pdf():
    """100-page sample PDF for testing."""
    return FIXTURES_DIR / "sample_100_pages.pdf"


@pytest.fixture
def sample_200_page_pdf():
    """200-page sample PDF for testing."""
    return FIXTURES_DIR / "sample_200_pages.pdf"


@pytest.fixture
def sample_422_page_pdf():
    """422-page sample PDF matching original failure case."""
    return FIXTURES_DIR / "sample_422_pages.pdf"


class TestLargeDocumentPipeline:
    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.parametrize("page_count,fixture_name", [
        (50, "sample_50_page_pdf"),
        (100, "sample_100_page_pdf"),
        (200, "sample_200_page_pdf"),
        (422, "sample_422_page_pdf"),
    ])
    async def test_full_pipeline_processes_document(
        self,
        page_count: int,
        fixture_name: str,
        request,
        mock_document_ai,
        test_supabase_client,
    ):
        """Test full pipeline from PDF split to OCR merge."""
        pdf_path = request.getfixturevalue(fixture_name)

        # Step 1: Split PDF into chunks
        chunker = PDFChunker(chunk_size=25)
        chunks = await chunker.split_pdf(pdf_path)

        expected_chunks = (page_count + 24) // 25  # ceiling division
        assert len(chunks) == expected_chunks, (
            f"Expected {expected_chunks} chunks for {page_count} pages, "
            f"got {len(chunks)}"
        )

        # Step 2: Process each chunk (mocked Document AI)
        chunk_results = []
        for chunk_bytes, chunk_index, page_start, page_end in chunks:
            # Mock OCR result with ~20 bboxes per page
            pages_in_chunk = page_end - page_start + 1
            bboxes = []
            for rel_page in range(1, pages_in_chunk + 1):
                for reading_idx in range(20):  # ~20 bboxes per page
                    bboxes.append({
                        "page": rel_page,
                        "reading_order_index": reading_idx,
                        "text": f"Text on page {page_start + rel_page - 1}",
                        "x": 0.1,
                        "y": 0.1 + (reading_idx * 0.04),
                        "width": 0.8,
                        "height": 0.03,
                    })

            chunk_results.append({
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "bounding_boxes": bboxes,
                "full_text": f"Chunk {chunk_index} text content",
                "page_count": pages_in_chunk,
            })

        # Step 3: Merge results
        merger = OCRResultMerger()
        merged = merger.merge_results(chunk_results, "doc-test")

        # Verify bbox count (~20 per page)
        expected_bboxes = page_count * 20
        assert len(merged.bounding_boxes) == expected_bboxes, (
            f"Expected ~{expected_bboxes} bboxes, got {len(merged.bounding_boxes)}"
        )

        # Verify all pages are present and in range
        pages_present = {bbox["page"] for bbox in merged.bounding_boxes}
        assert pages_present == set(range(1, page_count + 1)), (
            "Not all pages present in merged result"
        )


class TestCrossChunkBoundaryCitations:
    """PRE-MORTEM: Test citations spanning chunk boundaries."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_citation_at_chunk_boundary_25_26(
        self,
        sample_50_page_pdf,
        mock_document_ai,
    ):
        """Test citation that spans pages 25-26 (chunk boundary)."""
        # Process document
        # ... setup code ...

        # Find bboxes at pages 25 and 26
        page_25_bboxes = [
            b for b in merged.bounding_boxes if b["page"] == 25
        ]
        page_26_bboxes = [
            b for b in merged.bounding_boxes if b["page"] == 26
        ]

        assert len(page_25_bboxes) > 0, "No bboxes on page 25 (end of chunk 1)"
        assert len(page_26_bboxes) > 0, "No bboxes on page 26 (start of chunk 2)"

        # Verify coordinates are valid
        for bbox in page_25_bboxes + page_26_bboxes:
            assert 0 <= bbox["x"] <= 1, f"Invalid x coordinate: {bbox['x']}"
            assert 0 <= bbox["y"] <= 1, f"Invalid y coordinate: {bbox['y']}"
            assert bbox["width"] > 0, "Width must be positive"
            assert bbox["height"] > 0, "Height must be positive"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_citation_at_chunk_boundary_50_51(
        self,
        sample_100_page_pdf,
        mock_document_ai,
    ):
        """Test citation that spans pages 50-51 (chunk 2 to chunk 3)."""
        # Similar test for second chunk boundary
        ...


class TestViewerCoordinateValidation:
    """Validate bbox coordinates work in PDF viewer."""

    @pytest.mark.integration
    def test_bbox_coordinates_normalized(self, merged_result):
        """All bbox coordinates should be in 0-1 range (normalized)."""
        for bbox in merged_result.bounding_boxes:
            assert 0 <= bbox["x"] <= 1, f"x out of range: {bbox['x']}"
            assert 0 <= bbox["y"] <= 1, f"y out of range: {bbox['y']}"
            assert 0 < bbox["width"] <= 1, f"width invalid: {bbox['width']}"
            assert 0 < bbox["height"] <= 1, f"height invalid: {bbox['height']}"
            # x + width should not exceed 1
            assert bbox["x"] + bbox["width"] <= 1.01, (  # small tolerance
                f"bbox extends past page: x={bbox['x']}, width={bbox['width']}"
            )

    @pytest.mark.integration
    def test_page_navigation_with_highlighting(
        self,
        merged_result,
        mock_pdf_viewer,
    ):
        """Test page navigation shows correct highlight."""
        # Navigate to page 150
        page_150_bboxes = [
            b for b in merged_result.bounding_boxes if b["page"] == 150
        ]

        # Verify bboxes can be rendered
        for bbox in page_150_bboxes:
            highlight = mock_pdf_viewer.render_highlight(
                page=bbox["page"],
                x=bbox["x"],
                y=bbox["y"],
                width=bbox["width"],
                height=bbox["height"],
            )
            assert highlight is not None, "Failed to render highlight"
```

### Sample PDF Generation

```python
# scripts/generate_sample_pdfs.py
"""Generate sample PDFs for integration testing."""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_sample_pdf(output_path: str, num_pages: int):
    """Create a sample PDF with specified number of pages."""
    c = canvas.Canvas(output_path, pagesize=letter)

    for page_num in range(1, num_pages + 1):
        c.drawString(100, 750, f"Page {page_num} of {num_pages}")
        c.drawString(100, 700, f"This is sample content on page {page_num}")

        # Add some text blocks for OCR to find
        y_pos = 650
        for i in range(15):  # ~15 text blocks per page
            c.drawString(100, y_pos, f"Text block {i+1} on page {page_num}")
            y_pos -= 30

        c.showPage()

    c.save()


if __name__ == "__main__":
    create_sample_pdf("tests/fixtures/large_pdfs/sample_50_pages.pdf", 50)
    create_sample_pdf("tests/fixtures/large_pdfs/sample_100_pages.pdf", 100)
    create_sample_pdf("tests/fixtures/large_pdfs/sample_200_pages.pdf", 200)
    create_sample_pdf("tests/fixtures/large_pdfs/sample_422_pages.pdf", 422)
```

### Testing Requirements

**Test Markers:**
```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    "slow: marks tests as slow running",
]
```

### References

- [Source: epic-4-testing-validation.md#Story 4.4] - Full AC
- [Source: Story 16.3] - OCRResultMerger
- [Source: Story 16.2] - PDFChunker

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

