# Story 17.7: Trigger Downstream RAG Re-Processing After OCR

Status: ready-for-dev

## Story

As a system ensuring RAG data consistency,
I want to automatically trigger chunk re-linking and embedding after large document OCR completes,
so that the RAG pipeline has correct bbox_ids for search highlighting.

## Acceptance Criteria

1. **Automatic Pipeline Trigger**
   - When large document OCR completes and document status is 'ocr_complete'
   - Existing `chunk_document` Celery task is triggered
   - Old chunks deleted before new chunks created
   - New chunks fuzzy-matched to new bounding boxes

2. **Memory-Bounded Matching**
   - When fuzzy matching runs against 10,000+ bounding boxes
   - bbox_linker processes in batches (500 bboxes at a time)
   - Memory usage stays bounded during matching
   - Matching completes within 30 seconds for 400 pages

3. **Embedding Generation**
   - After chunks re-linked, embedding task runs
   - Embeddings generated for child chunks
   - Chunks searchable via hybrid search
   - Search results include correct bbox_ids

4. **Existing Pipeline Integration (CRITICAL)**
   - Workflow continues normally: chunk_document → embed_document → extract_entities
   - No special handling needed - existing pipeline handles re-processing
   - Idempotent chunk save prevents duplicates

## Tasks / Subtasks

- [ ] Task 1: Trigger chunking after OCR merge (AC: #1, #4)
  - [ ] Call `chunk_document.delay()` after successful merge
  - [ ] Ensure document status is 'ocr_complete'
  - [ ] Pass job_id for tracking

- [ ] Task 2: Implement batched bbox matching (AC: #2)
  - [ ] Modify bbox_linker to process in batches
  - [ ] Batch size of 500 bboxes
  - [ ] Log progress during matching

- [ ] Task 3: Verify pipeline integration (AC: #3, #4)
  - [ ] Test full pipeline: OCR → chunk → embed → extract
  - [ ] Verify search returns correct bbox_ids
  - [ ] Test highlighting works with large documents

- [ ] Task 4: Write tests (AC: #1-4)
  - [ ] Test trigger after OCR completion
  - [ ] Test batched matching performance
  - [ ] Test end-to-end pipeline

## Dev Notes

### Architecture Compliance

**Pipeline Trigger Pattern:**
```python
# In document_tasks.py after merge

def _merge_and_store_results(
    document_id: str,
    matter_id: str,
    chunk_results: list[ChunkOCRResult],
    job_id: str | None,
) -> dict:
    """Merge chunk results and trigger downstream pipeline."""
    merger = get_ocr_result_merger()
    bbox_service = get_bounding_box_service()

    # Merge results
    merged = merger.merge_results(chunk_results, document_id)

    # Save bounding boxes (idempotent)
    _run_async(
        bbox_service.save_bounding_boxes_idempotent(
            document_id=document_id,
            matter_id=matter_id,
            bounding_boxes=merged.bounding_boxes,
        )
    )

    # Update document status
    _update_document_status(document_id, "ocr_complete")

    # Trigger downstream pipeline
    # This continues: chunk_document → embed_document → extract_entities
    chunk_document.delay(
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
    )

    logger.info(
        "downstream_pipeline_triggered",
        document_id=document_id,
        bbox_count=merged.total_bboxes,
    )

    return {
        "status": "success",
        "page_count": merged.page_count,
        "bbox_count": merged.total_bboxes,
    }
```

**Batched Bbox Linking:**
```python
# Modify backend/app/services/chunking/bbox_linker.py

BBOX_BATCH_SIZE = 500

def link_chunks_to_bboxes_batched(
    chunks: list[Chunk],
    bounding_boxes: list[BoundingBox],
    batch_size: int = BBOX_BATCH_SIZE,
) -> list[Chunk]:
    """Link chunks to bboxes with batched processing.

    Processes bboxes in batches to prevent memory issues
    with large documents (10,000+ bboxes).
    """
    total_bboxes = len(bounding_boxes)
    linked_chunks = []

    logger.info(
        "bbox_linking_start",
        chunk_count=len(chunks),
        bbox_count=total_bboxes,
        batch_size=batch_size,
    )

    for chunk in chunks:
        # Find matching bboxes for this chunk's text
        matched_ids = []

        # Process bboxes in batches
        for batch_start in range(0, total_bboxes, batch_size):
            batch_end = min(batch_start + batch_size, total_bboxes)
            bbox_batch = bounding_boxes[batch_start:batch_end]

            # Fuzzy match chunk text against batch
            batch_matches = _fuzzy_match_batch(chunk.text, bbox_batch)
            matched_ids.extend(batch_matches)

        chunk.bbox_ids = matched_ids[:10]  # Limit to 10 most relevant
        linked_chunks.append(chunk)

    logger.info(
        "bbox_linking_complete",
        chunks_linked=len(linked_chunks),
    )

    return linked_chunks
```

### Testing Requirements

```python
class TestDownstreamTrigger:
    @pytest.mark.asyncio
    async def test_triggers_chunking_after_ocr(self, mock_celery):
        # After merge completes, chunk_document should be called
        result = _merge_and_store_results(
            document_id="doc-123",
            matter_id="matter-456",
            chunk_results=[...],
            job_id="job-789",
        )

        mock_celery.delay.assert_called_with(
            document_id="doc-123",
            matter_id="matter-456",
            job_id="job-789",
        )


class TestBatchedBboxLinking:
    def test_processes_large_bbox_set_in_batches(self):
        # 10,000 bboxes should be processed in batches
        bboxes = [MagicMock(id=f"b{i}") for i in range(10000)]
        chunks = [MagicMock(text="sample text")]

        result = link_chunks_to_bboxes_batched(chunks, bboxes, batch_size=500)

        # Should complete without memory issues
        assert len(result) == 1
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.7] - Full AC

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

