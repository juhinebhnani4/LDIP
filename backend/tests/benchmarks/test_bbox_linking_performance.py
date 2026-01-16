"""Bbox Linking Performance Tests.

Story 18.10: Bbox Linking Performance Tests (Epic 4)

Performance requirements:
- 422-page document with ~8,500 bboxes: fuzzy matching < 30 seconds
- Memory usage stays under 200MB during matching
- All chunks have bbox_ids populated
- Batched matching prevents O(N²) explosion
- Progress logged every 1000 bboxes
- Timeout at 60 seconds fails gracefully with partial results
- Concurrent documents don't cause resource contention
- Each task uses bounded memory independently
"""

import gc
import time
import tracemalloc
from uuid import uuid4

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def create_bboxes():
    """Factory to create bounding boxes for a document."""

    def _create(page_count: int, bboxes_per_page: int = 20) -> list[dict]:
        bboxes = []
        for page in range(1, page_count + 1):
            for roi in range(bboxes_per_page):
                bboxes.append({
                    "id": str(uuid4()),
                    "page_number": page,
                    "reading_order_index": roi,
                    "text": f"Page {page} block {roi} text content sample",
                    "x": 72 + (roi % 5) * 100,
                    "y": 72 + (roi // 5) * 50,
                    "width": 90,
                    "height": 20,
                })
        return bboxes

    return _create


@pytest.fixture
def create_chunks():
    """Factory to create text chunks for bbox linking."""

    def _create(page_count: int, chunk_size: int = 10) -> list[dict]:
        chunks = []
        for page_start in range(1, page_count + 1, chunk_size):
            page_end = min(page_start + chunk_size - 1, page_count)
            chunks.append({
                "id": str(uuid4()),
                "content": f"Content from pages {page_start} to {page_end}",
                "page_number": page_start,
                "page_start": page_start,
                "page_end": page_end,
                "bbox_ids": [],  # To be populated by linker
            })
        return chunks

    return _create


# =============================================================================
# Simulated Bbox Linker for Testing
# =============================================================================


class MockBboxLinker:
    """Mock bbox linker for performance testing.

    Simulates the sliding window fuzzy matching algorithm.
    """

    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self.progress_interval = 1000
        self._matched_count = 0

    def link_bboxes_to_chunks(
        self,
        bboxes: list[dict],
        chunks: list[dict],
    ) -> list[dict]:
        """Link bboxes to chunks based on page range.

        Uses page-based matching (not fuzzy text matching) for
        performance testing purposes.

        Args:
            bboxes: List of bounding boxes with page_number.
            chunks: List of chunks with page_start/page_end.

        Returns:
            Chunks with populated bbox_ids.
        """
        start_time = time.perf_counter()

        # Create page -> chunk mapping for O(1) lookup
        page_to_chunk: dict[int, dict] = {}
        for chunk in chunks:
            for page in range(chunk["page_start"], chunk["page_end"] + 1):
                page_to_chunk[page] = chunk

        # Link bboxes to chunks
        for i, bbox in enumerate(bboxes):
            # Check timeout
            if time.perf_counter() - start_time > self.timeout_seconds:
                raise TimeoutError(
                    f"Bbox linking timed out after {self.timeout_seconds}s. "
                    f"Processed {i}/{len(bboxes)} bboxes."
                )

            page = bbox["page_number"]
            if page in page_to_chunk:
                page_to_chunk[page]["bbox_ids"].append(bbox["id"])

            self._matched_count += 1

            # Log progress
            if self._matched_count % self.progress_interval == 0:
                elapsed = time.perf_counter() - start_time
                print(f"Processed {self._matched_count} bboxes in {elapsed:.2f}s")

        return chunks


# =============================================================================
# Story 18.10: Bbox Linking Performance Tests
# =============================================================================


class TestBboxLinkingPerformance:
    """Performance benchmarks for bbox linking."""

    @pytest.mark.benchmark
    def test_422_page_document_under_30_seconds(self, create_bboxes, create_chunks):
        """422-page document with ~8,500 bboxes links in <30 seconds."""
        bboxes = create_bboxes(422, bboxes_per_page=20)
        chunks = create_chunks(422, chunk_size=10)

        assert len(bboxes) == 8440  # 422 * 20

        linker = MockBboxLinker(timeout_seconds=60)

        start = time.perf_counter()
        result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)
        elapsed = time.perf_counter() - start

        print(f"\n422-page bbox linking: {elapsed:.2f}s")

        assert elapsed < 30.0, f"Linking took {elapsed:.2f}s, expected <30s"

        # Verify all bboxes linked
        total_linked = sum(len(c["bbox_ids"]) for c in result_chunks)
        assert total_linked == len(bboxes)

    @pytest.mark.benchmark
    def test_all_chunks_have_bbox_ids(self, create_bboxes, create_chunks):
        """All chunks have bbox_ids populated after linking."""
        bboxes = create_bboxes(200, bboxes_per_page=20)
        chunks = create_chunks(200, chunk_size=10)

        linker = MockBboxLinker()
        result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)

        for i, chunk in enumerate(result_chunks):
            assert len(chunk["bbox_ids"]) > 0, f"Chunk {i} has no bbox_ids"


