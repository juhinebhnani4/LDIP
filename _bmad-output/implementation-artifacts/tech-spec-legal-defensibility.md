# Tech-Spec: Legal Defensibility - Reasoning Traces & Court-Ready Certification

**Created:** 2026-01-27
**Status:** Ready for Development
**Epic:** 4 - Legal Defensibility (Gap Remediation)
**Stories:** 4.1, 4.2, 4.3
**Gaps Addressed:** #5 (Reasoning trace/explainability), #17 (Court-ready certification stamp)

---

## Overview

### Problem Statement

LDIP uses AI engines to extract citations, build timelines, detect contradictions, and answer questions. However:

1. **No explainability:** When AI reaches a conclusion, there's no record of *why* - making it impossible to explain decisions to courts
2. **No audit trail:** If a finding is challenged, we can't show the AI's reasoning process
3. **No certification:** Exports don't prove that findings were human-verified before court submission

Legal professionals need to demonstrate due diligence when using AI-assisted analysis. Without reasoning traces and certification, LDIP outputs lack the defensibility required for court submissions.

### Solution

Implement a three-part legal defensibility system:

1. **Reasoning Trace Capture:** Store the AI's chain-of-thought reasoning for every finding
2. **Tiered Storage:** Keep recent traces in PostgreSQL (hot), archive older traces to Supabase Storage (cold)
3. **Court-Ready Certification:** Add a verification certificate to PDF exports showing human oversight

### Scope

**In Scope:**
- Capture reasoning from all 5 engines (Citation, Timeline, Contradiction, RAG, Entity)
- New `reasoning_traces` table with 30-day hot retention
- Archival job moving traces to Supabase Storage after 30 days
- Certification stamp on first page of PDF exports
- API endpoint to retrieve reasoning for any finding

**Out of Scope:**
- Attorney bar number tracking (deferred)
- S3 Glacier integration (using Supabase Storage instead)
- Reasoning trace editing/modification (immutable by design)
- Real-time reasoning display during processing (future enhancement)

---

## Context for Development

### Codebase Patterns

**Engine Pattern:**
- All engines inherit from `EngineBase` in `engines/base.py`
- LLM calls happen in specific methods (e.g., `extract_citations()`, `compare_statements()`)
- Prompts already request JSON with `"reasoning"` field - just not stored

**Storage Pattern:**
- Supabase Storage used for documents, exports
- Path convention: `/{type}/{matter_id}/{id}/{filename}`
- Signed URLs with 1-hour expiry

**Verification Pattern:**
- `finding_verifications` table snapshots finding state
- `verification_summary` JSONB in exports captures stats at export time

**Audit Pattern:**
- `QueryAuditEntry` in orchestrator logs forensic trails
- Append-only design for compliance

### Files to Reference

**Engine Files (add reasoning capture):**
- `backend/app/engines/citation/extractor.py` - Gemini calls
- `backend/app/engines/timeline/date_extractor.py` - Gemini calls
- `backend/app/engines/contradiction/comparator.py` - GPT-4 calls
- `backend/app/engines/rag/generator.py` - Gemini calls
- `backend/app/services/mig/entity_resolver.py` - Gemini calls

**Prompt Files (standardize reasoning request):**
- `backend/app/engines/citation/prompts.py`
- `backend/app/engines/timeline/prompts.py`
- `backend/app/engines/contradiction/prompts.py`
- `backend/app/engines/rag/prompts.py`
- `backend/app/services/mig/prompts.py`

**Export Files (add certification):**
- `backend/app/services/export/export_service.py`
- `backend/app/services/export/pdf_generator.py`
- `backend/app/api/routes/exports.py`

**Storage Files:**
- `backend/app/services/storage_service.py`

**Models:**
- `backend/app/models/verification.py`
- `backend/app/models/export.py`

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hot storage duration | 30 days | Balance query speed vs storage cost |
| Cold storage location | Supabase Storage | Already integrated, no new infra |
| Archive format | JSONL (gzipped) | Compact, streamable, human-readable |
| Certification in PDF | First page | Immediately visible to court |
| Reasoning immutability | Enforced via RLS | Compliance requirement |

---

## Implementation Plan

### Tasks

#### Task 1: Create Reasoning Traces Table

**File:** `supabase/migrations/YYYYMMDD_create_reasoning_traces.sql`

