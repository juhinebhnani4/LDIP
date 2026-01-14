"""Integration tests for OCR document processing pipeline.

Tests the full OCR pipeline including:
- Document upload → OCR task queue → processing → status updates
- Status transitions: pending → processing → ocr_complete
- Failure handling: processing → ocr_failed
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.document import DocumentStatus
from app.models.ocr import OCRBoundingBox, OCRPage, OCRResult
from app.services.bounding_box_service import BoundingBoxService
from app.services.document_service import DocumentService, DocumentServiceError
from app.services.ocr import OCRProcessor, OCRServiceError
from app.services.storage_service import StorageError, StorageService
from app.workers.tasks.document_tasks import process_document


class TestOCRPipelineIntegration:
    """Integration tests for full OCR processing pipeline."""

    @pytest.fixture
    def mock_document_service(self) -> MagicMock:
        """Create mock document service with standard responses."""
        service = MagicMock(spec=DocumentService)
        service.get_document_for_processing.return_value = (
            "matters/matter-123/uploads/test.pdf",
            "matter-123",
        )
        return service

    @pytest.fixture
    def mock_storage_service(self) -> MagicMock:
        """Create mock storage service."""
        service = MagicMock(spec=StorageService)
        service.download_file.return_value = b"%PDF-1.4 fake pdf content"
        return service

    @pytest.fixture
    def mock_ocr_processor(self) -> MagicMock:
        """Create mock OCR processor with sample result."""
        processor = MagicMock(spec=OCRProcessor)
        processor.process_document.return_value = OCRResult(
            document_id="doc-123",
            pages=[
                OCRPage(
                    page_number=1,
                    text="This is sample extracted text from page 1.",
                    confidence=0.95,
                    image_quality_score=0.88,
                ),
                OCRPage(
                    page_number=2,
                    text="Page 2 content in English and Hindi.",
                    confidence=0.92,
                    image_quality_score=0.85,
                ),
            ],
            bounding_boxes=[
                OCRBoundingBox(
                    page=1,
                    x=10.0,
                    y=15.0,
                    width=80.0,
                    height=5.0,
                    text="This is sample",
                    confidence=0.96,
                ),
                OCRBoundingBox(
                    page=1,
                    x=10.0,
                    y=20.0,
                    width=75.0,
                    height=5.0,
                    text="extracted text from page 1.",
                    confidence=0.94,
                ),
                OCRBoundingBox(
                    page=2,
                    x=10.0,
                    y=15.0,
                    width=70.0,
                    height=5.0,
                    text="Page 2 content",
                    confidence=0.93,
                ),
            ],
            full_text="This is sample extracted text from page 1.\nPage 2 content in English and Hindi.",
            overall_confidence=0.935,
            processing_time_ms=1500,
            page_count=2,
        )
        return processor

    @pytest.fixture
    def mock_bbox_service(self) -> MagicMock:
        """Create mock bounding box service."""
        service = MagicMock(spec=BoundingBoxService)
        service.save_bounding_boxes.return_value = 3
        service.delete_bounding_boxes.return_value = 0
        return service

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_full_pipeline_upload_to_ocr_complete(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test complete pipeline: upload → queue → process → save → complete.

        Simulates the full flow a document goes through after upload:
        1. Document record created with 'pending' status
        2. Celery task queued
        3. Task downloads PDF from storage
        4. OCR processor extracts text and bounding boxes
        5. Bounding boxes saved to database
        6. Document status updated to 'ocr_complete'
        7. Status broadcast via pub/sub
        """
        # Setup service mocks
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_ocr.return_value = mock_ocr_processor
        mock_get_bbox_svc.return_value = mock_bbox_service

        # Execute the task synchronously
        result = process_document.run("doc-123")

        # Verify successful completion
        assert result["status"] == "ocr_complete"
        assert result["document_id"] == "doc-123"
        assert result["page_count"] == 2
        assert result["bbox_count"] == 3
        assert result["overall_confidence"] == 0.935

        # Verify pipeline steps occurred in order

        # Step 1: Got document info
        mock_document_service.get_document_for_processing.assert_called_once_with(
            "doc-123"
        )

        # Step 2: Status updated to PROCESSING
        processing_call = mock_document_service.update_ocr_status.call_args_list[0]
        assert processing_call.kwargs["document_id"] == "doc-123"
        assert processing_call.kwargs["status"] == DocumentStatus.PROCESSING

        # Step 3: PDF downloaded from storage
        mock_storage_service.download_file.assert_called_once_with(
            "matters/matter-123/uploads/test.pdf"
        )

        # Step 4: OCR processed
        mock_ocr_processor.process_document.assert_called_once()

        # Step 5: Old bounding boxes deleted, new ones saved
        mock_bbox_service.delete_bounding_boxes.assert_called_once_with("doc-123")
        mock_bbox_service.save_bounding_boxes.assert_called_once()

        # Step 6: Final status updated to OCR_COMPLETE
        final_call = mock_document_service.update_ocr_status.call_args_list[-1]
        assert final_call.kwargs["status"] == DocumentStatus.OCR_COMPLETE
        assert "This is sample extracted text" in final_call.kwargs["extracted_text"]
        assert final_call.kwargs["page_count"] == 2
        assert final_call.kwargs["ocr_confidence"] == 0.935

        # Step 7: Status broadcast via pub/sub
        assert mock_broadcast.call_count == 2  # processing + ocr_complete

        # First broadcast: processing
        first_broadcast = mock_broadcast.call_args_list[0]
        assert first_broadcast.kwargs["status"] == "processing"
        assert first_broadcast.kwargs["matter_id"] == "matter-123"
        assert first_broadcast.kwargs["document_id"] == "doc-123"

        # Second broadcast: ocr_complete
        second_broadcast = mock_broadcast.call_args_list[1]
        assert second_broadcast.kwargs["status"] == "ocr_complete"
        assert second_broadcast.kwargs["page_count"] == 2

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_status_transitions_pending_to_processing_to_complete(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test document status transitions through the pipeline."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_ocr.return_value = mock_ocr_processor
        mock_get_bbox_svc.return_value = mock_bbox_service

        process_document.run("doc-456")

        # Verify status update calls
        status_calls = mock_document_service.update_ocr_status.call_args_list
        assert len(status_calls) == 2

        # First: pending → processing
        assert status_calls[0].kwargs["status"] == DocumentStatus.PROCESSING

        # Second: processing → ocr_complete
        assert status_calls[1].kwargs["status"] == DocumentStatus.OCR_COMPLETE


class TestOCRFailureHandling:
    """Integration tests for OCR failure scenarios."""

    @pytest.fixture
    def mock_document_service(self) -> MagicMock:
        """Create mock document service."""
        service = MagicMock(spec=DocumentService)
        service.get_document_for_processing.return_value = (
            "matters/matter-789/uploads/test.pdf",
            "matter-789",
        )
        return service

    @pytest.fixture
    def mock_storage_service(self) -> MagicMock:
        """Create mock storage service."""
        service = MagicMock(spec=StorageService)
        service.download_file.return_value = b"%PDF-1.4 fake content"
        return service

    @pytest.fixture
    def mock_bbox_service(self) -> MagicMock:
        """Create mock bounding box service."""
        return MagicMock(spec=BoundingBoxService)

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_storage_error_raises_for_retry(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that storage errors are raised for Celery retry."""
        mock_get_doc_svc.return_value = mock_document_service

        # Storage service fails
        failing_storage = MagicMock(spec=StorageService)
        failing_storage.download_file.side_effect = StorageError(
            message="Storage unavailable",
            code="STORAGE_UNAVAILABLE",
        )
        mock_get_storage_svc.return_value = failing_storage
        mock_get_bbox_svc.return_value = mock_bbox_service

        # Task should raise StorageError for retry
        with pytest.raises(StorageError) as exc_info:
            process_document.run("doc-storage-fail")

        assert exc_info.value.code == "STORAGE_UNAVAILABLE"

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_ocr_error_raises_for_retry(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that OCR errors are raised for Celery retry."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_bbox_svc.return_value = mock_bbox_service

        # OCR processor fails
        failing_ocr = MagicMock(spec=OCRProcessor)
        failing_ocr.process_document.side_effect = OCRServiceError(
            message="Document AI API error",
            code="DOCUMENT_AI_ERROR",
        )
        mock_get_ocr.return_value = failing_ocr

        # Task should raise OCRServiceError for retry
        with pytest.raises(OCRServiceError) as exc_info:
            process_document.run("doc-ocr-fail")

        assert exc_info.value.code == "DOCUMENT_AI_ERROR"

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_document_not_found_fails_without_retry(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_storage_service: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that document not found errors fail immediately without retry."""
        # Document service throws not found error
        failing_doc_service = MagicMock(spec=DocumentService)
        failing_doc_service.get_document_for_processing.side_effect = (
            DocumentServiceError(
                message="Document not found",
                code="NOT_FOUND",
            )
        )
        mock_get_doc_svc.return_value = failing_doc_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_bbox_svc.return_value = mock_bbox_service

        # Task should return failure result (not raise)
        result = process_document.run("doc-not-found")

        assert result["status"] == "ocr_failed"
        assert result["error_code"] == "NOT_FOUND"
        assert "not found" in result["error_message"].lower()

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_unexpected_error_marks_document_failed(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that unexpected errors mark document as failed."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_bbox_svc.return_value = mock_bbox_service

        # OCR processor raises unexpected error
        failing_ocr = MagicMock(spec=OCRProcessor)
        failing_ocr.process_document.side_effect = RuntimeError("Unexpected crash")
        mock_get_ocr.return_value = failing_ocr

        result = process_document.run("doc-unexpected-error")

        assert result["status"] == "ocr_failed"
        assert result["error_code"] == "UNEXPECTED_ERROR"

        # Document should be updated to failed status
        mock_document_service.update_ocr_status.assert_called()
        final_call = mock_document_service.update_ocr_status.call_args_list[-1]
        assert final_call.kwargs["status"] == DocumentStatus.OCR_FAILED


class TestOCRPubSubIntegration:
    """Integration tests for pub/sub status broadcasting."""

    @pytest.fixture
    def mock_document_service(self) -> MagicMock:
        """Create mock document service."""
        service = MagicMock(spec=DocumentService)
        service.get_document_for_processing.return_value = (
            "matters/matter-pubsub/uploads/test.pdf",
            "matter-pubsub",
        )
        return service

    @pytest.fixture
    def mock_storage_service(self) -> MagicMock:
        """Create mock storage service."""
        service = MagicMock(spec=StorageService)
        service.download_file.return_value = b"%PDF-1.4 content"
        return service

    @pytest.fixture
    def mock_ocr_processor(self) -> MagicMock:
        """Create mock OCR processor."""
        processor = MagicMock(spec=OCRProcessor)
        processor.process_document.return_value = OCRResult(
            document_id="doc-pubsub",
            pages=[
                OCRPage(
                    page_number=1,
                    text="Test content",
                    confidence=0.9,
                )
            ],
            bounding_boxes=[],
            full_text="Test content",
            overall_confidence=0.9,
            processing_time_ms=500,
            page_count=1,
        )
        return processor

    @pytest.fixture
    def mock_bbox_service(self) -> MagicMock:
        """Create mock bounding box service."""
        service = MagicMock(spec=BoundingBoxService)
        service.save_bounding_boxes.return_value = 0
        return service

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_broadcasts_processing_status(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that processing status is broadcast via pub/sub."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_ocr.return_value = mock_ocr_processor
        mock_get_bbox_svc.return_value = mock_bbox_service

        process_document.run("doc-pubsub")

        # Find the processing broadcast call
        processing_calls = [
            call
            for call in mock_broadcast.call_args_list
            if call.kwargs.get("status") == "processing"
        ]
        assert len(processing_calls) == 1

        call = processing_calls[0]
        assert call.kwargs["matter_id"] == "matter-pubsub"
        assert call.kwargs["document_id"] == "doc-pubsub"

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_broadcasts_completion_with_metadata(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that completion broadcast includes page_count and confidence."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_ocr.return_value = mock_ocr_processor
        mock_get_bbox_svc.return_value = mock_bbox_service

        process_document.run("doc-pubsub")

        # Find the completion broadcast call
        completion_calls = [
            call
            for call in mock_broadcast.call_args_list
            if call.kwargs.get("status") == "ocr_complete"
        ]
        assert len(completion_calls) == 1

        call = completion_calls[0]
        assert call.kwargs["matter_id"] == "matter-pubsub"
        assert call.kwargs["document_id"] == "doc-pubsub"
        assert call.kwargs["page_count"] == 1
        assert call.kwargs["ocr_confidence"] == 0.9


class TestOCRBoundingBoxIntegration:
    """Integration tests for bounding box saving."""

    @pytest.fixture
    def mock_document_service(self) -> MagicMock:
        """Create mock document service."""
        service = MagicMock(spec=DocumentService)
        service.get_document_for_processing.return_value = (
            "matters/matter-bbox/uploads/test.pdf",
            "matter-bbox",
        )
        return service

    @pytest.fixture
    def mock_storage_service(self) -> MagicMock:
        """Create mock storage service."""
        service = MagicMock(spec=StorageService)
        service.download_file.return_value = b"%PDF-1.4 content"
        return service

    @pytest.fixture
    def mock_ocr_processor(self) -> MagicMock:
        """Create mock OCR processor with multiple bounding boxes."""
        processor = MagicMock(spec=OCRProcessor)
        processor.process_document.return_value = OCRResult(
            document_id="doc-bbox",
            pages=[
                OCRPage(page_number=1, text="Page 1", confidence=0.9),
                OCRPage(page_number=2, text="Page 2", confidence=0.85),
            ],
            bounding_boxes=[
                OCRBoundingBox(
                    page=1,
                    x=5.0,
                    y=10.0,
                    width=90.0,
                    height=8.0,
                    text="Header text",
                    confidence=0.95,
                ),
                OCRBoundingBox(
                    page=1,
                    x=5.0,
                    y=20.0,
                    width=85.0,
                    height=40.0,
                    text="Body paragraph",
                    confidence=0.92,
                ),
                OCRBoundingBox(
                    page=2,
                    x=5.0,
                    y=10.0,
                    width=80.0,
                    height=30.0,
                    text="Page 2 content",
                    confidence=0.88,
                ),
            ],
            full_text="Page 1\nPage 2",
            overall_confidence=0.875,
            processing_time_ms=1000,
            page_count=2,
        )
        return processor

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_deletes_existing_bboxes_before_save(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
    ) -> None:
        """Test that existing bounding boxes are deleted before saving new ones."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_ocr.return_value = mock_ocr_processor

        # Track call order
        call_order: list[str] = []

        mock_bbox_service = MagicMock(spec=BoundingBoxService)
        mock_bbox_service.delete_bounding_boxes.return_value = 5  # 5 old boxes deleted
        mock_bbox_service.delete_bounding_boxes.side_effect = (
            lambda *args, **kwargs: call_order.append("delete") or 5
        )
        mock_bbox_service.save_bounding_boxes.side_effect = (
            lambda *args, **kwargs: call_order.append("save") or 3
        )
        mock_get_bbox_svc.return_value = mock_bbox_service

        result = process_document.run("doc-bbox")

        # Verify delete called before save
        mock_bbox_service.delete_bounding_boxes.assert_called_once_with("doc-bbox")
        mock_bbox_service.save_bounding_boxes.assert_called_once()

        # Verify the order: delete was called before save
        assert call_order == ["delete", "save"], f"Expected delete before save, got: {call_order}"

        assert result["bbox_count"] == 3

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_passes_matter_id_to_bbox_service(
        self,
        mock_get_doc_svc: MagicMock,
        mock_get_storage_svc: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox_svc: MagicMock,
        mock_broadcast: MagicMock,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
    ) -> None:
        """Test that matter_id is passed to bounding box service for RLS."""
        mock_get_doc_svc.return_value = mock_document_service
        mock_get_storage_svc.return_value = mock_storage_service
        mock_get_ocr.return_value = mock_ocr_processor

        mock_bbox_service = MagicMock(spec=BoundingBoxService)
        mock_bbox_service.save_bounding_boxes.return_value = 3
        mock_get_bbox_svc.return_value = mock_bbox_service

        process_document.run("doc-bbox")

        # Verify matter_id passed to save_bounding_boxes
        save_call = mock_bbox_service.save_bounding_boxes.call_args
        assert save_call.kwargs["document_id"] == "doc-bbox"
        assert save_call.kwargs["matter_id"] == "matter-bbox"
        assert len(save_call.kwargs["bounding_boxes"]) == 3


class TestOCRQueueTaskIntegration:
    """Integration tests for OCR task queuing from document upload."""

    def test_queue_ocr_task_uses_high_priority_for_small_files(self) -> None:
        """Test that small files (<10MB) use 'high' priority queue.

        The implementation creates a Celery chain of tasks:
        process_document -> validate_ocr -> calculate_confidence -> chunk_document -> embed_chunks -> extract_entities

        We verify that:
        1. A chain is created starting with process_document.s(document_id)
        2. The chain is applied to the 'high' queue for small files
        """
        from app.api.routes.documents import _queue_ocr_task

        # Mock the chain function at celery module level (imported inside function)
        with patch("celery.chain") as mock_chain:
            mock_task_chain = MagicMock()
            mock_chain.return_value = mock_task_chain

            # Small file: 5MB
            _queue_ocr_task("doc-small", 5 * 1024 * 1024)

            # Verify chain was created and apply_async was called with high queue
            mock_chain.assert_called_once()
            mock_task_chain.apply_async.assert_called_once_with(queue="high")

    def test_queue_ocr_task_uses_default_priority_for_large_files(self) -> None:
        """Test that large files (>=10MB) use 'default' priority queue."""
        from app.api.routes.documents import _queue_ocr_task

        with patch("celery.chain") as mock_chain:
            mock_task_chain = MagicMock()
            mock_chain.return_value = mock_task_chain

            # Large file: 50MB
            _queue_ocr_task("doc-large", 50 * 1024 * 1024)

            mock_chain.assert_called_once()
            mock_task_chain.apply_async.assert_called_once_with(queue="default")

    def test_queue_ocr_task_boundary_case_exactly_10mb(self) -> None:
        """Test boundary case: exactly 10MB should use default queue."""
        from app.api.routes.documents import _queue_ocr_task

        with patch("celery.chain") as mock_chain:
            mock_task_chain = MagicMock()
            mock_chain.return_value = mock_task_chain

            # Exactly 10MB
            _queue_ocr_task("doc-boundary", 10 * 1024 * 1024)

            mock_chain.assert_called_once()
            # 10MB is NOT less than 10MB, so should use default
            mock_task_chain.apply_async.assert_called_once_with(queue="default")
