---
stepsCompleted: [1, 2, 3, 4]
workflowComplete: true
inputDocuments:
  - "project-planning-artifacts/MVP-Scope-Definition-v1.0.md"
  - "project-planning-artifacts/Requirements-Baseline-v1.0.md"
  - "architecture.md"
  - "project-planning-artifacts/UX-Decisions-Log.md"
---

# LDIP - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for LDIP (Legal Document Intelligence Platform), decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Core Engine Requirements:**

FR1: Citation Verification Engine - Extract Act citations from case files (petitions, appeals, rejoinders, annexures, application, affidavits, etc), implement Act Discovery Report showing which Acts are referenced and which are available/missing, allow user to upload Act documents per matter, verify citations against user-provided Acts (section exists, quoted text matches), flag misattributions and section errors, link citations to bounding boxes in BOTH source document AND Act document for visual highlighting, support graceful degradation (mark as "Unverified - Act not provided" when Act unavailable), provide confidence scoring for each verification

FR2: Timeline Construction Engine - Extract all dates with surrounding context (±200 words) using Gemini, classify event types (filing, notice, hearing, order, transaction), store in events table with entity_ids from MIG, order events chronologically, flag date ambiguities (DD/MM vs MM/DD), validate logical sequence (notice before filing, hearing after notice), flag anomalies with warnings (e.g., "Notice dated 9 months after borrower default"), cache timeline in Matter Memory (/matter-{id}/timeline_cache.jsonb), support filtering by date_range, event_types, and entities parameters

FR3: Consistency & Contradiction Engine - Query all chunks mentioning a canonical entity_id from MIG, group statements by entity (e.g., "Nirav Jobalia" = "N.D. Jobalia" = "Mr. Jobalia"), compare statement pairs using GPT-4 chain-of-thought reasoning, detect contradiction types: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch, provide contradiction_explanation in natural language, assign severity (high/medium/low) based on type (high for clear factual contradictions like dates/amounts, medium for semantic requiring interpretation, low for possible contradictions needing review), store statement evidence with document_id, page, bbox_ids, text_excerpt, date_made, context

FR4: Engine Orchestrator - Analyze query intent to determine which engines to invoke, select engines based on query type (citation query → Citation Engine, timeline query → Timeline Engine, contradiction query → Contradiction Engine), execute engines in correct order (some parallel, some sequential), aggregate results from multiple engines, apply safety layer (guardrails + language policing) before returning response, log full execution to audit trail (input, engines invoked, outputs, confidence, cost)

**Memory System Requirements:**

FR5: Session Memory (Layer 1) - Redis-based storage with key format session:{matter_id}:{user_id}, 7-day TTL (auto-extends on activity, max 30 days), store SessionContext with session_id, matter_id, user_id, created_at, last_activity, messages array (sliding window max 20), entities_mentioned map for pronoun resolution, each SessionMessage includes role, content, timestamp, engine_trace (engines_invoked, execution_time_ms, findings_count), auto-archive to Matter Memory on expiry for context restoration, clear on logout or manual session end

FR6: Matter Memory (Layer 2) - PostgreSQL JSONB storage in matter_memory table with matter_id, file_path, content, created_by, created_at, modified_by, modified_at, archived flag, implement RLS policy (only attorneys on matter can access), file structure: /matter-{id}/query_history.jsonb (forensic audit log, append-only with query_id, query_text, query_intent, asked_by, asked_at, engines_invoked, execution_time_ms, findings_count, response_summary, verified, verified_by, verified_at), /matter-{id}/timeline_cache.jsonb (cached_at, events, last_document_upload for invalidation), /matter-{id}/entity_graph.jsonb (cached_at, entities map, relationships), /matter-{id}/key_findings.jsonb (attorney-verified facts with finding_id, finding_type, description, evidence, verified_by, verified_at, notes), /matter-{id}/research_notes.jsonb (attorney annotations with note_id, created_by, created_at, title, content markdown, tags, linked_findings)

FR7: Query Cache (Layer 3) - Redis cache with key format cache:query:{matter_id}:{query_hash} where query_hash is SHA256 of normalized query, 1-hour TTL (3600 seconds), return cached results in ~10ms vs 3-5 seconds for fresh query, clear all matter cache keys on document upload (invalidation pattern: cache:query:{matterId}:*)

**Safety Feature Requirements:**

FR8: Query Guardrails - Implement fast-path regex pattern detection for dangerous patterns (e.g., /should (i|we|client) (file|appeal|settle)/i, /is (client|defendant|plaintiff) (guilty|innocent|liable)/i, /will (judge|court) (rule|decide|hold)/i, /what are (my|our) chances/i), use GPT-4o-mini for subtle violation detection when patterns don't match, return GuardrailCheck with is_safe, violation_type (legal_conclusion, prediction, advice, personal_opinion), explanation, suggested_rewrite, provide contextual query rewrites (e.g., "Should I file appeal?" → "What are the grounds for appeal in this matter?")

FR9: Language Policing - Apply regex-based fast replacements (e.g., "violated Section X" → "affected by Section X", "defendant is guilty/innocent/liable" → "defendant's liability regarding", "the court will rule/hold/decide" → "the court may consider", "proves that" → "suggests that", "client should" → "client may consider"), then apply GPT-4o-mini for subtle conclusion removal, ensure user never sees raw LLM output (transparent filtering), apply policing to all engine outputs before user display

FR10: Attorney Verification Workflow - Create finding_verifications table with verification_id, matter_id, finding_id, finding_type, finding_summary, verified_by, verified_at, decision (approved/rejected/flagged), notes, confidence_before (engine confidence 0-100), confidence_after (attorney adjustment 0-100), implement verification queue UI showing all unverified findings with finding_type, description, confidence progress bar, Approve/Reject/Flag buttons, implement tiered verification: >90% confidence (informational, optional verification), 70-90% (suggested verification badge shown), <70% (required verification, blocked from export until verified), tie verification requirement to export action not viewing

**Document Processing Requirements:**

FR11: Document Upload - Support PDF and ZIP (containing PDFs) file formats, maximum 500MB per file and 100 files per matter, implement drag-and-drop interface with file validation, store files in Supabase Storage with folder structure documents/{matter_id}/uploads/ for case files and documents/{matter_id}/acts/ for Act documents, implement documents table with document_type field (case_file, act, annexure, other) and is_reference_material boolean (true for Acts), support adding documents to existing matter with incremental processing (new docs merge into existing analysis)

FR12: OCR Processing - Use Google Document AI as primary OCR with bounding box extraction and per-word confidence scores (cost ~$9.50 per 2000-page matter), use Gemini 3 Flash for OCR validation: flag low-confidence words (<85%), apply contextual validation for dates/amounts/case numbers, implement pattern-based auto-correction, route critical low-confidence content (<50%) to human review queue, support Indian languages (Gujarati, Hindi, English), create bounding_boxes table linking extracted text to document page coordinates

FR13: RAG Pipeline - Implement parent-child chunking: parent chunks 1500-2000 tokens preserving document structure, child chunks 400-700 tokens with 50-100 token overlap, link all chunks to bounding_boxes for visual citations, implement hybrid search: BM25 via PostgreSQL tsvector for keyword matching + pgvector with HNSW index for semantic similarity, merge results via Reciprocal Rank Fusion (RRF) returning top 20 candidates, apply Cohere Rerank v3 to rerank top 20 → return top 3 most relevant (40-70% precision gain, $0.10 per query), use OpenAI text-embedding-ada-002 embeddings (1536 dimensions)

FR14: MIG (Matter Identity Graph) - Create identity_nodes table for canonical entities with entity_id, matter_id, canonical_name, entity_type (PERSON, ORG, INSTITUTION, ASSET), metadata JSONB, create identity_edges table with source_entity_id, target_entity_id, relationship_type (ALIAS_OF, HAS_ROLE, RELATED_TO), confidence score, create pre_linked_relationships table for pre-computed entity connections with document references, create events table for timeline fragments with entity associations, implement entity extraction using Gemini during ingestion, implement alias resolution to link name variants (e.g., "Nirav Jobalia" = "N.D. Jobalia" = "Mr. Jobalia") to single canonical entity_id

**User Interface Requirements:**

FR15: Dashboard/Home Page - Implement header with logo, global search, notifications badge (with count), help, and user profile dropdown, display hero section with personalized greeting, status summary ("You have X findings awaiting verification and Y matters processing"), and prominent "+ New Matter" CTA button, show matter cards grid (70% width) with states: processing (progress bar with %, estimated time, doc/page counts) and ready (status badge, page count, last activity, verification %, issue count, Resume button), implement grid/list view toggle, sort options (Recent, Alphabetical, Most pages, Least verified, Date created), filter options (All, Processing, Ready, Needs attention, Archived), display activity feed (30% width) with icon-coded entries (green=success, blue=info, yellow=in progress, orange=attention, red=error), show quick stats panel (active matters, verified findings, pending reviews)

FR16: Matter Workspace - Implement header with back to Dashboard, editable matter name, Export dropdown, Share button, Settings gear, implement tab bar with exact order: Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents, implement main content area (changes per tab) with Q&A panel alongside, support Q&A panel positions: right sidebar (default, resizable 20-60% width), bottom panel (resizable height), floating (draggable, resizable, can overlap), hidden (collapsed with small chat button to expand), implement split-view PDF viewer that opens on citation click with workspace still visible, implement full modal PDF view via expand button

FR17: Upload & Processing Flow - Stage 1 File Selection: drag-drop zone with icon animation, "Browse Files" button, supported formats note (PDF, ZIP), limits note (500MB/file, 100 files), Stage 2 Review & Name: show auto-generated matter name (editable), file list with remove option, Act Discovery Report modal (which Acts referenced, which available/missing, options: upload Acts, skip specific Acts, continue with partial verification), Stage 3 Upload Progress: file-by-file progress bars with checkmarks, Stage 4 Processing & Live Discovery: overall progress bar with stage indicator ("Stage 3 of 5: Extracting entities"), split view showing document processing (files received, pages extracted, OCR progress) and live discoveries panel (entities found with roles, dates extracted with earliest/latest, citations detected by Act, mini timeline preview, early insights with warnings), "Continue in Background" button for returning to dashboard, Stage 5 Processing Complete: auto-redirect to Matter Workspace, browser notification if backgrounded

FR18: Export Builder - Open as modal overlay, implement section selection with checkboxes (Executive Summary, Timeline, Entities, Citations, Contradictions, Key Findings), support drag-and-drop section reordering, enable inline editing of section content, show export preview panel, support export formats: PDF (primary, court-ready), Word (editable), PowerPoint (presentation), enforce verification check on export (findings <70% confidence must be verified before export allowed), include verification status in exported document

FR19: Summary Tab - Display attention banner at top (items needing action: contradictions, citation issues with count and "Review All" link), show Parties section with Petitioner and Respondent cards including entity links and source citations, display Subject Matter with description and source links, show Current Status with last order date, description, and "View Full Order" link, display Key Issues numbered list with verification status badges (Verified/Pending/Flagged), show Matter Statistics cards (pages, entities, events, citations), display Verification Progress bar with percentage, implement inline verification on each section ([✓ Verify] [✗ Flag] [💬 Note] buttons), implement editable sections with Edit button, preserve original AI version, support Regenerate for fresh AI analysis, show clickable citation links on every factual claim with hover preview tooltip

FR20: Timeline Tab - Implement three view modes: Vertical List (default, detailed chronological scroll), Horizontal Timeline (visual overview with zoom slider, event clusters, gap indicators), Multi-Track view (parallel timelines by actor for complex cases), display timeline header with event count and date range, implement view toggle and filter controls, display event cards with: date, type icon (📋 Filing, ⚖️ Order, 📧 Notice, 🔔 Hearing, 💼 Transaction, 📄 Document, ⏰ Deadline), title, description, actor(s) linked to Entities tab, source document+page (clickable), cross-references to other documents, verification status, contradiction flag if applicable, show duration between events on connector lines, support manual event addition (date, type, title, description, actor, source) marked as "Manually added", implement filters: Event Type, Actors, Date Range, Verification Status

FR21: Entities Tab - Display MIG entity graph visualization using D3.js or React Flow, show entity cards with: canonical name, entity type badge (PERSON, ORG, INSTITUTION, ASSET), list of aliases, relationship connections, document mentions count, implement entity detail panel on selection showing all mentions across documents with source links, support entity merge dialog for manually linking entities LDIP missed, implement filter by entity type, show entity statistics

FR22: Citations Tab - Display Act Discovery Report summary (X Acts referenced, Y available, Z missing), show list of all extracted citations with columns: citation text, Act name, section, source document+page, verification status (verified/mismatch/not_found/act_unavailable), confidence score, implement filter by verification status and Act name, show action button to upload missing Acts, implement click on citation to open split-view showing source location (case file) on left AND target location (Act file) on right with both locations highlighted

FR23: Contradictions Tab - Display contradictions grouped by entity (canonical name header, contradiction cards below), show contradiction cards with: contradiction type badge (semantic/factual/date_mismatch/amount_mismatch), severity indicator (high/medium/low), entity name, Statement 1 with document+page+excerpt+date, Statement 2 with document+page+excerpt+date, contradiction explanation in natural language, evidence links (click to view in PDF), implement inline verification on each contradiction ([✓ Verified] [✗ Reject] [🔄 Needs Review]), implement filter by severity, entity, contradiction type

