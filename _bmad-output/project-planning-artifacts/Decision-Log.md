# Decision Log
# LDIP - Legal Document Intelligence Platform
**Date Range:** 2025-12-30 to 2026-01-03
**Process:** Gap Resolution Research

---

## Document Purpose

This Decision Log documents all major architectural and scope decisions made during the gap resolution process. Each decision includes:
- The problem being solved
- Alternatives considered
- Final decision and rationale
- Trade-offs accepted
- Stakeholder approval

**Primary Research Document:** [fizzy-conjuring-zephyr.md](C:\Users\Jyotsna\.claude\plans\fizzy-conjuring-zephyr.md) (3482 lines)

---

## Decision Index

1. [Architecture Decision: Engines vs Features](#decision-1-architecture-engines-vs-features)
2. [LLM Strategy: Hybrid Gemini + GPT](#decision-2-llm-strategy-hybrid-gemini-gpt)
3. [Memory Architecture: 3-Layer System](#decision-3-memory-architecture-3-layer-system)
4. [Data Strategy: MIG + RAG Hybrid](#decision-4-data-strategy-mig-rag-hybrid)
5. [MVP Scope: 5 Engines + 3 Safety Features](#decision-5-mvp-scope-5-engines-3-safety)
6. [Process Templates: Deferred to Phase 2](#decision-6-process-templates-deferred)
7. [Advanced Engines: Deferred to Phase 2](#decision-7-advanced-engines-deferred)
8. [Database Strategy: PostgreSQL for Everything](#decision-8-database-postgresql)
9. [OCR Strategy: Google Document AI + Gemini Validation](#decision-9-ocr-strategy)
10. [MVP Scope Refinement: 3 Core Engines Only](#decision-10-mvp-scope-refinement)
11. [Epic 10 Split: Workspace Tabs into Sub-Epics](#decision-11-epic-10-split)
12. [Quick Analysis Mode: Deferred to Phase 2](#decision-12-quick-analysis-mode-deferred)

---

## Decision 1: Architecture - Engines vs Features

### Problem Statement
Implementation Readiness Report identified conflicting guidance:
- Deep Research docs: 8 specialized engines with I/O contracts
- MVP spec: 10 user-facing features with monolithic RAG + MIG
- Question: Are they the same thing with different names, or fundamentally different architectures?

### Alternatives Considered

**Option A: Features Architecture (8.25 months)**
- Monolithic RAG + MIG pipeline
- Features call shared infrastructure
- No orchestrator
- Simpler, faster to build
- Phase 2 refactoring required for modularity

**Option B: Engine Architecture (13-14 months)**
- Modular engines with strict I/O contracts
- Orchestrator selects which engines to invoke
- Forensic audit trail (engine execution logs)
- Deterministic outputs (same input → same output)
- No Phase 2 refactoring needed

**Option C: Hybrid (Features now, refactor later)**
- Build features in 8 months
- Add safeguards for future engine extraction
- Refactor to engines in Phase 2 if pain points emerge
- Lower upfront cost, potential technical debt

### Final Decision: ✅ Option B - Full Engine Architecture (13-14 months)

**Rationale:**
- **User directive:** "I think we should develop engines. Let's go strong from the start"
- **Long-term vision:** Engines provide better quality, modularity, court-defensibility
- **Avoid technical debt:** Build right architecture from Day 1, not quick shortcuts
- **Strong foundation:** Investment in upfront design pays dividends in maintenance

### Trade-offs Accepted
- ❌ Timeline: 15-16 months (vs 8.25 months for features)
- ❌ Complexity: Need orchestrator, engine registry, I/O contract validation
- ❌ Higher upfront cost: More development time

### Benefits Gained
- ✅ Modularity: Update Citation Engine without touching Timeline Engine
- ✅ Testability: Each engine unit-testable in isolation
- ✅ Forensic Audit: Granular logging (which engines ran, inputs, outputs, confidence)
- ✅ Scalability: Add new engines (Phase 2) without refactoring core

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved - "go strong from the start"
- **Date:** 2025-12-30

---

## Decision 2: LLM Strategy - Hybrid Gemini + GPT

### Problem Statement
MVP spec specified GPT-4 for all tasks ($75-110 per matter). Research identified Gemini 3 Flash as 3.5x-4.5x cheaper. Question: Which LLM to use?

### Alternatives Considered

**Option A: GPT-4 Only**
- Use GPT-4 for ingestion + reasoning
- Pros: Single vendor, consistent quality, <1% hallucination
- Cons: $75-110 per matter, 128K context window (requires chunking for large cases)

**Option B: Gemini Only**
- Use Gemini 3 Flash for all tasks
- Pros: $12-14 per matter, 1M context window, native multimodal
- Cons: ~3-5% hallucination, Jan 2025 knowledge cutoff (pre-BNS jurisprudence), code-mixing in Indic languages

**Option C: Hybrid (Gemini Ingestion + GPT Reasoning)**
- Layer 1: Gemini 3 Flash for bulk processing (OCR, entity extraction, timeline)
- Layer 2: GPT-4/GPT-5.2 for high-stakes reasoning (contradiction detection, summary, Q&A)
- Pros: Best of both worlds, 5-7x cost reduction vs GPT-only
- Cons: Two vendors, integration complexity

### Final Decision: ✅ Option C - Hybrid Architecture

**Rationale:**
- **Cost:** $13-14 per matter (vs $75-110 GPT-only) = 5-7x savings
- **Gemini strengths:** 1M context window (entire case file fits), 3.5x-4.5x cheaper, native multimodal (scanned PDFs, CCTV, audio)
- **GPT strengths:** <1% hallucination (Thinking mode), Aug 2025 knowledge cutoff (BNS jurisprudence critical for Indian legal)
- **Use right tool for right layer:** Gemini = "The Registry" (bulk processing), GPT = "The Jurist" (legal reasoning)

### Architecture Flow
```
Document Upload (2000 pages)
  ↓
GEMINI 3 FLASH: Ingestion Layer
  - OCR entire case file (1M context)
  - Extract entities → MIG population
  - Extract events → Timeline fragments
  - Extract citations → Pre-link to Acts
  - Cost: $1.00 for 2000 pages
  ↓
MIG Database Populated
  ↓
User Query: "Show contradictions in custodian statements"
  ↓
MIG Fast Path: Resolve custodian → entity_id
  ↓
RAG Search: Retrieve top 3 chunks (BM25 + Vector + Rerank)
  ↓
Context Pack Assembly:
  - Top 3 chunks (from Gemini ingestion)
  - MIG entity mappings
  - Pre-linked relationships
  - Timeline events
  ↓
GPT-4: Reasoning Layer
  - Deep semantic analysis
  - Contradiction detection
  - Generate response with citations
  - Cost: $0.05 per query
  ↓
Response to user
```

### Trade-offs Accepted
- ❌ Two vendors (Google + OpenAI) vs one
- ❌ Integration complexity (layered architecture)

### Benefits Gained
- ✅ 5-7x cost reduction ($13-14 vs $75-110)
- ✅ Entire case file fits in Gemini 1M context (no chunking for ingestion)
- ✅ GPT-5.2 Aug 2025 knowledge cutoff (critical BNS jurisprudence)
- ✅ Multimodal: Native PDF, audio, video processing (Gemini)
- ✅ <1% hallucination for final outputs (GPT Thinking mode)

### GPT-4 vs GPT-5.2 Clarification
**Decision:** Start with GPT-4, upgrade to GPT-5.2 when available/cost-effective

**Rationale:**
- GPT-5.2 advantages: Aug 2025 knowledge cutoff (BNS/BNSS jurisprudence), <1% hallucination with Thinking mode
- Flexibility: Implementation can start with GPT-4, upgrade later without architecture changes
- Research compared GPT-5.2 to show future direction

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved hybrid strategy
- **Date:** 2025-12-30

---

## Decision 3: Memory Architecture - 3-Layer System

### Problem Statement
User asked: "Somewhere I have also talked about memory. How are we handling that?"

Research found:
- ✅ MVP had basic query caching (Redis, 1-hour TTL)
- ❌ MVP did NOT have conversation context memory (multi-turn conversations)
- ❌ MVP did NOT have Matter Memory Files (query history, timeline cache)
- ? Status unclear: Should memory be in MVP or deferred to Phase 2?

### Alternatives Considered

**Option A: Stateless Engines (Simpler, 13-14 months)**
- Each engine execution is independent
- No conversation memory
- Query caching only (1-hour Redis TTL)
- Each query = fresh MIG lookup + RAG retrieval
- Pros: Simpler, faster to build
- Cons: No multi-turn conversations, no query history

**Option B: Stateful Engines with Matter Memory (Advanced, 14-16 months)**
- Engines maintain matter-level memory
- Conversation context across queries
- Persistent Matter Memory Files (query history, timeline cache, entity graph)
- Multi-turn conversation support
- Pros: Better UX, forensic audit trail, faster re-queries
- Cons: +6-8 weeks development, database storage overhead

### Final Decision: ✅ Option B - Stateful Engines with 3-Layer Memory (15-16 months)

**Rationale:**
- **Aligns with engine vision:** Engines can maintain state between executions
- **Better UX:** Multi-turn conversations feel natural ("Who is custodian?" → "When did they file affidavit?")
- **Forensic audit trail:** Query history = court-defensible usage log (legal requirement)
- **Performance:** Cached MIG + timeline = faster subsequent queries (40-60% cost reduction)
- **Collaboration:** Multiple attorneys working on same matter share memory
- **Pattern detection:** Memory enables learning across queries (Phase 2+ feature prep)

### 3-Layer Memory System Design

**Layer 1: Session Memory (Ephemeral)**
- Redis storage with 4-hour TTL
- Current conversation within a matter (sliding window: last 10-20 messages)
- Enables multi-turn: "Who is custodian?" → (answer) → "When did they file?" (system remembers "they" = custodian)
- Entity pronoun resolution
- Cleared on logout or session timeout

**Layer 2: Matter Memory (Persistent)**
- PostgreSQL JSONB storage per matter
- File structure:
  - `/matter-{id}/query_history.jsonb` - Append-only log (forensic audit)
  - `/matter-{id}/timeline_cache.jsonb` - Pre-built timeline (persistent)
  - `/matter-{id}/entity_graph.jsonb` - MIG relationships (cached)
  - `/matter-{id}/key_findings.jsonb` - Attorney-verified facts
  - `/matter-{id}/research_notes.jsonb` - Attorney annotations
- Soft-delete only (mark as archived, not purge)
- RLS policy: Only attorneys on the matter can access

**Layer 3: Query Cache (Optimization)**
- Redis cache with 1-hour TTL
- Key: `cache:query:{matter_id}:{query_hash}`
- Identical queries return in ~10ms (vs 3-5 seconds)
- Cleared on document upload (matter data changes)

### Trade-offs Accepted
- ❌ Timeline: +6-8 weeks (14-16 months total)
- ❌ Storage overhead: PostgreSQL JSONB per matter
- ❌ Complexity: Three memory layers vs simple caching

### Benefits Gained
- ✅ Multi-turn conversations (natural lawyer workflow)
- ✅ Forensic audit trail (query history for court)
- ✅ Collaboration (shared memory across attorneys)
- ✅ Performance: 40-60% fewer LLM calls (cached entities/timeline)
- ✅ Pattern detection prep (Phase 2+ features)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved 3-layer memory in MVP
- **Date:** 2025-12-31

---

## Decision 4: Data Strategy - MIG + RAG Hybrid

### Problem Statement
Conflicting guidance:
- Deep Research: "Build MIG (Matter Identity Graph) + Pre-linking from Day 1"
- Some interpretations: "Gemini 1M context = no chunking needed, skip RAG"
- MVP spec: "Simple RAG for MVP, MIG in Phase 2"
- Question: What data architecture should MVP have?

### Alternatives Considered

**Option A: RAG Only (4 months)**
- Parent-child chunking + BM25 + Vector + Rerank
- No MIG, no entity resolution
- Pros: Simpler, faster to build
- Cons: Can't detect contradictions across name variants ("Nirav Jobalia" ≠ "N.D. Jobalia")

**Option B: MIG Only (4 months)**
- Pre-linking (entity extraction, relationship linking)
- No RAG, no semantic search
- Pros: Fast entity lookups, deterministic
- Cons: Struggles with novel semantic queries ("Why did custodian delay?")

**Option C: MIG + RAG Hybrid (6 months)**
- Build both from Day 1 (not sequential phases)
- MIG provides fast path + entity resolution
- RAG provides semantic understanding
- Hybrid orchestration: check MIG first, fallback to RAG
- Pros: Best of both worlds, enables killer features
- Cons: +2 months development

### Final Decision: ✅ Option C - MIG + RAG Hybrid (6 months)

**Rationale:**
- **Entity resolution critical:** Contradiction detection requires linking name variants (MIG)
- **Semantic understanding needed:** Complex queries need RAG ("Why did X happen?")
- **User wants MIG from start:** "go strong from the start"
- **Killer features enabled:**
  - Speed: Visual citations (RAG bounding boxes)
  - Comprehension: Timeline (MIG events) + Executive Summary (RAG + MIG)
  - Contradiction Catching: MIG entity resolution + GPT-4 semantic comparison

### How MIG + RAG Work Together

**Ingestion Pipeline:**
```
Document Upload
  ↓
Google Document AI OCR
  ↓
STEP 1: PRE-LINKING (MIG Population - Deterministic)
  ├─ Entity Extraction → identity_nodes table
  ├─ Alias Linking → identity_edges table
  ├─ Event Extraction → events table
  ├─ Relationship Linking → pre_linked_relationships table
  └─ Citation Extraction → citations table
  ↓
STEP 2: RAG PREPARATION
  ├─ Parent-Child Chunking (1500-2000 parent, 400-700 child)
  ├─ Embedding Generation (OpenAI ada-002)
  └─ Full-Text Indexing (PostgreSQL tsvector)
```

**Query Pipeline:**
```
User Query: "Where is property attachment order?"
  ↓
STEP 1: Query Understanding
  - Extract intent, entities, constraints
  ↓
STEP 2A: MIG Entity Resolution (FAST PATH)
  - Resolve "property" → entity_id
  - Check pre_linked_relationships for attachment orders
  - If found → Use pre-linked doc/page references
  ↓
STEP 2B: Hybrid RAG Search (if MIG insufficient)
  ├─ BM25 Search (keywords)
  ├─ Vector Search (semantic)
  └─ Merge via RRF → Top 20
  ↓
STEP 3: Reranking (Cohere Rerank v3)
  - Top 20 → Top 3 most relevant
  ↓
STEP 4: Context Enrichment with MIG
  - Resolve entity mentions to canonical entity_ids
  - Add pre-linked relationships
  - Include timeline context
  ↓
STEP 5: LLM Generation (GPT-4)
  - System prompt enforces canonical entity names
  - Cite bounding boxes
  - Flag contradictions using entity_id grouping
```

### Trade-offs Accepted
- ❌ Timeline: 6 months (vs 4 months for RAG-only or MIG-only)
- ❌ Complexity: Hybrid orchestration

### Benefits Gained
- ✅ Entity resolution: "Nirav Jobalia" = "N.D. Jobalia" via MIG
- ✅ Contradiction detection: Group statements by canonical entity_id
- ✅ Timeline construction: Pre-linked events with entity associations
- ✅ Fast queries: Pre-linked facts answer common queries in <1 second
- ✅ Semantic understanding: RAG provides context for novel patterns
- ✅ Evolution path: Can add bounded adaptive computation in Phase 2

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved MIG + RAG hybrid from Day 1
- **Date:** 2025-12-30

---

## Decision 5: MVP Scope - 5 Engines + 3 Safety

### Problem Statement
Deep Research specified 8 engines. Question: Which engines in MVP vs Phase 2?

### Final Decision: ✅ 5 Core Engines + 3 Safety Features in MVP

**5 Core Engines (In Scope):**
1. **Citation Verification Engine** - Verify Act references, flag errors
2. **Timeline Construction Engine** - Extract events, build chronology
3. **Consistency & Contradiction Engine** - Detect conflicting statements
4. **Documentation Gap Engine** - Flag missing documents (basic version, needs templates)
5. **Process Chain Integrity Engine** - Detect timeline deviations (basic version, needs templates)

**3 Safety Features (In Scope):**
1. **Query Guardrails** (2 weeks) - Block dangerous legal questions
2. **Language Policing** (1 week) - Sanitize legal conclusions
3. **Attorney Verification Workflow** (3 weeks) - Court-defensible audit trail

**3 Advanced Engines (Deferred to Phase 2):**
- ❌ Engine 6: Entity Authenticity (forgery detection via signature/seal analysis)
- ❌ Engine 7: Admissions & Non-Denial (detect strategic silence in pleadings)
- ❌ Engine 8: Pleading Mismatch (cross-check claims vs supporting evidence)

### Rationale for Deferrals

**Engine 4 & 5 (Gap, Process) - Basic version in MVP:**
- User doesn't have manual process templates ready
- MVP ships with hardcoded rules for 2-3 common processes (SARFAESI, DRT)
- Phase 2: Full template-based detection (after user creates templates from real matter data)

**Engine 6 (Authenticity) - Deferred:**
- Extreme complexity: Requires computer vision models (not just LLM)
- Timeline impact: +4-6 weeks
- Liability risk: False "forgery detected" claim could derail legitimate case
- Domain expertise: Needs forensic document analysis knowledge

**Engine 7 (Admissions) - Deferred:**
- Medium complexity, high legal sensitivity
- Requires pleading document parsing (different format from evidence docs)
- False positives: "You didn't deny X" when they denied indirectly
- Timeline impact: +2-3 weeks
- Attorneys very cautious about AI making adversarial claims

**Engine 8 (Pleading Mismatch) - Deferred:**
- Medium complexity
- Overlaps with Contradiction Engine
- Can add in Phase 2 if attorneys request

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved scope (5 engines + 3 safety, defer 3 advanced)
- **Date:** 2025-12-31

---

## Decision 6: Process Templates - Deferred

### Problem Statement
Engines 4 (Documentation Gap) and 5 (Process Chain Integrity) require process templates. User doesn't have manual templates ready. Question: Build hardcoded templates now or defer?

### Alternatives Considered

**Option A: Accept Dependency - Defer to Phase 2** ✅
- Ship MVP with basic hardcoded rules for 2-3 processes
- Attorney verification workflow provides manual gap-checking
- Phase 2: Build data-driven templates from actual matter data
- Pros: No guessing, better template quality, faster MVP
- Cons: No auto-detection of "9 months vs typical 2-3 months" deviations

**Option B: Build Hardcoded Templates for 2-3 Processes**
- Research SARFAESI, DRT, IBC processes now
- Hardcode templates (required docs, typical timelines)
- Pros: Partial automation, pitch alignment ("process integrity checking")
- Cons: +4 weeks timeline, hardcoded breaks when laws change, user can't validate accuracy

### Final Decision: ✅ Option A - Defer Full Templates to Phase 2

**Rationale:**
- **Template quality requires real data:** Can't validate template accuracy without 10-20 matters
- **Better approach:** Ship MVP → Collect matters → Analyze actual timelines → Build data-driven templates
- **Mitigation:** Attorney Verification Workflow UI asks: "Are any required documents missing?" (manual checklist)
- **Basic version in MVP:** Hardcoded rules for 2-3 top processes (SARFAESI notice period, RBI approval requirement)

### MVP Scope for Engines 4 & 5
- Basic hardcoded checks for SARFAESI, DRT (top 2 processes)
- Examples:
  - Documentation Gap: "SARFAESI requires RBI approval letter (check uploaded docs)"
  - Process Chain: "Notice period: 60 days required (actual: 9 months - flag for review)"
- Full template engine deferred to Phase 2

### Phase 2 Trigger
- After 6 months of MVP usage
- User (Juhi) creates manual templates from 10-20 real matters
- Templates validated against actual data (not guesses)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved deferral, will create templates in Phase 2
- **Date:** 2025-12-31

---

## Decision 7: Advanced Engines - Deferred

### Problem Statement
Engines 6, 7, 8 are advanced features. Question: Any critical for MVP?

### Final Decision: ✅ Defer All Three to Phase 2

**Rationale:**
- **Focus on core value:** Speed, Comprehension, Contradiction are killer features
- **Faster MVP:** Saves 6-9 weeks (2-3 weeks per engine)
- **Lower risk:** Advanced features have complex legal nuances (high error risk)
- **Attorney workflow alignment:** Lawyers already manually check authenticity, admissions, mismatches (no broken workflow)

**Senior Dev Assessment:**
- Engine 7 (Admissions): Medium complexity, high legal sensitivity → Phase 2
- Engine 6 (Authenticity): High complexity, extreme liability risk → Phase 2+ or never
- Engine 8 (Pleading Mismatch): Medium complexity, overlaps with Contradiction → Phase 2

**Mitigation:**
- Attorney verification UI includes manual checklist: "Have you checked for strategic non-denials?"

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved deferral
- **Date:** 2025-12-31

---

## Decision 8: Database - PostgreSQL

### Problem Statement
Deep Research docs mentioned graph databases (Neo4j, ArangoDB) for MIG. Question: PostgreSQL vs Graph DB?

### Alternatives Considered

**Option A: PostgreSQL for Everything** ✅
- MIG + RAG + Core tables all in PostgreSQL
- Pros: Simplicity (one database), RLS built-in, pgvector for RAG, user preference (Supabase)
- Cons: Less optimized for complex graph traversals

**Option B: PostgreSQL + Graph DB (Neo4j/ArangoDB)**
- PostgreSQL for RAG + Core tables
- Graph DB for MIG
- Pros: Optimized graph queries
- Cons: Two databases to manage, RLS requires custom implementation in graph DB, complexity

### Final Decision: ✅ Option A - PostgreSQL for Everything

**Rationale:**
- **Simplicity:** One database, not multiple systems
- **RLS built-in:** Matter isolation via Row-Level Security (legal requirement)
- **pgvector:** Vector search without separate vector DB
- **User preference:** Supabase chosen by Juhi
- **MIG queries are simple:** Lookups by entity_id, not complex graph traversals (Cypher not needed)

### Trade-offs Accepted
- ❌ Slightly less optimized graph queries (vs Neo4j)
- ✅ Acceptable: MIG queries are straightforward (get aliases, get relationships)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved PostgreSQL-only (Supabase)
- **Date:** 2025-12-29

---

## Decision 9: OCR Strategy

### Problem Statement
Confusion: Does Gemini do OCR, or does Google Document AI do OCR?

### Clarification: ✅ Google Document AI does OCR, Gemini validates output

**Final Decision:** Google Document AI + Gemini Validation + Human Review Queue

**Pipeline:**
```
Scanned PDF
  ↓
Google Document AI OCR (PRIMARY OCR)
  ↓ Extract text + bounding boxes + confidence scores
  ↓
Gemini Quality Check (VALIDATION - NOT OCR)
  ├─ Flag low-confidence words (<85%)
  ├─ Contextual validation (is "20I7" likely "2017"?)
  ├─ Pattern-based auto-correction
  └─ Queue critical errors for human review
  ↓
MIG Pre-linking (Gemini)
  ↓
RAG Chunking
```

**Rationale:**
- Google Document AI: Industry-leading OCR with bounding boxes
- Gemini validation: Contextual correction (dates, amounts, names)
- Human review: Safety net for critical documents
- Cost: $9.50 per 2000-page matter (Google Document AI)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved OCR strategy
- **Date:** 2025-12-30

---

## Summary: All Decisions Locked

| Decision | Status | Timeline Impact | Cost Impact |
|----------|--------|-----------------|-------------|
| 1. Engines vs Features | ✅ Engines | +7-8 months | Higher upfront, lower long-term |
| 2. LLM Strategy | ✅ Hybrid Gemini + GPT | Neutral | 5-7x cost reduction |
| 3. Memory Architecture | ✅ 3-Layer Memory | +6-8 weeks | Storage overhead, 40% cost savings (fewer LLM calls) |
| 4. MIG + RAG Hybrid | ✅ Both from Day 1 | +2 months | Neutral |
| 5. MVP Scope | ✅ 5 engines + 3 safety | Baseline | Baseline |
| 6. Process Templates | ✅ Deferred | Saves 4 weeks | Neutral |
| 7. Advanced Engines | ✅ Deferred | Saves 6-9 weeks | Neutral |
| 8. Database | ✅ PostgreSQL only | Neutral | Neutral |
| 9. OCR Strategy | ✅ Google Doc AI + Gemini | Neutral | $9.50 per matter |

**Total Timeline:** 15-16 months
**Total Cost per Matter:** $13-14

---

## Decision 10: MVP Scope Refinement - 3 Core Engines Only

### Problem Statement
During epic/story creation, critical review identified that Decision 5 listed 5 engines in MVP scope, but Documentation Gap Engine and Process Chain Integrity Engine both depend on process templates that don't exist yet (per Decision 6).

### Final Decision: ✅ Reduce MVP to 3 Core Engines

**3 Core Engines (In MVP Scope):**
1. **Citation Verification Engine** - Verify Act references, flag errors
2. **Timeline Construction Engine** - Extract events, build chronology
3. **Consistency & Contradiction Engine** - Detect conflicting statements

**Deferred to Phase 2 (with Process Templates):**
- ❌ Documentation Gap Engine - Requires process templates
- ❌ Process Chain Integrity Engine - Requires process templates

### Rationale
- Decision 6 already deferred process templates to Phase 2
- Engines 4 & 5 cannot function without templates
- Orphan NFRs (NFR16, NFR17) referencing these engines were removed from requirements
- Cleaner MVP scope with 3 fully functional engines

### Impact
- Removed NFR16 (Documentation gap detection accuracy)
- Removed NFR17 (Process deviation detection)
- FR Coverage Map unchanged (these engines had no FR mappings in MVP)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved during epic review
- **Date:** 2026-01-03

---

## Decision 11: Epic 10 Split - Workspace Tabs into Sub-Epics

### Problem Statement
Pre-mortem analysis identified Epic 10 (Matter Workspace Tabs) as too large - 18 stories vs. average of 5-6 stories per epic. This creates sprint planning challenges and makes progress tracking difficult.

### Final Decision: ✅ Split Epic 10 into 4 Sub-Epics

| Sub-Epic | Stories | Focus |
|----------|---------|-------|
| Epic 10A | 3 stories | Workspace Shell & Navigation |
| Epic 10B | 5 stories | Summary & Timeline Tabs |
| Epic 10C | 4 stories | Entities & Citations Tabs |
| Epic 10D | 6 stories | Contradictions, Verification & Documents Tabs |

### Rationale
- Enables parallel development by different team members
- Each sub-epic is independently deployable
- Better sprint velocity tracking
- Stories within each sub-epic are cohesive

### Impact
- FR Coverage Map updated to reference 10A/10B/10C/10D
- Story numbering changed from 10.1-10.18 to 10A.1-10D.6
- Total story count unchanged (18 stories)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved during pre-mortem analysis
- **Date:** 2026-01-03

---

## Decision 12: Quick Analysis Mode - Deferred to Phase 2

### Problem Statement
Pre-mortem analysis identified risk: Full analysis including citation verification may take 30-60 minutes. Users may abandon before seeing value.

### Alternatives Considered

**Option A: Quick Analysis Mode (Full Implementation)**
- Allow immediate workspace access with Timeline, Entities, Summary
- Citation verification runs in background
- 3 new stories, touches 5 epics

**Option B: Simpler Mitigation (Chosen)**
- Add acceptance criterion to Story 2.12 allowing workspace access during processing
- Document Quick Analysis Mode as Phase 2 candidate
- Validate with real user data before committing to full implementation

### Final Decision: ✅ Option B - Simpler Mitigation + Phase 2 Documentation

**Added to Story 2.12:**
- "Given documents are still processing, When I click 'Enter Workspace', Then I can access the workspace with partially available data"

**Documented in Phase 2 Candidates:**
- Quick Analysis Mode with validation metric: "If >30% users abandon at Act Discovery, prioritize for Phase 2"

### Rationale
- PM approach: Validate problem exists before building solution
- Lower implementation cost for MVP
- Real user data will inform whether full Quick Analysis Mode is needed
- 80/20 solution: Workspace access during processing addresses most of the concern

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved simpler approach
- **Date:** 2026-01-03

---

## Decision 13: Epic 2 Split - Document Ingestion into Sub-Epics

### Problem Statement
Implementation Readiness Assessment identified that Epic 2 (Document Ingestion & Processing Pipeline) contains 12 stories, which is larger than the typical 4-6 stories per epic. This creates sprint planning challenges similar to Epic 10.

### Final Decision: ✅ Split Epic 2 into 3 Sub-Epics

| Sub-Epic | Stories | Focus |
|----------|---------|-------|
| Epic 2A | 3 stories | Document Upload & Storage |
| Epic 2B | 7 stories | OCR & RAG Pipeline |
| Epic 2C | 3 stories | Entity Extraction & MIG |

### Rationale
- Enables parallel development by different team members
- Each sub-epic is independently testable
- Better sprint velocity tracking
- Stories within each sub-epic are cohesive
- Aligns with Epic 10 split pattern (Decision 11)

### Impact
- FR Coverage Map updated to reference 2A/2B/2C
- Story numbering changed from 2.1-2.12 to 2A.1-2C.3
- Total story count unchanged (13 stories)

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved during implementation readiness review
- **Date:** 2026-01-03

---

## Decision 14: User-Facing Error Story for Epic 13

### Problem Statement
Implementation Readiness Assessment noted that Epic 13 (Observability & Production Hardening) was infrastructure-focused with no explicit user-facing story.

### Final Decision: ✅ Add Story 13.6

**New Story:** 13.6: Implement user-facing error messages with actionable guidance (retry, contact support, wait)

### Rationale
- Reinforces user value in a technical epic
- Ensures attorneys see helpful error messages, not technical jargon
- Aligns with UX-Decisions-Log error states section

### Impact
- Epic 13 now has 6 stories (was 5)
- User value statement updated to emphasize user communication

### Stakeholder Sign-Off
- **Juhi (Product Owner):** Approved during implementation readiness review
- **Date:** 2026-01-03

---

## Summary: Decisions 10-14 (Epic Creation & Readiness Phase)

| Decision | Status | Impact |
|----------|--------|--------|
| 10. MVP Scope Refinement | ✅ 3 Core Engines | Removed 2 engines dependent on templates |
| 11. Epic 10 Split | ✅ 4 Sub-Epics | Better sprint planning, parallel dev |
| 12. Quick Analysis Mode | ✅ Deferred + Simple Mitigation | Validate before building |
| 13. Epic 2 Split | ✅ 3 Sub-Epics | Aligns with Epic 10 pattern |
| 14. Epic 13 User Story | ✅ Story 13.6 Added | Reinforces user value |

**Updated Story Count:** 85 stories across 19 epics (13 base + 4 Epic 10 splits + 3 Epic 2 splits - 1 original Epic 2 - 1 original Epic 10)

---

**END OF DECISION LOG**
