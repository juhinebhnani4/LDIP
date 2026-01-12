"""Tests for document processing Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.document import DocumentStatus
from app.models.ocr import OCRBoundingBox, OCRPage, OCRResult
from app.services.document_service import DocumentServiceError
from app.services.ocr import OCRServiceError
from app.services.storage_service import StorageError
from app.workers.tasks.document_tasks import (
    MAX_RETRIES,
    PDF_MAGIC_BYTES,
    _handle_max_retries_exceeded,
    _validate_pdf_content,
    process_document,
)


class TestProcessDocumentTask:
    """Tests for process_document Celery task."""

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        doc_service = MagicMock()
        doc_service.get_document_for_processing.return_value = (
            "path/to/file.pdf",
            "matter-123",
        )

        storage_service = MagicMock()
        # Use valid PDF magic bytes for content validation
        storage_service.download_file.return_value = b"%PDF-1.4 fake pdf content"

        ocr_processor = MagicMock()
        ocr_processor.process_document.return_value = OCRResult(
            document_id="doc-123",
            pages=[
                OCRPage(
                    page_number=1,
                    text="Page 1 text",
                    confidence=0.95,
                    image_quality_score=0.9,
                ),
            ],
            bounding_boxes=[
                OCRBoundingBox(
                    page=1,
                    x=10.0,
                    y=20.0,
                    width=30.0,
                    height=10.0,
                    text="Test",
                    confidence=0.95,
                ),
            ],
            full_text="Page 1 text",
            overall_confidence=0.95,
            processing_time_ms=100,
            page_count=1,
        )

        bbox_service = MagicMock()
        bbox_service.save_bounding_boxes.return_value = 1

        return {
            "document_service": doc_service,
            "storage_service": storage_service,
            "ocr_processor": ocr_processor,
            "bounding_box_service": bbox_service,
        }

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_successful_processing(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should process document successfully and update status."""
        # Setup mocks
        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        # Execute task directly (run() bypasses celery binding)
        result = process_document.run("doc-123")

        # Verify result
        assert result["status"] == "ocr_complete"
        assert result["document_id"] == "doc-123"
        assert result["page_count"] == 1
        assert result["bbox_count"] == 1

        # Verify document service calls
        doc_service = mock_services["document_service"]
        doc_service.get_document_for_processing.assert_called_once_with("doc-123")
        doc_service.update_ocr_status.assert_called()

        # Verify storage service calls
        storage_service = mock_services["storage_service"]
        storage_service.download_file.assert_called_once_with("path/to/file.pdf")

        # Verify OCR processor calls
        ocr_processor = mock_services["ocr_processor"]
        ocr_processor.process_document.assert_called_once()

        # Verify bounding box service calls
        bbox_service = mock_services["bounding_box_service"]
        bbox_service.delete_bounding_boxes.assert_called_once_with("doc-123")
        bbox_service.save_bounding_boxes.assert_called_once()

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_updates_status_to_processing(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should update status to processing at start."""
        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        process_document.run("doc-123")

        # Check first call to update_ocr_status was PROCESSING
        doc_service = mock_services["document_service"]
        first_call = doc_service.update_ocr_status.call_args_list[0]
        assert first_call.kwargs["status"] == DocumentStatus.PROCESSING

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_updates_status_to_ocr_complete(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should update status to ocr_complete on success."""
        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        process_document.run("doc-123")

        # Check last call to update_ocr_status was OCR_COMPLETE
        doc_service = mock_services["document_service"]
        last_call = doc_service.update_ocr_status.call_args_list[-1]
        assert last_call.kwargs["status"] == DocumentStatus.OCR_COMPLETE

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_broadcasts_status_updates(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should broadcast status updates via pub/sub."""
        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        process_document.run("doc-123")

        # Should broadcast processing and completion
        assert mock_broadcast.call_count >= 2

        # First broadcast should be processing
        first_call = mock_broadcast.call_args_list[0]
        assert first_call.kwargs["status"] == "processing"

        # Second broadcast should be ocr_complete
        second_call = mock_broadcast.call_args_list[1]
        assert second_call.kwargs["status"] == "ocr_complete"

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_handles_storage_error(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should raise StorageError for retry."""
        mock_services["storage_service"].download_file.side_effect = StorageError(
            message="Download failed",
            code="DOWNLOAD_FAILED",
        )

        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        with pytest.raises(StorageError):
            process_document.run("doc-123")

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_handles_ocr_error(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should raise OCRServiceError for retry."""
        mock_services["ocr_processor"].process_document.side_effect = OCRServiceError(
            message="OCR failed",
            code="OCR_FAILED",
        )

        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        with pytest.raises(OCRServiceError):
            process_document.run("doc-123")

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    @patch("app.workers.tasks.document_tasks.get_bounding_box_service")
    @patch("app.workers.tasks.document_tasks.get_ocr_processor")
    @patch("app.workers.tasks.document_tasks.get_storage_service")
    @patch("app.workers.tasks.document_tasks.get_document_service")
    def test_handles_document_service_error(
        self,
        mock_get_doc: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ocr: MagicMock,
        mock_get_bbox: MagicMock,
        mock_broadcast: MagicMock,
        mock_services: dict,
    ) -> None:
        """Should handle DocumentServiceError without retry."""
        mock_services["document_service"].get_document_for_processing.side_effect = (
            DocumentServiceError(
                message="Document not found",
                code="NOT_FOUND",
            )
        )

        mock_get_doc.return_value = mock_services["document_service"]
        mock_get_storage.return_value = mock_services["storage_service"]
        mock_get_ocr.return_value = mock_services["ocr_processor"]
        mock_get_bbox.return_value = mock_services["bounding_box_service"]

        result = process_document.run("doc-123")

        assert result["status"] == "ocr_failed"
        assert result["error_code"] == "NOT_FOUND"


class TestHandleMaxRetriesExceeded:
    """Tests for _handle_max_retries_exceeded helper."""

    def test_updates_status_to_failed(self) -> None:
        """Should update document status to OCR_FAILED."""
        doc_service = MagicMock()

        _handle_max_retries_exceeded(
            doc_service=doc_service,
            document_id="doc-123",
            error=Exception("Test error"),
        )

        doc_service.update_ocr_status.assert_called_once()
        call_kwargs = doc_service.update_ocr_status.call_args.kwargs
        assert call_kwargs["status"] == DocumentStatus.OCR_FAILED
        assert "Max retries exceeded" in call_kwargs["ocr_error"]

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    def test_broadcasts_failure_when_matter_id_provided(
        self,
        mock_broadcast: MagicMock,
    ) -> None:
        """Should broadcast failure status when matter_id is provided."""
        doc_service = MagicMock()

        _handle_max_retries_exceeded(
            doc_service=doc_service,
            document_id="doc-123",
            error=Exception("Test error"),
            matter_id="matter-456",
        )

        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["status"] == "ocr_failed"
        assert call_kwargs["matter_id"] == "matter-456"
        assert call_kwargs["document_id"] == "doc-123"

    @patch("app.workers.tasks.document_tasks.broadcast_document_status")
    def test_does_not_broadcast_without_matter_id(
        self,
        mock_broadcast: MagicMock,
    ) -> None:
        """Should not broadcast when matter_id is not provided."""
        doc_service = MagicMock()

        _handle_max_retries_exceeded(
            doc_service=doc_service,
            document_id="doc-123",
            error=Exception("Test error"),
            matter_id=None,
        )

        mock_broadcast.assert_not_called()

    def test_returns_failure_result(self) -> None:
        """Should return dict with failure status."""
        doc_service = MagicMock()

        result = _handle_max_retries_exceeded(
            doc_service=doc_service,
            document_id="doc-123",
            error=Exception("Test error"),
        )

        assert result["status"] == "ocr_failed"
        assert result["document_id"] == "doc-123"
        assert "Max retries exceeded" in result["error_message"]

    def test_extracts_error_code_from_exception(self) -> None:
        """Should extract error code from exception if available."""
        doc_service = MagicMock()

        error = OCRServiceError(
            message="Test error",
            code="CUSTOM_ERROR_CODE",
        )

        result = _handle_max_retries_exceeded(
            doc_service=doc_service,
            document_id="doc-123",
            error=error,
        )

        assert result["error_code"] == "CUSTOM_ERROR_CODE"

    def test_handles_doc_service_error_gracefully(self) -> None:
        """Should not raise if doc service update fails."""
        doc_service = MagicMock()
        doc_service.update_ocr_status.side_effect = DocumentServiceError(
            message="Update failed"
        )

        # Should not raise
        result = _handle_max_retries_exceeded(
            doc_service=doc_service,
            document_id="doc-123",
            error=Exception("Test error"),
        )

        assert result["status"] == "ocr_failed"


class TestValidatePdfContent:
    """Tests for PDF content validation."""

    def test_valid_pdf_passes(self) -> None:
        """Should not raise for valid PDF content."""
        valid_content = b"%PDF-1.4 some pdf content here"
        # Should not raise
        _validate_pdf_content(valid_content, "doc-123")

    def test_invalid_pdf_raises_error(self) -> None:
        """Should raise OCRServiceError for non-PDF content."""
        invalid_content = b"This is not a PDF file"

        with pytest.raises(OCRServiceError) as exc_info:
            _validate_pdf_content(invalid_content, "doc-123")

        assert exc_info.value.code == "INVALID_PDF_FORMAT"
        assert exc_info.value.is_retryable is False

    def test_empty_content_raises_error(self) -> None:
        """Should raise OCRServiceError for empty content."""
        empty_content = b""

        with pytest.raises(OCRServiceError) as exc_info:
            _validate_pdf_content(empty_content, "doc-123")

        assert exc_info.value.code == "INVALID_PDF_FORMAT"

    def test_pdf_magic_bytes_constant(self) -> None:
        """Should have correct PDF magic bytes constant."""
        assert PDF_MAGIC_BYTES == b"%PDF-"


class TestExtractEntitiesTask:
    """Tests for extract_entities Celery task."""

    @pytest.fixture
    def mock_mig_services(self) -> dict:
        """Create mock MIG services for testing."""
        from app.models.entity import (
            EntityExtractionResult,
            EntityNode,
            EntityType,
            ExtractedEntity,
        )
        from datetime import datetime, timezone

        doc_service = MagicMock()
        doc_service.get_document_for_processing.return_value = (
            "path/to/file.pdf",
            "matter-123",
        )

        # Mock extractor
        extractor = MagicMock()
        extractor.extract_entities_sync.return_value = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test Person",
                    canonical_name="Test Person",
                    type=EntityType.PERSON,
                    roles=["plaintiff"],
                    confidence=0.95,
                ),
            ],
            relationships=[],
            source_document_id="doc-123",
            source_chunk_id="chunk-456",
        )

        # Mock graph service
        graph_service = MagicMock()
        graph_service.save_entities = MagicMock(return_value=[
            EntityNode(
                id="entity-123",
                matter_id="matter-123",
                canonical_name="Test Person",
                entity_type=EntityType.PERSON,
                metadata={},
                mention_count=1,
                aliases=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        ])

        return {
            "document_service": doc_service,
            "mig_extractor": extractor,
            "mig_graph_service": graph_service,
        }

    @patch("app.workers.tasks.document_tasks.get_service_client")
    def test_successful_entity_extraction(
        self,
        mock_get_client: MagicMock,
        mock_mig_services: dict,
    ) -> None:
        """Should extract entities from document chunks."""
        from app.workers.tasks.document_tasks import extract_entities

        # Mock database client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock chunks query
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "chunk-1", "content": "Test content", "chunk_type": "child", "page_number": 1},
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_response

        # Make graph_service.save_entities an async mock
        import asyncio
        async def mock_save_entities(*args, **kwargs):
            return mock_mig_services["mig_graph_service"].save_entities.return_value
        mock_mig_services["mig_graph_service"].save_entities = mock_save_entities

        # Execute task with prev_result indicating successful embedding
        result = extract_entities.run(
            prev_result={"status": "searchable", "document_id": "doc-123"},
            document_service=mock_mig_services["document_service"],
            mig_extractor=mock_mig_services["mig_extractor"],
            mig_graph_service=mock_mig_services["mig_graph_service"],
        )

        # Verify result
        assert result["status"] == "entity_extraction_complete"
        assert result["document_id"] == "doc-123"
        assert result["entities_extracted"] == 1

    @patch("app.workers.tasks.document_tasks.get_service_client")
    def test_skips_when_previous_task_failed(
        self,
        mock_get_client: MagicMock,
        mock_mig_services: dict,
    ) -> None:
        """Should skip extraction when previous task failed."""
        from app.workers.tasks.document_tasks import extract_entities

        # Execute task with failed embedding status
        result = extract_entities.run(
            prev_result={"status": "embedding_failed", "document_id": "doc-123"},
            document_service=mock_mig_services["document_service"],
        )

        # Verify result - should skip
        assert result["status"] == "entity_extraction_skipped"
        assert "embedding_failed" in result["reason"]

    def test_returns_error_when_no_document_id(self) -> None:
        """Should return error when no document_id provided."""
        from app.workers.tasks.document_tasks import extract_entities

        result = extract_entities.run(prev_result=None, document_id=None)

        assert result["status"] == "entity_extraction_failed"
        assert result["error_code"] == "NO_DOCUMENT_ID"

    @patch("app.workers.tasks.document_tasks.get_service_client")
    def test_handles_no_chunks(
        self,
        mock_get_client: MagicMock,
        mock_mig_services: dict,
    ) -> None:
        """Should handle documents with no chunks gracefully."""
        from app.workers.tasks.document_tasks import extract_entities

        # Mock database client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock empty chunks query
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_response

        # Execute task
        result = extract_entities.run(
            prev_result={"status": "searchable", "document_id": "doc-123"},
            document_service=mock_mig_services["document_service"],
        )

        # Verify result
        assert result["status"] == "entity_extraction_complete"
        assert result["entities_extracted"] == 0
        assert "No chunks found" in result["reason"]