FR24: Verification Tab - Display verification queue as DataTable with columns: finding type, description, confidence (as progress bar), source, actions, implement bulk selection for batch verification, show Approve (green check), Reject (red X), Flag (yellow flag) action buttons on each row, implement notes prompt on Reject/Flag actions, display verification statistics (total findings, verified count, pending count, flagged count), implement filter by finding type, confidence tier, verification status, show recently verified items with timestamps and verifier name

FR25: Documents Tab - Display document list table with columns: document name, page count, date added, status (Indexed/Processing), type badge (case_file/act/annexure), action menu, show "+ ADD FILES" button in header, implement inline processing progress bar for new documents ("Processing NEW DOCUMENTS: X files, Y%"), show "You can continue working while this processes" message, implement document action menu with: View, Rename, Set as Act, Delete, implement drag-and-drop file addition anywhere in workspace

FR26: Q&A Panel - Implement panel header with title "ASK LDIP", minimize button, position selector dropdown (Right/Bottom/Float/Hide), show conversation history with user and assistant message bubbles, display assistant messages with source references as clickable links, implement streaming response display with typing indicator, show message input field with send button, display suggested questions for empty state ("What is this case about?"), implement engine trace display (which engines were invoked, execution time, findings count) on assistant messages

FR27: PDF Viewer - Implement split-view mode (opens alongside workspace content) and full modal mode (expand button), display document header with filename, page number, total pages, expand/close buttons, implement page navigation (prev/next, go to page), implement zoom controls, display bounding box overlays as semi-transparent highlights on relevant text, implement different highlight colors for different purposes (yellow for citations, blue for entity mentions, red for contradictions), support click on cross-reference links within document to jump to referenced document+page, implement side-by-side view for citation verification (source document left, Act document right)

**Authentication & Authorization Requirements:**

FR28: Authentication - Implement Supabase Auth integration with three methods: email/password (standard signup/login flow), magic link (passwordless email login), OAuth via Google (social login), implement JWT token handling with automatic refresh, store user profile in users table with user_id, email, full_name, avatar_url, created_at, last_login, implement secure session management

FR29: Authorization - Implement role-per-matter model with three roles: Owner (full control including delete and share), Editor (can modify content, verify findings, add documents), Viewer (read-only access), create matter_attorneys junction table with matter_id, user_id, role, invited_by, invited_at, implement PostgreSQL Row-Level Security (RLS) policies on all matter-related tables (matters, documents, findings, matter_memory, etc.), implement 4-layer matter isolation: RLS policies (database layer), vector namespace prefix matter_{id}_ (embedding isolation), Redis key prefix matter:{id}: (cache isolation), API middleware validation (application layer), ensure zero cross-matter data leakage

### NonFunctional Requirements

**Performance Requirements:**

NFR1: Query response time < 10 seconds (95th percentile)

NFR2: Document ingestion < 5 minutes per 100 pages

NFR3: Timeline generation < 2 minutes for 2000-page matter

NFR4: UI page load < 2 seconds

NFR5: Citation verification < 10 seconds for all citations in 2000-page document

**Cost Requirements:**

NFR6: Cost per 2000-page matter < $15 (target: $13-14)

NFR7: LLM API costs monitored and optimized via hybrid Gemini + GPT routing

**Accuracy Requirements:**

NFR8: Citation extraction recall > 95%

NFR9: Citation verification accuracy > 95%

NFR10: Event extraction recall > 80%

NFR11: Event extraction accuracy > 90%

NFR12: Chronological ordering accuracy > 95%

NFR13: Entity resolution accuracy > 95%

NFR14: Contradiction detection recall > 70%

NFR15: Contradiction detection precision > 90%

**Security Requirements:**

NFR18: Matter isolation via 4-layer enforcement (RLS, vector namespace prefix, Redis key prefix, API middleware)

NFR19: Zero cross-matter data leakage

NFR20: All API endpoints require JWT authentication

NFR21: Rate limiting: 100 req/min per user (FastAPI), automatic edge limiting (Vercel)

**Safety Requirements:**

NFR22: 0 legal conclusions escape language policing (100% sanitized)

NFR23: Query guardrails block 95%+ dangerous questions

NFR24: Complete audit trail (who verified what, when)

**Reliability Requirements:**

NFR25: RTO (Recovery Time Objective): 4 hours

NFR26: RPO (Recovery Point Objective): 1 hour

NFR27: Retry logic with exponential backoff for LLM and external API calls

**Data Retention Requirements:**

NFR28: Matter documents retention: 7 years (S3 Glacier after 1 year inactive)

NFR29: Engine outputs (findings) retention: 7 years

NFR30: Audit logs retention: 7 years

NFR31: Session memory retention: 7 days (auto-expire)

NFR32: Query cache retention: 1 hour (auto-expire)

NFR33: Deleted matters: 30 days soft-delete, then hard delete

### Additional Requirements

**From Architecture - Starter Template:**
- Frontend: Next.js 16 with App Router, TypeScript, shadcn/ui, Tailwind CSS, Zustand
- Backend: FastAPI, Python 3.12+, Pydantic v2, SQLAlchemy 2.0
- Project initialization using `create-next-app` and `uv init` (Epic 1, Story 1)

**From Architecture - Infrastructure:**
- Supabase PostgreSQL with pgvector extension for vector search
- Supabase Storage for document storage with RLS integration
- Redis (Upstash) for session memory and query cache
- Celery for background job processing
- Production: Vercel (frontend), Railway (backend), Supabase, Upstash Redis

**From Architecture - Observability:**
- Axiom for application logging (30 days hot, 1 year cold)
- PagerDuty/Opsgenie for alerting
- Structured JSON logging with correlation IDs

**From Architecture - Security:**
- Circuit breakers with tenacity library (max 3 retries, 30s timeout for LLM calls)
- Rate limiting via slowapi middleware
- DDoS protection via Vercel edge (automatic)
- Secrets management via Railway secrets + Vercel env + 1Password

**From Architecture - Performance:**
- Two-phase response pattern (0-2s cached results, 2-10s streaming enhanced analysis)
- Semantic query normalization before cache lookup
- Pre-computation during ingestion (timeline, entity graph, citation index)
- Virtualized PDF rendering (visible pages + 1 buffer only)

**From Architecture - ADRs:**
- ADR-001: PostgreSQL only (no Neo4j for MIG) - simpler security, adequate for our query patterns
- ADR-002: Hybrid LLM (Gemini ingestion + GPT-4 reasoning) - cost optimization
- ADR-003: 5 modular engines (not monolithic) - auditability and testability
- ADR-004: Tiered verification thresholds (>90% optional, 70-90% suggested, <70% required before export)
- ADR-005: Act Discovery with User-Driven Resolution for Citation Engine

**From UX Design:**
- Multi-matter support (lawyers juggle multiple active matters)
- Dashboard shows both "Start New" AND "Continue Where Left Off"
- Q&A panel: user-controlled position (right sidebar default, bottom panel, floating, hidden)
- PDF Viewer: split view by default, expandable to full modal
- Verification: dedicated tab + inline verify buttons on all findings
- Live discovery during processing (entities, dates, citations shown as found)
- Background processing support ("Continue in Background" option)
- Add documents to existing matter (incremental processing)
- Tab order: Summary > Timeline > Entities > Citations > Contradictions > Verification > Documents

**From UX Design - Micro-interactions & Error States:**
- Responsive feedback for all user actions
- Clear loading states for long operations
- Graceful degradation on errors
- Browser notifications for background processing completion

### FR Coverage Map

| FR | Epic | Story | Description |
|----|------|-------|-------------|
| FR1 | Epic 3 | 3.1-3.4 | Citation Verification Engine |
| FR2 | Epic 4 | 4.1-4.4 | Timeline Construction Engine |
| FR3 | Epic 5 | 5.1-5.4 | Consistency & Contradiction Engine |
| FR4 | Epic 6 | 6.1-6.3 | Engine Orchestrator |
| FR5 | Epic 7 | 7.1-7.2 | Session Memory (Redis) |
| FR6 | Epic 7 | 7.3-7.4 | Matter Memory (PostgreSQL JSONB) |
| FR7 | Epic 7 | 7.5 | Query Cache (Redis) |
| FR8 | Epic 8 | 8.1-8.2 | Query Guardrails |
| FR9 | Epic 8 | 8.3 | Language Policing |
| FR10 | Epic 8 | 8.4-8.5 | Attorney Verification Workflow |
| FR11 | Epic 2A | 2A.1-2A.3 | Document Upload & Storage |
| FR12 | Epic 2B | 2B.1-2B.4 | OCR Processing |
| FR13 | Epic 2B | 2B.5-2B.7 | RAG Pipeline |
| FR14 | Epic 2C | 2C.1-2C.2 | MIG (Matter Identity Graph) |
| FR15 | Epic 9 | 9.1-9.3 | Dashboard/Home Page |
| FR16 | Epic 10A | 10A.1-10A.3 | Matter Workspace Shell |
| FR17 | Epic 9 | 9.4-9.6 | Upload & Processing Flow |
| FR18 | Epic 12 | 12.1-12.3 | Export Builder |
| FR19 | Epic 10B | 10B.1-10B.2 | Summary Tab |
| FR20 | Epic 10B | 10B.3-10B.5 | Timeline Tab |
| FR21 | Epic 10C | 10C.1-10C.2 | Entities Tab |
| FR22 | Epic 10C | 10C.3-10C.4 | Citations Tab |
| FR23 | Epic 10D | PHASE 2 | Contradictions Tab (DEFERRED - see Phase-2-Backlog.md) |
| FR24 | Epic 10D | 10D.1-10D.2 | Verification Tab (includes contradiction findings) |
| FR25 | Epic 10D | 10D.3-10D.4 | Documents Tab |
| FR26 | Epic 11 | 11.1-11.4 | Q&A Panel |
| FR27 | Epic 11 | 11.5-11.7 | PDF Viewer |
| FR28 | Epic 1 | 1.3-1.5 | Authentication |
| FR29 | Epic 1 | 1.6-1.7 | Authorization |

## Epic List

### Epic 1: Project Foundation & Authentication
**Goal:** Establish project infrastructure, authentication, and authorization so attorneys can securely access their matters.

**User Value:** Attorneys can sign in securely and only access matters they're authorized for, with proper role-based permissions.

**Stories:**
- 1.1: Initialize Next.js 16 frontend project with TypeScript, shadcn/ui, Tailwind CSS, Zustand
- 1.2: Initialize FastAPI backend project with Python 3.12+, Pydantic v2, SQLAlchemy 2.0
- 1.3: Implement Supabase Auth integration (email/password, magic link, Google OAuth)
- 1.4: Implement JWT token handling with automatic refresh and session management
- 1.5: Implement password reset flow via email
- 1.6: Implement role-per-matter model (Owner, Editor, Viewer) with matter_attorneys table
- 1.7: Implement PostgreSQL RLS policies for 4-layer matter isolation

**FRs Covered:** FR28, FR29
**NFRs Addressed:** NFR18, NFR19, NFR20

---

### Epic 2A: Document Upload & Storage
**Goal:** Enable attorneys to upload legal documents securely with proper storage organization.

**User Value:** Attorneys can upload case files and Acts via drag-drop with clear progress feedback and organized storage.

**Stories:**
- 2A.1: Implement document upload UI (drag-drop, file validation, progress indicators)
- 2A.2: Implement Supabase Storage integration with folder structure (documents/{matter_id}/uploads/, /acts/)
- 2A.3: Implement documents table with document_type and is_reference_material fields

**FRs Covered:** FR11
**NFRs Addressed:** NFR2

---

### Epic 2B: OCR & RAG Pipeline
**Goal:** Extract searchable text from uploaded documents with high accuracy and enable intelligent retrieval.

**User Value:** Attorneys can search within documents and get accurate results even from scanned PDFs.

**Stories:**
- 2B.1: Integrate Google Document AI for OCR with bounding box extraction
- 2B.2: Implement Gemini-based OCR validation and low-confidence routing
- 2B.3: Display OCR quality assessment with manual review request option
- 2B.4: Create bounding_boxes table linking extracted text to page coordinates
- 2B.5: Implement parent-child chunking (1500-2000 token parents, 400-700 token children)
- 2B.6: Implement hybrid search (BM25 via tsvector + pgvector HNSW) with RRF fusion
- 2B.7: Integrate Cohere Rerank v3 for top-20 → top-3 refinement

**FRs Covered:** FR12, FR13
**NFRs Addressed:** NFR8, NFR13

---

### Epic 2C: Entity Extraction & MIG
**Goal:** Extract and resolve entities from documents into the Matter Identity Graph.

**User Value:** Attorneys see all parties, organizations, and key entities automatically identified with aliases resolved.

**Stories:**
- 2C.1: Implement MIG entity extraction and identity_nodes/identity_edges tables
- 2C.2: Implement alias resolution for entity name variants
- 2C.3: Implement background job status tracking and retry mechanism

**FRs Covered:** FR14
**NFRs Addressed:** NFR8

---

### Epic 3: Citation Verification Engine
**Goal:** Verify legal citations in case documents against actual Act texts with visual highlighting.

**User Value:** Attorneys see exactly which citations are verified, misattributed, or unverifiable, with side-by-side document views.

**Stories:**
- 3.1: Implement Act citation extraction from case files (petitions, appeals, annexures)
- 3.2: Implement Act Discovery Report UI (which Acts referenced, available, missing)
- 3.3: Implement citation verification against user-provided Acts (section exists, text matches)
- 3.4: Implement split-view citation highlighting (source document left, Act document right)

**FRs Covered:** FR1
**NFRs Addressed:** NFR8, NFR9, NFR5

