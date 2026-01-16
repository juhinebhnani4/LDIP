"""Unit tests for OCR chunk service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.ocr_chunk import (
    VALID_STATUS_TRANSITIONS,
    ChunkProgress,
    ChunkSpec,
    ChunkStatus,
)
from app.services.ocr_chunk_service import (
    STALE_CHUNK_THRESHOLD_SECONDS,
    ChunkNotFoundError,
    DuplicateChunkError,
    InvalidPageRangeError,
    InvalidStatusTransitionError,
    OCRChunkService,
    OCRChunkServiceError,
    get_ocr_chunk_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    with patch("app.services.ocr_chunk_service.get_supabase_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def service(mock_supabase):
    """Create an OCRChunkService instance with mock client."""
    return OCRChunkService()


@pytest.fixture
def sample_chunk_row():
    """Sample database row for a chunk."""
    now = datetime.now(UTC)
    return {
        "id": str(uuid4()),
        "matter_id": str(uuid4()),
        "document_id": str(uuid4()),
        "chunk_index": 0,
        "page_start": 1,
        "page_end": 25,
        "status": "pending",
        "error_message": None,
        "result_storage_path": None,
        "result_checksum": None,
        "processing_started_at": None,
        "processing_completed_at": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


# =============================================================================
# Test Service Initialization
# =============================================================================


class TestOCRChunkServiceInit:
    """Tests for OCRChunkService initialization."""

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_lazy_loads_client(self, mock_get_client: MagicMock) -> None:
        """Should lazy load Supabase client on first access."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        service = OCRChunkService()
        # Client not loaded yet
        assert service._client is None

        # Access client property
        _ = service.client
        assert service._client is mock_client

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_raises_when_client_not_configured(self, mock_get_client: MagicMock) -> None:
        """Should raise error when Supabase is not configured."""
        mock_get_client.return_value = None

        service = OCRChunkService()

        with pytest.raises(OCRChunkServiceError) as exc_info:
            _ = service.client

        assert exc_info.value.code == "SUPABASE_NOT_CONFIGURED"


class TestGetOCRChunkService:
    """Tests for get_ocr_chunk_service factory."""

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_returns_singleton(self, mock_get_client: MagicMock) -> None:
        """Should return the same instance."""
        # Clear the LRU cache
        get_ocr_chunk_service.cache_clear()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        service1 = get_ocr_chunk_service()
        service2 = get_ocr_chunk_service()

        assert service1 is service2


# =============================================================================
# Test Create Chunk
# =============================================================================


