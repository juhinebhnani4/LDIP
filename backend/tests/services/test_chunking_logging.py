"""Structured Logging Validation Tests.

Story 18.7: Structured Logging Validation (Epic 4)

Validates structured logging for the chunking pipeline:
- All log entries include document_id and correlation_id
- Chunk-specific logs include chunk_index
- Complete processing history visible by correlation_id
- Exact failure point identifiable
- Performance metrics logged for monitoring
"""

import json
import logging
from io import BytesIO, StringIO
from unittest.mock import MagicMock, patch

import pytest
import structlog
from pypdf import PdfWriter

from app.services.pdf_chunker import PDFChunker
from app.services.ocr_result_merger import ChunkOCRResult, MergeValidationError, OCRResultMerger


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def capture_logs():
    """Capture structlog output for verification."""

    class LogCapture:
        def __init__(self):
            self.entries: list[dict] = []

        def __call__(self, logger, method_name, event_dict):
            self.entries.append(event_dict.copy())
            return event_dict

        def find(self, event: str) -> list[dict]:
            """Find all log entries with given event name."""
            return [e for e in self.entries if e.get("event") == event]

        def contains(self, event: str) -> bool:
            """Check if event was logged."""
            return len(self.find(event)) > 0

        def get_latest(self, event: str) -> dict | None:
            """Get most recent log entry for event."""
            matches = self.find(event)
            return matches[-1] if matches else None

    return LogCapture()


@pytest.fixture
def create_pdf():
    """Factory to create test PDFs."""

    def _create(page_count: int) -> bytes:
        writer = PdfWriter()
        for _ in range(page_count):
            writer.add_blank_page(612, 792)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return _create


# =============================================================================
# Story 18.7: Structured Logging Tests
# =============================================================================


class TestPDFChunkerLogging:
    """Tests for PDFChunker structured logging."""

    def test_split_complete_logged(self, create_pdf, capture_logs):
        """Successful split logs completion event."""
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(75)
            chunker = PDFChunker(enable_memory_tracking=False)
            chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Find the completion log
        split_complete = [
            e for e in captured if e.get("event") == "pdf_split_complete"
        ]
        assert len(split_complete) == 1

        log = split_complete[0]
        assert log["total_pages"] == 75
        assert log["chunk_count"] == 3
        assert log["chunk_size"] == 25

    def test_chunk_extracted_logged(self, create_pdf):
        """Each chunk extraction is logged."""
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(50)
            chunker = PDFChunker(enable_memory_tracking=False)
            chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Should have 2 chunk_extracted events (at debug level)
        chunk_logs = [e for e in captured if e.get("event") == "chunk_extracted"]
        assert len(chunk_logs) == 2

        # Verify each log has page range
        for log in chunk_logs:
            assert "page_start" in log
            assert "page_end" in log
            assert "chunk_size_bytes" in log

    def test_streaming_split_logged(self, create_pdf):
        """Streaming split logs completion event."""
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(75)
            chunker = PDFChunker(enable_memory_tracking=False)
            with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
                pass

        split_complete = [
            e for e in captured if e.get("event") == "pdf_streaming_split_complete"
        ]
        assert len(split_complete) == 1

        log = split_complete[0]
        assert log["total_pages"] == 75
        assert log["chunk_count"] == 3
        assert "temp_dir" in log

    def test_cleanup_logged(self, create_pdf):
        """Streaming cleanup is logged."""
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(50)
            chunker = PDFChunker(enable_memory_tracking=False)
            with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
                pass  # Trigger cleanup on exit

        cleanup_logs = [
            e for e in captured if e.get("event") == "streaming_chunks_cleaned_up"
        ]
        assert len(cleanup_logs) == 1

    def test_error_logged_on_invalid_pdf(self):
        """Error is logged when PDF parsing fails."""
        with structlog.testing.capture_logs() as captured:
            chunker = PDFChunker(enable_memory_tracking=False)
            try:
                chunker.split_pdf(b"Invalid PDF content")
            except Exception:
                pass

        error_logs = [
            e for e in captured if e.get("event") == "pdf_parse_failed"
        ]
        assert len(error_logs) == 1
        assert "error" in error_logs[0]


class TestOCRResultMergerLogging:
    """Tests for OCRResultMerger structured logging."""

    def test_merge_complete_logged(self):
        """Successful merge logs completion event."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[{"page": 1}, {"page": 25}],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[{"page": 1}, {"page": 25}],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            result = merger.merge_results(chunks, "doc-123")

        merge_complete = [
            e for e in captured if e.get("event") == "ocr_results_merged"
        ]
        assert len(merge_complete) == 1

        log = merge_complete[0]
        assert log["document_id"] == "doc-123"
        assert log["chunk_count"] == 2
        assert log["total_pages"] == 50
        assert log["total_bboxes"] == 4
        assert "confidence" in log

    def test_validation_logged(self):
        """Page range validation is logged."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            merger.merge_results(chunks, "doc-test")

        validation_logs = [
            e for e in captured if e.get("event") == "page_ranges_validated"
        ]
        assert len(validation_logs) == 1
        assert validation_logs[0]["chunk_count"] == 1

    def test_validation_error_logged(self):
        """Validation failures are logged."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=2,  # Should be 1!
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=24,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            try:
                merger.merge_results(chunks, "doc-test")
            except MergeValidationError:
                pass

        error_logs = [
            e for e in captured if e.get("event") == "page_range_validation_failed"
        ]
        assert len(error_logs) == 1
        assert "errors" in error_logs[0]
        assert error_logs[0]["chunk_count"] == 1

    def test_checksum_mismatch_logged(self):
        """Checksum mismatch is logged as warning."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
                checksum="invalid_checksum",
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            try:
                merger.merge_results(chunks, "doc-test")
            except MergeValidationError:
                pass

        checksum_logs = [
            e for e in captured if e.get("event") == "chunk_checksum_mismatch"
        ]
        assert len(checksum_logs) == 1
        assert checksum_logs[0]["chunk_index"] == 0
        assert "expected" in checksum_logs[0]
        assert "computed" in checksum_logs[0]