---

### Epic 4: Timeline Construction Engine
**Goal:** Extract and visualize chronological events from legal documents with anomaly detection.

**User Value:** Attorneys see a complete, validated timeline of case events with flagged anomalies (e.g., "9-month gap").

**Stories:**
- 4.1: Implement date extraction with ±200 word context using Gemini
- 4.2: Implement event classification (filing, notice, hearing, order, transaction)
- 4.3: Implement events table with entity_ids from MIG and chronological ordering
- 4.4: Implement timeline anomaly detection (sequence validation, gap flagging)

**FRs Covered:** FR2
**NFRs Addressed:** NFR10, NFR11, NFR12, NFR3

---

### Epic 5: Consistency & Contradiction Engine
**Goal:** Detect contradictory statements across documents grouped by entity.

**User Value:** Attorneys discover critical contradictions (date/amount mismatches, conflicting facts) before opposing counsel does.

**Stories:**
- 5.1: Implement entity-grouped statement querying via MIG canonical_entity_id
- 5.2: Implement statement pair comparison using GPT-4 chain-of-thought
- 5.3: Implement contradiction type classification (semantic, factual, date_mismatch, amount_mismatch)
- 5.4: Implement severity scoring and contradiction explanation generation

**FRs Covered:** FR3
**NFRs Addressed:** NFR14, NFR15

---

### Epic 6: Engine Orchestrator
**Goal:** Intelligently route queries to appropriate engines and aggregate results.

**User Value:** Attorneys ask natural language questions and get comprehensive answers from the right combination of engines.

**Stories:**
- 6.1: Implement query intent analysis for engine selection
- 6.2: Implement engine execution ordering (parallel vs sequential) and result aggregation
- 6.3: Implement audit trail logging (input, engines invoked, outputs, confidence, cost)

**FRs Covered:** FR4
**NFRs Addressed:** NFR1, NFR24

---

### Epic 7: Three-Layer Memory System
**Goal:** Implement session, matter, and cache memory for context persistence and performance.

**User Value:** LDIP remembers conversation context, caches expensive computations, and maintains matter history.

**Stories:**
- 7.1: Implement Session Memory Redis storage (session:{matter_id}:{user_id} key format)
- 7.2: Implement 7-day TTL with auto-extend, sliding window messages, pronoun resolution
- 7.3: Implement Matter Memory PostgreSQL JSONB (query_history, timeline_cache, entity_graph)
- 7.4: Implement key_findings and research_notes storage with RLS policies
- 7.5: Implement Query Cache (cache:query:{matter_id}:{query_hash}, 1-hour TTL, invalidation on upload)

**FRs Covered:** FR5, FR6, FR7
**NFRs Addressed:** NFR31, NFR32, NFR1

---

### Epic 8: Safety Layer (Guardrails, Policing, Verification)
**Goal:** Ensure no legal conclusions escape to users and all findings are verifiable.

**User Value:** Attorneys trust LDIP won't make them look unprofessional with legal conclusions or unverified claims.

**Stories:**
- 8.1: Implement fast-path regex pattern detection for dangerous queries
- 8.2: Implement GPT-4o-mini subtle violation detection with contextual rewrites
- 8.3: Implement language policing (regex replacements + GPT-4o-mini conclusion removal)
- 8.4: Implement finding_verifications table and tiered verification thresholds
- 8.5: Implement verification queue UI with bulk selection and action buttons

**FRs Covered:** FR8, FR9, FR10
**NFRs Addressed:** NFR22, NFR23, NFR24

---

### Epic 9: Dashboard & Upload Experience
**Goal:** Create the home experience for matter management and new matter creation.

**User Value:** Attorneys see all their matters at a glance and can easily start new matters with guided upload.

**Stories:**
- 9.1: Implement dashboard header (logo, global search, notifications, profile dropdown)
- 9.2: Implement matter cards grid with processing/ready states, filters, and sorting
- 9.3: Implement activity feed and quick stats panel
- 9.4: Implement Stage 1-2 upload flow (file selection, review & name, Act Discovery modal)
- 9.5: Implement Stage 3-4 upload progress and live discovery panel
- 9.6: Implement Stage 5 completion redirect and background processing notification

**FRs Covered:** FR15, FR17
**NFRs Addressed:** NFR4

---

### Epic 10A: Workspace Shell & Navigation
**Goal:** Build the core workspace layout and navigation framework.

**User Value:** Attorneys have a consistent, navigable workspace to access all analysis features.

**Stories:**
- 10A.1: Implement workspace shell (header with matter name, Export, Share, Settings)
- 10A.2: Implement tab bar (Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents)
- 10A.3: Implement main content area switching and Q&A panel integration

**FRs Covered:** FR16
**NFRs Addressed:** NFR4

---

### Epic 10B: Summary & Timeline Tabs
**Goal:** Build the Summary and Timeline analysis views.

**User Value:** Attorneys see case overview and chronological events at a glance.

**Stories:**
- 10B.1: Implement Summary tab (attention banner, parties, subject matter, status, key issues)
- 10B.2: Implement Summary tab inline verification and edit capabilities
- 10B.3: Implement Timeline tab vertical list view (default)
- 10B.4: Implement Timeline tab horizontal timeline and multi-track views
- 10B.5: Implement Timeline tab filtering and manual event addition

**FRs Covered:** FR19, FR20
**NFRs Addressed:** NFR4

---

### Epic 10C: Entities & Citations Tabs
**Goal:** Build the Entities graph and Citations verification views.

**User Value:** Attorneys explore party relationships and verify legal citations.

**Stories:**
- 10C.1: Implement Entities tab MIG graph visualization (D3.js/React Flow)
- 10C.2: Implement Entities tab detail panel with mentions and merge dialog
- 10C.3: Implement Citations tab Act Discovery Report and citation list
- 10C.4: Implement Citations tab split-view citation verification

**FRs Covered:** FR21, FR22
**NFRs Addressed:** NFR4

---

### Epic 10D: Contradictions, Verification & Documents Tabs
**Goal:** Build the remaining analysis and management tabs.

**User Value:** Attorneys review contradictions, verify findings, and manage documents.

**Stories:**
- ~~10D.1: Implement Contradictions tab entity-grouped display~~ → **PHASE 2**
- ~~10D.2: Implement Contradictions tab inline verification~~ → **PHASE 2**
- 10D.1: Implement Verification tab queue DataTable with bulk actions (includes contradiction findings)
- 10D.2: Implement Verification tab statistics and filtering
- 10D.3: Implement Documents tab file list with processing progress
- 10D.4: Implement Documents tab file actions (view, rename, set as Act, delete)

**FRs Covered:** FR23, FR24, FR25
**NFRs Addressed:** NFR4

---

### Epic 11: Q&A Panel & PDF Viewer
**Goal:** Enable natural language querying and document viewing with visual citations.

**User Value:** Attorneys ask questions and see answers with clickable source links that highlight the exact text in documents.

**Stories:**
- 11.1: Implement Q&A panel header with position selector (right/bottom/float/hide)
- 11.2: Implement conversation history with user/assistant message bubbles
- 11.3: Implement streaming response display with engine trace
- 11.4: Implement suggested questions and message input
- 11.5: Implement PDF viewer split-view mode with workspace visible
- 11.6: Implement PDF viewer full modal mode with navigation and zoom
- 11.7: Implement bounding box overlays with color-coded highlights

**FRs Covered:** FR26, FR27
**NFRs Addressed:** NFR4

---

### Epic 12: Export Builder
**Goal:** Enable attorneys to export case analysis as court-ready documents.

**User Value:** Attorneys produce professional PDF/Word/PowerPoint exports with verified findings only.

**Stories:**
- 12.1: Implement Export Builder modal with section selection and reordering
- 12.2: Implement inline editing and export preview
- 12.3: Implement verification check on export and format generation (PDF, Word, PowerPoint)
- 12.4: Implement partner executive summary export (one-click, 1-2 page PDF)

**FRs Covered:** FR18
**NFRs Addressed:** NFR24

---

### Epic 13: Observability & Production Hardening
**Goal:** Ensure production reliability, monitoring, and error handling with clear user feedback.

**User Value:** Attorneys experience a reliable, fast system that clearly communicates when something goes wrong and recovers gracefully.

**Stories:**
- 13.1: Implement Axiom logging integration with structured JSON and correlation IDs
- 13.2: Implement circuit breakers with tenacity (3 retries, 30s timeout for LLM calls)
- 13.3: Implement rate limiting via slowapi middleware (100 req/min per user)
- 13.4: Implement graceful degradation and error states across UI
- 13.5: Configure production deployment (Vercel, Railway, Supabase, Upstash)
- 13.6: Implement user-facing error messages with actionable guidance (retry, contact support, wait)

**FRs Covered:** Additional Architecture Requirements
**NFRs Addressed:** NFR21, NFR25, NFR26, NFR27

---

## Detailed Story Specifications

### Epic 1: Project Foundation & Authentication

#### Story 1.1: Initialize Next.js 16 Frontend Project

As a **developer**,
I want **a properly configured Next.js 16 frontend project with TypeScript, shadcn/ui, Tailwind CSS, and Zustand**,
So that **I have a production-ready foundation for building the LDIP user interface**.

**Acceptance Criteria:**

**Given** the LDIP repository is empty
**When** I run the project initialization commands
**Then** a Next.js 16 project is created with App Router enabled
**And** TypeScript is configured with strict mode
**And** Tailwind CSS is installed and configured with the LDIP design tokens
**And** shadcn/ui is initialized with the default components
**And** Zustand is installed for state management
**And** ESLint and Prettier are configured with consistent rules
**And** the project runs successfully with `npm run dev`

---

#### Story 1.2: Initialize FastAPI Backend Project

As a **developer**,
I want **a properly configured FastAPI backend project with Python 3.12+, Pydantic v2, and SQLAlchemy 2.0**,
So that **I have a production-ready foundation for building the LDIP API**.

**Acceptance Criteria:**

**Given** the backend directory is empty
**When** I run `uv init` and configure the project
**Then** a FastAPI project is created with Python 3.12+ configured
**And** Pydantic v2 is installed for request/response validation
**And** SQLAlchemy 2.0 is installed with async support
**And** alembic is configured for database migrations
**And** the project structure follows FastAPI best practices (routers, services, models directories)
**And** pytest is configured for testing
**And** the server runs successfully with `uvicorn`

---

#### Story 1.3: Implement Supabase Auth Integration

As an **attorney**,
I want **to sign up and log in using email/password, magic link, or Google OAuth**,
So that **I can securely access my LDIP account with my preferred authentication method**.

**Acceptance Criteria:**

**Given** I am on the login page
**When** I enter my email and password and click "Sign In"
**Then** I am authenticated and redirected to the dashboard
**And** my session is established with Supabase Auth

**Given** I am on the login page
**When** I enter my email and click "Send Magic Link"
**Then** I receive an email with a one-time login link
**And** clicking the link logs me in and redirects to the dashboard

**Given** I am on the login page
**When** I click "Sign in with Google"
**Then** I am redirected to Google OAuth flow
**And** after successful authentication, I am redirected to the dashboard

**Given** I am a new user
**When** I complete the signup form with email and password
**Then** a user record is created in the `users` table with user_id, email, full_name, avatar_url, created_at
**And** I receive a verification email (if email verification is enabled)

---

#### Story 1.4: Implement JWT Token Handling and Session Management

As an **attorney**,
I want **my authentication session to persist and automatically refresh**,
So that **I don't have to log in repeatedly during my work session**.

**Acceptance Criteria:**

**Given** I am logged in with a valid JWT token
**When** I make API requests
**Then** the JWT token is included in the Authorization header
**And** requests are authenticated successfully

**Given** my JWT token is about to expire (within 5 minutes)
**When** I make an API request
**Then** the token is automatically refreshed using the refresh token
**And** the new token is stored in the browser

**Given** my refresh token has expired
**When** I make an API request
**Then** I am redirected to the login page
**And** a message indicates my session has expired

**Given** I click "Logout"
**When** the logout action completes
**Then** my session is invalidated
**And** my tokens are cleared from storage
**And** I am redirected to the login page

---

#### Story 1.5: Implement Password Reset Flow

As an **attorney**,
I want **to reset my password if I forget it**,
So that **I can regain access to my LDIP account without contacting support**.

**Acceptance Criteria:**

**Given** I am on the login page
**When** I click "Forgot Password"
**Then** I am shown a form to enter my email address

**Given** I enter my registered email and click "Send Reset Link"
**When** the request is processed
**Then** I receive an email with a password reset link (valid for 1 hour)
**And** the UI shows "Check your email for reset instructions"

**Given** I click the password reset link in my email
**When** the link is valid and not expired
**Then** I am shown a form to enter a new password

**Given** I enter a valid new password (meets complexity requirements)
**When** I click "Reset Password"
**Then** my password is updated
**And** I am redirected to the login page with a success message
**And** I can log in with my new password

**Given** I click an expired or already-used reset link
**When** the page loads
**Then** I see an error message "This reset link has expired or already been used"
**And** I am prompted to request a new reset link

---

#### Story 1.6: Implement Role-Per-Matter Model

As a **matter owner**,
I want **to assign roles (Owner, Editor, Viewer) to attorneys on my matters**,
So that **I can control who can view, edit, or manage each matter**.

**Acceptance Criteria:**

**Given** I have created a new matter
**When** the matter is created
**Then** I am automatically assigned as the "Owner" role
**And** a record is created in the `matter_attorneys` table with matter_id, user_id, role="owner", invited_by, invited_at

