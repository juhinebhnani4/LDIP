"""PDF Chunker Service for splitting large PDFs.

Story 16.2: Implement PDFChunker Service
Story 17.1: Memory-Safe Streaming PDF Split

Library Selection Rationale:
- pypdf chosen over pikepdf (C library, harder to deploy) and pymupdf (GPL license)
- pypdf is pure Python, well-maintained, good memory efficiency for page extraction
- Supports lazy page loading - only extracted pages are fully loaded into memory

Memory Safety (Story 17.1):
- Streaming split writes chunks to temporary files as they're created
- Only current page + output buffer in memory at any time
- Atomic write pattern (.tmp then rename) prevents corruption
- Memory profiling warns at 75% of limit
"""

import os
import shutil
import tempfile
import threading
import tracemalloc
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pypdf
import structlog

logger = structlog.get_logger(__name__)

# Configuration
DEFAULT_CHUNK_SIZE = 15  # Pages per chunk (Document AI limit: 15 non-imageless, 30 imageless)
CHUNK_THRESHOLD = 30  # Documents > 30 pages use chunking
SPLIT_TIMEOUT_SECONDS = 30  # Max time for split operation

# Memory safety configuration (Story 17.1)
MEMORY_LIMIT_MB = 50  # Max memory usage during split
MEMORY_WARNING_THRESHOLD = 0.75  # Warn at 75% of limit
STREAMING_THRESHOLD_MB = 100  # Use streaming for PDFs > 100MB


