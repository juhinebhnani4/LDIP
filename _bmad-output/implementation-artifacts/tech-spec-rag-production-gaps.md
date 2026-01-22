# Tech-Spec: RAG Production Gaps - Table Extraction, Evaluation Framework, Inspector Mode

**Created:** 2026-01-22
**Status:** Ready for Development
**Baseline Commit:** `bbe6d77d3dc1c79cf600e34ac05278a7ac55b95f`

---

## Overview

### Problem Statement

LDIP's RAG implementation is ~60% production-grade with strong foundations in chunking, hybrid search, and reranking. Three critical gaps remain:

1. **Table Extraction** - Legal documents contain critical tables (balance sheets, fee schedules, timelines) that are currently flattened to text, losing structure and reducing retrieval accuracy.

2. **Evaluation Framework** - No way to measure retrieval quality improvements. Cannot track Context Recall, Faithfulness, or Answer Relevancy metrics.

3. **Inspector/Debug Mode** - Reranker scores exist in API responses but no UI to visualize them. Developers cannot debug search quality issues.

### Solution

Implement three integrated features:

1. **Docling-based Table Extraction** - Extract tables during ingestion, convert to Markdown, store with chunk linkage
2. **RAGAS Evaluation Framework** - Automated + manual evaluation with golden dataset support
3. **Inspector Mode UI** - Debug toggle in chat + dedicated admin page showing all search scores

### Scope

**In Scope:**
- Docling integration for PDF table extraction
- Table-to-Markdown conversion with metadata
- RAGAS metrics: Context Recall, Faithfulness, Answer Relevancy
- Golden dataset creation and management
- Debug toggle showing scores inline in chat
- Admin inspector page with detailed analysis
- Matter-isolated evaluation data

**Out of Scope:**
- LlamaParse (deferred - cloud dependency)
- Real-time evaluation during chat (too slow)
- Excel/CSV table export (Phase 2)
- Historical evaluation comparison dashboards

---

## Context for Development

### Codebase Patterns

**Service Pattern (follow exactly):**
```python
# backend/app/services/{service_name}/service.py
from functools import lru_cache
import structlog
from app.core.circuit_breaker import with_circuit_breaker, CircuitService

logger = structlog.get_logger(__name__)

class MyService:
    def __init__(self) -> None:
        self._client = None

    async def process(self, matter_id: str, ...) -> Result:
        logger.info("process_start", matter_id=matter_id)
        try:
            result = await self._do_work(...)
            logger.info("process_complete", matter_id=matter_id, count=len(result))
            return result
        except ExternalAPIError as e:
            logger.warning("process_fallback", error=str(e))
            return self._fallback_result()

@lru_cache(maxsize=1)
def get_my_service() -> MyService:
    return MyService()
```

**API Route Pattern:**
```python
# backend/app/api/routes/{feature}.py
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import require_matter_role, MatterRole

router = APIRouter(prefix="/matters/{matter_id}/{feature}", tags=["{feature}"])

@router.post("", response_model=FeatureResponse)
async def endpoint(
    matter_id: str,
    body: FeatureRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    service: MyService = Depends(get_my_service),
) -> FeatureResponse:
    result = await service.process(matter_id, body)
    return FeatureResponse(data=result)
```

**Frontend Component Pattern:**
```typescript
// frontend/src/components/features/{feature}/FeatureComponent.tsx
'use client';
import { useState } from 'react';
import { useFeatureStore } from '@/stores/featureStore';

export function FeatureComponent({ matterId }: { matterId: string }) {
  const data = useFeatureStore((state) => state.data);  // Selector pattern
  const setData = useFeatureStore((state) => state.setData);

  return <div>...</div>;
}
```

### Files to Reference

| Purpose | File | Lines |
|---------|------|-------|
| Hybrid Search Service | `backend/app/services/rag/hybrid_search.py` | Follow structure |
| Reranker Service | `backend/app/services/rag/reranker.py` | Circuit breaker pattern |
| Search API Routes | `backend/app/api/routes/search.py` | Auth + response format |
| OCR Processor | `backend/app/services/ocr/processor.py` | External API pattern |
| Parent-Child Chunker | `backend/app/services/chunking/parent_child_chunker.py` | Chunk linkage |
| Search Models | `backend/app/models/search.py` | Response models |
| Q&A Panel | `frontend/src/components/features/chat/QAPanel.tsx` | Zustand usage |
| Engine Trace | `frontend/src/components/features/chat/EngineTrace.tsx` | Debug display |

### Technical Decisions

1. **Docling over LlamaParse** - Open-source, no per-page cost, self-hosted, good accuracy
2. **RAGAS over DeepEval** - Better community support, cleaner API, established metrics
3. **Inline toggle + admin page** - Maximum flexibility for debugging
4. **Celery for evaluation** - Async processing, doesn't block ingestion
5. **PostgreSQL for golden dataset** - Already have Supabase, no new infra

---

## Feature 1: Table Extraction Pipeline (Docling)

### Overview

Integrate Docling to extract tables from legal PDFs during ingestion, convert to Markdown format, and link to parent chunks for retrieval.

### Implementation Plan

#### Task 1.1: Add Docling Dependencies

**File:** `backend/pyproject.toml`

```toml
# Add to [tool.poetry.dependencies]
docling = "^2.0.0"
docling-core = "^2.0.0"
pandas = "^2.0.0"  # For table manipulation
```

**Acceptance Criteria:**
- [ ] Dependencies install without conflicts
- [ ] `from docling.document_converter import DocumentConverter` works

#### Task 1.2: Create Table Extractor Service

**Files to create:**
- `backend/app/services/table_extraction/__init__.py`
- `backend/app/services/table_extraction/extractor.py`
- `backend/app/services/table_extraction/models.py`
- `backend/app/services/table_extraction/formatter.py`

