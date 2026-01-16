"""Tests for chunked document processing tasks.

Story 16.4: Parallel Chunk Processing with Celery
Story 16.5: Individual Chunk Retry
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ocr_chunk import ChunkStatus, DocumentOCRChunk


@pytest.fixture
def sample_chunks():
    """Create sample chunk records for testing."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return [
        DocumentOCRChunk(
            id="chunk-1",
            matter_id="matter-123",
            document_id="doc-456",
            chunk_index=0,
            page_start=1,
            page_end=25,
            status=ChunkStatus.PENDING,
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
            status=ChunkStatus.PENDING,
            created_at=now,
            updated_at=now,
        ),
    ]


@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    return {
        "storage_service": MagicMock(),
        "chunk_service": MagicMock(),
        "doc_service": MagicMock(),
        "ocr_processor": MagicMock(),
        "pdf_chunker": MagicMock(),
    }


class TestProcessDocumentChunked:
    """Tests for process_document_chunked task."""

    def test_no_pending_chunks_returns_no_chunks_status(
        self,
        mock_services,
    ):
        """Returns no_chunks when no pending chunks found."""
        from app.workers.tasks.chunked_document_tasks import (
            process_document_chunked,
        )

        mock_services["chunk_service"].get_pending_chunks = AsyncMock(return_value=[])

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.get_storage_service",
                return_value=mock_services["storage_service"],
            ):
                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service",
                    return_value=mock_services["doc_service"],
                ):
                    result = process_document_chunked(
                        document_id="doc-456",
                        matter_id="matter-123",
                    )

        assert result["status"] == "no_chunks"
        assert result["document_id"] == "doc-456"

    def test_dispatches_all_chunks_in_parallel(
        self,
        mock_services,
        sample_chunks,
    ):
        """All pending chunks are dispatched as a Celery group."""
        from app.workers.tasks.chunked_document_tasks import (
            process_document_chunked,
        )

        mock_services["chunk_service"].get_pending_chunks = AsyncMock(
            return_value=sample_chunks
        )

        mock_document = MagicMock()
        mock_document.storage_path = "matter-123/uploads/doc.pdf"
        mock_services["doc_service"].get_document_by_id.return_value = mock_document

        mock_group_result = MagicMock()
        mock_group_result.get.return_value = [
            {"status": "success", "chunk_index": 0},
            {"status": "success", "chunk_index": 1},
        ]

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.get_storage_service",
                return_value=mock_services["storage_service"],
            ):
                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service",
                    return_value=mock_services["doc_service"],
                ):
                    with patch(
                        "app.workers.tasks.chunked_document_tasks.group"
                    ) as mock_group:
                        mock_group.return_value.apply_async.return_value = mock_group_result

                        with patch(
                            "app.workers.tasks.chunked_document_tasks._merge_and_store_results"
                        ) as mock_merge:
                            mock_merge.return_value = {"status": "ocr_complete"}

                            result = process_document_chunked(
                                document_id="doc-456",
                                matter_id="matter-123",
                            )

        # Verify group was called with tasks
        mock_group.assert_called_once()

    def test_handles_partial_failures(
        self,
        mock_services,
        sample_chunks,
    ):
        """Partial failures are reported without marking document as failed."""
        from app.workers.tasks.chunked_document_tasks import (
            process_document_chunked,
        )

        mock_services["chunk_service"].get_pending_chunks = AsyncMock(
            return_value=sample_chunks
        )

        mock_document = MagicMock()
        mock_document.storage_path = "matter-123/uploads/doc.pdf"
        mock_services["doc_service"].get_document_by_id.return_value = mock_document

        mock_group_result = MagicMock()
        mock_group_result.get.return_value = [
            {"status": "success", "chunk_index": 0},
            Exception("Chunk 1 failed"),  # Failure
        ]

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.get_storage_service",
                return_value=mock_services["storage_service"],
            ):
                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service",
                    return_value=mock_services["doc_service"],
                ):
                    with patch(
                        "app.workers.tasks.chunked_document_tasks.group"
                    ) as mock_group:
                        mock_group.return_value.apply_async.return_value = mock_group_result

                        with patch(
                            "app.workers.tasks.chunked_document_tasks.get_chunk_progress_tracker"
                        ) as mock_tracker:
                            mock_tracker.return_value.report_chunk_failure = AsyncMock()

                            result = process_document_chunked(
                                document_id="doc-456",
                                matter_id="matter-123",
                            )

        assert result["status"] == "partial_failure"
        assert len(result["failed_chunks"]) == 1
        assert result["successful_count"] == 1