class PDFChunkerError(Exception):
    """Base exception for PDF chunker operations."""

    def __init__(self, message: str, code: str = "PDF_CHUNKER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class MemoryLimitExceededError(PDFChunkerError):
    """Raised when memory usage exceeds the limit."""

    def __init__(self, current_mb: float, limit_mb: float):
        super().__init__(
            f"Memory usage ({current_mb:.1f}MB) exceeded limit ({limit_mb}MB)",
            code="MEMORY_LIMIT_EXCEEDED",
        )
        self.current_mb = current_mb
        self.limit_mb = limit_mb


class StreamingChunkResult:
    """Result container for streaming split that uses temp files.

    Provides context manager for automatic cleanup of temporary files.

    Example:
        >>> with chunker.split_pdf_streaming(pdf_bytes) as result:
        ...     for chunk_path, page_start, page_end in result.chunks:
        ...         chunk_bytes = chunk_path.read_bytes()
        ...         process(chunk_bytes)
        >>> # Temp files automatically cleaned up
    """

    def __init__(self, temp_dir: Path, chunks: list[tuple[Path, int, int]]):
        """Initialize streaming result.

        Args:
            temp_dir: Temporary directory containing chunk files.
            chunks: List of (chunk_path, page_start, page_end) tuples.
        """
        self.temp_dir = temp_dir
        self.chunks = chunks

    def __enter__(self) -> "StreamingChunkResult":
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and cleanup temp files."""
        self.cleanup()

    def cleanup(self) -> None:
        """Remove temporary directory and all chunk files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.debug(
                "streaming_chunks_cleaned_up",
                temp_dir=str(self.temp_dir),
                chunk_count=len(self.chunks),
            )

    def get_chunk_bytes(self, index: int) -> bytes:
        """Read chunk bytes from file.

        Args:
            index: Chunk index (0-based).

        Returns:
            Chunk PDF content as bytes.

        Raises:
            IndexError: If index out of range.
        """
        if index < 0 or index >= len(self.chunks):
            raise IndexError(f"Chunk index {index} out of range (0-{len(self.chunks) - 1})")
        return self.chunks[index][0].read_bytes()

    def iter_chunk_bytes(self):
        """Iterate over chunks, yielding bytes for each.

        Yields:
            Tuple of (chunk_bytes, page_start, page_end).
        """
        for chunk_path, page_start, page_end in self.chunks:
            yield chunk_path.read_bytes(), page_start, page_end


class PDFChunker:
    """Service for splitting large PDFs into processable chunks.

    Each chunk stays within Document AI's 30-page limit while
    maintaining valid PDF structure for OCR processing.

    Page Number Convention:
    - Return tuples use 1-based page numbers (user-facing)
    - pypdf internally uses 0-based indices
    - page_start=1, page_end=25 -> pypdf indices 0-24

    Memory Safety (Story 17.1):
    - For PDFs > 100MB, use split_pdf_streaming() to write chunks to temp files
    - Memory is tracked using tracemalloc with warnings at 75% of 50MB limit
    - Atomic write pattern prevents corruption on crash

    Example:
        >>> chunker = PDFChunker()
        >>> chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)
        >>> # For 75-page PDF:
        >>> # [(chunk1_bytes, 1, 25), (chunk2_bytes, 26, 50), (chunk3_bytes, 51, 75)]

        >>> # For very large PDFs, use streaming:
        >>> with chunker.split_pdf_streaming(large_pdf_bytes) as result:
        ...     for chunk_bytes, start, end in result.iter_chunk_bytes():
        ...         process(chunk_bytes)
    """

    def __init__(self, enable_memory_tracking: bool = True):
        """Initialize PDF chunker.

        Args:
            enable_memory_tracking: Whether to track memory usage (default True).
        """
        self._enable_memory_tracking = enable_memory_tracking

    def should_chunk(self, page_count: int) -> bool:
        """Determine if PDF should be split into chunks.

        Args:
            page_count: Total pages in PDF.

        Returns:
            True if page_count > 30, False otherwise.
        """
        return page_count > CHUNK_THRESHOLD

    def should_use_streaming(self, pdf_size_bytes: int) -> bool:
        """Determine if streaming split should be used.

        Args:
            pdf_size_bytes: Size of PDF in bytes.

        Returns:
            True if PDF > 100MB and streaming is recommended.
        """
        return pdf_size_bytes > STREAMING_THRESHOLD_MB * 1024 * 1024

    def split_pdf(
        self,
        pdf_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> list[tuple[bytes, int, int]]:
        """Split PDF into chunks of specified size.

        Each chunk is a valid PDF file containing chunk_size pages
        (or fewer for the last chunk).

        For large PDFs (>100MB), consider using split_pdf_streaming()
        to reduce memory usage.

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Maximum pages per chunk (default 25).

        Returns:
            List of tuples: (chunk_bytes, page_start, page_end)
            where page numbers are 1-based.

        Raises:
            PDFChunkerError: If splitting fails.
            MemoryLimitExceededError: If memory usage exceeds 50MB.

        Example:
            >>> chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)
            >>> for chunk_bytes, page_start, page_end in chunks:
            ...     print(f"Pages {page_start}-{page_end}: {len(chunk_bytes)} bytes")
        """
        # Start memory tracking
        if self._enable_memory_tracking:
            tracemalloc.start()

        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            total_pages = len(reader.pages)

            if total_pages == 0:
                raise PDFChunkerError("PDF has no pages", code="EMPTY_PDF")

            chunks = []
            page_start = 1  # 1-based page numbering

            while page_start <= total_pages:
                page_end = min(page_start + chunk_size - 1, total_pages)

                # Check memory before extracting
                if self._enable_memory_tracking:
                    self._check_memory_usage()

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
        except (PDFChunkerError, MemoryLimitExceededError):
            raise
        except Exception as e:
            logger.error("pdf_split_failed", error=str(e))
            raise PDFChunkerError(f"Failed to split PDF: {e}") from e
        finally:
            if self._enable_memory_tracking:
                tracemalloc.stop()

    def split_pdf_streaming(
        self,
        pdf_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> StreamingChunkResult:
        """Split PDF into chunks using streaming with temp files.

        Memory-safe alternative to split_pdf() for very large PDFs.
        Writes each chunk to a temporary file immediately after extraction,
        keeping memory usage bounded regardless of PDF size.

        Story 17.1: Memory-Safe Streaming PDF Split

        Uses atomic write pattern: writes to .tmp file, then renames to final.
        This prevents corruption if the process crashes mid-write.

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Maximum pages per chunk (default 25).

        Returns:
            StreamingChunkResult with paths to chunk files.
            Use as context manager for automatic cleanup.

        Raises:
            PDFChunkerError: If splitting fails.

        Example:
            >>> with chunker.split_pdf_streaming(large_pdf) as result:
            ...     for chunk_bytes, start, end in result.iter_chunk_bytes():
            ...         await ocr.process(chunk_bytes)
        """
        # Create temporary directory for chunks
        temp_dir = Path(tempfile.mkdtemp(prefix="pdf_chunks_"))
        chunks: list[tuple[Path, int, int]] = []

        # Start memory tracking
        if self._enable_memory_tracking:
            tracemalloc.start()

        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            total_pages = len(reader.pages)

            if total_pages == 0:
                raise PDFChunkerError("PDF has no pages", code="EMPTY_PDF")

            page_start = 1  # 1-based page numbering
            chunk_index = 0

            while page_start <= total_pages:
                page_end = min(page_start + chunk_size - 1, total_pages)

                # Check memory before extracting
                if self._enable_memory_tracking:
                    self._check_memory_usage()

                # Extract chunk to temporary file with atomic write
                chunk_path = self._extract_page_range_to_file(
                    reader=reader,
                    start_index=page_start - 1,
                    end_index=page_end - 1,
                    output_dir=temp_dir,
                    chunk_index=chunk_index,
                )

                chunks.append((chunk_path, page_start, page_end))

                logger.debug(
                    "streaming_chunk_extracted",
                    page_start=page_start,
                    page_end=page_end,
                    chunk_path=str(chunk_path),
                    chunk_size_bytes=chunk_path.stat().st_size,
                )

                page_start = page_end + 1
                chunk_index += 1

                # Note: pypdf's lazy loading handles memory automatically.
                # Explicit deletion of pages from reader is not recommended
                # as it can cause issues with page indexing. Memory is released
                # when the reader goes out of scope or when chunks are written to disk.

            logger.info(
                "pdf_streaming_split_complete",
                total_pages=total_pages,
                chunk_count=len(chunks),
                chunk_size=chunk_size,
                temp_dir=str(temp_dir),
            )

            return StreamingChunkResult(temp_dir, chunks)

        except (PDFChunkerError, MemoryLimitExceededError):
            # Cleanup on error
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        except pypdf.errors.PdfReadError as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error("pdf_parse_failed", error=str(e))
            raise PDFChunkerError(f"Failed to parse PDF: {e}", code="PDF_PARSE_ERROR") from e
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error("pdf_streaming_split_failed", error=str(e))
            raise PDFChunkerError(f"Failed to split PDF: {e}") from e
        finally:
            if self._enable_memory_tracking:
                tracemalloc.stop()

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

    def _extract_page_range_to_file(
        self,
        reader: pypdf.PdfReader,
        start_index: int,
        end_index: int,
        output_dir: Path,
        chunk_index: int,
    ) -> Path:
        """Extract pages to a file using atomic write pattern.

        Writes to a .tmp file first, then renames to final path.
        This prevents corruption if the process crashes mid-write.

        Story 17.1: Atomic Temp Files - CHAOS MONKEY requirement.

        Args:
            reader: Source PDF reader.
            start_index: Start page index (0-based).
            end_index: End page index (0-based, inclusive).
            output_dir: Directory to write chunk file.
            chunk_index: Chunk index for filename.

        Returns:
            Path to the created chunk file.
        """
        final_path = output_dir / f"chunk_{chunk_index}.pdf"
        tmp_path = output_dir / f"chunk_{chunk_index}.pdf.tmp"

        writer = pypdf.PdfWriter()

        for page_index in range(start_index, end_index + 1):
            writer.add_page(reader.pages[page_index])

        try:
            # Write to temp file first
            with open(tmp_path, "wb") as f:
                writer.write(f)

            # Atomic rename (on same filesystem)
            os.replace(tmp_path, final_path)

            return final_path

        except Exception:
            # Cleanup .tmp file on failure
            tmp_path.unlink(missing_ok=True)
            raise

    def _check_memory_usage(self) -> None:
        """Check current memory usage and warn/raise if too high.

        Story 17.1: Memory Profiling - PRE-MORTEM requirement.

        Raises:
            MemoryLimitExceededError: If memory exceeds MEMORY_LIMIT_MB.
        """
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / (1024 * 1024)
        peak_mb = peak / (1024 * 1024)

        # Warn at 75% of limit
        warning_threshold_mb = MEMORY_LIMIT_MB * MEMORY_WARNING_THRESHOLD
        if current_mb > warning_threshold_mb:
            logger.warning(
                "pdf_split_memory_warning",
                current_mb=round(current_mb, 2),
                peak_mb=round(peak_mb, 2),
                limit_mb=MEMORY_LIMIT_MB,
                threshold_pct=int(MEMORY_WARNING_THRESHOLD * 100),
            )

        # Error if exceeds limit
        if current_mb > MEMORY_LIMIT_MB:
            logger.error(
                "pdf_split_memory_exceeded",
                current_mb=round(current_mb, 2),
                limit_mb=MEMORY_LIMIT_MB,
            )
            raise MemoryLimitExceededError(current_mb, MEMORY_LIMIT_MB)

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
