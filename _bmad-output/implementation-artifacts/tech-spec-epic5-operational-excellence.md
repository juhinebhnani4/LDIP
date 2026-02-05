# Tech-Spec: Epic 5 Operational Excellence (Stories 5.4-5.7)

**Created:** 2026-01-27
**Status:** Ready for Development
**Gaps Covered:** #50 (Cross-Engine Consistency), #39 (LLM Errors), #41 (Queue Depth), #42 (ETA)

---

## Overview

### Problem Statement

LDIP lacks operational visibility and cross-engine data integrity validation:
1. **No consistency checking** - Timeline and Citation engines can extract conflicting dates from the same document without detection
2. **Cryptic LLM errors** - Raw API errors (429, 500) confuse users with technical jargon
3. **No queue visibility** - Admins cannot see processing bottlenecks or backlog depth
4. **No ETA** - Users have no idea when processing will complete after upload

### Solution

Implement four interconnected stories that improve operational visibility and data quality:
1. **Cross-Engine Consistency Checking** - Automated validation comparing engine outputs, flagging conflicts
2. **User-Friendly LLM Errors** - Error transformer mapping API errors to actionable messages
3. **Queue Depth Dashboard** - Admin widget showing job counts per queue with trends
4. **Processing ETA** - Estimated completion time displayed on upload confirmation

### Scope

**In Scope:**
- Story 5.4: Cross-engine date consistency checking (Timeline vs Citation)
- Story 5.5: LLM error message transformation for OpenAI and Gemini
- Story 5.6: Admin dashboard queue depth widget
- Story 5.7: Processing ETA on upload confirmation and matter status

**Out of Scope:**
- Cross-entity contradiction detection (Phase 8)
- Full SSE for real-time updates (use polling MVP)
- Missing event detection from timeline gaps

---

## Context for Development

### Codebase Patterns

**API Response Format (MANDATORY):**
```python
# Success
{"data": {...}}

# Error
{"error": {"code": "ERROR_CODE", "message": "Human message", "details": {}}}
```

**Exception Pattern:**
```python
from app.core.exceptions import AppException

class MyError(AppException):
    def __init__(self, message: str):
        super().__init__(code="MY_ERROR", message=message, status_code=400)
```

**Pydantic Models:** Use v2 syntax with `model_config = ConfigDict(populate_by_name=True)` and `Field(..., alias="camelCase")`.

**Celery Tasks:** Use `@celery_app.task` decorator with explicit `name`, `bind=True`, `max_retries`, and `soft_time_limit`.

**Structlog:** All logging via `structlog.get_logger(__name__)`.

### Files to Reference

| File | Purpose |
|------|---------|
| `backend/app/services/cross_engine_service.py` | Base for consistency service |
| `backend/app/models/cross_engine.py` | Pydantic models for cross-engine API |
| `backend/app/engines/timeline/date_extractor.py` | Date parsing and normalization logic |
| `backend/app/core/exceptions.py` | Error class patterns |
| `backend/app/workers/celery.py` | Celery config, beat schedule |
| `backend/app/api/routes/admin/quota.py` | Admin endpoint pattern |
| `backend/app/workers/tasks/quota_monitoring_tasks.py` | Celery beat task pattern |
| `frontend/src/components/features/admin/` | Admin dashboard components |

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Date comparison | Normalize to ISO before compare | Avoid false positives from format differences |
| Consistency validation | Batch after pipeline | Full context available, less complexity |
| ETA calculation | Rolling average + fallback | Handles cold start, adapts to load |
| Error display | Toast + inline hybrid | Transient vs blocking distinction |
| Queue metrics source | Redis `LLEN` on Celery queues | Direct, no extra infrastructure |
| Admin access | Email whitelist | Existing pattern in quota.py |

---

## Implementation Plan

### Tasks

#### Story 5.4: Cross-Engine Consistency Checking

- [ ] **Task 5.4.1:** Create `consistency_issues` table migration
  - Columns: id, matter_id, issue_type, severity, source_engine, source_finding_id, source_value, target_engine, target_finding_id, target_value, document_id, status, content_hash, dismissed_at, dismissal_reason, resolved_by, resolved_at, created_at
  - Add RLS policy for matter isolation
  - Index on (matter_id, status)

