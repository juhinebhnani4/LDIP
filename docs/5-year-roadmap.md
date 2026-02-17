# Jaanch AI — 5-Year Roadmap

> Lessons from Perplexity and Claude Code applied to legal document intelligence.
>
> Created: 2026-02-18

---

## Current State Summary

Jaanch is an AI-powered legal document intelligence platform for Indian lawyers. It processes case files (100-2000+ pages) and detects contradictions, misquoted laws, timeline gaps, missing documents, and entity relationship anomalies — all cited to exact page/line numbers with reasoning traces.

### What Already Exists

| Capability | Implementation |
|------------|---------------|
| **5 AI Engines** | Timeline, Entities (MIG), Citations, Contradictions, Orchestrator |
| **Hybrid Retrieval** | BM25 + semantic (pgvector HNSW) + RRF (k=60) + Cohere reranking |
| **Multi-Model Routing** | Gemini (ingestion) → GPT-4o (escalation) → GPT-3.5 (intent) → GPT-4o-mini (safety) |
| **Two-Tier Contradiction** | Gemini screens all pairs → GPT-4 escalates uncertain cases only |
| **Citation Verification** | Regex + LLM dual extraction, India Code auto-fetch, section-level validation |
| **Matter Spaces** | Persistent documents + findings + session memory per matter |
| **Parallel Processing** | Celery workers run all 5 engines concurrently post-OCR |
| **Session Memory** | 20-message sliding window per matter with archive restore |
| **Library** | Shared legal documents across matters with fuzzy dedup |
| **Verification Workflow** | Tiered confidence (REQUIRED/SUGGESTED/OPTIONAL) with forensic audit trail |
| **Cost Tracking** | Dual currency (INR/USD), per-operation, $120/month budget cap |
| **Export** | PDF/DOCX/PPT with section-specific renderers |

---

## Inspiration Sources

### From Perplexity

Perplexity is a search engine with an LLM synthesis layer on top, powered by real RAG with its own web index of 200B+ URLs. Key architectural concepts applicable to Jaanch:

- **Own Your Index** — Pre-crawl and index content proactively, don't wait for uploads
- **Multi-Stage Retrieval** — Dense + sparse + cross-encoder reranking
- **Pro Search (Multi-Step Reasoning)** — Break complex queries into sub-questions, run follow-up searches based on initial results
- **Spaces** — Persistent collaborative environments where context accumulates
- **Cross-Session Memory** — Learn user preferences across conversations
- **Citation-First Output** — Every claim traceable to source

### From Claude Code

Claude Code is a coding agent with local tool execution and an agentic loop. Key architectural concepts applicable to Jaanch:

- **Agentic Tool Loop** — LLM decides which tool to call, executes, reads result, decides next step
- **Hierarchical Context** — Layered memory (global → project → user → session) loaded automatically
- **Context Compaction** — Intelligent summarization when context window fills up
- **Parallel Subagents** — Spawn specialized agents for independent tasks
- **Local-First / Private by Default** — Tool execution happens on the user's machine, not the cloud

---

## Gap Analysis: What Jaanch Has vs What's Missing

### Already Built (~60% of the vision)

| Concept | Source | Jaanch Implementation |
|---------|--------|-----------------------|
| Hybrid retrieval (dense + sparse + rerank) | Perplexity | BM25 + pgvector + RRF + Cohere reranking |
| Citation-first output | Perplexity | Every finding → exact page, line, bounding box. Stronger than Perplexity (section-level, not URL-level) |
| Multi-model routing | Perplexity | Gemini/GPT-4o/GPT-3.5/GPT-4o-mini routed by task type |
| Spaces (persistent context) | Perplexity | Matters with persistent docs, findings, session memory |
| Agentic tool loop | Claude Code | Orchestrator: intent → plan → execute → aggregate |
| Parallel subagents | Claude Code | Celery workers running 5 engines concurrently |
| Session memory | Both | 20-message sliding window per matter with archive restore |

### Gaps to Close