**extractor.py:**
```python
"""Table extraction service using Docling.

Extracts tables from PDF documents, converts to Markdown,
and links to parent chunks for retrieval.
"""

import structlog
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from functools import lru_cache
from pathlib import Path

from app.services.table_extraction.models import ExtractedTable, TableExtractionResult
from app.services.table_extraction.formatter import TableFormatter

logger = structlog.get_logger(__name__)


class TableExtractor:
    """Extract tables from documents using Docling."""

    def __init__(self) -> None:
        self._converter = None
        self._formatter = TableFormatter()

    @property
    def converter(self) -> DocumentConverter:
        """Lazy-load Docling converter."""
        if self._converter is None:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_table_structure = True
            pipeline_options.do_ocr = False  # We use Document AI for OCR

            self._converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                pdf_pipeline_options=pipeline_options,
            )
            logger.info("table_extractor_initialized")
        return self._converter

    async def extract_tables(
        self,
        file_path: Path,
        matter_id: str,
        document_id: str,
    ) -> TableExtractionResult:
        """Extract all tables from a document.

        Args:
            file_path: Path to PDF file
            matter_id: Matter UUID for isolation
            document_id: Document UUID for linkage

        Returns:
            TableExtractionResult with all extracted tables
        """
        logger.info(
            "table_extraction_start",
            matter_id=matter_id,
            document_id=document_id,
            file_path=str(file_path),
        )

        try:
            # Convert document
            result = self.converter.convert(str(file_path))
            doc = result.document

            tables: list[ExtractedTable] = []

            for idx, table in enumerate(doc.tables):
                # Convert to Markdown
                markdown = self._formatter.to_markdown(table)

                # Extract metadata
                extracted = ExtractedTable(
                    table_index=idx,
                    page_number=table.prov[0].page_no if table.prov else None,
                    markdown_content=markdown,
                    row_count=len(table.data),
                    col_count=len(table.data[0]) if table.data else 0,
                    confidence=table.score if hasattr(table, 'score') else 0.9,
                    bounding_box=self._extract_bbox(table),
                )
                tables.append(extracted)

            logger.info(
                "table_extraction_complete",
                matter_id=matter_id,
                document_id=document_id,
                table_count=len(tables),
            )

            return TableExtractionResult(
                document_id=document_id,
                matter_id=matter_id,
                tables=tables,
                total_tables=len(tables),
            )

        except Exception as e:
            logger.error(
                "table_extraction_failed",
                matter_id=matter_id,
                document_id=document_id,
                error=str(e),
            )
            # Return empty result - don't fail ingestion
            return TableExtractionResult(
                document_id=document_id,
                matter_id=matter_id,
                tables=[],
                total_tables=0,
                error=str(e),
            )

    def _extract_bbox(self, table) -> dict | None:
        """Extract bounding box from table provenance."""
        if not table.prov:
            return None
        prov = table.prov[0]
        return {
            "page": prov.page_no,
            "x": prov.bbox.l,
            "y": prov.bbox.t,
            "width": prov.bbox.r - prov.bbox.l,
            "height": prov.bbox.b - prov.bbox.t,
        }


@lru_cache(maxsize=1)
def get_table_extractor() -> TableExtractor:
    """Get singleton table extractor instance."""
    return TableExtractor()
```

**models.py:**
```python
"""Table extraction data models."""

from pydantic import BaseModel, Field


class ExtractedTable(BaseModel):
    """A single extracted table."""

    table_index: int = Field(..., description="Index of table in document")
    page_number: int | None = Field(None, description="Page where table appears")
    markdown_content: str = Field(..., description="Table in Markdown format")
    row_count: int = Field(..., ge=0)
    col_count: int = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: dict | None = Field(None, description="Location in document")


class TableExtractionResult(BaseModel):
    """Result of table extraction for a document."""

    document_id: str
    matter_id: str
    tables: list[ExtractedTable] = Field(default_factory=list)
    total_tables: int = Field(default=0)
    error: str | None = None
```

**formatter.py:**
```python
"""Table formatting utilities."""

from docling.datamodel.document import Table


class TableFormatter:
    """Convert tables to various formats."""

    def to_markdown(self, table: Table) -> str:
        """Convert Docling table to Markdown format.

        Args:
            table: Docling Table object

        Returns:
            Markdown-formatted table string
        """
        if not table.data:
            return ""

        rows = table.data
        if not rows:
            return ""

        # Build header
        header = rows[0]
        md_lines = [
            "| " + " | ".join(str(cell) for cell in header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]

        # Build body
        for row in rows[1:]:
            md_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(md_lines)

    def to_json(self, table: Table) -> list[dict]:
        """Convert Docling table to JSON format (list of row dicts)."""
        if not table.data or len(table.data) < 2:
            return []

        headers = [str(h) for h in table.data[0]]
        return [
            dict(zip(headers, [str(c) for c in row]))
            for row in table.data[1:]
        ]
```

**Acceptance Criteria:**
- [ ] TableExtractor initializes Docling converter lazily
- [ ] extract_tables() returns TableExtractionResult with all tables
- [ ] Tables are converted to valid Markdown format
- [ ] Bounding boxes are extracted for citation highlighting
- [ ] Errors don't fail ingestion - return empty result
- [ ] Structured logging with matter_id context

#### Task 1.3: Integrate with Ingestion Pipeline

**File:** `backend/app/workers/tasks/document_tasks.py`

Add table extraction step after OCR, before chunking:

```python
# In process_document task, after OCR step:

from app.services.table_extraction.extractor import get_table_extractor

# ... existing OCR code ...

# Step: Extract tables
table_extractor = get_table_extractor()
table_result = await table_extractor.extract_tables(
    file_path=file_path,
    matter_id=matter_id,
    document_id=document_id,
)

# Store tables in database
if table_result.tables:
    await store_extracted_tables(table_result)

# Include table markdown in text for chunking
text_with_tables = combine_text_and_tables(ocr_text, table_result.tables)
```

**Acceptance Criteria:**
- [ ] Table extraction runs after OCR in pipeline
- [ ] Tables stored in `document_tables` table
- [ ] Table Markdown appended to document text before chunking
- [ ] Pipeline doesn't fail if table extraction fails

