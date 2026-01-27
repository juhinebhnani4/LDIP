"""Google Document AI OCR processor service.

Provides document OCR processing using Google Document AI with support
for Indian languages (Hindi, Gujarati, English).

Story 17.2: Circuit Breaker for Document AI
- Wraps Document AI API calls with circuit breaker protection
- Fast-fails when Document AI is unhealthy
- Prevents cascade failures in chunked processing
"""

import json
import os
import tempfile
import time
from functools import lru_cache

from io import BytesIO

import pypdf
import structlog
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_sync_circuit_breaker,
)
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


class OCRCircuitOpenError(OCRServiceError):
    """Raised when the Document AI circuit breaker is open.

    Story 17.2: Circuit Breaker for Document AI
    """

    def __init__(self, cooldown_remaining: float):
        super().__init__(
            f"Document AI circuit is open. Retry after {cooldown_remaining:.1f}s",
            code="OCR_CIRCUIT_OPEN",
            is_retryable=True,
        )
        self.cooldown_remaining = cooldown_remaining


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

        Supports two authentication methods:
        1. GOOGLE_APPLICATION_CREDENTIALS env var (file path) - for local dev
        2. GOOGLE_APPLICATION_CREDENTIALS_JSON env var (JSON content) - for production/Railway

        Returns:
            Document AI client instance.

        Raises:
            OCRConfigurationError: If credentials are not configured.
        """
        if self._client is None:
            try:
                settings = get_settings()
                credentials_json = settings.google_application_credentials_json

                if credentials_json:
                    # Production: Use JSON content directly
                    logger.info("documentai_using_json_credentials")
                    credentials_dict = json.loads(credentials_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_dict
                    )
                    self._client = documentai.DocumentProcessorServiceClient(
                        credentials=credentials
                    )
                else:
                    # Local dev: Use GOOGLE_APPLICATION_CREDENTIALS file path
                    logger.info("documentai_using_file_credentials")
                    self._client = documentai.DocumentProcessorServiceClient()
            except json.JSONDecodeError as e:
                logger.error("documentai_json_parse_failed", error=str(e))
                raise OCRConfigurationError(
                    f"Failed to parse GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}"
                ) from e
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

    def _split_pdf(self, pdf_content: bytes, chunk_size: int = 15) -> list[bytes]:
        """Split a large PDF into smaller chunks.
        
        Args:
            pdf_content: Original PDF bytes.
            chunk_size: Maximum pages per chunk.
            
        Returns:
            List of PDF bytes for each chunk.
        """
        reader = pypdf.PdfReader(BytesIO(pdf_content))
        total_pages = len(reader.pages)
        chunks = []
        
        for start in range(0, total_pages, chunk_size):
            writer = pypdf.PdfWriter()
            end = min(start + chunk_size, total_pages)
            for i in range(start, end):
                writer.add_page(reader.pages[i])
                
            out_stream = BytesIO()
            writer.write(out_stream)
            chunks.append(out_stream.getvalue())
            
        return chunks

    def _merge_ocr_results(self, results: list[OCRResult], chunk_size: int = 15) -> OCRResult:
        """Merge multiple OCR results into one.
        
        Args:
            results: List of OCRResult objects from chunks.
            chunk_size: Page count per chunk (to calculate offsets).
            
        Returns:
            Combined OCRResult.
        """
        if not results:
            raise OCRProcessingError("No results to merge")
            
        base = results[0]
        merged = OCRResult(
            document_id=base.document_id,
            pages=[],
            bounding_boxes=[],
            full_text="",
            overall_confidence=0.0,
            processing_time_ms=0,
            page_count=0
        )
        
        total_conf = 0.0
        conf_count = 0
        current_page_offset = 0
        
        for res in results:
            # 1. Merge pages with offset
            for page in res.pages:
                page.page_number += current_page_offset
                merged.pages.append(page)
                
            # 2. Merge bounding boxes with offset
            for bbox in res.bounding_boxes:
                bbox.page += current_page_offset
                merged.bounding_boxes.append(bbox)
                
            # 3. Concatenate text
            merged.full_text += res.full_text + "\n"
            
            # 4. Aggregate stats
            if res.overall_confidence:
                total_conf += res.overall_confidence * len(res.pages) # Weight by pages
                conf_count += len(res.pages)
                
            merged.processing_time_ms = (merged.processing_time_ms or 0) + (res.processing_time_ms or 0)
            merged.page_count += res.page_count
            
            # Update offset based on actual pages in this chunk (could be < chunk_size)
            current_page_offset += res.page_count

        if conf_count > 0:
            merged.overall_confidence = total_conf / conf_count
            
        return merged

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

        Story 17.2: Wrapped with circuit breaker for resilience.
        - Fast-fails when Document AI is unhealthy (circuit open)
        - Retries with exponential backoff on transient failures
        - Prevents cascade failures in parallel chunk processing

        Args:
            pdf_content: PDF file content as bytes.
            document_id: Optional document ID for logging and result.
            enable_image_quality_scores: Whether to compute image quality scores.

        Returns:
            OCRResult with extracted text, pages, and bounding boxes.

        Raises:
            OCRServiceError: If processing fails.
            OCRCircuitOpenError: If Document AI circuit breaker is open.
        """
        start_time = time.time()

        # Story 16.1: Handle large documents by splitting
        # Document AI Online Processing limit is 15 pages
        try:
            reader = pypdf.PdfReader(BytesIO(pdf_content))
            page_count = len(reader.pages)
            if page_count > 15:
                logger.info(
                    "splitting_large_document",
                    document_id=document_id,
                    page_count=page_count,
                    chunk_limit=15
                )
                chunks = self._split_pdf(pdf_content, 15)
                results = []
                for i, chunk in enumerate(chunks):
                    logger.info(
                        "processing_chunk",
                        document_id=document_id,
                        chunk_index=i,
                        total_chunks=len(chunks)
                    )
                    # Recursive call for each chunk
                    results.append(self.process_document(
                        chunk, 
                        document_id, 
                        enable_image_quality_scores
                    ))
                
                return self._merge_ocr_results(results)
        except Exception as e:
            # If splitting fails, log and attempt direct processing
            logger.warning(
                "pdf_split_failed",
                document_id=document_id,
                error=str(e)
            )

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

            # Process document with circuit breaker protection (Story 17.2)
            document = self._call_document_ai(request)

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
        except CircuitOpenError as e:
            # Convert to OCR-specific exception
            logger.warning(
                "ocr_circuit_open",
                document_id=document_id,
                cooldown_remaining=e.cooldown_remaining,
            )
            raise OCRCircuitOpenError(e.cooldown_remaining) from e
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

    @with_sync_circuit_breaker(CircuitService.DOCUMENTAI_OCR)
    def _call_document_ai(
        self,
        request: documentai.ProcessRequest,
    ) -> documentai.Document:
        """Call Document AI with circuit breaker protection.

        Story 17.2: Circuit Breaker for Document AI

        This internal method is wrapped with the sync circuit breaker
        to protect against Document AI failures:
        - Opens circuit after 3 consecutive failures
        - 120 second recovery timeout before attempting again
        - 2 retry attempts with exponential backoff

        Args:
            request: Document AI process request.

        Returns:
            Processed document from Document AI.

        Raises:
            GoogleAPICallError: If API call fails.
            CircuitOpenError: If circuit is open.
        """
        response = self.client.process_document(request=request)
        return response.document

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
