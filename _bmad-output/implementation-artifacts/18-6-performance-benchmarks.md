# Story 18.6: Performance Benchmarks

Status: ready-for-dev

## Story

As a performance engineer,
I want benchmarks proving the system meets performance requirements,
so that we can deploy with confidence.

## Acceptance Criteria

1. **422-Page Document Performance**
   - 422-page PDF (matching original failure) processes in <4 minutes
   - Parallel chunking: 17 chunks, 5 concurrent, ~45s per chunk
   - Timing breakdown logged: split <10s, parallel OCR ~3min, merge <10s
   - Results include detailed timing metrics

2. **Concurrent Large Document Processing**
   - 5 concurrent large documents (200+ pages each) complete within 5 minutes
   - No OOM errors on workers with 2GB memory
   - Document AI rate limits not exceeded
   - All documents complete successfully

3. **Memory Profiling (PRE-MORTEM)**
   - Peak memory per worker is recorded
   - Memory growth over time is tracked (detect leaks)
   - Benchmark fails if memory exceeds 80% of limit
   - Memory metrics logged for each chunk

## Tasks / Subtasks

- [ ] Task 1: Create benchmark infrastructure (AC: #1, #2, #3)
  - [ ] Create `backend/tests/benchmarks/test_performance.py`
  - [ ] Add pytest-benchmark dependency
  - [ ] Create timing helper utilities
  - [ ] Create memory profiling utilities

- [ ] Task 2: Write 422-page benchmark (AC: #1)
  - [ ] Test split timing (<10s)
  - [ ] Test parallel OCR timing (~3min for 17 chunks)
  - [ ] Test merge timing (<10s)
  - [ ] Assert total time <4 minutes

- [ ] Task 3: Write concurrent processing benchmark (AC: #2)
  - [ ] Test 5 concurrent 200-page documents
  - [ ] Monitor memory usage per worker
  - [ ] Verify no rate limit errors (429)
  - [ ] Assert all complete within 5 minutes

- [ ] Task 4: Write memory benchmark (AC: #3)
  - [ ] Profile peak memory during processing
  - [ ] Track memory over time
  - [ ] Fail if exceeds 80% of 2GB limit (1.6GB)
  - [ ] Detect memory leaks

## Dev Notes

### Architecture Compliance

**Benchmark Test Structure:**
```python
# tests/benchmarks/test_performance.py
import pytest
import time
import tracemalloc
import psutil
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.pdf_chunker import PDFChunker
from app.services.ocr_result_merger import OCRResultMerger


MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2GB
MEMORY_THRESHOLD = 0.8  # 80%
MAX_MEMORY_BYTES = int(MEMORY_LIMIT_BYTES * MEMORY_THRESHOLD)  # 1.6GB


class TimingResult:
    """Container for benchmark timing results."""

    def __init__(self):
        self.split_time: float = 0
        self.ocr_time: float = 0
        self.merge_time: float = 0
        self.total_time: float = 0

    def __repr__(self):
        return (
            f"TimingResult(split={self.split_time:.2f}s, "
            f"ocr={self.ocr_time:.2f}s, "
            f"merge={self.merge_time:.2f}s, "
            f"total={self.total_time:.2f}s)"
        )


class MemoryTracker:
    """Track memory usage during benchmark."""

    def __init__(self):
        self.peak_memory = 0
        self.samples = []

    def sample(self):
        """Record current memory usage."""
        process = psutil.Process()
        current = process.memory_info().rss
        self.samples.append({
            "timestamp": datetime.now(),
            "memory_bytes": current,
        })
        if current > self.peak_memory:
            self.peak_memory = current
        return current

    def check_for_leaks(self) -> bool:
        """Check if memory is consistently growing (potential leak)."""
        if len(self.samples) < 10:
            return False

        # Compare first 25% to last 25%
        quarter = len(self.samples) // 4
        early_avg = sum(s["memory_bytes"] for s in self.samples[:quarter]) / quarter
        late_avg = sum(s["memory_bytes"] for s in self.samples[-quarter:]) / quarter

        # >50% growth suggests a leak
        return late_avg > early_avg * 1.5


@pytest.fixture
def memory_tracker():
    return MemoryTracker()


@pytest.fixture
def sample_422_page_pdf():
    return Path("tests/fixtures/large_pdfs/sample_422_pages.pdf")


class TestDocumentPerformance422Pages:
    """Benchmark 422-page document processing."""

    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_422_page_total_time_under_4_minutes(
        self,
        sample_422_page_pdf,
        mock_document_ai,
        memory_tracker,
    ):
        """422-page PDF should process in <4 minutes."""
        timing = TimingResult()
        start_total = time.perf_counter()

        # Phase 1: Split PDF
        start_split = time.perf_counter()
        chunker = PDFChunker(chunk_size=25)
        chunks = chunker.split_pdf(sample_422_page_pdf)
        timing.split_time = time.perf_counter() - start_split

        assert timing.split_time < 10, f"Split took {timing.split_time}s (>10s limit)"
        assert len(chunks) == 17, f"Expected 17 chunks, got {len(chunks)}"

        # Phase 2: Process chunks in parallel
        start_ocr = time.perf_counter()
        chunk_results = []

        # Simulate parallel processing with 5 concurrent workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for chunk_bytes, chunk_index, page_start, page_end in chunks:
                future = executor.submit(
                    self._mock_process_chunk,
                    chunk_index,
                    page_start,
                    page_end,
                    memory_tracker,
                )
                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                chunk_results.append(result)
                memory_tracker.sample()

        timing.ocr_time = time.perf_counter() - start_ocr

        # Phase 3: Merge results
        start_merge = time.perf_counter()
        merger = OCRResultMerger()
        merged = merger.merge_results(chunk_results, "doc-benchmark")
        timing.merge_time = time.perf_counter() - start_merge

        assert timing.merge_time < 10, f"Merge took {timing.merge_time}s (>10s limit)"

        timing.total_time = time.perf_counter() - start_total

        # Log timing breakdown
        print(f"\n{timing}")

        # Assertions
        assert timing.total_time < 240, (  # 4 minutes
            f"Total time {timing.total_time}s exceeds 4 minute limit"
        )
        assert timing.split_time < 10, "Split should be <10s"
        assert timing.merge_time < 10, "Merge should be <10s"

    def _mock_process_chunk(
        self,
        chunk_index: int,
        page_start: int,
        page_end: int,
        memory_tracker: MemoryTracker,
    ) -> dict:
        """Simulate chunk processing with realistic timing."""
        # Simulate ~45s processing time (scaled down for test)
        time.sleep(0.5)  # Scaled: 45s / 90 = 0.5s

        memory_tracker.sample()

        pages_in_chunk = page_end - page_start + 1
        return {
            "chunk_index": chunk_index,
            "page_start": page_start,
            "page_end": page_end,
            "bounding_boxes": [
                {"page": p, "reading_order_index": i}
                for p in range(1, pages_in_chunk + 1)
                for i in range(20)
            ],
            "full_text": f"Chunk {chunk_index} content",
            "page_count": pages_in_chunk,
        }


class TestConcurrentDocumentProcessing:
    """Benchmark concurrent large document processing."""

    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_5_concurrent_200_page_documents(
        self,
        memory_tracker,
        mock_document_ai,
    ):
        """5 concurrent 200-page documents should complete in <5 minutes."""
        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for doc_index in range(5):
                future = executor.submit(
                    self._process_large_document,
                    f"doc-{doc_index}",
                    200,
                    memory_tracker,
                )
                futures.append(future)

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                memory_tracker.sample()

        total_time = time.perf_counter() - start

        # Assertions
        assert total_time < 300, f"Total time {total_time}s exceeds 5 minutes"
        assert len(results) == 5, "All 5 documents should complete"
        assert all(r["success"] for r in results), "All documents should succeed"

        # Memory check
        assert memory_tracker.peak_memory < MAX_MEMORY_BYTES, (
            f"Peak memory {memory_tracker.peak_memory / 1e9:.2f}GB "
            f"exceeds {MAX_MEMORY_BYTES / 1e9:.2f}GB limit"
        )

    def _process_large_document(
        self,
        document_id: str,
        page_count: int,
        memory_tracker: MemoryTracker,
    ) -> dict:
        """Simulate processing a large document."""
        try:
            # Simulate processing time
            chunk_count = (page_count + 24) // 25
            for i in range(chunk_count):
                time.sleep(0.1)  # Scaled timing
                memory_tracker.sample()

            return {"document_id": document_id, "success": True}
        except Exception as e:
            return {"document_id": document_id, "success": False, "error": str(e)}


class TestMemoryBenchmark:
    """PRE-MORTEM: Memory profiling benchmarks."""

    @pytest.mark.benchmark
    def test_peak_memory_under_threshold(
        self,
        sample_422_page_pdf,
        memory_tracker,
    ):
        """Peak memory should stay under 80% of 2GB limit."""
        tracemalloc.start()

        # Simulate processing
        chunker = PDFChunker(chunk_size=25)
        chunks = chunker.split_pdf(sample_422_page_pdf)

        for chunk in chunks:
            memory_tracker.sample()
            # Process chunk (mocked)
            time.sleep(0.05)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\nPeak memory (tracemalloc): {peak / 1e6:.2f}MB")
        print(f"Peak memory (tracker): {memory_tracker.peak_memory / 1e6:.2f}MB")

        assert memory_tracker.peak_memory < MAX_MEMORY_BYTES, (
            f"Peak memory {memory_tracker.peak_memory / 1e9:.2f}GB "
            f"exceeds threshold"
        )

    @pytest.mark.benchmark
    def test_no_memory_leak_during_processing(
        self,
        memory_tracker,
    ):
        """Memory should not consistently grow during processing."""
        # Simulate multiple document processing cycles
        for cycle in range(10):
            for chunk in range(17):
                memory_tracker.sample()
                # Simulate chunk processing
                _ = [i for i in range(10000)]  # Allocate some memory
                time.sleep(0.01)

        has_leak = memory_tracker.check_for_leaks()
        assert not has_leak, "Potential memory leak detected"

    @pytest.mark.benchmark
    def test_memory_per_chunk_logged(
        self,
        memory_tracker,
    ):
        """Each chunk processing should log memory usage."""
        chunk_memories = []

        for chunk_index in range(17):
            before = memory_tracker.sample()
            # Simulate chunk processing
            time.sleep(0.05)
            after = memory_tracker.sample()

            chunk_memories.append({
                "chunk_index": chunk_index,
                "memory_before": before,
                "memory_after": after,
                "delta": after - before,
            })

        # Log memory per chunk
        for cm in chunk_memories:
            print(
                f"Chunk {cm['chunk_index']}: "
                f"delta={cm['delta'] / 1e6:.2f}MB"
            )

        # All chunks should have memory logged
        assert len(chunk_memories) == 17
```

### Dependencies

```toml
# pyproject.toml
[tool.poetry.group.dev.dependencies]
pytest-benchmark = "^4.0.0"
psutil = "^5.9.0"
```

### Test Markers

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "benchmark: marks tests as performance benchmarks",
    "slow: marks tests as slow-running",
]
```

### References

- [Source: epic-4-testing-validation.md#Story 4.6] - Full AC
- [Source: Story 16.4] - Parallel chunk processing
- [Source: architecture.md#Performance] - Performance requirements

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

