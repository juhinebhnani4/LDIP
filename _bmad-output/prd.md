---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - '_bmad-output/analysis/brainstorming-session-2026-01-25.md'
  - '_bmad-output/project-planning-artifacts/epics-large-pdf-chunking/index.md'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 1
  projectDocs: 1
workflowType: 'prd'
lastStep: 11
project_name: 'LDIP'
user_name: 'Juhi'
date: '2026-01-25'
prd_scope: 'User Experience First - 6 User-Facing Reliability Issues'
---

# Product Requirements Document - LDIP

**Author:** Juhi
**Date:** 2026-01-25

## Executive Summary

LDIP (Legal Document Intelligence Platform) is a production SaaS B2B platform that transforms how legal professionals analyze documents through AI-powered extraction, timeline construction, contradiction detection, and intelligent Q&A.

This PRD addresses **6 critical user-facing reliability issues** identified through a comprehensive pipeline audit. These issues undermine user trust by creating situations where the platform appears to work but delivers incorrect or incomplete results.

### The Problem

Legal professionals depend on accurate source citations and complete responses to make critical decisions. Currently:
- **48% of timeline events** point to the wrong source page — users click and don't find the referenced text
- **Chat responses silently truncate** when SSE parsing fails — users receive incomplete answers without warning
- **"p. ?" appears in citations** — confusing references that should show actual page numbers
- **Entity extraction failures look like empty results** — users can't distinguish "no entities" from "extraction failed"
- **Real-time updates stop silently** — pipeline progress disappears when WebSocket connections fail
- **API requests hang indefinitely** — the UI freezes with no timeout or error feedback

### What Makes This Special

**Trust Recovery Through Transparency**

This PRD converts silent failures into visible, actionable feedback. When something goes wrong, users will know:
- *What* failed
- *Why* it happened (when possible)
- *What to do* next

The goal isn't just to fix bugs — it's to rebuild confidence that when LDIP shows a citation, that citation is accurate; when it completes a response, that response is complete.

## Project Classification

**Technical Type:** SaaS B2B Platform (web_app + api_backend)
**Domain:** LegalTech
**Complexity:** Medium (focused fixes, not architectural changes)
**Project Context:** Brownfield - extending existing production system

**Existing Tech Stack:**
- Backend: FastAPI, Celery, Redis, Supabase (PostgreSQL)
- Frontend: Next.js, TypeScript
- AI/ML: Google Document AI, OpenAI, Gemini, Cohere
- Real-time: WebSocket, Server-Sent Events (SSE)

**Scope:** 6 user-facing reliability issues prioritized for maximum trust impact

## Success Criteria

### User Success

**The Trust Test:** When a legal professional clicks 10 citations in a row, every one lands on the correct page with the referenced text visible.

- **Citation Accuracy:** Users find the referenced text when clicking any source link
- **Complete Responses:** Chat answers arrive in full — no silent truncation
- **Clear Feedback:** When something fails, users see an error message with next steps
- **Reliable Progress:** Pipeline status always reflects actual processing state

### Business Success

- **Support Ticket Reduction:** "Citation wrong" and "response incomplete" complaints drop by >80%
- **User Confidence:** Reduced manual citation verification (measurable via session replay)
- **Trust Metrics:** User-reported confidence in LDIP accuracy improves in feedback surveys

### Technical Success

| Issue | Current | Target | Measurement |
|-------|---------|--------|-------------|
| Timeline source pages | 48% wrong | <5% wrong | DB: `source_page = 1` concentration |
| SSE JSON parsing | Silent skip | 0 silent failures | Error toast on parse failure |
| "p. ?" citations | Appears | 0 occurrences | Regex validation in responses |
| Entity extraction | Empty = error | Distinct states | UI: "Extraction failed" vs "No entities" |
| WebSocket reconnection | Dead silently | Auto-reconnect | "Reconnecting..." indicator |
| Frontend timeout | Hangs forever | 30s timeout | No requests >30s unresolved |

### Measurable Outcomes

- **Zero silent failures** — Every error produces user-visible feedback
- **<5% citation page errors** — Down from 48%
- **100% timeout coverage** — All frontend requests have bounded wait times
- **Automatic recovery** — WebSocket reconnects without user intervention

## Product Scope

### MVP — This Release