class TestProcessSingleChunk:
    """Tests for process_single_chunk task."""

    def test_acquires_lock_before_processing(self, mock_services):
        """Distributed lock is acquired before processing."""
        from app.workers.tasks.chunked_document_tasks import (
            process_single_chunk,
        )

        mock_services["chunk_service"].update_status = AsyncMock()
        mock_services["chunk_service"].update_result = AsyncMock()

        mock_document = MagicMock()
        mock_document.storage_path = "matter-123/uploads/doc.pdf"
        mock_services["doc_service"].get_document_by_id.return_value = mock_document

        mock_services["storage_service"].download_file.return_value = b"%PDF-1.4..."
        mock_services["storage_service"].upload_file.return_value = ("path", None)

        # Mock OCR result
        mock_ocr_result = MagicMock()
        mock_ocr_result.bounding_boxes = []
        mock_ocr_result.full_text = "Test text"
        mock_ocr_result.overall_confidence = 0.95
        mock_ocr_result.page_count = 25
        mock_services["ocr_processor"].process_document.return_value = mock_ocr_result

        # Mock PDF chunker
        mock_services["pdf_chunker"].split_pdf.return_value = [
            (b"%PDF-chunk...", 1, 25)
        ]

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.get_storage_service",
                return_value=mock_services["storage_service"],
            ):
                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service",
                    return_value=mock_services["doc_service"],
                ):
                    with patch(
                        "app.workers.tasks.chunked_document_tasks.get_ocr_processor",
                        return_value=mock_services["ocr_processor"],
                    ):
                        with patch(
                            "app.workers.tasks.chunked_document_tasks.get_pdf_chunker",
                            return_value=mock_services["pdf_chunker"],
                        ):
                            with patch(
                                "app.workers.tasks.chunked_document_tasks.acquire_chunk_lock"
                            ) as mock_lock:
                                mock_lock.return_value.__enter__ = MagicMock(
                                    return_value=True
                                )
                                mock_lock.return_value.__exit__ = MagicMock(
                                    return_value=False
                                )

                                with patch(
                                    "app.workers.tasks.chunked_document_tasks.get_chunk_progress_tracker"
                                ) as mock_tracker:
                                    mock_tracker.return_value.update_chunk_progress = (
                                        AsyncMock()
                                    )

                                    result = process_single_chunk(
                                        document_id="doc-456",
                                        matter_id="matter-123",
                                        chunk_id="chunk-1",
                                        chunk_index=0,
                                        page_start=1,
                                        page_end=25,
                                    )

        # Verify lock was used
        mock_lock.assert_called_once_with("doc-456", 0)

    def test_updates_chunk_status_to_processing(self, mock_services):
        """Chunk status is updated to processing at start."""
        from app.workers.tasks.chunked_document_tasks import (
            process_single_chunk,
        )

        mock_services["chunk_service"].update_status = AsyncMock()
        mock_services["chunk_service"].update_result = AsyncMock()

        mock_document = MagicMock()
        mock_document.storage_path = "matter-123/uploads/doc.pdf"
        mock_services["doc_service"].get_document_by_id.return_value = mock_document

        mock_services["storage_service"].download_file.return_value = b"%PDF-1.4..."
        mock_services["storage_service"].upload_file.return_value = ("path", None)

        mock_ocr_result = MagicMock()
        mock_ocr_result.bounding_boxes = []
        mock_ocr_result.full_text = "Test text"
        mock_ocr_result.overall_confidence = 0.95
        mock_ocr_result.page_count = 25
        mock_services["ocr_processor"].process_document.return_value = mock_ocr_result

        mock_services["pdf_chunker"].split_pdf.return_value = [
            (b"%PDF-chunk...", 1, 25)
        ]

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.get_storage_service",
                return_value=mock_services["storage_service"],
            ):
                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service",
                    return_value=mock_services["doc_service"],
                ):
                    with patch(
                        "app.workers.tasks.chunked_document_tasks.get_ocr_processor",
                        return_value=mock_services["ocr_processor"],
                    ):
                        with patch(
                            "app.workers.tasks.chunked_document_tasks.get_pdf_chunker",
                            return_value=mock_services["pdf_chunker"],
                        ):
                            with patch(
                                "app.workers.tasks.chunked_document_tasks.acquire_chunk_lock"
                            ) as mock_lock:
                                mock_lock.return_value.__enter__ = MagicMock(
                                    return_value=True
                                )
                                mock_lock.return_value.__exit__ = MagicMock(
                                    return_value=False
                                )

                                with patch(
                                    "app.workers.tasks.chunked_document_tasks.get_chunk_progress_tracker"
                                ) as mock_tracker:
                                    mock_tracker.return_value.update_chunk_progress = (
                                        AsyncMock()
                                    )

                                    process_single_chunk(
                                        document_id="doc-456",
                                        matter_id="matter-123",
                                        chunk_id="chunk-1",
                                        chunk_index=0,
                                        page_start=1,
                                        page_end=25,
                                    )

        # Verify status was updated to PROCESSING
        mock_services["chunk_service"].update_status.assert_any_call(
            "chunk-1", ChunkStatus.PROCESSING
        )

    def test_raises_error_when_lock_not_acquired(self, mock_services):
        """ChunkProcessingError raised when lock cannot be acquired."""
        from app.workers.tasks.chunked_document_tasks import (
            ChunkProcessingError,
            process_single_chunk,
        )

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.get_storage_service",
                return_value=mock_services["storage_service"],
            ):
                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service",
                    return_value=mock_services["doc_service"],
                ):
                    with patch(
                        "app.workers.tasks.chunked_document_tasks.acquire_chunk_lock"
                    ) as mock_lock:
                        # Lock returns False (not acquired)
                        mock_lock.return_value.__enter__ = MagicMock(return_value=False)
                        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

                        with pytest.raises(ChunkProcessingError) as exc:
                            process_single_chunk(
                                document_id="doc-456",
                                matter_id="matter-123",
                                chunk_id="chunk-1",
                                chunk_index=0,
                                page_start=1,
                                page_end=25,
                            )

        assert "lock" in str(exc.value).lower()


