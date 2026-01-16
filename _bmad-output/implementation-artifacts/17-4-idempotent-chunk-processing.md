# Story 17.4: Implement Idempotent Chunk Processing

Status: ready-for-dev

## Story

As a system handling retries and reprocessing,
I want idempotent chunk processing that deletes before inserting,
so that re-running a chunk doesn't create duplicate bounding boxes.

## Acceptance Criteria

1. **Delete-Before-Insert Pattern**
   - When document is reprocessed, all existing bounding boxes deleted first
   - New bounding boxes inserted in a single transaction
   - No duplicate bboxes created on retry

2. **Transaction Rollback**
   - If delete-insert transaction fails midway, transaction rolls back
   - Original bounding boxes preserved (no partial state)

3. **Downstream Reference Handling**
   - Old bboxes removed before new ones inserted
   - Downstream references (chunks.bbox_ids) handled by CASCADE or subsequent reprocessing

## Tasks / Subtasks

- [ ] Task 1: Implement idempotent bbox save (AC: #1, #2)
  - [ ] Modify `BoundingBoxService.save_bounding_boxes()`
  - [ ] Delete existing bboxes for document before insert
  - [ ] Wrap in transaction
  - [ ] Return count of deleted + inserted

- [ ] Task 2: Handle downstream references (AC: #3)
  - [ ] Document CASCADE behavior for chunk.bbox_ids
  - [ ] Or invalidate chunk references before delete
  - [ ] Ensure RAG pipeline handles reprocessing

- [ ] Task 3: Write tests (AC: #1-3)
  - [ ] Test reprocessing deletes old bboxes
  - [ ] Test transaction rollback preserves data
  - [ ] Test no duplicates on multiple runs

## Dev Notes

### Architecture Compliance

**Idempotent Save Pattern:**
```python
# Modify backend/app/services/bounding_box_service.py

async def save_bounding_boxes_idempotent(
    self,
    document_id: str,
    matter_id: str,
    bounding_boxes: list[dict],
) -> dict:
    """Save bounding boxes with idempotent delete-before-insert.

    Ensures no duplicates on reprocessing by deleting existing
    bboxes for the document before inserting new ones.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        bounding_boxes: List of bbox dicts to insert.

    Returns:
        {deleted: int, inserted: int}
    """
    def _delete_and_insert():
        # Delete existing bboxes for this document
        delete_response = (
            self.client.table("bounding_boxes")
            .delete()
            .eq("document_id", document_id)
            .execute()
        )
        deleted_count = len(delete_response.data) if delete_response.data else 0

        # Insert new bboxes
        if bounding_boxes:
            # Add document_id and matter_id to each bbox
            rows = [
                {
                    **bbox,
                    "document_id": document_id,
                    "matter_id": matter_id,
                }
                for bbox in bounding_boxes
            ]
            insert_response = (
                self.client.table("bounding_boxes")
                .insert(rows)
                .execute()
            )
            inserted_count = len(insert_response.data) if insert_response.data else 0
        else:
            inserted_count = 0

        return {"deleted": deleted_count, "inserted": inserted_count}

    result = await asyncio.to_thread(_delete_and_insert)

    logger.info(
        "bounding_boxes_saved_idempotent",
        document_id=document_id,
        deleted=result["deleted"],
        inserted=result["inserted"],
    )

    return result
```

### Testing Requirements

```python
class TestIdempotentSave:
    @pytest.mark.asyncio
    async def test_deletes_existing_before_insert(self, mock_supabase):
        # Arrange - existing bboxes
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = [
            {"id": "old-1"}, {"id": "old-2"}
        ]

        service = BoundingBoxService()

        # Act
        result = await service.save_bounding_boxes_idempotent(
            document_id="doc-123",
            matter_id="matter-456",
            bounding_boxes=[{"page": 1, "text": "new"}],
        )

        # Assert
        assert result["deleted"] == 2
        mock_supabase.table.return_value.delete.assert_called()

    @pytest.mark.asyncio
    async def test_no_duplicates_on_reprocessing(self, mock_supabase):
        # Call twice with same document_id
        # Should have same final count
        pass
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.4] - Full AC

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

