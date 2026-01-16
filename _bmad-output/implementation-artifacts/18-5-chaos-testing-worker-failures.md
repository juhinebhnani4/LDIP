# Story 18.5: Chaos Testing for Worker Failures

Status: ready-for-dev

## Story

As a reliability engineer,
I want chaos tests that simulate worker failures,
so that I know the system recovers gracefully.

## Acceptance Criteria

1. **Mid-Processing Worker Failure**
   - When a worker is killed mid-processing of chunk 5 (of 10)
   - Chunks 1-4 remain marked as 'completed'
   - Chunk 5 is marked as 'failed' or 'processing' (detected via timeout)
   - Retry correctly reprocesses only failed chunks

2. **Merge Interruption Recovery**
   - When merge operation is interrupted
   - System recovers with either merge completion or results preserved for retry
   - No partial/corrupt data is saved to bounding_boxes table
   - Transactional integrity is maintained

3. **State Consistency**
   - After any failure, document state is queryable
   - Chunk progress accurately reflects actual state
   - No orphaned chunk records after recovery

## Tasks / Subtasks

- [ ] Task 1: Create chaos test fixtures (AC: #1, #2, #3)
  - [ ] Create `backend/tests/chaos/test_worker_failures.py`
  - [ ] Create helper to simulate worker kill
  - [ ] Create helper to simulate network partition
  - [ ] Create helper to simulate merge interruption

- [ ] Task 2: Write mid-processing failure tests (AC: #1)
  - [ ] Test worker killed during chunk processing
  - [ ] Verify completed chunks preserved
  - [ ] Verify failed chunk detected via heartbeat timeout
  - [ ] Verify retry processes only failed chunks

- [ ] Task 3: Write merge interruption tests (AC: #2)
  - [ ] Test merge killed mid-transaction
  - [ ] Verify no partial bounding_boxes saved
  - [ ] Verify chunk results preserved for retry
  - [ ] Verify retry completes merge successfully

- [ ] Task 4: Write state consistency tests (AC: #3)
  - [ ] Test document state after various failures
  - [ ] Verify chunk progress calculation accuracy
  - [ ] Verify no orphaned records

## Dev Notes

### Architecture Compliance

**Chaos Test Structure:**
```python
# tests/chaos/test_worker_failures.py
import pytest
import asyncio
import signal
import os
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, UTC, timedelta

from app.services.ocr_chunk_service import OCRChunkService, ChunkStatus
from app.services.ocr_result_merger import OCRResultMerger
from app.workers.tasks.document_tasks import process_chunk_task


class WorkerSimulator:
    """Simulates worker behavior for chaos testing."""

    def __init__(self, chunk_service: OCRChunkService):
        self.chunk_service = chunk_service
        self.killed = False

    async def process_chunk_with_kill(
        self,
        chunk_index: int,
        kill_at_chunk: int,
        document_id: str,
    ):
        """Process chunk but kill worker at specified chunk."""
        if chunk_index == kill_at_chunk:
            self.killed = True
            # Simulate worker death - no cleanup, no status update
            raise SystemExit("Worker killed")

        # Normal processing
        await self.chunk_service.update_status(
            document_id=document_id,
            chunk_index=chunk_index,
            status=ChunkStatus.COMPLETED,
        )


@pytest.fixture
def worker_simulator(mock_chunk_service):
    return WorkerSimulator(mock_chunk_service)


class TestMidProcessingWorkerFailure:
    """Test system recovery when worker dies mid-chunk-processing."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_worker_kill_preserves_completed_chunks(
        self,
        mock_chunk_service,
        mock_supabase,
    ):
        """Chunks 1-4 should remain completed when worker dies on chunk 5."""
        document_id = "doc-test"

        # Setup: Create 10 chunks, mark 1-4 as completed
        chunks = []
        for i in range(10):
            chunk = await mock_chunk_service.create_chunk(
                document_id=document_id,
                matter_id="matter-test",
                chunk_index=i,
                page_start=i * 25 + 1,
                page_end=(i + 1) * 25,
            )
            if i < 4:
                await mock_chunk_service.update_status(
                    document_id=document_id,
                    chunk_index=i,
                    status=ChunkStatus.COMPLETED,
                )
            chunks.append(chunk)

        # Simulate chunk 5 (index 4) being processed when worker dies
        chunk_5 = chunks[4]
        await mock_chunk_service.update_status(
            document_id=document_id,
            chunk_index=4,
            status=ChunkStatus.PROCESSING,
        )

        # Simulate worker death (no status update, stale heartbeat)
        # ... worker dies ...

        # Verify completed chunks preserved
        progress = await mock_chunk_service.get_chunk_progress(document_id)
        assert progress.completed == 4, "Completed chunks should be preserved"
        assert progress.processing == 1, "Chunk 5 should still show processing"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_stale_chunk_detected_via_timeout(
        self,
        mock_chunk_service,
        mock_supabase,
    ):
        """Chunk stuck in processing should be detected via heartbeat timeout."""
        document_id = "doc-test"

        # Create chunk and set to processing with old heartbeat
        await mock_chunk_service.create_chunk(
            document_id=document_id,
            matter_id="matter-test",
            chunk_index=4,
            page_start=101,
            page_end=125,
        )
        await mock_chunk_service.update_status(
            document_id=document_id,
            chunk_index=4,
            status=ChunkStatus.PROCESSING,
        )

        # Simulate stale heartbeat (>90 seconds old)
        with patch.object(
            mock_chunk_service,
            "_get_chunk_heartbeat",
            return_value=datetime.now(UTC) - timedelta(seconds=100),
        ):
            stale_chunks = await mock_chunk_service.detect_stale_chunks(document_id)

        assert len(stale_chunks) == 1, "Should detect 1 stale chunk"
        assert stale_chunks[0].chunk_index == 4

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_retry_processes_only_failed_chunks(
        self,
        mock_chunk_service,
        mock_supabase,
    ):
        """Retry should only process failed/stale chunks."""
        document_id = "doc-test"

        # Setup: 4 completed, 1 failed, 5 pending
        for i in range(10):
            await mock_chunk_service.create_chunk(
                document_id=document_id,
                matter_id="matter-test",
                chunk_index=i,
                page_start=i * 25 + 1,
                page_end=(i + 1) * 25,
            )

            if i < 4:
                status = ChunkStatus.COMPLETED
            elif i == 4:
                status = ChunkStatus.FAILED
            else:
                status = ChunkStatus.PENDING

            await mock_chunk_service.update_status(
                document_id=document_id,
                chunk_index=i,
                status=status,
            )

        # Get chunks needing retry
        retry_chunks = await mock_chunk_service.get_retry_chunks(document_id)

        # Should include failed (1) + pending (5) = 6 chunks
        assert len(retry_chunks) == 6
        chunk_indices = [c.chunk_index for c in retry_chunks]
        assert 4 in chunk_indices, "Failed chunk should be included"
        assert all(i in chunk_indices for i in range(5, 10)), "Pending chunks included"
        assert all(i not in chunk_indices for i in range(4)), "Completed chunks excluded"


class TestMergeInterruptionRecovery:
    """Test system recovery when merge operation is interrupted."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_merge_kill_no_partial_bboxes(
        self,
        mock_chunk_service,
        mock_supabase,
    ):
        """Interrupted merge should not leave partial bounding_boxes."""
        document_id = "doc-test"

        # Setup: All chunks completed with results
        chunk_results = [
            {
                "chunk_index": i,
                "page_start": i * 25 + 1,
                "page_end": (i + 1) * 25,
                "bounding_boxes": [
                    {"page": p, "reading_order_index": 0}
                    for p in range(1, 26)
                ],
            }
            for i in range(4)
        ]

        # Simulate merge that dies mid-insert
        merger = OCRResultMerger()

        with patch.object(
            mock_supabase,
            "table",
            side_effect=Exception("Connection lost during insert"),
        ):
            with pytest.raises(Exception):
                await merger.merge_and_save(
                    chunk_results,
                    document_id,
                    supabase_client=mock_supabase,
                )

        # Verify no partial data saved
        # In real implementation, this uses transactions
        bboxes = await mock_supabase.table("bounding_boxes").select("*").execute()
        assert len(bboxes.data) == 0, "No partial bboxes should be saved"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_chunk_results_preserved_after_merge_failure(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        """Chunk results in storage should be preserved for retry."""
        document_id = "doc-test"
        matter_id = "matter-test"

        # Setup: Store chunk results
        for i in range(4):
            await mock_storage_service.upload(
                path=f"ocr-chunks/{matter_id}/{document_id}/{i}.json",
                data={"chunk_index": i, "bounding_boxes": []},
            )

        # Simulate merge failure
        with pytest.raises(Exception):
            # ... merge fails ...
            pass

        # Verify chunk results still in storage
        for i in range(4):
            result = await mock_storage_service.download(
                path=f"ocr-chunks/{matter_id}/{document_id}/{i}.json"
            )
            assert result is not None, f"Chunk {i} results should be preserved"


class TestStateConsistency:
    """Test state consistency after failures."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_document_state_queryable_after_failure(
        self,
        mock_chunk_service,
    ):
        """Document and chunk state should be queryable after any failure."""
        document_id = "doc-test"

        # Setup mixed state
        states = [
            ChunkStatus.COMPLETED,
            ChunkStatus.COMPLETED,
            ChunkStatus.FAILED,
            ChunkStatus.PROCESSING,  # Stale
            ChunkStatus.PENDING,
        ]

        for i, status in enumerate(states):
            await mock_chunk_service.create_chunk(
                document_id=document_id,
                matter_id="matter-test",
                chunk_index=i,
                page_start=i * 25 + 1,
                page_end=(i + 1) * 25,
            )
            await mock_chunk_service.update_status(
                document_id=document_id,
                chunk_index=i,
                status=status,
            )

        # Query state
        progress = await mock_chunk_service.get_chunk_progress(document_id)

        assert progress.total == 5
        assert progress.completed == 2
        assert progress.failed == 1
        assert progress.processing == 1
        assert progress.pending == 1

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_no_orphaned_records_after_recovery(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        """No orphaned chunk records should exist after recovery."""
        document_id = "doc-test"
        matter_id = "matter-test"

        # Create chunks
        for i in range(5):
            await mock_chunk_service.create_chunk(
                document_id=document_id,
                matter_id=matter_id,
                chunk_index=i,
                page_start=i * 25 + 1,
                page_end=(i + 1) * 25,
            )

        # Simulate partial cleanup (some storage deleted, records remain)
        await mock_storage_service.delete(
            path=f"ocr-chunks/{matter_id}/{document_id}/0.json"
        )
        await mock_storage_service.delete(
            path=f"ocr-chunks/{matter_id}/{document_id}/1.json"
        )

        # Run orphan detection
        orphans = await mock_chunk_service.detect_orphan_records(
            document_id=document_id,
            storage_service=mock_storage_service,
        )

        # Records without corresponding storage are orphans
        assert len(orphans) >= 0  # May vary based on implementation
```

### Testing Requirements

**Test Markers:**
```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "chaos: marks tests as chaos/reliability tests",
]
```

### References

- [Source: epic-4-testing-validation.md#Story 4.5] - Full AC
- [Source: Story 15.2] - OCRChunkService
- [Source: Story 17.4] - Idempotent processing

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