All 6 user-facing reliability issues:
1. Fix timeline event source page detection (48% → <5%)
2. Handle SSE malformed JSON with error visibility
3. Eliminate "p. ?" citation bug
4. Distinguish entity extraction empty vs error states
5. Implement WebSocket auto-reconnection with indicator
6. Add frontend fetch timeouts with error feedback

### Growth Features (Post-MVP)

From audit Tier 2 (infrastructure hardening):
- Circuit breaker for Redis/Celery broker
- Increased RAG context window (5 → 15-20 chunks)
- Distributed locks for task idempotency
- Explicit embedding/rerank fallback indicators

### Vision (Future)

Full reliability overhaul covering audit Tiers 3-4:
- Dead Letter Queue for failed tasks
- Cascade delete transactions
- Comprehensive chaos testing
- Pattern testing suite for safety guardrails

## User Journeys

### Journey 1: Priya Sharma — The Missed Citation (Before Fix)

Priya is a senior associate at a mid-size litigation firm preparing for a critical hearing tomorrow. She's using LDIP to build a timeline of events from 47 case documents. At 11 PM, she finds the perfect evidence — the timeline shows "Defendant signed agreement on March 15" with a source citation to Document 23, Page 8.

She clicks the citation to verify the exact wording for her brief. The PDF viewer opens to Page 1 — a cover letter. She scrolls through the 45-page document, searching for the agreement date. After 10 minutes, she finds it on Page 23, not Page 8. She starts questioning every other citation she's used.

For the next two hours, Priya manually verifies every timeline event she plans to cite. By 1 AM, she's found 4 more wrong page numbers. She finishes her brief at 3 AM, exhausted and uncertain whether she missed anything.

*Issues exposed: Timeline source page detection (48% wrong), citation accuracy*

### Journey 2: Amit Patel — The Incomplete Answer (Before Fix)

Amit is a junior lawyer researching precedents for a contract dispute. He asks LDIP: "What are the key cases involving force majeure clauses in supply chain agreements?" The response starts streaming — he sees three relevant cases with summaries appearing.

Suddenly, the response stops. The last visible text reads: "In Raj Industries v. Global Logistics (2019), the court held that..." — and nothing more. No error message, no indication something went wrong. Amit waits 30 seconds. A minute. He refreshes the page, losing the partial response entirely.

He asks the same question again. This time it completes. But Amit doesn't know if this answer includes what was cut off before, or if the first response had additional cases he'll never see. He spends 20 minutes manually searching to ensure he hasn't missed anything.

*Issues exposed: SSE malformed JSON silent skip, no error feedback*

### Journey 3: Meera Krishnan — The Frozen Screen (Before Fix)

Meera is a paralegal uploading 12 new documents to a matter. She drags the files, sees "Uploading..." and the progress bar reaches 100%. Then nothing. The "Processing" indicator shows for Document 1. She waits. And waits.

After 5 minutes, she opens a new tab and checks the Documents list — all 12 documents show "Processing." She goes back to the upload screen — still frozen on Document 1. Is it working in the background? Did something fail? Should she re-upload?

She messages IT support. An hour later, support confirms 8 documents completed successfully, but 4 had OCR failures. Meera never saw any notification. She re-uploads the 4 failed documents and watches them succeed this time — but has lost an hour of productive work.

*Issues exposed: WebSocket dead silently, frontend hangs forever, no error notifications*

### Journey 4: Priya Sharma — Trusting LDIP Again (After Fix)

Three months later, same scenario. Priya is preparing for another hearing, reviewing a timeline of 52 events. She clicks a citation — it opens directly to Page 23, Paragraph 3, with the exact text highlighted in yellow. She clicks four more citations in quick succession. Every one lands precisely where it should.

On the sixth click, she sees a brief toast: "Could not locate exact text position — showing page 15 where this content appears." The system couldn't find the precise bounding box, but told her where to look and why.

Priya finishes her brief in 2 hours, confident in every citation. She doesn't manually verify anything — the system earned her trust back.

*Success demonstrated: Accurate page detection, graceful degradation with clear feedback*

### Journey 5: Support Staff — Diagnosing Issues (Before vs After)

**Before:** Support receives a ticket: "LDIP keeps showing wrong pages." They have no logs showing which citations failed, no way to reproduce the issue, no visibility into why page detection chose page 1. They ask users to manually report each bad citation.

**After:** Support sees a dashboard showing "15 citations this week fell back to chunk page (bbox not found)" with document IDs, user IDs, and the specific text that failed to match. They can proactively reach out to affected users and prioritize OCR quality improvements for problematic document types.