```sql
-- Reasoning Traces table for legal defensibility (Story 4.1)
CREATE TABLE public.reasoning_traces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  finding_id uuid REFERENCES public.findings(id) ON DELETE SET NULL,

  -- Source identification
  engine_type text NOT NULL CHECK (engine_type IN ('citation', 'timeline', 'contradiction', 'rag', 'entity')),
  model_used text NOT NULL, -- e.g., 'gpt-4', 'gemini-1.5-flash'

  -- The reasoning content
  reasoning_text text NOT NULL, -- Chain-of-thought explanation
  reasoning_structured jsonb, -- Optional structured breakdown

  -- Context that produced this reasoning
  input_summary text, -- What was fed to the LLM (truncated)
  prompt_template_version text, -- Which prompt version was used

  -- Metadata
  confidence_score float, -- 0-1 scale
  tokens_used integer,
  cost_usd numeric(10, 6),

  -- Timestamps
  created_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz DEFAULT NULL, -- Set when moved to cold storage
  archive_path text DEFAULT NULL, -- Supabase Storage path when archived

  -- Constraints
  CONSTRAINT reasoning_not_empty CHECK (length(reasoning_text) > 0)
);

-- Indexes
CREATE INDEX idx_reasoning_traces_matter ON public.reasoning_traces(matter_id);
CREATE INDEX idx_reasoning_traces_finding ON public.reasoning_traces(finding_id) WHERE finding_id IS NOT NULL;
CREATE INDEX idx_reasoning_traces_engine ON public.reasoning_traces(matter_id, engine_type);
CREATE INDEX idx_reasoning_traces_archival ON public.reasoning_traces(created_at) WHERE archived_at IS NULL;

-- RLS Policies
ALTER TABLE public.reasoning_traces ENABLE ROW LEVEL SECURITY;

-- Users can view reasoning for their matters
CREATE POLICY "Users can view reasoning from their matters"
ON public.reasoning_traces FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Only system can insert (via service role)
CREATE POLICY "System inserts reasoning traces"
ON public.reasoning_traces FOR INSERT
WITH CHECK (true); -- Service role bypasses RLS

-- No updates allowed (immutable)
-- No deletes except via archival process

COMMENT ON TABLE public.reasoning_traces IS 'Stores AI reasoning chains for legal defensibility (Story 4.1)';
COMMENT ON COLUMN public.reasoning_traces.archived_at IS 'When trace was moved to cold storage (Story 4.2)';
```

---

#### Task 2: Create Reasoning Trace Model

**File:** `backend/app/models/reasoning_trace.py`

```python
"""Reasoning trace models for legal defensibility (Story 4.1)."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class EngineType(str, Enum):
    """Engine types that produce reasoning traces."""
    CITATION = "citation"
    TIMELINE = "timeline"
    CONTRADICTION = "contradiction"
    RAG = "rag"
    ENTITY = "entity"


class ReasoningTrace(BaseModel):
    """Complete reasoning trace record."""
    id: str
    matter_id: str
    finding_id: str | None = None

    engine_type: EngineType
    model_used: str

    reasoning_text: str
    reasoning_structured: dict[str, Any] | None = None

    input_summary: str | None = None
    prompt_template_version: str | None = None

    confidence_score: float | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None

    created_at: datetime
    archived_at: datetime | None = None
    archive_path: str | None = None


class ReasoningTraceCreate(BaseModel):
    """Input for creating a reasoning trace."""
    matter_id: str
    finding_id: str | None = None
    engine_type: EngineType
    model_used: str
    reasoning_text: str
    reasoning_structured: dict[str, Any] | None = None
    input_summary: str | None = None
    prompt_template_version: str | None = None
    confidence_score: float | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None


class ReasoningTraceSummary(BaseModel):
    """Lightweight summary for API responses."""
    id: str
    engine_type: EngineType
    model_used: str
    reasoning_preview: str = Field(description="First 200 chars of reasoning")
    confidence_score: float | None
    created_at: datetime
    is_archived: bool


class ReasoningTraceStats(BaseModel):
    """Statistics for a matter's reasoning traces."""
    total_traces: int
    traces_by_engine: dict[str, int]
    hot_storage_count: int
    cold_storage_count: int
    total_tokens_used: int
    total_cost_usd: float
    oldest_hot_trace: datetime | None
    newest_trace: datetime | None
```

---

#### Task 3: Create Reasoning Trace Service

**File:** `backend/app/services/reasoning_trace_service.py`

