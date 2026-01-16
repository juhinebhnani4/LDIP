# Story 17.1: Implement Memory-Safe Streaming PDF Split

Status: ready-for-dev

## Story

As a system processing large PDFs,
I want to split PDFs using streaming/incremental page reading,
so that memory usage stays under 50MB regardless of PDF size.

## Acceptance Criteria

1. **Memory Efficiency**
   - 100MB PDF (500 pages): peak memory does not exceed 50MB
   - Chunks written to temporary storage as created
   - Only current page and output buffer in memory at any time

2. **Large Document Handling**
   - 1000+ page PDFs complete without OOM
   - Temporary chunk files used if needed
   - Previous pages released after writing to chunk

3. **Atomic Temp Files (CHAOS MONKEY)**
   - Atomic write pattern: write to .tmp, then rename
   - Incomplete files don't corrupt processing on crash
   - Cleanup removes .tmp files on failure

4. **Memory Profiling (PRE-MORTEM)**
   - Memory usage tracked per operation
   - Warning logged if approaching 75% of memory limit
   - Metrics emitted for monitoring consumption patterns

## Tasks / Subtasks

- [ ] Task 1: Implement streaming page extraction (AC: #1, #2)
  - [ ] Modify PDFChunker to use incremental page reading
  - [ ] Use pypdf's lazy page loading
  - [ ] Write chunks to temp storage during split
  - [ ] Release memory after each chunk written

- [ ] Task 2: Implement atomic file operations (AC: #3)
  - [ ] Create `AtomicFileWriter` utility class
  - [ ] Write to .tmp file first, rename on success
  - [ ] Clean up .tmp files on failure
  - [ ] Add context manager for safe usage

- [ ] Task 3: Add memory monitoring (AC: #4)
  - [ ] Add memory tracking via `tracemalloc` or `psutil`
  - [ ] Log memory usage at chunk boundaries
  - [ ] Emit warning at 75% threshold
  - [ ] Add metrics for monitoring dashboards

- [ ] Task 4: Write tests (AC: #1-4)
  - [ ] Test memory usage stays under limit
  - [ ] Test atomic file operations
  - [ ] Test large document handling
  - [ ] Test crash recovery (incomplete files)

## Dev Notes

### Architecture Compliance

**Streaming PDF Split Pattern:**
```python
# Update backend/app/services/pdf_chunker.py
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import psutil
import structlog
import pypdf

logger = structlog.get_logger(__name__)

MEMORY_WARNING_THRESHOLD = 0.75  # 75% of limit
MEMORY_LIMIT_MB = 50


class StreamingPDFChunker:
    """Memory-efficient PDF chunker using streaming page extraction.

    Ensures memory usage stays under 50MB regardless of PDF size by:
    - Using pypdf's lazy page loading
    - Writing chunks to temp storage immediately
    - Releasing memory after each chunk
    """

    def split_pdf_streaming(
        self,
        pdf_bytes: bytes,
        chunk_size: int = 25,
        temp_dir: str | None = None,
    ) -> list[tuple[Path, int, int]]:
        """Split PDF using streaming approach.

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Pages per chunk.
            temp_dir: Directory for temp chunk files.

        Returns:
            List of (chunk_path, page_start, page_end) tuples.
            Paths are temp files that caller must clean up.
        """
        temp_path = Path(temp_dir or tempfile.gettempdir())
        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        total_pages = len(reader.pages)

        chunks = []
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)

            # Extract single chunk with memory monitoring
            chunk_path = self._extract_chunk_streaming(
                reader=reader,
                page_start=page_start,
                page_end=page_end,
                temp_dir=temp_path,
            )

            chunks.append((chunk_path, page_start, page_end))
            page_start = page_end + 1

            # Check memory and log warning if needed
            self._check_memory_usage()

        return chunks

    def _extract_chunk_streaming(
        self,
        reader: pypdf.PdfReader,
        page_start: int,
        page_end: int,
        temp_dir: Path,
    ) -> Path:
        """Extract a page range to temp file using streaming.

        Uses atomic write pattern to prevent corruption.
        """
        chunk_filename = f"chunk_{page_start}_{page_end}.pdf"
        final_path = temp_dir / chunk_filename
        tmp_path = temp_dir / f"{chunk_filename}.tmp"

        try:
            writer = pypdf.PdfWriter()

            # Add pages one at a time to minimize memory
            for page_idx in range(page_start - 1, page_end):
                writer.add_page(reader.pages[page_idx])

            # Write to temp file first (atomic pattern)
            with open(tmp_path, "wb") as f:
                writer.write(f)

            # Atomic rename
            tmp_path.rename(final_path)

            logger.debug(
                "chunk_extracted_streaming",
                page_start=page_start,
                page_end=page_end,
                file_size=final_path.stat().st_size,
            )

            return final_path

        except Exception as e:
            # Clean up temp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise PDFChunkerError(f"Failed to extract chunk: {e}")

        finally:
            # Help garbage collector
            del writer

    def _check_memory_usage(self) -> None:
        """Check current memory usage and log warnings."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)

        if memory_mb > MEMORY_LIMIT_MB * MEMORY_WARNING_THRESHOLD:
            logger.warning(
                "memory_usage_high",
                current_mb=round(memory_mb, 1),
                limit_mb=MEMORY_LIMIT_MB,
                threshold_pct=MEMORY_WARNING_THRESHOLD * 100,
            )

        # Emit metric for monitoring
        # metrics.gauge("pdf_chunker.memory_mb", memory_mb)


class AtomicFileWriter:
    """Context manager for atomic file writes.

    Writes to .tmp file first, renames on success.
    Cleans up .tmp on failure.
    """

    def __init__(self, final_path: Path):
        self.final_path = Path(final_path)
        self.tmp_path = self.final_path.with_suffix(
            self.final_path.suffix + ".tmp"
        )
        self._file = None

    def __enter__(self):
        self._file = open(self.tmp_path, "wb")
        return self._file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

        if exc_type is None:
            # Success - rename temp to final
            self.tmp_path.rename(self.final_path)
        else:
            # Failure - clean up temp file
            if self.tmp_path.exists():
                self.tmp_path.unlink()

        return False  # Don't suppress exceptions
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      pdf_chunker.py         # Modify - Add streaming methods
    utils/
      atomic_file.py         # NEW - Atomic file writer utility
  tests/
    services/
      test_streaming_pdf_chunker.py  # NEW - Memory tests
```

### Technical Requirements

**Memory Monitoring with psutil:**
```python
import psutil

def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)
```

**Temp File Cleanup:**
```python
import tempfile
from pathlib import Path

def cleanup_chunk_files(chunk_paths: list[Path]) -> None:
    """Clean up temporary chunk files."""
    for path in chunk_paths:
        try:
            if path.exists():
                path.unlink()
        except OSError as e:
            logger.warning("chunk_cleanup_failed", path=str(path), error=str(e))
```

### Testing Requirements

```python
# tests/services/test_streaming_pdf_chunker.py
import pytest
import psutil
from io import BytesIO
from pypdf import PdfWriter

from app.services.pdf_chunker import StreamingPDFChunker, MEMORY_LIMIT_MB


class TestMemoryUsage:
    def test_large_pdf_stays_under_memory_limit(self, create_large_pdf):
        # Arrange - Create 500-page PDF (~100MB)
        pdf_bytes = create_large_pdf(500)
        chunker = StreamingPDFChunker()

        initial_memory = psutil.Process().memory_info().rss

        # Act
        chunks = chunker.split_pdf_streaming(pdf_bytes, chunk_size=25)

        peak_memory = psutil.Process().memory_info().rss
        memory_increase_mb = (peak_memory - initial_memory) / (1024 * 1024)

        # Assert
        assert memory_increase_mb < MEMORY_LIMIT_MB

        # Cleanup
        for path, _, _ in chunks:
            path.unlink()


class TestAtomicFileWriter:
    def test_writes_to_final_on_success(self, tmp_path):
        final_path = tmp_path / "output.pdf"

        with AtomicFileWriter(final_path) as f:
            f.write(b"test content")

        assert final_path.exists()
        assert not (tmp_path / "output.pdf.tmp").exists()

    def test_cleans_up_on_failure(self, tmp_path):
        final_path = tmp_path / "output.pdf"

        with pytest.raises(ValueError):
            with AtomicFileWriter(final_path) as f:
                f.write(b"test content")
                raise ValueError("Simulated failure")

        assert not final_path.exists()
        assert not (tmp_path / "output.pdf.tmp").exists()


@pytest.fixture
def create_large_pdf():
    """Create test PDFs with specified page count."""
    def _create(page_count: int) -> bytes:
        writer = PdfWriter()
        for i in range(page_count):
            # Add page with some content to simulate real size
            page = writer.add_blank_page(612, 792)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    return _create
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.1] - Full AC
- [Source: Story 16.2] - Base PDFChunker implementation
- [Source: project-context.md#Backend] - Python patterns

### Critical Implementation Notes

**DO NOT:**
- Load entire PDF into memory
- Keep all pages in memory during split
- Leave .tmp files on failures
- Skip memory monitoring

**MUST:**
- Use pypdf's lazy page loading
- Write chunks to temp files as created
- Use atomic write pattern (.tmp → rename)
- Monitor and log memory usage
- Clean up temp files on both success and failure

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