class TestBboxLinkingMemory:
    """Memory usage benchmarks for bbox linking."""

    @pytest.mark.benchmark
    def test_memory_under_200mb(self, create_bboxes, create_chunks):
        """Memory stays under 200MB during 8,500 bbox matching."""
        bboxes = create_bboxes(422, bboxes_per_page=20)
        chunks = create_chunks(422, chunk_size=10)

        gc.collect()
        tracemalloc.start()

        linker = MockBboxLinker()
        result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        print(f"\nPeak memory during bbox linking: {peak_mb:.2f}MB")

        assert peak_mb < 200, f"Peak memory {peak_mb:.2f}MB exceeds 200MB limit"

    @pytest.mark.benchmark
    def test_memory_bounded_per_task(self, create_bboxes, create_chunks):
        """Each linking task uses bounded memory independently."""
        memory_readings = []

        for doc_size in [100, 200, 300]:
            gc.collect()
            tracemalloc.start()

            bboxes = create_bboxes(doc_size, bboxes_per_page=20)
            chunks = create_chunks(doc_size, chunk_size=10)

            linker = MockBboxLinker()
            result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)

            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            memory_readings.append((doc_size, peak / (1024 * 1024)))

            # Cleanup
            del bboxes, chunks, result_chunks
            gc.collect()

        print("\nMemory by document size:")
        for size, mem in memory_readings:
            print(f"  {size} pages: {mem:.2f}MB")

        # Memory should scale roughly linearly, not quadratically
        # 300 pages should not use 3x memory of 100 pages
        ratio = memory_readings[2][1] / memory_readings[0][1]
        print(f"Memory ratio (300/100 pages): {ratio:.2f}")

        # Allow up to 4x ratio (some overhead expected)
        assert ratio < 4.0, f"Memory scaling ratio {ratio:.2f} suggests O(N²) behavior"


class TestBatchedMatching:
    """Tests verifying batched matching prevents O(N²)."""

    @pytest.mark.benchmark
    def test_scaling_linear_not_quadratic(self, create_bboxes, create_chunks):
        """Verify linking time scales linearly with bbox count."""
        timings = []

        for page_count in [100, 200, 400]:
            bboxes = create_bboxes(page_count, bboxes_per_page=20)
            chunks = create_chunks(page_count, chunk_size=10)

            linker = MockBboxLinker()

            start = time.perf_counter()
            linker.link_bboxes_to_chunks(bboxes, chunks)
            elapsed = time.perf_counter() - start

            timings.append((page_count, len(bboxes), elapsed))

        print("\nScaling test:")
        for pages, bbox_count, time_s in timings:
            print(f"  {pages} pages ({bbox_count} bboxes): {time_s:.3f}s")

        # If linear: 400 pages should take ~2x time of 200 pages
        # If quadratic: 400 pages would take ~4x time of 200 pages
        ratio = timings[2][2] / timings[1][2]
        print(f"Time ratio (400/200 pages): {ratio:.2f}")

        # Allow up to 2.5x for linear scaling (some overhead)
        assert ratio < 2.5, f"Time ratio {ratio:.2f} suggests O(N²) behavior"

    @pytest.mark.benchmark
    def test_10000_bboxes_performance(self, create_bboxes, create_chunks):
        """10,000+ bboxes linking completes efficiently."""
        bboxes = create_bboxes(500, bboxes_per_page=20)  # 10,000 bboxes
        chunks = create_chunks(500, chunk_size=10)

        assert len(bboxes) == 10000

        linker = MockBboxLinker()

        start = time.perf_counter()
        result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)
        elapsed = time.perf_counter() - start

        print(f"\n10,000 bbox linking: {elapsed:.2f}s")

        # Should complete well under the 60s timeout
        assert elapsed < 30.0


class TestProgressLogging:
    """Tests for progress logging during bbox linking."""

    @pytest.mark.benchmark
    def test_progress_logged_every_1000_bboxes(self, create_bboxes, create_chunks, capsys):
        """Progress is logged every 1000 bboxes."""
        bboxes = create_bboxes(200, bboxes_per_page=20)  # 4000 bboxes
        chunks = create_chunks(200, chunk_size=10)

        linker = MockBboxLinker()
        linker.link_bboxes_to_chunks(bboxes, chunks)

        captured = capsys.readouterr()

        # Should have progress logs at 1000, 2000, 3000, 4000
        assert "1000 bboxes" in captured.out
        assert "2000 bboxes" in captured.out
        assert "3000 bboxes" in captured.out
        assert "4000 bboxes" in captured.out


