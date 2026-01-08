# Story 2B.5: Implement Parent-Child Chunking

Status: complete

## Story

As a **developer**,
I want **documents chunked with parent-child hierarchy**,
So that **semantic search returns relevant context while maintaining precision**.

## Acceptance Criteria

1. **Given** a document is processed **When** chunking begins **Then** parent chunks are created at 1500-2000 tokens preserving document structure (paragraphs, sections) **And** child chunks are created at 400-700 tokens with 50-100 token overlap

2. **Given** a child chunk is created **When** it is stored **Then** it links to its parent chunk via parent_chunk_id **And** it links to its source bounding_boxes

3. **Given** semantic search returns a child chunk **When** context is needed **Then** the parent chunk can be retrieved for expanded context **And** the UI can show surrounding text

4. **Given** a document has clear section headers **When** chunking is performed **Then** section boundaries are respected **And** chunks don't split mid-sentence when possible

## Tasks / Subtasks

- [ ] Task 1: Create Chunking Configuration (AC: #1)
  - [ ] Update `backend/app/core/config.py` with chunking settings
  - [ ] Add `CHUNK_PARENT_SIZE: int = 1750` (target: 1500-2000 tokens)
  - [ ] Add `CHUNK_PARENT_OVERLAP: int = 100` (5-7% overlap)
  - [ ] Add `CHUNK_CHILD_SIZE: int = 550` (target: 400-700 tokens)
  - [ ] Add `CHUNK_CHILD_OVERLAP: int = 75` (50-100 tokens, ~14%)
  - [ ] Add `CHUNK_MIN_SIZE: int = 100` (minimum viable chunk)

- [ ] Task 2: Create Token Counter Utility (AC: #1)
  - [ ] Create `backend/app/services/chunking/token_counter.py`
  - [ ] Implement `count_tokens(text: str, model: str = "cl100k_base") -> int` using tiktoken
  - [ ] Add tiktoken to backend dependencies
  - [ ] Cache tiktoken encoder for performance
  - [ ] Handle edge cases (empty text, special characters)

- [ ] Task 3: Create Text Splitter Service (AC: #1, #4)
  - [ ] Create `backend/app/services/chunking/text_splitter.py`
  - [ ] Implement recursive character text splitter pattern (LangChain-style)
  - [ ] Separators hierarchy: `["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]`
  - [ ] Implement `split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]`
  - [ ] Preserve sentence boundaries when possible
  - [ ] Handle edge cases: very long sentences, no separators

- [ ] Task 4: Create Parent-Child Chunker Service (AC: #1, #2, #4)
  - [ ] Create `backend/app/services/chunking/parent_child_chunker.py`
  - [ ] Implement `ParentChildChunker` class
  - [ ] Implement `chunk_document(document_id: str, text: str) -> ChunkingResult`
  - [ ] Create parent chunks first (1500-2000 tokens)
  - [ ] Create child chunks from each parent (400-700 tokens with overlap)
  - [ ] Track parent-child relationships
  - [ ] Assign chunk_index for ordering within document
  - [ ] Calculate token_count for each chunk

- [ ] Task 5: Create BoundingBox-to-Chunk Linker (AC: #2)
  - [ ] Create `backend/app/services/chunking/bbox_linker.py`
  - [ ] Implement `link_chunk_to_bboxes(chunk_text: str, document_id: str, page_number: int) -> list[uuid]`
  - [ ] Use fuzzy text matching to find bounding boxes containing chunk text
  - [ ] Handle text spanning multiple bounding boxes
  - [ ] Return ordered list of bbox_ids for the chunk

- [ ] Task 6: Create Chunk Models (AC: #1, #2)
  - [ ] Create `backend/app/models/chunk.py`
  - [ ] Define `ChunkCreate` model with all fields
  - [ ] Define `Chunk` model for database representation
  - [ ] Define `ChunkingResult` model with parent and child lists
  - [ ] Define `ChunkType` enum: 'parent', 'child'

- [ ] Task 7: Create Chunk Service for Database Operations (AC: #1, #2)
  - [ ] Create `backend/app/services/chunk_service.py`
  - [ ] Implement `save_chunks(chunks: list[ChunkCreate]) -> list[Chunk]`
  - [ ] Implement batch insert (100 chunks per insert for performance)
  - [ ] Implement `get_chunks_for_document(document_id: str) -> list[Chunk]`
  - [ ] Implement `get_parent_chunk(chunk_id: str) -> Chunk | None`
  - [ ] Implement `get_child_chunks(parent_id: str) -> list[Chunk]`

- [ ] Task 8: Integrate Chunking into Document Processing Pipeline (AC: #1, #2)
  - [ ] Update `backend/app/workers/tasks/document_tasks.py`
  - [ ] Add `chunk_document` Celery task
  - [ ] Chain: `process_document -> validate_ocr -> calculate_confidence -> chunk_document`
  - [ ] Use extracted_text from documents table as input
  - [ ] Update document status to "chunking" during processing
  - [ ] Update document status to "chunked" on completion

- [ ] Task 9: Create Chunk Retrieval API Endpoints (AC: #3)
  - [ ] Create `backend/app/api/routes/chunks.py`
  - [ ] `GET /api/documents/{document_id}/chunks` - Get all chunks for document
  - [ ] `GET /api/chunks/{chunk_id}` - Get single chunk with parent info
  - [ ] `GET /api/chunks/{chunk_id}/parent` - Get parent chunk
  - [ ] `GET /api/chunks/{chunk_id}/children` - Get child chunks
  - [ ] `GET /api/chunks/{chunk_id}/context` - Get chunk with surrounding context
  - [ ] Register router in `backend/app/main.py`

- [ ] Task 10: Create Frontend Chunk Types (AC: #3)
  - [ ] Update `frontend/src/types/document.ts`
  - [ ] Add `Chunk` interface with all fields
  - [ ] Add `ChunkType` type: 'parent' | 'child'
  - [ ] Add `ChunkListResponse` and `ChunkContextResponse` types

- [ ] Task 11: Create Frontend Chunk API Client (AC: #3)
  - [ ] Create `frontend/src/lib/api/chunks.ts`
  - [ ] Add `fetchChunksForDocument(documentId: string): Promise<Chunk[]>`
  - [ ] Add `fetchChunkWithContext(chunkId: string): Promise<ChunkContextResponse>`
  - [ ] Add `fetchParentChunk(chunkId: string): Promise<Chunk | null>`

- [ ] Task 12: Write Backend Unit Tests
  - [ ] Create `backend/tests/services/chunking/test_token_counter.py`
  - [ ] Create `backend/tests/services/chunking/test_text_splitter.py`
  - [ ] Create `backend/tests/services/chunking/test_parent_child_chunker.py`
  - [ ] Test token counting accuracy
  - [ ] Test chunk size boundaries (min/max)
  - [ ] Test sentence boundary preservation
  - [ ] Test parent-child relationship creation
  - [ ] Test chunk overlap calculation

- [ ] Task 13: Write Backend Integration Tests
  - [ ] Create `backend/tests/integration/test_chunking_pipeline.py`
  - [ ] Test full pipeline: OCR text -> chunking -> database
  - [ ] Test chunk retrieval API endpoints
  - [ ] Test parent-child navigation
  - [ ] Test bbox linking accuracy

## Dev Notes

### CRITICAL: Existing Infrastructure

**The chunks table ALREADY EXISTS** (created in Story 1-7 / Epic 1 foundation). This story is about **implementing the chunking service** that populates this table.

**Existing schema from `supabase/migrations/20260106000002_create_chunks_table.sql`:**
```sql
CREATE TABLE public.chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  parent_chunk_id uuid REFERENCES public.chunks(id) ON DELETE CASCADE,
  content text NOT NULL,
  embedding vector(1536),
  entity_ids uuid[],
  page_number integer,
  bbox_ids uuid[],
  token_count integer,
  chunk_type text CHECK (chunk_type IN ('parent', 'child')),
  created_at timestamptz DEFAULT now()
);
```

### Token Size Rationale (Architecture Compliance)

Per [architecture.md], the project mandates:
- **Parent chunks:** 1500-2000 tokens (provides broader context for LLM)
- **Child chunks:** 400-700 tokens (precise retrieval for semantic search)

**Why these sizes:**
1. **Child chunks (400-700 tokens):** Optimal for semantic search precision. Industry research shows 256-512 tokens provides best retrieval accuracy, but legal documents need slightly larger chunks to preserve clause context.
2. **Parent chunks (1500-2000 tokens):** When a child is retrieved, the parent provides expanded context without flooding the LLM context window.
3. **Overlap (50-100 tokens on children):** Ensures context straddling chunk boundaries is captured (~14% overlap).

### Chunking Algorithm (Recursive Character Splitting)

**Implementation pattern (LangChain-inspired):**

```python
# backend/app/services/chunking/text_splitter.py

from typing import Callable
import structlog

logger = structlog.get_logger(__name__)

SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]

class RecursiveTextSplitter:
    """
    Recursively splits text by trying separators in order.
    Preserves sentence/paragraph boundaries when possible.
    """

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        length_function: Callable[[str], int],
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function
        self.separators = separators or SEPARATORS

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks respecting size limits and separators."""
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursive splitting with separator hierarchy."""
        final_chunks: list[str] = []

        # Find the best separator for this text
        separator = separators[-1]  # Default to character split
        for sep in separators:
            if sep in text:
                separator = sep
                break

        # Split by separator
        splits = text.split(separator) if separator else list(text)

        # Merge splits into chunks
        current_chunk: list[str] = []
        current_length = 0

        for split in splits:
            split_length = self.length_function(split)

            # If single split exceeds chunk size, recursively split it
            if split_length > self.chunk_size:
                if current_chunk:
                    final_chunks.append(separator.join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Recurse with next separator level
                remaining_separators = separators[separators.index(separator) + 1:]
                if remaining_separators:
                    final_chunks.extend(self._split_text(split, remaining_separators))
                else:
                    # Force split at chunk_size if no more separators
                    final_chunks.extend(self._force_split(split))
                continue

            # Check if adding this split exceeds chunk size
            potential_length = current_length + split_length + (len(separator) if current_chunk else 0)

            if potential_length > self.chunk_size:
                if current_chunk:
                    final_chunks.append(separator.join(current_chunk))
                    # Apply overlap
                    overlap_chunks = self._get_overlap_chunks(current_chunk, separator)
                    current_chunk = overlap_chunks
                    current_length = self.length_function(separator.join(current_chunk))

            current_chunk.append(split)
            current_length = self.length_function(separator.join(current_chunk))

        if current_chunk:
            final_chunks.append(separator.join(current_chunk))

        return [chunk for chunk in final_chunks if chunk.strip()]

    def _get_overlap_chunks(self, chunks: list[str], separator: str) -> list[str]:
        """Get chunks that should be included in overlap."""
        overlap_text = ""
        overlap_chunks = []
        for chunk in reversed(chunks):
            test_text = separator.join([chunk] + overlap_chunks)
            if self.length_function(test_text) <= self.chunk_overlap:
                overlap_chunks.insert(0, chunk)
            else:
                break
        return overlap_chunks

    def _force_split(self, text: str) -> list[str]:
        """Force split text at exact chunk_size when no separators work."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        return chunks
```

### Parent-Child Chunker Implementation

```python
# backend/app/services/chunking/parent_child_chunker.py

from dataclasses import dataclass
from uuid import UUID, uuid4
import structlog

from app.core.config import get_settings
from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.token_counter import count_tokens

logger = structlog.get_logger(__name__)

@dataclass
class ChunkData:
    """Internal representation of a chunk before database insertion."""
    id: UUID
    content: str
    chunk_type: str  # 'parent' or 'child'
    chunk_index: int
    parent_id: UUID | None
    token_count: int
    page_number: int | None
    bbox_ids: list[UUID] | None


@dataclass
class ChunkingResult:
    """Result of chunking a document."""
    document_id: str
    parent_chunks: list[ChunkData]
    child_chunks: list[ChunkData]
    total_tokens: int


class ParentChildChunker:
    """
    Two-level hierarchical chunker for RAG retrieval.

    Creates parent chunks (1500-2000 tokens) for context,
    and child chunks (400-700 tokens) for precise retrieval.
    """

    def __init__(self):
        settings = get_settings()
        self.parent_size = settings.chunk_parent_size
        self.parent_overlap = settings.chunk_parent_overlap
        self.child_size = settings.chunk_child_size
        self.child_overlap = settings.chunk_child_overlap
        self.min_size = settings.chunk_min_size

        self.parent_splitter = RecursiveTextSplitter(
            chunk_size=self.parent_size,
            chunk_overlap=self.parent_overlap,
            length_function=count_tokens,
        )

        self.child_splitter = RecursiveTextSplitter(
            chunk_size=self.child_size,
            chunk_overlap=self.child_overlap,
            length_function=count_tokens,
        )

    def chunk_document(self, document_id: str, text: str) -> ChunkingResult:
        """
        Chunk a document into parent-child hierarchy.

        Args:
            document_id: UUID of the source document
            text: Extracted text from OCR

        Returns:
            ChunkingResult with parent and child chunks
        """
        logger.info("chunking_document_start", document_id=document_id, text_length=len(text))

        # Step 1: Create parent chunks
        parent_texts = self.parent_splitter.split_text(text)
        parent_chunks: list[ChunkData] = []

        for idx, parent_text in enumerate(parent_texts):
            token_count = count_tokens(parent_text)
            if token_count < self.min_size:
                logger.debug("skipping_small_parent", index=idx, tokens=token_count)
                continue

            parent_chunks.append(ChunkData(
                id=uuid4(),
                content=parent_text,
                chunk_type="parent",
                chunk_index=idx,
                parent_id=None,
                token_count=token_count,
                page_number=None,  # Determined during bbox linking
                bbox_ids=None,
            ))

        # Step 2: Create child chunks from each parent
        child_chunks: list[ChunkData] = []
        child_index = 0

        for parent in parent_chunks:
            child_texts = self.child_splitter.split_text(parent.content)

            for child_text in child_texts:
                token_count = count_tokens(child_text)
                if token_count < self.min_size:
                    continue

                child_chunks.append(ChunkData(
                    id=uuid4(),
                    content=child_text,
                    chunk_type="child",
                    chunk_index=child_index,
                    parent_id=parent.id,
                    token_count=token_count,
                    page_number=None,
                    bbox_ids=None,
                ))
                child_index += 1

        total_tokens = sum(c.token_count for c in parent_chunks) + sum(c.token_count for c in child_chunks)

        logger.info(
            "chunking_document_complete",
            document_id=document_id,
            parent_count=len(parent_chunks),
            child_count=len(child_chunks),
            total_tokens=total_tokens,
        )

        return ChunkingResult(
            document_id=document_id,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            total_tokens=total_tokens,
        )
```

### Token Counting with tiktoken

```python
# backend/app/services/chunking/token_counter.py

import tiktoken
from functools import lru_cache

@lru_cache(maxsize=1)
def get_encoder(encoding_name: str = "cl100k_base"):
    """Get cached tiktoken encoder."""
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        encoding_name: tiktoken encoding (cl100k_base for GPT-4/embeddings)

    Returns:
        Number of tokens
    """
    if not text:
        return 0

    encoder = get_encoder(encoding_name)
    return len(encoder.encode(text))
```

### BoundingBox Linking Strategy

Linking chunks to bounding boxes enables click-to-highlight in the PDF viewer:

```python
# backend/app/services/chunking/bbox_linker.py

from uuid import UUID
from rapidfuzz import fuzz
import structlog

from app.services.bounding_box_service import BoundingBoxService

logger = structlog.get_logger(__name__)

# Threshold for fuzzy text matching (0-100)
MATCH_THRESHOLD = 80


async def link_chunk_to_bboxes(
    chunk_text: str,
    document_id: str,
    bbox_service: BoundingBoxService,
) -> tuple[list[UUID], int | None]:
    """
    Find bounding boxes that contain the chunk's text.

    Uses fuzzy matching to handle OCR artifacts and minor text differences.

    Returns:
        Tuple of (list of bbox_ids, most common page_number)
    """
    # Get all bounding boxes for document, ordered by reading order
    all_bboxes = await bbox_service.get_bounding_boxes_for_document(document_id)

    if not all_bboxes:
        return [], None

    # Normalize chunk text for matching
    chunk_words = chunk_text.lower().split()
    matched_bbox_ids: list[UUID] = []
    page_counts: dict[int, int] = {}

    # Sliding window over bounding boxes to find text matches
    window_size = min(50, len(all_bboxes))  # Look at groups of bboxes

    for i in range(len(all_bboxes) - window_size + 1):
        window_bboxes = all_bboxes[i:i + window_size]
        window_text = " ".join(b["text_content"].lower() for b in window_bboxes)

        # Check if chunk text appears in this window
        match_score = fuzz.partial_ratio(chunk_text.lower()[:500], window_text[:1000])

        if match_score >= MATCH_THRESHOLD:
            # Find specific bboxes that contain chunk words
            for bbox in window_bboxes:
                bbox_text = bbox["text_content"].lower()
                for word in chunk_words[:20]:  # Check first 20 words
                    if word in bbox_text and bbox["id"] not in matched_bbox_ids:
                        matched_bbox_ids.append(UUID(bbox["id"]))
                        page = bbox["page_number"]
                        page_counts[page] = page_counts.get(page, 0) + 1

            if matched_bbox_ids:
                break  # Found a match, don't need to continue

    # Determine most common page
    most_common_page = max(page_counts, key=page_counts.get) if page_counts else None

    logger.debug(
        "bbox_linking_complete",
        document_id=document_id,
        bbox_count=len(matched_bbox_ids),
        page=most_common_page,
    )

    return matched_bbox_ids, most_common_page
```

### Celery Task Integration

```python
# Addition to backend/app/workers/tasks/document_tasks.py

@celery_app.task(bind=True, max_retries=3)
def chunk_document(self, document_id: str) -> dict:
    """
    Chunk a document into parent-child hierarchy.

    Called after OCR validation and confidence calculation.
    """
    from app.services.chunking.parent_child_chunker import ParentChildChunker
    from app.services.chunking.bbox_linker import link_chunk_to_bboxes
    from app.services.chunk_service import ChunkService
    from app.services.document_service import DocumentService
    from app.services.bounding_box_service import BoundingBoxService

    logger.info("chunk_document_task_start", document_id=document_id)

    try:
        # Update status
        doc_service = DocumentService()
        doc = await doc_service.get_document(document_id)

        if not doc or not doc.extracted_text:
            raise ValueError(f"Document {document_id} has no extracted text")

        await doc_service.update_status(document_id, "chunking")

        # Chunk the document
        chunker = ParentChildChunker()
        result = chunker.chunk_document(document_id, doc.extracted_text)

        # Link bounding boxes to chunks
        bbox_service = BoundingBoxService()
        for chunk in result.parent_chunks + result.child_chunks:
            bbox_ids, page_number = await link_chunk_to_bboxes(
                chunk.content,
                document_id,
                bbox_service,
            )
            chunk.bbox_ids = bbox_ids
            chunk.page_number = page_number

        # Save chunks to database
        chunk_service = ChunkService()
        await chunk_service.save_chunks(
            document_id=document_id,
            matter_id=doc.matter_id,
            parent_chunks=result.parent_chunks,
            child_chunks=result.child_chunks,
        )

        # Update document status
        await doc_service.update_status(document_id, "chunked")

        logger.info(
            "chunk_document_task_complete",
            document_id=document_id,
            parent_count=len(result.parent_chunks),
            child_count=len(result.child_chunks),
        )

        return {
            "document_id": document_id,
            "status": "chunked",
            "parent_count": len(result.parent_chunks),
            "child_count": len(result.child_chunks),
        }

    except Exception as e:
        logger.error("chunk_document_task_error", document_id=document_id, error=str(e))
        raise self.retry(exc=e)
```

### Previous Story Intelligence

**FROM Story 2b-1 (Google Document AI OCR):**
- `extracted_text` column on documents table contains OCR output
- `BoundingBoxService` provides bbox retrieval methods
- Celery task chain pattern: `process_document -> validate_ocr`
- structlog logging throughout

**FROM Story 2b-4 (Bounding Boxes Table Enhancement):**
- `reading_order_index` column enables ordered bbox retrieval
- `get_bounding_boxes_for_document()` returns ordered list
- `chunk_bbox_linker.py` exists but links chunks TO bboxes (we need inverse)
- BBox API endpoints available for chunk-bbox queries

**Key files to reference:**
- `backend/app/services/bounding_box_service.py` - Bbox retrieval methods
- `backend/app/services/chunk_bbox_linker.py` - Existing linking pattern
- `backend/app/workers/tasks/document_tasks.py` - Task chain pattern
- `supabase/migrations/20260106000002_create_chunks_table.sql` - Schema

### Git Intelligence

Recent commits:
```
d0ca6da fix(bbox): address code review issues for Story 2b-4
18427f4 feat(ocr): implement bounding boxes table enhancement (Story 2b-4)
79d15ca fix(ocr): address code review issues for Story 2b-3
1cd9607 feat(ocr): implement OCR quality assessment display (Story 2b-3)
```

**Recommended commit message:** `feat(chunking): implement parent-child chunking for RAG pipeline (Story 2b-5)`

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **Celery + Redis** - for background tasks

#### Matter Isolation (4-Layer Enforcement)
```python
# Layer 1: RLS on chunks table (already in migration)
# Layer 2: Vector namespace prefix (embeddings - Story 2b-6)
# Layer 3: Redis key prefix (for caching)
redis_key = f"matter:{matter_id}:document:{document_id}:chunks"
# Layer 4: API middleware validates matter access
```

#### API Response Format (MANDATORY)
```python
# Success - chunk list
{
  "data": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "chunk_type": "child",
      "content": "...",
      "token_count": 520,
      "parent_chunk_id": "uuid"
    }
  ],
  "meta": { "total": 45, "parent_count": 8, "child_count": 37 }
}

# Success - chunk with context
{
  "data": {
    "chunk": { ... },
    "parent": { ... },
    "siblings": [ ... ]
  }
}

# Error
{ "error": { "code": "DOCUMENT_NOT_CHUNKED", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database columns | snake_case | `parent_chunk_id`, `chunk_type` |
| TypeScript variables | camelCase | `parentChunkId`, `chunkType` |
| Python functions | snake_case | `chunk_document`, `count_tokens` |
| Python classes | PascalCase | `ParentChildChunker`, `ChunkService` |
| API endpoints | kebab-case | `/chunks`, `/chunks/{id}/context` |

### File Organization

```
backend/app/
├── services/
│   ├── chunking/                           (NEW)
│   │   ├── __init__.py                     (NEW)
│   │   ├── token_counter.py                (NEW) - tiktoken wrapper
│   │   ├── text_splitter.py                (NEW) - Recursive text splitter
│   │   ├── parent_child_chunker.py         (NEW) - Main chunker class
│   │   └── bbox_linker.py                  (NEW) - Chunk-to-bbox linking
│   ├── chunk_service.py                    (NEW) - Database operations
│   └── chunk_bbox_linker.py                (EXISTS) - From Story 2b-4
├── models/
│   └── chunk.py                            (NEW) - Pydantic models
├── workers/
│   └── tasks/
│       └── document_tasks.py               (UPDATE) - Add chunk_document task
└── api/
    └── routes/
        ├── __init__.py                     (UPDATE) - Register chunks router
        └── chunks.py                       (NEW) - Chunk API endpoints

frontend/src/
├── types/
│   └── document.ts                         (UPDATE) - Add Chunk types
└── lib/
    └── api/
        └── chunks.ts                       (NEW) - Chunk API client

backend/tests/
├── services/
│   └── chunking/
│       ├── __init__.py                     (NEW)
│       ├── test_token_counter.py           (NEW)
│       ├── test_text_splitter.py           (NEW)
│       └── test_parent_child_chunker.py    (NEW)
└── integration/
    └── test_chunking_pipeline.py           (NEW)
```

### Testing Guidance

#### Unit Tests

```python
# backend/tests/services/chunking/test_text_splitter.py

import pytest
from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.token_counter import count_tokens


def test_splits_at_paragraph_boundaries():
    """Test that text is split at paragraph breaks first."""
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."

    splitter = RecursiveTextSplitter(
        chunk_size=20,
        chunk_overlap=5,
        length_function=count_tokens,
    )

    chunks = splitter.split_text(text)

    assert len(chunks) == 3
    assert "First paragraph" in chunks[0]
    assert "Second paragraph" in chunks[1]
    assert "Third paragraph" in chunks[2]


def test_respects_sentence_boundaries():
    """Test that sentences aren't split mid-word."""
    text = "This is a sentence. This is another sentence. This is a third sentence."

    splitter = RecursiveTextSplitter(
        chunk_size=15,
        chunk_overlap=3,
        length_function=count_tokens,
    )

    chunks = splitter.split_text(text)

    # Each chunk should end with a complete sentence
    for chunk in chunks:
        assert chunk.endswith(".") or chunk.endswith(". ")


def test_chunk_size_limits():
    """Test that chunks don't exceed size limits."""
    text = "Word " * 500  # 500 words

    splitter = RecursiveTextSplitter(
        chunk_size=100,
        chunk_overlap=10,
        length_function=count_tokens,
    )

    chunks = splitter.split_text(text)

    for chunk in chunks:
        assert count_tokens(chunk) <= 100


def test_overlap_present():
    """Test that chunks have proper overlap."""
    text = "Word " * 200

    splitter = RecursiveTextSplitter(
        chunk_size=50,
        chunk_overlap=10,
        length_function=count_tokens,
    )

    chunks = splitter.split_text(text)

    # Check adjacent chunks have overlapping content
    for i in range(len(chunks) - 1):
        # Last words of chunk i should appear in chunk i+1
        last_words = chunks[i].split()[-5:]
        first_words = chunks[i + 1].split()[:10]

        # At least some overlap should exist
        overlap = set(last_words) & set(first_words)
        assert len(overlap) > 0


# backend/tests/services/chunking/test_parent_child_chunker.py

import pytest
from app.services.chunking.parent_child_chunker import ParentChildChunker


def test_creates_parent_and_child_chunks():
    """Test that chunker creates both parent and child chunks."""
    text = "Legal document content. " * 500  # Large enough for multiple chunks

    chunker = ParentChildChunker()
    result = chunker.chunk_document("doc-123", text)

    assert len(result.parent_chunks) > 0
    assert len(result.child_chunks) > 0
    assert len(result.child_chunks) > len(result.parent_chunks)  # More children


def test_child_chunks_reference_parents():
    """Test that all child chunks have valid parent references."""
    text = "Legal document content. " * 500

    chunker = ParentChildChunker()
    result = chunker.chunk_document("doc-123", text)

    parent_ids = {p.id for p in result.parent_chunks}

    for child in result.child_chunks:
        assert child.parent_id is not None
        assert child.parent_id in parent_ids


def test_parent_chunk_size_range():
    """Test parent chunks are in 1500-2000 token range."""
    text = "Legal document content with more words. " * 1000

    chunker = ParentChildChunker()
    result = chunker.chunk_document("doc-123", text)

    for parent in result.parent_chunks:
        # Allow some flexibility around boundaries
        assert 1400 <= parent.token_count <= 2100, f"Parent token count: {parent.token_count}"


def test_child_chunk_size_range():
    """Test child chunks are in 400-700 token range."""
    text = "Legal document content. " * 1000

    chunker = ParentChildChunker()
    result = chunker.chunk_document("doc-123", text)

    for child in result.child_chunks:
        # Allow some flexibility
        assert 350 <= child.token_count <= 750, f"Child token count: {child.token_count}"


def test_chunk_index_ordering():
    """Test chunk indices are sequential."""
    text = "Legal document content. " * 500

    chunker = ParentChildChunker()
    result = chunker.chunk_document("doc-123", text)

    parent_indices = [p.chunk_index for p in result.parent_chunks]
    assert parent_indices == list(range(len(parent_indices)))

    child_indices = [c.chunk_index for c in result.child_chunks]
    assert child_indices == list(range(len(child_indices)))
```

#### Integration Tests

```python
# backend/tests/integration/test_chunking_pipeline.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_document_chunking_pipeline(
    test_client: AsyncClient,
    test_document_with_ocr: Document,
    auth_headers: dict
):
    """Test full document → chunks pipeline."""
    # Trigger chunking (or verify it's automatic after OCR)
    # ...

    # Verify chunks created
    response = await test_client.get(
        f"/api/documents/{test_document_with_ocr.id}/chunks",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_chunk_context_retrieval(
    test_client: AsyncClient,
    test_chunk_with_parent: Chunk,
    auth_headers: dict
):
    """Test retrieving chunk with parent context."""
    response = await test_client.get(
        f"/api/chunks/{test_chunk_with_parent.id}/context",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert "chunk" in data
    assert "parent" in data
    assert data["parent"]["id"] == str(test_chunk_with_parent.parent_chunk_id)
```

### Anti-Patterns to AVOID

```python
# WRONG: Fixed character-based splitting
chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]

# CORRECT: Token-based with semantic boundaries
chunks = splitter.split_text(text)

# WRONG: No overlap between chunks
splitter = RecursiveTextSplitter(chunk_size=500, chunk_overlap=0, ...)

# CORRECT: Always have overlap for context continuity
splitter = RecursiveTextSplitter(chunk_size=500, chunk_overlap=75, ...)

# WRONG: Creating orphan children without parents
child_chunk = ChunkData(parent_id=None, chunk_type="child", ...)

# CORRECT: Always link children to parents
child_chunk = ChunkData(parent_id=parent.id, chunk_type="child", ...)

# WRONG: Not validating matter access on chunk retrieval
async def get_chunks(document_id: str):
    return await db.table("chunks").select("*").eq("document_id", document_id).execute()

# CORRECT: Validate via document's matter (RLS handles this)
async def get_chunks(document_id: str, current_user: User):
    doc = await validate_document_access(document_id, current_user.id)
    return await db.table("chunks").select("*").eq("document_id", document_id).execute()

# WRONG: Using standard logging
import logging
logger = logging.getLogger(__name__)

# CORRECT: Use structlog
import structlog
logger = structlog.get_logger(__name__)

# WRONG: Counting tokens with len()
token_count = len(text.split())

# CORRECT: Use tiktoken for accurate token counts
token_count = count_tokens(text)
```

### Performance Considerations

- **Batch chunk inserts:** Insert chunks in batches of 100 to avoid timeouts
- **Token counting cache:** tiktoken encoder is cached for performance
- **Bbox linking optimization:** Use fuzzy matching with early exit on match
- **Index utilization:** `idx_chunks_document_id` enables fast document-scoped queries
- **Parent retrieval:** `idx_chunks_parent_id` enables fast parent-child navigation
- **Pre-warm HNSW:** After embeddings are added (Story 2b-6), pre-warm the index

### Dependencies to Add

```bash
# backend/
uv add tiktoken          # Token counting
uv add rapidfuzz         # Fuzzy text matching for bbox linking
```

### Environment Variables Required

No new environment variables required. Uses existing configuration in `backend/app/core/config.py`.

### Manual Steps Required After Implementation

#### Migrations
- No new migrations needed - chunks table exists

#### Dependencies
- [ ] Run: `uv add tiktoken rapidfuzz`

#### Manual Tests
- [ ] Upload a document and verify chunking completes after OCR
- [ ] Check document status transitions: ... → chunking → chunked
- [ ] Verify parent chunks are 1500-2000 tokens
- [ ] Verify child chunks are 400-700 tokens with overlap
- [ ] Call `/api/documents/{id}/chunks` and verify response
- [ ] Call `/api/chunks/{id}/context` and verify parent is included
- [ ] Verify bbox_ids are populated on chunks

### Downstream Dependencies

This story enables:
- **Story 2b-6 (Hybrid Search):** Chunks need embeddings for semantic search
- **Story 2b-7 (Cohere Rerank):** Reranking operates on retrieved chunks
- **Epic 2C (Entity Extraction):** Entity linking uses chunks
- **Epic 3 (Citation Engine):** Citation verification references chunks
- **Epic 11 (Q&A Panel):** Q&A retrieval returns chunks with context

### Project Structure Notes

- Chunks table already exists with full schema including parent_chunk_id
- Embeddings column exists but will be populated in Story 2b-6
- Entity_ids column exists but will be populated in Epic 2C
- RLS policies already configured for matter isolation

### References

- [Source: _bmad-output/architecture.md#Parent-Child-Chunking] - Token size requirements
- [Source: _bmad-output/project-context.md#Testing-Rules] - Testing patterns
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-2.7] - Acceptance criteria
- [Source: supabase/migrations/20260106000002_create_chunks_table.sql] - Existing schema
- [Source: _bmad-output/implementation-artifacts/2b-1-google-document-ai-ocr.md] - OCR patterns
- [Source: _bmad-output/implementation-artifacts/2b-4-bounding-boxes-table.md] - Bbox linking patterns
- [Source: https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025] - 2025 chunking best practices
- [Source: https://medium.com/@seahorse.technologies.sl/parent-child-chunking-in-langchain-for-advanced-rag-e7c37171995a] - LangChain parent-child pattern
- [Source: https://weaviate.io/blog/chunking-strategies-for-rag] - Chunking strategies overview

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

