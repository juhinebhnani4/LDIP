# Requirements Baseline v1.0
# LDIP - Legal Document Intelligence Platform
**Status:** LOCKED - All major decisions finalized
**Date:** 2026-01-01

---

## Document Control

| Property | Value |
|----------|-------|
| **Version** | 1.0 |
| **Status** | LOCKED (Single Source of Truth) |
| **Supersedes** | All previous PRD, MVP Spec, Architecture documents |
| **Last Updated** | 2026-01-03 |
| **Amendment** | Decision 10 (2026-01-03): Reduced MVP to 3 core engines; Documentation Gap & Process Chain deferred to Phase 2 |
| **Next Review** | After MVP completion (15-16 months) |
| **Owner** | Juhi (Product Owner) |
| **Gap Resolution Research** | [fizzy-conjuring-zephyr.md](C:\Users\Jyotsna\.claude\plans\fizzy-conjuring-zephyr.md) |

---

## Executive Summary

**LDIP** is a Production-Ready Legal Document Intelligence Platform designed for complex multi-party litigation. It uses AI-powered engines to provide speed, comprehension, and pattern-catching capabilities that transform how attorneys analyze legal documents.

### Key Metrics
- **Timeline:** 15-16 months to MVP
- **Cost per Matter:** $13-14 for 2000-page case file
- **Target Users:** Litigation attorneys handling complex multi-party matters, junior associates, legal teams
- **Primary Use Case:** Corporate/securities fraud litigation
  - Securities fraud cases (Special Court - Trial of Offences Relating to Transactions in Securities Act, 1992)
  - Benami shareholding disputes
  - Dematerialization fraud
  - Custodial oversight matters (securities custodian compliance)
  - Multi-party ownership disputes involving corporate entities

**Future Expansion Note:** Architecture is domain-agnostic. Post-MVP expansion to general complex multi-party litigation (banking, employment, arbitration, IP, tax) requires only messaging changes, not architectural refactoring. See Phase 2+ roadmap.

### Value Proposition
**What Lawyers Get:**
- ✅ **Speed:** Visual citations in <10 seconds (vs 15-30 mins manual search)
- ✅ **Comprehension:** Timeline + Executive Summary automated (vs 4-6 hours manual)
- ✅ **Contradiction Catching:** Entity-resolved analysis finds name variant contradictions
- ✅ **Legal Safety:** Query guardrails + Language policing (no legal conclusions)
- ✅ **Court-Defensible:** Attorney verification workflow with forensic audit trail
- ✅ **Cost-Effective:** 5-7x cheaper than GPT-4-only solutions

### Strategic Decision
**"Go strong from the start"** - Build 3 core modular engines with 3-layer memory system from Day 1, not simple features that require refactoring later. *(Amended per Decision 10: reduced from 5 to 3 engines in MVP)*

---

## MoSCoW Prioritization

### MUST HAVE (MVP - 15-16 months)

#### 3 Core Engines (MVP) *(Amended per Decision 10)*

**1. Citation Verification Engine**
- Verify Act references against BNS/BNSS/IPC/SARFAESI statutes
- Flag misattributions and section errors
- Link citations to bounding boxes for visual highlighting
- Confidence scoring for each verification

**2. Timeline Construction Engine**
- Extract dates and events from all matter documents
- Build chronological timeline with entity associations
- Validate event sequences for logical consistency
- Cache timeline in Matter Memory for instant re-queries

**3. Consistency & Contradiction Engine**
- Use MIG (Matter Identity Graph) for entity resolution
- Group statements by canonical entity (e.g., "Nirav Jobalia" = "N.D. Jobalia")
- Detect semantic contradictions across documents
- Flag conflicting dates, amounts, claims

#### ❌ DEFERRED to Phase 2 (per Decision 10 - requires process templates)

**4. Documentation Gap Engine** - *DEFERRED*
- ~~Flag missing required documents (basic version in MVP)~~
- Requires process templates (manual templates to be created by Juhi)
- Will be implemented in Phase 2 after templates are available

**5. Process Chain Integrity Engine** - *DEFERRED*
- ~~Detect timeline deviations (basic version in MVP)~~
- Requires process templates for "typical timelines"
- Will be implemented in Phase 2 after templates are available

#### 3-Layer Memory System

