# Story 17.8: Validate Entity Mention and Citation Bbox References

Status: ready-for-dev

## Story

As a system ensuring citation and entity highlighting works,
I want to validate that entity mentions and citations reference valid bounding boxes,
so that click-to-highlight features work correctly on large documents.

## Acceptance Criteria

1. **Entity Mention Validation**
   - After entity extraction, EntityMention.bbox_ids reference valid bounding_boxes records
   - EntityMention.page_number matches the bbox page numbers
   - Invalid references logged as warnings

2. **Citation Re-Linking**
   - For re-processed documents, source_bbox_ids are re-linked via text matching
   - target_bbox_ids (in Act documents) remain unchanged
   - Citations with invalid bbox references flagged for re-verification

3. **Chunk Bbox Validation**
   - GET /api/chunks/{chunk_id}/bboxes returns valid bounding_box records
   - Coordinates are valid for PDF viewer
   - page_number in bbox matches chunk's page_number

4. **Integrity Check**
   - After document processing, verify COUNT(chunk.bbox_ids) > 0 for all chunks
   - All bbox_ids in chunks exist in bounding_boxes table
   - Warning logged for chunks without bbox_ids

## Tasks / Subtasks

- [ ] Task 1: Create BboxReferenceValidator service (AC: #1, #2, #3, #4)
  - [ ] Validate entity mention references
  - [ ] Validate citation references
  - [ ] Validate chunk references
  - [ ] Run integrity checks

- [ ] Task 2: Integrate into processing pipeline (AC: #1, #2)
  - [ ] Call validation after entity extraction
  - [ ] Re-link citations after OCR reprocessing
  - [ ] Log all validation results

- [ ] Task 3: Add API validation (AC: #3)
  - [ ] Validate bbox_ids exist before returning
  - [ ] Return error for invalid references
  - [ ] Log invalid reference attempts

- [ ] Task 4: Write tests (AC: #1-4)
  - [ ] Test valid references pass
  - [ ] Test invalid references caught
  - [ ] Test re-linking logic

## Dev Notes

### Architecture Compliance

**Bbox Reference Validator:**
```python
# backend/app/services/bbox_reference_validator.py
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


class BboxReferenceValidator:
    """Validates that bbox references are valid across entities, citations, and chunks."""

    def __init__(self, supabase_client=None):
        self._client = supabase_client

    async def validate_entity_mentions(
        self,
        document_id: str,
    ) -> dict:
        """Validate all entity mentions have valid bbox_ids.

        Returns:
            {valid: int, invalid: int, orphan_mentions: list}
        """
        # Get all entity mentions for document
        mentions = await self._get_entity_mentions(document_id)
        valid_bbox_ids = await self._get_valid_bbox_ids(document_id)

        valid_count = 0
        invalid_count = 0
        orphan_mentions = []

        for mention in mentions:
            if not mention.get("bbox_ids"):
                orphan_mentions.append(mention["id"])
                continue

            bbox_ids = mention["bbox_ids"]
            if all(bid in valid_bbox_ids for bid in bbox_ids):
                valid_count += 1
            else:
                invalid_count += 1
                logger.warning(
                    "invalid_mention_bbox_ref",
                    mention_id=mention["id"],
                    bbox_ids=bbox_ids,
                )

        return {
            "valid": valid_count,
            "invalid": invalid_count,
            "orphan_mentions": orphan_mentions,
        }

    async def validate_chunk_references(
        self,
        document_id: str,
    ) -> dict:
        """Validate all chunks have valid bbox_ids.

        Returns:
            {valid: int, invalid: int, empty_chunks: list}
        """
        chunks = await self._get_chunks(document_id)
        valid_bbox_ids = await self._get_valid_bbox_ids(document_id)

        valid_count = 0
        invalid_count = 0
        empty_chunks = []

        for chunk in chunks:
            bbox_ids = chunk.get("bbox_ids", [])

            if not bbox_ids:
                empty_chunks.append(chunk["id"])
                logger.warning(
                    "chunk_without_bbox_ids",
                    chunk_id=chunk["id"],
                )
                continue

            if all(bid in valid_bbox_ids for bid in bbox_ids):
                valid_count += 1
            else:
                invalid_count += 1
                invalid_ids = [bid for bid in bbox_ids if bid not in valid_bbox_ids]
                logger.warning(
                    "invalid_chunk_bbox_ref",
                    chunk_id=chunk["id"],
                    invalid_bbox_ids=invalid_ids,
                )

        return {
            "valid": valid_count,
            "invalid": invalid_count,
            "empty_chunks": empty_chunks,
        }

    async def run_full_integrity_check(
        self,
        document_id: str,
    ) -> dict:
        """Run complete integrity check for a document.

        Returns:
            Combined results from all validations.
        """
        mention_results = await self.validate_entity_mentions(document_id)
        chunk_results = await self.validate_chunk_references(document_id)

        logger.info(
            "integrity_check_complete",
            document_id=document_id,
            mentions=mention_results,
            chunks=chunk_results,
        )

        return {
            "document_id": document_id,
            "entity_mentions": mention_results,
            "chunks": chunk_results,
            "is_healthy": (
                mention_results["invalid"] == 0 and
                chunk_results["invalid"] == 0
            ),
        }
```

### Testing Requirements

```python
class TestBboxReferenceValidator:
    @pytest.mark.asyncio
    async def test_detects_invalid_mention_references(self, mock_supabase):
        # Mention references bbox that doesn't exist
        mock_mentions = [
            {"id": "m1", "bbox_ids": ["valid-1", "invalid-999"]},
        ]
        mock_valid_bboxes = {"valid-1"}

        validator = BboxReferenceValidator(mock_supabase)
        result = await validator.validate_entity_mentions("doc-1")

        assert result["invalid"] == 1

    @pytest.mark.asyncio
    async def test_detects_empty_chunks(self, mock_supabase):
        mock_chunks = [
            {"id": "c1", "bbox_ids": []},  # Empty
            {"id": "c2", "bbox_ids": ["b1"]},
        ]

        validator = BboxReferenceValidator(mock_supabase)
        result = await validator.validate_chunk_references("doc-1")

        assert len(result["empty_chunks"]) == 1
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.8] - Full AC

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

