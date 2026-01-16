# How I Built a Legal AI That Catches What Lawyers Miss — For $14 a Case

*A solo engineer's journey building forensic document intelligence for Indian litigation*

---

**TL;DR:** Litigation lawyers drown in 2000+ page case files. I built LDIP — a full-stack AI platform that ingests messy scanned PDFs, extracts entities, verifies legal citations against Acts, detects contradictions, and builds chronologies. It cuts review time by ~90% at $14 per matter. Here's how I built it.

---

## The Problem: Missing a Detail Means Malpractice

Picture this: A litigation lawyer receives a 2000-page case file. Scanned PDFs. Annexures. Petitions. Affidavits. Some handwritten. Some in regional languages. All of it dumped on their desk with a hearing date in two weeks.

Their job? Find where the opposing petition misquoted Section 65B. Track every mention of the key witness across all documents. Build a timeline that shows the notice was served 9 months late. Catch the contradiction between the affidavit on page 234 and the deposition on page 1,847.

Miss any of this? That's not just an error — it's malpractice.

**The current solutions don't work:**
- **"Chat with PDF" wrappers:** Hallucination-prone. When a lawyer asks "What does Section 65B say?", these tools often make things up. Unacceptable.
- **Enterprise monoliths:** $50K+/year. Out of reach for most Indian law firms.

I realized there was no *forensic* tool — one that could rigorously verify citations, map hidden relationships between entities across thousands of pages, and maintain an audit trail suitable for court. So I built one.

---

## The Solution: LDIP (Legal Document Intelligence Platform)

LDIP is a "Legal Operating System" that combines forensic document processing with AI reasoning. Think of it as a paranoid junior associate who reads every page, checks every citation, and never misses a contradiction — for $14 a case.

### What It Does

1. **Ingests messy documents** — Scanned PDFs, ZIP archives, handwritten notes → clean searchable text
2. **Extracts & resolves entities** — Knows "N.D. Jobalia" = "Nirav Jobalia" = "Mr. Jobalia" across 2000 pages
3. **Verifies citations** — When a petition claims "Section 65B(4) states X," LDIP checks if it actually does
4. **Builds timelines** — Auto-extracts dates, classifies events, detects sequence anomalies
5. **Finds contradictions** — "Document A says X about this person, but Document B says Y"
6. **Maintains audit trails** — Every AI finding is traceable to exact document, page, and bounding box

### The 30-Second Demo

A lawyer uploads a 2000-page case file. By the time they make coffee, LDIP has found that:
- The opposing petition misquoted Section 65B on page 234
- The key witness contradicted himself between his affidavit and deposition
- The timeline shows a document was supposedly signed two days before it existed

That's $14 and 10 minutes vs. a junior associate billing 40 hours.

---

## The Technical Architecture

### The Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16 (App Router), React 19, Tailwind CSS v4, Radix UI |
| **Backend** | FastAPI (Python 3.12), Pydantic v2, Celery + Redis |
| **Database** | Supabase PostgreSQL with pgvector for semantic search |
| **Infrastructure** | Vercel (frontend), Railway (backend), Supabase, Upstash Redis |
| **AI Engine** | Hybrid: Gemini 3 Flash + GPT-4o + Cohere Rerank v3.5 |

### The Key Insight: Hybrid AI Architecture

This was the unlock that made LDIP viable.

**The problem:** Running GPT-4 on every chunk of a 2000-page document costs $75-110. Unviable for the Indian legal market.

**The solution:** Route tasks to the right model:

| Task | Model | Why |
|------|-------|-----|
| OCR validation | Gemini 3 Flash | Bulk processing, 1M context window, 3.5x cheaper |
| Entity extraction | Gemini 3 Flash | Pattern matching, verifiable downstream |
| Citation extraction | Gemini 3 Flash | Regex-augmented, errors caught in verification |
| Contradiction detection | GPT-4o | High-stakes reasoning, user-facing |
| Q&A synthesis | GPT-4o | Accuracy critical |