```python
"""Service for storing and retrieving reasoning traces (Story 4.1)."""

import structlog
from datetime import datetime, timedelta
from typing import Any

from app.core.supabase import get_service_client
from app.models.reasoning_trace import (
    ReasoningTrace,
    ReasoningTraceCreate,
    ReasoningTraceSummary,
    ReasoningTraceStats,
    EngineType,
)

logger = structlog.get_logger(__name__)


class ReasoningTraceService:
    """Manages reasoning trace storage and retrieval."""

    def __init__(self):
        self.supabase = get_service_client()

    async def store_trace(self, trace: ReasoningTraceCreate) -> ReasoningTrace:
        """
        Store a new reasoning trace.

        Called by engines after LLM responses.
        """
        data = trace.model_dump()
        data["created_at"] = datetime.utcnow().isoformat()

        result = self.supabase.table("reasoning_traces").insert(data).execute()

        if not result.data:
            logger.error("Failed to store reasoning trace", matter_id=trace.matter_id)
            raise Exception("Failed to store reasoning trace")

        logger.info(
            "Stored reasoning trace",
            trace_id=result.data[0]["id"],
            engine=trace.engine_type,
            matter_id=trace.matter_id,
        )

        return ReasoningTrace(**result.data[0])

    async def get_trace(self, trace_id: str, matter_id: str) -> ReasoningTrace | None:
        """Get a specific reasoning trace."""
        result = (
            self.supabase.table("reasoning_traces")
            .select("*")
            .eq("id", trace_id)
            .eq("matter_id", matter_id)
            .single()
            .execute()
        )

        if not result.data:
            return None

        # If archived, fetch from storage
        trace = ReasoningTrace(**result.data)
        if trace.archived_at and trace.archive_path:
            trace = await self._hydrate_from_archive(trace)

        return trace

    async def get_traces_for_finding(
        self,
        finding_id: str,
        matter_id: str
    ) -> list[ReasoningTrace]:
        """Get all reasoning traces for a specific finding."""
        result = (
            self.supabase.table("reasoning_traces")
            .select("*")
            .eq("finding_id", finding_id)
            .eq("matter_id", matter_id)
            .order("created_at", desc=True)
            .execute()
        )

        return [ReasoningTrace(**row) for row in result.data]

    async def get_traces_for_matter(
        self,
        matter_id: str,
        engine_type: EngineType | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ReasoningTraceSummary]:
        """Get reasoning trace summaries for a matter."""
        query = (
            self.supabase.table("reasoning_traces")
            .select("id, engine_type, model_used, reasoning_text, confidence_score, created_at, archived_at")
            .eq("matter_id", matter_id)
        )

        if engine_type:
            query = query.eq("engine_type", engine_type.value)

        if not include_archived:
            query = query.is_("archived_at", "null")

        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        return [
            ReasoningTraceSummary(
                id=row["id"],
                engine_type=EngineType(row["engine_type"]),
                model_used=row["model_used"],
                reasoning_preview=row["reasoning_text"][:200] + "..." if len(row["reasoning_text"]) > 200 else row["reasoning_text"],
                confidence_score=row["confidence_score"],
                created_at=row["created_at"],
                is_archived=row["archived_at"] is not None,
            )
            for row in result.data
        ]

    async def get_stats(self, matter_id: str) -> ReasoningTraceStats:
        """Get reasoning trace statistics for a matter."""
        # Get counts by engine
        result = (
            self.supabase.table("reasoning_traces")
            .select("engine_type, archived_at, tokens_used, cost_usd, created_at")
            .eq("matter_id", matter_id)
            .execute()
        )

        traces = result.data
        if not traces:
            return ReasoningTraceStats(
                total_traces=0,
                traces_by_engine={},
                hot_storage_count=0,
                cold_storage_count=0,
                total_tokens_used=0,
                total_cost_usd=0.0,
                oldest_hot_trace=None,
                newest_trace=None,
            )

        traces_by_engine: dict[str, int] = {}
        hot_count = 0
        cold_count = 0
        total_tokens = 0
        total_cost = 0.0
        hot_traces_dates = []
        all_dates = []

        for t in traces:
            engine = t["engine_type"]
            traces_by_engine[engine] = traces_by_engine.get(engine, 0) + 1

            if t["archived_at"]:
                cold_count += 1
            else:
                hot_count += 1
                hot_traces_dates.append(t["created_at"])

            total_tokens += t["tokens_used"] or 0
            total_cost += float(t["cost_usd"] or 0)
            all_dates.append(t["created_at"])

        return ReasoningTraceStats(
            total_traces=len(traces),
            traces_by_engine=traces_by_engine,
            hot_storage_count=hot_count,
            cold_storage_count=cold_count,
            total_tokens_used=total_tokens,
            total_cost_usd=total_cost,
            oldest_hot_trace=min(hot_traces_dates) if hot_traces_dates else None,
            newest_trace=max(all_dates) if all_dates else None,
        )

    async def _hydrate_from_archive(self, trace: ReasoningTrace) -> ReasoningTrace:
        """Fetch full reasoning text from cold storage."""
        if not trace.archive_path:
            return trace

        try:
            # Download from Supabase Storage
            response = self.supabase.storage.from_("reasoning-archive").download(trace.archive_path)
            import gzip
            import json

            archived_data = json.loads(gzip.decompress(response))
            trace.reasoning_text = archived_data.get("reasoning_text", trace.reasoning_text)
            trace.reasoning_structured = archived_data.get("reasoning_structured")
            trace.input_summary = archived_data.get("input_summary")

            logger.info("Hydrated trace from archive", trace_id=trace.id)
        except Exception as e:
            logger.error("Failed to hydrate from archive", trace_id=trace.id, error=str(e))

        return trace
```