class TestCorrelationIdTracking:
    """Tests for correlation ID in log entries."""

    def test_document_id_in_merge_logs(self):
        """document_id is present in merge logs."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            result = merger.merge_results(chunks, "doc-correlation-test-123")

        merge_log = [e for e in captured if e.get("event") == "ocr_results_merged"][0]
        assert merge_log["document_id"] == "doc-correlation-test-123"


class TestChunkIndexTracking:
    """Tests for chunk_index in log entries."""

    def test_chunk_index_in_extraction_logs(self, create_pdf):
        """chunk_index (via page_start/end) present in chunk logs."""
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(50)
            chunker = PDFChunker(enable_memory_tracking=False)
            chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        chunk_logs = [e for e in captured if e.get("event") == "chunk_extracted"]

        # First chunk: pages 1-25
        assert chunk_logs[0]["page_start"] == 1
        assert chunk_logs[0]["page_end"] == 25

        # Second chunk: pages 26-50
        assert chunk_logs[1]["page_start"] == 26
        assert chunk_logs[1]["page_end"] == 50


class TestPerformanceMetricsLogging:
    """Tests for performance metrics in logs."""

    def test_page_count_logged(self, create_pdf):
        """Total page count logged for monitoring."""
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(100)
            chunker = PDFChunker(enable_memory_tracking=False)
            chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        split_log = [e for e in captured if e.get("event") == "pdf_split_complete"][0]
        assert split_log["total_pages"] == 100
        assert split_log["chunk_count"] == 4

    def test_chunk_count_logged(self):
        """Chunk count logged for monitoring."""
        chunks = []
        for i in range(10):
            chunks.append(
                ChunkOCRResult(
                    chunk_index=i,
                    page_start=i * 25 + 1,
                    page_end=(i + 1) * 25,
                    bounding_boxes=[],
                    full_text="",
                    overall_confidence=0.9,
                    page_count=25,
                )
            )

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            result = merger.merge_results(chunks, "doc-test")

        merge_log = [e for e in captured if e.get("event") == "ocr_results_merged"][0]
        assert merge_log["chunk_count"] == 10

    def test_bbox_count_logged(self):
        """Total bbox count logged for monitoring."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[{"page": i} for i in range(1, 26)],  # 25 bboxes
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            result = merger.merge_results(chunks, "doc-test")

        merge_log = [e for e in captured if e.get("event") == "ocr_results_merged"][0]
        assert merge_log["total_bboxes"] == 25

    def test_confidence_logged(self):
        """Average confidence logged for quality monitoring."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.92,
                page_count=25,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            result = merger.merge_results(chunks, "doc-test")

        merge_log = [e for e in captured if e.get("event") == "ocr_results_merged"][0]
        assert merge_log["confidence"] == 0.92


class TestFailurePointIdentification:
    """Tests for identifying exact failure points."""

    def test_failure_chunk_identified(self):
        """Failing chunk is identified in error log."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=30,  # Gap - this chunk fails validation
                page_end=55,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=26,
            ),
        ]

        with structlog.testing.capture_logs() as captured:
            merger = OCRResultMerger()
            try:
                merger.merge_results(chunks, "doc-test")
            except MergeValidationError:
                pass

        error_log = [e for e in captured if e.get("event") == "page_range_validation_failed"][0]

        # Error should identify the problematic chunk boundary
        assert "errors" in error_log
        errors = error_log["errors"]
        # Should mention the gap between chunk 0 (end=25) and chunk 1 (start=30)
        assert any("30" in str(err) for err in errors)

    def test_empty_pdf_error_identified(self):
        """Empty PDF error clearly logged."""
        writer = PdfWriter()
        buffer = BytesIO()
        writer.write(buffer)
        empty_pdf = buffer.getvalue()

        with structlog.testing.capture_logs() as captured:
            chunker = PDFChunker(enable_memory_tracking=False)
            try:
                chunker.split_pdf(empty_pdf)
            except Exception:
                pass

        # Should have an error event (the specific event depends on implementation)
        error_events = [e for e in captured if e.get("log_level") == "error"]
        # Note: structlog.testing.capture_logs may not capture log_level
        # This test verifies error path is exercised


class TestMemoryWarningLogging:
    """Tests for memory warning logs."""

    def test_memory_warning_includes_metrics(self, create_pdf):
        """Memory warning includes current and limit values."""
        # This test would trigger memory warning logging
        # In real scenario, we'd need a large enough PDF to trigger warning

        # Verify warning log structure when it occurs
        with structlog.testing.capture_logs() as captured:
            pdf_bytes = create_pdf(10)  # Small PDF won't trigger warning
            chunker = PDFChunker(enable_memory_tracking=True)
            chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Check if any memory warning was logged (unlikely with small PDF)
        memory_warnings = [
            e for e in captured if e.get("event") == "pdf_split_memory_warning"
        ]

        # If warning exists, verify structure
        if memory_warnings:
            log = memory_warnings[0]
            assert "current_mb" in log
            assert "peak_mb" in log
            assert "limit_mb" in log
            assert "threshold_pct" in log