**Given** I am an Owner of a matter
**When** I invite another attorney by email with role "Editor"
**Then** a record is created in `matter_attorneys` with role="editor"
**And** the invited user can access the matter with edit permissions

**Given** I am an Owner of a matter
**When** I invite another attorney with role "Viewer"
**Then** a record is created in `matter_attorneys` with role="viewer"
**And** the invited user can only view the matter (read-only access)

**Given** I am an Editor on a matter
**When** I try to delete the matter or change sharing settings
**Then** the action is denied with a permission error
**And** only Owners can delete or manage sharing

---

#### Story 1.7: Implement PostgreSQL RLS Policies for 4-Layer Matter Isolation

As an **attorney**,
I want **my matters to be completely isolated from other users' matters**,
So that **no one can ever access my confidential legal documents**.

**Acceptance Criteria:**

**Given** RLS policies are enabled on matter-related tables (matters, documents, findings, matter_memory, etc.)
**When** I query for documents
**Then** I only see documents from matters where I have a role in `matter_attorneys`
**And** no query can return data from matters I'm not assigned to

**Given** the vector embeddings use namespace prefix `matter_{id}_`
**When** a semantic search is performed
**Then** only embeddings from the specified matter are searched
**And** cross-matter embedding pollution is impossible

**Given** Redis cache keys use prefix `matter:{id}:`
**When** cache operations are performed
**Then** only cache entries for the authorized matter are accessible
**And** no cache key collision can occur between matters

**Given** API middleware validates matter access
**When** any API endpoint is called with a matter_id
**Then** the middleware verifies the user has a role on that matter
**And** returns 403 Forbidden if access is not authorized

---

### Epic 2: Document Ingestion & Processing Pipeline

#### Story 2.1: Implement Document Upload UI

As an **attorney**,
I want **to upload PDF and ZIP files via drag-and-drop with clear progress indicators**,
So that **I can easily add case documents to my matter**.

**Acceptance Criteria:**

**Given** I am in a matter workspace or upload flow
**When** I drag files onto the drop zone
**Then** the drop zone highlights to indicate it will accept the files
**And** supported file types (PDF, ZIP) are accepted
**And** unsupported file types show an error message

**Given** I drop valid files
**When** the upload begins
**Then** I see a progress bar for each file showing upload percentage
**And** I see the file name and size

**Given** a file exceeds 500MB
**When** I attempt to upload it
**Then** the file is rejected with message "File exceeds 500MB limit"

**Given** I have more than 100 files to upload
**When** I attempt to upload them
**Then** only the first 100 are accepted
**And** I see a warning "Maximum 100 files per upload"

**Given** I click "Browse Files" button
**When** the file picker opens
**Then** I can select PDF and ZIP files from my computer
**And** selected files are added to the upload queue

---

#### Story 2.2: Implement Supabase Storage Integration

As a **developer**,
I want **documents stored in Supabase Storage with proper folder structure**,
So that **files are organized by matter and type with security enforced**.

**Acceptance Criteria:**

**Given** a user uploads a case file
**When** the file is stored
**Then** it is saved to `documents/{matter_id}/uploads/{filename}`
**And** the storage path is recorded in the documents table

**Given** a user uploads an Act document
**When** the file is stored
**Then** it is saved to `documents/{matter_id}/acts/{filename}`
**And** the document is marked as is_reference_material=true

**Given** a user without access to a matter
**When** they attempt to access a file via storage URL
**Then** access is denied by Supabase Storage RLS policies
**And** a 403 error is returned

**Given** a ZIP file is uploaded
**When** processing begins
**Then** the ZIP is extracted
**And** each PDF inside is stored individually in the uploads folder
**And** the original ZIP is deleted after successful extraction

---

#### Story 2.3: Implement Documents Table

As a **developer**,
I want **a documents table tracking all uploaded files with metadata**,
So that **the system can manage document lifecycle and types**.

**Acceptance Criteria:**

**Given** a document is uploaded
**When** the record is created
**Then** the documents table contains: document_id, matter_id, filename, storage_path, file_size, page_count, document_type, is_reference_material, uploaded_by, uploaded_at, status, processing_started_at, processing_completed_at

**Given** document_type is specified
**When** the document is created
**Then** valid types are: case_file, act, annexure, other
**And** invalid types are rejected

**Given** a document is an Act
**When** is_reference_material is set
**Then** it is true for Acts and false for case files
**And** this flag affects how the document is used in citation verification

**Given** RLS policies are applied
**When** a user queries documents
**Then** only documents from their authorized matters are returned

---

#### Story 2.4: Integrate Google Document AI for OCR

As an **attorney**,
I want **uploaded PDFs to be OCR-processed with high accuracy**,
So that **scanned documents become searchable and analyzable**.

**Acceptance Criteria:**

**Given** a PDF document is uploaded
**When** OCR processing begins
**Then** Google Document AI extracts text from each page
**And** per-word confidence scores are captured
**And** bounding box coordinates are extracted for each text block

**Given** a page contains a mix of text and images
**When** OCR is performed
**Then** text from images is extracted
**And** native text is preserved with its positions

**Given** a document is in Indian languages (Gujarati, Hindi, English)
**When** OCR is performed
**Then** text is correctly extracted in the original language
**And** mixed-language documents are handled correctly

**Given** OCR completes for a document
**When** results are saved
**Then** extracted text is stored with page numbers
**And** processing status is updated to "ocr_complete"

**Given** Google Document AI is unavailable or returns an error
**When** OCR is attempted
**Then** the document is queued for automatic retry with exponential backoff
**And** after 3 failed retries, the document is marked as "ocr_failed" with error details
**And** the user is notified and can manually trigger retry later

---

#### Story 2.5: Implement Gemini-Based OCR Validation

As an **attorney**,
I want **low-confidence OCR results to be validated and corrected**,
So that **critical information like dates and amounts is accurate**.

**Acceptance Criteria:**

**Given** a word has confidence score < 85%
**When** validation runs
**Then** the word is flagged for Gemini validation
**And** surrounding context is sent to Gemini for correction

**Given** a date or amount has low confidence
**When** Gemini validates it
**Then** pattern-based auto-correction is applied (e.g., "1O" → "10")
**And** the corrected value replaces the original

**Given** a word has confidence score < 50%
**When** validation runs
**Then** the word is routed to a human review queue
**And** marked as "requires_human_review"

**Given** Gemini validation completes
**When** results are saved
**Then** the validated text replaces the original
**And** a validation_log records original, corrected, and confidence

---

#### Story 2.5.1: Display OCR Quality Assessment

As an **attorney**,
I want **to see OCR quality metrics before relying on extracted text**,
So that **I know if a document needs manual review due to poor scan quality**.

**Acceptance Criteria:**

**Given** OCR completes for a document
**When** I view the document in the Documents tab
**Then** I see an OCR quality indicator (Good >85%, Fair 70-85%, Poor <70%)
**And** the indicator is based on average word confidence across all pages

**Given** a document has Poor OCR quality (<70% confidence)
**When** processing completes
**Then** a warning badge appears on the document row
**And** a tooltip explains "Low OCR confidence - some text may be inaccurate"

**Given** I click on a Poor quality document
**When** the detail view opens
**Then** I see a page-by-page breakdown of confidence scores
**And** pages with <60% confidence are highlighted
**And** I see a "Request Manual Review" button

**Given** I click "Request Manual Review"
**When** the dialog opens
**Then** I can flag specific pages for manual transcription
**And** those pages are added to a review queue
**And** the document status shows "Partial - awaiting manual review"

---

#### Story 2.6: Create Bounding Boxes Table

As a **developer**,
I want **bounding box coordinates stored for all extracted text**,
So that **the UI can highlight exact text locations in documents**.

**Acceptance Criteria:**

**Given** OCR extracts text from a page
**When** bounding boxes are saved
**Then** the bounding_boxes table contains: bbox_id, document_id, page_number, x, y, width, height, text_content, confidence_score

**Given** a chunk references text
**When** the chunk is created
**Then** it links to one or more bbox_ids
**And** the UI can retrieve coordinates for highlighting

**Given** a citation is found in a document
**When** it is stored
**Then** it references the bbox_ids for the citation text
**And** clicking the citation highlights the exact location

**Given** multiple text blocks are on a page
**When** bounding boxes are stored
**Then** they are ordered by reading order (top-to-bottom, left-to-right)

---

#### Story 2.7: Implement Parent-Child Chunking

As a **developer**,
I want **documents chunked with parent-child hierarchy**,
So that **semantic search returns relevant context while maintaining precision**.

**Acceptance Criteria:**

**Given** a document is processed
**When** chunking begins
**Then** parent chunks are created at 1500-2000 tokens preserving document structure (paragraphs, sections)
**And** child chunks are created at 400-700 tokens with 50-100 token overlap

**Given** a child chunk is created
**When** it is stored
**Then** it links to its parent chunk via parent_chunk_id
**And** it links to its source bounding_boxes

**Given** semantic search returns a child chunk
**When** context is needed
**Then** the parent chunk can be retrieved for expanded context
**And** the UI can show surrounding text

**Given** a document has clear section headers
**When** chunking is performed
**Then** section boundaries are respected
**And** chunks don't split mid-sentence when possible

---

#### Story 2.8: Implement Hybrid Search with RRF Fusion

As an **attorney**,
I want **search to find relevant content using both keywords and meaning**,
So that **I can find documents whether I remember exact terms or just concepts**.

**Acceptance Criteria:**

**Given** I search for a query
**When** hybrid search executes
**Then** BM25 keyword search runs via PostgreSQL tsvector
**And** semantic search runs via pgvector with HNSW index
**And** results are merged using Reciprocal Rank Fusion (RRF)

**Given** RRF fusion is applied
**When** results are merged
**Then** documents appearing in both result sets rank higher
**And** the top 20 candidates are returned for reranking

**Given** a matter has embeddings
**When** semantic search is performed
**Then** only embeddings with namespace prefix `matter_{id}_` are searched
**And** cross-matter results are impossible

**Given** a query contains exact legal terms (e.g., "Section 138 NI Act")
**When** search executes
**Then** BM25 finds exact matches
**And** semantic search finds conceptually similar content

---

#### Story 2.9: Integrate Cohere Rerank

As an **attorney**,
I want **search results ranked by relevance using AI**,
So that **the most pertinent documents appear first**.

**Acceptance Criteria:**

**Given** hybrid search returns 20 candidates
**When** Cohere Rerank v3 processes them
**Then** candidates are reranked by relevance to the query
**And** the top 3 most relevant are returned

**Given** reranking is applied
**When** results are returned
**Then** each result includes a relevance_score from Cohere
**And** results are ordered by this score descending

**Given** a query is vague
**When** reranking occurs
**Then** Cohere identifies the most contextually relevant matches
**And** precision improves by 40-70% vs. hybrid search alone

**Given** Cohere API is unavailable
**When** reranking fails
**Then** the system falls back to RRF-ranked results
**And** a warning is logged

---

#### Story 2.10: Implement MIG Entity Extraction

As an **attorney**,
I want **people, organizations, and assets automatically extracted from documents**,
So that **I can see all parties and their relationships in my matter**.

**Acceptance Criteria:**

**Given** a document is processed
**When** entity extraction runs via Gemini
**Then** entities are extracted with types: PERSON, ORG, INSTITUTION, ASSET
**And** each entity is stored in identity_nodes table

**Given** an entity is extracted
**When** it is stored
**Then** identity_nodes contains: entity_id, matter_id, canonical_name, entity_type, metadata (roles, aliases found, first_mention_doc)

**Given** relationships between entities are detected
**When** they are stored
**Then** identity_edges contains: source_entity_id, target_entity_id, relationship_type (ALIAS_OF, HAS_ROLE, RELATED_TO), confidence

**Given** an entity appears in multiple documents
**When** extraction runs
**Then** document references are stored in pre_linked_relationships
**And** mention count is tracked per entity

---

#### Story 2.11: Implement Alias Resolution

As an **attorney**,
I want **name variants automatically linked to the same person**,
So that **"Nirav Jobalia", "N.D. Jobalia", and "Mr. Jobalia" all refer to one entity**.

**Acceptance Criteria:**

**Given** multiple name variants appear in documents
**When** alias resolution runs
**Then** variants are linked to a single canonical entity_id
**And** ALIAS_OF edges are created in identity_edges

**Given** a name is ambiguous (e.g., "Mr. Patel")
**When** resolution runs
**Then** context is used to determine which entity it refers to
**And** if uncertain, it remains unlinked with confidence < 0.7

**Given** an entity has aliases
**When** I search for any alias
**Then** all documents mentioning any alias are returned
**And** the entity detail shows all known aliases

**Given** the system incorrectly links two different people
**When** I view the Entities tab
**Then** I can use the merge/split dialog to correct the linking
**And** manual corrections persist and inform future extractions

---

#### Story 2.12: Implement Background Job Status Tracking and Retry

As an **attorney**,
I want **to see the status of document processing jobs and retry failed ones**,
So that **I know if something went wrong and can recover without losing work**.

**Acceptance Criteria:**

**Given** a document processing job is running
**When** I view the matter or dashboard
**Then** I see the current job status (queued, processing, stage X of Y, completed, failed)
**And** I see estimated time remaining for large jobs

**Given** a processing job fails at any stage (OCR, chunking, entity extraction, etc.)
**When** the failure occurs
**Then** the job is automatically retried up to 3 times with exponential backoff
**And** partial progress is preserved (completed pages are not reprocessed)
**And** the failure reason is logged

