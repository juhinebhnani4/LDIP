"""Tests for reliability event logging (Epic 6: Reliability Monitoring & Diagnostics).

Tests cover:
- Story 6.1: Citation page accuracy logging
- Story 6.2: SSE error rate logging
- Story 6.3: WebSocket health metrics logging
- Story 6.4: Entity extraction success rate logging
- Story 6.5: Comprehensive reliability event logging schema

All tests verify that logs follow the consistent schema required by NFR10/NFR14:
- event_type, user_id, matter_id, timestamp, details (JSON)
"""

import io
import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import structlog

from app.core.reliability_logging import (
    ReliabilityEventType,
    log_citation_page_detection,
    log_citation_page_fallback,
    log_entity_extraction_result,
    log_reliability_event,
    log_request_slow,
    log_request_timeout,
    log_sse_parse_error,
    log_sse_stream_status,
    log_websocket_connected,
    log_websocket_disconnected,
    log_websocket_event,
    log_websocket_reconnect_attempt,
    log_websocket_reconnect_failed,
)


@pytest.fixture
def log_capture():
    """Fixture to capture log output as JSON."""
    log_output = io.StringIO()

    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=log_output),
        cache_logger_on_first_use=False,
    )

    yield log_output

    structlog.reset_defaults()


def parse_log_output(log_output: io.StringIO) -> dict:
    """Parse the captured log output as JSON."""
    log_output.seek(0)
    log_line = log_output.read().strip()
    return json.loads(log_line)


class TestReliabilityEventType:
    """Tests for ReliabilityEventType enum."""

    def test_all_event_types_are_strings(self):
        """Verify all event types are string values for JSON serialization."""
        for event_type in ReliabilityEventType:
            assert isinstance(event_type.value, str)
            assert len(event_type.value) > 0

    def test_citation_events_exist(self):
        """Verify citation-related event types exist (Story 6.1)."""
        assert ReliabilityEventType.CITATION_PAGE_DETECTED_BBOX
        assert ReliabilityEventType.CITATION_PAGE_DETECTED_CHUNK
        assert ReliabilityEventType.CITATION_PAGE_FALLBACK
        assert ReliabilityEventType.CITATION_PAGE_MISSING

    def test_sse_events_exist(self):
        """Verify SSE-related event types exist (Story 6.2)."""
        assert ReliabilityEventType.SSE_JSON_PARSE_FAILED
        assert ReliabilityEventType.SSE_MAX_ERRORS_EXCEEDED
        assert ReliabilityEventType.SSE_STREAM_INTERRUPTED
        assert ReliabilityEventType.SSE_STREAM_COMPLETE

    def test_websocket_events_exist(self):
        """Verify WebSocket-related event types exist (Story 6.3)."""
        assert ReliabilityEventType.WEBSOCKET_CONNECTED
        assert ReliabilityEventType.WEBSOCKET_DISCONNECTED
        assert ReliabilityEventType.WEBSOCKET_RECONNECT_ATTEMPT
        assert ReliabilityEventType.WEBSOCKET_RECONNECT_SUCCESS
        assert ReliabilityEventType.WEBSOCKET_RECONNECT_FAILED
        assert ReliabilityEventType.WEBSOCKET_HEARTBEAT_TIMEOUT

    def test_entity_extraction_events_exist(self):
        """Verify entity extraction event types exist (Story 6.4)."""
        assert ReliabilityEventType.ENTITY_EXTRACTION_SUCCESS
        assert ReliabilityEventType.ENTITY_EXTRACTION_ERROR
        assert ReliabilityEventType.ENTITY_EXTRACTION_EMPTY