#### Task 1.4: Create Database Schema

**File:** `backend/supabase/migrations/YYYYMMDD_add_document_tables.sql`

```sql
-- Table to store extracted tables
CREATE TABLE IF NOT EXISTS document_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    table_index INTEGER NOT NULL,
    page_number INTEGER,
    markdown_content TEXT NOT NULL,
    json_content JSONB,
    row_count INTEGER NOT NULL DEFAULT 0,
    col_count INTEGER NOT NULL DEFAULT 0,
    confidence FLOAT NOT NULL DEFAULT 0.9,
    bounding_box JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_document_table UNIQUE (document_id, table_index)
);

-- RLS policy for matter isolation
ALTER TABLE document_tables ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matter tables"
ON document_tables FOR ALL
USING (
    matter_id IN (
        SELECT matter_id FROM matter_attorneys
        WHERE user_id = auth.uid()
    )
);

-- Index for fast lookups
CREATE INDEX idx_document_tables_document ON document_tables(document_id);
CREATE INDEX idx_document_tables_matter ON document_tables(matter_id);
```

**Acceptance Criteria:**
- [ ] Migration runs without errors
- [ ] RLS policy enforces matter isolation
- [ ] Indexes created for performance

#### Task 1.5: Add Table Retrieval API

**File:** `backend/app/api/routes/tables.py`

```python
"""API routes for table extraction and retrieval."""

from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import require_matter_role, MatterRole, MatterMembership
from app.models.table import TablesResponse, TableResponse
from app.services.supabase import get_supabase

router = APIRouter(prefix="/matters/{matter_id}/tables", tags=["tables"])


@router.get("", response_model=TablesResponse)
async def get_matter_tables(
    matter_id: str,
    document_id: str | None = None,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> TablesResponse:
    """Get all tables for a matter, optionally filtered by document."""
    supabase = get_supabase()

    query = supabase.table("document_tables").select("*").eq("matter_id", matter_id)

    if document_id:
        query = query.eq("document_id", document_id)

    result = query.order("created_at", desc=True).execute()

    return TablesResponse(
        data=result.data,
        meta={"total": len(result.data)},
    )


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    matter_id: str,
    table_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> TableResponse:
    """Get a specific table by ID."""
    supabase = get_supabase()

    result = (
        supabase.table("document_tables")
        .select("*")
        .eq("id", table_id)
        .eq("matter_id", matter_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Table not found")

    return TableResponse(data=result.data)
```

**Acceptance Criteria:**
- [ ] GET /matters/{matter_id}/tables returns all tables
- [ ] GET /matters/{matter_id}/tables?document_id=X filters by document
- [ ] GET /matters/{matter_id}/tables/{table_id} returns single table
- [ ] All endpoints enforce matter authorization

#### Task 1.6: Write Tests

**File:** `backend/tests/services/table_extraction/test_extractor.py`

```python
"""Tests for table extraction service."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.table_extraction.extractor import TableExtractor
from app.services.table_extraction.models import ExtractedTable


class TestTableExtractor:
    @pytest.fixture
    def extractor(self):
        return TableExtractor()

    @pytest.mark.anyio
    async def test_extract_tables_returns_result(self, extractor):
        """Should return TableExtractionResult even with no tables."""
        with patch.object(extractor, 'converter') as mock_converter:
            mock_doc = MagicMock()
            mock_doc.tables = []
            mock_result = MagicMock()
            mock_result.document = mock_doc
            mock_converter.convert.return_value = mock_result

            result = await extractor.extract_tables(
                file_path=Path("/tmp/test.pdf"),
                matter_id="matter-123",
                document_id="doc-456",
            )

            assert result.document_id == "doc-456"
            assert result.matter_id == "matter-123"
            assert result.total_tables == 0
            assert result.error is None

    @pytest.mark.anyio
    async def test_extract_tables_handles_error_gracefully(self, extractor):
        """Should return empty result on error, not raise."""
        with patch.object(extractor, 'converter') as mock_converter:
            mock_converter.convert.side_effect = Exception("Docling failed")

            result = await extractor.extract_tables(
                file_path=Path("/tmp/test.pdf"),
                matter_id="matter-123",
                document_id="doc-456",
            )

            assert result.total_tables == 0
            assert result.error == "Docling failed"
```

**Acceptance Criteria:**
- [ ] Tests cover happy path
- [ ] Tests cover error handling
- [ ] Tests mock Docling to avoid real PDF processing

---

## Feature 2: Evaluation Framework (RAGAS)

### Overview

Integrate RAGAS for measuring RAG quality with support for golden datasets, automated post-ingestion evaluation, and manual evaluation triggers.

### Implementation Plan

#### Task 2.1: Add RAGAS Dependencies

**File:** `backend/pyproject.toml`

```toml
# Add to [tool.poetry.dependencies]
ragas = "^0.2.0"
datasets = "^3.0.0"  # For golden dataset management
```

**Acceptance Criteria:**
- [ ] Dependencies install without conflicts
- [ ] `from ragas import evaluate` works
- [ ] `from ragas.metrics import context_recall, faithfulness, answer_relevancy` works

#### Task 2.2: Create Evaluation Service

**Files to create:**
- `backend/app/services/evaluation/__init__.py`
- `backend/app/services/evaluation/ragas_evaluator.py`
- `backend/app/services/evaluation/models.py`
- `backend/app/services/evaluation/golden_dataset.py`