**Layer 1: Session Memory (Ephemeral)**
- Redis-based storage with 7-day TTL (auto-extends on activity, max 30 days)
- Maintains conversation context across multi-day work sessions (50-100 Q&A pairs)
- Enables multi-turn conversations ("Who is custodian?" → "When did they file?")
- Entity pronoun resolution ("they" = resolved entity from context)
- Survives lunch breaks, weekends, and multi-day case preparation cycles
- Auto-archives to Matter Memory on expiry for context restoration
- Scope: Per matter + per attorney (session:{matter_id}:{user_id})
- Cleared on logout, manual session end, or 30-day hard limit

**Layer 2: Matter Memory (Persistent)**
- PostgreSQL JSONB storage per matter
- File structure:
  - `/matter-{id}/query_history.jsonb` - Forensic audit log (append-only)
  - `/matter-{id}/timeline_cache.jsonb` - Pre-built timeline (persistent)
  - `/matter-{id}/entity_graph.jsonb` - MIG relationships (cached)
  - `/matter-{id}/key_findings.jsonb` - Attorney-verified facts
  - `/matter-{id}/research_notes.jsonb` - Attorney annotations
- Enables pattern detection across sessions
- Supports collaboration (multiple attorneys, shared memory)
- Soft-delete only (audit trail compliance)

**Layer 3: Query Cache (Optimization)**
- Redis cache with 1-hour TTL
- Key format: `cache:query:{matter_id}:{query_hash}`
- Identical queries return in ~10ms (vs 3-5 seconds for fresh query)
- Cleared on document upload (matter data changes)

#### 3 Safety Features

**1. Query Guardrails (2 weeks)**
- Block dangerous legal questions
- Pattern detection using GPT-4o-mini
- Suggest safe query rewrites
- Examples:
  - Block: "Should I file appeal?" → Suggest: "What are the grounds for appeal in this matter?"
  - Block: "Is client guilty?" → Suggest: "What evidence supports/contradicts the charges?"

**2. Language Policing (1 week)**
- Sanitize legal conclusions from all outputs
- Regex + GPT-4o-mini filtering
- Transformations:
  - "violated Section 138" → "affected by Section 138"
  - "custodian is liable" → "custodian's actions may be relevant to"
  - "client is innocent" → "evidence suggests"
- Transparent filtering (user never sees raw output)

**3. Attorney Verification Workflow (3 weeks)**
- Review UI for all engine findings
- Approve/Reject/Flag with comments
- PostgreSQL audit log (who verified, when, decision)
- Court-defensible verification trail
- Dashboard showing verification queue

#### Infrastructure

**Frontend Stack:**
- Next.js 14+ (App Router with React 18)
- TypeScript (type safety)
- shadcn/ui (component library built on Radix UI)
- Tailwind CSS (styling)
- D3.js (timeline visualization)
- Zustand (state management)
- react-pdf (PDF viewing)
- SWR (data fetching)

**Backend Stack:**
- Python 3.11+
- FastAPI (REST API framework)
- Uvicorn (ASGI server)
- SQLAlchemy 2.0 (async ORM)
- Celery (task queue for long-running jobs)
- Pydantic (data validation)

**Database & Storage:**
- Supabase PostgreSQL 15+ (managed)
  - pgvector extension (vector similarity search)
  - Row-Level Security (RLS) for matter isolation
  - JSONB for Matter Memory storage
- Supabase Storage (PDF uploads, document storage)
- Supabase Auth (JWT-based authentication)

**Cache & Queue:**
- Redis 7+ (session memory + query cache)
- Celery + Redis (background task processing)

**LLM Strategy (Hybrid):**
- **Ingestion Layer:** Gemini 3 Flash
  - OCR analysis, entity extraction, timeline extraction
  - 1M token context window (entire case file)
  - Cost: $0.50 input / $3.00 output per 1M tokens
  - Multimodal (native PDF, audio, video processing)
- **Reasoning Layer:** GPT-4 (with planned GPT-5.2 upgrade)
  - Contradiction detection, executive summary, Q&A
  - Start with GPT-4, upgrade to GPT-5.2 when available/cost-effective
  - GPT-5.2 advantages: Aug 2025 knowledge cutoff (BNS jurisprudence), <1% hallucination with Thinking mode
  - Cost: ~$0.05 per query

