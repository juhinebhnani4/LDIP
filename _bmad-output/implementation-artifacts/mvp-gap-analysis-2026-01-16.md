# MVP Gap Analysis Report
**Date:** 2026-01-16
**Status:** ACTIVE - Source of Truth for Epic 14
**Author:** BMad Master (Gap Analysis Workflow)
**Scope:** Comprehensive analysis of MVP implementation gaps

---

## Document Control

| Property | Value |
|----------|-------|
| **Purpose** | Identify and document all gaps between MVP requirements and current implementation |
| **Source Documents** | Requirements-Baseline-v1.0.md, epics.md, all story files, backend code |
| **Related Epic** | Epic 14: MVP Gap Remediation |
| **Sprint Status** | `sprint-status.yaml` lines 212-236 |

---

## Methodology

This gap analysis was performed by:

1. **Reading Requirements-Baseline-v1.0.md** - Extracted all FR1-FR29 functional requirements
2. **Inventorying Backend API Routes** - Examined all 110 endpoints across 14 route files in `backend/app/api/routes/`
3. **Reviewing All Story Files** - Searched 75 story files in `_bmad-output/implementation-artifacts/` for:
   - Items marked "deferred", "later story", "follow-up story"
   - Unchecked task boxes `- [ ]`
   - TODO comments
   - "Mock data" usage notes
4. **Cross-Referencing** - Compared required functionality against actual implementation

---

## Gap Inventory

### GAP-API-1: Summary API Endpoint (CRITICAL)

**Status:** ❌ NOT IMPLEMENTED

**FR Reference:**
> **FR19: Summary Tab** - Display attention banner at top (items needing action: contradictions, citation issues with count and "Review All" link), show Parties section with Petitioner and Respondent cards including entity links and source citations, display Subject Matter with description and source links, show Current Status with last order date, description, and "View Full Order" link, display Key Issues numbered list with verification status badges (Verified/Pending/Flagged), show Matter Statistics cards (pages, entities, events, citations)...

**Required Endpoint:** `GET /api/matters/{matter_id}/summary`

**Evidence of Gap:**
- Story 10B.1 (line 279): *"The Summary API (`GET /api/matters/{matterId}/summary`) will be implemented in a later story. For this MVP, mock data is used with TODO comments for API integration."*
- Backend routes inventory: No `/summary` endpoint exists in `matters.py` or any other route file
- Frontend `useMatterSummary.ts` hook uses mock data

**What's Missing:**
- GPT-4 executive summary generation using top chunks, timeline, entities, last order
- Output structure matching `MatterSummary` TypeScript interface:
  - `attentionItems[]` - contradictions, citation issues, timeline gaps
  - `parties[]` - petitioner, respondent with entity links
  - `subjectMatter` - AI-generated description with sources
  - `currentStatus` - last order date, description
  - `keyIssues[]` - numbered list with verification status
  - `stats` - pages, entities, events, citations counts
- Redis caching with 1-hour TTL

**Impact:** Summary Tab displays only mock data. Attorneys cannot see real case summaries.

---

### GAP-API-2: Contradictions List Endpoint (CRITICAL)

**Status:** ❌ NOT IMPLEMENTED

**FR Reference:**
> **FR3: Consistency & Contradiction Engine** - Query all chunks mentioning a canonical entity_id from MIG, group statements by entity (e.g., "Nirav Jobalia" = "N.D. Jobalia" = "Mr. Jobalia"), compare statement pairs using GPT-4 chain-of-thought reasoning, detect contradiction types: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch, provide contradiction_explanation in natural language, assign severity (high/medium/low)...

> **FR23: Contradictions Tab** - Display contradictions grouped by entity (canonical name header, contradiction cards below), show contradiction cards with: contradiction type badge (semantic/factual/date_mismatch/amount_mismatch), severity indicator (high/medium/low), entity name, Statement 1 with document+page+excerpt+date, Statement 2 with document+page+excerpt+date, contradiction explanation in natural language, evidence links (click to view in PDF), implement inline verification on each contradiction...

**Required Endpoint:** `GET /api/matters/{matter_id}/contradictions`

**What Currently Exists:**
```
GET /api/matters/{matter_id}/contradictions/entities/{entity_id}/statements
POST /api/matters/{matter_id}/contradictions/entities/{entity_id}/compare
```

**Evidence of Gap:**
- Backend `contradiction.py` only has entity-specific endpoints
- No endpoint to list ALL contradictions across ALL entities for a matter
- FR23 requires: "Display contradictions grouped by entity" - implies a single endpoint returning all contradictions

**What's Missing:**
- `GET /api/matters/{matter_id}/contradictions` endpoint that:
  - Returns all detected contradictions for the matter
  - Groups by entity (canonical_name header)
  - Includes contradiction_type, severity, statements, explanation
  - Supports filtering by severity, entity, contradiction_type
  - Supports pagination

**Impact:** Contradictions Tab cannot display all contradictions. Must query per-entity which is impractical.

---

### GAP-API-3: Summary Verification APIs (HIGH)

**Status:** ❌ NOT IMPLEMENTED