| Concept | Source | What's Missing |
|---------|--------|---------------|
| Iterative sub-question decomposition | Perplexity Pro Search | Orchestrator does single-pass, not iterative "dig deeper" loops |
| Pre-crawled legal index | Perplexity | Library is upload-driven, not proactively crawled |
| Cross-session user memory | Perplexity | No learning across matters or user preference persistence |
| Hierarchical preference layers | Claude Code | Matter isolation exists but no firm → matter → user → query enrichment chain |
| LLM-driven dynamic tool selection | Claude Code | Fixed pipeline stages, not LLM-generated plans per query |
| Smart context compaction | Claude Code | Window truncation only, no LLM-summarized compaction |
| On-premise deployment | Claude Code | Cloud-only (Railway), no self-hosted option |
| Case law index | Perplexity | Citation engine covers Acts only, not judgments |
| Custom legal LLM | Perplexity (ROSE) | Relies entirely on third-party models |

---

## Roadmap

### Phase 1: Reasoning Layer (Now – 6 months)

#### 1.1 Iterative Sub-Question Decomposition

**What**: Upgrade the orchestrator from single-pass to iterative multi-step reasoning.

**Current state**:
```
Query → Intent → [Engines in parallel] → Aggregate → Done
```

**Target state**:
```
Query → Intent → [Engines in parallel] → Aggregate
  → "Need more on Section 55" → [Targeted search]
  → Re-aggregate → "Check if amended" → [Amendment check]
  → Final synthesis → Done
```

**Why**: The difference between "find what matches" and "research until you have a complete answer." A lawyer asking "Can a private company issue preference shares?" needs Jaanch to check Companies Act Section 55, then SEBI regulations, then recent amendments, then contradictions between them — iteratively, not in one shot.

**Implementation**: The orchestrator already has intent → plan → execute → aggregate. Add a feedback loop where the aggregator evaluates completeness and triggers follow-up plans if gaps are detected. Cap at 3 iterations to control cost.

**Effort**: Medium. Orchestrator refactor, no new infrastructure.

#### 1.2 Smart Context Compaction

**What**: Replace the 20-message sliding window with LLM-summarized compaction.

**Current state**: Oldest messages dropped when window fills.

**Target state**:
- LLM summarizes older turns, preserving key findings and decisions
- Selective detail preservation ("keep RERA findings in full, summarize Companies Act sections")
- Re-retrieval capability when user circles back to a summarized topic

**Why**: Deep compliance reviews involve 50+ sections across 10 Acts. Truncation loses critical earlier analysis. Summarization preserves conclusions while freeing context for new work.

**Effort**: Low-medium. New summarization step in session memory service.

---

### Phase 2: Knowledge Layer (6 months – 1 year)

#### 2.1 Pre-Crawled Legal Index

**What**: Proactively crawl and index every publicly available Indian legal document.

**Current state**: Library is upload-driven. India Code auto-fetch is reactive (triggered by citation references).

**Target state**:
- Pre-crawl India Code (all Central Acts)
- Index Gazette of India notifications
- Index State Act repositories (starting with Maharashtra, Delhi, Karnataka)
- Index RBI, SEBI, MCA circulars and notifications
- Incremental updates on a schedule (daily for circulars, weekly for Acts)

**Why**: This is the moat. When a user uploads a case file, Jaanch already knows every Act, circular, and notification referenced — no upload required. The transition from "document analysis tool" to "legal knowledge platform."

**Scale**: India Code alone has ~800 Central Acts. State repositories add ~5,000 more. Circulars from major regulators (RBI, SEBI, IRDAI, MCA) add ~10,000 documents/year.

**Infrastructure**:
- Scheduled Celery Beat tasks for crawling
- Dedicated storage bucket for the legal corpus
- Section-level chunking and embedding for the entire corpus
- Version tracking (amendment history per section)

**Effort**: High. New crawling infrastructure, significant storage, ongoing maintenance.

#### 2.2 Cross-Matter User Memory

**What**: Learn user and firm preferences across matters.