**ragas_evaluator.py:**
```python
"""RAGAS evaluation service for RAG quality metrics.

Measures:
- Context Recall: How much relevant context was retrieved
- Faithfulness: How grounded is the answer in the context
- Answer Relevancy: How relevant is the answer to the question
"""

import structlog
from functools import lru_cache
from ragas import evaluate
from ragas.metrics import context_recall, faithfulness, answer_relevancy
from datasets import Dataset

from app.services.evaluation.models import (
    EvaluationRequest,
    EvaluationResult,
    MetricScores,
)
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class RAGASEvaluator:
    """Evaluate RAG quality using RAGAS metrics."""

    def __init__(self) -> None:
        self._metrics = [context_recall, faithfulness, answer_relevancy]
        settings = get_settings()
        self._llm_model = settings.openai_evaluation_model or "gpt-4"

    async def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> EvaluationResult:
        """Evaluate a single QA pair.

        Args:
            question: User's question
            answer: Generated answer
            contexts: Retrieved context chunks
            ground_truth: Expected answer (optional, for context_recall)

        Returns:
            EvaluationResult with metric scores
        """
        logger.info(
            "evaluation_start",
            question_length=len(question),
            context_count=len(contexts),
            has_ground_truth=ground_truth is not None,
        )

        try:
            # Prepare dataset
            data = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            }
            if ground_truth:
                data["ground_truth"] = [ground_truth]

            dataset = Dataset.from_dict(data)

            # Select metrics based on available data
            metrics = self._metrics if ground_truth else [faithfulness, answer_relevancy]

            # Run evaluation
            result = evaluate(
                dataset,
                metrics=metrics,
                llm=self._llm_model,
            )

            scores = MetricScores(
                context_recall=result.get("context_recall"),
                faithfulness=result.get("faithfulness"),
                answer_relevancy=result.get("answer_relevancy"),
            )

            logger.info(
                "evaluation_complete",
                faithfulness=scores.faithfulness,
                answer_relevancy=scores.answer_relevancy,
                context_recall=scores.context_recall,
            )

            return EvaluationResult(
                question=question,
                scores=scores,
                overall_score=scores.overall,
            )

        except Exception as e:
            logger.error("evaluation_failed", error=str(e))
            raise

    async def evaluate_batch(
        self,
        items: list[EvaluationRequest],
    ) -> list[EvaluationResult]:
        """Evaluate multiple QA pairs (for golden dataset)."""
        results = []
        for item in items:
            result = await self.evaluate_single(
                question=item.question,
                answer=item.answer,
                contexts=item.contexts,
                ground_truth=item.ground_truth,
            )
            results.append(result)
        return results


@lru_cache(maxsize=1)
def get_ragas_evaluator() -> RAGASEvaluator:
    """Get singleton RAGAS evaluator instance."""
    return RAGASEvaluator()
```

**models.py:**
```python
"""Evaluation data models."""

from pydantic import BaseModel, Field, computed_field


class MetricScores(BaseModel):
    """RAGAS metric scores."""

    context_recall: float | None = Field(None, ge=0.0, le=1.0)
    faithfulness: float | None = Field(None, ge=0.0, le=1.0)
    answer_relevancy: float | None = Field(None, ge=0.0, le=1.0)

    @computed_field
    @property
    def overall(self) -> float:
        """Calculate overall score (average of available metrics)."""
        scores = [s for s in [self.faithfulness, self.answer_relevancy, self.context_recall] if s is not None]
        return sum(scores) / len(scores) if scores else 0.0


class EvaluationRequest(BaseModel):
    """Request to evaluate a QA pair."""

    question: str
    answer: str
    contexts: list[str]
    ground_truth: str | None = None


class EvaluationResult(BaseModel):
    """Result of evaluation."""

    question: str
    scores: MetricScores
    overall_score: float


class GoldenDatasetItem(BaseModel):
    """A single item in the golden dataset."""

    id: str | None = None
    matter_id: str
    question: str
    expected_answer: str
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_by: str | None = None
```

**golden_dataset.py:**
```python
"""Golden dataset management for evaluation."""

import structlog
from app.services.supabase import get_supabase
from app.services.evaluation.models import GoldenDatasetItem

logger = structlog.get_logger(__name__)


class GoldenDatasetService:
    """Manage golden QA pairs for evaluation."""

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase

    async def add_item(self, item: GoldenDatasetItem) -> GoldenDatasetItem:
        """Add a QA pair to the golden dataset."""
        result = self.supabase.table("golden_dataset").insert({
            "matter_id": item.matter_id,
            "question": item.question,
            "expected_answer": item.expected_answer,
            "relevant_chunk_ids": item.relevant_chunk_ids,
            "tags": item.tags,
            "created_by": item.created_by,
        }).execute()

        logger.info(
            "golden_item_added",
            matter_id=item.matter_id,
            question_preview=item.question[:50],
        )

        item.id = result.data[0]["id"]
        return item

    async def get_items(
        self,
        matter_id: str,
        tags: list[str] | None = None,
    ) -> list[GoldenDatasetItem]:
        """Get golden dataset items for a matter."""
        query = (
            self.supabase.table("golden_dataset")
            .select("*")
            .eq("matter_id", matter_id)
        )

        if tags:
            query = query.contains("tags", tags)

        result = query.execute()
        return [GoldenDatasetItem(**item) for item in result.data]

    async def delete_item(self, item_id: str, matter_id: str) -> bool:
        """Delete a golden dataset item."""
        result = (
            self.supabase.table("golden_dataset")
            .delete()
            .eq("id", item_id)
            .eq("matter_id", matter_id)
            .execute()
        )
        return len(result.data) > 0
```

**Acceptance Criteria:**
- [ ] RAGASEvaluator evaluates single QA pairs
- [ ] Supports batch evaluation for golden datasets
- [ ] GoldenDatasetService manages QA pairs in database
- [ ] Graceful error handling with logging

#### Task 2.3: Create Database Schema for Evaluation

**File:** `backend/supabase/migrations/YYYYMMDD_add_evaluation_tables.sql`