**Given** a job has failed after all retry attempts
**When** I view the Documents tab
**Then** the document shows "Processing Failed" status with error details
**And** I see a "Retry" button to manually trigger reprocessing
**And** I see a "Skip" option to proceed without this document

**Given** I am an admin or matter owner
**When** I view processing status
**Then** I can see all jobs in the queue for my matters
**And** I can prioritize or cancel pending jobs

**Given** documents are still processing (OCR, chunking, or entity extraction in progress)
**When** I click "Enter Workspace" on the matter
**Then** I can access the workspace with partially available data
**And** tabs show what's ready vs. still processing (e.g., "Timeline (12 events)" vs. "Citations (processing...)")
**And** a banner indicates "Analysis in progress - some features updating"
**And** data updates in real-time as processing completes

---

### Epic 3: Citation Verification Engine

#### Story 3.1: Implement Act Citation Extraction

As an **attorney**,
I want **all Act citations automatically extracted from case documents**,
So that **I know which laws are referenced without reading everything**.

**Acceptance Criteria:**

**Given** a case document is processed
**When** citation extraction runs
**Then** citations like "Section 138 of the Negotiable Instruments Act, 1881" are identified
**And** each citation is parsed into: act_name, section_number, subsection, clause

**Given** a citation uses abbreviations
**When** extraction runs
**Then** common abbreviations are recognized (e.g., "NI Act" = "Negotiable Instruments Act")
**And** the full Act name is stored

**Given** citations are extracted
**When** they are stored
**Then** the citations table contains: citation_id, matter_id, document_id, page_number, bbox_ids, act_name, section_number, raw_text, verification_status

**Given** a document references multiple Acts
**When** extraction completes
**Then** all unique Acts are identified
**And** a count of citations per Act is available

---

#### Story 3.2: Implement Act Discovery Report

As an **attorney**,
I want **to see which Acts are referenced and which are available for verification**,
So that **I can upload missing Acts to enable full verification**.

**Acceptance Criteria:**

**Given** citation extraction is complete
**When** I view the Act Discovery Report
**Then** I see a list of all Acts referenced in my documents
**And** each Act shows: name, citation count, availability status (Available/Missing)

**Given** an Act is marked as "Missing"
**When** I click "Upload Act"
**Then** I can upload the Act PDF
**And** the Act is stored in documents/{matter_id}/acts/
**And** its status changes to "Available"

**Given** I choose not to upload an Act
**When** I click "Skip this Act"
**Then** the Act remains marked as "Missing"
**And** citations to it are marked "Unverified - Act not provided"

**Given** I click "Continue with Partial Verification"
**When** processing continues
**Then** citations to available Acts are verified
**And** citations to missing Acts show graceful degradation status

---

#### Story 3.3: Implement Citation Verification

As an **attorney**,
I want **citations verified against the actual Act text**,
So that **I know if sections exist and quoted text is accurate**.

**Acceptance Criteria:**

**Given** a citation references Section 138 of NI Act
**When** the NI Act is uploaded and indexed
**Then** the system checks if Section 138 exists in the Act
**And** verification_status is set to: verified, mismatch, section_not_found, or act_unavailable

**Given** a citation includes quoted text from the Act
**When** verification runs
**Then** the quoted text is compared against the actual Act text
**And** mismatches are flagged with explanation

**Given** a citation references a section that doesn't exist
**When** verification runs
**Then** the citation is marked as "section_not_found"
**And** a confidence score is assigned based on fuzzy matching

**Given** an Act is not uploaded
**When** verification runs
**Then** the citation is marked "Unverified - Act not provided"
**And** verification can be completed later when Act is uploaded

---

#### Story 3.4: Implement Split-View Citation Highlighting

As an **attorney**,
I want **to see the case document and Act side-by-side with citations highlighted**,
So that **I can visually verify the citation accuracy**.

**Acceptance Criteria:**

**Given** I click on a citation in the Citations tab
**When** the split view opens
**Then** the left panel shows the case document at the citation location
**And** the right panel shows the Act document at the referenced section
**And** both locations are highlighted with bounding boxes

**Given** the split view is open
**When** I view the citation
**Then** the case document highlights the citation text in yellow
**And** the Act document highlights the referenced section in blue

**Given** a citation has a mismatch
**When** I view it in split view
**Then** the differing text is highlighted in red
**And** the explanation appears above the panels

**Given** an Act is not available
**When** I click the citation
**Then** only the case document panel is shown
**And** a message indicates "Act not uploaded"

---

### Epic 4: Timeline Construction Engine

#### Story 4.1: Implement Date Extraction

As an **attorney**,
I want **all dates extracted from documents with surrounding context**,
So that **I can understand what happened and when**.

**Acceptance Criteria:**

**Given** a document is processed
**When** date extraction runs via Gemini
**Then** dates are extracted in various formats (DD/MM/YYYY, Month DD, YYYY, etc.)
**And** ±200 words of surrounding context are captured

**Given** a date is ambiguous (e.g., 01/02/2024)
**When** extraction runs
**Then** context is used to determine DD/MM vs MM/DD
**And** if uncertain, a date_ambiguity flag is set

**Given** a date is extracted
**When** it is stored
**Then** the raw_events table contains: event_id, matter_id, document_id, page_number, extracted_date, date_confidence, context_text, bbox_ids

**Given** multiple dates appear in close proximity
**When** extraction runs
**Then** each date is extracted separately
**And** context distinguishes their purposes

---

#### Story 4.2: Implement Event Classification

As an **attorney**,
I want **dates classified by event type (filing, notice, hearing, etc.)**,
So that **I can filter and understand the timeline by event category**.

**Acceptance Criteria:**

**Given** a date with context is extracted
**When** classification runs
**Then** the event is assigned a type: filing, notice, hearing, order, transaction, document, deadline
**And** classification confidence is recorded

**Given** context mentions "filed on"
**When** classification runs
**Then** the event is classified as "filing"

**Given** context mentions "next hearing"
**When** classification runs
**Then** the event is classified as "hearing"

**Given** classification is uncertain
**When** confidence < 0.7
**Then** the event type is marked as "unclassified"
**And** it appears in verification queue for manual classification

---

#### Story 4.3: Implement Events Table with MIG Integration

As a **developer**,
I want **events stored with entity links and chronological ordering**,
So that **timelines can show who was involved in each event**.

**Acceptance Criteria:**

**Given** an event is created
**When** it is stored
**Then** the events table contains: event_id, matter_id, document_id, event_date, event_type, title, description, entity_ids (array), bbox_ids, source_text, confidence, verified

**Given** an event mentions "Nirav Jobalia filed a petition"
**When** entity linking runs
**Then** the event's entity_ids includes the canonical entity_id for Nirav Jobalia

**Given** multiple events exist for a matter
**When** timeline is constructed
**Then** events are ordered by event_date ascending
**And** events on the same date maintain document order

**Given** timeline data is needed frequently
**When** timeline is generated
**Then** it is cached in Matter Memory at /matter-{id}/timeline_cache.jsonb
**And** cache is invalidated when new documents are uploaded

---

#### Story 4.4: Implement Timeline Anomaly Detection

As an **attorney**,
I want **unusual timeline patterns flagged automatically**,
So that **I notice potential issues like "9 months between notice and filing"**.

**Acceptance Criteria:**

**Given** a timeline is constructed
**When** anomaly detection runs
**Then** logical sequence violations are flagged (e.g., hearing before filing)
**And** unusual gaps are flagged with context

**Given** a notice period appears unusually long
**When** detection runs
**Then** a warning is generated: "Notice dated 9 months after borrower default - verify"
**And** the anomaly appears in the attention banner

**Given** events are out of expected order
**When** detection runs
**Then** sequence violations are flagged with severity
**And** explanations suggest possible causes (date error, exceptional circumstances)

**Given** an anomaly is detected
**When** it is stored
**Then** anomalies table contains: anomaly_id, matter_id, event_ids involved, anomaly_type, severity, explanation, verified

---

### Epic 5: Consistency & Contradiction Engine

#### Story 5.1: Implement Entity-Grouped Statement Querying

As an **attorney**,
I want **all statements about an entity grouped together**,
So that **I can compare what different documents say about the same person or organization**.

**Acceptance Criteria:**

**Given** an entity exists in the MIG
**When** I request statements about that entity
**Then** all chunks mentioning the entity's canonical_id or aliases are retrieved
**And** statements are grouped by document source

**Given** an entity has multiple aliases
**When** statement querying runs
**Then** mentions of any alias are included
**And** all are attributed to the canonical entity

**Given** a statement mentions dates or amounts related to an entity
**When** it is retrieved
**Then** the specific values are extracted and structured
**And** they can be compared across statements

**Given** no statements exist for an entity
**When** querying runs
**Then** an empty result is returned
**And** no error occurs

---

#### Story 5.2: Implement Statement Pair Comparison

As an **attorney**,
I want **statements compared pairwise to detect contradictions**,
So that **I find conflicts like different dates for the same event**.

**Acceptance Criteria:**

**Given** multiple statements exist about an entity
**When** comparison runs via GPT-4 chain-of-thought
**Then** each unique pair of statements is compared
**And** potential contradictions are identified

**Given** two statements claim different loan amounts
**When** comparison runs
**Then** the contradiction is detected
**And** both amounts are extracted for display

**Given** statements are consistent
**When** comparison runs
**Then** no contradiction is flagged
**And** the pair is marked as "consistent"

**Given** comparison requires reasoning
**When** GPT-4 processes the pair
**Then** chain-of-thought reasoning is recorded
**And** the reasoning is available for attorney review

---

#### Story 5.3: Implement Contradiction Type Classification

As an **attorney**,
I want **contradictions classified by type**,
So that **I can prioritize factual contradictions over semantic ones**.

**Acceptance Criteria:**

**Given** a contradiction is detected
**When** classification runs
**Then** it is assigned a type: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch

**Given** two statements disagree on a date
**When** classification runs
**Then** the type is "date_mismatch"
**And** both dates are extracted and displayed

**Given** two statements disagree on an amount (loan, payment, etc.)
**When** classification runs
**Then** the type is "amount_mismatch"
**And** both amounts are extracted and displayed

**Given** statements conflict in meaning but not on specific facts
**When** classification runs
**Then** the type is "semantic_contradiction"
**And** the explanation highlights the semantic conflict

---

#### Story 5.4: Implement Severity Scoring and Explanation

As an **attorney**,
I want **contradictions scored by severity with explanations**,
So that **I focus on the most critical issues first**.

**Acceptance Criteria:**

**Given** a contradiction is detected
**When** severity scoring runs
**Then** severity is assigned: high, medium, or low

**Given** a contradiction involves clear factual differences (dates, amounts)
**When** scoring runs
**Then** severity is "high"

**Given** a contradiction requires interpretation
**When** scoring runs
**Then** severity is "medium"

**Given** a contradiction is possible but uncertain
**When** scoring runs
**Then** severity is "low"

**Given** a contradiction is scored
**When** it is displayed
**Then** a natural language explanation is provided
**And** evidence links show both statements with document sources

---

### Epic 6: Engine Orchestrator

#### Story 6.1: Implement Query Intent Analysis

As an **attorney**,
I want **my questions automatically routed to the right analysis engine**,
So that **I get the best answer without knowing which engine to use**.

**Acceptance Criteria:**

**Given** I ask "What are all the citations in this case?"
**When** intent analysis runs
**Then** the query is routed to the Citation Engine
**And** citation results are returned

**Given** I ask "What happened in chronological order?"
**When** intent analysis runs
**Then** the query is routed to the Timeline Engine
**And** timeline results are returned

**Given** I ask "Are there any contradictions about the loan amount?"
**When** intent analysis runs
**Then** the query is routed to the Contradiction Engine
**And** contradiction results are returned

**Given** I ask a general question
**When** intent analysis runs
**Then** RAG search is used
**And** relevant chunks are returned with sources

---

#### Story 6.2: Implement Engine Execution and Result Aggregation

As an **attorney**,
I want **complex queries to use multiple engines with combined results**,
So that **I get comprehensive answers**.

**Acceptance Criteria:**

**Given** a query requires multiple engines
**When** orchestration runs
**Then** engines are executed in the correct order (some parallel, some sequential)
**And** results are aggregated into a unified response

**Given** engines can run in parallel (e.g., Citation + Timeline)
**When** orchestration runs
**Then** both engines execute simultaneously
**And** response time is optimized

**Given** engines have dependencies (e.g., Contradiction needs MIG)
**When** orchestration runs
**Then** dependent engines wait for prerequisites
**And** correct execution order is maintained

**Given** all engine results are ready
**When** aggregation runs
**Then** results are combined into a coherent response
**And** sources from all engines are included

---

#### Story 6.3: Implement Audit Trail Logging

As an **attorney**,
I want **every query and its processing logged**,
So that **I have a forensic record of all analysis performed**.

**Acceptance Criteria:**

**Given** a query is processed
**When** logging runs
**Then** the audit trail records: query_id, query_text, query_intent, asked_by, asked_at, engines_invoked, execution_time_ms, findings_count, response_summary

**Given** engines produce findings
**When** logging runs
**Then** each finding is recorded with confidence score and source

**Given** LLM calls are made
**When** logging runs
**Then** token usage and cost are recorded
**And** total query cost is calculated

**Given** the audit trail is queried
**When** Matter Memory is accessed
**Then** /matter-{id}/query_history.jsonb contains all queries
**And** the log is append-only (forensic integrity)

---