*Success demonstrated: Error visibility, monitoring capability, proactive support*

### Journey Requirements Summary

| Journey | User Type | Key Capabilities Required |
|---------|-----------|--------------------------|
| Priya (Before) | Legal Professional | Accurate page detection, citation verification |
| Amit (Incomplete) | Legal Professional | SSE error handling, completion indicators, retry |
| Meera (Frozen) | Paralegal | WebSocket reliability, progress accuracy, error notifications |
| Priya (After) | Legal Professional | Bbox accuracy, graceful degradation, confidence indicators |
| Support Staff | Internal Ops | Error logging, monitoring dashboards, proactive diagnostics |

## Technical Requirements

### Backend Changes (Python/FastAPI)

| Fix | Files Affected | Change Type |
|-----|----------------|-------------|
| Timeline page detection | `date_extractor.py:256`, `storage.py:156-161` | Logic fix — use bbox page instead of chunk page |
| "p. ?" citation bug | `generator.py:229-266` | Regex fix — improve post-processing |
| Entity extraction error state | `extractor.py:309-325` | Return type change — distinguish empty vs error |
| WebSocket reconnection | `main.py:111-120`, `pubsub_service.py` | Add Redis health check + reconnect logic |

### Frontend Changes (TypeScript/Next.js)

| Fix | Files Affected | Change Type |
|-----|----------------|-------------|
| SSE malformed JSON | `useSSE.ts:399` | Error handling — show toast instead of silent skip |
| Frontend timeout | `apiClient.ts` | Add 30s timeout to all fetch calls |
| WebSocket indicator | `useWebSocket.ts` | Add "Reconnecting..." UI state |
| Entity extraction UI | Entities components | Show "Extraction failed" vs "No entities found" |

### Real-time Stack Considerations

**WebSocket Reconnection Strategy:**
- Detect disconnect via heartbeat timeout (30s no message)
- Show "Reconnecting..." indicator immediately
- Exponential backoff: 1s → 2s → 4s → 8s → max 30s
- Re-subscribe to matter topics on reconnect
- Queue missed updates during disconnect (if feasible)

**SSE Error Handling:**
- Wrap JSON.parse in try/catch
- On parse error: show error toast with "Response interrupted — please retry"
- Log malformed chunk to console for debugging
- Don't silently continue with partial data

### Database Considerations

**No schema changes required.** All fixes use existing tables:
- `bounding_boxes` — already has page numbers
- `citations` / `events` — already have `source_page` column
- Fix is in the *logic* that populates these fields, not the schema

### Monitoring & Alerting

**New log patterns to add:**
- `sse_json_parse_failed` — count of SSE parse errors
- `websocket_reconnection` — count of reconnects per user session
- `citation_page_fallback` — when bbox lookup fails and falls back
- `entity_extraction_failed` — distinguish from empty result

**Dashboard metrics:**
- Citation page accuracy: `COUNT(source_page != 1) / COUNT(*)` per matter
- SSE error rate: parse failures / total chunks
- WebSocket health: reconnections / hour
- Entity extraction success rate

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — Fix core trust-breaking issues before any new features
**Resource Requirements:** 1-2 developers, ~2-3 weeks estimated

This scope is intentionally tight. These 6 issues were prioritized from 200+ audit findings specifically because they:
1. Directly impact user trust
2. Are user-visible (not infrastructure)
3. Have clear success metrics
4. Don't require architectural changes

### MVP Feature Set (Phase 1) — This Release

**Core User Journeys Supported:**
- Priya's citation accuracy journey → Fix #1, #3
- Amit's complete response journey → Fix #2
- Meera's reliable progress journey → Fix #5, #6
- Support's diagnostic journey → All fixes include logging

**Must-Have Capabilities (All 6 Fixes):**

| # | Fix | User Value | Effort |
|---|-----|------------|--------|
| 1 | Timeline source page detection | Citations land on correct page | Medium |
| 2 | SSE malformed JSON handling | Responses don't silently truncate | Low |
| 3 | "p. ?" citation bug | Clean, professional references | Low |
| 4 | Entity extraction error states | Clear feedback on failures | Low |
| 5 | WebSocket auto-reconnection | Reliable real-time updates | Medium |
| 6 | Frontend fetch timeouts | No frozen UI states | Low |

