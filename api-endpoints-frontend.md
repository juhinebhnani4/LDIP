# Frontend API Endpoints Status

**Last Updated:** 2026-01-16
**Version:** 2.0 (Cleaned up and verified)

---

## Executive Summary

| Category | Count |
|----------|-------|
| Total API Endpoints Defined | ~55 |
| Connected to Real Backend | ~52 |
| Using Mock Data (by design) | 3 |

---

## API Client Layer (`frontend/src/lib/api/`)

All endpoints below are **connected to the real backend**.

| API File | Endpoint | Methods |
|----------|----------|---------|
| `client.ts` | `/api/v1/` (base) | GET, POST, PUT, PATCH, DELETE |
| `matters.ts` | `/api/matters` | GET, POST |
| | `/api/matters/{matterId}` | GET, PATCH, DELETE |
| | `/api/matters/{matterId}/members` | GET, POST |
| | `/api/matters/{matterId}/members/{userId}` | PATCH, DELETE |
| `documents.ts` | `/api/documents/upload` | POST |
| | `/api/matters/{matterId}/documents` | GET |
| | `/api/documents/{documentId}` | GET, PATCH, DELETE |
| | `/api/documents/bulk` | PATCH |
| | `/api/documents/{documentId}/ocr-quality` | GET |
| | `/api/documents/{documentId}/request-manual-review` | POST |
| `search.ts` | `/api/matters/{matterId}/search` | POST |
| | `/api/matters/{matterId}/search/bm25` | POST |
| | `/api/matters/{matterId}/search/semantic` | POST |
| | `/api/matters/{matterId}/search/rerank` | POST |
| `entities.ts` | `/api/matters/{matterId}/entities` | GET |
| | `/api/matters/{matterId}/entities/{entityId}` | GET |
| | `/api/matters/{matterId}/entities/{entityId}/mentions` | GET |
| | `/api/matters/{matterId}/entities/merge` | POST |
| | `/api/matters/{matterId}/entities/{entityId}/aliases` | POST, DELETE |
| `chunks.ts` | `/api/documents/{documentId}/chunks` | GET |
| | `/api/chunks/{chunkId}` | GET |
| | `/api/chunks/{chunkId}/context` | GET |
| | `/api/chunks/{chunkId}/parent` | GET |
| | `/api/chunks/{chunkId}/children` | GET |
| `citations.ts` | `/api/matters/{matterId}/citations` | GET |
| | `/api/matters/{matterId}/citations/{citationId}` | GET |
| | `/api/matters/{matterId}/citations/summary/by-act` | GET |
| | `/api/matters/{matterId}/citations/stats` | GET |
| | `/api/matters/{matterId}/citations/acts/discovery` | GET |
| | `/api/matters/{matterId}/citations/acts/mark-uploaded` | POST |
| | `/api/matters/{matterId}/citations/acts/mark-skipped` | POST |
| | `/api/matters/{matterId}/citations/verify` | POST |
| | `/api/matters/{matterId}/citations/{citationId}/verify` | POST |
| | `/api/matters/{matterId}/citations/{citationId}/verification` | GET |
| | `/api/matters/{matterId}/citations/{citationId}/split-view` | GET |
| `bounding-boxes.ts` | `/api/documents/{documentId}/bounding-boxes` | GET |
| | `/api/documents/{documentId}/pages/{pageNumber}/bounding-boxes` | GET |
| | `/api/chunks/{chunkId}/bounding-boxes` | GET |
| `jobs.ts` | `/api/jobs/matters/{matterId}` | GET |
| | `/api/jobs/matters/{matterId}/stats` | GET |
| | `/api/jobs/{jobId}` | GET |
| | `/api/jobs/documents/{documentId}/active` | GET |
| | `/api/jobs/{jobId}/retry` | POST |
| | `/api/jobs/{jobId}/skip` | POST |
| | `/api/jobs/{jobId}/cancel` | POST |
| `verifications.ts` | `/api/matters/{matterId}/verifications/stats` | GET |
| | `/api/matters/{matterId}/verifications/pending` | GET |
| | `/api/matters/{matterId}/verifications` | GET |
| | `/api/matters/{matterId}/verifications/{id}/approve` | POST |
| | `/api/matters/{matterId}/verifications/{id}/reject` | POST |
| | `/api/matters/{matterId}/verifications/{id}/flag` | POST |
| | `/api/matters/{matterId}/verifications/bulk` | POST |
| `chat.ts` | `/api/v1/session/{matterId}/{userId}` | GET |
| | `/api/v1/session/{matterId}/{userId}/archived` | GET |