```sql
-- Golden dataset for evaluation
CREATE TABLE IF NOT EXISTS golden_dataset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    relevant_chunk_ids UUID[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evaluation results history
CREATE TABLE IF NOT EXISTS evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    golden_item_id UUID REFERENCES golden_dataset(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    context_recall FLOAT,
    faithfulness FLOAT,
    answer_relevancy FLOAT,
    overall_score FLOAT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_by TEXT NOT NULL DEFAULT 'manual' -- 'manual', 'auto', 'batch'
);

-- RLS policies
ALTER TABLE golden_dataset ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matter golden dataset"
ON golden_dataset FOR ALL
USING (matter_id IN (SELECT matter_id FROM matter_attorneys WHERE user_id = auth.uid()));

CREATE POLICY "Users access own matter evaluation results"
ON evaluation_results FOR ALL
USING (matter_id IN (SELECT matter_id FROM matter_attorneys WHERE user_id = auth.uid()));

-- Indexes
CREATE INDEX idx_golden_dataset_matter ON golden_dataset(matter_id);
CREATE INDEX idx_evaluation_results_matter ON evaluation_results(matter_id);
CREATE INDEX idx_evaluation_results_date ON evaluation_results(evaluated_at DESC);
```

**Acceptance Criteria:**
- [ ] Migration runs without errors
- [ ] RLS policies enforce matter isolation
- [ ] Indexes support common queries

#### Task 2.4: Create Evaluation API Routes

**File:** `backend/app/api/routes/evaluation.py`

```python
"""API routes for RAG evaluation."""

from fastapi import APIRouter, Depends, BackgroundTasks
from app.api.dependencies.auth import require_matter_role, MatterRole, MatterMembership
from app.services.evaluation.ragas_evaluator import get_ragas_evaluator
from app.services.evaluation.golden_dataset import GoldenDatasetService
from app.services.evaluation.models import (
    EvaluationRequest,
    EvaluationResult,
    GoldenDatasetItem,
)
from app.models.evaluation import (
    EvaluateRequest,
    EvaluateResponse,
    GoldenDatasetResponse,
    AddGoldenItemRequest,
    BatchEvaluateRequest,
)

router = APIRouter(prefix="/matters/{matter_id}/evaluation", tags=["evaluation"])


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_qa_pair(
    matter_id: str,
    body: EvaluateRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
) -> EvaluateResponse:
    """Evaluate a single QA pair using RAGAS metrics."""
    evaluator = get_ragas_evaluator()

    result = await evaluator.evaluate_single(
        question=body.question,
        answer=body.answer,
        contexts=body.contexts,
        ground_truth=body.ground_truth,
    )

    return EvaluateResponse(data=result)


@router.post("/evaluate/batch")
async def evaluate_batch(
    matter_id: str,
    body: BatchEvaluateRequest,
    background_tasks: BackgroundTasks,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
) -> dict:
    """Trigger batch evaluation of golden dataset (async)."""
    # Queue as Celery task for async processing
    from app.workers.tasks.evaluation_tasks import run_batch_evaluation

    task = run_batch_evaluation.delay(
        matter_id=matter_id,
        tags=body.tags,
        triggered_by=membership.user_id,
    )

    return {
        "data": {
            "task_id": task.id,
            "status": "queued",
            "message": "Batch evaluation started",
        }
    }


@router.get("/golden-dataset", response_model=GoldenDatasetResponse)
async def get_golden_dataset(
    matter_id: str,
    tags: str | None = None,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> GoldenDatasetResponse:
    """Get golden dataset items for a matter."""
    service = GoldenDatasetService()
    tag_list = tags.split(",") if tags else None
    items = await service.get_items(matter_id, tags=tag_list)
    return GoldenDatasetResponse(data=items, meta={"total": len(items)})


@router.post("/golden-dataset", response_model=GoldenDatasetResponse)
async def add_golden_item(
    matter_id: str,
    body: AddGoldenItemRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
) -> GoldenDatasetResponse:
    """Add a QA pair to the golden dataset."""
    service = GoldenDatasetService()

    item = GoldenDatasetItem(
        matter_id=matter_id,
        question=body.question,
        expected_answer=body.expected_answer,
        relevant_chunk_ids=body.relevant_chunk_ids or [],
        tags=body.tags or [],
        created_by=membership.user_id,
    )

    created = await service.add_item(item)
    return GoldenDatasetResponse(data=[created], meta={"total": 1})


@router.delete("/golden-dataset/{item_id}")
async def delete_golden_item(
    matter_id: str,
    item_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
) -> dict:
    """Delete a golden dataset item."""
    service = GoldenDatasetService()
    deleted = await service.delete_item(item_id, matter_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"data": {"deleted": True}}
```

**Acceptance Criteria:**
- [ ] POST /evaluate evaluates single QA pair
- [ ] POST /evaluate/batch triggers async Celery evaluation
- [ ] GET /golden-dataset returns matter's golden items
- [ ] POST /golden-dataset adds new items
- [ ] DELETE /golden-dataset/{id} removes items
- [ ] All endpoints enforce matter authorization

#### Task 2.5: Create Celery Task for Batch Evaluation

**File:** `backend/app/workers/tasks/evaluation_tasks.py`