---

#### Task 4: Create Archival Service (Story 4.2)

**File:** `backend/app/services/reasoning_archive_service.py`

```python
"""Service for archiving reasoning traces to cold storage (Story 4.2)."""

import gzip
import json
import structlog
from datetime import datetime, timedelta

from app.core.supabase import get_service_client

logger = structlog.get_logger(__name__)

# Configuration
HOT_RETENTION_DAYS = 30
ARCHIVE_BATCH_SIZE = 100


class ReasoningArchiveService:
    """Manages archival of reasoning traces to Supabase Storage."""

    def __init__(self):
        self.supabase = get_service_client()
        self.bucket = "reasoning-archive"

    async def archive_old_traces(self) -> dict[str, int]:
        """
        Archive traces older than HOT_RETENTION_DAYS to cold storage.

        Returns count of archived traces.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=HOT_RETENTION_DAYS)

        # Find traces to archive
        result = (
            self.supabase.table("reasoning_traces")
            .select("id, matter_id, reasoning_text, reasoning_structured, input_summary, created_at")
            .lt("created_at", cutoff_date.isoformat())
            .is_("archived_at", "null")
            .limit(ARCHIVE_BATCH_SIZE)
            .execute()
        )

        traces = result.data
        if not traces:
            logger.info("No traces to archive")
            return {"archived": 0, "failed": 0}

        archived = 0
        failed = 0

        for trace in traces:
            try:
                await self._archive_single_trace(trace)
                archived += 1
            except Exception as e:
                logger.error(
                    "Failed to archive trace",
                    trace_id=trace["id"],
                    error=str(e),
                )
                failed += 1

        logger.info(
            "Archival batch complete",
            archived=archived,
            failed=failed,
            cutoff_date=cutoff_date.isoformat(),
        )

        return {"archived": archived, "failed": failed}

    async def _archive_single_trace(self, trace: dict) -> None:
        """Archive a single trace to Supabase Storage."""
        trace_id = trace["id"]
        matter_id = trace["matter_id"]

        # Prepare archive data
        archive_data = {
            "reasoning_text": trace["reasoning_text"],
            "reasoning_structured": trace["reasoning_structured"],
            "input_summary": trace["input_summary"],
            "archived_at": datetime.utcnow().isoformat(),
        }

        # Compress
        compressed = gzip.compress(json.dumps(archive_data).encode("utf-8"))

        # Upload to storage
        archive_path = f"{matter_id}/{trace_id}.json.gz"

        self.supabase.storage.from_(self.bucket).upload(
            archive_path,
            compressed,
            {"content-type": "application/gzip"},
        )

        # Update trace record (clear large text, set archive path)
        self.supabase.table("reasoning_traces").update({
            "reasoning_text": f"[Archived to cold storage: {archive_path}]",
            "reasoning_structured": None,
            "input_summary": None,
            "archived_at": datetime.utcnow().isoformat(),
            "archive_path": archive_path,
        }).eq("id", trace_id).execute()

        logger.debug("Archived trace", trace_id=trace_id, path=archive_path)

    async def restore_trace(self, trace_id: str, matter_id: str) -> bool:
        """
        Restore a trace from cold storage to hot storage.

        Used when archived trace needs frequent access.
        """
        # Get trace record
        result = (
            self.supabase.table("reasoning_traces")
            .select("*")
            .eq("id", trace_id)
            .eq("matter_id", matter_id)
            .single()
            .execute()
        )

        if not result.data or not result.data.get("archive_path"):
            return False

        archive_path = result.data["archive_path"]

        # Download from storage
        response = self.supabase.storage.from_(self.bucket).download(archive_path)
        archived_data = json.loads(gzip.decompress(response))

        # Restore to database
        self.supabase.table("reasoning_traces").update({
            "reasoning_text": archived_data["reasoning_text"],
            "reasoning_structured": archived_data.get("reasoning_structured"),
            "input_summary": archived_data.get("input_summary"),
            "archived_at": None,
            "archive_path": None,
        }).eq("id", trace_id).execute()

        # Delete from storage
        self.supabase.storage.from_(self.bucket).remove([archive_path])

        logger.info("Restored trace from archive", trace_id=trace_id)
        return True
```

---

#### Task 5: Create Archival Celery Task

**File:** `backend/app/workers/tasks/reasoning_archive_tasks.py`