**FR Reference:**
> **FR19: Summary Tab** - ...implement inline verification on each section ([✓ Verify] [✗ Flag] [💬 Note] buttons), implement editable sections with Edit button, preserve original AI version...

**Required Endpoints:**
- `POST /api/matters/{matter_id}/summary/verify`
- `POST /api/matters/{matter_id}/summary/notes`

**Evidence of Gap:**
- Story 10B.2 (line 678): *"Backend API endpoints for `POST /api/matters/{matterId}/summary/verify` and `POST /api/matters/{matterId}/summary/notes` need to be implemented in a follow-up story."*
- `useSummaryVerification` hook uses optimistic updates with local state only

**What's Missing:**
- Verify endpoint to persist verification decisions (approved/flagged) per summary section
- Notes endpoint to save attorney notes on summary sections
- Database table for summary verifications

**Impact:** Verification decisions on Summary Tab are not persisted. Lost on page refresh.

---

### GAP-STORY-1: Upload Stage 3-4 (CRITICAL)

**Status:** ❌ 0% COMPLETE - Story 9.5

**FR Reference:**
> **FR17: Upload & Processing Flow** - ...Stage 3 Upload Progress: file-by-file progress bars with checkmarks, Stage 4 Processing & Live Discovery: overall progress bar with stage indicator ("Stage 3 of 5: Extracting entities"), split view showing document processing (files received, pages extracted, OCR progress) and live discoveries panel (entities found with roles, dates extracted with earliest/latest, citations detected by Act, mini timeline preview, early insights with warnings), "Continue in Background" button for returning to dashboard...

**Evidence of Gap:**
- Story file `9-5-upload-stage-3-4.md` has ALL 11 tasks marked as unchecked `- [ ]`
- Tasks include:
  - Upload types extension
  - Store updates for processing state
  - UploadProgressView component
  - ProcessingProgressView component
  - LiveDiscoveriesPanel component
  - ProcessingScreen component
  - Route updates
  - Mock progress simulation
  - Matter card updates
  - Exports and tests

**What's Missing:**
- Entire Stage 3 UI (upload progress with file-by-file bars)
- Entire Stage 4 UI (processing progress + live discoveries panel)
- "Continue in Background" functionality
- WebSocket/SSE for real-time progress updates

**Impact:** Users cannot see upload/processing progress. No live discovery feedback during ingestion.

---

### GAP-API-4: Dashboard Real APIs (HIGH)

**Status:** ⚠️ MOCK DATA ONLY

**FR Reference:**
> **FR15: Dashboard/Home Page** - ...display activity feed (30% width) with icon-coded entries (green=success, blue=info, yellow=in progress, orange=attention, red=error), show quick stats panel (active matters, verified findings, pending reviews)

**Required Endpoints:**
- `GET /api/activity-feed` or `GET /api/matters/activity`
- `GET /api/stats/quick` or `GET /api/dashboard/stats`

**Evidence of Gap:**
- Story 9.3 (line 274): *"Future API Endpoints (not implemented yet) - Mock data pattern with Activities and stats using mock data, with TODO comments for backend integration."*

**What's Missing:**
- Activity feed API returning recent actions across matters
- Quick stats API returning aggregate counts (active matters, verified findings, pending reviews)

**Impact:** Dashboard shows hardcoded mock data. Not useful for real users.

---

### GAP-FE-1: Summary EditableSection Integration (HIGH)

**Status:** ❌ NOT INTEGRATED

**FR Reference:**
> **FR19: Summary Tab** - ...implement editable sections with Edit button, preserve original AI version, support Regenerate for fresh AI analysis...

**Evidence of Gap:**
- Story 10B.2 (line 674): *"The EditableSection component is fully functional and tested, but integration into Summary section components is deferred. Full edit mode integration should be implemented in a follow-up story when the backend API for saving edited content is ready."*

**What's Missing:**
- EditableSection component integration into PartiesSection, SubjectMatterSection, CurrentStatusSection, KeyIssuesSection
- Backend API for saving edited content
- "Regenerate" functionality for fresh AI analysis

**Impact:** Summary sections are read-only. Attorneys cannot edit AI-generated content.

---

### GAP-FE-2: Summary CitationLink Integration (HIGH)

**Status:** ❌ NOT INTEGRATED

**FR Reference:**
> **FR19: Summary Tab** - ...show clickable citation links on every factual claim with hover preview tooltip

**Evidence of Gap:**
- Story 10B.2 (line 676): *"The CitationLink component is fully functional and tested, but integration requires backend support for citation data in the Summary API response. Full CitationLink integration should be implemented when the Summary API returns structured citation data."*

**What's Missing:**
- CitationLink component integration into Summary sections
- Summary API returning structured citation data with document_id, page, bbox_id
- Hover preview tooltip showing citation context

**Impact:** Summary factual claims have no source links. Cannot click to verify in PDF.

---

### GAP-ORCH-1: Anomaly Detection Auto-Trigger (MEDIUM)

**Status:** ❌ MANUAL ONLY

