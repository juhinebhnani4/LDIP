"""Tests for ChunkCleanupService.

Story 15.4: Chunk Cleanup Mechanism
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ocr_chunk import ChunkStatus, DocumentOCRChunk
from app.services.chunk_cleanup_service import (
    ChunkCleanupService,
    get_chunk_cleanup_service,
)


@pytest.fixture
def mock_chunk_service():
    """Create a mock OCRChunkService."""
    service = MagicMock()
    service.get_chunks_by_document = AsyncMock()
    service.delete_chunks_for_document = AsyncMock()
    service.get_stale_chunk_documents = AsyncMock()
    return service


@pytest.fixture
def mock_storage_service():
    """Create a mock StorageService."""
    service = MagicMock()
    service.delete_file = MagicMock()
    return service


@pytest.fixture
def sample_chunks():
    """Create sample chunk records for testing."""
    now = datetime.now(UTC)
    return [
        DocumentOCRChunk(
            id="chunk-1",
            matter_id="matter-123",
            document_id="doc-456",
            chunk_index=0,
            page_start=1,
            page_end=25,
            status=ChunkStatus.COMPLETED,
            result_storage_path="matter-123/chunks/chunk-1.json",
            result_checksum="abc123",
            created_at=now,
            updated_at=now,
        ),
        DocumentOCRChunk(
            id="chunk-2",
            matter_id="matter-123",
            document_id="doc-456",
            chunk_index=1,
            page_start=26,
            page_end=50,
            status=ChunkStatus.COMPLETED,
            result_storage_path="matter-123/chunks/chunk-2.json",
            result_checksum="def456",
            created_at=now,
            updated_at=now,
        ),
        DocumentOCRChunk(
            id="chunk-3",
            matter_id="matter-123",
            document_id="doc-456",
            chunk_index=2,
            page_start=51,
            page_end=75,
            status=ChunkStatus.COMPLETED,
            result_storage_path=None,  # No storage path
            result_checksum=None,
            created_at=now,
            updated_at=now,
        ),
    ]


class TestCleanupDocumentChunks:
    """Tests for cleanup_document_chunks method."""

    @pytest.mark.asyncio
    async def test_deletes_chunks_and_storage(
        self,
        mock_chunk_service,
        mock_storage_service,
        sample_chunks,
    ):
        """Cleanup deletes both chunk records and storage files."""
        mock_chunk_service.get_chunks_by_document.return_value = sample_chunks
        mock_chunk_service.delete_chunks_for_document.return_value = 3

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        result = await service.cleanup_document_chunks("doc-456")

        # Verify chunks were retrieved
        mock_chunk_service.get_chunks_by_document.assert_called_once_with("doc-456")

        # Verify storage files deleted (only 2 have paths)
        assert mock_storage_service.delete_file.call_count == 2
        mock_storage_service.delete_file.assert_any_call(
            "matter-123/chunks/chunk-1.json"
        )
        mock_storage_service.delete_file.assert_any_call(
            "matter-123/chunks/chunk-2.json"
        )

        # Verify chunk records deleted
        mock_chunk_service.delete_chunks_for_document.assert_called_once_with("doc-456")

        # Verify result
        assert result["document_id"] == "doc-456"
        assert result["chunks_deleted"] == 3
        assert result["storage_files_deleted"] == 2
        assert result["storage_errors"] == []

    @pytest.mark.asyncio
    async def test_skips_storage_when_disabled(
        self,
        mock_chunk_service,
        mock_storage_service,
        sample_chunks,
    ):
        """Storage deletion can be disabled."""
        mock_chunk_service.get_chunks_by_document.return_value = sample_chunks
        mock_chunk_service.delete_chunks_for_document.return_value = 3

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        result = await service.cleanup_document_chunks(
            "doc-456", delete_storage=False
        )

        # Verify storage NOT deleted
        mock_storage_service.delete_file.assert_not_called()

        # Verify chunks still deleted
        assert result["chunks_deleted"] == 3
        assert result["storage_files_deleted"] == 0

    @pytest.mark.asyncio
    async def test_handles_no_chunks(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        """Handles documents with no chunks gracefully."""
        mock_chunk_service.get_chunks_by_document.return_value = []

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        result = await service.cleanup_document_chunks("doc-456")

        # Should not attempt delete
        mock_chunk_service.delete_chunks_for_document.assert_not_called()
        mock_storage_service.delete_file.assert_not_called()

        assert result["chunks_deleted"] == 0
        assert result["storage_files_deleted"] == 0

    @pytest.mark.asyncio
    async def test_continues_after_storage_error(
        self,
        mock_chunk_service,
        mock_storage_service,
        sample_chunks,
    ):
        """Storage errors don't stop cleanup process."""
        mock_chunk_service.get_chunks_by_document.return_value = sample_chunks
        mock_chunk_service.delete_chunks_for_document.return_value = 3

        # First storage delete fails, second succeeds
        mock_storage_service.delete_file.side_effect = [
            Exception("Storage error"),
            None,
        ]

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        result = await service.cleanup_document_chunks("doc-456")

        # Verify chunk records still deleted
        mock_chunk_service.delete_chunks_for_document.assert_called_once()

        # Verify result captures error but continues
        assert result["chunks_deleted"] == 3
        assert result["storage_files_deleted"] == 1
        assert len(result["storage_errors"]) == 1
        assert "Storage error" in result["storage_errors"][0]["error"]