**Current state**: Session memory is per-matter only. No cross-matter learning.

**Target state**:
- Track which Acts, jurisdictions, and practice areas a user works with most
- Learn query patterns ("this user always follows up about limitation periods")
- Firm-level defaults ("all matters from this firm are Maharashtra jurisdiction")
- Proactive suggestions ("Based on your last 10 matters, you may want to check Section 138 NI Act")

**Storage**: User preference store (separate from matter data). Updated asynchronously after each session.

**Privacy**: User memory is private to each user. Firm memory is shared within the firm. Clear opt-out and deletion controls.

**Effort**: Medium. New preference service, async learning pipeline.

#### 2.3 Hierarchical Context Enrichment

**What**: Layer preferences automatically into every query.

**Architecture**:
```
Firm level:    Jurisdiction = Maharashtra, Practice = Corporate + Litigation
  ↓
Matter level:  Client = Section 8 Company, Applicable Acts = Companies Act + IT Act
  ↓
User level:    Prefers timeline-first analysis, wants Hindi term translations
  ↓
Query level:   Enriched with all above automatically
```

**Why**: The lawyer never types "in Maharashtra" or "for a Section 8 company" — Jaanch infers it from context. Reduces friction, improves relevance, builds trust.

**Effort**: Medium. New context enrichment middleware in the orchestrator.

---

### Phase 3: Intelligence Layer (Year 1 – 2)

#### 3.1 LLM-Driven Dynamic Tool Selection

**What**: Replace fixed pipeline stages with LLM-generated execution plans.

**Current state**: Intent classification maps to pre-defined engine combinations.

**Target state**:
```python
# Available tools for the legal reasoning agent
tools = [
    search_act,           # Search the pre-crawled legal index
    read_section,         # Get full text of a specific section
    find_contradictions,  # Compare two provisions
    check_amendments,     # Check if a section has been amended/repealed
    get_definitions,      # Legal definitions in context
    search_case_law,      # Find relevant judgments
    compare_provisions,   # Cross-Act comparison
    calculate_timeline,   # Date/event analysis
    resolve_entity,       # Entity disambiguation
]
# LLM decides which tools, in what order, based on the query
```

**Why**: Legal questions don't fit into 5 neat engine categories. "Is this FIR valid given the limitation period?" needs timeline analysis + Act lookup + case law search + jurisdiction check — a combination no fixed pipeline would anticipate.

**Migration**: Keep existing engines as tools. The orchestrator becomes a planner that generates tool-call sequences dynamically. Existing intent classification becomes a fast-path for common patterns.

**Effort**: High. Core architectural shift in the orchestrator.

#### 3.2 Case Law Index + Precedent Search

**What**: Extend the citation engine from Acts to judgments.

**Current state**: Citation engine validates Act references only.

**Target state**:
- Index judgments from Indian Kanoon (open access), SCC Online (with licensing), Manupatra
- Extract holdings, ratio decidendi, obiter dicta per judgment
- Link judgments to Act sections they interpret
- When Jaanch finds a contradiction about Section 138 NI Act, it surfaces: "In Dashrath Rupsingh Rathod v. State of Maharashtra, the Supreme Court held..."
- Precedent chain tracking (which judgments overruled/followed which)

**Why**: Acts tell you what the law says. Judgments tell you what the law means. A legal intelligence platform needs both.

**Licensing**: Indian Kanoon is open access. SCC Online and Manupatra require commercial licensing agreements.

**Effort**: Very high. New data partnerships, judgment parsing pipeline, legal NLP for holding extraction.

---

### Phase 4: Enterprise Layer (Year 2 – 4)

#### 4.1 On-Premise / Private Deployment

**What**: Self-hosted option for large law firms and enterprises.

**Why**: Top-tier firms (AZB, Cyril Amarchand, Trilegal, Khaitan) won't send client documents to a shared cloud. Government legal departments have even stricter requirements.