**FR Reference:**
> **FR2: Timeline Construction Engine** - ...flag anomalies with warnings (e.g., "Notice dated 9 months after borrower default")...

**Evidence of Gap:**
- Story 4.4 (line 133): *"Task 4 - Integrate with timeline pipeline (DEFERRED - requires orchestration work). After entity linking completes, queue anomaly detection. Pipeline: extraction → classification → entity linking → anomaly detection. NOTE: Currently anomaly detection is triggered manually via POST /api/matters/{matter_id}/anomalies/detect"*

**What's Missing:**
- Automatic triggering of anomaly detection after entity linking completes
- Pipeline integration: extraction → classification → entity linking → **anomaly detection**
- Celery task chaining or event-driven trigger

**Impact:** Anomalies not automatically detected. Must manually call endpoint.

---

### GAP-FE-3: Timeline Real API Integration (MEDIUM)

**Status:** ⚠️ MOCK DATA WITH TODO

**FR Reference:**
> **FR20: Timeline Tab** - Implement three view modes: Vertical List (default, detailed chronological scroll), Horizontal Timeline (visual overview with zoom slider, event clusters, gap indicators), Multi-Track view...

**Evidence of Gap:**
- Story 10B.5 (line 81): *"Task 6.7: Comment realFetcher with TODO for backend filter support - Needs implementation when real API is available"*
- `useTimeline.ts` and `useTimelineStats.ts` have `realFetcher` commented out with eslint-disable

**What's Missing:**
- Switch from mock data to real API calls in useTimeline hooks
- Backend filter support for timeline queries (currently filters applied client-side)

**Impact:** Timeline Tab works but uses mock data patterns. Real API integration incomplete.

---

## Summary Table

| Gap ID | Type | Priority | FR Reference | Status |
|--------|------|----------|--------------|--------|
| GAP-API-1 | Backend API | 🔴 CRITICAL | FR19 | Not implemented |
| GAP-API-2 | Backend API | 🔴 CRITICAL | FR3, FR23 | Not implemented |
| GAP-STORY-1 | Story | 🔴 CRITICAL | FR17 | 0% complete |
| GAP-API-3 | Backend API | 🟠 HIGH | FR19 | Not implemented |
| GAP-API-4 | Backend API | 🟠 HIGH | FR15 | Mock data only |
| GAP-FE-1 | Frontend | 🟠 HIGH | FR19 | Not integrated |
| GAP-FE-2 | Frontend | 🟠 HIGH | FR19 | Not integrated |
| GAP-ORCH-1 | Pipeline | 🟡 MEDIUM | FR2 | Manual only |
| GAP-FE-3 | Frontend | 🟡 MEDIUM | FR20 | Mock data |

---

## Sprint Status Mapping

These gaps are tracked in `sprint-status.yaml` under Epic 14:

| Gap ID | Sprint Status ID | Description |
|--------|-----------------|-------------|
| GAP-API-1 | 14-1-summary-api-endpoint | GET /api/matters/{id}/summary |
| GAP-API-2 | 14-2-contradictions-list-api | GET /api/matters/{id}/contradictions |
| GAP-STORY-1 | 14-3-upload-stage-3-4 | Story 9.5 completion |
| GAP-API-3 | 14-4-summary-verification-api | POST verify + notes |
| GAP-API-4 | 14-5-dashboard-real-apis | Activity feed + quick stats |
| GAP-FE-1 + GAP-FE-2 | 14-6-summary-fe-integration | EditableSection + CitationLink |
| GAP-ORCH-1 | 14-7-anomaly-auto-trigger | Pipeline integration |
| GAP-FE-3 | 14-8-timeline-real-api | Switch from mock to real |

---

## Deferred Tests (Non-Blocking)

These test gaps are tracked but not blocking MVP:

| Source | Deferred Item |
|--------|---------------|
| Story 2B.3 (line 103) | Backend integration tests for OCR |
| Story 2B.3 (line 106) | Frontend component tests for OCR |
| Story 11.3 (line 124) | useSSE hook tests |
| Story 11.3 (line 128) | Streaming integration tests |
| Story 10D.3 (line 320+) | Documents component tests |

---

## Recommendations

### Immediate Actions (Before MVP Release)

1. **Implement GAP-API-1 (Summary API)** - Highest user-facing impact
2. **Implement GAP-API-2 (Contradictions List)** - FR23 requirement unfulfilled
3. **Complete GAP-STORY-1 (Upload Stage 3-4)** - Core user flow incomplete

### Secondary Actions

4. **Implement GAP-API-3 (Summary Verification)** - Persist verification decisions
5. **Implement GAP-API-4 (Dashboard APIs)** - Replace mock data
6. **Complete GAP-FE-1/2 (Summary Integration)** - Full FR19 compliance

### Can Defer

7. **GAP-ORCH-1 (Anomaly Auto-Trigger)** - Manual trigger is acceptable workaround
8. **GAP-FE-3 (Timeline Real API)** - UI works, just needs API switch

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-16 | Initial gap analysis created | BMad Master |

---

*This document is the source of truth for Epic 14: MVP Gap Remediation. Update this document when gaps are resolved.*