**Result:** Cost dropped from $75-110 to **$13-14 per matter** — a 5-7x reduction.

```
Document Upload (2000 pages)
    ↓
GEMINI 3 FLASH: Bulk Processing
  - OCR entire case file (1M context)
  - Extract entities → Identity Graph
  - Extract events → Timeline
  - Extract citations → Pre-link to Acts
  - Cost: ~$1.00
    ↓
GPT-4o: Reasoning Layer
  - Contradiction detection
  - Complex Q&A
  - Generate responses with citations
  - Cost: ~$0.05 per query
    ↓
Response with source citations
```

---

## The Build Journey: 14 Epics, 80+ Stories, 4400+ Tests

I built LDIP over 14 epics and 80+ user stories. Here's what each layer does:

### Foundation (Epics 1-2)

**Authentication & 4-Layer Security**

Every database table has Row-Level Security policies. But I went further with 4-layer matter isolation:

1. **PostgreSQL RLS** — Database-level enforcement
2. **Vector namespaces** — Embeddings prefixed by matter_id
3. **Redis key prefixes** — Cache isolated by matter_id
4. **API middleware** — Application-level validation

Result: Zero cross-matter data leakage. Critical for legal confidentiality.

**Document Processing Pipeline**

The ingestion system handles the messy reality of legal documents:
- **Upload:** Drag-and-drop PDFs and ZIPs with progress tracking
- **OCR:** Google Document AI extracts text with bounding boxes. Gemini validates low-confidence words.
- **Chunking:** Parent-child hierarchy (large chunks for context, small for precision)
- **Search:** Hybrid BM25 + pgvector, topped by Cohere reranking

### Intelligence Engines (Epics 3-7)

**Citation Verification Engine**

The forensic heart of LDIP. When a petition claims "Section 65B(4) states X," the system:
1. Extracts all Act citations using regex + Gemini
2. Shows an "Act Discovery Report" — which Acts are referenced but missing
3. After the user uploads Act PDFs, verifies every quote against source
4. Displays mismatches in split-view with bounding-box highlighting

**Timeline Construction**

Automatically extracts dates, classifies events (filing, hearing, judgment), links them to entities, and detects anomalies. "Response filed before petition?" That's a red flag.

**Contradiction Detection**

The "gotcha" finder. Groups all statements about a specific entity across all documents, uses GPT-4o to compare statement pairs, and classifies contradictions by type (semantic, factual, date mismatch, amount mismatch) and severity.

**Engine Orchestrator**

When a user asks a question, the orchestrator:
- Analyzes intent (citation question? timeline? entity?)
- Routes to appropriate engines — sometimes in parallel
- Maintains an audit trail of every AI decision

**Three-Layer Memory System**

- **Session Memory (Redis):** Short-term conversation context with pronoun resolution
- **Matter Memory (PostgreSQL):** Long-term findings, research notes, verified facts
- **Query Cache:** Identical queries return in ~10ms vs 3-5 seconds

### Safety Layer (Epic 8)

Lawyers cannot tolerate hallucinations. I built three defenses:

1. **Query Guardrails:** Block dangerous questions ("Will I win?") via regex + GPT-4o-mini classifier
2. **Language Policing:** Post-process outputs to strip "legal advice" language ("This proves guilt" → "This document suggests...")
3. **Verification Queue:** Findings below 70% confidence must be human-verified before export

### User Experience (Epics 9-12)

- **Dashboard:** Matter cards with processing status, activity feed, grid/list toggle
- **Upload Wizard:** 5 stages with live discovery feed (watch entities appear in real-time)
- **Workspace:** 7 tabs (Summary, Timeline, Entities, Citations, Contradictions, Verification, Documents)
- **Q&A Panel:** Floating, resizable, with engine trace visibility
- **Export Builder:** Generate court-ready reports with section selection and inline editing