**Components**:
- Dockerized deployment (backend + worker + frontend)
- Local LLM support (see 4.3) to avoid sending data to external APIs
- Bring-your-own API keys (for firms that prefer their own OpenAI/Gemini accounts)
- Air-gapped deployment option for classified matters
- Supabase self-hosted or PostgreSQL + pgvector direct

**Pricing model**: Annual license + support, not per-query SaaS.

**Effort**: Very high. Deployment engineering, local LLM integration, enterprise support infrastructure.

#### 4.2 Collaboration & Workflow

**What**: Multi-user collaboration within matters.

**Features**:
- Role-based access (Partner, Associate, Paralegal, Client — read/write/verify permissions)
- Finding assignment ("Assign this contradiction to Associate X for verification")
- Comments and annotations on findings
- Approval workflows (Associate verifies → Partner approves → ready for court)
- Activity feed per matter showing team actions

**Why**: Law firms are teams. A solo-user tool hits a ceiling. Collaboration unlocks firm-wide adoption.

**Effort**: High. RBAC expansion, real-time collaboration (WebSocket already exists), notification system expansion.

#### 4.3 Custom Legal LLM (Fine-Tuned)

**What**: Fine-tune an open-source model on Indian legal text for high-volume tasks.

**Current state**: All LLM tasks use third-party APIs (Gemini, OpenAI).

**Target state**:
- Fine-tune Llama/Mistral on:
  - Indian legal text (Acts, judgments, circulars)
  - Legal NER (entity extraction patterns)
  - Date/event extraction in Indian legal context
  - Citation extraction patterns
- Use for high-volume ingestion tasks (entity extraction, date extraction, screening)
- Keep GPT-4o only for escalation (high-stakes reasoning)
- Host on dedicated GPU infrastructure (or use on-premise deployment)

**Why**:
- Cost reduction: Fine-tuned 7B model for entity extraction vs Gemini per call
- Latency reduction: Self-hosted inference is faster for batch processing
- Privacy: No data leaves the infrastructure
- Quality: Domain-specific fine-tuning outperforms general models on legal text

**Training data**: Use Jaanch's own verified findings as training data (citations verified by attorneys, entities manually merged, contradictions confirmed). This is a flywheel — more usage → better training data → better model.

**Effort**: Very high. ML engineering, GPU infrastructure, ongoing model maintenance.

---

### Phase 5: Platform Layer (Year 4 – 5)

#### 5.1 Legal Knowledge Graph

**What**: Connect all indexed knowledge into a queryable graph.

**Nodes**: Acts, Sections, Judgments, Entities (Judges, Courts, Parties), Circulars, Amendments
**Edges**: "interprets", "amends", "overrules", "follows", "contradicts", "cites"

**Capabilities**:
- "Show me all Supreme Court judgments that interpreted Section 138 of NI Act in the last 5 years"
- "Which RBI circulars affect this provision of the Banking Regulation Act?"
- "Trace the amendment history of Companies Act Section 149"
- Graph-powered contradiction detection (find conflicts at the legal system level, not just within a case file)

**Why**: Individual document analysis is table stakes in 5 years. The platform that maps the relationships between all Indian law becomes the infrastructure layer for legal AI.

#### 5.2 API Platform / Legal AI Infrastructure

**What**: Expose Jaanch's capabilities as APIs for third-party legal tech.

**APIs**:
- `/search/acts` — Search the pre-crawled legal index
- `/search/judgments` — Search case law with precedent chains
- `/verify/citation` — Validate an Act citation against actual text
- `/extract/entities` — NER for Indian legal documents
- `/detect/contradictions` — Cross-document contradiction detection
- `/analyze/document` — Full pipeline analysis

**Why**: Not every legal tech company needs to build their own citation engine or legal NER. Jaanch becomes the Stripe of legal AI — other products build on top of it.

**Revenue**: Usage-based API pricing alongside SaaS subscriptions.

#### 5.3 Regulatory Change Monitoring

**What**: Real-time alerts when the law changes.