class TestRetryFailedChunks:
    """Tests for retry_failed_chunks task."""

    def test_returns_no_failed_chunks_when_none(self, mock_services):
        """Returns appropriate status when no failed chunks exist."""
        from app.workers.tasks.chunked_document_tasks import retry_failed_chunks

        mock_services["chunk_service"].get_failed_chunks = AsyncMock(return_value=[])

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            result = retry_failed_chunks(
                document_id="doc-456",
                matter_id="matter-123",
            )

        assert result["status"] == "no_failed_chunks"

    def test_resets_failed_chunks_and_dispatches(self, mock_services, sample_chunks):
        """Failed chunks are reset and reprocessing is dispatched."""
        from app.workers.tasks.chunked_document_tasks import retry_failed_chunks

        # Mark chunks as failed
        for chunk in sample_chunks:
            chunk.status = ChunkStatus.FAILED

        mock_services["chunk_service"].get_failed_chunks = AsyncMock(
            return_value=sample_chunks
        )
        mock_services["chunk_service"].reset_chunk_for_retry = AsyncMock()

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_chunk_service",
            return_value=mock_services["chunk_service"],
        ):
            with patch(
                "app.workers.tasks.chunked_document_tasks.process_document_chunked"
            ) as mock_process:
                mock_process.delay = MagicMock()

                result = retry_failed_chunks(
                    document_id="doc-456",
                    matter_id="matter-123",
                )

        # Verify chunks were reset
        assert mock_services["chunk_service"].reset_chunk_for_retry.call_count == 2

        # Verify reprocessing was dispatched
        mock_process.delay.assert_called_once()

        assert result["status"] == "retry_dispatched"
        assert result["chunks_reset"] == 2


class TestMergeAndStoreResults:
    """Tests for _merge_and_store_results function."""

    def test_merges_results_correctly(self):
        """Chunk results are merged with correct page offsets."""
        from app.workers.tasks.chunked_document_tasks import _merge_and_store_results

        successful_results = [
            {
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 25,
                "bounding_boxes": [{"page": 1, "text": "Chunk 0"}],
                "full_text": "Text from chunk 0",
                "confidence": 0.95,
                "page_count": 25,
            },
            {
                "chunk_index": 1,
                "page_start": 26,
                "page_end": 50,
                "bounding_boxes": [{"page": 1, "text": "Chunk 1"}],
                "full_text": "Text from chunk 1",
                "confidence": 0.87,
                "page_count": 25,
            },
        ]

        with patch(
            "app.workers.tasks.chunked_document_tasks.get_ocr_result_merger"
        ) as mock_merger:
            mock_merged = MagicMock()
            mock_merged.bounding_boxes = [
                {"page": 1},
                {"page": 26},
            ]
            mock_merged.full_text = "Combined text"
            mock_merged.overall_confidence = 0.91
            mock_merged.page_count = 50
            mock_merged.chunk_count = 2
            mock_merger.return_value.merge_results.return_value = mock_merged

            with patch(
                "app.workers.tasks.chunked_document_tasks.get_bounding_box_service"
            ) as mock_bbox:
                mock_bbox.return_value.delete_bounding_boxes.return_value = None
                mock_bbox.return_value.save_bounding_boxes.return_value = 2

                with patch(
                    "app.workers.tasks.chunked_document_tasks.get_document_service"
                ) as mock_doc:
                    mock_doc.return_value.update_ocr_status.return_value = None

                    with patch(
                        "app.workers.tasks.chunked_document_tasks.get_chunk_cleanup_service"
                    ) as mock_cleanup:
                        mock_cleanup.return_value.cleanup_document_chunks = AsyncMock()

                        with patch(
                            "app.workers.tasks.chunked_document_tasks.get_chunk_progress_tracker"
                        ) as mock_tracker:
                            mock_tracker.return_value.start_merge_stage = AsyncMock()

                            with patch(
                                "app.workers.tasks.chunked_document_tasks.broadcast_document_status"
                            ):
                                result = _merge_and_store_results(
                                    document_id="doc-456",
                                    matter_id="matter-123",
                                    successful_results=successful_results,
                                )

        assert result["status"] == "ocr_complete"
        assert result["chunk_count"] == 2
        assert result["page_count"] == 50