- [ ] **Task 5.4.2:** Add ConsistencyIssue model to `backend/app/models/cross_engine.py`
  ```python
  class ConsistencyIssue(BaseModel):
      id: str
      matter_id: str = Field(..., alias="matterId")
      issue_type: str = Field(..., alias="issueType")  # 'date_mismatch', 'entity_conflict'
      severity: str  # 'warning', 'error'
      source_engine: str = Field(..., alias="sourceEngine")
      source_finding_id: str = Field(..., alias="sourceFindingId")
      source_value: str = Field(..., alias="sourceValue")
      target_engine: str = Field(..., alias="targetEngine")
      target_finding_id: str = Field(..., alias="targetFindingId")
      target_value: str = Field(..., alias="targetValue")
      document_id: str = Field(..., alias="documentId")
      status: str  # 'open', 'resolved', 'dismissed'
      content_hash: str = Field(..., alias="contentHash")
  ```

- [ ] **Task 5.4.3:** Create date normalization utility in `backend/app/core/date_normalizer.py`
  - Extract logic from `date_extractor.py`
  - Handle formats: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, "January 15, 2024", etc.
  - Handle legal patterns: "dated this 15th day of January" → regex extraction
  - Handle partial dates: "January 2024" → compare at month precision only
  - Handle relative dates: "last Tuesday", "next month" → return None (skip comparison)
  - Handle fiscal years: "FY 2023-24" → return None (ambiguous)
  - Handle European dot notation: "15.01.2024" → parse with locale hint
  - Handle archaic legal: "the 15th inst." → return None (requires context)
  - Return `tuple[date | None, str]` where str is precision: "day", "month", "year", "unparseable"
  - **Red Team fix:** Log all unparseable formats to `exotic_date_formats` table for future improvement
  - **Red Team fix:** Multi-tier parsing: regex → dateutil → return None (no LLM tier for cost)

- [ ] **Task 5.4.4:** Add `CrossEngineConsistencyService` to `cross_engine_service.py`
  ```python
  async def validate_matter_consistency(self, matter_id: str) -> list[ConsistencyIssue]:
      """Run all consistency checks for a matter."""

  async def check_date_consistency(self, matter_id: str) -> list[ConsistencyIssue]:
      """Compare timeline dates vs citation dates for same documents.

      Red Team defenses:
      - Only compare same date_context types (document_date vs document_date)
      - Mark cross-midnight with time info as 'needs_review' not 'conflict'
      - Rate limit: max 100 open issues per matter
      """

  async def dismiss_issue(self, issue_id: str, user_id: str, reason: str) -> None:
      """Mark issue as dismissed with reason."""

  async def get_open_issues(self, matter_id: str) -> list[ConsistencyIssue]:
      """Get all open consistency issues for matter."""

  def _extract_date_context(self, surrounding_text: str) -> str:
      """Extract date context type: 'document_date', 'effective_date', 'signing_date', etc."""
  ```
  - **Red Team fix:** Add `date_context` field to issues, only compare same context types
  - **Red Team fix:** Cap at 100 open issues per matter (prevent DoS)

- [ ] **Task 5.4.5:** Add Celery task `validate_consistency_batch` in `backend/app/workers/tasks/engine_tasks.py`
  - Triggered after document pipeline completes
  - Add to pipeline chain after entity resolution
  - **CRITICAL:** Add integration test verifying task executes after upload
  - Add Prometheus metric: `consistency_checks_executed_total`
  - Add alert rule: no checks in 24h with active uploads → warning

- [ ] **Task 5.4.6:** Add API endpoints in `backend/app/api/routes/cross_engine.py`
  - `GET /api/matters/{matter_id}/consistency-issues` - List open issues
  - `POST /api/consistency-issues/{issue_id}/dismiss` - Dismiss with reason

- [ ] **Task 5.4.7:** Frontend: Add warning badge to Timeline/Citation cards
  - Location: `frontend/src/components/features/timeline/TimelineEventCard.tsx`
  - Show warning icon if event has linked consistency issue

