# Story 17.5: Implement Batch Bounding Box Inserts

Status: ready-for-dev

## Story

As a system saving large numbers of bounding boxes,
I want to batch inserts in groups of 500,
so that database transactions don't timeout on large documents.

## Acceptance Criteria

1. **Batch Size Limiting**
   - Document with 8,500 bboxes inserts in batches of 500
   - Each batch is a separate transaction
   - Progress logged after each batch

2. **Partial Failure Handling**
   - If batch 5/17 fails, batches 1-4 are committed (partial progress saved)
   - Failure reported with batch number
   - Retry can resume from batch 5

3. **Success Verification**
   - Total inserted matches expected count after all batches complete
   - Document status updated only after all batches succeed

4. **Transaction Management (CHAOS MONKEY)**
   - Explicit BEGIN/COMMIT wraps each batch
   - Isolation level is READ COMMITTED
   - Connection pooler handles transaction boundaries

5. **Timestamp Validation (CHAOS MONKEY)**
   - Timestamps set correctly by database
   - `created_at` reflects actual insert time
   - Warning logged if timestamps inconsistent

## Tasks / Subtasks

- [ ] Task 1: Implement batched insert method (AC: #1, #2, #3)
  - [ ] Create `save_bounding_boxes_batched()` method
  - [ ] Batch size of 500 records
  - [ ] Track progress per batch
  - [ ] Log after each batch

- [ ] Task 2: Implement resume-from-failure (AC: #2)
  - [ ] Track which batches completed
  - [ ] Support resuming from specific batch
  - [ ] Report clear failure context

- [ ] Task 3: Add validation (AC: #3, #5)
  - [ ] Verify total count after all batches
  - [ ] Validate timestamps are set
  - [ ] Log warnings for inconsistencies

- [ ] Task 4: Write tests (AC: #1-5)
  - [ ] Test batching with various counts
  - [ ] Test partial failure handling
  - [ ] Test timestamp validation

## Dev Notes

### Architecture Compliance

**Batched Insert Pattern:**
```python
# backend/app/services/bounding_box_service.py

BATCH_SIZE = 500


async def save_bounding_boxes_batched(
    self,
    document_id: str,
    matter_id: str,
    bounding_boxes: list[dict],
    batch_size: int = BATCH_SIZE,
) -> dict:
    """Save bounding boxes in batches to prevent timeout.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        bounding_boxes: List of bbox dicts.
        batch_size: Records per batch (default 500).

    Returns:
        {batches_completed: int, total_inserted: int, failed_batch: int | None}
    """
    total = len(bounding_boxes)
    batches = (total + batch_size - 1) // batch_size  # Ceiling division
    inserted = 0
    failed_batch = None

    logger.info(
        "bbox_batch_insert_start",
        document_id=document_id,
        total_bboxes=total,
        batch_count=batches,
        batch_size=batch_size,
    )

    for batch_num in range(batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total)
        batch = bounding_boxes[start_idx:end_idx]

        try:
            count = await self._insert_batch(
                document_id=document_id,
                matter_id=matter_id,
                batch=batch,
            )
            inserted += count

            logger.info(
                "bbox_batch_complete",
                document_id=document_id,
                batch=batch_num + 1,
                total_batches=batches,
                inserted_in_batch=count,
                total_inserted=inserted,
            )

        except Exception as e:
            failed_batch = batch_num + 1
            logger.error(
                "bbox_batch_failed",
                document_id=document_id,
                batch=failed_batch,
                total_batches=batches,
                error=str(e),
            )
            break

    return {
        "batches_completed": batch_num + 1 if failed_batch is None else failed_batch - 1,
        "total_batches": batches,
        "total_inserted": inserted,
        "failed_batch": failed_batch,
    }


async def _insert_batch(
    self,
    document_id: str,
    matter_id: str,
    batch: list[dict],
) -> int:
    """Insert a single batch of bounding boxes."""
    rows = [
        {
            **bbox,
            "document_id": document_id,
            "matter_id": matter_id,
        }
        for bbox in batch
    ]

    def _insert():
        response = (
            self.client.table("bounding_boxes")
            .insert(rows)
            .execute()
        )
        return len(response.data) if response.data else 0

    return await asyncio.to_thread(_insert)
```

### Testing Requirements

```python
class TestBatchedInsert:
    @pytest.mark.asyncio
    async def test_batches_large_insert(self, mock_supabase):
        # 1,250 bboxes should create 3 batches
        bboxes = [{"page": i} for i in range(1250)]
        service = BoundingBoxService()

        result = await service.save_bounding_boxes_batched(
            "doc-1", "matter-1", bboxes, batch_size=500
        )

        assert result["total_batches"] == 3
        assert result["batches_completed"] == 3

    @pytest.mark.asyncio
    async def test_partial_failure_preserves_progress(self, mock_supabase):
        # Fail on batch 3
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = [
            MagicMock(data=[{}] * 500),  # Batch 1 success
            MagicMock(data=[{}] * 500),  # Batch 2 success
            Exception("DB timeout"),      # Batch 3 fails
        ]

        bboxes = [{"page": i} for i in range(1250)]
        service = BoundingBoxService()

        result = await service.save_bounding_boxes_batched(
            "doc-1", "matter-1", bboxes, batch_size=500
        )

        assert result["failed_batch"] == 3
        assert result["total_inserted"] == 1000  # Batches 1-2
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.5] - Full AC

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

