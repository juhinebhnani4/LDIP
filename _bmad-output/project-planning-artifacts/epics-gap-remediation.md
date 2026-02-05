---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
workflowStatus: complete
inputDocuments:
  - "_bmad-output/analysis/first-principles-gap-analysis-2026-01-26.md"
projectType: brownfield
---

# LDIP Gap Remediation - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for LDIP gap remediation, decomposing the 58 gaps identified in the First Principles Gap Analysis into implementable stories organized by phase.

**Source:** First Principles Gap Analysis (2026-01-26)
**Project Context:** Brownfield - extending existing production system
**Analysis Methods:** 20 advanced elicitation methods across 4 phases
**Total Gaps:** 58 → All mapped to FRs with gap # traceability
**Timeline:** 18 weeks across 10 phases (Phases 7-9 optional for MVP)
**Coverage:** Security Gate (2) + Phases 1-6 (22) + Phases 7-9 (24) + Backlog (10) = 58 gaps

---

## Requirements Inventory

### Functional Requirements

#### Security Gate (Must Pass Before Phase 1)

- FR-SG1: Prompt injection defense - implement structured XML prompts between system and content; add LLM detection for suspicious documents (~$0.001/doc) [Gap #2]
- FR-SG2: Embedding version tracking - store model version with each embedding; implement migration path for model upgrades [Gap #3]

#### Phase 1: Foundation (Week 1-2)

- FR1.1: Zombie job detection via Redis heartbeat (30s TTL) with automatic recovery via `job_recovery` Celery beat task [Gap #4]
- FR1.2: Batch verification UI with multi-select, bulk approve/reject, and keyboard navigation [Gap #7]
- FR1.3: File size limits enforcement (50MB default) via validation middleware in upload endpoint [Gap #13]

#### Phase 2: Compliance & UX (Week 3-4)

- FR2.1: Configurable verification gates per matter - default=acknowledgment required, "Court-ready mode"=100% verification required [Gap #1]
- FR2.2: Entity split functionality via soft merge with `merged_into_id` FK; split = set FK to NULL; preserve original entity mentions [Gap #6]
- FR2.3: Proactive token refresh - background refresh 5 minutes before expiry; silent retry on 401 [Gap #12]
- FR2.4: Keyboard shortcuts for verification - Y=approve, N=reject, S=skip, J/K=navigate queue [Gap #18]

#### Phase 3: Legal Defensibility (Week 5-6)

- FR3.1: Reasoning trace storage - tiered approach with structured summaries (hot, 30-day retention) and full LLM logs (cold, S3 Glacier) [Gap #5]
- FR3.2: Court-ready certification stamp on exports - show verification %, attorney sign-off, timestamp [Gap #17]

#### Phase 4: Operational Excellence (Week 7-8)

- FR4.1: Email notification on processing completion via SendGrid/Resend integration [Gap #19]
- FR4.2: LLM quota monitoring dashboard - widget showing usage vs limits; alert at 80% threshold [Gap #14]
- FR4.3: Cross-engine correlation - timeline to contradiction links; entity journey visualization [Gap #15]
- FR4.4: Cross-engine consistency checking - compare timeline dates vs citation dates; flag conflicts automatically [Gap #50]
- FR4.5: User-friendly LLM errors - contextual error messages when OpenAI/Gemini APIs fail; actionable recovery suggestions [Gap #39]
- FR4.6: Queue depth visibility - dashboard showing pending jobs per queue; processing backlog metrics [Gap #41]
- FR4.7: Processing ETA - estimated completion time based on queue depth and historical processing rates [Gap #42]

#### Phase 5: User Adoption (Week 9-10)

- FR5.1: Progressive disclosure UI - hide advanced features behind toggles; "Power user" mode setting [Gap #9]
- FR5.2: Onboarding flow - first-run wizard; demo "Sample Case" matter with pre-loaded data [Gap #10]
- FR5.3: Workflow modes - quick scan vs deep analysis toggle per matter (`analysis_mode` column) [Gap #8]

#### Phase 6: Enterprise Features (Week 11-12)

- FR6.1: User-facing cost tracking - per-matter cost widget with daily/weekly rollup [Gap #22]
- FR6.2: Monthly cost report by practice group - breakdown with CSV/PDF export [Gap #21]
- FR6.3: Data residency controls - region selector; route API calls to regional endpoints [Gap #20]

#### Phase 7: Chaos Resilience (Week 13-14) [Optional for MVP]

- FR7.1: Per-document pipeline isolation - wrap each document in try/catch; continue on failure [Gap #45]
- FR7.2: Atomic transaction rollback - DB transactions for multi-step operations; cleanup service on failure [Gap #46]
- FR7.3: Job persistence before acknowledgment - write job to DB before Redis ack; recover from DB on restart [Gap #37]
- FR7.4: Worker memory limits - configure Celery memory limits; restart on OOM [Gap #43]
- FR7.5: Session persistence fallback - write session to DB as backup; failover on Redis down [Gap #35]
- FR7.6: Orphan chunk cleanup - detect and remove orphaned chunks after worker crashes; scheduled cleanup job [Gap #34]
- FR7.7: Rate limit fallback mode - degrade gracefully when Redis rate limiting unavailable; in-memory fallback [Gap #36]
- FR7.8: Graceful search degradation - return partial results when OpenAI embeddings unavailable; BM25-only fallback [Gap #38]
- FR7.9: Retry cost controls - cap retry attempts per job; exponential backoff with max cost limits [Gap #40]
- FR7.10: Priority queue lanes - separate queues for urgent vs batch jobs; priority-based worker allocation [Gap #44]

#### Phase 8: Intelligence Improvements (Week 15-16) [Optional for MVP]

- FR8.1: Cross-entity contradiction detection - compare statements between entities, not just within single entity [Gap #49]
- FR8.2: Synonym expansion in search - use WordNet or embedding similarity for query expansion [Gap #31]
- FR8.3: Flag unknown timeline participants - mark mentions not linked to known entities [Gap #48]
- FR8.4: Citation granularity - store sentence-level positions, not just chunk-level [Gap #30]
- FR8.5: Completeness verification - detect if extraction missed content; confidence scoring for coverage [Gap #29]
- FR8.6: Entity resolver confidence tracking - store and display confidence scores for entity resolution decisions [Gap #47]

#### Phase 9: Governance & Compliance (Week 17-18) [Optional for MVP]

- FR9.1: SLA documentation and monitoring - define SLAs; uptime monitoring; alerting [Gap #51]
- FR9.2: Data retention policy - define retention periods; implement auto-purge jobs [Gap #53]
- FR9.3: Algorithm documentation - document each engine's logic for regulatory transparency [Gap #57]
- FR9.4: Self-service matter restore - admin UI to restore soft-deleted matters [Gap #54]
- FR9.5: Deletion alert to owner - email matter owner when member deletes [Gap #56]
- FR9.6: Conflict of interest detection - flag when opposing parties in different matters share entities [Gap #52]
- FR9.7: Point-in-time backup - enable restoration to specific timestamps; PITR for PostgreSQL [Gap #55]
- FR9.8: Bias testing framework - automated tests for AI fairness; demographic parity checks [Gap #58]

#### Backlog (Deferred)

- FR-BL1: Fallback OCR provider (high effort) [Gap #11]
- FR-BL2: Resumable uploads (medium effort) [Gap #16]
- FR-BL3: Exhaustive contradiction mode (high effort) [Gap #23]
- FR-BL4: Passage importance scoring (high effort) [Gap #24]
- FR-BL5: Regional date format testing (low effort) [Gap #25]
- FR-BL6: SSO integration - Azure AD (high effort) [Gap #26]
- FR-BL7: Data flow audit documentation (medium effort) [Gap #27]
- FR-BL8: ROI metrics dashboard - calculate and display return on investment per matter (medium effort) [Gap #28]
- FR-BL9: Adaptive search fusion - dynamically adjust BM25/semantic weighting based on query type (medium effort) [Gap #32]
- FR-BL10: Search learning from behavior - improve search relevance based on user click patterns (high effort) [Gap #33]

### Non-Functional Requirements

- NFR1: **Security** - All prompts must use structured XML boundaries between system and content (ADR-001)
- NFR2: **Reliability** - Worker heartbeat every 30 seconds with stale key detection and automatic job recovery (ADR-003)
- NFR3: **Storage** - 30-day hot retention for reasoning traces, then S3 Glacier cold storage (ADR-002)
- NFR4: **Compliance** - Audit log captures all verification acknowledgments, overrides, and export decisions (ADR-005)
- NFR5: **Cost** - LLM prompt injection detection adds ~$0.001 per document (ADR-001)
- NFR6: **Data Integrity** - Soft merge preserves original entity nodes; split restores via NULL FK (ADR-004)

### Additional Requirements (Phase 0 Root Cause Initiatives)

These parallel initiatives address 35 gaps systemically:

| Initiative | Gaps Addressed | Owner | Deliverables |
|------------|----------------|-------|--------------|
| Lawyer Advisory Board | 12 | PM | Monthly meetings with 3-5 practicing lawyers; charter document; structured feedback loop |
| AI-Specific Threat Model | 8 | Security | Quarterly AI security reviews; adversarial testing framework; threat model document |
| Staging Environment | 5 | DevOps | Production-like load testing; chaos experiment pipeline; synthetic load generation |
| Error Scenario Specs | 3 | PM + Dev | Feature spec template with mandatory failure modes section |

---

## Architecture Decision Records

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Prompt isolation + LLM detection | Defense in depth; ~$0.001/doc detection cost; structured XML boundaries |
| ADR-002 | Tiered storage (summary hot, full cold) | Balance cost and query speed; 30-day hot retention then S3 Glacier |
| ADR-003 | Redis heartbeat for job recovery | Matches existing infrastructure; 30s TTL; `job_recovery` Celery beat task |
| ADR-004 | Soft merge with `merged_into_id` FK | Low complexity; easy split via NULL; preserve original mentions |
| ADR-005 | Configurable verification gate | Flexible compliance; default=acknowledgment; court-ready=100% |

---

## Stakeholder Priorities

| Stakeholder | Top 3 Priorities | Gaps |
|-------------|------------------|------|
| Senior Partner | Explainability, Mandatory verification, Court-ready certification | FR3.1, FR2.1, FR3.2 |
| Associate | Batch verification, Entity split, Keyboard shortcuts | FR1.2, FR2.2, FR2.4 |
| Paralegal | Resumable uploads, Processing status, Email notifications | FR-BL2, FR4.1 |
| IT Admin | Prompt injection, Data flow audit, Data residency | FR-SG1, FR-BL7, FR6.3 |
| CFO | Cost tracking, Usage analytics, ROI metrics | FR6.1, FR6.2 |

---

## FR Coverage Map

| Epic | FRs Covered | Gaps | Phase | Theme |
|------|-------------|------|-------|-------|
| Epic 0 | Systemic initiatives | 35 (via root causes) | 0 (Parallel) | Root Cause Initiatives |
| Epic 1 | FR-SG1, FR-SG2 | #2, #3 | Security Gate | Security Foundation |
| Epic 2 | FR1.1-FR1.3 | #4, #7, #13 | 1 | Foundation Fixes |
| Epic 3 | FR2.1-FR2.4 | #1, #6, #12, #18 | 2 | Compliance & UX |
| Epic 4 | FR3.1-FR3.2 | #5, #17 | 3 | Legal Defensibility |
| Epic 5 | FR4.1-FR4.7 | #14, #15, #19, #39, #41, #42, #50 | 4 | Operational Excellence |
| Epic 6 | FR5.1-FR5.3 | #8, #9, #10 | 5 | User Adoption |
| Epic 7 | FR6.1-FR6.3 | #20, #21, #22 | 6 | Enterprise Features |
| Epic 8* | FR7.1-FR7.10 | #34, #35, #36, #37, #38, #40, #43, #44, #45, #46 | 7 | Chaos Resilience |
| Epic 9* | FR8.1-FR8.6 | #29, #30, #31, #47, #48, #49 | 8 | Intelligence |
| Epic 10* | FR9.1-FR9.8 | #51, #52, #53, #54, #55, #56, #57, #58 | 9 | Governance |
| Backlog | FR-BL1-FR-BL10 | #11, #16, #23, #24, #25, #26, #27, #28, #32, #33 | - | Deferred |

*Epics 8-10 are Optional for MVP*

### Gap Coverage Summary

| Category | Count | Status |
|----------|-------|--------|
| Security Gate | 2 | ✓ Mapped |
| Phase 1-6 (MVP) | 22 | ✓ Mapped |
| Phase 7-9 (Optional) | 24 | ✓ Mapped |
| Backlog | 10 | ✓ Mapped |
| **Total Explicit** | **58** | **✓ Complete** |

---

## Epic List

1. **Epic 0: Root Cause Initiatives** - Systemic fixes addressing 35 gaps via 4 initiatives (Phase 0, parallel)
2. **Epic 1: Security Foundation** - 2 gaps: Pass/fail security gate (Pre-Phase 1)
3. **Epic 2: Foundation Fixes** - 3 gaps: Silent failure prevention and batch operations (Phase 1, Week 1-2)
4. **Epic 3: Compliance & UX** - 4 gaps: Verification gates and user productivity (Phase 2, Week 3-4)
5. **Epic 4: Legal Defensibility** - 2 gaps: Explainability and court-ready exports (Phase 3, Week 5-6)
6. **Epic 5: Operational Excellence** - 7 gaps: Reliability, visibility, cross-engine intelligence (Phase 4, Week 7-8)
7. **Epic 6: User Adoption** - 3 gaps: Progressive disclosure and onboarding (Phase 5, Week 9-10)
8. **Epic 7: Enterprise Features** - 3 gaps: Firm-wide controls and reporting (Phase 6, Week 11-12)
9. **Epic 8: Chaos Resilience** - 10 gaps: Infrastructure failure survival [Optional] (Phase 7, Week 13-14)
10. **Epic 9: Intelligence Improvements** - 6 gaps: Smarter search and insights [Optional] (Phase 8, Week 15-16)
11. **Epic 10: Governance & Compliance** - 8 gaps: Regulatory readiness [Optional] (Phase 9, Week 17-18)
12. **Backlog** - 10 gaps: Deferred items for future consideration

---

## Gap Traceability Matrix (All 58 Gaps)

| Gap # | Description | FR | Phase |
|-------|-------------|-----|-------|
| 1 | Configurable verification gates | FR2.1 | 2 |
| 2 | Prompt injection defense | FR-SG1 | Security Gate |
| 3 | Embedding version tracking | FR-SG2 | Security Gate |
| 4 | Zombie job detection | FR1.1 | 1 |
| 5 | Reasoning trace/explainability | FR3.1 | 3 |
| 6 | Entity split (only merge) | FR2.2 | 2 |
| 7 | Batch verification UI | FR1.2 | 1 |
| 8 | Workflow modes (quick vs deep) | FR5.3 | 5 |
| 9 | Progressive disclosure UI | FR5.1 | 5 |
| 10 | Onboarding flow | FR5.2 | 5 |
| 11 | Fallback OCR provider | FR-BL1 | Backlog |
| 12 | Proactive token refresh | FR2.3 | 2 |
| 13 | File size limits enforced | FR1.3 | 1 |
| 14 | LLM quota monitoring | FR4.2 | 4 |
| 15 | Cross-engine correlation | FR4.3 | 4 |
| 16 | Resumable uploads | FR-BL2 | Backlog |
| 17 | Court-ready certification stamp | FR3.2 | 3 |
| 18 | Keyboard shortcuts for verification | FR2.4 | 2 |
| 19 | Email notification on completion | FR4.1 | 4 |
| 20 | Data residency controls | FR6.3 | 6 |
| 21 | Monthly cost report by practice | FR6.2 | 6 |
| 22 | User-facing cost tracking | FR6.1 | 6 |
| 23 | Exhaustive contradiction mode | FR-BL3 | Backlog |
| 24 | Passage importance scoring | FR-BL4 | Backlog |
| 25 | Regional date format testing | FR-BL5 | Backlog |
| 26 | SSO integration (Azure AD) | FR-BL6 | Backlog |
| 27 | Data flow audit documentation | FR-BL7 | Backlog |
| 28 | ROI metrics dashboard | FR-BL8 | Backlog |
| 29 | Completeness verification | FR8.5 | 8 |
| 30 | Citation granularity (sentence-level) | FR8.4 | 8 |
| 31 | Synonym expansion in search | FR8.2 | 8 |
| 32 | Adaptive search fusion | FR-BL9 | Backlog |
| 33 | Search learning from behavior | FR-BL10 | Backlog |
| 34 | Orphan chunk cleanup | FR7.6 | 7 |
| 35 | Session persistence fallback | FR7.5 | 7 |
| 36 | Rate limit fallback mode | FR7.7 | 7 |
| 37 | Jobs persisted before ack | FR7.3 | 7 |
| 38 | Graceful search degradation | FR7.8 | 7 |
| 39 | User-friendly LLM errors | FR4.5 | 4 |
| 40 | Retry cost controls | FR7.9 | 7 |
| 41 | Queue depth visibility | FR4.6 | 4 |
| 42 | Processing ETA | FR4.7 | 4 |
| 43 | Worker memory limits | FR7.4 | 7 |
| 44 | Priority queue lanes | FR7.10 | 7 |
| 45 | Per-document pipeline isolation | FR7.1 | 7 |
| 46 | Atomic transaction rollback | FR7.2 | 7 |
| 47 | Entity resolver confidence tracking | FR8.6 | 8 |
| 48 | Timeline flag unknown participants | FR8.3 | 8 |
| 49 | Cross-entity contradiction detection | FR8.1 | 8 |
| 50 | Cross-engine consistency checking | FR4.4 | 4 |
| 51 | SLA documentation/monitoring | FR9.1 | 9 |
| 52 | Conflict of interest detection | FR9.6 | 9 |
| 53 | Data retention policy | FR9.2 | 9 |
| 54 | Self-service matter restore | FR9.4 | 9 |
| 55 | Point-in-time backup | FR9.7 | 9 |
| 56 | Deletion alert to owner | FR9.5 | 9 |
| 57 | Algorithm documentation | FR9.3 | 9 |
| 58 | Bias testing framework | FR9.8 | 9 |

**Total: 58 gaps → 58 FRs mapped ✓**

---

## Epic 1: Security Foundation

**Goal:** Establish pass/fail security gate protecting against prompt injection and embedding version drift before any feature development proceeds.

**FRs Covered:** FR-SG1, FR-SG2
**Gaps Addressed:** #2, #3

### Story 1.1: Implement Structured XML Prompt Boundaries

As a **system administrator**,
I want **all LLM prompts to use structured XML boundaries separating system instructions from document content**,
So that **adversarial text in uploaded documents cannot manipulate LLM behavior**.

**Acceptance Criteria:**

**Given** a document contains text like "Ignore previous instructions and..."
**When** the text is processed by any LLM prompt
**Then** the adversarial text is contained within `<document_content>` tags
**And** system instructions remain in `<system>` tags outside the content boundary
**And** the LLM processes the content as data, not instructions

---

### Story 1.2: Add LLM Detection for Suspicious Documents

As a **system administrator**,
I want **documents flagged when they contain potential prompt injection patterns**,
So that **high-risk documents are identified before entering the pipeline**.

**Acceptance Criteria:**

**Given** a document is uploaded
**When** OCR extraction completes
**Then** a lightweight LLM check (~$0.001/doc) scans for injection patterns
**And** suspicious documents are flagged with `injection_risk: high/medium/low`
**And** high-risk documents require manual review before processing

---

### Story 1.3: Store Embedding Model Version with Vectors

As a **developer**,
I want **each embedding stored with its model version identifier**,
So that **model upgrades don't silently break semantic search**.

**Acceptance Criteria:**

**Given** a chunk is embedded using OpenAI text-embedding-ada-002
**When** the embedding is stored in pgvector
**Then** the `embedding_model_version` column stores "text-embedding-ada-002-v2"
**And** queries filter by matching model version
**And** mismatched versions are excluded from results

---

### Story 1.4: Implement Embedding Migration Path

As a **system administrator**,
I want **a migration utility to re-embed chunks when model versions change**,
So that **search quality is maintained after model upgrades**.

**Acceptance Criteria:**

**Given** a new embedding model is deployed
**When** the migration job runs
**Then** chunks with old model versions are queued for re-embedding
**And** progress is tracked via `embedding_migration_status`
**And** search continues working with old embeddings until migration completes

---

## Epic 2: Foundation Fixes

**Goal:** Fix silent failures and enable batch operations for immediate productivity gains.

**FRs Covered:** FR1.1, FR1.2, FR1.3
**Gaps Addressed:** #4, #7, #13
**Phase:** 1 (Week 1-2)

### Story 2.1: Add Worker Heartbeat to Redis

As a **system administrator**,
I want **Celery workers to send heartbeats every 30 seconds**,
So that **stuck or crashed workers can be detected automatically**.

**Acceptance Criteria:**

**Given** a Celery worker is processing a job
**When** the worker is healthy
**Then** it updates Redis key `worker:{worker_id}:heartbeat` every 30 seconds
**And** the key has a 60-second TTL
**And** missing heartbeats indicate a stale worker

---

### Story 2.2: Implement Zombie Job Detection and Recovery

As a **system administrator**,
I want **a scheduled task that detects and recovers zombie jobs**,
So that **stuck jobs are automatically restarted without manual intervention**.

**Acceptance Criteria:**

**Given** a job has been in "processing" state for >5 minutes without heartbeat
**When** the `job_recovery` Celery beat task runs (every 2 minutes)
**Then** the job is marked as "failed_stale" and requeued
**And** the original worker's heartbeat key is cleaned up
**And** an alert is logged for monitoring

---

### Story 2.3: Add Multi-Select to Verification Queue

As an **associate attorney**,
I want **to select multiple findings in the verification queue**,
So that **I can verify similar findings in bulk instead of one-by-one**.

**Acceptance Criteria:**

**Given** the verification queue displays 50 pending findings
**When** I click the checkbox on multiple rows (or use Shift+Click for range)
**Then** all selected findings are highlighted
**And** a bulk action bar appears showing "X items selected"
**And** I can apply Approve/Reject/Flag to all selected items

---

### Story 2.4: Implement Bulk Verification Actions

As an **associate attorney**,
I want **bulk approve, reject, and flag actions for selected findings**,
So that **I can process verification 10x faster**.

**Acceptance Criteria:**

**Given** 20 findings are selected in the verification queue
**When** I click "Approve All"
**Then** all 20 findings are marked as verified with my user_id
**And** a confirmation toast shows "20 findings approved"
**And** the queue refreshes to show remaining unverified items

---

### Story 2.5: Add File Size Validation Middleware

As a **system administrator**,
I want **uploads rejected if they exceed 50MB per file**,
So that **oversized files don't overwhelm the processing pipeline**.

**Acceptance Criteria:**

**Given** a user attempts to upload a 75MB PDF
**When** the upload request reaches the API
**Then** the request is rejected with 413 Payload Too Large
**And** the error message specifies "Maximum file size is 50MB"
**And** the rejection is logged for monitoring

**Backward Compatibility:**

**Given** the feature is deployed with `FILE_SIZE_ENFORCEMENT=warn`
**When** a file exceeds 50MB during the soft-launch period (2 weeks)
**Then** the upload is allowed but logged as a warning
**And** after soft-launch, enforcement can be enabled via config flag

---

## Epic 3: Compliance & UX

**Goal:** Enable configurable verification gates and improve user productivity with entity management and keyboard navigation.

**FRs Covered:** FR2.1, FR2.2, FR2.3, FR2.4
**Gaps Addressed:** #1, #6, #12, #18
**Phase:** 2 (Week 3-4)

### Story 3.1: Add Verification Mode Setting to Matters

As a **senior partner**,
I want **to configure verification requirements per matter**,
So that **court-ready matters enforce 100% verification while routine matters allow acknowledgment**.

**Acceptance Criteria:**

**Given** I create or edit a matter
**When** I set verification mode to "Court-ready"
**Then** the `verification_mode` column stores "required"
**And** exports are blocked until all findings reach 100% verification
**And** the default mode is "advisory" (acknowledgment only)

---

### Story 3.2: Implement Export Gate Check

As a **senior partner**,
I want **exports blocked when unverified findings exist in court-ready mode**,
So that **unverified AI output never reaches court documents**.

**Acceptance Criteria:**

**Given** a matter has `verification_mode = "required"`
**When** I click Export with unverified findings
**Then** a modal displays "X findings require verification before export"
**And** the Export button is disabled until verification is complete
**And** in "advisory" mode, an acknowledgment checkbox appears instead

**Backward Compatibility:**

**Given** an existing matter created before this feature launch
**When** the migration runs
**Then** the matter's `verification_mode` defaults to "advisory"
**And** existing export behavior is preserved (no blocking)
**And** only matters explicitly set to "required" are affected

---

### Story 3.3: Add Soft Merge Tracking to Entity Nodes

As a **developer**,
I want **entity merges tracked via `merged_into_id` foreign key**,
So that **merges can be undone without losing original entity data**.

**Acceptance Criteria:**

**Given** two entities "N.D. Jobalia" and "Nirav Jobalia" exist
**When** they are merged into a canonical entity
**Then** the secondary entity's `merged_into_id` points to the canonical
**And** the secondary entity's `merged_at` timestamp is recorded
**And** original mentions retain their original entity reference

---

### Story 3.4: Implement Entity Split UI

As an **associate attorney**,
I want **to split incorrectly merged entities back into separate nodes**,
So that **I can correct merge errors without losing work**.

**Acceptance Criteria:**

**Given** an entity was previously merged
**When** I click "Split" on the entity detail panel
**Then** the `merged_into_id` is set to NULL
**And** mentions are re-linked to their original entities
**And** the split action is logged in the audit trail

---

### Story 3.5: Implement Proactive Token Refresh

As a **user**,
I want **my authentication token refreshed automatically before expiry**,
So that **I don't experience random session timeouts**.

**Acceptance Criteria:**

**Given** my JWT token expires in 5 minutes
**When** the background refresh worker runs
**Then** a new token is obtained via Supabase refresh
**And** the new token replaces the old one silently
**And** if refresh fails, I'm redirected to login with "Session expired" message

---

### Story 3.6: Add Keyboard Shortcuts to Verification Queue

As an **associate attorney**,
I want **keyboard shortcuts for rapid verification actions**,
So that **I can process findings without touching the mouse**.

**Acceptance Criteria:**

**Given** I'm focused on the verification queue
**When** I press Y/N/S
**Then** Y approves the current finding, N rejects, S skips
**And** J/K navigate down/up the queue
**And** Enter opens the finding detail view
**And** Escape closes any open modal

**Given** a screen reader user navigates the verification queue
**When** they use keyboard shortcuts
**Then** all actions are announced via ARIA live regions
**And** focus management follows WCAG 2.1 AA guidelines
**And** visual focus indicators have minimum 3:1 contrast ratio

---

## Epic 4: Legal Defensibility

**Goal:** Provide explainability for AI decisions and court-ready certification for exports.

**FRs Covered:** FR3.1, FR3.2
**Gaps Addressed:** #5, #17
**Phase:** 3 (Week 5-6)

### Story 4.1: Implement Reasoning Trace Storage

As a **senior partner**,
I want **AI reasoning traces stored for every extraction and analysis**,
So that **I can explain to courts how conclusions were reached**.

**Acceptance Criteria:**

**Given** the contradiction engine identifies a conflict
**When** the analysis completes
**Then** a structured summary is stored in the `reasoning_traces` table
**And** the summary includes: input context, key evidence, confidence score, decision rationale
**And** traces are queryable via the finding detail API

**Given** the database write fails during trace storage
**When** the storage operation encounters an error
**Then** the analysis result is still returned to the user
**And** the failed trace is queued for retry
**And** the error is logged with correlation ID for debugging

---

### Story 4.2: Implement Tiered Reasoning Storage

As a **system administrator**,
I want **reasoning traces moved to cold storage after 30 days**,
So that **storage costs are managed while preserving legal audit trails**.

**Acceptance Criteria:**

**Given** a reasoning trace is older than 30 days
**When** the nightly archival job runs
**Then** the full LLM prompt/response is moved to S3 Glacier
**And** the structured summary remains in hot storage (PostgreSQL)
**And** archived traces are retrievable within 24 hours when needed

**Given** S3 Glacier upload fails during archival
**When** the storage operation encounters an error
**Then** the trace remains in hot storage (not deleted)
**And** the failed archival is retried on next job run
**And** an alert is sent if failures exceed threshold (3 consecutive)

---

### Story 4.3: Add Court-Ready Certification to Exports

As a **senior partner**,
I want **exports to include a certification stamp showing verification status**,
So that **court submissions demonstrate due diligence**.

**Acceptance Criteria:**

**Given** I export a matter with `verification_mode = "required"`
**When** all findings are verified
**Then** the export includes a certification block with:
  - Verification percentage (100%)
  - Verifying attorney name and bar number (if configured)
  - Verification completion timestamp
  - Matter ID and export timestamp
**And** the certification is visible on the first page of PDF exports

---

## Epic 5: Operational Excellence

**Goal:** Improve reliability, visibility, and cross-engine intelligence for operational efficiency.

**FRs Covered:** FR4.1, FR4.2, FR4.3, FR4.4, FR4.5, FR4.6, FR4.7
**Gaps Addressed:** #14, #15, #19, #39, #41, #42, #50
**Phase:** 4 (Week 7-8)

### Story 5.1: Add Email Notification on Processing Completion

As a **paralegal**,
I want **an email notification when document processing completes**,
So that **I don't have to keep checking the dashboard for status**.

**Acceptance Criteria:**

**Given** a document upload job completes (success or failure)
**When** the final pipeline stage finishes
**Then** an email is sent to the uploading user via SendGrid/Resend
**And** the email includes: matter name, document count, status summary
**And** users can opt out of notifications in their profile settings

---

### Story 5.2: Add LLM Quota Monitoring Dashboard

As a **system administrator**,
I want **a dashboard widget showing LLM API usage vs limits**,
So that **I can prevent service disruption from quota exhaustion**.

**Acceptance Criteria:**

**Given** the system is processing documents
**When** I view the admin dashboard
**Then** I see current usage vs quota for OpenAI and Gemini
**And** an alert triggers at 80% threshold
**And** the widget shows projected exhaustion date based on trend

---

### Story 5.3: Implement Cross-Engine Correlation Links

As an **associate attorney**,
I want **timeline events linked to related contradictions and entities**,
So that **I can see the full context of each event**.

**Acceptance Criteria:**

**Given** a timeline event involves "John Smith" on "Jan 15, 2024"
**When** I view the event detail
**Then** I see links to all contradictions involving John Smith
**And** I see the entity's journey (all timeline events for that entity)
**And** clicking a link navigates to the related finding

---

### Story 5.4: Implement Cross-Engine Consistency Checking

As an **associate attorney**,
I want **automatic flagging when engines produce conflicting information**,
So that **I'm alerted to potential data quality issues**.

**Acceptance Criteria:**

**Given** the timeline engine extracts "Contract signed Jan 15, 2024"
**And** the citation engine references the same document as "dated Jan 16, 2024"
**When** cross-engine validation runs
**Then** the conflict is flagged in a `consistency_issues` table
**And** both findings are marked with a warning icon
**And** the issue appears in a "Review Needed" queue

---

### Story 5.5: Add User-Friendly LLM Error Messages

As a **user**,
I want **clear error messages when LLM APIs fail**,
So that **I understand what happened and what to do next**.

**Acceptance Criteria:**

**Given** an OpenAI API call fails with rate limit error
**When** the error propagates to the UI
**Then** the message shows "AI service temporarily busy" (not raw API error)
**And** actionable suggestion: "Processing will retry automatically in 5 minutes"
**And** critical failures show "Contact support" with error reference ID

---

### Story 5.6: Add Queue Depth Visibility Dashboard

As a **system administrator**,
I want **a dashboard showing pending jobs per processing queue**,
So that **I can identify bottlenecks and capacity issues**.

**Acceptance Criteria:**

**Given** multiple processing queues exist (OCR, embedding, analysis)
**When** I view the operations dashboard
**Then** I see job counts per queue (pending, processing, failed)
**And** I see queue depth trend over last 24 hours
**And** alerts trigger when any queue exceeds threshold (configurable)

---

### Story 5.7: Add Processing ETA Display

As a **paralegal**,
I want **to see estimated completion time for document processing**,
So that **I can plan my work accordingly**.

**Acceptance Criteria:**

**Given** 50 documents are queued for processing
**When** I view the matter's processing status
**Then** I see "Estimated completion: ~45 minutes"
**And** the ETA is calculated from queue depth × average processing time
**And** the estimate updates as jobs complete

---

## Epic 6: User Adoption

**Goal:** Enable progressive disclosure and smooth onboarding for new users.

**FRs Covered:** FR5.1, FR5.2, FR5.3
**Gaps Addressed:** #8, #9, #10
**Phase:** 5 (Week 9-10)

### Story 6.1: Implement Progressive Disclosure UI

As a **new user**,
I want **advanced features hidden by default with an option to enable them**,
So that **I'm not overwhelmed when first using the system**.

**Acceptance Criteria:**

**Given** a new user logs in for the first time
**When** they view any workspace
**Then** advanced features (cross-engine correlation, bulk operations, keyboard shortcuts) are hidden
**And** a "Power User Mode" toggle exists in user settings
**And** enabling Power User Mode reveals all advanced features with tooltips

**Backward Compatibility:**

**Given** an existing user created before the feature launch date
**When** they log in after the feature is deployed
**Then** their `power_user_mode` is automatically set to `true`
**And** all features remain visible (no change to their experience)
**And** progressive disclosure only applies to users created after launch

---

### Story 6.2: Implement First-Run Onboarding Wizard

As a **new user**,
I want **a guided first-run experience explaining key features**,
So that **I can quickly understand how to use the platform**.

**Acceptance Criteria:**

**Given** a user logs in for the first time
**When** the dashboard loads
**Then** an onboarding wizard appears with 5-7 steps covering:
  - Uploading documents
  - Viewing timeline and entities
  - Running Q&A queries
  - Verifying findings
  - Exporting results
**And** users can skip or dismiss the wizard
**And** wizard progress is saved if interrupted

---

### Story 6.3: Create Sample Case Demo Matter

As a **new user**,
I want **a pre-loaded "Sample Case" matter to explore**,
So that **I can learn the system with realistic data before uploading my own**.

**Acceptance Criteria:**

**Given** a new user completes registration
**When** they view the dashboard
**Then** a "Sample Case" matter appears with demo documents
**And** the sample includes: 5 documents, 20 timeline events, 10 entities, 3 contradictions
**And** a "Explore Sample Case" button links to guided tour
**And** users can delete the sample when ready

---

### Story 6.4: Add Workflow Mode Toggle

As a **paralegal**,
I want **to choose between quick scan and deep analysis modes**,
So that **I can balance speed vs thoroughness based on matter urgency**.

**Acceptance Criteria:**

**Given** I create or edit a matter
**When** I select analysis mode
**Then** I can choose "Quick Scan" or "Deep Analysis"
**And** Quick Scan: faster processing, basic extraction, lower cost
**And** Deep Analysis: thorough processing, all engines, higher confidence
**And** the `analysis_mode` column stores the selection

---

## Epic 7: Enterprise Features

**Goal:** Enable firm-wide cost visibility and data residency controls for enterprise compliance.

**FRs Covered:** FR6.1, FR6.2, FR6.3
**Gaps Addressed:** #20, #21, #22
**Phase:** 6 (Week 11-12)

### Story 7.1: Add Per-Matter Cost Tracking Widget

As a **CFO**,
I want **to see AI processing costs per matter**,
So that **I can track technology spend against client billing**.

**Acceptance Criteria:**

**Given** a matter has processed documents using LLM APIs
**When** I view the matter dashboard
**Then** a cost widget shows total LLM cost for this matter
**And** costs are broken down by: embedding, analysis, Q&A
**And** daily and weekly rollups are available
**And** costs are stored in `matter_costs` table with timestamps

---

### Story 7.2: Implement Monthly Cost Report by Practice Group

As a **CFO**,
I want **monthly cost reports broken down by practice group**,
So that **I can analyze AI spend across the firm**.

**Acceptance Criteria:**

**Given** it's the first of the month
**When** I access the admin cost reports section
**Then** I can generate a report showing costs by practice group
**And** the report includes: matter count, document count, total cost per group
**And** I can export the report as CSV or PDF
**And** reports are retained for 12 months

---

### Story 7.3: Add Data Residency Controls

As an **IT administrator**,
I want **to configure data residency regions per matter or firm-wide**,
So that **we can comply with client data sovereignty requirements**.

**Acceptance Criteria:**

**Given** I'm creating a matter for an EU client
**When** I set the data residency to "EU"
**Then** all API calls for this matter route to EU regional endpoints
**And** document storage uses EU-region buckets
**And** the residency setting is immutable after documents are uploaded
**And** a firm-wide default can be set in admin settings

---

## MVP Stories Complete

**Summary:** Epics 1-7 contain 29 stories covering 24 FRs from the gap analysis.

| Epic | Stories | FRs | Phase |
|------|---------|-----|-------|
| Epic 1: Security Foundation | 4 | 2 | Security Gate |
| Epic 2: Foundation Fixes | 5 | 3 | Phase 1 |
| Epic 3: Compliance & UX | 6 | 4 | Phase 2 |
| Epic 4: Legal Defensibility | 3 | 2 | Phase 3 |
| Epic 5: Operational Excellence | 7 | 7 | Phase 4 |
| Epic 6: User Adoption | 4 | 3 | Phase 5 |
| Epic 7: Enterprise Features | 3 | 3 | Phase 6 |
| **Total MVP** | **32** | **24** | Weeks 1-12 |

---

<!-- Optional Epics 8-10 not included in MVP scope -->