```python
"""Celery tasks for reasoning trace archival (Story 4.2)."""

import structlog
from app.workers.celery_app import celery_app
from app.services.reasoning_archive_service import ReasoningArchiveService

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="archive_reasoning_traces",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def archive_reasoning_traces(self) -> dict[str, int]:
    """
    Nightly task to archive old reasoning traces.

    Scheduled via Celery Beat to run daily at 2 AM.
    """
    import asyncio

    async def run_archival():
        service = ReasoningArchiveService()
        total_archived = 0
        total_failed = 0

        # Process in batches until no more traces to archive
        while True:
            result = await service.archive_old_traces()
            total_archived += result["archived"]
            total_failed += result["failed"]

            # Stop if no more traces or too many failures
            if result["archived"] == 0 or result["failed"] > 10:
                break

        return {"total_archived": total_archived, "total_failed": total_failed}

    try:
        result = asyncio.run(run_archival())
        logger.info("Archival task complete", **result)
        return result
    except Exception as e:
        logger.error("Archival task failed", error=str(e))
        raise self.retry(exc=e)
```

**Add to Celery Beat schedule in** `backend/app/workers/celery_app.py`:

```python
# Add to beat_schedule
"archive-reasoning-traces": {
    "task": "archive_reasoning_traces",
    "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
},
```

---

#### Task 6: Update Engine Prompts to Capture Reasoning

**File:** `backend/app/engines/contradiction/prompts.py` (example - apply pattern to all engines)

Add to existing prompt templates:

```python
# Add to COMPARISON_PROMPT or equivalent
REASONING_INSTRUCTION = """
IMPORTANT: Include your complete reasoning process in the response.

Your response MUST include a "reasoning" field with:
1. What evidence you considered
2. How you interpreted the evidence
3. Why you reached your conclusion
4. Any assumptions or limitations

This reasoning will be stored for legal audit purposes.
"""

# Update response schema to require reasoning
RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["decision", "confidence", "reasoning"],
    "properties": {
        "decision": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {
            "type": "string",
            "description": "Complete chain-of-thought explanation",
            "minLength": 50,
        },
        "reasoning_structured": {
            "type": "object",
            "properties": {
                "evidence_considered": {"type": "array", "items": {"type": "string"}},
                "key_factors": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}
```

---

#### Task 7: Integrate Reasoning Capture in Engines

**File:** `backend/app/engines/base.py` (add mixin or base method)

```python
from app.services.reasoning_trace_service import ReasoningTraceService
from app.models.reasoning_trace import ReasoningTraceCreate, EngineType


class ReasoningCaptureMixin:
    """Mixin for engines to capture reasoning traces."""

    _reasoning_service: ReasoningTraceService | None = None

    @property
    def reasoning_service(self) -> ReasoningTraceService:
        if not self._reasoning_service:
            self._reasoning_service = ReasoningTraceService()
        return self._reasoning_service

    async def store_reasoning(
        self,
        matter_id: str,
        finding_id: str | None,
        engine_type: EngineType,
        model_used: str,
        llm_response: dict,
        input_summary: str | None = None,
        prompt_version: str | None = None,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """
        Store reasoning trace from LLM response.

        Call this after every LLM interaction that produces findings.
        """
        reasoning_text = llm_response.get("reasoning", "")
        if not reasoning_text:
            # Fallback: construct from available fields
            reasoning_text = f"Decision: {llm_response.get('decision', 'N/A')}. Confidence: {llm_response.get('confidence', 'N/A')}"

        trace = ReasoningTraceCreate(
            matter_id=matter_id,
            finding_id=finding_id,
            engine_type=engine_type,
            model_used=model_used,
            reasoning_text=reasoning_text,
            reasoning_structured=llm_response.get("reasoning_structured"),
            input_summary=input_summary[:1000] if input_summary else None,  # Truncate
            prompt_template_version=prompt_version,
            confidence_score=llm_response.get("confidence"),
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        try:
            await self.reasoning_service.store_trace(trace)
        except Exception as e:
            # Log but don't fail the main operation
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error(
                "Failed to store reasoning trace",
                error=str(e),
                matter_id=matter_id,
                engine=engine_type,
            )
```

**Usage in engines (example for contradiction):**

```python
# In comparator.py after GPT-4 call
response = await self.llm_client.generate(prompt)
parsed = json.loads(response.content)

# Store reasoning trace
await self.store_reasoning(
    matter_id=matter_id,
    finding_id=finding.id if finding else None,
    engine_type=EngineType.CONTRADICTION,
    model_used="gpt-4",
    llm_response=parsed,
    input_summary=f"Comparing statements: {statement_a[:100]}... vs {statement_b[:100]}...",
    prompt_version="v2.1",
    tokens_used=response.usage.total_tokens,
    cost_usd=calculate_cost(response.usage),
)
```

---

#### Task 8: Add Reasoning Trace API Routes

**File:** `backend/app/api/routes/reasoning.py`

