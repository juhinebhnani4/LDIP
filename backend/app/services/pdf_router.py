"""PDF Router service for page count detection and routing decisions.

Story 16.1: Implement PDF Page Count Detection and Routing

Determines whether a PDF should use sync processing (<=15 pages)
or chunked parallel processing (>15 pages).
"""

from functools import lru_cache
from io import BytesIO

import pypdf
import structlog

from app.models.ocr_chunk import ChunkSpec

logger = structlog.get_logger(__name__)

# Routing thresholds
PAGE_COUNT_THRESHOLD = 15  # Documents > 15 pages use chunked processing (Document AI limit)
MAX_PAGE_COUNT = 10000  # Security limit
CHUNK_SIZE = 15  # Pages per chunk (Document AI limit: 15 for non-imageless, 30 for imageless)


class PDFRouterError(Exception):
    """Base exception for PDF routing errors."""

    def __init__(self, message: str, code: str = "PDF_ROUTER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class MaliciousPDFError(PDFRouterError):
    """Raised when PDF appears malicious or malformed."""

    def __init__(self, message: str):
        super().__init__(message, code="MALICIOUS_PDF_DETECTED")


class PDFRouter:
    """Service for PDF page count detection and routing decisions.

    Determines whether a PDF should use sync processing (<=15 pages)
    or chunked parallel processing (>15 pages).

    Example:
        >>> router = PDFRouter()
        >>> count = router.get_page_count(pdf_bytes)
        >>> if router.should_use_chunked_processing(count):
        ...     specs = router.calculate_chunk_specs(count)
    """

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get PDF page count without loading full content.

        Uses pypdf for lightweight page counting. Validates PDF
        before parsing to prevent malicious file attacks.

        Args:
            pdf_bytes: PDF file content.

        Returns:
            Number of pages in the PDF.

        Raises:
            PDFRouterError: If PDF cannot be parsed.
            MaliciousPDFError: If PDF appears malicious.
        """
        self._validate_pdf_magic_bytes(pdf_bytes)

        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            claimed_count = len(reader.pages)

            # Validate count is reasonable
            if claimed_count > MAX_PAGE_COUNT:
                logger.warning(
                    "pdf_page_count_exceeded_max",
                    claimed_count=claimed_count,
                    max_allowed=MAX_PAGE_COUNT,
                )
                raise MaliciousPDFError(
                    f"PDF claims {claimed_count} pages, exceeds max {MAX_PAGE_COUNT}"
                )

            # Validate by actually verifying pages exist (defense against header spoofing)
            actual_count = self._count_actual_pages(reader, claimed_count)

            if actual_count != claimed_count:
                logger.warning(
                    "pdf_page_count_mismatch",
                    claimed=claimed_count,
                    actual=actual_count,
                )

            logger.debug(
                "pdf_page_count_detected",
                page_count=actual_count,
            )

            return actual_count

        except pypdf.errors.PdfReadError as e:
            logger.error("pdf_parse_failed", error=str(e))
            raise PDFRouterError(f"Failed to parse PDF: {e}") from e
        except MaliciousPDFError:
            raise
        except Exception as e:
            logger.error("pdf_read_unexpected_error", error=str(e))
            raise PDFRouterError(f"Unexpected error reading PDF: {e}") from e

    def _validate_pdf_magic_bytes(self, pdf_bytes: bytes) -> None:
        """Validate PDF starts with correct magic bytes.

        Args:
            pdf_bytes: PDF file content.

        Raises:
            PDFRouterError: If file doesn't start with PDF magic bytes.
        """
        if not pdf_bytes:
            raise PDFRouterError(
                "Empty file provided",
                code="EMPTY_FILE",
            )

        if not pdf_bytes.startswith(b"%PDF-"):
            logger.warning(
                "pdf_magic_bytes_invalid",
                first_bytes=pdf_bytes[:20].hex() if pdf_bytes else "empty",
            )
            raise PDFRouterError(
                "File does not appear to be a valid PDF",
                code="INVALID_PDF_FORMAT",
            )

    def _count_actual_pages(
        self,
        reader: pypdf.PdfReader,
        claimed_count: int,
    ) -> int:
        """Count actual pages by verification (limited for performance).

        For performance, only fully validates if claimed count is suspicious.
        Uses spot checking for reasonable claims.

        Args:
            reader: PyPDF reader instance.
            claimed_count: Number of pages claimed by PDF header.

        Returns:
            Verified page count.
        """
        # For reasonable claims, do spot checks
        if claimed_count <= MAX_PAGE_COUNT:
            try:
                # Verify first page exists
                _ = reader.pages[0]

                # Verify last page exists (if multiple pages)
                if claimed_count > 1:
                    _ = reader.pages[claimed_count - 1]

                return claimed_count

            except IndexError:
                # Page doesn't exist - do full enumeration
                logger.warning(
                    "pdf_spot_check_failed",
                    claimed_count=claimed_count,
                )

        # Full enumeration for suspicious cases
        actual = 0
        for _ in reader.pages:
            actual += 1
            if actual > MAX_PAGE_COUNT:
                raise MaliciousPDFError(
                    f"PDF exceeds maximum allowed pages ({MAX_PAGE_COUNT})"
                )
        return actual

    def should_use_chunked_processing(self, page_count: int) -> bool:
        """Determine if PDF should use chunked processing.

        Args:
            page_count: Number of pages in PDF.

        Returns:
            True if PDF should be chunked (>15 pages), False for sync processing.
        """
        return page_count > PAGE_COUNT_THRESHOLD

    def calculate_chunk_specs(
        self,
        total_pages: int,
        chunk_size: int = CHUNK_SIZE,
    ) -> list[ChunkSpec]:
        """Calculate chunk boundaries for a document.

        Divides the document into chunks of `chunk_size` pages each,
        with the last chunk containing any remainder.

        Args:
            total_pages: Total pages in document.
            chunk_size: Pages per chunk (default 25).

        Returns:
            List of ChunkSpec models for batch creation.
        """
        chunks = []
        chunk_index = 0
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            chunks.append(
                ChunkSpec(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                )
            )
            chunk_index += 1
            page_start = page_end + 1

        logger.debug(
            "chunk_specs_calculated",
            total_pages=total_pages,
            chunk_size=chunk_size,
            chunk_count=len(chunks),
        )

        return chunks


@lru_cache(maxsize=1)
def get_pdf_router() -> PDFRouter:
    """Get singleton PDFRouter instance.

    Returns:
        PDFRouter instance.
    """
    return PDFRouter()