- [ ] **Task 5.4.8:** Frontend: Add "Review Needed" queue component
  - Location: `frontend/src/components/features/crossEngine/ConsistencyReviewQueue.tsx`
  - List all open issues with dismiss/resolve actions

#### Story 5.5: User-Friendly LLM Error Messages

- [ ] **Task 5.5.1:** Create `backend/app/core/llm_error_handler.py`
  ```python
  from dataclasses import dataclass
  from enum import Enum

  class LLMErrorSeverity(Enum):
      TRANSIENT = "transient"  # Auto-retry, toast
      BLOCKING = "blocking"    # User action needed, inline
      CRITICAL = "critical"    # Contact support, modal

  @dataclass
  class UserFriendlyError:
      title: str
      message: str
      action: str | None
      severity: LLMErrorSeverity
      retry_after_seconds: int | None
      correlation_id: str

  def transform_llm_error(
      exception: Exception,
      provider: str,
      operation: str,
  ) -> UserFriendlyError:
      """Transform raw LLM exception to user-friendly error."""
  ```

- [ ] **Task 5.5.2:** Define error mappings
  | Raw Error | Provider | User Message | Action | Severity |
  |-----------|----------|--------------|--------|----------|
  | 429 Rate Limit | OpenAI/Gemini | "AI service temporarily busy" | "Retrying in {n} seconds" | TRANSIENT |
  | 500 Server Error | OpenAI/Gemini | "AI service experiencing issues" | "Retrying automatically" | TRANSIENT |
  | 401 Auth Error | OpenAI/Gemini | "Service configuration error" | "Contact support" | CRITICAL |
  | Quota Exceeded | OpenAI/Gemini | "Daily AI limit reached" | "Contact admin" | BLOCKING |
  | Timeout | OpenAI/Gemini | "Request took too long" | "Retrying with smaller request" | TRANSIENT |
  | Context Length | OpenAI | "Document section too large" | "Processing in smaller chunks" | TRANSIENT |

- [ ] **Task 5.5.3:** Update LLM call sites to use handler
  - `backend/app/engines/rag/generator.py`
  - `backend/app/engines/timeline/date_extractor.py`
  - `backend/app/engines/citation/extractor.py`
  - `backend/app/engines/contradiction/comparator.py`
  - **Self-Consistency fix:** Also update these missing call sites:
    - `backend/app/services/mig/extractor.py` (entity extraction)
    - `backend/app/engines/timeline/entity_linker.py` (entity linking)
    - `backend/app/services/summary_service.py` (summary generation)

- [ ] **Task 5.5.4:** Add error response field to chat API
  - Extend `ChatResponse` model with optional `llmError: UserFriendlyError`
  - Return in SSE stream when LLM errors occur

- [ ] **Task 5.5.5:** Frontend: Create error display components
  - `frontend/src/components/ui/LLMErrorToast.tsx` - For transient errors
  - `frontend/src/components/ui/LLMErrorBanner.tsx` - For blocking errors
  - Use existing toast system from shadcn/ui
  - **Pre-mortem fix:** Differentiate toast colors: blue=retrying, yellow=degraded, red=failed
  - **Pre-mortem fix:** Add "Copy error details" button (correlation ID + context)
  - **Pre-mortem fix:** Track consecutive errors in session storage → escalate to banner after 3

- [ ] **Task 5.5.6:** Frontend: Integrate error handling in chat
  - Update `frontend/src/components/features/chat/QAPanel.tsx`
  - Show toast for transient, inline banner for blocking

#### Story 5.6: Queue Depth Visibility Dashboard

- [ ] **Task 5.6.1:** Create `backend/app/services/queue_metrics_service.py`
  ```python
  @dataclass
  class QueueMetrics:
      queue_name: str
      pending_count: int
      active_count: int
      failed_count: int
      completed_24h: int
      avg_processing_time_ms: int

  class QueueMetricsService:
      async def get_all_queue_metrics(self) -> list[QueueMetrics]:
          """Get metrics for all Celery queues."""

      async def get_queue_depth_trend(self, hours: int = 24) -> dict:
          """Get hourly queue depth for trend chart."""
  ```