class TestLogReliabilityEvent:
    """Tests for the core log_reliability_event function (Story 6.5)."""

    def test_includes_event_category(self, log_capture):
        """Test that all reliability events include event_category='reliability'."""
        log_reliability_event(ReliabilityEventType.CITATION_PAGE_DETECTED_BBOX)

        log_data = parse_log_output(log_capture)
        assert log_data["event_category"] == "reliability"

    def test_includes_event_type(self, log_capture):
        """Test that event_type is included in log."""
        log_reliability_event(ReliabilityEventType.WEBSOCKET_CONNECTED)

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_connected"

    def test_includes_timestamp(self, log_capture):
        """Test that timestamp is included in log (NFR10)."""
        log_reliability_event(ReliabilityEventType.SSE_JSON_PARSE_FAILED)

        log_data = parse_log_output(log_capture)
        assert "timestamp" in log_data
        # Verify it's ISO format
        datetime.fromisoformat(log_data["timestamp"].replace("Z", "+00:00"))

    def test_includes_user_id_when_provided(self, log_capture):
        """Test that user_id is included when provided (NFR10)."""
        log_reliability_event(
            ReliabilityEventType.SSE_STREAM_COMPLETE,
            user_id="user-123",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["user_id"] == "user-123"

    def test_includes_matter_id_when_provided(self, log_capture):
        """Test that matter_id is included when provided (NFR10)."""
        log_reliability_event(
            ReliabilityEventType.ENTITY_EXTRACTION_SUCCESS,
            matter_id="matter-456",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["matter_id"] == "matter-456"

    def test_includes_session_id_when_provided(self, log_capture):
        """Test that session_id is included when provided (NFR12)."""
        log_reliability_event(
            ReliabilityEventType.SSE_JSON_PARSE_FAILED,
            session_id="sse_abc123",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["session_id"] == "sse_abc123"

    def test_includes_additional_details(self, log_capture):
        """Test that additional kwargs are included as details."""
        log_reliability_event(
            ReliabilityEventType.CITATION_PAGE_DETECTED_BBOX,
            page_number=42,
            detection_method="bbox",
            confidence=0.95,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["page_number"] == 42
        assert log_data["detection_method"] == "bbox"
        assert log_data["confidence"] == 0.95


class TestCitationPageLogging:
    """Tests for citation page accuracy logging (Story 6.1)."""

    def test_log_citation_page_detection_bbox(self, log_capture):
        """Test logging bbox-based page detection."""
        log_citation_page_detection(
            matter_id="matter-123",
            document_id="doc-456",
            detection_method="bbox",
            page_number=15,
            event_id="event-789",
            bbox_id="bbox-abc",
            confidence=0.92,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "citation_page_detected_bbox"
        assert log_data["matter_id"] == "matter-123"
        assert log_data["document_id"] == "doc-456"
        assert log_data["detection_method"] == "bbox"
        assert log_data["page_number"] == 15

    def test_log_citation_page_detection_chunk(self, log_capture):
        """Test logging chunk-based page detection."""
        log_citation_page_detection(
            matter_id="matter-123",
            document_id="doc-456",
            detection_method="chunk",
            page_number=10,
            chunk_id="chunk-xyz",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "citation_page_detected_chunk"
        assert log_data["detection_method"] == "chunk"

    def test_log_citation_page_detection_missing(self, log_capture):
        """Test logging when detection method is unknown."""
        log_citation_page_detection(
            matter_id="matter-123",
            document_id="doc-456",
            detection_method="unknown",
            page_number=None,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "citation_page_missing"

    def test_log_citation_page_fallback(self, log_capture):
        """Test logging fallback events (NFR11)."""
        log_citation_page_fallback(
            matter_id="matter-123",
            document_id="doc-456",
            event_id="event-789",
            reason="no_bbox_data",
            chunk_page=5,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "citation_page_fallback"
        assert log_data["fallback_reason"] == "no_bbox_data"
        assert log_data["chunk_page"] == 5


class TestSSEErrorLogging:
    """Tests for SSE error rate logging (Story 6.2)."""

    def test_log_sse_parse_error_basic(self, log_capture):
        """Test logging SSE parse error with basic context."""
        log_sse_parse_error(
            user_id="user-123",
            matter_id="matter-456",
            session_id="sse_abc123",
            error_type="sse_json_parse_failed",
            error_message="Unexpected token",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "sse_json_parse_failed"
        assert log_data["session_id"] == "sse_abc123"
        assert log_data["error_message"] == "Unexpected token"

    def test_log_sse_parse_error_truncates_raw_chunk(self, log_capture):
        """Test that raw_chunk is truncated to 1KB."""
        long_chunk = "x" * 2000  # 2KB of data

        log_sse_parse_error(
            user_id="user-123",
            matter_id="matter-456",
            session_id="sse_abc123",
            error_type="sse_json_parse_failed",
            error_message="Parse error",
            raw_chunk=long_chunk,
        )

        log_data = parse_log_output(log_capture)
        assert len(log_data["raw_chunk"]) == 1024

    def test_log_sse_parse_error_max_errors_type(self, log_capture):
        """Test logging max errors exceeded event."""
        log_sse_parse_error(
            user_id="user-123",
            matter_id="matter-456",
            session_id="sse_abc123",
            error_type="sse_max_errors_exceeded",
            error_message="Aborted after 5 parse errors",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "sse_max_errors_exceeded"

    def test_log_sse_stream_status_complete(self, log_capture):
        """Test logging stream completion."""
        log_sse_stream_status(
            user_id="user-123",
            matter_id="matter-456",
            session_id="sse_abc123",
            status="complete",
            parse_error_count=0,
            total_chunks=42,
            duration_ms=3500,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "sse_stream_complete"
        assert log_data["stream_status"] == "complete"
        assert log_data["total_chunks"] == 42
        assert log_data["duration_ms"] == 3500

    def test_log_sse_stream_status_interrupted(self, log_capture):
        """Test logging stream interruption."""
        log_sse_stream_status(
            user_id="user-123",
            matter_id="matter-456",
            session_id="sse_abc123",
            status="interrupted",
            parse_error_count=3,
            total_chunks=15,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "sse_stream_interrupted"
        assert log_data["parse_error_count"] == 3


class TestWebSocketHealthLogging:
    """Tests for WebSocket health metrics logging (Story 6.3)."""

    def test_log_websocket_connected(self, log_capture):
        """Test logging successful connection."""
        log_websocket_connected(
            user_id="user-123",
            matter_id="matter-456",
            session_id="ws_abc123",
            was_reconnect=False,
            previous_attempts=0,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_connected"
        assert log_data["was_reconnect"] is False

    def test_log_websocket_connected_after_reconnect(self, log_capture):
        """Test logging successful reconnection (NFR13)."""
        log_websocket_connected(
            user_id="user-123",
            matter_id="matter-456",
            session_id="ws_abc123",
            was_reconnect=True,
            previous_attempts=3,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_reconnect_success"
        assert log_data["previous_attempts"] == 3

    def test_log_websocket_disconnected(self, log_capture):
        """Test logging disconnection."""
        log_websocket_disconnected(
            user_id="user-123",
            matter_id="matter-456",
            session_id="ws_abc123",
            reason="client_disconnected",
            code=1000,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_disconnected"
        assert log_data["disconnect_reason"] == "client_disconnected"
        assert log_data["close_code"] == 1000

    def test_log_websocket_reconnect_attempt(self, log_capture):
        """Test logging reconnection attempt."""
        log_websocket_reconnect_attempt(
            user_id="user-123",
            matter_id="matter-456",
            session_id="ws_abc123",
            attempt=2,
            max_attempts=5,
            delay_ms=2000,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_reconnect_attempt"
        assert log_data["reconnect_attempt"] == 2
        assert log_data["max_attempts"] == 5

    def test_log_websocket_reconnect_failed(self, log_capture):
        """Test logging reconnection failure."""
        log_websocket_reconnect_failed(
            user_id="user-123",
            matter_id="matter-456",
            session_id="ws_abc123",
            attempts=5,
            reason="max_attempts_exceeded",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_reconnect_failed"
        assert log_data["failure_reason"] == "max_attempts_exceeded"

    def test_log_websocket_event_heartbeat_timeout(self, log_capture):
        """Test logging heartbeat timeout."""
        log_websocket_event(
            user_id="user-123",
            matter_id="matter-456",
            session_id="ws_abc123",
            event_type=ReliabilityEventType.WEBSOCKET_HEARTBEAT_TIMEOUT,
            reason="ping_failed",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "websocket_heartbeat_timeout"
        assert log_data["reason"] == "ping_failed"


class TestEntityExtractionLogging:
    """Tests for entity extraction success rate logging (Story 6.4)."""

    def test_log_entity_extraction_success(self, log_capture):
        """Test logging successful extraction."""
        log_entity_extraction_result(
            matter_id="matter-123",
            document_id="doc-456",
            status="success",
            entity_count=5,
            entity_types={"PERSON": 3, "ORG": 2},
            processing_time_ms=1500,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "entity_extraction_success"
        assert log_data["entity_count"] == 5
        assert log_data["entity_types"] == {"PERSON": 3, "ORG": 2}
        assert log_data["processing_time_ms"] == 1500

    def test_log_entity_extraction_error(self, log_capture):
        """Test logging extraction error."""
        log_entity_extraction_result(
            matter_id="matter-123",
            document_id="doc-456",
            status="error",
            error_message="API rate limited",
            error_type="RateLimitError",
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "entity_extraction_error"
        assert log_data["error_message"] == "API rate limited"
        assert log_data["error_type"] == "RateLimitError"

    def test_log_entity_extraction_empty(self, log_capture):
        """Test logging empty extraction result."""
        log_entity_extraction_result(
            matter_id="matter-123",
            document_id="doc-456",
            status="empty",
            entity_count=0,
            processing_time_ms=800,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "entity_extraction_empty"
        assert log_data["entity_count"] == 0


class TestRequestTimeoutLogging:
    """Tests for request timeout logging (supporting Epic 5)."""

    def test_log_request_timeout(self, log_capture):
        """Test logging request timeout."""
        log_request_timeout(
            user_id="user-123",
            matter_id="matter-456",
            endpoint="/api/chat/stream",
            timeout_ms=30000,
            duration_ms=30500,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "request_timeout"
        assert log_data["endpoint"] == "/api/chat/stream"
        assert log_data["timeout_ms"] == 30000

    def test_log_request_slow(self, log_capture):
        """Test logging slow request."""
        log_request_slow(
            user_id="user-123",
            matter_id="matter-456",
            endpoint="/api/matters/documents",
            threshold_ms=5000,
            duration_ms=8000,
        )

        log_data = parse_log_output(log_capture)
        assert log_data["event_type"] == "request_slow"
        assert log_data["threshold_ms"] == 5000
        assert log_data["duration_ms"] == 8000


class TestLogSchemaConsistency:
    """Tests verifying consistent schema across all event types (Story 6.5, NFR14)."""

    def test_all_events_have_event_category(self, log_capture):
        """Verify all events include event_category for filtering."""
        test_cases = [
            (ReliabilityEventType.CITATION_PAGE_DETECTED_BBOX, {}),
            (ReliabilityEventType.SSE_JSON_PARSE_FAILED, {}),
            (ReliabilityEventType.WEBSOCKET_CONNECTED, {}),
            (ReliabilityEventType.ENTITY_EXTRACTION_SUCCESS, {}),
            (ReliabilityEventType.REQUEST_TIMEOUT, {}),
        ]

        for event_type, kwargs in test_cases:
            log_capture.seek(0)
            log_capture.truncate(0)

            log_reliability_event(event_type, **kwargs)
            log_data = parse_log_output(log_capture)

            assert log_data["event_category"] == "reliability", (
                f"Event type {event_type} missing event_category"
            )

    def test_all_events_have_timestamp(self, log_capture):
        """Verify all events include ISO timestamp (NFR10)."""
        log_reliability_event(
            ReliabilityEventType.SSE_STREAM_COMPLETE,
            session_id="test",
        )

        log_data = parse_log_output(log_capture)

        # Verify timestamp exists and is valid ISO format
        assert "timestamp" in log_data
        timestamp = log_data["timestamp"]
        # Should not raise
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_events_can_be_filtered_by_type(self, log_capture):
        """Verify events can be filtered by event_type for dashboards (NFR14)."""
        # This test verifies the logging format supports Axiom/logging queries
        log_reliability_event(
            ReliabilityEventType.CITATION_PAGE_FALLBACK,
            matter_id="test-matter",
        )

        log_data = parse_log_output(log_capture)

        # Support staff should be able to query:
        # event_category == "reliability" AND event_type == "citation_page_fallback"
        assert log_data["event_category"] == "reliability"
        assert log_data["event_type"] == "citation_page_fallback"

    def test_events_can_be_filtered_by_matter(self, log_capture):
        """Verify events can be filtered by matter_id (NFR14)."""
        log_reliability_event(
            ReliabilityEventType.ENTITY_EXTRACTION_SUCCESS,
            matter_id="specific-matter-id",
        )

        log_data = parse_log_output(log_capture)

        # Support staff should be able to query: matter_id == "specific-matter-id"
        assert log_data["matter_id"] == "specific-matter-id"

    def test_events_can_be_filtered_by_user(self, log_capture):
        """Verify events can be filtered by user_id (NFR14)."""
        log_reliability_event(
            ReliabilityEventType.SSE_JSON_PARSE_FAILED,
            user_id="specific-user-id",
        )

        log_data = parse_log_output(log_capture)

        # Support staff should be able to query: user_id == "specific-user-id"
        assert log_data["user_id"] == "specific-user-id"
