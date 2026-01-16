# Story 18.10: Bbox Linking Performance Tests

Status: ready-for-dev

## Story

As a performance engineer,
I want benchmarks for bbox fuzzy matching on large documents,
so that chunking doesn't become a bottleneck.

## Acceptance Criteria

1. **422-Page Document Bbox Linking**
   - 422-page document with ~8,500 bounding boxes
   - chunk_document task with bbox linking completes in <30 seconds
   - Memory usage stays under 200MB during matching
   - All chunks have bbox_ids populated

2. **Large Scale Matching**
   - bbox_linker processes 10,000+ bounding boxes
   - Sliding window fuzzy match is batched to prevent O(N²) explosion
   - Progress is logged every 1000 bboxes
   - Timeout at 60 seconds fails gracefully with partial results

3. **Concurrent Processing**
   - Multiple large documents being chunked concurrently
   - Bbox matching doesn't create resource contention
   - Each task uses bounded memory independently

## Tasks / Subtasks

- [ ] Task 1: Create bbox linking benchmark fixtures (AC: #1, #2, #3)
  - [ ] Create `backend/tests/benchmarks/test_bbox_linking_performance.py`
  - [ ] Create 8,500 bbox test data fixture
  - [ ] Create mock chunk service

- [ ] Task 2: Write 422-page benchmark (AC: #1)
  - [ ] Test bbox linking completes in <30s
  - [ ] Monitor memory during matching
  - [ ] Verify all chunks have bbox_ids

- [ ] Task 3: Write large scale matching tests (AC: #2)
  - [ ] Test 10,000+ bbox processing
  - [ ] Verify batched matching (not O(N²))
  - [ ] Test progress logging
  - [ ] Test 60s timeout with partial results

- [ ] Task 4: Write concurrent processing tests (AC: #3)
  - [ ] Test multiple concurrent bbox linking tasks
  - [ ] Verify no resource contention
  - [ ] Verify bounded memory per task

## Dev Notes

### Architecture Compliance

**Bbox Linking Benchmark Structure:**
```python
# tests/benchmarks/test_bbox_linking_performance.py
import pytest
import time
import psutil
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, AsyncMock

from app.services.bbox_linker import BboxLinker, BboxLinkingConfig


MEMORY_LIMIT_MB = 200


@pytest.fixture
def large_document_bboxes():
    """8,500 bounding boxes for 422-page document (~20 per page)."""
    bboxes = []
    for page in range(1, 423):
        for idx in range(20):
            bboxes.append({
                "id": f"bbox-{page}-{idx}",
                "page": page,
                "reading_order_index": idx,
                "text": f"Text block {idx} on page {page}. " * 5,  # ~50 chars
                "x": 0.1,
                "y": 0.05 + (idx * 0.045),
                "width": 0.8,
                "height": 0.04,
            })
    return bboxes


@pytest.fixture
def chunks_for_linking():
    """Chunks that need bbox linking."""
    chunks = []
    # ~1000 tokens per chunk, roughly 5 pages
    for chunk_idx in range(85):  # 422 / 5 ≈ 85 chunks
        start_page = chunk_idx * 5 + 1
        end_page = min(start_page + 4, 422)

        # Chunk content matches some bbox text
        content_parts = []
        for page in range(start_page, end_page + 1):
            content_parts.append(f"Text block 10 on page {page}.")

        chunks.append({
            "id": f"chunk-{chunk_idx}",
            "chunk_index": chunk_idx,
            "page_number": start_page,
            "content": " ".join(content_parts),
        })
    return chunks


class MemoryMonitor:
    """Monitor memory usage during benchmark."""

    def __init__(self, limit_mb: int = MEMORY_LIMIT_MB):
        self.limit_bytes = limit_mb * 1024 * 1024
        self.samples = []
        self.process = psutil.Process()

    def sample(self) -> int:
        """Record current memory usage."""
        current = self.process.memory_info().rss
        self.samples.append(current)
        return current

    @property
    def peak_mb(self) -> float:
        return max(self.samples) / (1024 * 1024) if self.samples else 0

    def check_limit(self) -> bool:
        """Return True if within limit."""
        return self.peak_mb < MEMORY_LIMIT_MB


class TestBboxLinking422Pages:
    """Benchmark bbox linking for 422-page document."""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_bbox_linking_under_30_seconds(
        self,
        large_document_bboxes,
        chunks_for_linking,
    ):
        """Bbox linking for 8,500 bboxes should complete in <30s."""
        linker = BboxLinker(
            config=BboxLinkingConfig(
                batch_size=500,
                timeout_seconds=60,
            )
        )

        start = time.perf_counter()

        result = await linker.link_bboxes_to_chunks(
            bboxes=large_document_bboxes,
            chunks=chunks_for_linking,
        )

        elapsed = time.perf_counter() - start

        print(f"\nBbox linking completed in {elapsed:.2f}s")

        assert elapsed < 30, f"Bbox linking took {elapsed:.2f}s (>30s limit)"
        assert result.chunks_linked == len(chunks_for_linking)

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_memory_under_200mb_during_linking(
        self,
        large_document_bboxes,
        chunks_for_linking,
    ):
        """Memory usage should stay under 200MB during matching."""
        memory = MemoryMonitor()
        linker = BboxLinker()

        # Sample memory during linking
        async def link_with_monitoring():
            memory.sample()

            result = await linker.link_bboxes_to_chunks(
                bboxes=large_document_bboxes,
                chunks=chunks_for_linking,
                progress_callback=lambda _: memory.sample(),
            )

            memory.sample()
            return result

        result = await link_with_monitoring()

        print(f"\nPeak memory: {memory.peak_mb:.2f}MB")

        assert memory.check_limit(), (
            f"Peak memory {memory.peak_mb:.2f}MB exceeds {MEMORY_LIMIT_MB}MB limit"
        )

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_all_chunks_have_bbox_ids(
        self,
        large_document_bboxes,
        chunks_for_linking,
    ):
        """All chunks should have bbox_ids populated after linking."""
        linker = BboxLinker()

        result = await linker.link_bboxes_to_chunks(
            bboxes=large_document_bboxes,
            chunks=chunks_for_linking,
        )

        chunks_with_bboxes = [
            c for c in result.chunks
            if c.get("bbox_ids") and len(c["bbox_ids"]) > 0
        ]

        assert len(chunks_with_bboxes) == len(chunks_for_linking), (
            f"Only {len(chunks_with_bboxes)}/{len(chunks_for_linking)} "
            "chunks have bbox_ids"
        )


class TestLargeScaleMatching:
    """Test matching performance at scale."""

    @pytest.fixture
    def extra_large_bboxes(self):
        """10,000+ bounding boxes for stress testing."""
        return [
            {
                "id": f"bbox-{i}",
                "page": (i // 20) + 1,
                "reading_order_index": i % 20,
                "text": f"Large scale test text block {i}",
            }
            for i in range(10500)
        ]

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_10000_bboxes_batched_matching(
        self,
        extra_large_bboxes,
    ):
        """10,000+ bboxes should use batched matching, not O(N²)."""
        linker = BboxLinker(
            config=BboxLinkingConfig(
                batch_size=500,  # Process 500 at a time
            )
        )

        # Create simple chunks
        chunks = [
            {
                "id": f"chunk-{i}",
                "content": f"Large scale test text block {i * 100}",
            }
            for i in range(100)
        ]

        start = time.perf_counter()

        result = await linker.link_bboxes_to_chunks(
            bboxes=extra_large_bboxes,
            chunks=chunks,
        )

        elapsed = time.perf_counter() - start

        # O(N²) would take much longer than 60s for 10,000 items
        # Batched O(N*M/batch) should be much faster
        assert elapsed < 60, (
            f"Matching took {elapsed:.2f}s - may not be batched properly"
        )

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_progress_logged_every_1000_bboxes(
        self,
        extra_large_bboxes,
        caplog,
    ):
        """Progress should be logged every 1000 bboxes."""
        linker = BboxLinker(
            config=BboxLinkingConfig(
                log_progress_every=1000,
            )
        )

        chunks = [{"id": "chunk-1", "content": "test"}]

        with caplog.at_level("INFO"):
            await linker.link_bboxes_to_chunks(
                bboxes=extra_large_bboxes,
                chunks=chunks,
            )

        # Should have progress logs at 1000, 2000, 3000, etc.
        progress_logs = [
            record for record in caplog.records
            if "progress" in record.message.lower()
            or "bboxes" in record.message.lower()
        ]

        # At least 10 progress updates for 10,500 bboxes
        assert len(progress_logs) >= 10, (
            f"Only {len(progress_logs)} progress logs found"
        )

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_timeout_returns_partial_results(
        self,
        extra_large_bboxes,
    ):
        """60s timeout should fail gracefully with partial results."""
        linker = BboxLinker(
            config=BboxLinkingConfig(
                timeout_seconds=1,  # Very short timeout for test
                batch_size=100,
            )
        )

        chunks = [
            {
                "id": f"chunk-{i}",
                "content": f"Content {i}",
            }
            for i in range(1000)
        ]

        result = await linker.link_bboxes_to_chunks(
            bboxes=extra_large_bboxes,
            chunks=chunks,
        )

        # Should have partial results, not crash
        assert result.timed_out == True
        assert result.chunks_linked > 0, "Should have some partial results"
        assert result.chunks_linked < len(chunks), "Should not complete all"


class TestConcurrentBboxLinking:
    """Test concurrent bbox linking doesn't cause contention."""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_linking_no_contention(
        self,
        large_document_bboxes,
    ):
        """Multiple concurrent linking tasks should not contend."""
        async def link_document(doc_id: str) -> dict:
            linker = BboxLinker()

            chunks = [
                {
                    "id": f"{doc_id}-chunk-{i}",
                    "content": f"Content for {doc_id} chunk {i}",
                }
                for i in range(20)
            ]

            start = time.perf_counter()

            result = await linker.link_bboxes_to_chunks(
                bboxes=large_document_bboxes[:2000],  # Subset for speed
                chunks=chunks,
            )

            elapsed = time.perf_counter() - start

            return {
                "doc_id": doc_id,
                "elapsed": elapsed,
                "chunks_linked": result.chunks_linked,
            }

        # Run 5 concurrent linking tasks
        tasks = [
            link_document(f"doc-{i}")
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should complete
        assert len(results) == 5
        assert all(r["chunks_linked"] > 0 for r in results)

        # No task should take excessively long due to contention
        elapsed_times = [r["elapsed"] for r in results]
        max_time = max(elapsed_times)
        min_time = min(elapsed_times)

        # If contention exists, spread would be very large
        # Allow 3x variation (some natural variation expected)
        assert max_time < min_time * 3, (
            f"Large time variation suggests contention: "
            f"min={min_time:.2f}s, max={max_time:.2f}s"
        )

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_bounded_memory_per_task(
        self,
        large_document_bboxes,
    ):
        """Each concurrent task should use bounded memory."""
        memory_samples = {}

        async def link_with_memory_check(doc_id: str) -> dict:
            process = psutil.Process()
            initial_memory = process.memory_info().rss

            linker = BboxLinker()
            chunks = [
                {"id": f"{doc_id}-chunk-{i}", "content": f"Content {i}"}
                for i in range(10)
            ]

            await linker.link_bboxes_to_chunks(
                bboxes=large_document_bboxes[:1000],
                chunks=chunks,
            )

            final_memory = process.memory_info().rss
            memory_delta = (final_memory - initial_memory) / (1024 * 1024)

            return {
                "doc_id": doc_id,
                "memory_delta_mb": memory_delta,
            }

        # Run concurrent tasks
        tasks = [
            link_with_memory_check(f"doc-{i}")
            for i in range(3)
        ]

        results = await asyncio.gather(*tasks)

        # Each task's memory delta should be bounded
        for result in results:
            # Individual task shouldn't use more than 100MB
            assert result["memory_delta_mb"] < 100, (
                f"Task {result['doc_id']} used {result['memory_delta_mb']:.2f}MB"
            )
```

### BboxLinker Configuration

```python
# app/services/bbox_linker.py
from dataclasses import dataclass


@dataclass
class BboxLinkingConfig:
    """Configuration for bbox linking."""

    batch_size: int = 500
    timeout_seconds: int = 60
    log_progress_every: int = 1000
    fuzzy_threshold: float = 0.8
```

### Testing Requirements

**Test Markers:**
```python
[tool.pytest.ini_options]
markers = [
    "benchmark: marks tests as performance benchmarks",
]
```

### References

- [Source: epic-4-testing-validation.md#Story 4.10] - Full AC
- [Source: Story 17.5] - Batch bbox inserts
- [Source: architecture.md#Chunking] - Chunk service patterns

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

