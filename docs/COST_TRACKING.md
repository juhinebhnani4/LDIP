# LLM Cost Tracking System — How It Works

> Internal reference doc. Explains how every LLM call in jaanch.ai gets priced,
> recorded, and surfaced on the admin usage dashboard.

---

## Table of Contents

1. [High-Level Flow](#1-high-level-flow)
2. [What Gets Tracked](#2-what-gets-tracked)
3. [Pricing — How Costs Are Calculated](#3-pricing--how-costs-are-calculated)
4. [Backend: The Cost Tracker](#4-backend-the-cost-tracker)
5. [Database: Where Costs Live](#5-database-where-costs-live)
6. [API Endpoint: Serving the Dashboard](#6-api-endpoint-serving-the-dashboard)
7. [Frontend: The Usage Dashboard](#7-frontend-the-usage-dashboard)
8. [All Tracked Operations (Complete List)](#8-all-tracked-operations-complete-list)
9. [Provider Routing — Why Each Model Is Used](#9-provider-routing--why-each-model-is-used)
10. [Cost Attribution — How Costs Map to Matters & Documents](#10-cost-attribution--how-costs-map-to-matters--documents)
11. [Query-Level Cost Grouping (Correlation IDs)](#11-query-level-cost-grouping-correlation-ids)
12. [Configuration Knobs](#12-configuration-knobs)

---

## 1. High-Level Flow

```
 LLM call happens        Cost recorded           Stored in DB         Shown on dashboard
 (backend service)   →   (CostTracker)       →   (llm_costs table)  →  (admin/usage page)
```

**Step by step:**

1. A backend service (e.g. citation extractor, RAG generator) makes an LLM API call.
2. After the call returns, a `CostTracker` object calculates the cost from the
   token counts and the provider's per-token pricing.
3. The tracker persists a row into the `llm_costs` Supabase table with all the
   details — provider, operation, tokens, cost in USD and INR, duration, matter ID,
   document ID, and a `metadata` JSONB blob containing the correlation ID and
   optional cache hit info.
4. The admin dashboard frontend calls `GET /api/admin/usage?year=2026&month=2`.
5. The backend queries `llm_costs`, aggregates by date/provider/operation/matter,
   and returns the summary.
6. The frontend renders charts and cards.

There are **two persistence paths** because costs happen in two different contexts:

| Context | Where | Persistence Method |
|---------|-------|--------------------|
| **Query-side** (user asks a question) | FastAPI async endpoint | `await persist_cost(tracker)` |
| **Worker-side** (document processing) | Celery worker task | `persist_cost_sync(tracker)` |

Both insert into the same `llm_costs` table.

---

## 2. What Gets Tracked

Every row in the `llm_costs` table captures:

| Field | What it is |
|-------|-----------|
| `provider` | Which LLM model (e.g. `gpt-4o`, `gemini-2.5-flash`) |
| `operation` | What the call was for (e.g. `citation_extraction`, `rag_generation`) |
| `input_tokens` | Tokens sent to the model |
| `output_tokens` | Tokens received back |
| `total_cost_usd` | Calculated USD cost |
| `total_cost_inr` | Calculated INR cost (primary currency) |
| `matter_id` | Which matter this cost belongs to (all 26 tracked sites now pass this) |
| `document_id` | Which document (worker-side ops pass this; query-side ops use `NULL`) |
| `duration_ms` | How long the API call took |
| `metadata` | JSONB with `correlation_id`, optional `cached_input_tokens` and `cache_hit_rate` |
| `created_at` | Timestamp |

---

## 3. Pricing — How Costs Are Calculated

All pricing is hardcoded in `backend/app/core/cost_tracking.py` (lines ~118-171).
Last updated: **Feb 2026**. Sources: openai.com/api/pricing, ai.google.dev/gemini-api/docs/pricing.

> **Future plan**: Move pricing to a `llm_model_pricing` Supabase table and
> exchange rates to an `fx_rates` table with a daily API sync. This avoids
> code deploys just to update a price. Each `llm_costs` row already snapshots
> the rate used at insert time, so historical data won't change.

### Per-Token Providers

| Provider | Model ID | Input (per 1K tokens) | Output (per 1K tokens) |
|----------|----------|-----------------------|------------------------|
| GPT-4 Turbo | `gpt-4-turbo-preview` | $0.0100 | $0.0300 |
| GPT-4o | `gpt-4o` | $0.0025 | $0.0100 |
| GPT-4o Mini | `gpt-4o-mini` | $0.00015 | $0.0006 |
| GPT-3.5 Turbo | `gpt-3.5-turbo` | $0.0005 | $0.0015 |
| Embeddings (Small) | `text-embedding-3-small` | $0.00002 | $0.0000 |
| Embeddings (Large) | `text-embedding-3-large` | $0.00013 | $0.0000 |
| Gemini 2.5 Flash | `gemini-2.5-flash` | $0.0003 | $0.0025 |
| Gemini 1.5 Pro | `gemini-1.5-pro` | $0.00125 | $0.0050 |

### Per-Unit Providers (NOT per-token)

| Provider | Model ID | Pricing | Unit |
|----------|----------|---------|------|
| Cohere Rerank | `rerank-v3.5` | $2.00 per 1K searches | per search |
| Google Document AI | `document-ai` | $60.00 per 1K pages ($0.06/page) | per page |

### Cost Formula

```
input_cost  = (input_tokens / 1000) * input_price_per_1k
output_cost = (output_tokens / 1000) * output_price_per_1k
total_usd   = input_cost + output_cost
total_inr   = total_usd * 90.50          # fixed exchange rate (Feb 2026)
```

**Example** — A GPT-4o call with 500 input tokens and 150 output tokens:
```
input_cost  = (500 / 1000) * $0.0025 = $0.00125
output_cost = (150 / 1000) * $0.01   = $0.0015
total_usd   = $0.00275
total_inr   = $0.00275 * 90.50 = Rs 0.25
```

---

## 4. Backend: The Cost Tracker

**Core file:** `backend/app/core/cost_tracking.py`

### Key Classes

**`CostTracker`** — Created per LLM call. Tracks tokens, calculates costs.

```python
# Typical usage inside a backend service:
tracker = CostTracker(
    provider=LLMProvider.GEMINI_FLASH,
    operation="citation_extraction",
    matter_id=matter_id,       # Always pass when available
    document_id=document_id,   # Always pass when available
)

response = await gemini_client.generate_content(prompt)   # actual LLM call

tracker.add_tokens(
    input_tokens=response.usage_metadata.prompt_token_count,
    output_tokens=response.usage_metadata.candidates_token_count,
    cached_input_tokens=response.usage_metadata.cached_content_token_count,  # Gemini prefix caching
)
tracker.log_cost()                    # structured log line
await persist_cost(tracker)           # save to DB
```

For per-unit providers like Cohere or Document AI:
```python
tracker.add_units(num_pages)          # instead of add_tokens()
```

**`CostPersistenceService`** — Handles DB inserts.
- `save_cost(tracker)` — Insert a single cost record (auto-injects `correlation_id` from request context)
- `save_batch(trackers)` — Batch insert for efficiency

**`QuotaMonitoringService`** — Monitors daily/monthly usage against limits.
- Tracks tokens used vs quota per provider
- Projects exhaustion dates from 7-day rolling average
- Alerts at 80% threshold

### Persistence Flow

```
CostTracker.log_cost()
    |
persist_cost(tracker)  or  persist_cost_sync(tracker)
    |
CostPersistenceService.save_cost()
    |
    |-- Auto-injects correlation_id from request context (get_correlation_id())
    |-- Auto-injects cached_input_tokens / cache_hit_rate if prefix caching was used
    |
supabase.table("llm_costs").insert({...}).execute()
```

---

## 5. Database: Where Costs Live

### Table: `llm_costs`

Migrations:
- `20260122000003_create_llm_costs_table.sql` — Initial table creation
- `20260218000001_llm_costs_preserve_on_matter_delete.sql` — Changed `matter_id` and `document_id` foreign keys from `ON DELETE CASCADE` to `ON DELETE SET NULL`, so deleting a matter preserves all historical cost records (just nullifies the FK)

```sql
CREATE TABLE llm_costs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id       UUID REFERENCES matters(id) ON DELETE SET NULL,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    entity_id       UUID,
    provider        VARCHAR(100),          -- e.g. 'gpt-4o'
    operation       VARCHAR(100),          -- e.g. 'citation_extraction'
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    input_cost_usd  NUMERIC(10,8),
    output_cost_usd NUMERIC(10,8),
    total_cost_usd  NUMERIC(10,8),
    input_cost_inr  NUMERIC(12,4),
    output_cost_inr NUMERIC(12,4),
    total_cost_inr  NUMERIC(12,4),
    usd_to_inr_rate NUMERIC(6,2),
    duration_ms     INTEGER,
    metadata        JSONB DEFAULT '{}',    -- Contains correlation_id, cache info
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

**Indexes** (for fast dashboard queries):
- `idx_llm_costs_matter` — matter_id lookups
- `idx_llm_costs_provider` — filter by provider
- `idx_llm_costs_operation` — filter by operation
- `idx_llm_costs_created_at` — time-range queries
- `idx_llm_costs_matter_provider_op` — composite for aggregations

**RLS:** Users can only see costs for matters they're attorneys on.

**ON DELETE behavior:** `matter_id` and `document_id` use `ON DELETE SET NULL` (not CASCADE). This means deleting a matter or document preserves all cost history — the FK just becomes NULL. This is critical for accurate monthly cost reporting.

### Table: `llm_quota_limits`

Stores per-provider quotas (daily/monthly token + cost limits).

---

## 6. API Endpoint: Serving the Dashboard

**Endpoint:** `GET /api/admin/usage`
**File:** `backend/app/api/routes/admin/quota.py` (line ~661)
**Access:** Admin-only

**Query params:**
- `year` (int, optional) — defaults to current year
- `month` (int 1-12, optional) — defaults to current month

**What it does:**
1. Queries all `llm_costs` rows for the given month
2. Aggregates into four groups:
   - **Daily** — spend per day (for the bar chart)
   - **By Provider** — spend per LLM model
   - **By Operation** — spend per operation type
   - **By Matter** — top 20 matters by spend
3. Returns totals: spend USD/INR, total tokens, total requests, budget

**Response shape:**
```json
{
  "month": "2026-02",
  "totalSpendUsd": 26.27,
  "totalSpendInr": 2348.76,
  "budgetUsd": 120.00,
  "totalTokens": 10400000,
  "totalRequests": 6851,
  "dailySpend": [
    { "date": "2026-02-04", "spendUsd": 0.77, "spendInr": 64.30, "requests": 12, "tokens": 85000 }
  ],
  "byProvider": [
    { "provider": "gpt-4o", "spendUsd": 1.05, "requests": 60, "inputTokens": 180000, "outputTokens": 180300 }
  ],
  "byOperation": [
    { "operation": "summary_subject_matter", "spendUsd": 1.50, "requests": 20 }
  ],
  "byMatter": [
    { "matterId": "91a4a4db-...", "spendUsd": 6.04, "requests": 180 }
  ]
}
```

---

## 7. Frontend: The Usage Dashboard

**Page:** `frontend/src/app/(dashboard)/admin/usage/page.tsx`
**Hook:** `frontend/src/hooks/useUsageDashboard.ts`
**URL:** `/admin/usage` (admin-only)

### What the hook does

```typescript
const { data, isLoading, error, refresh } = useUsageDashboard(year, month);
```

- Fetches from `GET /api/admin/usage?year=YYYY&month=M`
- Auto-polls every 60 seconds while the tab is visible
- Stops polling when tab is hidden (saves API calls)
- Provides manual `refresh()` function

### What the page shows

| Section | Visual | Data Source |
|---------|--------|-------------|
| **Total Spend** | Card with USD + INR | `totalSpendUsd`, `totalSpendInr` |
| **Budget** | Progress bar with % | `totalSpendUsd / budgetUsd * 100` |
| **Tokens** | Card with formatted count | `totalTokens` |
| **Requests** | Card with count | `totalRequests` |
| **Daily Spend** | Vertical bar chart (Recharts) | `dailySpend[]` array |
| **By Provider** | Progress bars with labels | `byProvider[]` array |
| **By Operation** | Horizontal bar chart (Recharts) | `byOperation[]` array |
| **Top Matters** | Progress bars | `byMatter[]` array |

**Budget color coding:**
- Green: < 70% of budget
- Yellow: 70-90% of budget
- Red: > 90% of budget

**Special label:** Cohere Rerank shows "units" instead of "tokens" since it uses
per-search pricing, not per-token.

---

## 8. All Tracked Operations (Complete List)

### Worker-Side (Document Processing Pipeline)

These run in Celery workers when a document is uploaded and processed:

| Operation | Provider | What It Does | File |
|-----------|----------|-------------|------|
| `ocr_document_ai` | Document AI | OCR to extract text from PDF pages | `services/ocr/processor.py` |
| `ocr_validation` | Gemini Flash | Validates low-confidence OCR words | `services/ocr/gemini_validator.py` |
| `entity_extraction` | Gemini Flash | Extracts people/orgs/dates from chunks | `services/mig/extractor.py` |
| `entity_extraction_batch` | Gemini Flash | Mega-batch extraction (5 chunks/call) | `services/mig/extractor.py` |
| `entity_alias_resolution` | Gemini Flash | Resolves entity aliases (e.g. "JHM" = "Jyoti H. Mehta") | `services/mig/entity_resolver.py` |
| `entity_alias_extraction` | Gemini Flash | Extracts alias patterns from entity contexts | `services/mig/entity_resolver.py` |
| `citation_extraction` | Gemini Flash | Extracts legal citations from chunks | `engines/citation/extractor.py` |
| `citation_extraction_batch` | Gemini Flash | Batch citation extraction (3 chunks/call) | `engines/citation/extractor.py` |
| `citation_extraction_sync` | Gemini Flash | Synchronous citation extraction fallback | `engines/citation/extractor.py` |
| `citation_verification` | Gemini Flash | Verifies citation accuracy against source | `engines/citation/verifier.py` |
| `citation_act_validation` | Gemini Flash | Validates act names via LLM | `engines/citation/validation.py` |
| `date_extraction` | Gemini Flash | Extracts dates/events from chunks | `engines/timeline/date_extractor.py` |
| `event_classification` | Gemini Flash | Classifies timeline events by type | `engines/timeline/event_classifier.py` |
| `event_classification_batch` | Gemini Flash | Batch event classification | `engines/timeline/event_classifier.py` |
| `event_classification_fallback` | Gemini Flash | Fallback classification for failed events | `engines/timeline/event_classifier.py` |
| `event_classification_importance` | Gemini Flash | Rates event importance (1-5) | `engines/timeline/event_classifier.py` |
| `timeline_entity_linking` | Gemini Flash | Links entities mentioned in events | `engines/timeline/entity_linker.py` |
| `contradiction_screening` | Gemini Flash | Quick screen for contradictions (tier 1) | `engines/contradiction/comparator.py` |
| `contradiction_comparison` | GPT-4o | Deep contradiction analysis (tier 2) | `engines/contradiction/comparator.py` |
| `contradiction_classification` | GPT-4o | Classifies contradiction severity/type | `engines/contradiction/classifier.py` |
| `embedding_batch` | Embeddings (Small) | Generates vector embeddings for chunks | `services/rag/embedder.py` |
| `security_injection_scan` | Gemini Flash | Scans document content for prompt injection | `services/security/injection_detector.py` |
| `summary_subject_matter` | GPT-4o | Generates matter subject summary | `services/summary_service.py` |
| `summary_key_issues` | GPT-4o | Generates key issues summary | `services/summary_service.py` |
| `summary_current_status` | GPT-4o | Generates current status summary | `services/summary_service.py` |
| `summary_subject_matter_retry` | GPT-4o | Retry when placeholder detected in summary | `services/summary_service.py` |

### Query-Side (User Asks a Question)

These run in the FastAPI server when a user sends a query:

| Operation | Provider | What It Does | File |
|-----------|----------|-------------|------|
| `conversation_summarization` | Gemini Flash | Summarizes conversation history for context | `services/memory/summarizer.py` |
| `query_rewrite` | Gemini Flash | Rewrites query for better retrieval | `engines/rag/generator.py` |
| `intent_classification` | GPT-3.5 Turbo | Classifies query intent (citation/timeline/search) | `engines/orchestrator/intent_analyzer.py` |
| `multi_intent_refine` | GPT-3.5 Turbo | Breaks multi-part questions into sub-queries | `engines/orchestrator/intent_analyzer.py` |
| `embedding_single` | Embeddings (Small) | Embeds user query for vector search | `services/rag/embedder.py` |
| `search_rerank` | Cohere Rerank | Reranks search results by relevance | `services/rag/reranker.py` |
| `rag_generation` | Gemini Flash | Generates answer from retrieved context | `engines/rag/generator.py` |
| `safety_subtle_detection` | GPT-4o Mini | Checks query for subtle policy violations | `services/safety/subtle_detector.py` |
| `safety_language_policing` | GPT-4o Mini | Sanitizes response language (legal tone) | `services/safety/language_police.py` |

### Dashboard Category Mapping

The usage dashboard groups operations into categories for the "By Operation" chart:

| Dashboard Category | Operations |
|--------------------|------------|
| **Entities** | `entity_extraction`, `entity_extraction_batch`, `entity_alias_resolution`, `entity_alias_extraction`, `timeline_entity_linking` |
| **Summary** | `summary_subject_matter`, `summary_key_issues`, `summary_current_status`, `summary_subject_matter_retry` |
| **Contradictions** | `contradiction_screening`, `contradiction_comparison`, `contradiction_classification` |
| **OCR** | `ocr_document_ai`, `ocr_validation` |
| **Timeline** | `date_extraction`, `event_classification`, `event_classification_batch`, `event_classification_fallback`, `event_classification_importance` |
| **Q&A** | `rag_generation`, `query_rewrite`, `conversation_summarization` |
| **Safety** | `safety_subtle_detection`, `safety_language_policing`, `security_injection_scan` |
| **Intent** | `intent_classification`, `multi_intent_refine` |
| **Embedding** | `embedding_single`, `embedding_batch` |
| **Search** | `search_rerank`, `citation_extraction`, `citation_extraction_batch`, `citation_extraction_sync`, `citation_verification`, `citation_act_validation` |

---

## 9. Provider Routing — Why Each Model Is Used

| Provider | Cost Tier | Used For | Reasoning |
|----------|-----------|----------|-----------|
| **GPT-4o** | Mid-range ($0.0025/$0.01 per 1K) | Contradiction detection, matter summaries | Strong reasoning at 75% lower cost than GPT-4 Turbo |
| **GPT-4 Turbo** | Expensive ($0.01/$0.03 per 1K) | Legacy (historical cost records only) | Replaced by GPT-4o in Feb 2026 |
| **GPT-4o Mini** | Very cheap ($0.00015/$0.0006) | Safety checks, language policing | Good enough for classification, 200x cheaper than GPT-4 |
| **GPT-3.5 Turbo** | Cheap ($0.0005/$0.0015) | Intent classification | Simple classification, doesn't need GPT-4 level reasoning |
| **Gemini 2.5 Flash** | Budget LLM ($0.0003/$0.0025 per 1K) | Entity/citation/date extraction, RAG generation, OCR validation, query rewrite, conversation summarization | High volume worker tasks — cheapest option for bulk processing. Supports prefix caching for repeated system instructions |
| **Embeddings (Small)** | Tiny ($0.00002) | Vector search | Only option, no output tokens |
| **Cohere Rerank** | Per-search ($0.002/search) | Search result reranking | Specialized reranker, per-search pricing. Used in `search_with_rerank_and_library()` which combines rerank + library search with a shared pre-computed query embedding |
| **Document AI** | Per-page ($0.06/page) | OCR text extraction | Google's production OCR, per-page pricing |

**Two-tier contradiction detection:**
1. Gemini Flash screens first (cheap, fast) — if confidence > 85%, done
2. GPT-4o only for uncertain/contradictory results (accurate, 75% cheaper than GPT-4 Turbo)

This saves ~90% on contradiction costs vs using GPT-4 Turbo for everything.

---

## 10. Cost Attribution — How Costs Map to Matters & Documents

Every `CostTracker` instance now receives `matter_id` and/or `document_id` so costs
can be attributed to specific matters and documents. This was completed across all
26 tracked sites in Feb 2026.

### Worker-Side Attribution

Worker tasks always have `matter_id` and `document_id` in scope from the Celery
task arguments. These are threaded through to every `CostTracker` call:

```python
# In a Celery task:
def process_document(document_id: str, matter_id: str):
    tracker = CostTracker(
        provider=LLMProvider.GEMINI_FLASH,
        operation="entity_extraction",
        matter_id=matter_id,
        document_id=document_id,
    )
```

### Query-Side Attribution

Query-side operations get `matter_id` from the chat request context. There is no
`document_id` for query-side ops (they operate across all documents in a matter):

```python
# In a FastAPI endpoint handler:
tracker = CostTracker(
    provider=LLMProvider.OPENAI_GPT4O_MINI,
    operation="safety_subtle_detection",
    matter_id=matter_id,  # from request
)
```

### Attribution Coverage

| Scope | Sites | matter_id | document_id |
|-------|-------|-----------|-------------|
| Worker-side (document processing) | 17 | All pass | All pass |
| Query-side (user queries) | 9 | All pass | N/A (no single doc) |
| **Total** | **26** | **26/26** | **17/17** |

### "Top Matters by Cost" Dashboard

Because every cost record has `matter_id`, the usage dashboard can show a "Top
Matters by Cost" section ranking the most expensive matters. This helps identify
which matters are driving LLM spend.

---

## 11. Query-Level Cost Grouping (Correlation IDs)

### Problem

A single user query triggers 6-9 LLM calls (intent classification, embedding,
reranking, RAG generation, safety checks, language policing, etc.). Without
grouping, you can't answer "how much did this one query cost?"

### Solution

Every HTTP request gets a `correlation_id` (UUID) assigned by middleware. The
`CostPersistenceService.save_cost()` method auto-injects this into the `metadata`
JSONB field:

```python
# In save_cost() — automatic, no caller changes needed:
"metadata": {
    **(metadata or {}),
    **({"cached_input_tokens": ..., "cache_hit_rate": ...}
       if tracker.cached_input_tokens > 0 else {}),
    **({"correlation_id": cid}
       if (cid := get_correlation_id()) else {}),
},
```

### Querying Costs for a Single Query

```sql
-- Find all costs for a specific query (from structured logs or API response):
SELECT operation, provider, total_cost_inr, total_cost_usd, input_tokens, output_tokens
FROM llm_costs
WHERE metadata->>'correlation_id' = '76a21c6d-ad66-4cfb-8ecb-bd556b0d565e'
ORDER BY created_at;
```

**Example output** (real query from Feb 2026):

| Operation | Provider | Cost (INR) | Tokens |
|-----------|----------|-----------|--------|
| conversation_summarization | gemini-2.5-flash | 0.0192 | 659+6 |
| query_rewrite | gemini-2.5-flash | 0.005 | 51+16 |
| safety_subtle_detection | gpt-4o-mini | 0.0183 | 1047+75 |
| multi_intent_refine | gpt-3.5-turbo | 0.0308 | 459+74 |
| embedding_single | text-embedding-3-small | ~0 | 16+0 |
| search_rerank | rerank-v3.5 | 0.0002 | 1 search |
| rag_generation | gemini-2.5-flash | 0.1599 | 2846+365 |
| safety_language_policing | gpt-4o-mini | 0.0295 | 760+354 |
| **Total** | | **0.2629** | **5839+890** |

### Limitations

- `correlation_id` is only available on **query-side** costs (FastAPI request context).
  Worker-side costs (Celery tasks) do not have a correlation ID.
- The correlation ID is stored in `metadata` JSONB, not a top-level indexed column.
  For high-volume querying, consider adding a dedicated `correlation_id` column with
  an index in a future migration.

---

## 12. Configuration Knobs

In `backend/app/core/config.py`:

| Setting | Default | What It Controls |
|---------|---------|-----------------|
| `monthly_cost_budget_usd` | `120.0` | Budget shown on dashboard |
| `policing_llm_timeout` | `15.0` | Timeout for language policing LLM call (seconds). Set to 15s because gpt-4o-mini needs ~5-6s to process full RAG responses in JSON mode |
| `safety_llm_timeout` | `10.0` | Timeout for safety detection LLM call (seconds) |
| `safety_llm_enabled` | `True` | Enable/disable LLM safety checks |
| `policing_llm_enabled` | `True` | Enable/disable LLM language policing |
| `contradiction_model_routing_enabled` | `True` | Enable two-tier routing (Gemini screen + GPT-4 escalation) |
| `contradiction_screening_confidence_threshold` | `0.85` | Below this, escalate to GPT-4 |
| `citation_batching_enabled` | `True` | Batch 3 chunks per Gemini call (saves API calls) |
| `citation_batch_size` | `3` | Chunks per batch call |
| `entity_extraction_batch_size` | `5` | Chunks per mega-batch extraction call |

### Language Policing Pipeline

The language policing pipeline uses a two-layer approach:

1. **Regex pass** — instant, always runs (23 patterns for legal terminology)
2. **LLM polish** — gpt-4o-mini rewrites the response for professional legal tone

Configuration:
- `MAX_RETRIES = 1` — Only one LLM attempt (was 3; reduced to prevent SSE timeout)
- `policing_llm_timeout = 15.0` — Hard timeout per attempt (was 20.0)
- **Worst-case pipeline impact**: 1 attempt x 15s = 15s (vs old: 3 x 20s = 60s)
- **Typical latency**: ~5-6s for a standard RAG response (~1000 chars)

If the LLM times out or fails, the regex-only result is used as a graceful fallback.
The response is never blocked — only potentially less polished.

All settings can be overridden via environment variables (e.g. `MONTHLY_COST_BUDGET_USD=200`).