```python
"""Celery tasks for evaluation."""

import structlog
from app.core.celery_app import celery_app
from app.services.evaluation.ragas_evaluator import get_ragas_evaluator
from app.services.evaluation.golden_dataset import GoldenDatasetService
from app.services.supabase import get_supabase

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def run_batch_evaluation(
    self,
    matter_id: str,
    tags: list[str] | None = None,
    triggered_by: str | None = None,
):
    """Run evaluation on golden dataset items.

    Args:
        matter_id: Matter to evaluate
        tags: Filter golden items by tags
        triggered_by: User who triggered evaluation
    """
    import asyncio

    async def _run():
        logger.info(
            "batch_evaluation_start",
            matter_id=matter_id,
            tags=tags,
        )

        # Get golden dataset
        dataset_service = GoldenDatasetService()
        items = await dataset_service.get_items(matter_id, tags=tags)

        if not items:
            logger.info("batch_evaluation_no_items", matter_id=matter_id)
            return {"evaluated": 0, "skipped": 0}

        evaluator = get_ragas_evaluator()
        supabase = get_supabase()

        evaluated = 0
        for item in items:
            try:
                # Get current answer from RAG
                # (simplified - would call actual RAG pipeline)
                from app.services.rag.hybrid_search import get_hybrid_search_service
                search_service = get_hybrid_search_service()

                # Search for context
                search_result = await search_service.search(
                    matter_id=matter_id,
                    query=item.question,
                    limit=5,
                )

                contexts = [r.content for r in search_result.results]

                # Generate answer (simplified)
                answer = item.expected_answer  # Would call LLM

                # Evaluate
                result = await evaluator.evaluate_single(
                    question=item.question,
                    answer=answer,
                    contexts=contexts,
                    ground_truth=item.expected_answer,
                )

                # Store result
                supabase.table("evaluation_results").insert({
                    "matter_id": matter_id,
                    "golden_item_id": item.id,
                    "question": item.question,
                    "answer": answer,
                    "context_recall": result.scores.context_recall,
                    "faithfulness": result.scores.faithfulness,
                    "answer_relevancy": result.scores.answer_relevancy,
                    "overall_score": result.overall_score,
                    "triggered_by": triggered_by or "batch",
                }).execute()

                evaluated += 1

            except Exception as e:
                logger.error(
                    "batch_evaluation_item_failed",
                    item_id=item.id,
                    error=str(e),
                )

        logger.info(
            "batch_evaluation_complete",
            matter_id=matter_id,
            evaluated=evaluated,
            total=len(items),
        )

        return {"evaluated": evaluated, "total": len(items)}

    return asyncio.run(_run())
```

**Acceptance Criteria:**
- [ ] Task evaluates all golden dataset items
- [ ] Results stored in evaluation_results table
- [ ] Errors logged but don't fail entire batch
- [ ] Task is retryable (max 3 retries)

#### Task 2.6: Add Auto-Evaluation Hook (Optional)

**File:** `backend/app/workers/tasks/document_tasks.py`

Add hook to trigger evaluation after ingestion completes:

```python
# At end of process_document task:

from app.core.config import get_settings

settings = get_settings()
if settings.auto_evaluation_enabled:
    from app.workers.tasks.evaluation_tasks import run_batch_evaluation
    run_batch_evaluation.delay(
        matter_id=matter_id,
        triggered_by="auto",
    )
```

**Config addition** (`backend/app/core/config.py`):
```python
auto_evaluation_enabled: bool = False  # Disabled by default
```

**Acceptance Criteria:**
- [ ] Auto-evaluation triggers after ingestion (when enabled)
- [ ] Configurable via environment variable
- [ ] Disabled by default to avoid cost

---

## Feature 3: Inspector/Debug Mode

### Overview

Add debug visibility for search scores: inline toggle in chat UI showing scores, plus dedicated admin page for detailed analysis.

### Implementation Plan

#### Task 3.1: Enhance Search Response Models

**File:** `backend/app/models/search.py`

Ensure all debug fields are exposed:

```python
class SearchResultItem(BaseModel):
    """Enhanced search result with debug info."""

    id: str
    content: str
    document_id: str
    chunk_index: int

    # Debug scores (always included)
    bm25_rank: int | None = Field(None, description="BM25 ranking position")
    semantic_rank: int | None = Field(None, description="Semantic ranking position")
    rrf_score: float = Field(..., description="RRF fusion score")
    relevance_score: float | None = Field(None, description="Reranker score (if used)")

    # Metadata
    page_number: int | None = None
    source_file: str | None = None


class SearchMetadata(BaseModel):
    """Search execution metadata for debugging."""

    query: str
    matter_id: str
    search_mode: str  # "hybrid", "bm25", "semantic"
    rerank_used: bool
    fallback_reason: str | None = None

    # Timing
    bm25_time_ms: int | None = None
    semantic_time_ms: int | None = None
    rerank_time_ms: int | None = None
    total_time_ms: int

    # Counts
    bm25_candidates: int
    semantic_candidates: int
    total_candidates: int

    # Weights
    bm25_weight: float
    semantic_weight: float
```

**Acceptance Criteria:**
- [ ] All debug fields included in response
- [ ] Timing metrics captured and returned
- [ ] Candidate counts at each stage visible

#### Task 3.2: Add Timing to Search Service

**File:** `backend/app/services/rag/hybrid_search.py`

Add timing capture:

```python
import time

async def search(...) -> HybridSearchResult:
    start_time = time.time()

    # BM25 search
    bm25_start = time.time()
    bm25_results = await self._bm25_search(...)
    bm25_time = int((time.time() - bm25_start) * 1000)

    # Semantic search
    semantic_start = time.time()
    semantic_results = await self._semantic_search(...)
    semantic_time = int((time.time() - semantic_start) * 1000)

    # Fusion
    fusion_start = time.time()
    fused = self._rrf_fusion(bm25_results, semantic_results)

    total_time = int((time.time() - start_time) * 1000)

    return HybridSearchResult(
        results=fused,
        metadata=SearchMetadata(
            bm25_time_ms=bm25_time,
            semantic_time_ms=semantic_time,
            total_time_ms=total_time,
            bm25_candidates=len(bm25_results),
            semantic_candidates=len(semantic_results),
            ...
        ),
    )
```

**Acceptance Criteria:**
- [ ] BM25 search time captured
- [ ] Semantic search time captured
- [ ] Rerank time captured (when used)
- [ ] Total time calculated

#### Task 3.3: Create Inspector API Endpoint

**File:** `backend/app/api/routes/search.py`

Add inspector endpoint with extra detail:

```python
@router.post("/inspect", response_model=InspectorResponse)
async def inspect_search(
    matter_id: str,
    body: SearchRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    search_service: HybridSearchService = Depends(get_hybrid_search_service),
    reranker: CohereRerankService = Depends(get_reranker_service),
) -> InspectorResponse:
    """Detailed search inspection with all debug data.

    Returns:
        - Raw BM25 results with scores
        - Raw semantic results with distances
        - RRF fusion breakdown
        - Reranker scores (before/after comparison)
        - Timing breakdown
    """
    # Run all search modes
    bm25_results = await search_service.bm25_search(matter_id, body.query, limit=50)
    semantic_results = await search_service.semantic_search(matter_id, body.query, limit=50)
    hybrid_results = await search_service.search(matter_id, body.query, limit=20)

    # Optionally rerank
    reranked_results = None
    if body.rerank:
        reranked_results = await reranker.rerank(
            query=body.query,
            results=hybrid_results.results,
            top_k=10,
        )

    return InspectorResponse(
        data={
            "bm25": {
                "results": bm25_results,
                "time_ms": hybrid_results.metadata.bm25_time_ms,
            },
            "semantic": {
                "results": semantic_results,
                "time_ms": hybrid_results.metadata.semantic_time_ms,
            },
            "hybrid": {
                "results": hybrid_results.results,
                "fusion_method": "rrf",
            },
            "reranked": {
                "results": reranked_results,
                "time_ms": hybrid_results.metadata.rerank_time_ms,
            } if reranked_results else None,
        },
        metadata=hybrid_results.metadata,
    )
```

**Acceptance Criteria:**
- [ ] Returns all three search modes in one response
- [ ] Includes timing for each stage
- [ ] Shows before/after reranking comparison
- [ ] Only accessible to Owners/Editors

#### Task 3.4: Create Frontend Debug Toggle

**File:** `frontend/src/components/features/chat/DebugToggle.tsx`

```typescript
'use client';

import { useState } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { useChatStore } from '@/stores/chatStore';

export function DebugToggle() {
  const debugMode = useChatStore((state) => state.debugMode);
  const setDebugMode = useChatStore((state) => state.setDebugMode);

  return (
    <div className="flex items-center space-x-2">
      <Switch
        id="debug-mode"
        checked={debugMode}
        onCheckedChange={setDebugMode}
      />
      <Label htmlFor="debug-mode" className="text-sm text-muted-foreground">
        Debug Mode
      </Label>
    </div>
  );
}
```

**File:** `frontend/src/stores/chatStore.ts`

Add debug state:

```typescript
interface ChatState {
  // ... existing state
  debugMode: boolean;
  setDebugMode: (enabled: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  // ... existing state
  debugMode: false,
  setDebugMode: (enabled) => set({ debugMode: enabled }),
}));
```

**Acceptance Criteria:**
- [ ] Toggle visible in chat header
- [ ] State persists in Zustand store
- [ ] Uses shadcn/ui Switch component

#### Task 3.5: Create Inline Debug Display

**File:** `frontend/src/components/features/chat/SourceDebugInfo.tsx`

```typescript
'use client';

import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import type { SourceReference } from '@/types/chat';

interface SourceDebugInfoProps {
  source: SourceReference;
  show: boolean;
}

export function SourceDebugInfo({ source, show }: SourceDebugInfoProps) {
  if (!show) return null;

  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {source.bm25Rank !== null && (
        <Tooltip>
          <TooltipTrigger>
            <Badge variant="outline" className="text-xs">
              BM25: #{source.bm25Rank}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>BM25 keyword search ranking</TooltipContent>
        </Tooltip>
      )}

      {source.semanticRank !== null && (
        <Tooltip>
          <TooltipTrigger>
            <Badge variant="outline" className="text-xs">
              Semantic: #{source.semanticRank}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>Vector similarity ranking</TooltipContent>
        </Tooltip>
      )}

      <Tooltip>
        <TooltipTrigger>
          <Badge variant="secondary" className="text-xs">
            RRF: {(source.rrfScore * 100).toFixed(1)}%
          </Badge>
        </TooltipTrigger>
        <TooltipContent>Reciprocal Rank Fusion score</TooltipContent>
      </Tooltip>

      {source.relevanceScore !== null && (
        <Tooltip>
          <TooltipTrigger>
            <Badge
              variant={source.relevanceScore > 0.7 ? "default" : "destructive"}
              className="text-xs"
            >
              Rerank: {(source.relevanceScore * 100).toFixed(0)}%
            </Badge>
          </TooltipTrigger>
          <TooltipContent>Cohere reranker relevance score</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Shows BM25, semantic, RRF, rerank scores as badges
- [ ] Tooltips explain each score
- [ ] Only renders when debug mode enabled
- [ ] Color-coded based on score quality

#### Task 3.6: Create Admin Inspector Page

**File:** `frontend/src/app/(dashboard)/admin/inspector/page.tsx`

```typescript
import { Suspense } from 'react';
import { InspectorPanel } from '@/components/features/admin/InspectorPanel';
import { requireAdmin } from '@/lib/auth';

export default async function InspectorPage() {
  await requireAdmin();  // Server-side auth check

  return (
    <div className="container py-6">
      <h1 className="text-2xl font-bold mb-6">Search Inspector</h1>
      <Suspense fallback={<div>Loading inspector...</div>}>
        <InspectorPanel />
      </Suspense>
    </div>
  );
}
```

**File:** `frontend/src/components/features/admin/InspectorPanel.tsx`

```typescript
'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useInspectorSearch } from '@/hooks/useInspectorSearch';