- [ ] **Task 5.6.2:** Add Redis queries for Celery queue inspection
  - **CRITICAL:** Verify actual Redis key names (Celery uses `celery` not `default`)
  - Use `redis.llen("celery")` for default queue
  - Use `redis.llen("high")` and `redis.llen("low")` for priority queues
  - Track historical data in `queue_metrics` table (optional, for trends)
  - **Pre-mortem fix:** Add integration test that enqueues task → verifies LLEN increases
  - **Pre-mortem fix:** Include `last_checked_at` timestamp in response
  - **Pre-mortem fix:** Add health check endpoint `/api/admin/queue-status/health`
  - Show staleness warning if metrics older than 60 seconds

- [ ] **Task 5.6.3:** Add API endpoint `GET /api/admin/queue-status`
  ```python
  @router.get("/queue-status")
  async def get_queue_status(
      admin: AuthenticatedUser = Depends(require_admin_access),
  ) -> QueueStatusResponse:
      """Get current queue depths and metrics."""
  ```

- [ ] **Task 5.6.4:** Frontend: Create queue depth widget
  - Location: `frontend/src/components/features/admin/QueueDepthWidget.tsx`
  - Show: Queue name, pending count, active count, trend arrow
  - Alert indicator when any queue exceeds threshold (configurable, default 100)

- [ ] **Task 5.6.5:** Frontend: Add to admin dashboard
  - Update `frontend/src/app/(dashboard)/admin/page.tsx`
  - Place alongside existing LLM quota widget

#### Story 5.7: Processing ETA Display

- [ ] **Task 5.7.1:** Create `backend/app/services/eta_calculator.py`
  ```python
  @dataclass
  class ETAResult:
      min_seconds: int      # Optimistic estimate
      max_seconds: int      # Pessimistic estimate
      best_guess_seconds: int
      confidence: str       # "high", "medium", "low"
      factors: dict         # Explain calculation

  class ETACalculator:
      FALLBACK_SECONDS_PER_PAGE = 2  # Changed: per-page not per-doc
      ROLLING_WINDOW = 100

      async def get_processing_eta(
          self,
          matter_id: str,
          pending_docs: list[dict],  # Include page_count per doc
      ) -> ETAResult:
          """Calculate ETA with confidence range, not point estimate."""

      async def get_weighted_avg_time(self) -> float:
          """Get rolling average weighted by document page count."""

      async def get_active_worker_count(self) -> int:
          """Query actual active workers (not config value)."""

      async def record_completion(
          self,
          document_id: str,
          page_count: int,
          processing_time_ms: int,
      ) -> None:
          """Record completion with page count for weighted average."""
  ```
  - **Pre-mortem fix:** Weight by page count, query real workers, return range

- [ ] **Task 5.7.2:** Add Redis keys for metrics tracking
  ```
  metrics:processing_time:history  # List of last 100 processing times
  metrics:processing_time:avg      # Cached average (TTL 60s)
  metrics:active_workers           # Current worker count
  ```

- [ ] **Task 5.7.3:** Update document completion to record metrics
  - Modify `backend/app/workers/tasks/chunked_document_tasks.py`
  - Call `eta_calculator.record_completion()` on success

- [ ] **Task 5.7.4:** Extend document status response with ETA
  - Add to `DocumentStatusResponse` in `backend/app/models/document.py`:
    ```python
    # Self-consistency fix: Use min/max to match ETAResult, not single datetime
    estimated_completion_min: datetime | None = Field(None, alias="estimatedCompletionMin")
    estimated_completion_max: datetime | None = Field(None, alias="estimatedCompletionMax")
    eta_confidence: str | None = Field(None, alias="etaConfidence")  # "high", "medium", "low"
    queue_position: int | None = Field(None, alias="queuePosition")
    ```

- [ ] **Task 5.7.5:** Update document status endpoint
  - Modify `GET /api/documents/{document_id}/status`
  - Include ETA when status is `processing` or `queued`

- [ ] **Task 5.7.6:** Frontend: Create processing status component
  - Location: `frontend/src/components/features/upload/ProcessingStatus.tsx`
  - Display: Progress bar, X of Y complete, ETA range (not point estimate)
  - Example: "Estimated: 15-45 minutes" with confidence indicator
  - Auto-refresh via polling (5s interval)
  - **Pre-mortem fix:** Show confidence level (high/medium/low) as visual indicator

