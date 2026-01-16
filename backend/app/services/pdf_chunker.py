"""PDF Chunker Service for splitting large PDFs.

Story 16.2: Implement PDFChunker Service

Library Selection Rationale:
- pypdf chosen over pikepdf (C library, harder to deploy) and pymupdf (GPL license)
- pypdf is pure Python, well-maintained, good memory efficiency for page extraction
- Supports lazy page loading - only extracted pages are fully loaded into memory
"""

import threading
from functools import lru_cache
from io import BytesIO

import pypdf
import structlog

logger = structlog.get_logger(__name__)

# Configuration
DEFAULT_CHUNK_SIZE = 25  # Pages per chunk (Document AI limit is 30)
CHUNK_THRESHOLD = 30  # Documents > 30 pages use chunking
SPLIT_TIMEOUT_SECONDS = 30  # Max time for split operation


class PDFChunkerError(Exception):
    """Base exception for PDF chunker operations."""

    def __init__(self, message: str, code: str = "PDF_CHUNKER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class PDFChunker:
    """Service for splitting large PDFs into processable chunks.

    Each chunk stays within Document AI's 30-page limit while
    maintaining valid PDF structure for OCR processing.

    Page Number Convention:
    - Return tuples use 1-based page numbers (user-facing)
    - pypdf internally uses 0-based indices
    - page_start=1, page_end=25 -> pypdf indices 0-24

    Example:
        >>> chunker = PDFChunker()
        >>> chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)
        >>> # For 75-page PDF:
        >>> # [(chunk1_bytes, 1, 25), (chunk2_bytes, 26, 50), (chunk3_bytes, 51, 75)]
    """

    def should_chunk(self, page_count: int) -> bool:
        """Determine if PDF should be split into chunks.

        Args:
            page_count: Total pages in PDF.

        Returns:
            True if page_count > 30, False otherwise.
        """
        return page_count > CHUNK_THRESHOLD

    def split_pdf(
        self,
        pdf_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> list[tuple[bytes, int, int]]:
        """Split PDF into chunks of specified size.

        Each chunk is a valid PDF file containing chunk_size pages
        (or fewer for the last chunk).

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Maximum pages per chunk (default 25).

        Returns:
            List of tuples: (chunk_bytes, page_start, page_end)
            where page numbers are 1-based.

        Raises:
            PDFChunkerError: If splitting fails.

        Example:
            >>> chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)
            >>> for chunk_bytes, page_start, page_end in chunks:
            ...     print(f"Pages {page_start}-{page_end}: {len(chunk_bytes)} bytes")
        """
        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            total_pages = len(reader.pages)

            if total_pages == 0:
                raise PDFChunkerError("PDF has no pages", code="EMPTY_PDF")

            chunks = []
            page_start = 1  # 1-based page numbering

            while page_start <= total_pages:
                page_end = min(page_start + chunk_size - 1, total_pages)

                chunk_bytes = self._extract_page_range(
                    reader,
                    page_start - 1,  # Convert to 0-based for pypdf
                    page_end - 1,
                )

                chunks.append((chunk_bytes, page_start, page_end))

                logger.debug(
                    "chunk_extracted",
                    page_start=page_start,
                    page_end=page_end,
                    chunk_size_bytes=len(chunk_bytes),
                )

                page_start = page_end + 1

            logger.info(
                "pdf_split_complete",
                total_pages=total_pages,
                chunk_count=len(chunks),
                chunk_size=chunk_size,
            )

            return chunks

        except pypdf.errors.PdfReadError as e:
            logger.error("pdf_parse_failed", error=str(e))
            raise PDFChunkerError(f"Failed to parse PDF: {e}", code="PDF_PARSE_ERROR") from e
        except PDFChunkerError:
            raise
        except Exception as e:
            logger.error("pdf_split_failed", error=str(e))
            raise PDFChunkerError(f"Failed to split PDF: {e}") from e

    def _extract_page_range(
        self,
        reader: pypdf.PdfReader,
        start_index: int,
        end_index: int,
    ) -> bytes:
        """Extract a range of pages as a new PDF.

        Uses pypdf's lazy loading - only the pages being extracted
        are fully loaded into memory.

        Args:
            reader: Source PDF reader.
            start_index: Start page index (0-based).
            end_index: End page index (0-based, inclusive).

        Returns:
            PDF bytes containing only the specified pages.
        """
        writer = pypdf.PdfWriter()

        for page_index in range(start_index, end_index + 1):
            writer.add_page(reader.pages[page_index])

        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def split_pdf_with_timeout(
        self,
        pdf_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        timeout_seconds: int = SPLIT_TIMEOUT_SECONDS,
    ) -> list[tuple[bytes, int, int]]:
        """Split PDF with timeout protection.

        Uses threading-based timeout for cross-platform compatibility
        (works on both Windows and Unix).

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Maximum pages per chunk.
            timeout_seconds: Max time allowed for operation.

        Returns:
            List of chunk tuples.

        Raises:
            PDFChunkerError: If operation times out or fails.
        """
        result: list[tuple[bytes, int, int]] = []
        error: Exception | None = None

        def split_worker():
            nonlocal result, error
            try:
                result = self.split_pdf(pdf_bytes, chunk_size)
            except Exception as e:
                error = e

        thread = threading.Thread(target=split_worker)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            # Thread is still running - timeout occurred
            logger.error(
                "pdf_split_timeout",
                timeout_seconds=timeout_seconds,
            )
            raise PDFChunkerError(
                f"PDF split timed out after {timeout_seconds}s",
                code="SPLIT_TIMEOUT",
            )

        if error is not None:
            raise error

        return result


@lru_cache(maxsize=1)
def get_pdf_chunker() -> PDFChunker:
    """Get singleton PDFChunker instance.

    Returns:
        PDFChunker instance.
    """
    return PDFChunker()