### Epic 7: Three-Layer Memory System

#### Story 7.1: Implement Session Memory Redis Storage

As an **attorney**,
I want **my conversation context maintained during my session**,
So that **I can ask follow-up questions without repeating context**.

**Acceptance Criteria:**

**Given** I start a conversation in a matter
**When** the session is created
**Then** a Redis key is created: session:{matter_id}:{user_id}
**And** SessionContext is stored with session_id, matter_id, user_id, created_at, last_activity

**Given** I send a message
**When** the message is processed
**Then** it is added to the messages array in SessionContext
**And** last_activity is updated

**Given** the messages array grows
**When** it exceeds 20 messages
**Then** a sliding window removes the oldest messages
**And** the most recent 20 are retained

**Given** I mention entities in conversation
**When** tracking runs
**Then** entities_mentioned map is updated
**And** pronouns can be resolved to mentioned entities

---

#### Story 7.2: Implement Session TTL and Context Restoration

As an **attorney**,
I want **my session to persist for a week with automatic extension**,
So that **I can continue where I left off**.

**Acceptance Criteria:**

**Given** a session exists
**When** 7 days pass without activity
**Then** the session auto-expires
**And** is archived to Matter Memory before deletion

**Given** I am active in a session
**When** activity occurs
**Then** the TTL is extended (max 30 days total)
**And** the session persists

**Given** I log out or manually end the session
**When** the action completes
**Then** the session is cleared from Redis
**And** is archived to Matter Memory

**Given** a session has expired
**When** I return to the matter
**Then** context can be restored from the archived session in Matter Memory
**And** a new session is created with previous context available

---

#### Story 7.3: Implement Matter Memory PostgreSQL JSONB Storage

As an **attorney**,
I want **matter-level data persisted in the database**,
So that **query history, timelines, and entity graphs are available long-term**.

**Acceptance Criteria:**

**Given** a matter exists
**When** Matter Memory is accessed
**Then** the matter_memory table stores JSONB at paths like /matter-{id}/query_history.jsonb

**Given** query history is logged
**When** it is stored
**Then** /matter-{id}/query_history.jsonb contains append-only query records
**And** each record has query_id, query_text, asked_by, asked_at, response_summary, verified status

**Given** timeline is cached
**When** /matter-{id}/timeline_cache.jsonb is accessed
**Then** it contains cached_at, events array, last_document_upload for invalidation

**Given** entity graph is cached
**When** /matter-{id}/entity_graph.jsonb is accessed
**Then** it contains cached_at, entities map, relationships

---

#### Story 7.4: Implement Key Findings and Research Notes

As an **attorney**,
I want **to save verified findings and personal notes on a matter**,
So that **my analysis work is preserved and accessible**.

**Acceptance Criteria:**

**Given** I verify a finding
**When** it is saved
**Then** /matter-{id}/key_findings.jsonb is updated
**And** the finding includes finding_id, finding_type, description, evidence, verified_by, verified_at, notes

**Given** I create a research note
**When** it is saved
**Then** /matter-{id}/research_notes.jsonb is updated
**And** the note includes note_id, created_by, created_at, title, content (markdown), tags, linked_findings

**Given** RLS policies are applied
**When** Matter Memory is accessed
**Then** only users with roles on the matter can read/write
**And** cross-matter access is blocked

---

#### Story 7.5: Implement Query Cache

As an **attorney**,
I want **repeated queries to return instantly**,
So that **I don't wait for expensive LLM calls on identical questions**.

**Acceptance Criteria:**

**Given** I ask a query
**When** the query is processed
**Then** results are cached at cache:query:{matter_id}:{query_hash}
**And** query_hash is SHA256 of normalized query text

**Given** I ask the same query again
**When** cache is checked
**Then** cached results are returned in ~10ms
**And** no LLM calls are made

**Given** cache entry is 1 hour old
**When** TTL expires
**Then** the entry is automatically deleted
**And** next query runs fresh

**Given** I upload a new document
**When** upload completes
**Then** all cache entries for the matter are invalidated (pattern: cache:query:{matterId}:*)
**And** queries run fresh with new document content

---

### Epic 8: Safety Layer (Guardrails, Policing, Verification)

#### Story 8.1: Implement Fast-Path Regex Pattern Detection

As a **developer**,
I want **dangerous query patterns blocked instantly**,
So that **obvious legal conclusion requests don't reach the LLM**.

**Acceptance Criteria:**

**Given** a query matches dangerous patterns
**When** regex detection runs
**Then** patterns like /should (i|we|client) (file|appeal|settle)/i are matched
**And** the query is blocked before LLM processing

**Given** a query asks "Will the judge rule in my favor?"
**When** detection runs
**Then** it matches /will (judge|court) (rule|decide|hold)/i
**And** the query is blocked with an explanation

**Given** a query asks "What are my chances of winning?"
**When** detection runs
**Then** it matches /what are (my|our) chances/i
**And** the query is blocked

**Given** a query is blocked
**When** the response is returned
**Then** GuardrailCheck includes: is_safe=false, violation_type, explanation, suggested_rewrite

---

#### Story 8.2: Implement GPT-4o-mini Subtle Violation Detection

As a **developer**,
I want **subtle legal conclusion requests detected by AI**,
So that **cleverly worded requests are still blocked**.

**Acceptance Criteria:**

**Given** a query passes regex detection
**When** subtle detection runs via GPT-4o-mini
**Then** the query is analyzed for implicit legal conclusions
**And** violations are detected

**Given** a query asks "Based on this evidence, is it clear that..."
**When** detection runs
**Then** the implicit conclusion request is detected
**And** the query is blocked

**Given** a violation is detected
**When** the response is returned
**Then** a contextual rewrite is suggested
**And** the rewrite removes the conclusion-seeking aspect

**Given** GPT-4o-mini approves the query
**When** processing continues
**Then** the query is marked as safe
**And** normal processing proceeds

---

#### Story 8.3: Implement Language Policing

As an **attorney**,
I want **all LLM outputs sanitized of legal conclusions**,
So that **I never see unprofessional language in LDIP responses**.

**Acceptance Criteria:**

**Given** LLM output contains "violated Section X"
**When** policing runs
**Then** it is replaced with "affected by Section X"

**Given** LLM output contains "defendant is guilty"
**When** policing runs
**Then** it is replaced with "defendant's liability regarding"

**Given** LLM output contains "the court will rule"
**When** policing runs
**Then** it is replaced with "the court may consider"

**Given** LLM output contains "proves that"
**When** policing runs
**Then** it is replaced with "suggests that"

**Given** regex replacements complete
**When** subtle policing runs via GPT-4o-mini
**Then** remaining conclusions are removed or rephrased
**And** the final output is 100% sanitized

**Given** text is a direct quote from a source document (indicated by quotation marks or explicit citation reference)
**When** language policing runs
**Then** the original quoted text is preserved verbatim
**And** a note indicates "Direct quote from [document name, page X]"
**And** no sanitization is applied to the quoted content

---

#### Story 8.4: Implement Finding Verifications Table

As a **developer**,
I want **verification records stored for all findings**,
So that **attorney approvals are tracked for audit and export**.

**Acceptance Criteria:**

**Given** a finding is generated by an engine
**When** it is created
**Then** finding_verifications table records: verification_id, matter_id, finding_id, finding_type, finding_summary, verified_by (null), decision (pending)

**Given** an attorney verifies a finding
**When** approval is recorded
**Then** verified_by, verified_at, decision (approved/rejected/flagged), notes are updated
**And** confidence_before and confidence_after are recorded

**Given** finding confidence is > 90%
**When** verification requirement is checked
**Then** verification is optional (informational only)

**Given** finding confidence is 70-90%
**When** verification requirement is checked
**Then** verification is suggested (badge shown)

**Given** finding confidence is < 70%
**When** verification requirement is checked
**Then** verification is required before export

---

#### Story 8.5: Implement Verification Queue UI

As an **attorney**,
I want **a queue of findings awaiting my verification**,
So that **I can efficiently review and approve findings**.

**Acceptance Criteria:**

**Given** I open the Verification tab
**When** the queue loads
**Then** I see a DataTable with columns: finding type, description, confidence (progress bar), source, actions

**Given** I select multiple findings
**When** I click "Approve Selected"
**Then** all selected findings are marked as approved
**And** verified_by and verified_at are recorded

**Given** I click "Reject" on a finding
**When** the action dialog opens
**Then** I am prompted to enter a rejection reason
**And** the finding is marked rejected with notes

**Given** I click "Flag" on a finding
**When** the action dialog opens
**Then** I can flag for review with notes
**And** the finding remains in the queue with "flagged" status

**Given** I filter the queue
**When** filters are applied
**Then** I can filter by finding type, confidence tier, verification status
**And** the table updates accordingly

---

### Epic 9: Dashboard & Upload Experience

#### Story 9.1: Implement Dashboard Header

As an **attorney**,
I want **a consistent header with navigation and user controls**,
So that **I can access key features from anywhere in the app**.

**Acceptance Criteria:**

**Given** I am logged in
**When** the dashboard loads
**Then** the header shows: LDIP logo, global search bar, notifications badge (with count), help button, user profile dropdown

**Given** I click the notifications badge
**When** the dropdown opens
**Then** I see recent notifications (processing complete, verification needed, etc.)
**And** I can mark notifications as read

**Given** I click the user profile dropdown
**When** it opens
**Then** I see my name and avatar
**And** options: Settings, Help, Logout

**Given** I use the global search
**When** I enter a query
**Then** I can search across all my matters
**And** results show matter names and matched content

---

#### Story 9.2: Implement Matter Cards Grid

As an **attorney**,
I want **to see all my matters as cards with status information**,
So that **I can quickly assess my work and continue where I left off**.

**Acceptance Criteria:**

**Given** I have multiple matters
**When** the dashboard loads
**Then** matters are displayed as cards in a grid (70% of viewport width)
**And** each card shows: matter name, status badge, page count, last activity, verification %, issue count

**Given** a matter is processing
**When** its card is displayed
**Then** it shows a progress bar with percentage
**And** estimated time remaining and doc/page counts

**Given** a matter is ready
**When** its card is displayed
**Then** it shows "Ready" status badge
**And** a "Resume" button to enter the workspace

**Given** I click the view toggle
**When** I switch between grid and list
**Then** the layout changes accordingly
**And** my preference is remembered

**Given** I use sort and filter controls
**When** I select options
**Then** matters are sorted by: Recent, Alphabetical, Most pages, Least verified, Date created
**And** filtered by: All, Processing, Ready, Needs attention, Archived

---

#### Story 9.3: Implement Activity Feed and Quick Stats

As an **attorney**,
I want **to see recent activity and summary statistics**,
So that **I know what's happening across my matters**.

**Acceptance Criteria:**

**Given** I view the dashboard
**When** activity feed loads (30% of viewport width)
**Then** I see recent activities with icon-coded entries
**And** colors indicate: green=success, blue=info, yellow=in progress, orange=attention, red=error

**Given** activity entries exist
**When** I view them
**Then** each shows: icon, matter name, action description, timestamp
**And** clicking an entry navigates to the relevant matter/tab

**Given** I view quick stats panel
**When** it loads
**Then** I see: active matters count, verified findings count, pending reviews count
**And** stats update in real-time

---

#### Story 9.4: Implement Upload Flow Stages 1-2

As an **attorney**,
I want **a guided flow to upload documents and name my matter**,
So that **I can easily start a new case analysis**.

**Acceptance Criteria:**

**Given** I click "+ New Matter"
**When** Stage 1 (File Selection) opens
**Then** I see a drag-drop zone with icon animation
**And** "Browse Files" button, supported formats note (PDF, ZIP), limits note (500MB/file, 100 files)

**Given** I drop or select files
**When** Stage 2 (Review & Name) appears
**Then** I see an auto-generated matter name (editable)
**And** file list with remove option for each file

**Given** citations are detected
**When** Act Discovery Report modal appears
**Then** I see which Acts are referenced and which are available/missing
**And** options: upload missing Acts, skip specific Acts, continue with partial verification

**Given** I complete Stage 2
**When** I click "Start Processing"
**Then** the upload begins and Stage 3 appears

---

#### Story 9.5: Implement Upload Flow Stages 3-4

As an **attorney**,
I want **to see upload progress and live discoveries**,
So that **I know processing is working and what's being found**.

**Acceptance Criteria:**

**Given** upload begins (Stage 3)
**When** files are uploading
**Then** I see file-by-file progress bars with checkmarks on completion
**And** overall progress percentage

**Given** processing begins (Stage 4)
**When** analysis runs
**Then** I see overall progress bar with stage indicator ("Stage 3 of 5: Extracting entities")
**And** split view showing: document processing progress, live discoveries panel

**Given** live discoveries are found
**When** the panel updates
**Then** I see: entities found with roles, dates extracted (earliest/latest), citations detected by Act, mini timeline preview, early insights with warnings

**Given** I want to continue working
**When** I click "Continue in Background"
**Then** I return to the dashboard
**And** the matter card shows processing progress

---

#### Story 9.6: Implement Upload Flow Stage 5 and Notifications

As an **attorney**,
I want **to be notified when processing completes**,
So that **I know when my matter is ready for analysis**.

**Acceptance Criteria:**

**Given** processing completes (Stage 5)
**When** I am viewing the upload flow
**Then** I am auto-redirected to the Matter Workspace

**Given** processing completes
**When** I had clicked "Continue in Background"
**Then** a browser notification appears: "Matter [name] is ready"
**And** clicking the notification opens the workspace