- [ ] **Task 5.7.7:** Frontend: Add to upload confirmation
  - Update `frontend/src/components/features/upload/UploadWizard.tsx`
  - Show ProcessingStatus after successful upload
  - Include "You'll receive an email when ready" message

### Acceptance Criteria

#### Story 5.4: Cross-Engine Consistency Checking

- [ ] **AC 5.4.1:** Given timeline extracts "Contract signed Jan 15, 2024" and citation references same doc as "dated Jan 16, 2024", when cross-engine validation runs, then a consistency issue is created with `issue_type='date_mismatch'`, `severity='warning'`, and both finding IDs linked.

- [ ] **AC 5.4.2:** Given "January 15, 2024" and "2024-01-15" are extracted for same event, when validation runs, then NO issue is created (format difference, not conflict).

- [ ] **AC 5.4.2b:** Given "January 2024" (month precision) and "January 15, 2024" (day precision) are extracted, when validation runs, then NO issue is created (comparison at month precision only).

- [ ] **AC 5.4.2c:** Given "dated this 15th day of January 2024" is extracted, when date normalizer runs, then it parses to 2024-01-15 correctly.

- [ ] **AC 5.4.3:** Given user dismisses an issue with reason "Known discrepancy in source", when same document is reprocessed, then issue with matching `content_hash` is auto-dismissed.

- [ ] **AC 5.4.4:** Given an open consistency issue exists, when user views the linked timeline event, then a warning icon appears with tooltip "Date inconsistency detected".

- [ ] **AC 5.4.5 (Red Team):** Given a matter has 100 open consistency issues, when validation finds a 101st issue, then it is logged but NOT created, and admin is notified "Issue limit reached".

- [ ] **AC 5.4.6 (Red Team):** Given timeline has "document date: Jan 15" and citation has "effective date: Jan 16", when validation runs, then NO issue is created (different date contexts).

- [ ] **AC 5.4.7 (Red Team):** Given same issue is dismissed on Document A, when Document B has identical source/target values, then Document B's issue is NOT auto-dismissed (different document_id in hash).

- [ ] **AC 5.4.8 (Self-Consistency):** Given open consistency issues exist for a matter, when user views the Review Needed queue, then issues are listed with document name, date values, and dismiss/resolve action buttons.

#### Story 5.5: User-Friendly LLM Error Messages

- [ ] **AC 5.5.1:** Given OpenAI returns 429 rate limit, when error is processed, then user sees toast "AI service temporarily busy" with "Retrying in X seconds".

- [ ] **AC 5.5.2:** Given Gemini quota is exhausted, when error is processed, then user sees inline banner "Daily AI limit reached" with "Contact admin" action button.

- [ ] **AC 5.5.3:** Given any LLM error occurs, when error is displayed, then a correlation ID is shown for support reference.

- [ ] **AC 5.5.4:** Given a transient error auto-retries successfully, when retry succeeds, then error toast auto-dismisses and operation completes normally.

- [ ] **AC 5.5.5:** Given 3 consecutive transient errors occur in the same session, when the 3rd error happens, then display escalates from toast to inline banner with "Contact support" option.

#### Story 5.6: Queue Depth Visibility Dashboard

- [ ] **AC 5.6.1:** Given admin accesses the dashboard, when queue-status endpoint is called, then response includes `pending`, `active`, and `failed` counts for each queue (default, high, low).

- [ ] **AC 5.6.2:** Given default queue has 150 pending jobs (threshold=100), when admin views dashboard, then queue widget shows alert indicator.

- [ ] **AC 5.6.3:** Given queue depth was 50 an hour ago and is now 100, when admin views dashboard, then trend arrow shows "increasing".

- [ ] **AC 5.6.4:** Given queue metrics haven't updated in >60 seconds, when admin views dashboard, then staleness warning "Data may be stale" is displayed.

#### Story 5.7: Processing ETA Display