**OCR Stack:**
- Google Document AI (primary OCR)
  - Bounding box extraction
  - Confidence scores per word
  - Cost: ~$9.50 per 2000-page matter
- Gemini 3 Flash (OCR validation)
  - Flag low-confidence words (<85%)
  - Contextual validation (dates, amounts, case numbers)
  - Pattern-based auto-correction
  - Human review queue for critical errors

**RAG Strategy:**
- **Chunking:** Parent-Child
  - Parent: 1500-2000 tokens (preserve structure)
  - Child: 400-700 tokens (50-100 token overlap)
  - Link chunks to bounding boxes for visual citations
- **Retrieval:** Hybrid Search
  - BM25 (PostgreSQL tsvector, keyword matching)
  - Vector Search (pgvector + HNSW index, semantic similarity)
  - Merge via Reciprocal Rank Fusion (RRF) → Top 20
- **Reranking:** Cohere Rerank v3
  - Rerank top 20 → Return top 3 most relevant
  - 40-70% precision gain
  - Cost: $0.10 per query
- **Embeddings:** OpenAI text-embedding-ada-002 (1536 dimensions)

**MIG (Matter Identity Graph):**
- **Tables:**
  - `identity_nodes` - Canonical entities (PERSON, ORG, INSTITUTION, ASSET)
  - `identity_edges` - Alias relationships (ALIAS_OF, HAS_ROLE, RELATED_TO)
  - `pre_linked_relationships` - Pre-computed entity connections with document references
  - `events` - Timeline fragments with entity associations
- **Purpose:** Entity resolution across name variants ("Nirav Jobalia" = "N.D. Jobalia")
- **Benefit:** Fast path for simple queries, enables contradiction detection by entity_id

---

### SHOULD HAVE (Phase 2 - After MVP)

**3 Advanced Engines (Deferred):**
- **Engine 6: Entity Authenticity** - Forgery detection via signature/seal analysis (computer vision required, high complexity, extreme liability risk)
- **Engine 7: Admissions & Non-Denial** - Detect strategic silence in pleadings (requires pleading document parsing, adversarial claim sensitivity)
- **Engine 8: Pleading Mismatch** - Cross-check claims vs supporting evidence (overlaps with Contradiction Engine, medium complexity)

**Process Templates:**
- Manual templates for common processes (SARFAESI, DRT, IBC)
- Template format: Required documents + typical timelines
- Enables full Documentation Gap and Process Chain engines
- User (Juhi) will create manual templates from real matter data during Phase 2

**Bounded Adaptive Computation:**
- Engine looping until confidence threshold reached
- Iterative refinement ("gather more evidence" → recheck)
- Variable latency (10-40 seconds vs <10 seconds single-pass)
- Adds 3 weeks development + complexity

---

### COULD HAVE (Phase 3+)

**Cross-Matter Analysis:**
- Pattern detection across multiple matters
- Trend analysis (e.g., "typical SARFAESI timeline for this bank")
- Requires aggregated data privacy considerations
- Phase 3+ scope

**Indian Cultural Sensitivity Layer:**
- Vernacular language nuance handling
- Cultural context for Indian legal proceedings
- Address Gemini code-mixing in Indic languages
- Phase 2-3 scope

**Research Journal:**
- File-based matter notes
- Analysis history tracking
- Collaborative attorney annotations
- Phase 2 scope

---

### WON'T HAVE (Out of Scope)

**NOT Building:**
- ❌ Full document management system (DMS)
- ❌ Case management system (CMS)
- ❌ Billing/time tracking
- ❌ Client portal
- ❌ Email integration
- ❌ Calendar/docketing
- ❌ E-filing integration with courts
- ❌ General-purpose legal Q&A (scope limited to matter documents only)

**Rationale:** LDIP is a **document intelligence platform**, not a law firm management suite. Focus is on AI-powered analysis of uploaded documents for a specific matter.

---

## Architecture Decisions

### 1. Engines vs Features: Modular Engine Architecture ✅

**Decision:** Build 5 modular engines with strict I/O contracts and orchestrator (not monolithic features)

**Rationale:**
- User directive: "Let's go strong from the start"
- Long-term vision: Engines are swappable, testable in isolation
- Court-defensible: Forensic audit trail at engine level
- Avoid Phase 2 refactoring: Build right architecture from Day 1