### Post-MVP Features (Phase 2) — Next Sprint

From audit Tier 2 (infrastructure hardening):
- Circuit breaker for Redis/Celery broker
- Increased RAG context window (5 → 15-20 chunks)
- Distributed locks for task idempotency
- Explicit embedding/rerank fallback indicators
- JWKS cache TTL refresh

### Expansion Features (Phase 3) — Backlog

From audit Tiers 3-4 (full reliability overhaul):
- Dead Letter Queue for failed Celery tasks
- Cascade delete transactions
- Comprehensive chaos testing suite
- Pattern testing for safety guardrails
- Multi-language date format support

### Risk Mitigation Strategy

**Technical Risks:**
- *Page detection logic change* — Test with documents that currently fail; run before/after comparison on existing matters
- *WebSocket reconnection* — May need Redis health monitoring; fallback to polling if reconnect fails

**Market Risks:**
- *None* — These are fixes to existing product, not market validation

**Resource Risks:**
- *If constrained:* Prioritize fixes #1, #2, #5 (highest user impact)
- *Minimum viable:* Even fixing just #1 (page detection) would significantly improve trust

## Functional Requirements

### Citation Accuracy

- FR1: System can detect the correct source page from bounding box data when displaying timeline events
- FR2: System can fall back to chunk-level page detection when bounding box data is unavailable
- FR3: Users can see which page number will be displayed before clicking a citation link
- FR4: System can process citation page references without producing "p. ?" output
- FR5: System can log when page detection falls back to chunk page for monitoring purposes

### Response Completeness

- FR6: Users can see an error notification when SSE stream contains malformed JSON
- FR7: System can detect SSE parse failures and display user-visible feedback
- FR8: Users can understand when a chat response was interrupted vs completed normally
- FR9: System can log SSE parse errors with sufficient context for debugging

### Error Visibility & Feedback

- FR10: Users can distinguish between "no entities found" and "entity extraction failed" states
- FR11: Users can see clear error messages when backend operations fail
- FR12: Users can understand what action to take when an error occurs
- FR13: System can display contextual error messages with actionable next steps

### Real-time Connection Reliability

- FR14: System can detect when WebSocket connection is lost
- FR15: System can automatically attempt to reconnect WebSocket connections
- FR16: Users can see a "Reconnecting..." indicator when WebSocket is disconnecting
- FR17: System can re-subscribe to relevant topics after WebSocket reconnection
- FR18: Users can continue using the application during WebSocket reconnection attempts

### Request Timeout Handling

- FR19: System can enforce maximum wait times on all frontend API requests
- FR20: Users can see feedback when a request is taking longer than expected
- FR21: Users can see an error message when a request times out
- FR22: System can cancel and cleanup requests that exceed timeout thresholds

### Monitoring & Diagnostics

- FR23: Support staff can view citation page accuracy metrics per matter
- FR24: Support staff can view SSE error rates and patterns
- FR25: Support staff can view WebSocket connection health metrics
- FR26: Support staff can view entity extraction success/failure rates
- FR27: System can log all reliability events with sufficient context for debugging

## Non-Functional Requirements

### Performance

- **NFR1**: Frontend API requests must timeout after 30 seconds maximum
- **NFR2**: WebSocket reconnection attempts must begin within 1 second of disconnect detection
- **NFR3**: Error toast notifications must appear within 500ms of error detection
- **NFR4**: Citation page detection must not add perceptible latency to timeline/citation display

### Reliability

- **NFR5**: WebSocket connections must automatically reconnect with exponential backoff (1s → 2s → 4s → 8s → 30s max)
- **NFR6**: SSE parse failures must never silently fail — all errors produce user-visible feedback
- **NFR7**: Citation page accuracy must be ≥95% (down from 52% current failure rate)
- **NFR8**: Zero frontend requests may hang indefinitely without timeout or error feedback
- **NFR9**: Entity extraction must clearly distinguish error states from empty results in 100% of cases

### Observability

- **NFR10**: All reliability-related errors must be logged with sufficient context for debugging (user ID, matter ID, error type, timestamp)
- **NFR11**: Citation page fallback events must be countable in monitoring dashboards
- **NFR12**: SSE parse errors must be trackable per user session
- **NFR13**: WebSocket reconnection events must be trackable per hour/day
- **NFR14**: Support staff must be able to access reliability metrics without engineering involvement

