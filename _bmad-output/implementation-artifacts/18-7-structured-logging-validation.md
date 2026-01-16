# Story 18.7: Structured Logging Validation

Status: ready-for-dev

## Story

As an operations engineer,
I want structured logging with correlation IDs,
so that I can debug issues in production.

## Acceptance Criteria

1. **Correlation ID in All Logs**
   - All log entries include document_id and correlation_id
   - Chunk-specific logs include chunk_index
   - Logs are machine-parseable (JSON format via structlog)

2. **Failure Traceability**
   - When failure occurs in chunk processing, logs are searchable by correlation_id
   - Complete processing history is visible via correlation_id filter
   - Exact failure point is identifiable from logs

3. **Performance Metrics Logging**
   - Processing times per chunk are logged
   - Total processing time is logged
   - Metrics are available for monitoring aggregation

## Tasks / Subtasks

- [ ] Task 1: Create logging validation tests (AC: #1, #2, #3)
  - [ ] Create `backend/tests/services/test_structured_logging.py`
  - [ ] Create log capture helper for testing
  - [ ] Verify JSON format compliance

- [ ] Task 2: Write correlation ID tests (AC: #1)
  - [ ] Test document_id present in all logs
  - [ ] Test correlation_id present in all logs
  - [ ] Test chunk_index in chunk-specific logs

- [ ] Task 3: Write failure traceability tests (AC: #2)
  - [ ] Test failure logs include full context
  - [ ] Test correlation_id enables history reconstruction
  - [ ] Test exact failure point identification

- [ ] Task 4: Write performance logging tests (AC: #3)
  - [ ] Test per-chunk timing logged
  - [ ] Test total processing time logged
  - [ ] Test metrics extractable for monitoring

## Dev Notes

### Architecture Compliance

**Structured Logging Test Structure:**
```python
# tests/services/test_structured_logging.py
import pytest
import json
import structlog
from io import StringIO
from contextlib import contextmanager
from unittest.mock import patch

from app.services.pdf_chunker import PDFChunker
from app.services.ocr_chunk_service import OCRChunkService
from app.services.ocr_result_merger import OCRResultMerger


class LogCapture:
    """Capture structlog output for testing."""

    def __init__(self):
        self.logs = []
        self._stream = StringIO()

    @contextmanager
    def capture(self):
        """Context manager to capture logs."""
        # Configure structlog to write to our stream
        processors = [
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]

        old_config = structlog.get_config()

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(0),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(self._stream),
            cache_logger_on_first_use=False,
        )

        try:
            yield
        finally:
            # Parse captured logs
            self._stream.seek(0)
            for line in self._stream:
                if line.strip():
                    try:
                        self.logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            # Restore original config
            structlog.configure(**old_config)

    def get_logs_by_event(self, event: str) -> list:
        """Filter logs by event name."""
        return [log for log in self.logs if log.get("event") == event]

    def get_logs_by_correlation_id(self, correlation_id: str) -> list:
        """Filter logs by correlation_id."""
        return [
            log for log in self.logs
            if log.get("correlation_id") == correlation_id
        ]

    def get_logs_by_document_id(self, document_id: str) -> list:
        """Filter logs by document_id."""
        return [
            log for log in self.logs
            if log.get("document_id") == document_id
        ]


@pytest.fixture
def log_capture():
    return LogCapture()


class TestCorrelationIdLogging:
    """Test that correlation IDs are present in all logs."""

    @pytest.mark.asyncio
    async def test_document_id_in_all_chunk_logs(
        self,
        log_capture,
        mock_chunk_service,
    ):
        """All chunk processing logs should include document_id."""
        document_id = "doc-test-123"

        with log_capture.capture():
            await mock_chunk_service.create_chunk(
                document_id=document_id,
                matter_id="matter-test",
                chunk_index=0,
                page_start=1,
                page_end=25,
            )

        doc_logs = log_capture.get_logs_by_document_id(document_id)
        assert len(doc_logs) > 0, "Should have logs with document_id"

        # All logs related to this operation should have document_id
        for log in doc_logs:
            assert "document_id" in log, f"Log missing document_id: {log}"

    @pytest.mark.asyncio
    async def test_correlation_id_present_in_processing_logs(
        self,
        log_capture,
        mock_chunk_service,
    ):
        """Processing logs should include correlation_id for tracing."""
        correlation_id = "corr-abc-123"
        document_id = "doc-test"

        with log_capture.capture():
            # Simulate processing with correlation_id
            with structlog.contextvars.bind_contextvars(
                correlation_id=correlation_id,
                document_id=document_id,
            ):
                await mock_chunk_service.update_status(
                    document_id=document_id,
                    chunk_index=0,
                    status="processing",
                )

        corr_logs = log_capture.get_logs_by_correlation_id(correlation_id)
        assert len(corr_logs) > 0, "Should have logs with correlation_id"

    @pytest.mark.asyncio
    async def test_chunk_index_in_chunk_specific_logs(
        self,
        log_capture,
        mock_chunk_service,
    ):
        """Chunk-specific logs should include chunk_index."""
        document_id = "doc-test"

        with log_capture.capture():
            for chunk_index in range(3):
                await mock_chunk_service.create_chunk(
                    document_id=document_id,
                    matter_id="matter-test",
                    chunk_index=chunk_index,
                    page_start=chunk_index * 25 + 1,
                    page_end=(chunk_index + 1) * 25,
                )

        # Each chunk creation should log chunk_index
        chunk_logs = [
            log for log in log_capture.logs
            if "chunk_index" in log
        ]

        chunk_indices = {log["chunk_index"] for log in chunk_logs}
        assert chunk_indices == {0, 1, 2}, "All chunk indices should be logged"


class TestFailureTraceability:
    """Test that failures can be traced via logs."""

    @pytest.mark.asyncio
    async def test_failure_logs_include_full_context(
        self,
        log_capture,
        mock_chunk_service,
    ):
        """Failure logs should include all context for debugging."""
        document_id = "doc-fail-test"
        correlation_id = "corr-fail-123"
        chunk_index = 5

        with log_capture.capture():
            with structlog.contextvars.bind_contextvars(
                correlation_id=correlation_id,
                document_id=document_id,
            ):
                # Simulate failure
                try:
                    raise ValueError("Document AI timeout")
                except Exception:
                    structlog.get_logger().error(
                        "chunk_processing_failed",
                        chunk_index=chunk_index,
                        page_start=126,
                        page_end=150,
                        error="Document AI timeout",
                    )

        # Find failure log
        failure_logs = log_capture.get_logs_by_event("chunk_processing_failed")
        assert len(failure_logs) == 1, "Should have one failure log"

        failure_log = failure_logs[0]
        assert failure_log.get("document_id") == document_id
        assert failure_log.get("correlation_id") == correlation_id
        assert failure_log.get("chunk_index") == chunk_index
        assert failure_log.get("page_start") == 126
        assert failure_log.get("page_end") == 150
        assert "error" in failure_log

    @pytest.mark.asyncio
    async def test_correlation_id_enables_history_reconstruction(
        self,
        log_capture,
        mock_chunk_service,
    ):
        """All logs for a request should be filterable by correlation_id."""
        correlation_id = "corr-history-123"
        document_id = "doc-history"

        with log_capture.capture():
            with structlog.contextvars.bind_contextvars(
                correlation_id=correlation_id,
                document_id=document_id,
            ):
                # Simulate full processing lifecycle
                logger = structlog.get_logger()

                logger.info("document_processing_started")
                logger.info("chunk_created", chunk_index=0)
                logger.info("chunk_processing_started", chunk_index=0)
                logger.info("chunk_processing_completed", chunk_index=0)
                logger.info("merge_started")
                logger.info("merge_completed")
                logger.info("document_processing_completed")

        # Reconstruct history
        history = log_capture.get_logs_by_correlation_id(correlation_id)

        assert len(history) == 7, "Should have all lifecycle events"

        events = [log["event"] for log in history]
        assert events == [
            "document_processing_started",
            "chunk_created",
            "chunk_processing_started",
            "chunk_processing_completed",
            "merge_started",
            "merge_completed",
            "document_processing_completed",
        ]


class TestPerformanceMetricsLogging:
    """Test performance metrics are logged."""

    @pytest.mark.asyncio
    async def test_chunk_processing_time_logged(
        self,
        log_capture,
    ):
        """Each chunk should log its processing time."""
        with log_capture.capture():
            logger = structlog.get_logger()

            for chunk_index in range(3):
                logger.info(
                    "chunk_processing_completed",
                    chunk_index=chunk_index,
                    processing_time_seconds=45.2,
                    page_count=25,
                )

        timing_logs = log_capture.get_logs_by_event("chunk_processing_completed")
        assert len(timing_logs) == 3

        for log in timing_logs:
            assert "processing_time_seconds" in log
            assert log["processing_time_seconds"] > 0

    @pytest.mark.asyncio
    async def test_total_processing_time_logged(
        self,
        log_capture,
    ):
        """Total document processing time should be logged."""
        with log_capture.capture():
            logger = structlog.get_logger()

            logger.info(
                "document_processing_completed",
                document_id="doc-test",
                total_time_seconds=180.5,
                split_time_seconds=8.2,
                ocr_time_seconds=165.0,
                merge_time_seconds=7.3,
                chunk_count=17,
                page_count=422,
            )

        completion_logs = log_capture.get_logs_by_event("document_processing_completed")
        assert len(completion_logs) == 1

        log = completion_logs[0]
        assert log["total_time_seconds"] == 180.5
        assert log["split_time_seconds"] == 8.2
        assert log["ocr_time_seconds"] == 165.0
        assert log["merge_time_seconds"] == 7.3

    @pytest.mark.asyncio
    async def test_metrics_extractable_for_monitoring(
        self,
        log_capture,
    ):
        """Metrics should be easily extractable for monitoring systems."""
        with log_capture.capture():
            logger = structlog.get_logger()

            # Log various metrics
            logger.info(
                "chunk_metrics",
                chunk_index=0,
                memory_mb=150.5,
                bbox_count=500,
            )
            logger.info(
                "chunk_metrics",
                chunk_index=1,
                memory_mb=148.2,
                bbox_count=480,
            )

        # Extract metrics
        metric_logs = log_capture.get_logs_by_event("chunk_metrics")

        # Calculate aggregates (what monitoring would do)
        total_bboxes = sum(log["bbox_count"] for log in metric_logs)
        avg_memory = sum(log["memory_mb"] for log in metric_logs) / len(metric_logs)

        assert total_bboxes == 980
        assert abs(avg_memory - 149.35) < 0.01
```

### Structlog Configuration Reference

```python
# app/core/logging.py
import structlog


def configure_logging():
    """Configure structlog for the application."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### References

- [Source: epic-4-testing-validation.md#Story 4.7] - Full AC
- [Source: project-context.md#Logging] - Structlog patterns
- [structlog documentation](https://www.structlog.org/)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