```python
"""API routes for reasoning traces (Story 4.1)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated

from app.api.dependencies import get_current_user, require_matter_access
from app.models.reasoning_trace import (
    ReasoningTrace,
    ReasoningTraceSummary,
    ReasoningTraceStats,
    EngineType,
)
from app.services.reasoning_trace_service import ReasoningTraceService

router = APIRouter(prefix="/matters/{matter_id}/reasoning", tags=["reasoning"])


@router.get("/stats", response_model=ReasoningTraceStats)
async def get_reasoning_stats(
    matter_id: str,
    _: Annotated[None, Depends(require_matter_access)],
) -> ReasoningTraceStats:
    """Get reasoning trace statistics for a matter."""
    service = ReasoningTraceService()
    return await service.get_stats(matter_id)


@router.get("/traces", response_model=list[ReasoningTraceSummary])
async def list_reasoning_traces(
    matter_id: str,
    _: Annotated[None, Depends(require_matter_access)],
    engine: EngineType | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ReasoningTraceSummary]:
    """List reasoning traces for a matter."""
    service = ReasoningTraceService()
    return await service.get_traces_for_matter(
        matter_id=matter_id,
        engine_type=engine,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.get("/traces/{trace_id}", response_model=ReasoningTrace)
async def get_reasoning_trace(
    matter_id: str,
    trace_id: str,
    _: Annotated[None, Depends(require_matter_access)],
) -> ReasoningTrace:
    """Get a specific reasoning trace (hydrates from archive if needed)."""
    service = ReasoningTraceService()
    trace = await service.get_trace(trace_id, matter_id)

    if not trace:
        raise HTTPException(status_code=404, detail="Reasoning trace not found")

    return trace


@router.get("/findings/{finding_id}/traces", response_model=list[ReasoningTrace])
async def get_finding_reasoning(
    matter_id: str,
    finding_id: str,
    _: Annotated[None, Depends(require_matter_access)],
) -> list[ReasoningTrace]:
    """Get all reasoning traces for a specific finding."""
    service = ReasoningTraceService()
    return await service.get_traces_for_finding(finding_id, matter_id)
```

**Register in** `backend/app/api/routes/__init__.py`:

```python
from app.api.routes.reasoning import router as reasoning_router

# Add to router includes
api_router.include_router(reasoning_router)
```

---

#### Task 9: Add Court-Ready Certification to Exports (Story 4.3)

**File:** `backend/app/services/export/certification.py`

```python
"""Court-ready certification stamp generation (Story 4.3)."""

from datetime import datetime
from pydantic import BaseModel


class CertificationData(BaseModel):
    """Data for certification stamp."""
    matter_title: str
    matter_id: str
    verification_status: str  # "COMPLETE" or "PARTIAL"
    findings_verified: int
    findings_total: int
    verification_percentage: int
    verified_by_name: str
    verification_completed_at: datetime | None
    export_generated_at: datetime
    platform_version: str
    document_hash: str  # First 16 chars of SHA-256


def generate_certification_text(data: CertificationData) -> str:
    """Generate the certification stamp text."""
    status_icon = "✓" if data.verification_status == "COMPLETE" else "⚠"

    cert_text = f"""
══════════════════════════════════════════════════════════════════
                      AI-ASSISTED ANALYSIS
                     VERIFICATION CERTIFICATE
══════════════════════════════════════════════════════════════════

  Matter: {data.matter_title}
  Matter ID: {data.matter_id}

  ────────────────────────────────────────────────────────────────

  VERIFICATION STATUS: {status_icon} {data.verification_status}
  Findings Verified: {data.verification_percentage}% ({data.findings_verified} of {data.findings_total})

  ────────────────────────────────────────────────────────────────

  Verified By: {data.verified_by_name}
  Verification Completed: {data.verification_completed_at.strftime('%d %B %Y, %I:%M %p IST') if data.verification_completed_at else 'N/A'}
  Export Generated: {data.export_generated_at.strftime('%d %B %Y, %I:%M %p IST')}

  ────────────────────────────────────────────────────────────────

  This document contains AI-assisted legal analysis.
  All findings have been reviewed and verified by the
  individual named above prior to export.

  Platform: LDIP {data.platform_version}
  Document Hash: {data.document_hash}

══════════════════════════════════════════════════════════════════
"""
    return cert_text


def generate_partial_certification_text(data: CertificationData) -> str:
    """Generate certification for partial verification (advisory mode)."""
    cert_text = f"""
══════════════════════════════════════════════════════════════════
                      AI-ASSISTED ANALYSIS
                     VERIFICATION CERTIFICATE
══════════════════════════════════════════════════════════════════

  Matter: {data.matter_title}
  Matter ID: {data.matter_id}

  ────────────────────────────────────────────────────────────────

  VERIFICATION STATUS: ⚠ PARTIAL
  Findings Verified: {data.verification_percentage}% ({data.findings_verified} of {data.findings_total})

  NOTE: Unverified findings are included with acknowledgment.
  This export was generated in advisory mode.

  ────────────────────────────────────────────────────────────────

  Exported By: {data.verified_by_name}
  Export Generated: {data.export_generated_at.strftime('%d %B %Y, %I:%M %p IST')}

  ────────────────────────────────────────────────────────────────

  This document contains AI-assisted legal analysis.
  Some findings may not have been individually verified.
  Please review all content before relying on it.

  Platform: LDIP {data.platform_version}
  Document Hash: {data.document_hash}

══════════════════════════════════════════════════════════════════
"""
    return cert_text
```