---

## The Pivots: What I Learned the Hard Way

### The "Graph DB" Trap

**Initial thought:** "I need Neo4j for the entity graph!"

**Reality:** Managing a separate graph database added massive complexity for simple queries. MIG queries are straightforward — get aliases for entity X, get relationships for entity Y. No complex 6-hop traversals.

**Solution:** PostgreSQL for everything. Implemented the graph using relational tables (`identity_nodes`, `identity_edges`) with proper indexing. It's faster, ACID-compliant, and simpler to secure with RLS.

### The Cost Barrier

**Blocker:** $75-110 per matter using GPT-4 for everything.

**Unlock:** Hybrid model routing. Gemini 3 Flash for bulk processing (3.5x cheaper), GPT-4o only for high-stakes reasoning.

**Result:** $13-14 per matter. 5-7x cost reduction.

### The "Hallucination" Fear

**Challenge:** Lawyers cannot tolerate made-up laws. One wrong citation could tank a case.

**Solution:** Three-layer safety:
1. Guardrails block dangerous queries before they reach the LLM
2. Language policing sanitizes outputs
3. Verification queue requires human approval for low-confidence findings

Every finding links back to exact source — document, page, bounding box. If it can't be traced, it doesn't leave the system.

---

## The Results

| Metric | Value |
|--------|-------|
| **Scale** | 14 epics, 80+ stories, 4400+ tests |
| **Cost** | $13-14 per 2,000-page matter |
| **Speed** | 100 pages in ~5 minutes |
| **Query response** | <10 seconds to verified results |
| **Citation accuracy** | >95% recall on extraction |
| **Security** | 4-layer isolation, 0% cross-matter leakage |

---

## Key Learnings

### 1. Structured Data > Chat

Lawyers don't want to "chat with their PDFs." They want structured tables — timelines, entity lists, citation verifications, contradiction reports. The chat interface is supplementary, not primary.

### 2. Show Your Work

Displaying "Thinking...", intermediate steps, and confidence scores builds trust more than instant black-box answers. Every finding shows which engine produced it, what sources it used, and how confident the system is.

### 3. Test Everything

With 4400+ tests across frontend and backend, I caught regressions early. When you're building for lawyers, you can't ship bugs that might affect case outcomes.

### 4. Design for Verification, Not Automation

The goal isn't to replace lawyers — it's to surface what they'd otherwise miss. Every AI finding goes through human verification before it can be exported. The audit trail makes this court-defensible.

---

## What's Next

**Completing MVP:**
- Export Builder with PDF/Word/PowerPoint generation
- Dashboard API integrations (replacing mocks with real data)
- Production hardening (logging, circuit breakers, rate limiting)

**Phase 2:**
- Dedicated Contradictions Tab with side-by-side comparison
- Documentation Gap Engine (auto-detect missing required documents)
- Process Chain Engine (validate event sequences against legal procedures)
- Table extraction using Docling/TableFormer
- RAG evaluation framework with lawyer-verified golden datasets

**Beta Launch:**
- Rolling out to 50 beta users in Q1 2026
- 2 pilot clients already testing

---

## The Pitch

> **Other tools help you search. LDIP helps you verify.**
>
> It's the difference between finding case law and catching where your opponent misquoted it.

What if you could walk into court knowing you've found every hole in the other side's story?

That's LDIP.

---

*Built with guidance from 100xEngineers. Powered by Supabase, Vercel, and Railway.*

*Looking for early adopter law firms handling document-heavy litigation. Reach out if you're interested in the beta.*

---

**About the Author**

Juhi is a solo full-stack engineer building LDIP as part of the 100xEngineers program. She handles product, design, backend, frontend, and DevOps — because when you're solving a real problem, you do whatever it takes.

---

*Tags: #LegalTech #AI #GenAI #FullStack #RAG #LLM #Startup #IndiaLegal*