**Given** I am on the dashboard
**When** a matter finishes processing
**Then** the matter card updates to "Ready" status
**And** a notification badge updates

---

### Epic 10A: Workspace Shell & Navigation

#### Story 10A.1: Implement Workspace Shell

As an **attorney**,
I want **a consistent workspace layout with header controls**,
So that **I can navigate and manage my matter efficiently**.

**Acceptance Criteria:**

**Given** I enter a matter workspace
**When** the shell loads
**Then** the header shows: back to Dashboard, editable matter name, Export dropdown, Share button, Settings gear

**Given** I click the matter name
**When** edit mode activates
**Then** I can rename the matter
**And** the name updates across the system

**Given** I click Export
**When** the dropdown opens
**Then** I see format options (PDF, Word, PowerPoint)
**And** clicking an option opens the Export Builder

**Given** I click Share
**When** the dialog opens
**Then** I can invite attorneys by email with role selection (Editor, Viewer)
**And** see current collaborators

---

#### Story 10A.2: Implement Tab Bar

As an **attorney**,
I want **tabs to navigate between different analysis views**,
So that **I can switch between timeline, entities, citations, etc.**.

**Acceptance Criteria:**

**Given** I am in the workspace
**When** the tab bar loads
**Then** tabs appear in order: Summary → Timeline → Entities → Citations → Contradictions → Verification → Documents

**Given** I click a tab
**When** the tab activates
**Then** the main content area updates to show that tab's content
**And** the URL updates to reflect the active tab

**Given** findings need attention
**When** the tab bar renders
**Then** affected tabs show a badge with count (e.g., Citations (3))
**And** the badge indicates issues to review