export function InspectorPanel() {
  const [query, setQuery] = useState('');
  const [matterId, setMatterId] = useState('');
  const { data, isLoading, runInspection } = useInspectorSearch();

  const handleInspect = () => {
    if (query && matterId) {
      runInspection({ matterId, query, rerank: true });
    }
  };

  return (
    <div className="space-y-6">
      {/* Query Input */}
      <Card>
        <CardHeader>
          <CardTitle>Search Query</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            placeholder="Matter ID"
            value={matterId}
            onChange={(e) => setMatterId(e.target.value)}
          />
          <Input
            placeholder="Search query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button onClick={handleInspect} disabled={isLoading}>
            {isLoading ? 'Inspecting...' : 'Run Inspection'}
          </Button>
        </CardContent>
      </Card>

      {/* Results Tabs */}
      {data && (
        <Tabs defaultValue="hybrid">
          <TabsList>
            <TabsTrigger value="bm25">BM25 ({data.bm25.results.length})</TabsTrigger>
            <TabsTrigger value="semantic">Semantic ({data.semantic.results.length})</TabsTrigger>
            <TabsTrigger value="hybrid">Hybrid ({data.hybrid.results.length})</TabsTrigger>
            {data.reranked && (
              <TabsTrigger value="reranked">Reranked ({data.reranked.results.length})</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="bm25">
            <ResultsTable results={data.bm25.results} scoreKey="bm25Score" />
          </TabsContent>
          <TabsContent value="semantic">
            <ResultsTable results={data.semantic.results} scoreKey="distance" />
          </TabsContent>
          <TabsContent value="hybrid">
            <ResultsTable results={data.hybrid.results} scoreKey="rrfScore" />
          </TabsContent>
          {data.reranked && (
            <TabsContent value="reranked">
              <ResultsTable results={data.reranked.results} scoreKey="relevanceScore" />
            </TabsContent>
          )}
        </Tabs>
      )}

      {/* Timing Summary */}
      {data?.metadata && (
        <Card>
          <CardHeader>
            <CardTitle>Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold">{data.metadata.bm25TimeMs}ms</div>
                <div className="text-sm text-muted-foreground">BM25</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{data.metadata.semanticTimeMs}ms</div>
                <div className="text-sm text-muted-foreground">Semantic</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{data.metadata.rerankTimeMs ?? '-'}ms</div>
                <div className="text-sm text-muted-foreground">Rerank</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{data.metadata.totalTimeMs}ms</div>
                <div className="text-sm text-muted-foreground">Total</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

**Acceptance Criteria:**
- [ ] Page only accessible to admins
- [ ] Query input with matter selection
- [ ] Tabs showing BM25, semantic, hybrid, reranked results
- [ ] Timing breakdown visualization
- [ ] Results table with all scores visible

#### Task 3.7: Create Inspector Hook

**File:** `frontend/src/hooks/useInspectorSearch.ts`

```typescript
import { useState } from 'react';
import { apiClient } from '@/lib/api';

interface InspectorRequest {
  matterId: string;
  query: string;
  rerank?: boolean;
}

interface InspectorResponse {
  bm25: { results: any[]; timeMs: number };
  semantic: { results: any[]; timeMs: number };
  hybrid: { results: any[]; fusionMethod: string };
  reranked?: { results: any[]; timeMs: number };
  metadata: {
    bm25TimeMs: number;
    semanticTimeMs: number;
    rerankTimeMs?: number;
    totalTimeMs: number;
  };
}

export function useInspectorSearch() {
  const [data, setData] = useState<InspectorResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const runInspection = async ({ matterId, query, rerank = true }: InspectorRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.post<InspectorResponse>(
        `/matters/${matterId}/search/inspect`,
        { query, rerank }
      );
      setData(response.data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  return { data, isLoading, error, runInspection };
}
```

**Acceptance Criteria:**
- [ ] Hook manages loading/error state
- [ ] Calls inspector API endpoint
- [ ] Returns typed response data

#### Task 3.8: Update Types

**File:** `frontend/src/types/chat.ts`

Add debug fields to SourceReference:

```typescript
export interface SourceReference {
  id: string;
  content: string;
  documentId: string;
  pageNumber?: number;

  // Debug scores
  bm25Rank: number | null;
  semanticRank: number | null;
  rrfScore: number;
  relevanceScore: number | null;
}
```

**Acceptance Criteria:**
- [ ] Types match backend response models
- [ ] All debug fields properly typed

---

## Additional Context

### Dependencies to Add

**Backend (`pyproject.toml`):**
```toml
docling = "^2.0.0"
docling-core = "^2.0.0"
pandas = "^2.0.0"
ragas = "^0.2.0"
datasets = "^3.0.0"
```

### Testing Strategy

**Unit Tests:**
- Table extractor with mocked Docling
- RAGAS evaluator with mocked LLM
- Golden dataset CRUD operations

**Integration Tests:**
- Table extraction pipeline end-to-end
- Evaluation API endpoints
- Inspector API endpoints

**Manual Tests:**
- Upload PDF with tables, verify extraction
- Add golden dataset item, run evaluation
- Enable debug mode, verify scores display

### Configuration Additions

**Backend (`app/core/config.py`):**
```python
# Table Extraction
table_extraction_enabled: bool = True
table_detection_confidence_threshold: float = 0.70

# Evaluation
auto_evaluation_enabled: bool = False
openai_evaluation_model: str = "gpt-4"
evaluation_batch_size: int = 10

# Inspector
inspector_enabled: bool = True
```

### Database Migrations Required

1. `YYYYMMDD_add_document_tables.sql` - Table extraction storage
2. `YYYYMMDD_add_evaluation_tables.sql` - Golden dataset + results

### Notes

- **Cost Awareness**: RAGAS uses LLM for evaluation - estimated $0.10-0.50 per QA pair
- **Performance**: Table extraction adds ~2-5s per document to ingestion
- **Security**: Inspector endpoint restricted to Owners/Editors only

---

## Acceptance Criteria Summary

### Feature 1: Table Extraction
- [ ] Docling extracts tables from PDFs
- [ ] Tables converted to Markdown format
- [ ] Tables stored in database with matter isolation
- [ ] Tables linked to chunks via bounding boxes
- [ ] API endpoints for table retrieval
- [ ] Errors don't fail document ingestion

### Feature 2: Evaluation Framework
- [ ] RAGAS evaluates Context Recall, Faithfulness, Answer Relevancy
- [ ] Golden dataset CRUD operations work
- [ ] Manual evaluation via API works
- [ ] Batch evaluation via Celery works
- [ ] Auto-evaluation after ingestion (configurable)
- [ ] Results stored with matter isolation

### Feature 3: Inspector/Debug Mode
- [ ] Debug toggle in chat UI
- [ ] Inline scores display when enabled
- [ ] Admin inspector page accessible
- [ ] All search modes visible (BM25, semantic, hybrid, reranked)
- [ ] Timing breakdown visible
- [ ] Only Owners/Editors can access