---

#### Task 10: Update PDF Generator with Certification Page

**File:** `backend/app/services/export/pdf_generator.py` (update existing)

```python
"""PDF generation with court-ready certification (Story 4.3)."""

import hashlib
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.enums import TA_CENTER
from io import BytesIO

from app.services.export.certification import (
    CertificationData,
    generate_certification_text,
    generate_partial_certification_text,
)


class PDFGenerator:
    """Generates PDF exports with certification stamp."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.platform_version = "1.0.0"  # TODO: Pull from config

    def generate(
        self,
        matter_title: str,
        matter_id: str,
        content_sections: list[dict],
        verification_stats: dict,
        exported_by_name: str,
        verification_mode: str,
    ) -> bytes:
        """
        Generate PDF with certification page.

        Args:
            matter_title: Matter name
            matter_id: Matter UUID
            content_sections: List of {"title": str, "content": str}
            verification_stats: {"verified": int, "total": int, "completed_at": datetime}
            exported_by_name: Name of user generating export
            verification_mode: "advisory" or "required"

        Returns:
            PDF bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []

        # Calculate document hash (of content)
        content_str = "".join(s["content"] for s in content_sections)
        doc_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

        # Build certification data
        verified = verification_stats.get("verified", 0)
        total = verification_stats.get("total", 0)
        percentage = int((verified / total * 100) if total > 0 else 0)

        cert_data = CertificationData(
            matter_title=matter_title,
            matter_id=matter_id,
            verification_status="COMPLETE" if percentage == 100 else "PARTIAL",
            findings_verified=verified,
            findings_total=total,
            verification_percentage=percentage,
            verified_by_name=exported_by_name,
            verification_completed_at=verification_stats.get("completed_at"),
            export_generated_at=datetime.utcnow(),
            platform_version=self.platform_version,
            document_hash=doc_hash,
        )

        # Add certification page
        if verification_mode == "required" and percentage == 100:
            cert_text = generate_certification_text(cert_data)
        else:
            cert_text = generate_partial_certification_text(cert_data)

        cert_style = self.styles["Code"]
        cert_style.fontSize = 9
        cert_style.leading = 11

        story.append(Preformatted(cert_text, cert_style))
        story.append(Spacer(1, 0.5 * inch))

        # Page break after certification
        from reportlab.platypus import PageBreak
        story.append(PageBreak())

        # Add content sections
        for section in content_sections:
            # Section title
            title_style = self.styles["Heading1"]
            story.append(Paragraph(section["title"], title_style))
            story.append(Spacer(1, 0.2 * inch))

            # Section content
            body_style = self.styles["BodyText"]
            # Split content into paragraphs
            for para in section["content"].split("\n\n"):
                if para.strip():
                    story.append(Paragraph(para, body_style))
                    story.append(Spacer(1, 0.1 * inch))

            story.append(Spacer(1, 0.3 * inch))

        # Build PDF
        doc.build(story)

        return buffer.getvalue()
```

---

#### Task 11: Update Export Service to Include Certification

**File:** `backend/app/services/export/export_service.py` (update existing)

Add to the export generation flow:

```python
# In generate_export method, before PDF generation:

# Get verification stats for certification
verification_stats = await self._get_verification_stats(matter_id)

# Get user name for certification
user = await self._get_user(user_id)
exported_by_name = user.full_name or user.email

# Get matter verification mode
matter = await self._get_matter(matter_id)
verification_mode = matter.verification_mode or "advisory"

# Generate PDF with certification
pdf_generator = PDFGenerator()
pdf_bytes = pdf_generator.generate(
    matter_title=matter.title,
    matter_id=matter_id,
    content_sections=content_sections,
    verification_stats=verification_stats,
    exported_by_name=exported_by_name,
    verification_mode=verification_mode,
)
```

---

#### Task 12: Create Supabase Storage Bucket for Archives

**File:** `supabase/migrations/YYYYMMDD_create_reasoning_archive_bucket.sql`

```sql
-- Create storage bucket for reasoning trace archives (Story 4.2)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'reasoning-archive',
  'reasoning-archive',
  false,  -- Private bucket
  52428800,  -- 50MB limit per file
  ARRAY['application/gzip', 'application/json']
)
ON CONFLICT (id) DO NOTHING;

-- RLS policy: Only service role can access
CREATE POLICY "Service role access only"
ON storage.objects FOR ALL
USING (bucket_id = 'reasoning-archive')
WITH CHECK (bucket_id = 'reasoning-archive');

COMMENT ON TABLE storage.buckets IS 'Added reasoning-archive bucket for cold storage (Story 4.2)';
```