**Trade-offs Accepted:**
- Timeline: 15-16 months (vs 8 months for features)
- Complexity: Orchestrator + engine registry + I/O contracts
- Cost: Higher upfront development investment

**Benefits:**
- Modularity: Update Citation Engine without touching Timeline Engine
- Testability: Each engine unit-testable in isolation
- Forensic Audit: Granular logging (which engines ran, inputs, outputs, confidence)
- Scalability: Add new engines without refactoring core architecture

---

### 2. LLM Strategy: Hybrid Gemini + GPT ✅

**Decision:** Gemini 3 Flash for ingestion, GPT-4/GPT-5.2 for reasoning

**Rationale:**
- Gemini strengths: 1M context window, 3.5x-4.5x cheaper, native multimodal
- GPT strengths: <1% hallucination (Thinking mode), Aug 2025 knowledge cutoff (BNS jurisprudence)
- Use right tool for each layer

**Architecture Flow:**
```
Document Upload → Gemini Ingestion (OCR, entity extraction, timeline)
                → MIG Population
                → User Query
                → MIG Fast Path + RAG Retrieval
                → GPT-4 Reasoning (contradiction detection, summary, Q&A)
                → Response
```

**Cost Comparison:**
- Hybrid: $13-14 per 2000-page matter
- GPT-4 only (old MVP spec): $75-110 per matter
- Savings: 5-7x cost reduction

---

### 3. Memory Architecture: 3-Layer System ✅

**Decision:** Session + Matter + Cache (not stateless engines)

**Rationale:**
- User requirement: Multi-turn conversations ("Who is custodian?" → "When did they file?")
- Forensic audit: Query history = court-defensible usage log
- Performance: Cached MIG + timeline = faster subsequent queries
- Collaboration: Multiple attorneys share Matter Memory

**Timeline Impact:** +6-8 weeks (vs stateless engines)

**Benefits:**
- Natural UX: Lawyers can ask follow-up questions with context
- Audit Trail: Full query history per matter (legal requirement)
- Pattern Detection: Memory enables learning across queries
- Cost Savings: Cached entities reduce RAG queries by 40-60%

---

### 4. MIG + RAG Hybrid ✅

**Decision:** Build both MIG and RAG from Day 1 (not sequential)

**Rationale:**
- MIG: Entity resolution critical for contradiction detection
- RAG: Semantic understanding for complex queries
- Hybrid: MIG provides fast path, RAG provides depth

**How They Work Together:**
- MIG resolves entities: "Nirav Jobalia" → entity_id (deterministic)
- RAG retrieves context: Semantic chunks about entity (probabilistic)
- LLM combines: Entity-resolved language + semantic understanding

**Example:**
```
Query: "What did custodian say about property?"
  → MIG: Resolve "custodian" → entity_id=e-jitendra
  → RAG: Retrieve all chunks mentioning e-jitendra + "property"
  → GPT-4: Synthesize answer with canonical entity names
```

---

### 5. Database: PostgreSQL (not Graph DB) ✅

**Decision:** Supabase PostgreSQL for everything (MIG + RAG + Core tables)

**Rationale:**
- Simplicity: One database, not multiple systems
- RLS built-in: Matter isolation via Row-Level Security
- pgvector: Vector search without separate vector DB
- User preference: Supabase chosen by Juhi

**Trade-offs:**
- MIG in PostgreSQL (not Neo4j/ArangoDB): Simpler but less graph query optimization
- Acceptable: MIG queries are simple lookups, not complex graph traversals

---

### 6. OCR Strategy ✅

**Decision:** Google Document AI + Gemini validation (not Gemini-only OCR)

**Clarification:** Gemini does NOT do OCR - it validates OCR output

**Pipeline:**
```
Scanned PDF → Google Document AI (OCR)
            → Bounding boxes + text + confidence scores
            → Gemini validation (flag low confidence, contextual correction)
            → Human review queue (critical docs)
            → MIG pre-linking
```

**OCR Quality Assessment (Added 2026-01-03):**
Display OCR quality indicator per document:
| Tier | Confidence | Display | User Action |
|------|------------|---------|-------------|
| Good | >85% | Green ✓ | None required |
| Fair | 70-85% | Yellow ⚠ | Review suggested |
| Poor | <70% | Red ✗ | "Request Manual Review" button |