---

## Stores & Hooks - Current Status

### Connected to Real Backend

| Location | API Used | Status |
|----------|----------|--------|
| `matterStore.ts` | `mattersApi.list()` | Fixed (was `getMockMatters()`) |
| `useTimeline.ts` | `/api/matters/{id}/timeline/full` | Fixed (was `MOCK_EVENTS`) |
| `useTimelineStats.ts` | `/api/matters/{id}/timeline/stats` | Fixed (was `MOCK_STATS`) |

### Using Mock Data (By Design - No Backend Endpoint)

| Location | What It Uses | Reason | Recommended Action |
|----------|--------------|--------|-------------------|
| `activityStore.ts` | `getMockActivities()` | No `/api/activities` endpoint planned in PRD | Return `[]` or derive from timeline events |
| `activityStore.ts` | `getMockStats()` | No unified dashboard stats endpoint | Compute from `mattersApi` + `verificationsApi.getStats()` |
| `useMatterSummary.ts` | `MOCK_SUMMARY` | Backend endpoint not yet implemented | See "Summary Endpoint" section below |

---

## Summary Tab Endpoint Clarification

### `/api/matters/{matterId}/summary`

**Status:** NOT IMPLEMENTED
**Is it MVP or Phase 2?** BOTH - see clarification below

**From Story 10B.1 Task 8.3:**
> "Define mock data for MVP (actual summary generation is Phase 2)"

**From Story 10B.1 Dev Notes:**
> "The Summary API (`GET /api/matters/{matterId}/summary`) will be implemented in a later story."

### What This Means

| Component | Scope | Status |
|-----------|-------|--------|
| Summary Tab UI (frontend) | MVP | Done |
| Basic summary endpoint (aggregates existing data) | MVP | Not implemented (deferred) |
| AI-generated content (subject matter, key issues) | Phase 2 | Not started |

**The design decision was intentional:** The frontend uses mock data for MVP because:
1. The basic aggregation endpoint was deferred
2. AI-generated content is Phase 2

**For MVP completion**, a basic endpoint could aggregate from:
- `/api/matters/{id}/entities` (parties)
- `/api/matters/{id}/timeline` (current status from latest order)
- `/api/matters/{id}/citations` (stats)
- `/api/matters/{id}/verifications/stats` (attention items)

**For Phase 2**, add:
- LLM-generated subject matter description
- LLM-synthesized key issues

---

## Design Decisions Explained

### Why no `/api/activities` endpoint?

Per PRD Story 9.3, the "activity feed" is derived data from matter events, not a separate API.

**Solution:** Aggregate from timeline events OR return empty array.

### Why no `/api/dashboard/stats` endpoint?

PRD FR15 shows "quick stats panel" but these are computed client-side from:
- **Active matters:** `mattersApi.list()` filtered by status
- **Verified findings:** `verificationsApi.getStats()`
- **Pending reviews:** `verificationsApi.getStats()`

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-16 | v2.0 - Fixed `useTimelineStats.ts` to use real API. Cleaned up document, removed contradictions, clarified Summary Tab scope. |
| 2026-01-15 | v1.0 - Initial analysis document with multiple passes (messy). |