- [ ] **AC 5.7.1:** Given 50 documents (varying page counts) are queued, when user views upload confirmation, then ETA shows range "15-45 minutes" with confidence indicator (not point estimate).

- [ ] **AC 5.7.2:** Given fewer than 10 historical completions exist, when ETA is calculated, then fallback estimate of 30s/doc is used.

- [ ] **AC 5.7.3:** Given processing completes for a batch, when user refreshes status, then ETA updates based on remaining queue and actual processing times.

- [ ] **AC 5.7.4:** Given ETA is displayed on upload confirmation, then message "You'll receive an email when ready" is also shown.

- [ ] **AC 5.7.5 (Self-Consistency):** Given a document completes processing in 45 seconds with 10 pages, when completion is recorded, then weighted processing time (4.5s/page) is added to rolling average.

---

## Additional Context

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| redis | existing | Queue inspection, metrics storage |
| celery | existing | Task queuing, beat schedule |
| structlog | existing | Structured logging |
| pydantic | v2 | Model validation |

### Testing Strategy

**Unit Tests:**
- `test_date_normalizer.py` - All date format variations
- `test_llm_error_handler.py` - All error type mappings
- `test_eta_calculator.py` - Rolling average, fallback, edge cases
- `test_queue_metrics.py` - Redis query mocking

**Integration Tests:**
- `test_consistency_validation.py` - End-to-end with real DB
- `test_queue_status_endpoint.py` - Admin auth + response format

**Critical Test Cases:**
```python
# Date normalization - must NOT flag as different
@pytest.mark.parametrize("date_a,date_b", [
    ("January 15, 2024", "2024-01-15"),
    ("Jan 15, 2024", "15 January 2024"),
    ("1/15/24", "01/15/2024"),
    ("15/01/2024", "2024-01-15"),  # Indian format
])
def test_same_date_different_formats(date_a, date_b):
    assert normalize_date(date_a) == normalize_date(date_b)

# ETA edge cases
def test_eta_empty_history_uses_fallback():
    eta = calculator.get_processing_eta(matter_id, pending=10)
    assert eta.seconds == 10 * 30  # fallback

def test_eta_accounts_for_workers():
    # 50 jobs, 5 workers, 30s avg = 5 minutes not 25
    eta = calculator.get_processing_eta(matter_id, pending=50)
    assert eta.seconds < 50 * 30
```

### Migration Required

```sql
-- supabase/migrations/YYYYMMDD_create_consistency_issues.sql

CREATE TABLE consistency_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    source_engine TEXT NOT NULL,
    source_finding_id UUID NOT NULL,
    source_value TEXT NOT NULL,
    target_engine TEXT NOT NULL,
    target_finding_id UUID NOT NULL,
    target_value TEXT NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'open',
    content_hash TEXT NOT NULL,
    dismissed_at TIMESTAMPTZ,
    dismissal_reason TEXT,
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_consistency_issues_matter_status ON consistency_issues(matter_id, status);
CREATE INDEX idx_consistency_issues_content_hash ON consistency_issues(content_hash);

-- RLS Policy
ALTER TABLE consistency_issues ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matters consistency issues"
ON consistency_issues FOR ALL
USING (
    matter_id IN (
        SELECT matter_id FROM matter_attorneys
        WHERE user_id = auth.uid()
    )
);
```

### Notes

- **Implementation Order:** 5.6 → 5.7 → 5.5 → 5.4 (queue depth feeds ETA; errors are independent; consistency is most complex)
- **Self-Consistency fix:** ETACalculator constructor should accept QueueMetricsService as dependency (for `get_active_worker_count()`). This makes the 5.6→5.7 dependency explicit.
- **Polling vs SSE:** MVP uses polling for simplicity. SSE can be added later for real-time updates.
- **Content Hash:** Use `hashlib.sha256(f"{source_value}|{target_value}|{document_id}".encode()).hexdigest()[:16]` for dismissal persistence. **MUST include document_id** to prevent cross-document collision (Red Team fix).
- **Worker Count:** Get from `celery_app.control.inspect().active()` or estimate from config.

---

**Tech-Spec Complete!**

Saved to: `_bmad-output/implementation-artifacts/tech-spec-epic5-operational-excellence.md`