Poor quality documents show warning in Documents Tab with option to request manual review.

---

### 7. Export Features ✅

**Decision:** Customizable PDF export with quick summary option

**Export Builder:**
- Section selection and reordering
- Inline editing before export
- Preview before download
- Formats: PDF (primary), Word, PowerPoint

**Quick Export: Executive Summary (Added 2026-01-03):**
One-click generation of 1-2 page partner briefing:
- Case Overview (2-3 paragraphs)
- Key Parties (top 5 by mention count)
- Critical Dates (max 10)
- Verified Issues only (confidence >90% AND status='verified')
- Note: "X findings pending verification"
- Deep link to full workspace

Designed for partner/client briefings without modal interaction.

---

## Success Metrics (MVP)

| Metric | Target | Baseline (Manual) |
|--------|--------|-------------------|
| **Speed: Citation found** | <10 seconds | 15-30 minutes |
| **Comprehension: Executive summary** | <2 minutes | 4-6 hours |
| **Timeline: Event extraction** | 80%+ events, 90%+ accuracy | Manual review required |
| **Entity Resolution: Alias linking** | 95%+ accuracy | Manual name variant tracking |
| **Contradiction Detection** | 70%+ pattern flagging | Missed in manual review |
| **Citation Accuracy** | 95%+ bounding box precision | Manual verification |
| **Safety: Legal conclusions** | 0 escapes policing | N/A (manual control) |
| **Cost per Matter** | <$15 (achieved: $13-14) | Junior associate: $500-1000 |
| **Attorney Satisfaction** | 80%+ would recommend | N/A |
| **Court Acceptance** | 100% verified findings defensible | Manual work always accepted |

---

## Timeline & Cost

### MVP Timeline: 15-16 months

**Breakdown:**
- **Months 1-3:** Infrastructure setup
  - Database schema (MIG + RAG + Core tables)
  - Supabase configuration (RLS policies, Auth)
  - FastAPI backend scaffolding
  - Vue 3 frontend scaffolding
  - Dev environment setup

- **Months 4-8:** Core Engines (3 engines) *(Amended per Decision 10)*
  - Engine 1: Citation Verification (6 weeks)
  - Engine 2: Timeline Construction (6 weeks)
  - Engine 3: Consistency & Contradiction (6 weeks)
  - ~~Engine 4: Documentation Gap~~ - DEFERRED to Phase 2
  - ~~Engine 5: Process Chain Integrity~~ - DEFERRED to Phase 2
  - Engine orchestrator (2 weeks)

- **Months 9-12:** Memory System + RAG
  - MIG implementation (identity_nodes, identity_edges, pre_linked_relationships, events)
  - RAG pipeline (chunking, embeddings, hybrid search, reranking)
  - Session Memory (Redis, multi-turn conversations)
  - Matter Memory (PostgreSQL JSONB, query history, timeline cache)
  - Query Cache (Redis, 1-hour TTL)

- **Months 13-14:** Safety Features
  - Query Guardrails (2 weeks)
  - Language Policing (1 week)
  - Attorney Verification Workflow (3 weeks)

- **Months 14-15:** Integration + Testing
  - Frontend-backend integration
  - End-to-end testing
  - Performance optimization
  - Security audit

- **Month 16:** Deployment + UAT
  - Production deployment
  - User acceptance testing
  - Documentation
  - Training materials

### Cost per Matter: $13-14

**Breakdown (2000-page case file):**
- Google Document AI OCR: $9.50 (one-time)
- Gemini 3 Flash ingestion: $1.00-2.00 (one-time)
- GPT-4 reasoning: $0.05 × 10 queries = $0.50
- Cohere Rerank: $0.10 × 10 queries = $1.00
- OpenAI embeddings: $0.50 (one-time, chunking)
- **Total:** $12.00-14.00 per matter

**Comparison:**
- Old MVP spec (GPT-4 only): $75-110 per matter
- **Savings:** 5-7x cost reduction

---

## Phase Boundaries

### Phase 1 (MVP): 15-16 months *(Amended per Decision 10)*
- 3 Core Engines (Citation/Timeline/Contradiction) - *reduced from 5*
- 3-Layer Memory System (Session + Matter + Cache)
- 3 Safety Features (Guardrails + Policing + Verification)
- MIG + RAG Hybrid
- Production deployment