class TestCleanupStaleChunks:
    """Tests for cleanup_stale_chunks method."""

    @pytest.mark.asyncio
    async def test_cleans_up_stale_documents(
        self,
        mock_chunk_service,
        mock_storage_service,
        sample_chunks,
    ):
        """Cleans up chunks for documents with stale records."""
        # Setup stale documents
        mock_chunk_service.get_stale_chunk_documents.return_value = [
            {"document_id": "doc-1", "matter_id": "matter-1", "chunk_count": 5},
            {"document_id": "doc-2", "matter_id": "matter-2", "chunk_count": 3},
        ]

        # Each document has chunks
        mock_chunk_service.get_chunks_by_document.return_value = sample_chunks[:1]
        mock_chunk_service.delete_chunks_for_document.return_value = 1

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
            retention_hours=24,
        )

        result = await service.cleanup_stale_chunks()

        # Verify stale documents were queried
        mock_chunk_service.get_stale_chunk_documents.assert_called_once()

        # Verify cleanup called for each document
        assert mock_chunk_service.delete_chunks_for_document.call_count == 2

        # Verify result
        assert result["documents_checked"] == 2
        assert result["documents_cleaned"] == 2
        assert result["total_chunks_deleted"] == 2
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_dry_run_mode(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        """Dry run mode reports but doesn't delete."""
        mock_chunk_service.get_stale_chunk_documents.return_value = [
            {"document_id": "doc-1", "matter_id": "matter-1", "chunk_count": 5},
        ]

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        result = await service.cleanup_stale_chunks(dry_run=True)

        # Verify NO cleanup performed
        mock_chunk_service.delete_chunks_for_document.assert_not_called()
        mock_storage_service.delete_file.assert_not_called()

        # Verify result shows dry run
        assert result["dry_run"] is True
        assert result["documents_checked"] == 1
        assert result["documents_cleaned"] == 0

    @pytest.mark.asyncio
    async def test_uses_custom_retention(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        """Custom retention period is used."""
        mock_chunk_service.get_stale_chunk_documents.return_value = []

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
            retention_hours=48,  # Default 48 hours
        )

        # Override with 12 hours
        await service.cleanup_stale_chunks(retention_hours=12)

        # Verify the call used 12 hours
        call_args = mock_chunk_service.get_stale_chunk_documents.call_args
        cutoff_date = call_args.kwargs["cutoff_date"]

        # Cutoff should be ~12 hours ago
        expected_cutoff = datetime.now(UTC) - timedelta(hours=12)
        assert abs((cutoff_date - expected_cutoff).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_handles_cleanup_errors(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        """Errors in individual document cleanup don't stop batch."""
        mock_chunk_service.get_stale_chunk_documents.return_value = [
            {"document_id": "doc-1", "matter_id": "matter-1", "chunk_count": 5},
            {"document_id": "doc-2", "matter_id": "matter-2", "chunk_count": 3},
        ]

        # First document cleanup fails, second succeeds
        mock_chunk_service.get_chunks_by_document.side_effect = [
            Exception("Database error"),
            [],  # No chunks for doc-2
        ]

        service = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        result = await service.cleanup_stale_chunks()

        # Verify both documents were attempted
        assert mock_chunk_service.get_chunks_by_document.call_count == 2

        # Verify result captures error
        assert result["documents_cleaned"] == 1  # Only doc-2 succeeded
        assert len(result["errors"]) == 1
        assert result["errors"][0]["document_id"] == "doc-1"


class TestGetChunkCleanupService:
    """Tests for get_chunk_cleanup_service factory."""

    def test_returns_singleton(self):
        """Factory returns the same instance."""
        # Clear the cache first
        get_chunk_cleanup_service.cache_clear()

        service1 = get_chunk_cleanup_service()
        service2 = get_chunk_cleanup_service()

        assert service1 is service2

    def test_returns_chunk_cleanup_service_instance(self):
        """Factory returns ChunkCleanupService instance."""
        get_chunk_cleanup_service.cache_clear()

        service = get_chunk_cleanup_service()

        assert isinstance(service, ChunkCleanupService)