---

### Acceptance Criteria

#### Story 4.1: Reasoning Trace Storage

- [ ] **AC 4.1.1:** Given the contradiction engine identifies a conflict, when the analysis completes, then a structured summary is stored in the `reasoning_traces` table with: input context, key evidence, confidence score, decision rationale
- [ ] **AC 4.1.2:** Given the database write fails during trace storage, when the storage operation encounters an error, then the analysis result is still returned to the user, the failed trace is queued for retry, and the error is logged with correlation ID
- [ ] **AC 4.1.3:** Given any engine (citation, timeline, contradiction, RAG, entity) completes an LLM call, when the response is received, then the reasoning is captured and stored
- [ ] **AC 4.1.4:** Given a user views a finding, when they request the reasoning, then the API returns the full chain-of-thought explanation

#### Story 4.2: Tiered Reasoning Storage

- [ ] **AC 4.2.1:** Given a reasoning trace is older than 30 days, when the nightly archival job runs, then the full content is moved to Supabase Storage (gzipped JSONL)
- [ ] **AC 4.2.2:** Given a trace is archived, when a user requests it, then the trace is hydrated from cold storage and returned (within 5 seconds)
- [ ] **AC 4.2.3:** Given archival upload fails, when the storage operation encounters an error, then the trace remains in hot storage (not deleted), failed archival is retried on next job run, and an alert is sent if failures exceed 3 consecutive
- [ ] **AC 4.2.4:** Given archived traces exist, when stats are requested, then both hot and cold storage counts are returned

#### Story 4.3: Court-Ready Certification

- [ ] **AC 4.3.1:** Given a matter has `verification_mode = "required"` and all findings are verified, when the user exports, then the PDF includes a certification block on the first page with: verification percentage (100%), verifying user name, verification completion timestamp, matter ID, export timestamp, document hash
- [ ] **AC 4.3.2:** Given a matter has `verification_mode = "advisory"`, when the user exports, then the certification shows "PARTIAL" status with acknowledgment that unverified findings are included
- [ ] **AC 4.3.3:** Given an export is generated, when the PDF is opened, then the certification stamp is visible on the first page before any content
- [ ] **AC 4.3.4:** Given the document content changes, when the hash is recalculated, then the hash value changes (tamper detection)

---

## Additional Context

### Dependencies

**Python packages (add to requirements.txt):**
```
reportlab>=4.0.0  # PDF generation (may already exist)
```

**Supabase:**
- New `reasoning_traces` table
- New `reasoning-archive` storage bucket
- Update RLS policies

### Testing Strategy

**Unit Tests:**
- `test_reasoning_trace_service.py` - CRUD operations, archival logic
- `test_certification.py` - Certification text generation
- `test_pdf_generator.py` - PDF output with certification

**Integration Tests:**
- `test_reasoning_api.py` - API endpoint behavior
- `test_archival_task.py` - Celery task execution
- `test_export_certification.py` - End-to-end export with certification

**Manual Tests:**
- Export PDF and verify certification is on first page
- Verify reasoning traces appear in database after engine runs
- Verify archival moves old traces to storage
- Verify archived traces can be retrieved

### Notes

1. **Reasoning is immutable:** Once stored, traces cannot be modified. This is enforced by RLS (no UPDATE policy) and ensures audit integrity.

2. **Graceful degradation:** If reasoning storage fails, the main engine operation should still complete. Reasoning capture is non-blocking.

3. **Cost tracking:** Each trace stores `tokens_used` and `cost_usd` for future cost analytics (ties into Epic 7 cost tracking).

4. **Archive retrieval latency:** Hydrating from cold storage may take 2-5 seconds. Consider caching frequently accessed archived traces.

5. **Storage costs:** Supabase Storage is ~$0.021/GB/month. Gzipped traces average ~2KB each. 100,000 traces = ~200MB = ~$0.004/month.

---

## Manual Steps Required

### Migrations
- [ ] Run: `supabase/migrations/YYYYMMDD_create_reasoning_traces.sql`
- [ ] Run: `supabase/migrations/YYYYMMDD_create_reasoning_archive_bucket.sql`

### Environment Variables
- None required (uses existing Supabase config)

### Dashboard Configuration
- [ ] Verify `reasoning-archive` bucket created in Supabase Storage

### Manual Tests
- [ ] Upload a document, wait for processing, verify reasoning traces created
- [ ] Export a matter in court-ready mode, verify certification on first page
- [ ] Wait 30+ days (or manually backdate a trace), run archival, verify cold storage

---

**End of Tech-Spec**