**Deliverable:** Court-defensible, production-ready Legal Document Intelligence Platform with attorney supervision

---

### Phase 2: TBD (After MVP)
**Triggers:** User creates manual process templates, MVP user feedback collected

**Scope:**
- Documentation Gap Engine (requires process templates)
- Process Chain Integrity Engine (requires process templates)
- 3 Advanced Engines (Authenticity, Admissions, Pleading Mismatch)
- Full Process Templates system
- Bounded Adaptive Computation (engine looping for higher accuracy)
- Research Journal (collaborative annotations)
- Indian Cultural Sensitivity Layer (vernacular improvements)

**Decision Point:** Phase 2 scope finalized after 3-6 months of MVP usage

---

### Phase 3+: Future Vision
- Cross-Matter Analysis (pattern detection across multiple cases)
- Predictive analytics (case outcome prediction)
- Integration with court e-filing systems
- Mobile app for on-the-go access

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **OCR quality poor for handwritten docs** | High | High | Gemini validation + human review queue |
| **MIG entity resolution <95% accuracy** | Medium | High | Iterative prompt engineering + attorney verification |
| **Timeline: 15-16 months may slip** | Medium | Medium | Buffer built into each phase, prioritize ruthlessly |
| **Cost: LLM API prices increase** | Medium | Medium | Hybrid architecture allows swapping models |
| **GPT-5.2 not available/affordable** | Low | Low | Start with GPT-4, upgrade when ready |
| **Process templates not ready for Phase 2** | High | Medium | MVP ships with basic hardcoded rules, Phase 2 waits for templates |
| **Attorney adoption resistance** | Medium | High | Focus on UX, attorney verification workflow (not autonomous AI) |
| **Court acceptance of AI findings** | Low | High | Attorney verification workflow = court-defensible audit trail |

---

## References

### Primary Documents
- **Gap Resolution Research:** [fizzy-conjuring-zephyr.md](C:\Users\Jyotsna\.claude\plans\fizzy-conjuring-zephyr.md) (3482 lines, all 9 gaps resolved)
- **Decision Log:** [Decision-Log.md](./Decision-Log.md) (detailed rationale for each decision)
- **MVP Scope Definition:** [MVP-Scope-Definition-v1.0.md](./MVP-Scope-Definition-v1.0.md) (implementation guide)

### Superseded Documents
- ⚠️ **LDIP-MVP-Complete-Specification.md** - SUPERSEDED (old MVP spec)
- ⚠️ **All PRD documents** - SUPERSEDED (decisions consolidated here)

### Phase 2+ Reference
- 📋 **Deep Research Analysis (parts 1-8)** - Phase 2+ vision, deferred scope

### Research Documents (Supporting)
- **GPT vs Gemini Comparison:** [gptvsgemini.md](e:\Career coaching\100x\LDIP\gptvsgemini.md)
- **Tech Stack Analysis:** [technical-ldip-tech-stack-analysis-2025-12-29.md](./research/technical-ldip-tech-stack-analysis-2025-12-29.md)
- **OCR Research:** [technical-ocr-llm-latest-technologies-research-2025-12-28.md](./research/technical-ocr-llm-latest-technologies-research-2025-12-28.md)
- **Implementation Readiness Report:** [implementation-readiness-report-2025-12-30.md](./implementation-readiness-report-2025-12-30.md)

---

## Approval & Sign-Off

**Product Owner:** Juhi
**Decision Date:** 2025-12-30 through 2026-01-01 (Gap resolution process)
**Final Decision:** "Let's go strong from the start" - Build engines with memory from Day 1

**Key Stakeholder Decisions:**
- ✅ Engines over features (15-16 months accepted)
- ✅ 3-Layer Memory in MVP (not deferred)
- ✅ Hybrid LLM strategy (Gemini + GPT)
- ✅ MIG + RAG from Day 1
- ✅ Process templates deferred to Phase 2
- ✅ **Decision 10 (2026-01-03):** Documentation Gap & Process Chain engines deferred to Phase 2 (require templates)

**Status:** LOCKED - Ready for implementation planning *(Amended 2026-01-03 per Decision 10)*

---

**END OF REQUIREMENTS BASELINE v1.0**