**Given** documents are still processing (from Story 2C.3 AC#5)
**When** the tab bar renders
**Then** tabs show what's ready vs. still processing (e.g., "Timeline (12 events)" vs. "Entities (processing...)")
**And** loading placeholders appear for tabs still receiving data

---

#### Story 10A.3: Implement Main Content Area and Q&A Panel Integration

As an **attorney**,
I want **the main content area to work alongside the Q&A panel**,
So that **I can ask questions while viewing analysis results**.

**Acceptance Criteria:**

**Given** I am in the workspace
**When** content loads
**Then** the main content area shows the active tab content
**And** the Q&A panel appears in its configured position (default: right sidebar)

**Given** I resize the Q&A panel
**When** I drag the divider
**Then** the panel resizes (20-60% width range)
**And** the main content adjusts accordingly

**Given** I change Q&A panel position
**When** I select a new position (right, bottom, float, hide)
**Then** the panel moves to the new position
**And** my preference is saved

---

### Epic 10B: Summary & Timeline Tabs

#### Story 10B.1: Implement Summary Tab Content

As an **attorney**,
I want **a summary view of my matter with key information**,
So that **I can quickly understand the case at a glance**.

**Acceptance Criteria:**

**Given** I open the Summary tab
**When** content loads
**Then** I see: attention banner (items needing action), parties section, subject matter, current status, key issues, matter statistics

**Given** items need attention
**When** the attention banner shows
**Then** it lists: contradictions found, citation issues with count
**And** "Review All" links to the relevant tabs

**Given** parties are extracted
**When** the parties section shows
**Then** Petitioner and Respondent cards show entity links
**And** clicking an entity opens the Entities tab

**Given** matter statistics load
**When** the stats section shows
**Then** I see cards with: total pages, entities found, events extracted, citations found

---

#### Story 10B.2: Implement Summary Tab Verification and Edit

As an **attorney**,
I want **to verify and edit summary content inline**,
So that **I can correct AI-generated summaries**.

**Acceptance Criteria:**

**Given** a summary section is displayed
**When** I hover over it
**Then** I see inline buttons: [✓ Verify] [✗ Flag] [💬 Note]

**Given** I click [✓ Verify]
**When** verification is recorded
**Then** the section shows a "Verified" badge
**And** verified_by and verified_at are stored

**Given** I click the Edit button on a section
**When** edit mode activates
**Then** I can modify the text
**And** the original AI version is preserved
**And** I can click "Regenerate" for fresh AI analysis

**Given** factual claims are displayed
**When** citations are available
**Then** each claim shows a clickable citation link
**And** hovering shows a preview tooltip

---

#### Story 10B.3: Implement Timeline Tab Vertical List View

As an **attorney**,
I want **a chronological list of all events**,
So that **I can understand the sequence of the case**.

**Acceptance Criteria:**

**Given** I open the Timeline tab
**When** the default vertical list loads
**Then** events are displayed chronologically as cards
**And** the header shows event count and date range

**Given** an event card is displayed
**When** I view it
**Then** it shows: date, type icon (📋 Filing, ⚖️ Order, etc.), title, description, actor(s), source document+page, cross-references, verification status, contradiction flag if applicable

**Given** events have duration between them
**When** the list renders
**Then** connector lines show duration between events
**And** large gaps are visually emphasized

---

#### Story 10B.4: Implement Timeline Tab Alternative Views

As an **attorney**,
I want **different timeline visualizations**,
So that **I can view the timeline in the most useful format**.

**Acceptance Criteria:**

**Given** I am in the Timeline tab
**When** I click the view toggle
**Then** I can switch between: Vertical List (default), Horizontal Timeline, Multi-Track

**Given** I select Horizontal Timeline
**When** the view renders
**Then** events are displayed on a horizontal axis with zoom slider
**And** event clusters and gap indicators are visible

**Given** I select Multi-Track view
**When** the view renders
**Then** parallel timelines are shown by actor
**And** events are aligned vertically by date across tracks

---

#### Story 10B.5: Implement Timeline Tab Filtering and Manual Addition

As an **attorney**,
I want **to filter timeline events and add manual entries**,
So that **I can focus on specific events and add missing information**.

**Acceptance Criteria:**

**Given** I am in the Timeline tab
**When** I use filter controls
**Then** I can filter by: Event Type, Actors, Date Range, Verification Status
**And** the timeline updates to show only matching events

**Given** I click "Add Event"
**When** the dialog opens
**Then** I can enter: date, type, title, description, actor, source
**And** the event is marked as "Manually added"

**Given** I add a manual event
**When** it is saved
**Then** it appears in the timeline at the correct chronological position
**And** it can be edited or deleted

---

### Epic 10C: Entities & Citations Tabs

#### Story 10C.1: Implement Entities Tab Graph Visualization

As an **attorney**,
I want **to see entities and relationships as a visual graph**,
So that **I can understand the connections in my case**.

**Acceptance Criteria:**

**Given** I open the Entities tab
**When** the graph loads
**Then** entities are displayed as nodes using D3.js or React Flow
**And** relationships are shown as edges between nodes

**Given** nodes are displayed
**When** I view them
**Then** each shows: canonical name, entity type badge (PERSON, ORG, INSTITUTION, ASSET)
**And** node size reflects mention count

**Given** I click a node
**When** the selection activates
**Then** connected nodes are highlighted
**And** the detail panel shows entity information

---

#### Story 10C.2: Implement Entities Tab Detail Panel and Merge Dialog

As an **attorney**,
I want **to see entity details and merge incorrectly split entities**,
So that **I can correct entity linking errors**.

**Acceptance Criteria:**

**Given** I select an entity
**When** the detail panel opens
**Then** it shows: canonical name, aliases, relationship connections, document mentions with source links

**Given** I click on a mention
**When** the link activates
**Then** the PDF viewer opens to that location
**And** the entity mention is highlighted

**Given** I notice two nodes should be one entity
**When** I select both and click "Merge"
**Then** a dialog confirms the merge
**And** the entities are combined with aliases preserved

**Given** I filter entities
**When** I select entity type filters
**Then** only entities of selected types are shown
**And** statistics update to reflect filtered set

---

#### Story 10C.3: Implement Citations Tab List and Act Discovery

As an **attorney**,
I want **to see all citations with their verification status**,
So that **I can identify citation issues quickly**.

**Acceptance Criteria:**

**Given** I open the Citations tab
**When** the content loads
**Then** I see the Act Discovery Report summary (X Acts referenced, Y available, Z missing)
**And** a list of all extracted citations

**Given** citations are displayed
**When** I view the list
**Then** columns show: citation text, Act name, section, source document+page, verification status, confidence score

**Given** I filter citations
**When** I select filters
**Then** I can filter by: verification status (verified, mismatch, not_found, act_unavailable), Act name
**And** the list updates accordingly

**Given** an Act is missing
**When** I click "Upload Act"
**Then** I can upload the Act document
**And** citations are re-verified automatically

---

#### Story 10C.4: Implement Citations Tab Split-View Verification

As an **attorney**,
I want **to see citation source and target side-by-side**,
So that **I can visually verify citation accuracy**.

**Acceptance Criteria:**

**Given** I click a citation
**When** the split view opens
**Then** the left panel shows the case document at the citation location
**And** the right panel shows the Act document at the referenced section

**Given** both panels are displayed
**When** I view the citation
**Then** the case document highlights the citation in yellow
**And** the Act document highlights the referenced section in blue

**Given** a mismatch exists
**When** the split view shows it
**Then** differing text is highlighted in red
**And** an explanation describes the mismatch

---

### Epic 10D: Verification & Documents Tabs

> **Note (Decision 10, 2026-01-03):** Dedicated Contradictions Tab stories (10D.1-10D.2) are **DEFERRED to Phase 2**. Entity-based contradictions appear as finding type in Verification Tab. See [Phase-2-Backlog.md](Phase-2-Backlog.md).

---

#### Phase 2: Story 10D.1 & 10D.2 - Contradictions Tab (DEFERRED)

<details>
<summary>Click to expand Phase 2 Contradictions Tab Stories</summary>

##### Story 10D.1: Implement Contradictions Tab Entity-Grouped Display (PHASE 2)

As an **attorney**,
I want **contradictions grouped by entity with severity indicators**,
So that **I can review contradictions systematically**.

**Acceptance Criteria:**

**Given** I open the Contradictions tab
**When** content loads
**Then** contradictions are grouped by entity (canonical name as header, cards below)

**Given** a contradiction card is displayed
**When** I view it
**Then** it shows: type badge (semantic/factual/date_mismatch/amount_mismatch), severity indicator (high/medium/low), entity name, Statement 1 with source, Statement 2 with source, explanation

**Given** I click an evidence link
**When** the action activates
**Then** the PDF viewer opens to that location
**And** the statement is highlighted

---

##### Story 10D.2: Implement Contradictions Tab Inline Verification (PHASE 2)

As an **attorney**,
I want **to verify contradictions directly in the tab**,
So that **I can quickly work through the list**.

**Acceptance Criteria:**

**Given** a contradiction is displayed
**When** I hover over it
**Then** I see inline buttons: [✓ Verified] [✗ Reject] [🔄 Needs Review]

**Given** I click [✓ Verified]
**When** verification is recorded
**Then** the contradiction shows a "Verified" badge
**And** it moves to the verified section

**Given** I click [✗ Reject]
**When** the dialog opens
**Then** I enter a rejection reason
**And** the contradiction is marked as rejected (false positive)

**Given** I filter contradictions
**When** filters are applied
**Then** I can filter by: severity, entity, contradiction type, verification status

</details>

---

#### Story 10D.1: Implement Verification Tab Queue (Renumbered from 10D.3)

As an **attorney**,
I want **a unified queue of all findings needing verification**,
So that **I can efficiently verify across all categories**.

**Acceptance Criteria:**

**Given** I open the Verification tab
**When** the queue loads
**Then** I see a DataTable with all unverified findings
**And** columns: finding type, description, confidence (progress bar), source, actions

**Given** I select multiple rows
**When** I click a bulk action (Approve, Reject, Flag)
**Then** the action is applied to all selected findings
**And** the queue updates

**Given** I click action buttons on a row
**When** the action is selected
**Then** Approve (green check) marks as verified
**And** Reject (red X) prompts for reason
**And** Flag (yellow flag) prompts for note

---

#### Story 10D.4: Implement Verification Tab Statistics and Filtering

As an **attorney**,
I want **to see verification progress and filter the queue**,
So that **I can track my progress and focus on specific items**.

**Acceptance Criteria:**

**Given** I view the Verification tab
**When** statistics load
**Then** I see: total findings, verified count, pending count, flagged count
**And** a progress bar shows overall verification percentage

**Given** I use filters
**When** I select options
**Then** I can filter by: finding type, confidence tier (>90%, 70-90%, <70%), verification status
**And** the queue updates

**Given** I sort the table
**When** I click column headers
**Then** I can sort by any column
**And** default sort is by confidence ascending (lowest first)

---

#### Story 10D.5: Implement Documents Tab File List

As an **attorney**,
I want **to see all documents in my matter with status**,
So that **I can manage my document collection**.

**Acceptance Criteria:**

**Given** I open the Documents tab
**When** the content loads
**Then** I see a table with columns: document name, page count, date added, status (Indexed/Processing), type badge (case_file/act/annexure), action menu

**Given** documents are processing
**When** the list loads
**Then** processing documents show an inline progress bar
**And** message: "Processing NEW DOCUMENTS: X files, Y%"

**Given** I click "+ ADD FILES"
**When** the upload dialog opens
**Then** I can drag-drop or browse files to add to the matter
**And** message: "You can continue working while this processes"

---

#### Story 10D.6: Implement Documents Tab File Actions

As an **attorney**,
I want **to manage individual documents**,
So that **I can rename, reclassify, or remove documents**.

**Acceptance Criteria:**

**Given** I click the action menu on a document
**When** the menu opens
**Then** I see options: View, Rename, Set as Act, Delete

**Given** I select "View"
**When** the action executes
**Then** the PDF viewer opens to display the document

**Given** I select "Rename"
**When** the dialog opens
**Then** I can enter a new name
**And** the document is renamed

**Given** I select "Set as Act"
**When** the action executes
**Then** the document is moved to the acts folder
**And** is_reference_material is set to true
**And** citations can be verified against it

**Given** I select "Delete"
**When** the confirmation appears
**Then** I must confirm deletion
**And** the document is soft-deleted (30-day retention)

---

### Epic 11: Q&A Panel & PDF Viewer

#### Story 11.1: Implement Q&A Panel Header and Position

As an **attorney**,
I want **to control the Q&A panel position**,
So that **I can arrange my workspace optimally**.

**Acceptance Criteria:**

**Given** I am in the workspace
**When** the Q&A panel loads
**Then** the header shows: "ASK LDIP", minimize button, position selector dropdown

**Given** I click the position selector
**When** options appear
**Then** I can choose: Right (default), Bottom, Float, Hide

**Given** I select "Float"
**When** the panel updates
**Then** it becomes a draggable, resizable floating window
**And** it can overlap workspace content

**Given** I select "Hide"
**When** the panel hides
**Then** a small chat button appears in the corner
**And** clicking it expands the panel

---

#### Story 11.2: Implement Q&A Conversation History

As an **attorney**,
I want **to see my conversation history with LDIP**,
So that **I can reference previous questions and answers**.

**Acceptance Criteria:**

**Given** I have asked questions
**When** the panel shows history
**Then** user messages appear as bubbles on the right
**And** assistant messages appear as bubbles on the left

**Given** an assistant message contains sources
**When** it is displayed
**Then** source references appear as clickable links
**And** clicking a link opens the PDF viewer to that location

**Given** I scroll up in history
**When** I reach older messages
**Then** the sliding window of 20 messages is shown
**And** older messages can be loaded from Matter Memory if archived

---

#### Story 11.3: Implement Streaming Response with Engine Trace

As an **attorney**,
I want **to see responses stream in with processing details**,
So that **I know what's happening and how long it takes**.

**Acceptance Criteria:**

**Given** I ask a question
**When** processing begins
**Then** a typing indicator appears
**And** the response streams in token-by-token

**Given** the response completes
**When** engine trace is displayed
**Then** I see: which engines were invoked, execution time in ms, findings count
**And** this metadata appears below the response

**Given** multiple engines are used
**When** the trace shows
**Then** each engine's contribution is visible
**And** total processing time is shown

---

#### Story 11.4: Implement Suggested Questions and Input

As an **attorney**,
I want **suggested questions and easy input**,
So that **I can quickly start asking questions**.

**Acceptance Criteria:**

**Given** the conversation is empty
**When** the panel loads
**Then** suggested questions appear: "What is this case about?", "Who are the main parties?", "What are the key dates?"

**Given** I click a suggested question
**When** the action executes
**Then** the question is submitted as if I typed it
**And** the response is generated

**Given** the input field is displayed
**When** I type a message
**Then** I can press Enter or click the send button to submit
**And** the input clears after sending

---

#### Story 11.5: Implement PDF Viewer Split-View Mode

As an **attorney**,
I want **to view documents alongside my workspace**,
So that **I can reference sources while working**.

**Acceptance Criteria:**

**Given** I click a citation or source link
**When** the split view opens
**Then** the PDF viewer appears alongside the workspace content
**And** the workspace is still visible and interactive

**Given** the split view is open
**When** I view the document
**Then** I see the document header with: filename, page number, total pages, expand button, close button

**Given** I navigate in the split view
**When** I use prev/next or go to page
**Then** the document navigates accordingly
**And** the cited location remains visible initially

---

#### Story 11.6: Implement PDF Viewer Full Modal Mode

As an **attorney**,
I want **to expand the PDF viewer to full screen**,
So that **I can examine documents in detail**.

**Acceptance Criteria:**

**Given** the split view is open
**When** I click the expand button
**Then** the PDF viewer opens as a full modal
**And** the workspace is hidden behind it

**Given** the full modal is open
**When** I view the document
**Then** I have full navigation controls: prev/next, go to page input
**And** zoom controls: zoom in, zoom out, fit to width, fit to page

**Given** I click close or press Escape
**When** the modal closes
**Then** I return to the workspace
**And** the previous state is preserved

---

#### Story 11.7: Implement Bounding Box Overlays

As an **attorney**,
I want **relevant text highlighted in documents**,
So that **I can see exactly what was extracted or cited**.

**Acceptance Criteria:**

**Given** I view a citation in the PDF
**When** the page loads
**Then** bounding box overlays highlight the citation text
**And** overlays are semi-transparent

**Given** different highlight purposes
**When** overlays are rendered
**Then** colors distinguish: yellow for citations, blue for entity mentions, red for contradictions

**Given** I click on a cross-reference
**When** the link activates
**Then** the viewer jumps to the referenced document and page
**And** the referenced text is highlighted

**Given** side-by-side view is active (for citation verification)
**When** both documents are shown
**Then** the source location is highlighted on the left
**And** the Act location is highlighted on the right

---

### Epic 12: Export Builder

#### Story 12.1: Implement Export Builder Modal

As an **attorney**,
I want **a modal to configure my export**,
So that **I can choose what to include in my document**.

**Acceptance Criteria:**

**Given** I click Export from the workspace
**When** the modal opens
**Then** I see section selection with checkboxes: Executive Summary, Timeline, Entities, Citations, Contradictions, Key Findings

**Given** sections are listed
**When** I view them
**Then** I can check/uncheck each to include or exclude
**And** sections show a preview of their content size

**Given** I want to reorder sections
**When** I drag a section
**Then** it moves to the new position
**And** the preview updates to reflect the order

---

#### Story 12.2: Implement Export Inline Editing and Preview

As an **attorney**,
I want **to edit content before export and preview the result**,
So that **I can customize the final document**.

**Acceptance Criteria:**

**Given** a section is selected
**When** I click "Edit"
**Then** the section content becomes editable inline
**And** I can modify text, remove items, or add notes

**Given** I make edits
**When** the preview updates
**Then** the preview panel shows the document as it will appear
**And** changes are reflected in real-time

**Given** the preview is displayed
**When** I scroll through it
**Then** I see all selected sections in order
**And** formatting matches the export format

---

#### Story 12.3: Implement Export Verification Check and Format Generation

As an **attorney**,
I want **exports to require verified findings and support multiple formats**,
So that **I only export accurate content in the format I need**.

**Acceptance Criteria:**

**Given** I click "Export"
**When** verification check runs
**Then** findings with confidence < 70% must be verified before export
**And** unverified findings are highlighted with a warning

**Given** unverified findings exist
**When** I try to export
**Then** I see a warning: "X findings require verification before export"
**And** links take me to the Verification tab

**Given** all required verifications are complete
**When** I select a format and click "Generate"
**Then** the export is created in the selected format (PDF, Word, PowerPoint)
**And** the file is downloaded or offered for download

**Given** the export is generated
**When** I view the document
**Then** verification status is included (showing which findings were verified and by whom)
**And** the document is court-ready with professional formatting

---

#### Story 12.4: Implement Partner Executive Summary Export

As a **senior partner**,
I want **a one-click executive summary export**,
So that **I can quickly get a decision-ready overview without configuring sections**.

**Acceptance Criteria:**

**Given** I click "Export" from the workspace
**When** I see export options
**Then** I see a "Quick Export: Executive Summary" button alongside the full Export Builder

**Given** I click "Quick Export: Executive Summary"
**When** the export generates
**Then** it includes only: Case Overview (2-3 paragraphs), Key Parties, Critical Dates (max 10), Verified Issues (contradictions/citation problems), Recommended Actions
**And** the format is a single-page PDF optimized for quick review

**Given** the executive summary is generated
**When** I view the document
**Then** all included findings show "Verified" status
**And** unverified findings are excluded with a note: "X additional findings pending verification"
**And** the document fits on 1-2 pages maximum

**Given** I want more detail after reviewing the summary
**When** I see the summary footer
**Then** it includes "Generated from full analysis - open LDIP for complete details"
**And** a link to the matter workspace is embedded

---

### Epic 13: Observability & Production Hardening

#### Story 13.1: Implement Axiom Logging Integration

As a **developer**,
I want **structured logging sent to Axiom**,
So that **I can monitor and debug production issues**.

**Acceptance Criteria:**

**Given** the application is running
**When** log events occur
**Then** structured JSON logs are sent to Axiom
**And** logs include: timestamp, level, message, correlation_id, user_id, matter_id

**Given** an API request is processed
**When** logging occurs
**Then** a correlation_id is assigned
**And** all related logs share this ID for tracing

**Given** logs are in Axiom
**When** I query them
**Then** hot storage provides 30 days of data
**And** cold storage retains 1 year

---

#### Story 13.2: Implement Circuit Breakers

As a **developer**,
I want **circuit breakers on external API calls**,
So that **failures don't cascade and the system degrades gracefully**.

**Acceptance Criteria:**

**Given** an LLM API call is made
**When** tenacity wraps the call
**Then** it retries up to 3 times with exponential backoff
**And** times out after 30 seconds

**Given** an API consistently fails
**When** the circuit opens
**Then** subsequent calls fail fast without attempting the API
**And** the circuit resets after a cooldown period

**Given** a circuit is open
**When** the system needs that API
**Then** graceful degradation provides a fallback response
**And** users see a warning that full functionality is limited

---

#### Story 13.3: Implement Rate Limiting

As a **developer**,
I want **rate limiting on API endpoints**,
So that **no user can overload the system**.

**Acceptance Criteria:**

**Given** rate limiting is configured
**When** a user makes API calls
**Then** slowapi middleware tracks calls per user
**And** limits are 100 requests per minute per user

**Given** a user exceeds the limit
**When** the next request is made
**Then** a 429 Too Many Requests response is returned
**And** the response includes a Retry-After header

**Given** Vercel edge handles the frontend
**When** DDoS protection is needed
**Then** automatic edge limiting applies
**And** malicious traffic is blocked

---

#### Story 13.4: Implement Graceful Degradation and Error States

As an **attorney**,
I want **clear error messages when things go wrong**,
So that **I understand what happened and what to do**.

**Acceptance Criteria:**

**Given** an API call fails
**When** the error is handled
**Then** the UI shows a clear error message
**And** suggests a retry or alternative action

**Given** a long operation is running
**When** loading states are shown
**Then** clear progress indicators appear
**And** users understand the wait

**Given** an external service is down
**When** degraded mode activates
**Then** affected features show a warning
**And** unaffected features continue to work

**Given** processing fails for a document
**When** the error occurs
**Then** the document shows an error state
**And** users can retry or skip the document

---

#### Story 13.5: Configure Production Deployment

As a **developer**,
I want **production infrastructure configured**,
So that **the application runs reliably at scale**.

**Acceptance Criteria:**

**Given** the frontend is deployed
**When** Vercel is configured
**Then** automatic deployments occur on push to main
**And** preview deployments occur on PRs

**Given** the backend is deployed
**When** Railway is configured
**Then** the FastAPI server runs with proper scaling
**And** environment variables are securely managed

**Given** Supabase is configured
**When** the database is ready
**Then** PostgreSQL with pgvector is available
**And** RLS policies are enforced

**Given** Upstash Redis is configured
**When** the cache is ready
**Then** session memory and query cache function correctly
**And** proper key prefixes are used

---

## Phase 2 Candidates

*Features considered during MVP planning but deferred pending user validation.*

### Quick Analysis Mode

**Problem:** Full analysis including citation verification may take 30-60 minutes. Users may abandon before seeing value.

**Proposed Solution:** Allow immediate workspace access with Timeline, Entities, and Summary while citation verification runs in background. Citations tab shows "unverified" status until Acts are uploaded.

**Validation Metric:** Measure % of users who abandon at Act Discovery step. If >30% abandon, prioritize Quick Analysis Mode for Phase 2.

**Stories if validated:**
- Quick Analysis Mode - workspace access before full verification
- Q&A guardrails for unverified citation responses
- Seamless upgrade path from quick to full analysis

### Documentation Gap Engine

**Deferred per Decision-Log.md** - Originally in PRD but removed from MVP scope to focus on core citation, timeline, and contradiction engines.

### Process Chain Deviation Engine

**Deferred per Decision-Log.md** - Originally in PRD but removed from MVP scope to focus on core citation, timeline, and contradiction engines.

### Mobile Q&A Interface

**Problem:** Attorneys are in court and need quick access from mobile devices.

**Proposed Solution:** Mobile-first query interface for Q&A panel only - minimal UI for asking questions and viewing responses with source links.

**Validation Metric:** Track user feedback requests for mobile access during beta.

### Guided Onboarding Wizard

**Problem:** First-time users face an empty dashboard with just "Create Matter" - no guidance on what to expect.

**Proposed Solution:** First-matter wizard with sample case pre-loaded, step-by-step walkthrough of upload → processing → analysis flow.

**Validation Metric:** Measure time-to-first-insight for users with vs. without onboarding. If delta >50%, prioritize for Phase 2.

### Team/Organization Accounts

**Problem:** Law firms want shared access - junior associates prepare, partners review. Individual accounts create friction.

**Proposed Solution:** Organization-level accounts with role-based access (Preparer, Reviewer, Admin). Shared matters, activity logs, team billing.

**Validation Metric:** Track support requests for "sharing" or "team access" during beta.

