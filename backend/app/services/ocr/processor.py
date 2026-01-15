"""Google Document AI OCR processor service.

Provides document OCR processing using Google Document AI with support
for Indian languages (Hindi, Gujarati, English).
"""

import time
from functools import lru_cache

import structlog
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import documentai_v1 as documentai

from app.core.config import get_settings
from app.models.ocr import OCRPage, OCRResult
from app.services.ocr.bbox_extractor import extract_bounding_boxes

logger = structlog.get_logger(__name__)


class OCRServiceError(Exception):
    """Base exception for OCR service operations."""

    def __init__(
        self,
        message: str,
        code: str = "OCR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class OCRConfigurationError(OCRServiceError):
    """Raised when OCR service is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="OCR_NOT_CONFIGURED", is_retryable=False)


class OCRProcessingError(OCRServiceError):
    """Raised when OCR processing fails."""

    def __init__(self, message: str, is_retryable: bool = True):
        super().__init__(message, code="OCR_PROCESSING_FAILED", is_retryable=is_retryable)


class OCRProcessor:
    """Service for processing documents with Google Document AI.

    Uses Document AI's Enterprise Document OCR for high-quality
    text extraction with bounding box coordinates and confidence scores.
    """

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        processor_id: str | None = None,
    ):
        """Initialize OCR processor.

        Args:
            project_id: Google Cloud project ID.
            location: Processor location (us, eu).
            processor_id: Document AI processor ID.
        """
        settings = get_settings()

        self.project_id = project_id or settings.google_cloud_project_id
        self.location = location or settings.google_cloud_location
        self.processor_id = processor_id or settings.google_document_ai_processor_id

        # Lazy initialize client
        self._client: documentai.DocumentProcessorServiceClient | None = None

    @property
    def client(self) -> documentai.DocumentProcessorServiceClient:
        """Get or create Document AI client.

        Returns:
            Document AI client instance.

        Raises:
            OCRConfigurationError: If credentials are not configured.
        """
        if self._client is None:
            try:
                self._client = documentai.DocumentProcessorServiceClient()
            except Exception as e:
                logger.error("documentai_client_init_failed", error=str(e))
                raise OCRConfigurationError(
                    f"Failed to initialize Document AI client: {e}"
                ) from e
        return self._client

    @property
    def processor_name(self) -> str:
        """Get the full processor resource name.

        Returns:
            Processor resource name string.

        Raises:
            OCRConfigurationError: If configuration is incomplete.
        """
        if not self.project_id or not self.processor_id:
            raise OCRConfigurationError(
                "Google Document AI is not configured. Set GOOGLE_CLOUD_PROJECT_ID "
                "and GOOGLE_DOCUMENT_AI_PROCESSOR_ID environment variables."
            )

        return (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"processors/{self.processor_id}"
        )

    def process_document(
        self,
        pdf_content: bytes,
        document_id: str | None = None,
        enable_image_quality_scores: bool = True,
    ) -> OCRResult:
        """Process a PDF document and extract text with bounding boxes.

        Note: This method is SYNCHRONOUS and makes a blocking API call to
        Google Document AI. It is designed to be called from Celery tasks
        (which run in separate worker processes). Do NOT call this directly
        from async FastAPI endpoints - use Celery task queuing instead.

        Args:
            pdf_content: PDF file content as bytes.
            document_id: Optional document ID for logging and result.
            enable_image_quality_scores: Whether to compute image quality scores.

        Returns:
            OCRResult with extracted text, pages, and bounding boxes.

        Raises:
            OCRServiceError: If processing fails.
        """
        start_time = time.time()

        logger.info(
            "ocr_processing_started",
            document_id=document_id,
            content_size=len(pdf_content),
        )

        try:
            # Build process request
            request = documentai.ProcessRequest(
                name=self.processor_name,
                raw_document=documentai.RawDocument(
                    content=pdf_content,
                    mime_type="application/pdf",
                ),
                process_options=documentai.ProcessOptions(
                    ocr_config=documentai.OcrConfig(
                        enable_image_quality_scores=enable_image_quality_scores,
                        # Language hints for Indian languages
                        # Document AI auto-detects, but hints improve accuracy
                        hints=documentai.OcrConfig.Hints(
                            language_hints=["en", "hi", "gu"]
                        ),
                    ),
                ),
            )

            # Process document
            response = self.client.process_document(request=request)
            document = response.document

            # Extract results
            pages = self._extract_pages(document)
            bounding_boxes = extract_bounding_boxes(document)

            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(pages)

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            result = OCRResult(
                document_id=document_id or "",
                pages=pages,
                bounding_boxes=bounding_boxes,
                full_text=document.text or "",
                overall_confidence=overall_confidence,
                processing_time_ms=processing_time_ms,
                page_count=len(pages),
            )

            logger.info(
                "ocr_processing_completed",
                document_id=document_id,
                page_count=len(pages),
                bbox_count=len(bounding_boxes),
                overall_confidence=overall_confidence,
                processing_time_ms=processing_time_ms,
            )

            return result

        except OCRConfigurationError:
            raise
        except GoogleAPICallError as e:
            logger.error(
                "documentai_api_error",
                document_id=document_id,
                error=str(e),
                error_code=getattr(e, "code", None),
            )
            # Most Google API errors are retryable (quota, transient failures)
            raise OCRProcessingError(
                f"Document AI API error: {e}",
                is_retryable=True,
            ) from e
        except Exception as e:
            logger.error(
                "ocr_processing_failed",
                document_id=document_id,
                error=str(e),
            )
            raise OCRProcessingError(
                f"OCR processing failed: {e}",
                is_retryable=False,
            ) from e

    def _extract_pages(
        self,
        document: documentai.Document,
    ) -> list[OCRPage]:
        """Extract page-level OCR results.

        Args:
            document: Document AI response document.

        Returns:
            List of OCRPage results.
        """
        pages: list[OCRPage] = []
        full_text = document.text or ""

        for page in document.pages:
            # Extract page text from text anchor
            page_text = self._extract_page_text(page, full_text)

            # Calculate average confidence for the page
            page_confidence = self._calculate_page_confidence(page)

            # Get image quality score if available
            image_quality_score = None
            if hasattr(page, "image_quality_scores") and page.image_quality_scores:
                quality_scores = page.image_quality_scores
                if hasattr(quality_scores, "quality_score"):
                    image_quality_score = quality_scores.quality_score

            pages.append(
                OCRPage(
                    page_number=page.page_number,
                    text=page_text,
                    confidence=page_confidence,
                    image_quality_score=image_quality_score,
                )
            )

        return pages

    def _extract_page_text(
        self,
        page: documentai.Document.Page,
        full_text: str,
    ) -> str:
        """Extract text content for a specific page.

        Args:
            page: Document page object.
            full_text: Full document text.

        Returns:
            Page text content.
        """
        if not page.layout or not page.layout.text_anchor:
            return ""

        text_anchor = page.layout.text_anchor
        if not text_anchor.text_segments:
            return ""

        text_parts: list[str] = []
        for segment in text_anchor.text_segments:
            start_idx = int(segment.start_index) if segment.start_index else 0
            end_idx = int(segment.end_index) if segment.end_index else len(full_text)
            text_parts.append(full_text[start_idx:end_idx])

        return "".join(text_parts)

    def _calculate_page_confidence(
        self,
        page: documentai.Document.Page,
    ) -> float | None:
        """Calculate average confidence for a page.

        Args:
            page: Document page object.

        Returns:
            Average confidence (0-1) or None if not available.
        """
        confidences: list[float] = []

        # Collect confidence from tokens
        for token in page.tokens:
            if hasattr(token.layout, "confidence") and token.layout.confidence:
                confidences.append(token.layout.confidence)

        if not confidences:
            return None

        return sum(confidences) / len(confidences)

    def _calculate_overall_confidence(
        self,
        pages: list[OCRPage],
    ) -> float | None:
        """Calculate overall document confidence.

        Args:
            pages: List of OCRPage results.

        Returns:
            Average confidence across all pages.
        """
        confidences = [p.confidence for p in pages if p.confidence is not None]
        if not confidences:
            return None
        return sum(confidences) / len(confidences)


@lru_cache(maxsize=1)
def get_ocr_processor() -> OCRProcessor:
    """Get singleton OCR processor instance.

    Returns:
        OCRProcessor instance.
    """
    return OCRProcessor()
