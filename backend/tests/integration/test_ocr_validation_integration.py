"""Integration tests for OCR validation pipeline.

Tests the full validation pipeline including:
- Pattern-based correction → Gemini validation → Human review queue
- Celery task chaining: process_document → validate_ocr
- Database updates and validation log entries
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ocr import OCRBoundingBox, OCRPage, OCRResult
from app.models.ocr_validation import (
    CorrectionType,
    HumanReviewStatus,
    LowConfidenceWord,
    ValidationResult,
    ValidationStatus,
)
from app.services.bounding_box_service import BoundingBoxService
from app.services.document_service import DocumentService
from app.services.ocr import OCRProcessor
from app.services.ocr.gemini_validator import GeminiOCRValidator
from app.services.ocr.human_review_service import HumanReviewService
from app.services.ocr.pattern_corrector import PatternCorrector, apply_pattern_corrections
from app.services.ocr.validation_extractor import ValidationExtractor
from app.services.storage_service import StorageService
from app.workers.tasks.document_tasks import validate_ocr


class TestValidationPipelineIntegration:
    """Integration tests for full OCR validation pipeline."""

    @pytest.fixture
    def mock_validation_extractor(self) -> MagicMock:
        """Create mock validation extractor."""
        extractor = MagicMock(spec=ValidationExtractor)
        # Default: no low-confidence words
        extractor.extract_low_confidence_words.return_value = ([], [])
        return extractor

    @pytest.fixture
    def mock_gemini_validator(self) -> MagicMock:
        """Create mock Gemini validator."""
        validator = MagicMock(spec=GeminiOCRValidator)
        validator.validate_batch_sync.return_value = []
        return validator

    @pytest.fixture
    def mock_human_review_service(self) -> MagicMock:
        """Create mock human review service."""
        service = MagicMock(spec=HumanReviewService)
        service.add_to_queue.return_value = 0
        return service

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create mock Supabase client."""
        client = MagicMock()
        # Mock table operations
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value.data = []
        mock_table.update.return_value.eq.return_value.execute.return_value.data = []
        mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        client.table.return_value = mock_table
        return client

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    def test_validation_skips_when_no_low_confidence_words(
        self,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
        mock_validation_extractor: MagicMock,
        mock_gemini_validator: MagicMock,
        mock_human_review_service: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test validation completes quickly when no low-confidence words found."""
        mock_get_extractor.return_value = mock_validation_extractor
        mock_get_gemini.return_value = mock_gemini_validator
        mock_get_human_review.return_value = mock_human_review_service
        mock_get_client.return_value = mock_supabase_client

        # No low-confidence words
        mock_validation_extractor.extract_low_confidence_words.return_value = ([], [])

        # Run validate_ocr task
        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-123",
            "matter_id": "matter-123",
        }
        result = validate_ocr.run(prev_result=prev_result)

        # Verify
        assert result["status"] == "validation_complete"
        assert result["document_id"] == "doc-123"
        assert result["pattern_corrections"] == 0
        assert result["gemini_corrections"] == 0
        assert result["human_review_queued"] == 0

        # Gemini should not be called
        mock_gemini_validator.validate_batch_sync.assert_not_called()

        # Human review queue should not be called
        mock_human_review_service.add_to_queue.assert_not_called()

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    @patch("app.workers.tasks.document_tasks.apply_pattern_corrections")
    def test_pattern_corrections_applied_first(
        self,
        mock_apply_patterns: MagicMock,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
        mock_validation_extractor: MagicMock,
        mock_gemini_validator: MagicMock,
        mock_human_review_service: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that pattern corrections are applied before Gemini validation."""
        mock_get_extractor.return_value = mock_validation_extractor
        mock_get_gemini.return_value = mock_gemini_validator
        mock_get_human_review.return_value = mock_human_review_service
        mock_get_client.return_value = mock_supabase_client

        # Words for Gemini validation
        gemini_words = [
            LowConfidenceWord(
                bbox_id="bbox-1",
                text="1O23",  # Has pattern: O -> 0
                confidence=0.70,
                page=1,
                context_before="Rs.",
                context_after="",
                x=10.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
            LowConfidenceWord(
                bbox_id="bbox-2",
                text="Section",  # No pattern match
                confidence=0.75,
                page=1,
                context_before="Under",
                context_after="302",
                x=20.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
        ]
        mock_validation_extractor.extract_low_confidence_words.return_value = (gemini_words, [])

        # Mock pattern correction result
        pattern_corrected = [
            ValidationResult(
                bbox_id="bbox-1",
                original="1O23",
                corrected="1023",
                old_confidence=0.70,
                new_confidence=0.95,
                correction_type=CorrectionType.PATTERN,
                reasoning="O confused with 0",
                was_corrected=True,
            )
        ]
        remaining_words = [gemini_words[1]]  # "Section" remains
        mock_apply_patterns.return_value = (pattern_corrected, remaining_words)

        # Mock Gemini returns no corrections for remaining
        mock_gemini_validator.validate_batch_sync.return_value = [
            ValidationResult(
                bbox_id="bbox-2",
                original="Section",
                corrected="Section",
                old_confidence=0.75,
                new_confidence=0.80,
                correction_type=None,
                reasoning=None,
                was_corrected=False,
            )
        ]

        # Run validate_ocr task
        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-123",
            "matter_id": "matter-123",
        }
        result = validate_ocr.run(prev_result=prev_result)

        # Verify pattern corrections applied first
        mock_apply_patterns.assert_called_once()

        # Verify Gemini only called with remaining words
        mock_gemini_validator.validate_batch_sync.assert_called_once()
        call_args = mock_gemini_validator.validate_batch_sync.call_args[0]
        assert len(call_args[0]) == 1  # Only "Section" word

        # Verify counts
        assert result["pattern_corrections"] == 1
        assert result["gemini_corrections"] == 0

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    def test_very_low_confidence_goes_to_human_review(
        self,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
        mock_validation_extractor: MagicMock,
        mock_gemini_validator: MagicMock,
        mock_human_review_service: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that words with <50% confidence go directly to human review."""
        mock_get_extractor.return_value = mock_validation_extractor
        mock_get_gemini.return_value = mock_gemini_validator
        mock_get_human_review.return_value = mock_human_review_service
        mock_get_client.return_value = mock_supabase_client

        # Words for human review (very low confidence)
        human_words = [
            LowConfidenceWord(
                bbox_id="bbox-low-1",
                text="?????",  # Completely unreadable
                confidence=0.30,
                page=1,
                context_before="filed on",
                context_after="in court",
                x=10.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
            LowConfidenceWord(
                bbox_id="bbox-low-2",
                text="unclear",
                confidence=0.45,
                page=2,
                context_before="amount",
                context_after="rupees",
                x=20.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
        ]
        mock_validation_extractor.extract_low_confidence_words.return_value = ([], human_words)
        mock_human_review_service.add_to_queue.return_value = 2

        # Run validate_ocr task
        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-123",
            "matter_id": "matter-123",
        }
        result = validate_ocr.run(prev_result=prev_result)

        # Verify human review service called
        mock_human_review_service.add_to_queue.assert_called_once()
        call_kwargs = mock_human_review_service.add_to_queue.call_args[1]
        assert call_kwargs["document_id"] == "doc-123"
        assert call_kwargs["matter_id"] == "matter-123"
        assert len(call_kwargs["words"]) == 2

        # Verify result
        assert result["human_review_queued"] == 2
        assert result["validation_status"] == "requires_human_review"


class TestValidationTaskChaining:
    """Tests for Celery task chaining between process_document and validate_ocr."""

    @pytest.fixture
    def mock_document_service(self) -> MagicMock:
        """Create mock document service."""
        service = MagicMock(spec=DocumentService)
        service.get_document_for_processing.return_value = (
            "matters/matter-chain/uploads/test.pdf",
            "matter-chain",
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
            document_id="doc-chain",
            pages=[
                OCRPage(page_number=1, text="Test content", confidence=0.9),
            ],
            bounding_boxes=[
                OCRBoundingBox(
                    page=1,
                    x=10.0,
                    y=15.0,
                    width=80.0,
                    height=5.0,
                    text="Test content",
                    confidence=0.75,  # Below Gemini threshold
                ),
            ],
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
        service.save_bounding_boxes.return_value = 1
        return service

    def test_process_document_result_feeds_validate_ocr(
        self,
        mock_document_service: MagicMock,
        mock_storage_service: MagicMock,
        mock_ocr_processor: MagicMock,
        mock_bbox_service: MagicMock,
    ) -> None:
        """Test that process_document result is correctly passed to validate_ocr."""
        from app.workers.tasks.document_tasks import process_document

        with patch("app.workers.tasks.document_tasks.broadcast_document_status"):
            with patch("app.workers.tasks.document_tasks.get_document_service") as mock_get_doc:
                with patch("app.workers.tasks.document_tasks.get_storage_service") as mock_get_storage:
                    with patch("app.workers.tasks.document_tasks.get_ocr_processor") as mock_get_ocr:
                        with patch("app.workers.tasks.document_tasks.get_bounding_box_service") as mock_get_bbox:
                            mock_get_doc.return_value = mock_document_service
                            mock_get_storage.return_value = mock_storage_service
                            mock_get_ocr.return_value = mock_ocr_processor
                            mock_get_bbox.return_value = mock_bbox_service

                            result = process_document.run("doc-chain")

        # Result should contain fields needed by validate_ocr
        assert result["status"] == "ocr_complete"
        assert result["document_id"] == "doc-chain"
        assert "matter_id" in result
        assert result["matter_id"] == "matter-chain"

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    def test_validate_ocr_accepts_process_document_result(
        self,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test validate_ocr correctly accepts result from process_document."""
        mock_extractor = MagicMock(spec=ValidationExtractor)
        mock_extractor.extract_low_confidence_words.return_value = ([], [])
        mock_get_extractor.return_value = mock_extractor

        mock_gemini = MagicMock(spec=GeminiOCRValidator)
        mock_get_gemini.return_value = mock_gemini

        mock_human_review = MagicMock(spec=HumanReviewService)
        mock_get_human_review.return_value = mock_human_review

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value.data = []
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Simulate result from process_document
        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-chain",
            "matter_id": "matter-chain",
            "page_count": 1,
            "bbox_count": 1,
            "overall_confidence": 0.9,
        }

        result = validate_ocr.run(prev_result=prev_result)

        # Should complete successfully
        assert result["status"] == "validation_complete"
        assert result["document_id"] == "doc-chain"

        # Extractor should be called with document_id
        mock_extractor.extract_low_confidence_words.assert_called_once_with("doc-chain")


class TestValidationDatabaseUpdates:
    """Tests for database updates during validation."""

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    @patch("app.workers.tasks.document_tasks.apply_pattern_corrections")
    def test_updates_bounding_box_text_on_correction(
        self,
        mock_apply_patterns: MagicMock,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that bounding box text is updated when correction is made."""
        mock_extractor = MagicMock(spec=ValidationExtractor)
        mock_extractor.extract_low_confidence_words.return_value = (
            [
                LowConfidenceWord(
                    bbox_id="bbox-update",
                    text="1O23",
                    confidence=0.70,
                    page=1,
                    context_before="",
                    context_after="",
                    x=10.0,
                    y=20.0,
                    width=8.0,
                    height=5.0,
                ),
            ],
            [],
        )
        mock_get_extractor.return_value = mock_extractor

        mock_gemini = MagicMock(spec=GeminiOCRValidator)
        mock_get_gemini.return_value = mock_gemini

        mock_human_review = MagicMock(spec=HumanReviewService)
        mock_get_human_review.return_value = mock_human_review

        # Mock pattern correction
        mock_apply_patterns.return_value = (
            [
                ValidationResult(
                    bbox_id="bbox-update",
                    original="1O23",
                    corrected="1023",
                    old_confidence=0.70,
                    new_confidence=0.95,
                    correction_type=CorrectionType.PATTERN,
                    reasoning="O confused with 0",
                    was_corrected=True,
                )
            ],
            [],
        )

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value.data = []
        mock_table.insert.return_value.execute.return_value.data = []
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-update",
            "matter_id": "matter-update",
        }
        validate_ocr.run(prev_result=prev_result)

        # Verify bounding_boxes table updated
        update_calls = [
            call for call in mock_client.table.call_args_list
            if call[0][0] == "bounding_boxes"
        ]
        assert len(update_calls) > 0

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    @patch("app.workers.tasks.document_tasks.apply_pattern_corrections")
    def test_creates_validation_log_entries(
        self,
        mock_apply_patterns: MagicMock,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that validation log entries are created for corrections."""
        mock_extractor = MagicMock(spec=ValidationExtractor)
        mock_extractor.extract_low_confidence_words.return_value = (
            [
                LowConfidenceWord(
                    bbox_id="bbox-log",
                    text="1O23",
                    confidence=0.70,
                    page=1,
                    context_before="",
                    context_after="",
                    x=10.0,
                    y=20.0,
                    width=8.0,
                    height=5.0,
                ),
            ],
            [],
        )
        mock_get_extractor.return_value = mock_extractor

        mock_gemini = MagicMock(spec=GeminiOCRValidator)
        mock_get_gemini.return_value = mock_gemini

        mock_human_review = MagicMock(spec=HumanReviewService)
        mock_get_human_review.return_value = mock_human_review

        # Mock pattern correction
        mock_apply_patterns.return_value = (
            [
                ValidationResult(
                    bbox_id="bbox-log",
                    original="1O23",
                    corrected="1023",
                    old_confidence=0.70,
                    new_confidence=0.95,
                    correction_type=CorrectionType.PATTERN,
                    reasoning="O confused with 0",
                    was_corrected=True,
                )
            ],
            [],
        )

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value.data = []
        mock_table.insert.return_value.execute.return_value.data = []
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-log",
            "matter_id": "matter-log",
        }
        validate_ocr.run(prev_result=prev_result)

        # Verify ocr_validation_log table has insert called
        insert_calls = [
            call for call in mock_client.table.call_args_list
            if call[0][0] == "ocr_validation_log"
        ]
        assert len(insert_calls) > 0

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    def test_updates_document_validation_status(
        self,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that document validation_status is updated."""
        mock_extractor = MagicMock(spec=ValidationExtractor)
        mock_extractor.extract_low_confidence_words.return_value = ([], [])
        mock_get_extractor.return_value = mock_extractor

        mock_gemini = MagicMock(spec=GeminiOCRValidator)
        mock_get_gemini.return_value = mock_gemini

        mock_human_review = MagicMock(spec=HumanReviewService)
        mock_get_human_review.return_value = mock_human_review

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value.data = []
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-status",
            "matter_id": "matter-status",
        }
        validate_ocr.run(prev_result=prev_result)

        # Verify documents table has validation_status updated
        update_calls = [
            call for call in mock_client.table.call_args_list
            if call[0][0] == "documents"
        ]
        assert len(update_calls) > 0


class TestPatternCorrectionIntegration:
    """Integration tests for pattern-based corrections."""

    def test_real_pattern_corrections_for_ocr_errors(self) -> None:
        """Test actual pattern correction behavior with realistic OCR errors."""
        words = [
            LowConfidenceWord(
                bbox_id="1",
                text="Rs. 1O,OOO",
                confidence=0.70,
                page=1,
                context_before="Amount:",
                context_after="only",
                x=10.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
            LowConfidenceWord(
                bbox_id="2",
                text="1l/O1/2024",  # Date with l and O errors
                confidence=0.65,
                page=1,
                context_before="Dated:",
                context_after="",
                x=20.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
            LowConfidenceWord(
                bbox_id="3",
                text="Section",  # No correction needed
                confidence=0.75,
                page=1,
                context_before="Under",
                context_after="302",
                x=30.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
        ]

        corrected, remaining = apply_pattern_corrections(words)

        # Should have corrected 2 words
        assert len(corrected) == 2

        # Rs. 1O,OOO -> Rs. 10,000
        currency_result = next(r for r in corrected if "Rs" in r.original)
        assert currency_result.corrected == "Rs. 10,000"
        assert currency_result.correction_type == CorrectionType.PATTERN

        # Section should remain (no pattern match)
        assert len(remaining) == 1
        assert remaining[0].text == "Section"


class TestHumanReviewIntegration:
    """Integration tests for human review queue."""

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create mock Supabase client."""
        client = MagicMock()
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value.data = [
            {"id": "review-1"},
            {"id": "review-2"},
        ]
        client.table.return_value = mock_table
        return client

    def test_human_review_service_adds_to_queue(
        self,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that HumanReviewService correctly adds items to queue."""
        service = HumanReviewService(client=mock_supabase_client)

        words = [
            LowConfidenceWord(
                bbox_id="bbox-review-1",
                text="unreadable",
                confidence=0.30,
                page=1,
                context_before="filed on",
                context_after="in court",
                x=10.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
            LowConfidenceWord(
                bbox_id="bbox-review-2",
                text="unclear",
                confidence=0.40,
                page=2,
                context_before="amount",
                context_after="rupees",
                x=20.0,
                y=20.0,
                width=8.0,
                height=5.0,
            ),
        ]

        count = service.add_to_queue(
            document_id="doc-review",
            matter_id="matter-review",
            words=words,
        )

        assert count == 2

        # Verify insert was called with correct data
        insert_call = mock_supabase_client.table.return_value.insert.call_args[0][0]
        assert len(insert_call) == 2
        assert insert_call[0]["document_id"] == "doc-review"
        assert insert_call[0]["matter_id"] == "matter-review"
        assert insert_call[0]["original_text"] == "unreadable"
        assert insert_call[0]["status"] == HumanReviewStatus.PENDING.value


class TestValidationErrorHandling:
    """Tests for error handling in validation pipeline."""

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    def test_handles_extraction_failure_gracefully(
        self,
        mock_get_extractor: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that extraction failures don't crash the task."""
        mock_extractor = MagicMock(spec=ValidationExtractor)
        mock_extractor.extract_low_confidence_words.side_effect = Exception(
            "Database connection failed"
        )
        mock_get_extractor.return_value = mock_extractor

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-error",
            "matter_id": "matter-error",
        }

        result = validate_ocr.run(prev_result=prev_result)

        # Should return failure status but not crash
        assert result["status"] == "validation_failed"
        assert "error" in result

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_human_review_service")
    @patch("app.workers.tasks.document_tasks.get_gemini_validator")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    @patch("app.workers.tasks.document_tasks.apply_pattern_corrections")
    def test_handles_gemini_failure_gracefully(
        self,
        mock_apply_patterns: MagicMock,
        mock_get_extractor: MagicMock,
        mock_get_gemini: MagicMock,
        mock_get_human_review: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test that Gemini failures don't crash the task."""
        mock_extractor = MagicMock(spec=ValidationExtractor)
        mock_extractor.extract_low_confidence_words.return_value = (
            [
                LowConfidenceWord(
                    bbox_id="bbox-1",
                    text="test",
                    confidence=0.70,
                    page=1,
                    context_before="",
                    context_after="",
                    x=10.0,
                    y=20.0,
                    width=8.0,
                    height=5.0,
                ),
            ],
            [],
        )
        mock_get_extractor.return_value = mock_extractor

        # Pattern correction returns no corrections
        mock_apply_patterns.return_value = (
            [],
            [
                LowConfidenceWord(
                    bbox_id="bbox-1",
                    text="test",
                    confidence=0.70,
                    page=1,
                    context_before="",
                    context_after="",
                    x=10.0,
                    y=20.0,
                    width=8.0,
                    height=5.0,
                ),
            ],
        )

        mock_gemini = MagicMock(spec=GeminiOCRValidator)
        mock_gemini.validate_batch_sync.side_effect = Exception("Gemini API error")
        mock_get_gemini.return_value = mock_gemini

        mock_human_review = MagicMock(spec=HumanReviewService)
        mock_get_human_review.return_value = mock_human_review

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value.data = []
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        prev_result = {
            "status": "ocr_complete",
            "document_id": "doc-gemini-error",
            "matter_id": "matter-gemini-error",
        }

        # Should not raise, should handle gracefully
        result = validate_ocr.run(prev_result=prev_result)

        # Either continues without Gemini corrections or marks as failed
        assert result["status"] in ["validation_complete", "validation_failed"]

    @patch("app.workers.tasks.document_tasks.get_service_client")
    @patch("app.workers.tasks.document_tasks.get_validation_extractor")
    def test_handles_missing_prev_result_fields(
        self,
        mock_get_extractor: MagicMock,
        mock_get_client: MagicMock,
    ) -> None:
        """Test handling when prev_result is missing required fields."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Missing document_id and matter_id
        prev_result = {"status": "ocr_complete"}

        result = validate_ocr.run(prev_result=prev_result)

        # Should fail gracefully
        assert result["status"] == "validation_failed"