class TestCreateChunk:
    """Tests for create_chunk method."""

    @pytest.mark.asyncio
    async def test_create_chunk_success(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should create chunk with pending status."""
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            sample_chunk_row
        ]

        result = await service.create_chunk(
            document_id=sample_chunk_row["document_id"],
            matter_id=sample_chunk_row["matter_id"],
            chunk_index=0,
            page_start=1,
            page_end=25,
        )

        assert result.status == ChunkStatus.PENDING
        assert result.chunk_index == 0
        assert result.page_start == 1
        assert result.page_end == 25

        # Verify insert was called with correct data
        mock_supabase.table.assert_called_with("document_ocr_chunks")
        insert_call = mock_supabase.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["status"] == "pending"
        assert insert_data["chunk_index"] == 0

    @pytest.mark.asyncio
    async def test_create_chunk_invalid_page_range(self, service) -> None:
        """Should raise error when page_start > page_end."""
        with pytest.raises(InvalidPageRangeError) as exc_info:
            await service.create_chunk(
                document_id="doc-1",
                matter_id="matter-1",
                chunk_index=0,
                page_start=30,  # Invalid: greater than page_end
                page_end=25,
            )

        assert exc_info.value.code == "INVALID_PAGE_RANGE"

    @pytest.mark.asyncio
    async def test_create_chunk_handles_unique_constraint(self, service, mock_supabase) -> None:
        """Should raise DuplicateChunkError on unique constraint violation."""
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
            "duplicate key value violates unique constraint"
        )

        with pytest.raises(DuplicateChunkError) as exc_info:
            await service.create_chunk(
                document_id="doc-1",
                matter_id="matter-1",
                chunk_index=0,
                page_start=1,
                page_end=25,
            )

        assert exc_info.value.code == "DUPLICATE_CHUNK"


# =============================================================================
# Test Get Chunk
# =============================================================================


class TestGetChunk:
    """Tests for get_chunk method."""

    @pytest.mark.asyncio
    async def test_get_chunk_found(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should return chunk when found."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            sample_chunk_row
        ]

        result = await service.get_chunk(sample_chunk_row["id"])

        assert result is not None
        assert result.id == sample_chunk_row["id"]
        assert result.status == ChunkStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_chunk_not_found(self, service, mock_supabase) -> None:
        """Should return None when chunk not found."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        result = await service.get_chunk("nonexistent-id")

        assert result is None


# =============================================================================
# Test Update Status
# =============================================================================


class TestUpdateStatus:
    """Tests for update_status method."""

    @pytest.mark.asyncio
    async def test_update_status_to_processing(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should set processing_started_at when transitioning to processing."""
        # Setup: chunk is pending
        pending_row = {**sample_chunk_row, "status": "pending"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            pending_row
        ]

        # Updated row
        processing_row = {
            **sample_chunk_row,
            "status": "processing",
            "processing_started_at": datetime.now(UTC).isoformat(),
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            processing_row
        ]

        result = await service.update_status(sample_chunk_row["id"], ChunkStatus.PROCESSING)

        assert result.status == ChunkStatus.PROCESSING

        # Verify update included processing_started_at
        update_call = mock_supabase.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert "processing_started_at" in update_data

    @pytest.mark.asyncio
    async def test_update_status_to_completed(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should set processing_completed_at when transitioning to completed."""
        # Setup: chunk is processing
        processing_row = {**sample_chunk_row, "status": "processing"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            processing_row
        ]

        # Updated row
        completed_row = {
            **sample_chunk_row,
            "status": "completed",
            "processing_completed_at": datetime.now(UTC).isoformat(),
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            completed_row
        ]

        result = await service.update_status(sample_chunk_row["id"], ChunkStatus.COMPLETED)

        assert result.status == ChunkStatus.COMPLETED

        # Verify update included processing_completed_at
        update_call = mock_supabase.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert "processing_completed_at" in update_data

    @pytest.mark.asyncio
    async def test_update_status_to_failed_with_error(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should set error_message when transitioning to failed."""
        # Setup: chunk is processing
        processing_row = {**sample_chunk_row, "status": "processing"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            processing_row
        ]

        # Updated row
        failed_row = {
            **sample_chunk_row,
            "status": "failed",
            "error_message": "OCR API timeout",
            "processing_completed_at": datetime.now(UTC).isoformat(),
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            failed_row
        ]

        result = await service.update_status(
            sample_chunk_row["id"],
            ChunkStatus.FAILED,
            error_message="OCR API timeout",
        )

        assert result.status == ChunkStatus.FAILED

        # Verify error_message was included
        update_call = mock_supabase.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["error_message"] == "OCR API timeout"

    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should raise error for invalid status transition."""
        # Setup: chunk is completed (terminal state)
        completed_row = {**sample_chunk_row, "status": "completed"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            completed_row
        ]

        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            await service.update_status(sample_chunk_row["id"], ChunkStatus.PENDING)

        assert exc_info.value.code == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_update_status_chunk_not_found(self, service, mock_supabase) -> None:
        """Should raise ChunkNotFoundError when chunk doesn't exist."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        with pytest.raises(ChunkNotFoundError):
            await service.update_status("nonexistent-id", ChunkStatus.PROCESSING)

    @pytest.mark.asyncio
    async def test_update_status_retry_clears_error(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should clear error_message when retrying (failed -> pending)."""
        # Setup: chunk is failed
        failed_row = {**sample_chunk_row, "status": "failed", "error_message": "Previous error"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            failed_row
        ]

        # Updated row
        pending_row = {**sample_chunk_row, "status": "pending", "error_message": None}
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            pending_row
        ]

        await service.update_status(sample_chunk_row["id"], ChunkStatus.PENDING)

        # Verify error_message was cleared
        update_call = mock_supabase.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["error_message"] is None


# =============================================================================
# Test Query Operations
# =============================================================================


class TestGetChunksByDocument:
    """Tests for get_chunks_by_document method."""

    @pytest.mark.asyncio
    async def test_returns_chunks_ordered_by_index(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should return chunks ordered by chunk_index."""
        chunk1 = {**sample_chunk_row, "id": str(uuid4()), "chunk_index": 0}
        chunk2 = {**sample_chunk_row, "id": str(uuid4()), "chunk_index": 1}

        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            chunk1, chunk2
        ]

        result = await service.get_chunks_by_document(sample_chunk_row["document_id"])

        assert len(result) == 2
        assert result[0].chunk_index == 0
        assert result[1].chunk_index == 1

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_chunks(self, service, mock_supabase) -> None:
        """Should return empty list when document has no chunks."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

        result = await service.get_chunks_by_document("doc-with-no-chunks")

        assert result == []


class TestGetFailedChunks:
    """Tests for get_failed_chunks method."""

    @pytest.mark.asyncio
    async def test_returns_only_failed_chunks(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should return only chunks with 'failed' status."""
        failed_chunk = {**sample_chunk_row, "status": "failed", "error_message": "API error"}

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            failed_chunk
        ]

        result = await service.get_failed_chunks(sample_chunk_row["document_id"])

        assert len(result) == 1
        assert result[0].status == ChunkStatus.FAILED


class TestGetPendingChunks:
    """Tests for get_pending_chunks method."""

    @pytest.mark.asyncio
    async def test_returns_only_pending_chunks(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should return only chunks with 'pending' status."""
        pending_chunk = {**sample_chunk_row, "status": "pending"}

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            pending_chunk
        ]

        result = await service.get_pending_chunks(sample_chunk_row["document_id"])

        assert len(result) == 1
        assert result[0].status == ChunkStatus.PENDING


class TestGetProcessingChunks:
    """Tests for get_processing_chunks method."""

    @pytest.mark.asyncio
    async def test_returns_only_processing_chunks(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should return only chunks with 'processing' status."""
        processing_chunk = {
            **sample_chunk_row,
            "status": "processing",
            "processing_started_at": datetime.now(UTC).isoformat(),
        }

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            processing_chunk
        ]

        result = await service.get_processing_chunks(sample_chunk_row["document_id"])

        assert len(result) == 1
        assert result[0].status == ChunkStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_processing_chunks(self, service, mock_supabase) -> None:
        """Should return empty list when no chunks are processing."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = []

        result = await service.get_processing_chunks("doc-id")

        assert result == []


# =============================================================================
# Test Update Result
# =============================================================================


class TestUpdateResult:
    """Tests for update_result method."""

    @pytest.mark.asyncio
    async def test_update_result_success(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should update result_storage_path and result_checksum."""
        # Setup: chunk exists
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            sample_chunk_row
        ]

        # Updated row with result fields
        updated_row = {
            **sample_chunk_row,
            "result_storage_path": "ocr-chunks/doc-123/chunk-0.json",
            "result_checksum": "abc123def456",
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            updated_row
        ]

        result = await service.update_result(
            chunk_id=sample_chunk_row["id"],
            result_storage_path="ocr-chunks/doc-123/chunk-0.json",
            result_checksum="abc123def456",
        )

        assert result.result_storage_path == "ocr-chunks/doc-123/chunk-0.json"
        assert result.result_checksum == "abc123def456"

        # Verify update was called with correct data
        update_call = mock_supabase.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["result_storage_path"] == "ocr-chunks/doc-123/chunk-0.json"
        assert update_data["result_checksum"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_update_result_chunk_not_found(self, service, mock_supabase) -> None:
        """Should raise ChunkNotFoundError when chunk doesn't exist."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        with pytest.raises(ChunkNotFoundError):
            await service.update_result(
                chunk_id="nonexistent-id",
                result_storage_path="path/to/result.json",
                result_checksum="checksum123",
            )


# =============================================================================
# Test Heartbeat Detection
# =============================================================================


class TestUpdateHeartbeat:
    """Tests for update_heartbeat method."""

    @pytest.mark.asyncio
    async def test_update_heartbeat_success(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should update processing_started_at timestamp."""
        processing_row = {**sample_chunk_row, "status": "processing"}
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            processing_row
        ]

        result = await service.update_heartbeat(sample_chunk_row["id"])

        assert result is True

        # Verify the correct update was made
        mock_supabase.table.return_value.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_heartbeat_chunk_not_processing(self, service, mock_supabase) -> None:
        """Should return False when chunk is not in processing state."""
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        result = await service.update_heartbeat("chunk-not-processing")

        assert result is False


class TestDetectStaleChunks:
    """Tests for detect_stale_chunks method."""

    @pytest.mark.asyncio
    async def test_detects_stale_chunks(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should find chunks stuck in processing past threshold."""
        # Chunk started 120 seconds ago (stale - past 90s threshold)
        stale_time = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
        stale_row = {
            **sample_chunk_row,
            "status": "processing",
            "processing_started_at": stale_time,
        }

        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value.data = [
            stale_row
        ]

        result = await service.detect_stale_chunks()

        assert len(result) == 1
        assert result[0].id == stale_row["id"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_stale_chunks(self, service, mock_supabase) -> None:
        """Should return empty list when no stale chunks."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value.data = []

        result = await service.detect_stale_chunks()

        assert result == []


class TestMarkChunkStale:
    """Tests for mark_chunk_stale method."""

    @pytest.mark.asyncio
    async def test_marks_chunk_as_failed(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should mark chunk as failed with worker_timeout error."""
        # Setup: chunk is processing
        processing_row = {**sample_chunk_row, "status": "processing"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            processing_row
        ]

        # Updated row
        failed_row = {
            **sample_chunk_row,
            "status": "failed",
            "error_message": "worker_timeout",
        }
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            failed_row
        ]

        result = await service.mark_chunk_stale(sample_chunk_row["id"])

        assert result.status == ChunkStatus.FAILED
        assert result.error_message == "worker_timeout"

    @pytest.mark.asyncio
    async def test_raises_error_when_chunk_not_processing(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should raise error when chunk is not in processing state."""
        # Setup: chunk is pending (not processing)
        pending_row = {**sample_chunk_row, "status": "pending"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            pending_row
        ]

        with pytest.raises(InvalidStatusTransitionError):
            await service.mark_chunk_stale(sample_chunk_row["id"])

    @pytest.mark.asyncio
    async def test_raises_error_when_chunk_not_found(self, service, mock_supabase) -> None:
        """Should raise ChunkNotFoundError when chunk doesn't exist."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        with pytest.raises(ChunkNotFoundError):
            await service.mark_chunk_stale("nonexistent-id")


# =============================================================================
# Test Batch Operations
# =============================================================================


class TestCreateChunksForDocument:
    """Tests for create_chunks_for_document method."""

    @pytest.mark.asyncio
    async def test_creates_multiple_chunks(self, service, mock_supabase, sample_chunk_row) -> None:
        """Should create multiple chunks in batch."""
        doc_id = str(uuid4())
        matter_id = str(uuid4())

        chunk_specs = [
            ChunkSpec(chunk_index=0, page_start=1, page_end=25),
            ChunkSpec(chunk_index=1, page_start=26, page_end=50),
            ChunkSpec(chunk_index=2, page_start=51, page_end=75),
        ]

        # Mock response with created chunks
        created_rows = [
            {**sample_chunk_row, "id": str(uuid4()), "chunk_index": i, "page_start": spec.page_start, "page_end": spec.page_end}
            for i, spec in enumerate(chunk_specs)
        ]
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = created_rows

        result = await service.create_chunks_for_document(
            document_id=doc_id,
            matter_id=matter_id,
            chunk_specs=chunk_specs,
        )

        assert len(result) == 3
        assert all(c.status == ChunkStatus.PENDING for c in result)

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_specs(self, service) -> None:
        """Should return empty list when no specs provided."""
        result = await service.create_chunks_for_document(
            document_id="doc-1",
            matter_id="matter-1",
            chunk_specs=[],
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_validates_all_page_ranges(self, service) -> None:
        """Should validate page ranges for all specs."""
        chunk_specs = [
            ChunkSpec(chunk_index=0, page_start=1, page_end=25),
            ChunkSpec(chunk_index=1, page_start=50, page_end=30),  # Invalid
        ]

        with pytest.raises(InvalidPageRangeError):
            await service.create_chunks_for_document(
                document_id="doc-1",
                matter_id="matter-1",
                chunk_specs=chunk_specs,
            )


class TestGetChunkProgress:
    """Tests for get_chunk_progress method."""

    @pytest.mark.asyncio
    async def test_returns_correct_counts(self, service, mock_supabase) -> None:
        """Should return correct status counts."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"status": "pending"},
            {"status": "pending"},
            {"status": "processing"},
            {"status": "completed"},
            {"status": "completed"},
            {"status": "completed"},
            {"status": "failed"},
        ]

        result = await service.get_chunk_progress("doc-1")

        assert result.total == 7
        assert result.pending == 2
        assert result.processing == 1
        assert result.completed == 3
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_returns_zero_for_no_chunks(self, service, mock_supabase) -> None:
        """Should return zeros when no chunks exist."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        result = await service.get_chunk_progress("doc-no-chunks")

        assert result.total == 0
        assert result.pending == 0
        assert result.processing == 0
        assert result.completed == 0
        assert result.failed == 0


# =============================================================================
# Test ChunkProgress Model
# =============================================================================


class TestChunkProgressModel:
    """Tests for ChunkProgress model properties."""

    def test_progress_pct_calculation(self) -> None:
        """Should calculate correct progress percentage."""
        progress = ChunkProgress(total=10, pending=2, processing=1, completed=6, failed=1)
        assert progress.progress_pct == 60  # 6/10 = 60%

    def test_progress_pct_zero_total(self) -> None:
        """Should return 100% when total is 0."""
        progress = ChunkProgress(total=0, pending=0, processing=0, completed=0, failed=0)
        assert progress.progress_pct == 100

    def test_is_complete_true(self) -> None:
        """Should return True when no pending or processing chunks."""
        progress = ChunkProgress(total=5, pending=0, processing=0, completed=4, failed=1)
        assert progress.is_complete is True

    def test_is_complete_false(self) -> None:
        """Should return False when chunks are still processing."""
        progress = ChunkProgress(total=5, pending=1, processing=1, completed=2, failed=1)
        assert progress.is_complete is False

    def test_has_failures_true(self) -> None:
        """Should return True when failed > 0."""
        progress = ChunkProgress(total=5, pending=0, processing=0, completed=4, failed=1)
        assert progress.has_failures is True

    def test_has_failures_false(self) -> None:
        """Should return False when no failures."""
        progress = ChunkProgress(total=5, pending=0, processing=0, completed=5, failed=0)
        assert progress.has_failures is False


# =============================================================================
# Test Status Transition Validation
# =============================================================================


class TestStatusTransitions:
    """Tests for status transition validation logic."""

    def test_valid_transitions_pending_to_processing(self) -> None:
        """Pending can transition to processing."""
        assert ChunkStatus.PROCESSING in VALID_STATUS_TRANSITIONS[ChunkStatus.PENDING]

    def test_valid_transitions_processing_to_completed(self) -> None:
        """Processing can transition to completed."""
        assert ChunkStatus.COMPLETED in VALID_STATUS_TRANSITIONS[ChunkStatus.PROCESSING]

    def test_valid_transitions_processing_to_failed(self) -> None:
        """Processing can transition to failed."""
        assert ChunkStatus.FAILED in VALID_STATUS_TRANSITIONS[ChunkStatus.PROCESSING]

    def test_valid_transitions_failed_to_pending(self) -> None:
        """Failed can transition to pending (retry)."""
        assert ChunkStatus.PENDING in VALID_STATUS_TRANSITIONS[ChunkStatus.FAILED]

    def test_completed_is_terminal(self) -> None:
        """Completed is a terminal state with no valid transitions."""
        assert len(VALID_STATUS_TRANSITIONS[ChunkStatus.COMPLETED]) == 0


# =============================================================================
# Test Exception Classes
# =============================================================================


class TestExceptions:
    """Tests for custom exception classes."""

    def test_ocr_chunk_service_error(self) -> None:
        """Should store message and code."""
        error = OCRChunkServiceError("Test error", code="TEST_CODE")
        assert error.message == "Test error"
        assert error.code == "TEST_CODE"
        assert str(error) == "Test error"

    def test_chunk_not_found_error(self) -> None:
        """Should format message with chunk ID."""
        error = ChunkNotFoundError("chunk-123")
        assert "chunk-123" in error.message
        assert error.code == "CHUNK_NOT_FOUND"

    def test_invalid_status_transition_error(self) -> None:
        """Should format message with statuses."""
        error = InvalidStatusTransitionError("completed", "pending")
        assert "completed" in error.message
        assert "pending" in error.message
        assert error.code == "INVALID_STATUS_TRANSITION"

    def test_duplicate_chunk_error(self) -> None:
        """Should format message with document and index."""
        error = DuplicateChunkError("doc-1", 5)
        assert "doc-1" in error.message
        assert "5" in error.message
        assert error.code == "DUPLICATE_CHUNK"

    def test_invalid_page_range_error(self) -> None:
        """Should format message with page numbers."""
        error = InvalidPageRangeError(30, 25)
        assert "30" in error.message
        assert "25" in error.message
        assert error.code == "INVALID_PAGE_RANGE"


# =============================================================================
# Test Timestamp Parsing
# =============================================================================


class TestTimestampParsing:
    """Tests for timestamp parsing helper."""

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_parses_iso_format(self, mock_get_client) -> None:
        """Should parse ISO format timestamps."""
        mock_get_client.return_value = MagicMock()
        service = OCRChunkService()

        result = service._parse_timestamp("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_handles_none(self, mock_get_client) -> None:
        """Should return None for None input."""
        mock_get_client.return_value = MagicMock()
        service = OCRChunkService()

        result = service._parse_timestamp(None)
        assert result is None

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_handles_invalid_format(self, mock_get_client) -> None:
        """Should return None for invalid format."""
        mock_get_client.return_value = MagicMock()
        service = OCRChunkService()

        result = service._parse_timestamp("not-a-timestamp")
        assert result is None


class TestTimestampParsingRequired:
    """Tests for _parse_timestamp_required helper."""

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_parses_valid_iso_format(self, mock_get_client) -> None:
        """Should parse valid ISO format timestamps."""
        mock_get_client.return_value = MagicMock()
        service = OCRChunkService()

        result = service._parse_timestamp_required("2024-01-15T10:30:00Z", "created_at")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    @patch("app.services.ocr_chunk_service.get_supabase_client")
    def test_raises_on_invalid_format(self, mock_get_client) -> None:
        """Should raise OCRChunkServiceError for invalid format."""
        mock_get_client.return_value = MagicMock()
        service = OCRChunkService()

        with pytest.raises(OCRChunkServiceError) as exc_info:
            service._parse_timestamp_required("not-a-timestamp", "created_at")

        assert exc_info.value.code == "TIMESTAMP_PARSE_ERROR"
        assert "created_at" in exc_info.value.message


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for service constants."""

    def test_stale_threshold_is_90_seconds(self) -> None:
        """Stale chunk threshold should be 90 seconds."""
        assert STALE_CHUNK_THRESHOLD_SECONDS == 90