**Features**:
- Monitor Gazette of India for new notifications
- Monitor regulator websites (RBI, SEBI, MCA) for new circulars
- Detect when an Act section used in an active matter gets amended
- Alert: "Section 55 of Companies Act was amended on [date]. 3 of your active matters reference this section."
- Impact analysis: "This amendment changes the interpretation used in Matter X's contradiction finding #7"

**Why**: Law changes constantly. A firm managing 200 active matters can't manually track every amendment. This is the "always-on legal intelligence" that justifies enterprise pricing.

---

## Priority Summary

| Phase | Timeline | Focus | Key Deliverables |
|-------|----------|-------|-----------------|
| **1** | Now – 6 months | Reasoning | Iterative sub-queries, smart compaction |
| **2** | 6 months – 1 year | Knowledge | Pre-crawled legal index, user memory, context enrichment |
| **3** | Year 1 – 2 | Intelligence | Dynamic tool selection, case law index |
| **4** | Year 2 – 4 | Enterprise | On-premise deployment, collaboration, custom LLM |
| **5** | Year 4 – 5 | Platform | Knowledge graph, API platform, regulatory monitoring |

---

## Architecture Vision (Year 5)

```
┌──────────────────────────────────────────────────────────────┐
│                      JAANCH PLATFORM                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌─────────────────────────────┐     │
│  │  LEGAL INDEX      │    │  MATTER SPACES              │     │
│  │  (from Perplexity) │    │  (from Perplexity)          │     │
│  │                    │    │                             │     │
│  │  Every Act,        │    │  Private docs + public law, │     │
│  │  Judgment,         │    │  accumulated context,       │     │
│  │  Circular          │    │  team collaboration         │     │
│  │  pre-indexed       │    │                             │     │
│  └────────┬───────────┘    └──────────┬──────────────────┘     │
│           │                           │                      │
│           ▼                           ▼                      │
│  ┌───────────────────────────────────────────────────────┐   │
│  │         HYBRID RETRIEVAL (from Perplexity)            │   │
│  │    Dense + Sparse + Legal Cross-Encoder Reranker      │   │
│  └───────────────────────┬───────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │       AGENTIC ORCHESTRATOR (from Claude Code)         │   │
│  │                                                       │   │
│  │  LLM-driven tool selection with iterative reasoning:  │   │
│  │  search_act, read_section, find_contradictions,       │   │
│  │  check_amendments, get_definitions, search_case_law,  │   │
│  │  compare_provisions, resolve_entity                   │   │
│  │                                                       │   │
│  │  Spawns parallel subagents for complex analysis       │   │
│  └───────────────────────┬───────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │        CONTEXT LAYERS (from Claude Code)              │   │
│  │                                                       │   │
│  │  Firm prefs → Matter context → User memory →          │   │
│  │  Query enrichment + Smart compaction                  │   │
│  └───────────────────────┬───────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │       CITATION-FIRST OUTPUT (from Perplexity)         │   │
│  │                                                       │   │
│  │  Every claim → Section, Act, Date, Page, Line         │   │
│  │  Contradiction warnings inline                        │   │
│  │  Amendment status flagged                             │   │
│  │  Relevant precedents cited                            │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              LEGAL KNOWLEDGE GRAPH                    │   │
│  │                                                       │   │
│  │  Acts ←→ Sections ←→ Judgments ←→ Amendments          │   │
│  │  Entities ←→ Courts ←→ Circulars ←→ Regulators       │   │
│  │                                                       │   │
│  │  "interprets" / "amends" / "overrules" / "follows"   │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              API PLATFORM                             │   │
│  │                                                       │   │
│  │  /search/acts  /verify/citation  /extract/entities    │   │
│  │  /search/judgments  /detect/contradictions             │   │
│  │  /monitor/amendments                                  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Principle

**Perplexity teaches you how to own the knowledge layer. Claude Code teaches you how to reason over it.**

Jaanch's 5-year trajectory is the fusion: own every piece of Indian law (knowledge), reason over it dynamically per query (intelligence), and make it trustworthy enough for court (citations + verification + audit trails).