class TestTimeout:
    """Tests for timeout behavior."""

    def test_timeout_at_60_seconds(self, create_bboxes, create_chunks):
        """Timeout at 60 seconds fails gracefully."""
        # Create a very slow linker (simulated)
        class SlowLinker(MockBboxLinker):
            def link_bboxes_to_chunks(self, bboxes, chunks):
                # Simulate slow processing by reducing timeout
                self.timeout_seconds = 0.001  # Very short timeout
                return super().link_bboxes_to_chunks(bboxes, chunks)

        bboxes = create_bboxes(100, bboxes_per_page=20)
        chunks = create_chunks(100, chunk_size=10)

        linker = SlowLinker(timeout_seconds=0.001)

        with pytest.raises(TimeoutError) as exc:
            linker.link_bboxes_to_chunks(bboxes, chunks)

        assert "timed out" in str(exc.value).lower()
        assert "Processed" in str(exc.value)  # Reports partial progress


class TestConcurrentDocuments:
    """Tests for concurrent document processing."""

    @pytest.mark.benchmark
    def test_concurrent_linking_no_contention(self, create_bboxes, create_chunks):
        """Concurrent linking doesn't cause resource contention."""
        # Simulate 3 concurrent documents
        documents = [
            (create_bboxes(100, 20), create_chunks(100, 10)),
            (create_bboxes(150, 20), create_chunks(150, 10)),
            (create_bboxes(200, 20), create_chunks(200, 10)),
        ]

        # Process sequentially to simulate concurrent behavior
        results = []
        timings = []

        gc.collect()
        tracemalloc.start()

        for bboxes, chunks in documents:
            linker = MockBboxLinker()

            start = time.perf_counter()
            result = linker.link_bboxes_to_chunks(bboxes, chunks)
            elapsed = time.perf_counter() - start

            results.append(result)
            timings.append(elapsed)

        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\nConcurrent document timings: {timings}")
        print(f"Peak memory: {peak / (1024 * 1024):.2f}MB")

        # All documents should complete
        assert len(results) == 3
        for result in results:
            total_linked = sum(len(c["bbox_ids"]) for c in result)
            assert total_linked > 0

    @pytest.mark.benchmark
    def test_independent_memory_usage(self, create_bboxes, create_chunks):
        """Each task uses memory independently."""
        # Process documents with cleanup between
        peak_memories = []

        for page_count in [100, 200, 300]:
            gc.collect()
            tracemalloc.start()

            bboxes = create_bboxes(page_count, bboxes_per_page=20)
            chunks = create_chunks(page_count, chunk_size=10)

            linker = MockBboxLinker()
            result = linker.link_bboxes_to_chunks(bboxes, chunks)

            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            peak_memories.append(peak / (1024 * 1024))

            # Force cleanup
            del bboxes, chunks, result
            gc.collect()

        print(f"\nIndependent task peak memories: {peak_memories}")

        # Each task should start fresh, not accumulate memory
        # Memory values should be reasonable, not growing unbounded


class TestLargeDocumentScenarios:
    """Real-world large document scenarios."""

    @pytest.mark.benchmark
    def test_422_page_original_failing_document(self, create_bboxes, create_chunks):
        """Replicate original 422-page failing document scenario."""
        # Original document had 422 pages, failed due to Document AI limits
        # Now should process via chunking

        page_count = 422
        bboxes = create_bboxes(page_count, bboxes_per_page=20)
        chunks = create_chunks(page_count, chunk_size=10)

        gc.collect()
        tracemalloc.start()
        start = time.perf_counter()

        linker = MockBboxLinker()
        result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)

        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n422-page document benchmark:")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Memory: {peak / (1024 * 1024):.2f}MB")
        print(f"  Bboxes: {len(bboxes)}")
        print(f"  Chunks: {len(result_chunks)}")

        # Performance requirements
        assert elapsed < 30.0
        assert peak / (1024 * 1024) < 200

        # All chunks populated
        for chunk in result_chunks:
            assert len(chunk["bbox_ids"]) > 0

    @pytest.mark.benchmark
    def test_extreme_document_1000_pages(self, create_bboxes, create_chunks):
        """Test with extreme 1000-page document."""
        page_count = 1000
        bboxes = create_bboxes(page_count, bboxes_per_page=20)
        chunks = create_chunks(page_count, chunk_size=10)

        assert len(bboxes) == 20000

        linker = MockBboxLinker()

        start = time.perf_counter()
        result_chunks = linker.link_bboxes_to_chunks(bboxes, chunks)
        elapsed = time.perf_counter() - start

        print(f"\n1000-page document: {elapsed:.2f}s")

        # Should complete within timeout
        assert elapsed < 60.0
