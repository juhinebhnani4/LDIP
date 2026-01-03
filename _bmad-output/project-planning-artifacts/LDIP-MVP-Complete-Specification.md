---
⚠️ **DOCUMENT STATUS: SUPERSEDED**

This document has been superseded by the official Requirements Baseline v1.0.

**Superseded Date:** 2026-01-01
**Replaced By:** [Requirements-Baseline-v1.0.md](./Requirements-Baseline-v1.0.md)
**Reason:** Gap resolution research identified conflicting decisions across 30+ documents. All decisions have been consolidated into a single source of truth.

**Do NOT reference this document for implementation.**

For current requirements, see:
- **Single Source of Truth:** [Requirements-Baseline-v1.0.md](./Requirements-Baseline-v1.0.md)
- **Decision Rationale:** [Decision-Log.md](./Decision-Log.md)
- **Implementation Guide:** [MVP-Scope-Definition-v1.0.md](./MVP-Scope-Definition-v1.0.md)

**Key Changes from this document:**
- ✅ Architecture: 5 Modular Engines (not 7 features) - "go strong from the start"
- ✅ Timeline: 15-16 months (not 4 months) - building engines from Day 1
- ✅ Memory: 3-Layer Memory System IN MVP (not deferred)
- ✅ LLM: Hybrid Gemini + GPT-4/GPT-5.2 (confirmed hybrid strategy)
- ✅ Cost: $13-14 per matter (vs $75-110 in this doc)
- ❌ Deferred: Process Templates, 3 Advanced Engines (Authenticity, Admissions, Pleading Mismatch)

---

# LDIP MVP Complete Specification
**Legal Document Intelligence Platform - Production Roadmap**

**Date:** 2025-12-30
**Version:** 1.0 - Final MVP Scope
**Author:** Juhi (with Claude analysis)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [MVP Vision & Value Proposition](#mvp-vision--value-proposition)
3. [The 7 Core Features](#the-7-core-features)
4. [Complete Tech Stack](#complete-tech-stack)
5. [End-to-End System Flow](#end-to-end-system-flow)
6. [Anti-Hallucination Strategy](#anti-hallucination-strategy)
7. [4-Month MVP Roadmap](#4-month-mvp-roadmap)
8. [Success Metrics](#success-metrics)
9. [Future Phases (Post-MVP)](#future-phases-post-mvp)
10. [Critical Gaps & Mitigations](#critical-gaps--mitigations)
11. [Cost Analysis](#cost-analysis)

---

## Executive Summary

### The Problem

Junior lawyers face 500-2000 page case files and need to:
- Orient themselves quickly (partner asks: "What's this case about?")
- Find specific information buried across hundreds of documents
- Verify citations and detect contradictions
- Build timelines and understand entity relationships
- Trust that they haven't missed anything critical

**Current solution:** Manual reading = 5-7 hours of tedious work per case

### The Solution

**LDIP MVP:** An AI-powered case intelligence system that delivers:
- **Visual document navigation** with highlighted citations
- **One-page executive summaries** generated in 2 minutes
- **Automatic timeline extraction** with visual display
- **Entity relationship mapping** with alias resolution
- **Citation verification** against bare acts
- **Contradiction detection** across documents
- **Natural language Q&A** with visual proof

**Time saved:** 4.8-7.2 hours per case
**Cost:** $75-110 per 2000-page case
**ROI:** 78-91% cost reduction vs manual junior lawyer review

### Strategic Approach

**MVP Focus:** Build features that DON'T require legal domain knowledge
- Prove massive value with intelligent search, summarization, and visualization
- Build credibility and trust with lawyers
- Then ask lawyers for process templates (Phase 2)
- Add advanced engines (Documentation Gap, Process Chain) in Phase 2-3

**Key Insight:** We can deliver 80% of value with 40% of complexity by focusing on RAG intelligence rather than rule-based engines.

---

## MVP Vision & Value Proposition

### Tagline
**"From 2000-page chaos to courtroom clarity in 5 minutes"**

### Target User
**Junior Lawyers (3-5 years experience)** handling:
- Securities fraud cases
- Property disputes
- Multi-party litigation
- Regulatory compliance matters
- Any case with 500+ page document sets

### User Journey (Before LDIP)

**8:00 PM:** Partner dumps 1500-page case file on desk
**8:05 PM:** "Court tomorrow at 10 AM. Brief me on what this case is about."
**8:10 PM:** Junior lawyer opens first PDF, starts reading...
**11:00 PM:** Still on page 347, taking notes manually
**1:30 AM:** Finally finishes, exhausted, uncertain if missed anything

### User Journey (With LDIP)

**8:00 PM:** Partner dumps 1500-page case file
**8:05 PM:** "Court tomorrow at 10 AM. Brief me."
**8:06 PM:** Junior uploads to LDIP
**8:08 PM:** (2 min processing) One-page summary generated
**8:10 PM:** Asks LDIP: "What does the last order say?"
**8:11 PM:** Click citation → PDF opens with exact text highlighted
**8:15 PM:** Reviews timeline, entity graph, contradictions
**8:20 PM:** Sends brief to partner, goes home at reasonable hour

**Result:** Happier lawyer, better work-life balance, confident they didn't miss critical info

---

## The 7 Core Features

### Feature 1: Visual Citation Navigator ⭐⭐⭐⭐⭐

**User Value:**
Click any finding → PDF opens to exact page with text highlighted in yellow

**Technical Implementation:**
- Store bounding box coordinates from Google Document AI OCR
- Database schema: `citations(doc_id, page, bbox_x, bbox_y, bbox_width, bbox_height, text, confidence)`
- PDF.js viewer with overlay system
- Click handler: Retrieve bbox → Open PDF → Draw highlight

**Time Saved:** 30-60 minutes per session (vs hunting through PDFs manually)

**Wow Factor:** EXTREME - This is what makes lawyers say "holy shit, I need this"

**Why Critical:** Without visual verification, lawyers won't trust AI findings. This builds trust instantly.

---

### Feature 2: One-Page Executive Summary ⭐⭐⭐⭐⭐

**User Value:**
"What is this case about?" answered in 2 minutes vs 2 hours of reading

**Technical Implementation:**
- GPT-4 with structured prompt:
  ```
  Analyze this case file and generate a one-page executive summary covering:
  1. Parties (petitioner, respondent, key actors)
  2. Subject matter (what is this case about?)
  3. Current status (last order, date, ruling)
  4. Key timeline (case filed, major events, current stage)
  5. Critical issues (3-5 bullet points)

  Base your summary ONLY on the documents provided. Cite sources.
  ```
- Parent-child chunking ensures full context available
- Hybrid search retrieves most relevant document sections

**Time Saved:** 90-120 minutes (vs reading entire file for overview)

**Wow Factor:** EXTREME - Partners want this, junior lawyers need this

**Output Example:**
```markdown
# Executive Summary - Case ABC/2018

**Parties:**
- Petitioner: Nirav D. Jobalia
- Respondent: Custodian (appointed under Securities Act 1992)
- Other parties: Payal Shah (witness), XYZ Corporation

**Subject Matter:**
Property attachment and dematerialisation dispute under Special Court
(Trial of Offences Relating to Transactions in Securities) Act, 1992

**Last Order:** January 15, 2020 - Appeal rejected by Special Court

**Status:** Case filed 2018, currently pending final resolution

**Key Issues:**
1. Whether property attachment was lawful under Section 3(2)
2. Validity of dematerialisation process timeline
3. Custodian's duty and alleged lapses
4. Contradictory statements by petitioner across filings
5. Missing documentation in transfer chain

**Next Steps:** Compliance hearing scheduled for February 15, 2025
```

---

### Feature 3: Automatic Timeline Extraction ⭐⭐⭐⭐⭐

**User Value:**
Visual chronology of all events - see case progression at a glance

**Technical Implementation:**
- NER (Named Entity Recognition) for date extraction
- Event extraction using GPT-4:
  - Identify: What happened, when, who did it, which document
  - Classify: Filing, order, hearing, transaction, notice, etc.
- Timeline data structure:
  ```json
  {
    "events": [
      {
        "date": "2018-05-05",
        "event": "Dematerialisation request filed",
        "actor": "Nirav D. Jobalia",
        "doc_id": "doc-14",
        "page": 23,
        "bbox_id": 145,
        "category": "filing"
      }
    ]
  }
  ```
- Visualization: Horizontal timeline with event markers
- Interactive: Click event → PDF opens with highlight

**Time Saved:** 45-60 minutes (vs manually building timeline)

**Wow Factor:** HIGH - Visual comprehension is instant

**Advanced Features (Optional for MVP):**
- Duration calculations (e.g., "Demat to Sale = 254 days")
- Gap detection (e.g., "8-month silence between events")
- Multi-track timeline (separate tracks for different parties)

---

### Feature 4: Entity Resolution & Relationship Graph ⭐⭐⭐⭐

**User Value:**
"Who is who?" with automatic alias detection and relationship mapping

**Technical Implementation:**

**Step 1: Entity Extraction**
- NER for: PERSON, ORG (organization), DATE, MONEY, LOCATION
- Store: `entities(matter_id, entity_id, entity_type, canonical_name, aliases[], first_mention_doc, first_mention_page)`

**Step 2: Alias Resolution**
- Fuzzy matching algorithm:
  - "Nirav D. Jobalia" vs "N.D. Jobalia" vs "Mr. Jobalia" → Same entity
  - Techniques: Edit distance, phonetic similarity, context analysis
- Confidence scoring: High (>95%), Medium (70-95%), Low (<70%)
- Manual override capability for lawyer verification

**Step 3: Relationship Extraction**
- Pattern matching: "X introduced Y", "X is director of Y", "X family member of Y"
- Store: `relationships(entity_id_1, entity_id_2, relationship_type, doc_id, page, bbox_id)`

**Step 4: Visualization**
- Network graph: Nodes = entities, Edges = relationships
- Libraries: D3.js or Vis.js for interactive graph
- Click node → See all mentions with highlights
- Click edge → See relationship evidence

**Time Saved:** 30-45 minutes (vs manually tracking entities)

**Wow Factor:** MEDIUM-HIGH - Lawyers love visual relationship maps

**Example:**
```
Graph:
Nirav D. Jobalia (PERSON)
  ├─ introduces → Payal Shah (PERSON)
  ├─ director of → XYZ Corporation (ORG)
  └─ related to → Ashwin Mehta (PERSON)

Payal Shah (PERSON)
  └─ witness for → Custodian (ORG)
```

---

### Feature 5: Citation Verification Engine ⭐⭐⭐⭐

**User Value:**
"Is Section X cited correctly?" - Catches misquotations and omitted provisos

**Technical Implementation:**

**Step 1: Act Ingestion**
- Ingest Securities Act 1992 PDF
- Structure: `acts(act_name, section_number, subsection, text, provisos[], exceptions[])`
- Make system generic: Can ingest ANY bare act

**Step 2: Citation Pattern Recognition**
- Regex patterns:
  - `Section \d+(\(\d+\))?` → "Section 3(2)"
  - `Section \d+ subsection \d+` → "Section 3 subsection 2"
  - `S\. \d+` → "S. 3"
- Extract: Which Act, which section, claimed text

**Step 3: Text Comparison**
- Retrieve actual section text from Act database
- Compare: Claimed text vs Actual text
- Similarity scoring: Levenshtein distance, semantic similarity
- Detect omissions: Are provisos/exceptions cited?

**Step 4: Output**
- Side-by-side display:
  ```
  Claimed (Doc 45, Page 12):
  "Section 3(2) allows property attachment without notice"

  Actual (Securities Act 1992, Section 3(2)):
  "...on being satisfied on information received that any person
  has been involved in any offence... shall stand attached
  simultaneously with the issue of the notification"

  ❌ Missing context: "on being satisfied on information received"
  ⚠️ Proviso omitted: Custodian must notify within 24 hours
  Similarity: 68% (🟡 Medium confidence)
  ```

**Time Saved:** 20-30 minutes (vs manually checking bare acts)

**Wow Factor:** HIGH - Catches errors lawyers might miss

---

### Feature 6: Contradiction Detection Engine ⭐⭐⭐

**User Value:**
"Did they change their story?" - Find inconsistent statements by same party

**Technical Implementation:**

**Step 1: Claim Extraction**
- Identify factual claims in documents:
  - Pattern: "X states that Y", "According to X, Y", "X claims Y"
- Store: `claims(entity_id, claim_text, doc_id, page, bbox_id, date_filed)`

**Step 2: Semantic Comparison**
- Group claims by same entity (using alias resolution)
- Compare semantically similar claims:
  - Embedding similarity (cosine similarity > 0.8)
  - Identify contradictory pairs using LLM:
    ```
    Claim 1: "Notice sent on June 5, 2018"
    Claim 2: "Notice pending as of June 2018"
    Are these contradictory? [Yes/No/Uncertain]
    ```

**Step 3: Confidence Scoring**
- Contradiction confidence:
  - High (>90%): Clear contradiction (dates, amounts, Yes/No statements)
  - Medium (70-90%): Semantic contradiction requiring interpretation
  - Low (<70%): Possibly contradictory, needs review

**Step 4: Output**
- List contradictions with evidence:
  ```
  ⚠️ Contradiction Detected
  Entity: Nirav D. Jobalia
  Confidence: 85% (🟡 Medium)

  Statement 1 (Doc 23, Page 45, 2018-06-12):
  "We sent notice to custodian on June 5, 2018"
  [Click to view highlight]

  Statement 2 (Doc 67, Page 89, 2020-03-15):
  "Notice to custodian was pending as of June 2018"
  [Click to view highlight]

  Recommended Action: Verify which statement is accurate
  ```

**Time Saved:** 15-30 minutes (vs manually cross-checking statements)

**Wow Factor:** MEDIUM - Requires tuning but very valuable when it works

**Challenges:**
- False positives (statements that seem contradictory but aren't)
- Context dependency (statement true in one context, false in another)
- Temporal logic (statement was true in 2018, changed in 2020 due to new evidence)

**Mitigation:**
- Conservative confidence thresholds (only flag high-confidence contradictions)
- Human-in-the-loop verification
- Clear labeling: "Potential contradiction - requires review"

---

### Feature 7: Natural Language Q&A with Visual Highlights ⭐⭐⭐⭐⭐

**User Value:**
Ask questions in plain English, get answers with visual proof

**Technical Implementation:**

**Step 1: Query Processing**
- User asks: "Where is the property attachment order?"
- Query understanding: Extract intent, entities, constraints

**Step 2: Retrieval (RAG)**
- Hybrid search (BM25 + Vector):
  - BM25: Keyword matching for exact phrases ("property attachment order")
  - Vector: Semantic similarity for conceptual matches
- Retrieve top 10 chunks (child chunks for precision)
- Rerank using Cohere Rerank v3 → Top 3 chunks

**Step 3: Context Enrichment**
- For each retrieved child chunk, fetch parent chunk (1500-2000 tokens)
- This gives LLM full context while retrieval used precise chunks

**Step 4: Answer Generation**
- GPT-4 prompt:
  ```
  Based ONLY on the context below, answer this question:
  "Where is the property attachment order?"

  Context: [Parent chunks with full context]

  Requirements:
  - Cite document ID, page number, and bbox_id for each claim
  - If answer not in context, say "Not found in documents"
  - Provide confidence score (High/Medium/Low)

  Format your answer as:
  Answer: [Your answer]
  Citations: [Doc ID, Page, bbox_id]
  Confidence: [High/Medium/Low]
  ```

**Step 5: Visual Presentation**
- Display answer with inline citation links
- Click citation → PDF opens with bounding box highlight
- Show confidence indicator (🟢🟡🔴)

**Example Interaction:**
```
User: "Where is the property attachment order?"

LDIP Response:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Answer:
The property attachment order was issued by the Special Court
on June 10, 2018, directing the Custodian to attach all movable
and immovable property belonging to Nirav D. Jobalia under
Section 3(3) of the Securities Act 1992.

Citations:
• Document 47, Page 89 [View Highlight]
• Document 51, Page 12 [View Highlight]

Confidence: 🟢 High (98%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Time Saved:** 60-90 minutes (vs searching manually)

**Wow Factor:** EXTREME - Natural language + visual proof = magic

**Advanced Capabilities (Optional for MVP):**
- Multi-hop reasoning: "What happened after the attachment order?"
- Comparison queries: "Compare Party A vs Party B's version of events"
- Negative queries: "What is NOT mentioned in the case file?"

---

## Complete Tech Stack

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 16 + React)            │
│  - Dashboard  - Timeline  - Entity Graph  - PDF Viewer      │
└─────────────────┬───────────────────────────────────────────┘
                  │ REST API / WebSocket
┌─────────────────▼───────────────────────────────────────────┐
│               BACKEND (FastAPI + Python 3.11)               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           ORCHESTRATOR / API LAYER                  │   │
│  │  - Request routing  - Matter isolation  - Auth      │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 7 CORE ENGINES                      │   │
│  │  1. Visual Navigator  5. Citation Verifier          │   │
│  │  2. Summarizer        6. Contradiction Detector     │   │
│  │  3. Timeline Builder  7. Q&A Engine                 │   │
│  │  4. Entity Resolver                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              RAG / INTELLIGENCE LAYER               │   │
│  │  - Hybrid Search  - Reranking  - Embeddings         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                   DATA & STORAGE LAYER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ PostgreSQL   │  │  Supabase    │  │    Redis     │      │
│  │ + pgvector   │  │   Storage    │  │   Cache      │      │
│  │ + RLS        │  │ (Documents)  │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                  EXTERNAL SERVICES                          │
│  - Google Document AI (OCR)  - OpenAI (GPT-4, Embeddings)  │
│  - Cohere (Rerank v3)        - Sentry (Monitoring)         │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Component Breakdown

#### **1. Frontend Stack**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Next.js 16 + React 19 | Modern, stable framework with App Router and SSR |
| **UI Components** | shadcn/ui + Tailwind CSS | Accessible, responsive component library |
| **State Management** | Zustand | Lightweight state management for React |
| **PDF Viewer** | PDF.js | Open-source PDF rendering with annotation support |
| **Charts/Graphs** | D3.js or Vis.js | Timeline and entity relationship visualization |
| **HTTP Client** | fetch (native) | API communication (Next.js native support) |
| **Auth** | Supabase Auth SDK | JWT-based authentication |

**Key Features:**
- Responsive design (mobile + desktop)
- Real-time updates (WebSocket for long-running operations)
- Accessibility (WCAG 2.1 AA compliance)
- Dark mode support (optional)

---

#### **2. Backend Stack**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI (Python 3.11+) | High-performance async API with auto-docs |
| **Validation** | Pydantic v2 | Type safety and data validation |
| **Background Tasks** | Celery + Redis | Async task processing for OCR, indexing |
| **WebSocket** | FastAPI WebSocket | Real-time progress updates |
| **Logging** | Structlog | Structured logging for debugging |
| **Metrics** | Prometheus + Grafana | Performance monitoring |

**API Design:**
- RESTful endpoints for CRUD operations
- WebSocket for long-running tasks (upload, processing)
- OpenAPI 3.0 auto-generated docs
- Rate limiting (per user, per matter)
- Request/response validation

---

#### **3. Data & Storage Layer**

##### **PostgreSQL 15+ with Extensions**

```sql
-- Core extensions
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector 0.5.0+
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- Trigram matching for fuzzy search
CREATE EXTENSION IF NOT EXISTS btree_gin;   -- Full-text search indexing
```

**Schema Design:**

```sql
-- Matter (case file)
CREATE TABLE matters (
  matter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(user_id),
  status TEXT DEFAULT 'active', -- active, archived, deleted
  metadata JSONB
);

-- Documents
CREATE TABLE documents (
  doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL, -- Supabase Storage URL
  total_pages INT,
  ocr_status TEXT, -- pending, processing, completed, failed
  ocr_confidence_avg DECIMAL(5,2), -- Average OCR confidence across pages
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB
);

-- Pages (for bounding boxes)
CREATE TABLE pages (
  page_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
  page_number INT NOT NULL,
  ocr_text TEXT, -- Full OCR text for this page
  ocr_confidence DECIMAL(5,2),
  width INT, -- Page dimensions for bbox scaling
  height INT,
  UNIQUE(doc_id, page_number)
);

-- Bounding Boxes (CRITICAL for visual citations)
CREATE TABLE bounding_boxes (
  bbox_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id UUID REFERENCES pages(page_id) ON DELETE CASCADE,
  x DECIMAL(10,2) NOT NULL, -- Normalized coordinates (0-1)
  y DECIMAL(10,2) NOT NULL,
  width DECIMAL(10,2) NOT NULL,
  height DECIMAL(10,2) NOT NULL,
  text TEXT NOT NULL, -- Extracted text in this box
  confidence DECIMAL(5,2), -- OCR confidence for this specific box
  bbox_type TEXT, -- word, line, paragraph, block
  INDEX idx_page_bbox (page_id)
);

-- Chunks (Parent-Child structure)
CREATE TABLE chunks (
  chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
  chunk_type TEXT NOT NULL, -- 'parent' or 'child'
  parent_chunk_id UUID REFERENCES chunks(chunk_id), -- NULL for parent chunks
  content TEXT NOT NULL,
  token_count INT,
  embedding vector(1536), -- OpenAI ada-002 embeddings
  page_start INT,
  page_end INT,
  bbox_ids UUID[], -- Array of bbox_id references for visual linking
  metadata JSONB,

  -- Vector search index (HNSW algorithm)
  INDEX idx_chunk_embedding ON chunks USING hnsw (embedding vector_cosine_ops)
);

-- Entities
CREATE TABLE entities (
  entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL, -- PERSON, ORG, DATE, MONEY, LOCATION
  canonical_name TEXT NOT NULL,
  aliases TEXT[], -- Alternative names/spellings
  first_mention_doc UUID REFERENCES documents(doc_id),
  first_mention_page INT,
  first_mention_bbox UUID REFERENCES bounding_boxes(bbox_id),
  metadata JSONB,
  UNIQUE(matter_id, canonical_name, entity_type)
);

-- Entity Mentions
CREATE TABLE entity_mentions (
  mention_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id UUID REFERENCES entities(entity_id) ON DELETE CASCADE,
  doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
  page_id UUID REFERENCES pages(page_id),
  bbox_id UUID REFERENCES bounding_boxes(bbox_id),
  mention_text TEXT, -- Actual text as it appears
  context TEXT, -- Surrounding text for disambiguation
  confidence DECIMAL(5,2) -- NER confidence
);

-- Relationships
CREATE TABLE relationships (
  relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  entity_id_1 UUID REFERENCES entities(entity_id),
  entity_id_2 UUID REFERENCES entities(entity_id),
  relationship_type TEXT, -- 'introduces', 'director_of', 'family', 'witness_for'
  doc_id UUID REFERENCES documents(doc_id),
  page_id UUID REFERENCES pages(page_id),
  bbox_id UUID REFERENCES bounding_boxes(bbox_id),
  confidence DECIMAL(5,2),
  CHECK (entity_id_1 != entity_id_2)
);

-- Timeline Events
CREATE TABLE timeline_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  event_date DATE NOT NULL,
  event_text TEXT NOT NULL,
  event_type TEXT, -- filing, order, hearing, transaction, notice
  actor_entity_id UUID REFERENCES entities(entity_id),
  doc_id UUID REFERENCES documents(doc_id),
  page_id UUID REFERENCES pages(page_id),
  bbox_id UUID REFERENCES bounding_boxes(bbox_id),
  confidence DECIMAL(5,2),
  INDEX idx_matter_date (matter_id, event_date)
);

-- Citations (from case documents)
CREATE TABLE citations (
  citation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  doc_id UUID REFERENCES documents(doc_id),
  page_id UUID REFERENCES pages(page_id),
  bbox_id UUID REFERENCES bounding_boxes(bbox_id),
  act_name TEXT, -- 'Securities Act 1992'
  section_number TEXT, -- '3(2)'
  cited_text TEXT, -- What the document claims the Act says
  verification_status TEXT, -- 'verified', 'mismatch', 'pending'
  similarity_score DECIMAL(5,2), -- Similarity to actual Act text
  INDEX idx_matter_act (matter_id, act_name)
);

-- Bare Acts (reference database)
CREATE TABLE acts (
  act_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  act_name TEXT NOT NULL,
  section_number TEXT NOT NULL,
  subsection TEXT,
  full_text TEXT NOT NULL,
  provisos TEXT[],
  exceptions TEXT[],
  metadata JSONB,
  UNIQUE(act_name, section_number, subsection)
);

-- Contradictions
CREATE TABLE contradictions (
  contradiction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(matter_id) ON DELETE CASCADE,
  entity_id UUID REFERENCES entities(entity_id), -- Who made contradictory statements
  claim_1_text TEXT,
  claim_1_doc UUID REFERENCES documents(doc_id),
  claim_1_bbox UUID REFERENCES bounding_boxes(bbox_id),
  claim_2_text TEXT,
  claim_2_doc UUID REFERENCES documents(doc_id),
  claim_2_bbox UUID REFERENCES bounding_boxes(bbox_id),
  contradiction_type TEXT, -- 'date', 'amount', 'fact', 'semantic'
  confidence DECIMAL(5,2),
  reviewed BOOLEAN DEFAULT FALSE
);

-- Row-Level Security (RLS) for matter isolation
ALTER TABLE matters ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own matters
CREATE POLICY matter_isolation ON matters
  FOR ALL
  USING (created_by = auth.uid());

CREATE POLICY document_isolation ON documents
  FOR ALL
  USING (matter_id IN (
    SELECT matter_id FROM matters WHERE created_by = auth.uid()
  ));
```

##### **Supabase Storage (S3-compatible)**

- **Bucket structure:**
  - `documents/{matter_id}/{doc_id}/original.pdf`
  - `documents/{matter_id}/{doc_id}/pages/page_{n}.png` (optional thumbnails)

- **Access control:** Signed URLs with expiration

##### **Redis 7+**

**Use cases:**
- Query result caching (TTL: 1 hour)
- Session management
- Rate limiting counters
- Background task queue (Celery broker)

**Key structure:**
```
cache:query:{matter_id}:{query_hash} → JSON result
session:{user_id} → Session data
ratelimit:{user_id}:{endpoint} → Request counter
```

---

#### **4. External Services**

##### **Google Document AI**

**API:** `documentai.googleapis.com/v1`

**Configuration:**
```python
from google.cloud import documentai_v1 as documentai

processor = documentai.DocumentProcessorServiceClient()
processor_name = "projects/{PROJECT}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

# Process document
request = documentai.ProcessRequest(
    name=processor_name,
    raw_document=documentai.RawDocument(
        content=pdf_bytes,
        mime_type="application/pdf"
    )
)

result = processor.process_document(request)

# Extract bounding boxes
for page in result.document.pages:
    for block in page.blocks:
        bbox = block.layout.bounding_poly
        # Store: bbox.normalized_vertices (x, y coordinates 0-1)
```

**Cost:** $60-90 per 2000-page matter

**Alternatives for evaluation:**
- **Docling (IBM Open Source)** - Free, evaluate quality on Indian legal docs

##### **OpenAI API**

**Models:**
- **GPT-4** (primary): Complex analysis, summarization, Q&A
  - Cost: $10-15 per 2000-page matter
  - Hallucination rate: 58% (lowest among commercial LLMs)

- **GPT-3.5-turbo** (secondary): Simple tasks, entity extraction
  - Cost: $1-2 per matter
  - Use for: NER, date extraction, simple classifications

- **text-embedding-ada-002**: Embeddings
  - Cost: $0.50 per 2000-page matter
  - Dimensions: 1536

**API Configuration:**
```python
import openai

# Summarization
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Summarize this case:\n{context}"}
    ],
    temperature=0.1,  # Low temperature for consistency
    max_tokens=1000
)

# Embeddings
embedding = openai.Embedding.create(
    model="text-embedding-ada-002",
    input=chunk_text
)
```

##### **Cohere Rerank v3**

**API:** `api.cohere.ai/v1/rerank`

**Purpose:** Rerank retrieved chunks for precision

**Implementation:**
```python
import cohere

co = cohere.Client(api_key=COHERE_API_KEY)

# After initial retrieval (BM25 + Vector → 10 chunks)
reranked = co.rerank(
    query=user_query,
    documents=[chunk.content for chunk in retrieved_chunks],
    top_n=3,  # Return top 3 most relevant
    model="rerank-english-v3.0"
)

# Use reranked results for LLM context
top_chunks = [retrieved_chunks[r.index] for r in reranked.results]
```

**Cost:** $0.10 per query (average 5-10 queries per case = $0.50-1.00)

**Benefit:** 40-70% precision gain (proven in legal RAG research)

##### **Sentry (Monitoring)**

**Free tier:** Up to 5k events/month

**Features:**
- Error tracking
- Performance monitoring
- User session replay (optional)
- Alerting (Slack/email)

---

#### **5. Development & Deployment**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Version Control** | GitHub | Code repository |
| **CI/CD** | GitHub Actions | Automated testing, deployment |
| **Hosting (Backend)** | Railway or Render | Python backend hosting |
| **Hosting (Frontend)** | Vercel | Static site + SSR for Next.js 16 |
| **Database** | Supabase (managed PostgreSQL) | Scalable database with RLS |
| **Secrets Management** | GitHub Secrets + Vault | API keys, credentials |
| **Testing** | Pytest + Playwright | Unit, integration, E2E tests |

**CI/CD Pipeline:**
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest tests/

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Railway
        run: railway up

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Vercel
        run: vercel --prod
```

---

## End-to-End System Flow

### Flow 1: Document Upload & Ingestion

**User Action:** Upload 2000-page PDF case file

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Upload & Storage (5 seconds)                            │
└─────────────────────────────────────────────────────────────────┘

User (Frontend)
  ↓ Upload PDF (2000 pages, ~150 MB)
Backend API (/api/matters/{matter_id}/documents/upload)
  ↓ Generate doc_id, create database record
Supabase Storage
  ↓ Store: documents/{matter_id}/{doc_id}/original.pdf
  ↓ Return: file_path (signed URL)
Database
  ↓ INSERT INTO documents (doc_id, matter_id, filename, file_path, ocr_status='pending')

┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: OCR Processing (30-45 seconds)                          │
└─────────────────────────────────────────────────────────────────┘

Backend (Celery background task)
  ↓ Fetch PDF from Supabase Storage
Google Document AI API
  ↓ POST /v1/projects/{PROJECT}/locations/{LOCATION}/processors/{PROCESSOR_ID}:process
  ↓ Returns: OCR text + bounding boxes for each word/line/block
Backend
  ↓ Parse response
  ↓ For each page:
      - Extract full OCR text
      - Extract bounding boxes (normalized coordinates)
      - Calculate OCR confidence score
Database
  ↓ INSERT INTO pages (doc_id, page_number, ocr_text, ocr_confidence, width, height)
  ↓ INSERT INTO bounding_boxes (page_id, x, y, width, height, text, confidence)
  ↓ UPDATE documents SET ocr_status='completed', ocr_confidence_avg=X

WebSocket
  ↓ Emit progress update to frontend: "OCR: 45% complete (900/2000 pages)"

┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Chunking (Parent-Child) (10 seconds)                    │
└─────────────────────────────────────────────────────────────────┘

Backend (Chunking Service)
  ↓ Retrieve: Full OCR text from pages table
  ↓ Chunk algorithm:
      - Parent chunks: 1500-2000 tokens (preserve section structure)
      - Child chunks: 400-700 tokens (50-100 token overlap)
      - Preserve page boundaries in metadata
  ↓ For each chunk:
      - Calculate token count
      - Link to bounding_boxes (which bboxes are in this chunk?)
      - Store parent-child relationships
Database
  ↓ INSERT INTO chunks (matter_id, doc_id, chunk_type, parent_chunk_id, content,
                        token_count, page_start, page_end, bbox_ids, embedding=NULL)

Result:
  - Parent chunks: ~1000 (2000 pages / 2 pages per parent)
  - Child chunks: ~3000 (each parent → 3 children average)

┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Embedding Generation (15-20 seconds)                    │
└─────────────────────────────────────────────────────────────────┘

Backend (Embedding Service)
  ↓ Fetch: All chunks (parents + children) - 4000 chunks
  ↓ Batch API calls to OpenAI (100 chunks per request):
OpenAI API (text-embedding-ada-002)
  ↓ POST /v1/embeddings
  ↓ Input: chunk.content (up to 8191 tokens)
  ↓ Returns: 1536-dimensional vector per chunk
Backend
  ↓ Update database:
Database
  ↓ UPDATE chunks SET embedding = {vector} WHERE chunk_id = X

Cost: 4000 chunks × ~500 tokens avg = 2M tokens = $0.50

┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Entity Extraction (20-30 seconds)                       │
└─────────────────────────────────────────────────────────────────┘

Backend (NER Service)
  ↓ Fetch: All OCR text (concatenated by page)
  ↓ Run NER (spaCy or GPT-3.5-turbo):
      - Extract: PERSON, ORG, DATE, MONEY, LOCATION entities
      - For each entity:
          - Record: canonical_name, entity_type, first_mention
          - Detect aliases using fuzzy matching
          - Link to bounding_boxes for visual references
Database
  ↓ INSERT INTO entities (matter_id, entity_type, canonical_name, aliases,
                          first_mention_doc, first_mention_page, first_mention_bbox)
  ↓ INSERT INTO entity_mentions (entity_id, doc_id, page_id, bbox_id, mention_text, confidence)

Result: ~200-500 entities extracted (depending on case complexity)

┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Timeline Extraction (10-15 seconds)                     │
└─────────────────────────────────────────────────────────────────┘

Backend (Timeline Service)
  ↓ Fetch: All chunks with DATE entities
  ↓ For each date mention:
      - Extract: event description (surrounding context)
      - Classify: event_type (filing, order, hearing, transaction, notice)
      - Link: actor (entity_id), document, bbox
      - Confidence scoring
Database
  ↓ INSERT INTO timeline_events (matter_id, event_date, event_text, event_type,
                                  actor_entity_id, doc_id, page_id, bbox_id, confidence)

Result: ~50-200 timeline events

┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Summary Generation (15-20 seconds)                      │
└─────────────────────────────────────────────────────────────────┘

Backend (Summary Service)
  ↓ Fetch: Most important chunks (hybrid search for "case overview")
  ↓ Enrich with: Timeline events, entities, last order
  ↓ Call GPT-4:
OpenAI API (GPT-4)
  ↓ POST /v1/chat/completions
  ↓ Prompt: "Generate one-page executive summary covering: parties, subject,
             status, timeline, key issues. Cite sources."
  ↓ Returns: Structured summary (JSON or Markdown)
Backend
  ↓ Parse summary
  ↓ Store in database or cache (Redis)
Database/Redis
  ↓ SET cache:summary:{matter_id} = {summary_json} EX 3600

Cost: ~1000 tokens input + 500 tokens output = $0.03

┌─────────────────────────────────────────────────────────────────┐
│ TOTAL INGESTION TIME: ~90-120 seconds (1.5-2 minutes)           │
│ TOTAL COST: $60-90 (OCR) + $0.50 (embeddings) + $0.03 (summary) │
│           ≈ $60-91 per 2000-page matter                          │
└─────────────────────────────────────────────────────────────────┘

Frontend
  ↓ WebSocket receives: "Processing complete! View your case summary."
  ↓ Redirect user to: /matters/{matter_id}/dashboard
```

---

### Flow 2: Natural Language Query (Q&A)

**User Action:** Ask "Where is the property attachment order?"

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Query Submission (instant)                              │
└─────────────────────────────────────────────────────────────────┘

User (Frontend)
  ↓ Type query: "Where is the property attachment order?"
  ↓ Submit
Backend API (/api/matters/{matter_id}/query)
  ↓ Validate: matter_id, user permissions (RLS check)
  ↓ Log query for analytics

┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Cache Check (5ms)                                       │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ Generate query hash: SHA256("where is the property attachment order")
Redis
  ↓ GET cache:query:{matter_id}:{query_hash}
  ↓ If HIT → Return cached result (skip to Step 7)
  ↓ If MISS → Continue to retrieval

┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Query Embedding (200ms)                                 │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ Call OpenAI Embeddings API:
OpenAI API (text-embedding-ada-002)
  ↓ Input: "Where is the property attachment order?"
  ↓ Returns: 1536-dimensional query vector

┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Hybrid Search (BM25 + Vector) (100-200ms)               │
└─────────────────────────────────────────────────────────────────┘

Backend (Search Service)
  ↓ Parallel execution:

  ┌─────────────────────────┐  ┌─────────────────────────┐
  │   BM25 Search           │  │   Vector Search         │
  │   (Keyword matching)    │  │   (Semantic similarity) │
  └─────────────────────────┘  └─────────────────────────┘
            ↓                              ↓
  Query: "property attachment order"    Query vector (1536d)
            ↓                              ↓
  Database (tsvector full-text search):  Database (pgvector HNSW index):
            ↓                              ↓
  SELECT chunk_id, content,              SELECT chunk_id, content,
    ts_rank(to_tsvector(content),          1 - (embedding <=> query_vec) AS similarity
            query) AS score              FROM chunks
  FROM chunks                            WHERE matter_id = {matter_id}
  WHERE matter_id = {matter_id}            AND chunk_type = 'child'
    AND chunk_type = 'child'             ORDER BY embedding <=> query_vec
    AND to_tsvector(content)             LIMIT 20
      @@ query
  ORDER BY score DESC
  LIMIT 20
            ↓                              ↓
  Returns: Top 20 chunks                 Returns: Top 20 chunks
            ↓                              ↓
            └──────────────┬───────────────┘
                           ↓
                   Merge & Deduplicate
                           ↓
                 Combined Top 20 chunks

┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Reranking (Cohere) (150-300ms)                          │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ Call Cohere Rerank API:
Cohere API (rerank-english-v3.0)
  ↓ POST /v1/rerank
  ↓ Input:
      - query: "Where is the property attachment order?"
      - documents: [chunk1.content, chunk2.content, ..., chunk20.content]
      - top_n: 3
  ↓ Returns: Top 3 most relevant chunks (with relevance scores)

Result:
  - Chunk #47 (relevance: 0.95) - Contains "Special Court order dated..."
  - Chunk #89 (relevance: 0.87) - Contains "property attachment Section 3(3)..."
  - Chunk #102 (relevance: 0.81) - Contains "Custodian directed to attach..."

┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Context Enrichment (Parent Chunks) (50ms)               │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ For each retrieved child chunk, fetch parent chunk:
Database
  ↓ SELECT content, page_start, page_end, bbox_ids
    FROM chunks
    WHERE chunk_id IN (
      SELECT parent_chunk_id FROM chunks WHERE chunk_id IN ({child_chunk_ids})
    )
  ↓ Returns: 3 parent chunks (1500-2000 tokens each)

Why? Child chunks are small (400-700 tokens) for precise retrieval,
     but parent chunks give LLM full context to avoid fragmentation.

┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Answer Generation (GPT-4) (2-4 seconds)                 │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ Construct prompt:

  SYSTEM_PROMPT = """
  You are a legal document analyst. Answer the user's question based
  ONLY on the provided context from case documents.

  Rules:
  - Cite document ID, page number, and bbox_id for every claim
  - If answer not in context, say "Not found in provided documents"
  - Provide confidence: High (95%+), Medium (70-95%), Low (<70%)
  - Use neutral, factual language
  - Do not make legal conclusions
  """

  USER_PROMPT = f"""
  Question: {user_query}

  Context (from case documents):

  [Parent Chunk 1 - Doc 47, Pages 88-90]
  {parent_chunk_1_content}

  [Parent Chunk 2 - Doc 51, Pages 11-13]
  {parent_chunk_2_content}

  [Parent Chunk 3 - Doc 89, Pages 45-47]
  {parent_chunk_3_content}

  Answer the question with citations.
  """

OpenAI API (GPT-4)
  ↓ POST /v1/chat/completions
  ↓ Model: gpt-4
  ↓ Temperature: 0.1 (low for consistency)
  ↓ max_tokens: 500
  ↓ Returns:

  {
    "answer": "The property attachment order was issued by the Special Court
               on June 10, 2018, directing the Custodian to attach all movable
               and immovable property belonging to Nirav D. Jobalia under
               Section 3(3) of the Securities Act 1992.",
    "citations": [
      {"doc_id": "doc-47", "page": 89, "bbox_id": "bbox-1245"},
      {"doc_id": "doc-51", "page": 12, "bbox_id": "bbox-3456"}
    ],
    "confidence": "High",
    "confidence_score": 0.98
  }

┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Citation Linking (Bounding Boxes) (20ms)                │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ For each citation, fetch bounding box details:
Database
  ↓ SELECT bb.x, bb.y, bb.width, bb.height, bb.text, p.page_number, d.file_path
    FROM bounding_boxes bb
    JOIN pages p ON bb.page_id = p.page_id
    JOIN documents d ON p.doc_id = d.doc_id
    WHERE bb.bbox_id IN ({bbox_ids})
  ↓ Returns: Coordinates + file paths for PDF rendering

┌─────────────────────────────────────────────────────────────────┐
│ STEP 9: Cache Result (5ms)                                      │
└─────────────────────────────────────────────────────────────────┘

Redis
  ↓ SET cache:query:{matter_id}:{query_hash} = {result_json} EX 3600
  ↓ TTL: 1 hour (next identical query = instant response)

┌─────────────────────────────────────────────────────────────────┐
│ STEP 10: Return to Frontend (10ms)                              │
└─────────────────────────────────────────────────────────────────┘

Backend API
  ↓ Format response:
  {
    "query": "Where is the property attachment order?",
    "answer": "The property attachment order was issued...",
    "citations": [
      {
        "doc_id": "doc-47",
        "page": 89,
        "bbox": {"x": 0.15, "y": 0.42, "width": 0.65, "height": 0.08},
        "text": "...Special Court order dated June 10, 2018...",
        "file_url": "https://storage.supabase.co/..."
      },
      {...}
    ],
    "confidence": "High (98%)",
    "processing_time_ms": 3250
  }

Frontend (Next.js 16)
  ↓ Render answer with inline citation links
  ↓ User clicks citation [View Highlight]
  ↓ Open PDF viewer:
      - Load PDF from file_url
      - Navigate to page 89
      - Draw yellow rectangle at bbox coordinates
      - Highlight text

┌─────────────────────────────────────────────────────────────────┐
│ TOTAL QUERY TIME: ~3-5 seconds (first time)                     │
│                    ~10ms (cached)                                 │
│ COST PER QUERY: $0.02 (GPT-4) + $0.10 (Cohere) = $0.12          │
└─────────────────────────────────────────────────────────────────┘
```

---

### Flow 3: Citation Verification

**User Action:** Click "Verify Citations" or system auto-runs during ingestion

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Citation Pattern Recognition (2-3 seconds)              │
└─────────────────────────────────────────────────────────────────┘

Backend (Citation Service)
  ↓ Fetch: All OCR text from case documents
  ↓ Run regex patterns:
      - Pattern 1: r"Section (\d+)(\((\d+)\))?"  → "Section 3(2)"
      - Pattern 2: r"S\. (\d+)"                  → "S. 3"
      - Pattern 3: r"Section (\d+) subsection (\d+)" → "Section 3 subsection 2"
  ↓ For each match:
      - Extract: act_name (inferred from context or manually tagged)
      - Extract: section_number, subsection
      - Extract: cited_text (surrounding context ±200 chars)
      - Record: doc_id, page, bbox_id

Result: ~50-200 citations extracted (depending on case type)

┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Fetch Actual Act Text (50ms)                            │
└─────────────────────────────────────────────────────────────────┘

Database (Acts table)
  ↓ For each citation:
  SELECT full_text, provisos, exceptions
  FROM acts
  WHERE act_name = 'Securities Act 1992'
    AND section_number = '3'
    AND subsection = '2'
  ↓ Returns: Actual statute text

Example:
  full_text = "The Custodian may, on being satisfied on information
               received that any person has been involved in any offence
               relating to transactions in securities after the 1st day
               of April, 1991 and on and before 6th June, 1992, notify
               the name of such person in the Official Gazette."

  provisos = ["Provided that no contract or agreement shall be cancelled
               except after giving to the parties to the contract or
               agreement a reasonable opportunity of being heard."]

┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Text Comparison & Similarity Scoring (1-2 seconds)      │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ For each citation:

  cited_text = "Section 3(2) allows property attachment without notice"
  actual_text = [full_text from database]

  ↓ Compute similarity:
      - Levenshtein distance (character-level edits)
      - Semantic similarity (embeddings)
      - Keyword overlap

  ↓ Check for omissions:
      - Are provisos mentioned in cited_text?
      - Are exceptions acknowledged?

  ↓ Classify result:
      - similarity_score ≥ 90% → "verified"
      - similarity_score 70-89% → "partial match" (flag for review)
      - similarity_score < 70% → "mismatch"
      - provisos omitted → "incomplete citation"

┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Store Verification Results (100ms)                      │
└─────────────────────────────────────────────────────────────────┘

Database
  ↓ INSERT INTO citations (
      matter_id, doc_id, page_id, bbox_id, act_name, section_number,
      cited_text, verification_status, similarity_score
    ) VALUES (...)
  ↓ Or UPDATE if citation already exists

┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Generate Verification Report (500ms)                    │
└─────────────────────────────────────────────────────────────────┘

Backend
  ↓ Aggregate results:
      - Total citations: 87
      - Verified: 65 (75%)
      - Mismatches: 12 (14%)
      - Incomplete: 10 (11%)

  ↓ For each mismatch/incomplete, generate comparison:

Frontend Display:
  ┌────────────────────────────────────────────────────────┐
  │ Citation Verification Report                           │
  ├────────────────────────────────────────────────────────┤
  │ ✅ 65 citations verified (75%)                         │
  │ ⚠️  12 mismatches found (14%) - Review required        │
  │ ⚠️  10 incomplete citations (11%) - Provisos omitted   │
  └────────────────────────────────────────────────────────┘

  ⚠️  Mismatch #1:
  ┌────────────────────────────────────────────────────────┐
  │ Document 45, Page 12 [View Highlight]                 │
  │                                                        │
  │ Claimed:                                               │
  │ "Section 3(2) allows property attachment without      │
  │  notice"                                               │
  │                                                        │
  │ Actual (Securities Act 1992, Section 3(2)):           │
  │ "...on being satisfied on information received that   │
  │  any person has been involved in any offence...       │
  │  shall stand attached simultaneously with the issue    │
  │  of the notification"                                  │
  │                                                        │
  │ ❌ Missing: "on being satisfied on information"       │
  │ ⚠️  Proviso omitted: Notification required            │
  │                                                        │
  │ Similarity: 68% (🟡 Medium confidence)                │
  └────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TOTAL VERIFICATION TIME: ~5-10 seconds for 87 citations         │
│ COST: $0 (regex + database lookups only)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Anti-Hallucination Strategy

### Layered Defense System

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 1: RETRIEVAL                            │
│  Ensure LLM receives high-quality, relevant context              │
└─────────────────────────────────────────────────────────────────┘

1. Hybrid Search (BM25 + Vector)
   - BM25: Exact keyword matching (can't hallucinate "Section 3(2)")
   - Vector: Semantic similarity for conceptual matches
   - Combination: Precision + Recall

2. Reranking (Cohere Rerank v3)
   - Re-score retrieved chunks for relevance
   - 40-70% precision improvement
   - Ensures LLM gets BEST context, not just good-enough

3. Parent-Child Chunking
   - Retrieve: Small child chunks (precision)
   - Feed LLM: Large parent chunks (context completeness)
   - Prevents: Context fragmentation leading to hallucination

┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 2: GENERATION                           │
│  Control LLM behavior to minimize hallucination                  │
└─────────────────────────────────────────────────────────────────┘

4. LLM Selection
   - Primary: GPT-4 (58% hallucination rate - lowest)
   - ❌ Never: Gemini 3 Flash (91% hallucination rate)
   - Secondary: GPT-3.5-turbo (simple extraction tasks only)

5. Structured Prompts with Constraints
   System prompt:
   """
   CRITICAL RULES:
   - Answer ONLY based on provided context
   - If answer not in context, respond: "Not found in documents"
   - NEVER infer, assume, or guess information
   - Cite document ID, page number, bbox_id for EVERY claim
   - If uncertain, say "Low confidence" and explain why
   """

6. Low Temperature (0.1)
   - Reduces randomness in generation
   - More consistent, deterministic outputs
   - Lower hallucination risk

7. Citation Requirement
   - Every finding MUST include:
     - Document ID
     - Page number
     - Bounding box ID
   - No citation = No finding (rejected)

┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 3: VERIFICATION                         │
│  Validate LLM outputs against source documents                  │
└─────────────────────────────────────────────────────────────────┘

8. Bounding Box Validation
   - LLM claims: "Document 47, Page 89, bbox-1245 says X"
   - System checks: Does bbox-1245 actually contain text X?
   - Validation query:
     SELECT text FROM bounding_boxes WHERE bbox_id = 'bbox-1245'
   - If mismatch → Reject finding, log error

9. Confidence Scoring
   - Retrieval confidence (cosine similarity scores)
   - LLM self-assessment ("I'm 95% confident...")
   - OCR quality (avg OCR confidence for cited bboxes)
   - Combined score: High (95%+), Medium (70-95%), Low (<70%)

10. Citation Verification Engine
    - For statutory citations: Compare vs bare act text
    - Similarity scoring
    - Detect omissions (provisos, exceptions)
    - Flag misquotations

┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 4: USER INTERFACE                       │
│  Enable human verification of LLM claims                         │
└─────────────────────────────────────────────────────────────────┘

11. Visual Verification (THE KILLER FEATURE)
    - User clicks citation link
    - PDF opens with exact text highlighted
    - User SEES if LLM is telling the truth
    - Instant hallucination detection by user

12. Confidence Indicators
    - Color coding: 🟢 High, 🟡 Medium, 🔴 Low
    - Explicit warnings: "This finding has medium confidence - verify before using"
    - Tooltip: "Based on OCR confidence 72%, semantic similarity 85%"

13. Source Transparency
    - Always show: Which documents, pages, bboxes were used
    - Link to original sources (PDFs)
    - Enable lawyer to trace reasoning chain

┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 5: MONITORING                           │
│  Track and learn from hallucinations                             │
└─────────────────────────────────────────────────────────────────┘

14. Error Logging
    - Log all low-confidence findings
    - Log validation failures (bbox mismatch)
    - Track user feedback ("This finding is incorrect")

15. A/B Testing
    - Test different prompts, temperatures, models
    - Measure: Accuracy, hallucination rate, user trust

16. Human Feedback Loop
    - Lawyer marks finding as "incorrect"
    - System learns: Improve prompts, adjust confidence thresholds
```

### Anti-Hallucination Metrics

**Target Metrics for MVP:**
- ✅ Citation accuracy: 95%+ (findings must trace to actual document text)
- ✅ Hallucination rate: <10% (compared to GPT-4 baseline 58%)
- ✅ User trust: 8/10 satisfaction ("I trust the findings")

**How to measure:**
- Manual validation on test set (20 cases, 100 queries)
- Compare LLM findings vs ground truth (lawyer-verified)
- User feedback: "Was this finding accurate?"

---

## 4-Month MVP Roadmap

### Month 1: Foundation + Smart Ingestion

#### Week 1-2: Infrastructure Setup

**Tasks:**
1. Set up development environment
   - Initialize Git repository
   - Configure Python virtual environment (Python 3.11+)
   - Set up pre-commit hooks (black, flake8, mypy)

2. Provision cloud services
   - Create Supabase project (PostgreSQL + Storage)
   - Configure Google Cloud project for Document AI
   - Set up Redis instance (Upstash or Redis Cloud)
   - Create OpenAI API account
   - Create Cohere API account

3. Database schema implementation
   - Execute SQL migrations (tables, indexes, RLS policies)
   - Seed data: Test acts (Securities Act 1992)
   - Create database backup strategy

4. Backend scaffolding
   - Initialize FastAPI project
   - Configure Pydantic models for type safety
   - Set up structured logging (Structlog)
   - Implement JWT authentication (Supabase Auth)
   - Create API documentation (OpenAPI/Swagger)

5. CI/CD pipeline
   - GitHub Actions workflows (test, lint, deploy)
   - Environment variables management (secrets)
   - Automated testing setup (Pytest)

**Deliverable:**
- ✅ Backend API running locally
- ✅ Database schema deployed
- ✅ CI/CD pipeline functional
- ✅ API documentation auto-generated

---

#### Week 3-4: OCR & Chunking

**Tasks:**
1. Google Document AI integration
   - Implement PDF upload handler
   - Call Document AI API (batch processing)
   - Parse response: Extract OCR text + bounding boxes
   - Handle errors: Low-quality scans, unsupported formats

2. Bounding box storage
   - Store normalized coordinates (0-1 range)
   - Link bboxes to pages, chunks
   - Create bbox retrieval API

3. Parent-child chunking implementation
   - Chunking algorithm:
     - Parent: 1500-2000 tokens (tiktoken library)
     - Child: 400-700 tokens with 50-100 overlap
   - Preserve page boundaries
   - Link chunks to bounding boxes

4. Quality scoring
   - OCR confidence per page
   - OCR confidence per bbox
   - Overall document quality score
   - Quality-based routing (future: <50% = manual review)

5. Background task processing
   - Celery setup for async OCR
   - WebSocket for progress updates
   - Job queue monitoring

**Deliverable:**
- ✅ Upload 2000-page PDF
- ✅ OCR processed with bounding boxes stored
- ✅ Parent-child chunks created
- ✅ Processing time: <2 minutes

**Test:**
- Upload Securities Act case (test file)
- Verify: All bounding boxes stored correctly
- Spot check: Random bbox ID → Correct text retrieved

---

### Month 2: Core Intelligence (Search + Entities + Timeline)

#### Week 5-6: RAG Foundation

**Tasks:**
1. Embedding generation
   - OpenAI text-embedding-ada-002 integration
   - Batch processing (100 chunks per API call)
   - Store embeddings in pgvector column
   - Create HNSW index for fast ANN search

2. Hybrid search implementation
   - **BM25 (Full-text search):**
     - PostgreSQL tsvector + tsquery
     - Rank results by tf-idf relevance
   - **Vector search:**
     - Cosine similarity using pgvector
     - HNSW index for speed
   - **Merge algorithm:**
     - Reciprocal Rank Fusion (RRF)
     - Combine BM25 + Vector scores

3. Cohere Rerank integration
   - API client implementation
   - Rerank top 20 → return top 3
   - Error handling (API downtime fallback)

4. Confidence scoring algorithm
   - Retrieval score (BM25 + Vector + Rerank)
   - OCR quality score (avg confidence of cited bboxes)
   - LLM certainty (parse from GPT-4 response)
   - Combined formula: `weighted_average(retrieval, ocr, llm)`

**Deliverable:**
- ✅ Hybrid search working
- ✅ Query: "property attachment" → Relevant chunks retrieved
- ✅ Reranking improves precision (measure before/after)
- ✅ Confidence scores assigned to all results

**Test:**
- Run 10 test queries
- Measure: Precision@3 (are top 3 results relevant?)
- Compare: With/without reranking

---

#### Week 7-8: Entity Extraction + Timeline

**Tasks:**
1. NER (Named Entity Recognition)
   - Library: spaCy (en_core_web_lg) or GPT-3.5-turbo
   - Extract: PERSON, ORG, DATE, MONEY, LOCATION
   - Store entities with first mention

2. Alias resolution
   - Fuzzy matching algorithm:
     - Edit distance (Levenshtein)
     - Phonetic similarity (Metaphone)
     - Context analysis (same paragraph = likely same entity)
   - Merge entities: "Nirav D. Jobalia" = "N.D. Jobalia"
   - Manual override UI (lawyer can confirm/reject merges)

3. Entity linking to bounding boxes
   - For each entity mention, find corresponding bbox
   - Store: entity_mentions table with bbox_id

4. Timeline extraction
   - Extract dates using regex + NER
   - Extract events (context around date mentions)
   - Classify event types: filing, order, hearing, transaction, notice
   - Link events to actors (entities)

5. Timeline visualization data structure
   - JSON format:
     ```json
     {
       "events": [
         {
           "date": "2018-05-05",
           "event": "Dematerialisation request filed",
           "actor": "Nirav D. Jobalia",
           "doc": "doc-14",
           "page": 23,
           "bbox": "bbox-145"
         }
       ]
     }
     ```

**Deliverable:**
- ✅ Entities extracted from 2000-page case
- ✅ Aliases resolved (e.g., 5 variations → 1 canonical entity)
- ✅ Timeline built with 50-200 events
- ✅ API endpoints: GET /matters/{id}/entities, GET /matters/{id}/timeline

**Test:**
- Verify entity count (should be 200-500 for complex case)
- Spot check aliases (manually verify 10 merges are correct)
- Timeline completeness (compare vs manual timeline)

---

### Month 3: Citation Verification + Contradictions + Summary

#### Week 9-10: Citation Verification Engine

**Tasks:**
1. Act ingestion system
   - Ingest Securities Act 1992 PDF
   - Parse structure: Section → Subsection → Text → Provisos → Exceptions
   - Store in `acts` table
   - Make generic: Ingest ANY bare act

2. Citation pattern recognition
   - Regex library for legal citations
   - Patterns: "Section X", "S. X", "Section X(Y)", etc.
   - Extract: act_name, section, subsection, cited_text

3. Text comparison engine
   - Levenshtein distance
   - Semantic similarity (embeddings)
   - Detect omissions (provisos not mentioned)

4. Verification report generation
   - For each citation:
     - verified / mismatch / incomplete
     - Similarity score
     - Missing text (provisos, exceptions)
   - Side-by-side display UI

**Deliverable:**
- ✅ 87 citations extracted from case
- ✅ 65 verified, 12 mismatches, 10 incomplete
- ✅ Report with side-by-side comparisons
- ✅ Click citation → PDF highlight + Act text comparison

**Test:**
- Manually verify 10 citations (ground truth)
- Measure: Precision (% correct verifications)
- False positives: Citations flagged as mismatch but actually correct

---

#### Week 11-12: Contradiction Detection + Summary

**Tasks:**
1. Claim extraction
   - Pattern matching: "X states that Y", "According to X, Y"
   - Store claims with entity attribution

2. Semantic comparison
   - Group claims by same entity
   - Embedding similarity (cosine > 0.8)
   - LLM-based contradiction detection:
     - Prompt: "Are these two claims contradictory?"
     - Response: Yes/No/Uncertain + Explanation

3. Confidence scoring for contradictions
   - High (>90%): Date conflicts, amount conflicts, Yes/No conflicts
   - Medium (70-90%): Semantic contradictions
   - Low (<70%): Potentially contradictory, unclear

4. Executive summary generation
   - GPT-4 structured prompt
   - Inputs: Top chunks, timeline, entities, last order
   - Output format:
     ```markdown
     # Executive Summary
     **Parties:** ...
     **Subject Matter:** ...
     **Last Order:** ...
     **Status:** ...
     **Key Issues:** ...
     **Next Steps:** ...
     ```
   - Store in cache (Redis, TTL: 1 hour)

**Deliverable:**
- ✅ Contradictions detected (3-10 per case average)
- ✅ Executive summary generated (<20 seconds)
- ✅ Summary quality: Manually reviewed by lawyer (8/10 rating)
- ✅ API endpoints: GET /matters/{id}/contradictions, GET /matters/{id}/summary

**Test:**
- Plant intentional contradictions in test case
- Measure: Detection rate (should catch 80%+ of contradictions)
- False positives: Claims flagged as contradictory but actually compatible

---

### Month 4: Frontend + Visual Layer + Pilot

#### Week 13-14: PDF Viewer with Highlights

**Tasks:**
1. PDF.js integration
   - Client-side PDF rendering
   - Load PDF from Supabase Storage (signed URL)
   - Handle large PDFs (2000 pages = lazy loading)

2. Bounding box overlay system
   - SVG layer on top of PDF canvas
   - Convert bbox coordinates (normalized 0-1) → pixel coordinates
   - Draw yellow rectangle highlights
   - Multi-highlight support (multiple bboxes on same page)

3. Navigation & interaction
   - Click citation → Open PDF to page X
   - Scroll to bbox, draw highlight
   - Zoom controls (zoom in/out, fit to width)
   - Pan (drag to move around page)
   - Search within PDF (Ctrl+F)

4. Performance optimization
   - Lazy load pages (only render visible pages)
   - Canvas caching
   - Debounced highlight rendering

**Deliverable:**
- ✅ PDF viewer functional
- ✅ Click "View Highlight" → PDF opens to exact location
- ✅ Yellow highlight appears on correct text
- ✅ Smooth performance (60fps rendering)

**Test:**
- Load 2000-page PDF
- Navigate to page 500, page 1500, page 2000 (speed test)
- Click 10 random citations → Verify highlights are accurate

---

#### Week 15: Next.js 16 Frontend Integration

**Tasks:**
1. Dashboard page
   - Matter overview card (summary, statistics)
   - Quick actions: Upload document, Ask question
   - Recent queries list

2. Timeline view
   - Horizontal timeline visualization (D3.js or similar)
   - Event markers with tooltips
   - Click event → Open PDF with highlight
   - Filter by: Date range, Event type, Actor

3. Entity graph view
   - Network diagram (Vis.js or D3.js force-directed graph)
   - Nodes: Entities (sized by mention count)
   - Edges: Relationships
   - Click node → See all mentions
   - Click edge → See relationship evidence

4. Citation verification tab
   - List of citations (verified / mismatch / incomplete)
   - Side-by-side comparison view
   - Filter: Show only mismatches

5. Contradictions tab
   - List of contradictions with confidence scores
   - Click contradiction → Side-by-side view with PDF highlights

6. Q&A interface
   - Search bar (natural language)
   - Results with inline citations
   - Click citation → PDF highlight
   - Confidence indicator (🟢🟡🔴)

7. Settings
   - User profile
   - Matter management (archive, delete)
   - API usage dashboard

**Deliverable:**
- ✅ Full frontend deployed (Vercel)
- ✅ All 7 core features accessible via UI
- ✅ Responsive design (works on tablet, desktop)
- ✅ Fast load times (<2s initial page load)

**Test:**
- User acceptance testing (5 lawyers)
- Collect feedback on UI/UX
- Measure: Task completion time ("Find property attachment order")

---

#### Week 16: Testing + Pilot Launch

**Tasks:**
1. Test suite (20 real cases)
   - Source: Public court records, sample legal documents
   - Size mix: 500 pages, 1000 pages, 2000 pages
   - Complexity mix: Simple (1 party), Complex (multi-party fraud)

2. Accuracy validation
   - Manual ground truth (lawyer creates answer key)
   - Compare: LDIP findings vs ground truth
   - Measure:
     - Citation accuracy (%)
     - Timeline completeness (%)
     - Entity resolution accuracy (%)
     - Contradiction detection rate (%)
     - Summary quality (1-10 rating)

3. Performance testing
   - Load testing (10 concurrent users)
   - Stress testing (upload 5 cases simultaneously)
   - Latency measurement (all API endpoints)

4. Security testing
   - Penetration testing (matter isolation)
   - Attempt cross-matter data access (should fail)
   - SQL injection, XSS testing
   - Authentication bypass attempts

5. Pilot program setup
   - Recruit 3-5 law firms
   - Onboarding: Training session (1 hour)
   - Provide: 10 cases each to process
   - Collect feedback:
     - Survey: 10 questions (satisfaction, trust, usefulness)
     - Interviews: 30-min calls with 5 lawyers
     - Usage analytics: Which features used most?

6. Documentation
   - User guide (PDF + video tutorials)
   - API documentation (OpenAPI)
   - Developer setup guide
   - Troubleshooting FAQ

**Deliverable:**
- ✅ Test suite passes (90%+ accuracy)
- ✅ Performance targets met (<5 min processing, <5s queries)
   - Security audit clean (no critical vulnerabilities)
- ✅ Pilot: 50+ cases processed across 3-5 firms
- ✅ Feedback collected (satisfaction score, feature requests)

**Success Criteria:**
- 8/10 lawyer satisfaction score
- 75%+ accuracy on test suite
- At least 3 lawyers willing to provide domain knowledge for Phase 2
- Zero critical security issues

---

## Success Metrics

### Technical Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Processing Time** | <5 min for 2000-page case | Avg time from upload → summary ready |
| **Query Latency** | <5 sec (first time), <1 sec (cached) | Avg API response time for Q&A |
| **Citation Accuracy** | 95%+ | Manual validation: LLM claim matches actual document text |
| **Hallucination Rate** | <10% | % of findings that cannot be traced to source documents |
| **OCR Quality** | 90%+ avg confidence | Avg confidence score from Document AI across all pages |
| **Timeline Completeness** | 80%+ events captured | Compare extracted timeline vs manual lawyer-created timeline |
| **Entity Resolution Accuracy** | 85%+ | % of alias merges that are correct |
| **Matter Isolation** | 100% (zero breaches) | Penetration testing: Attempt cross-matter access |
| **Uptime** | 99.5% | Monthly uptime monitoring |

---

### Business Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Law Firms Onboarded** | 3-5 firms | Count of pilot participants |
| **Cases Processed** | 50+ cases | Total matters uploaded during pilot |
| **User Satisfaction** | 8/10 rating | Post-pilot survey (10 questions) |
| **Time Saved** | 4.8-7.2 hours per case | User survey: "How much time did LDIP save you?" |
| **Cost per Case** | $75-110 | Track: OCR + API costs per matter |
| **ROI** | 78-91% cost reduction | Compare: LDIP cost vs junior lawyer time ($400-900) |
| **Lawyer Trust** | 8/10 rating | Survey: "Do you trust LDIP's findings?" (1-10 scale) |
| **Feature Usage** | Visual highlights used 80%+ | Analytics: % of users who click "View Highlight" |
| **Repeat Usage** | 70%+ lawyers use LDIP for 2nd case | Track: Users who upload >1 case |
| **Domain Knowledge Volunteers** | 5+ lawyers | Count: Lawyers willing to help with process templates |

---

### User Feedback Questions (Post-Pilot Survey)

1. **Overall Satisfaction:** How satisfied are you with LDIP? (1-10)
2. **Time Savings:** Approximately how much time did LDIP save you on case orientation?
3. **Trust:** How much do you trust LDIP's findings? (1-10)
4. **Accuracy:** Were the citations and findings accurate? (1-10)
5. **Visual Highlights:** Did the PDF highlight feature help you verify findings? (Yes/No)
6. **Summary Quality:** Was the executive summary useful? (1-10)
7. **Timeline:** Did the timeline visualization help you understand the case? (Yes/No)
8. **Ease of Use:** How easy was LDIP to use? (1-10)
9. **Would Recommend:** Would you recommend LDIP to a colleague? (Yes/No)
10. **Feature Requests:** What additional features would you like to see?

**Follow-up:**
- 30-min interviews with 5 lawyers (deep dive into pain points, feature requests)
- Usage analytics: Which features are used most? Least?

---

## Future Phases (Post-MVP)

### Phase 2: Advanced Engines + Domain Knowledge (Months 5-7)

**Goal:** Add domain-specific intelligence that requires legal expertise

**Prerequisites:**
- MVP proven successful (8/10 satisfaction, 50+ cases processed)
- 5+ lawyers willing to provide domain knowledge
- Budget: $210k

#### Features:

**1. Documentation Gap Engine**

**Capability:** "You're missing Form 10A which is required for dematerialisation under SEBI regulations"

**How it works:**
- Lawyers provide: Process templates for different case types
  - Securities fraud cases require: Chargesheet, FIR, Custodian notification, Property attachment order, Demat records
  - Tax cases require: Returns, Notices, Appeals, Assessment orders
- System stores: `required_documents(case_type, document_type, is_mandatory, legal_basis)`
- Engine checks: Which required documents are present vs missing
- Output: "Missing: Form 10A (mandatory under Regulation 76)"

**Development time:** 4 weeks (2 weeks requirements gathering, 2 weeks implementation)

**Cost:** $0 per query (rule-based checking)

---

**2. Process Chain Integrity Engine**

**Capability:** "Dematerialisation sequence is out of order - Step 3 happened before Step 2"

**How it works:**
- Lawyers provide: Process sequences (flowcharts)
  - Dematerialisation: Request → Acknowledgment → Verification → Execution → Confirmation
  - Appeals: Notice → Filing → Hearing → Order
- System stores: `process_chains(process_name, steps[], dependencies[], typical_duration)`
- Engine analyzes: Timeline events against expected sequence
- Output: "Alert: Share sale (Step 5) occurred before demat verification (Step 3)"

**Development time:** 6 weeks (3 weeks requirements, 3 weeks implementation + testing)

**Cost:** $0 per query (rule-based analysis)

---

**3. Deadline & Compliance Tracker**

**Capability:** "Appeal filed 45 days after order - violated 30-day deadline under Section 10"

**How it works:**
- Lawyers provide: Deadline rules from various Acts
  - Securities Act, Section 10: Appeal within 30 days
  - Income Tax Act, Section 249: Appeal within 60 days
- System stores: `deadlines(act_name, section, deadline_days, triggering_event)`
- Engine tracks: Timeline events + calculates elapsed time
- Output: "⚠️ Deadline violation: Appeal filed 45 days after order (required: 30 days)"

**Development time:** 3 weeks

**Cost:** $0 per query

---

**4. Bounded Agentic Reasoning (for Pattern Detection)**

**Capability:** "Detected potential hidden connection: Nirav introduced Payal, Payal is witness for Custodian, Custodian approved Nirav's request - potential conflict of interest"

**How it works:**
- Use LangGraph for bounded multi-hop reasoning
- Start: "Find connections between Nirav and Custodian"
- Agentic steps:
  1. Find all relationships involving Nirav
  2. For each related entity, find their relationships
  3. Check if any path leads to Custodian
  4. Classify: Direct, indirect, potential conflict
- Bounded: Max 3 hops, max 10 entities explored, 30-second timeout
- Output: Relationship graph with evidence trail

**Development time:** 8 weeks (complex, requires research + testing)

**Cost:** $5-10 per query (multiple LLM calls)

**Use sparingly:** Only for complex pattern discovery, not routine queries

---

#### Phase 2 Deliverables:

- ✅ Documentation Gap Engine (90%+ accuracy on known case types)
- ✅ Process Chain Integrity Engine (85%+ detection rate for out-of-order events)
- ✅ Deadline Tracker (100% accuracy for coded deadlines)
- ✅ Bounded Agentic (70%+ discovery rate for hidden patterns)
- ✅ Process template library (20+ case types documented)
- ✅ 200+ cases processed
- ✅ 10+ law firms using LDIP
- ✅ 9/10 satisfaction score

**Total Phase 2 Investment:** $210k

---

### Phase 3: Scale + Advanced Features (Months 8-12)

**Goal:** Enterprise readiness + advanced AI capabilities

**Budget:** $350k

#### Features:

**1. GraphRAG for Case Law**

**Capability:** "Section 3(2) was interpreted in Case A (2015), which was modified by Case B (2018), currently binding precedent"

**How it works:**
- Knowledge graph: Cases → Citations → Interpretations → Overrulings
- Nodes: Statutes, Cases, Judges, Courts
- Edges: Cites, Interprets, Overrules, Distinguishes
- Query: "What's the current law on Section 3(2)?"
- Traverse graph → Find latest binding precedent

**Data source:**
- SCC Online, Manupatra (Indian case law databases)
- Web scraping (if legal) or licensed data

**Development time:** 12 weeks

**Cost:** Data licensing ($10k-50k/year) + $0.50/query (graph traversal + LLM synthesis)

---

**2. Multi-Language Support (Hindi, Gujarati)**

**Capability:** Process Hindi/Gujarati legal documents

**How it works:**
- OCR: Google Document AI supports Indian languages
- Translation: Google Translate API or IndicTrans2 (open-source)
- NER: Multilingual models (mBERT, XLM-RoBERTa)

**Development time:** 8 weeks

**Cost:** +$20-30 per case (translation API costs)

---

**3. Self-Hosted OCR (Cost Optimization at Scale)**

**Capability:** Process 10k+ pages/day at 95% cost savings

**How it works:**
- Deploy DeepSeek-OCR (open-source) on self-hosted GPU
- Hardware: 1x A100 GPU (cloud or on-prem)
- Cost: $2-3/hour GPU rental vs $30-45/1k pages for Document AI

**Break-even:** ~3000 pages/day

**Development time:** 6 weeks (infrastructure setup, model fine-tuning)

---

**4. Enterprise Features**

- SSO (Single Sign-On): SAML, OAuth
- Compliance certifications: SOC 2, ISO 27001
- Audit logs: Track all user actions
- Custom branding: White-label for large firms
- Role-based access control: Admin, Attorney, Paralegal
- Matter-level permissions: Who can see which cases
- Export capabilities: PDF reports, CSV data extracts

**Development time:** 10 weeks

---

**5. Mobile App (iOS + Android)**

**Capability:** Access LDIP on mobile devices

**How it works:**
- React Native or Flutter
- Core features: Summary, Timeline, Q&A, PDF viewer
- Offline mode: Download case summary for court

**Development time:** 12 weeks

---

#### Phase 3 Deliverables:

- ✅ GraphRAG integrated (Indian case law database)
- ✅ Multi-language support (Hindi, Gujarati)
- ✅ Self-hosted OCR option (for high-volume users)
- ✅ Enterprise features (SSO, compliance, audit logs)
- ✅ Mobile app (iOS + Android)
- ✅ 500+ cases processed per month
- ✅ 20+ law firms (enterprise customers)
- ✅ 9.5/10 satisfaction score

**Total Phase 3 Investment:** $350k

---

### Long-Term Vision (Year 2+)

**1. AI Legal Assistant**
- Conversational interface: "Draft a response to this motion"
- Memo generation: Auto-draft legal memos with citations
- Strategy suggestions: "Opposing counsel's argument is weak because..."

**2. Predictive Analytics**
- Case outcome prediction: "Based on similar cases, 65% chance of success"
- Judge behavior analysis: "This judge rules in favor of petitioner 70% of the time in tax cases"

**3. Collaborative Features**
- Multi-user annotation: Lawyers collaborate on same case file
- Comments & threads: Discuss findings with team
- Version control: Track changes to case analysis over time

**4. Integration Ecosystem**
- LawCMS integration: Sync with case management systems
- Court filing integration: E-filing directly from LDIP
- Billing integration: Track time spent using LDIP for client billing

---

## Critical Gaps & Mitigations

### Gap 1: Legal Domain Knowledge (HIGH PRIORITY)

**Problem:** MVP cannot build Documentation Gap or Process Chain engines without knowing what documents/processes are required for each case type.

**Impact:**
- Missing 20-30% of potential value
- Cannot answer: "Am I missing required documents?"

**Mitigation Strategy:**
1. **MVP proves value first** (intelligent search, summarization, visualization)
2. **Then ask lawyers for help:**
   - "You've seen LDIP save you 5 hours. Now help us build gap detection."
   - Offer: Free Phase 2 features + lifetime discount in exchange for 10 hours of their time documenting processes
3. **Start small:** Document 5 common case types (securities fraud, property, tax, contracts, family)
4. **Iterate:** Expand to 20+ case types in Phase 2

**Timeline:** Gather domain knowledge in Months 4-5 (during/after pilot)

**Cost:** $0 (lawyer volunteers) or $5k-10k (hire legal consultant to document processes)

---

### Gap 2: OCR Quality for Handwritten Documents (MEDIUM PRIORITY)

**Problem:** Google Document AI has 78% accuracy on handwriting (Mistral OCR: 88.9%). Indian legal documents often contain handwritten notes, signatures.

**Impact:**
- Low OCR confidence (<50%) for handwritten sections
- Bounding boxes inaccurate for poor-quality scans

**Mitigation Strategy:**
1. **Quality-based routing:**
   - High confidence (>90%) → Use OCR text directly
   - Low confidence (<50%) → Flag for manual review OR use Vision-LLM
2. **Vision-LLM fallback:**
   - For low-confidence pages, send image directly to GPT-4 Vision
   - Cost: $0.10 per page (expensive, use sparingly)
3. **Hybrid approach (future):**
   - Combine OCR + Vision-LLM (arXiv 2510.10138 framework)
   - Achieves F1=1.0 (perfect accuracy) with strategic routing

**Timeline:** Implement quality-based routing in Month 1 (Week 4)

**Cost:** +$0-10 per case (depending on handwriting prevalence)

---

### Gap 3: Contradiction Detection False Positives (MEDIUM PRIORITY)

**Problem:** Semantic similarity can flag statements as contradictory when they're actually compatible.

**Example:**
- Statement 1: "Notice sent on June 5, 2018"
- Statement 2: "Notice received by custodian on June 7, 2018"
- False positive: Different dates, but not contradictory (2-day delivery time)

**Impact:**
- User frustration if too many false alarms
- Trust erosion

**Mitigation Strategy:**
1. **Conservative confidence thresholds:**
   - Only flag High confidence (>90%) contradictions in main UI
   - Show Medium (70-90%) in "Advanced" section with warning
2. **Temporal logic:**
   - Teach LLM: "Sent on X, received on Y" is normal, not contradictory
   - Pattern library: Common non-contradictions
3. **User feedback loop:**
   - "Mark as False Positive" button
   - System learns: Improve prompts over time

**Timeline:** Continuous improvement based on pilot feedback

---

### Gap 4: Cross-Document References (LOW PRIORITY)

**Problem:** Legal documents reference other documents: "See Exhibit A, page 14"

**Impact:**
- System retrieves Exhibit B instead of Exhibit A
- Missing cross-document context

**Mitigation Strategy:**
1. **Cross-reference index (already in MVP):**
   - Pattern matching during ingestion: `r"Exhibit ([A-Z]), page (\d+)"`
   - Store: `cross_references(source_chunk, target_doc, target_page)`
   - Query-time expansion: Retrieve both source AND target
2. **Cost:** $0 (pattern-based, implemented in Month 1)

**Timeline:** Included in MVP (Month 1, Week 4)

---

### Gap 5: Matter Isolation Security (CRITICAL PRIORITY)

**Problem:** If RLS (Row-Level Security) fails, users could access other users' case files (catastrophic for legal ethics).

**Impact:**
- Data breach
- Legal malpractice liability
- Loss of trust → product death

**Mitigation Strategy:**
1. **Defense in depth:**
   - Layer 1: PostgreSQL RLS policies (database level)
   - Layer 2: API-level auth checks (FastAPI middleware)
   - Layer 3: Frontend checks (Next.js middleware + route protection)
2. **Penetration testing:**
   - Hire security firm to attempt cross-matter access
   - Red team exercise: "Try to see another user's case"
3. **Automated tests:**
   - Integration tests: Create User A, User B with different cases
   - Test: User A tries to access User B's matter_id
   - Assert: 403 Forbidden error
4. **Audit logging:**
   - Log every database query with user_id, matter_id
   - Anomaly detection: "User accessed 100 different matters in 1 hour" = suspicious

**Timeline:** Implemented from Day 1, tested in Month 4 (Week 16)

**Cost:** $5k-10k (penetration testing service)

**Non-negotiable:** This MUST be 100% secure or product cannot launch.

---

### Gap 6: Cost Overruns (MEDIUM PRIORITY)

**Problem:** If users upload 10k-page cases or ask 100 queries, costs could explode.

**Impact:**
- $75-110 budget per case → $500+ actual cost
- Unsustainable unit economics

**Mitigation Strategy:**
1. **Rate limiting:**
   - Per user: Max 10 uploads/day, max 50 queries/day
   - Per matter: Max 3000 pages per upload
2. **Caching:**
   - Query cache (Redis, 1-hour TTL)
   - Identical queries = $0 cost (served from cache)
3. **Cost monitoring:**
   - Real-time dashboard: Track API costs per user, per matter
   - Alerts: "User X spent $100 today (threshold: $50)"
4. **Tiered pricing (future):**
   - Free tier: 5 cases/month, 100 queries/month
   - Pro tier: Unlimited cases, pay-per-use
5. **Optimize LLM usage:**
   - Simple tasks (entity extraction, date parsing) → GPT-3.5-turbo (90% cheaper)
   - Complex tasks (summarization, Q&A) → GPT-4

**Timeline:** Implement rate limiting in Month 1, monitoring in Month 2

---

### Gap 7: Latency for Large Cases (LOW-MEDIUM PRIORITY)

**Problem:** 2000-page case takes ~2 minutes to process. What about 5000-page cases?

**Impact:**
- User frustration waiting 5-10 minutes
- Timeouts on frontend

**Mitigation Strategy:**
1. **Background processing:**
   - Upload → Return immediately: "Processing started, we'll notify you"
   - Celery task runs in background
   - WebSocket sends real-time updates: "45% complete"
2. **Parallel processing:**
   - OCR pages in parallel (batch of 100 pages per API call)
   - Chunk + embed in parallel
3. **Optimization:**
   - HNSW index for fast vector search (vs IVF)
   - Redis caching for repeated queries
4. **Set expectations:**
   - Show estimated time: "Processing ~2000 pages, estimated 2 minutes"
   - Progress bar with stage indicators: "OCR (45%) → Chunking (0%) → Embedding (0%)"

**Timeline:** Parallel processing in Month 1, optimization in Month 2-3

**Target:** <5 minutes for 5000-page case

---

## Cost Analysis

### Per-Case Cost Breakdown (2000-page case)

| Component | Cost | Notes |
|-----------|------|-------|
| **OCR (Google Document AI)** | $60-90 | $30-45 per 1k pages × 2 |
| **Embeddings (OpenAI ada-002)** | $0.50 | 4000 chunks × 500 tokens avg = 2M tokens @ $0.10/1M |
| **Parent-Child Chunking** | $0.02 | Processing overhead (negligible) |
| **Summary Generation (GPT-4)** | $0.03 | 1000 input + 500 output tokens |
| **Entity Extraction (GPT-3.5)** | $0.05 | 10k tokens @ $0.50/1M |
| **Timeline Extraction** | $0.02 | Included in entity extraction |
| **Storage (Supabase)** | $0.01 | 150MB PDF + metadata |
| **Vector Search (pgvector)** | $0.01 | Query cost (negligible) |
| **Cache (Redis)** | $0.50 | Monthly allocation per active case |
| **TOTAL (Ingestion)** | **$61-92** | One-time cost per case upload |

### Per-Query Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| **Query Embedding** | $0.0001 | 10 tokens @ $0.10/1M |
| **Vector Search** | $0 | Database query (included in hosting) |
| **BM25 Search** | $0 | Database query |
| **Reranking (Cohere)** | $0.10 | Per query |
| **Answer Generation (GPT-4)** | $0.02 | 1500 input + 300 output tokens |
| **TOTAL (Per Query)** | **$0.12** | Repeated queries = $0 (cached) |

**Average queries per case:** 5-10
**Total query cost per case:** $0.60-1.20

### Total Cost Per Case

| Scenario | Ingestion | Queries | Total |
|----------|-----------|---------|-------|
| **Minimal usage** | $61 | $0.60 (5 queries) | **$61.60** |
| **Typical usage** | $75 | $0.84 (7 queries) | **$75.84** |
| **Heavy usage** | $92 | $1.20 (10 queries) | **$93.20** |

**Target:** $75-110 per case ✅ (within budget)

---

### Monthly Operating Costs (Pilot Phase - 50 cases/month)

| Component | Cost | Calculation |
|-----------|------|-------------|
| **Case Processing** | $3,792 | 50 cases × $75.84 avg |
| **Supabase (Database + Storage)** | $25 | Hobby plan (sufficient for pilot) |
| **Redis (Cache)** | $10 | Upstash free tier or $10/month |
| **Hosting (Backend)** | $20 | Railway Hobby plan |
| **Hosting (Frontend)** | $0 | Vercel free tier |
| **Monitoring (Sentry)** | $0 | Free tier (5k events/month) |
| **TOTAL (Monthly)** | **$3,847** | For 50 cases |

**Per-case marginal cost:** $75.84 (cloud APIs dominate)
**Fixed costs:** $55/month (hosting, infrastructure)

---

### Revenue Model (Future)

**Pricing Options:**

1. **Per-Case Pricing:**
   - Cost: $75-110 per case
   - Price: $199 per case
   - Margin: $89-124 per case (55-62% gross margin)

2. **Subscription Pricing:**
   - Free tier: 5 cases/month, 100 queries/month
   - Pro tier: $499/month (unlimited cases, priority support)
   - Enterprise tier: $2,999/month (dedicated instance, SLA, custom features)

3. **Tiered Per-Case:**
   - Small case (<500 pages): $99
   - Medium case (500-1500 pages): $149
   - Large case (1500-3000 pages): $249
   - Extra-large (3000+ pages): $349

**Break-even (MVP):**
- Development cost: $280k (Month 1-4)
- Break-even at: 1,400 cases @ $199/case
- Or: 560 Pro subscriptions @ $499/month
- Timeline: 6-12 months post-launch (estimated)

---

## Conclusion

### Summary

LDIP MVP is a **focused, achievable product** that delivers **massive value** (4.8-7.2 hours saved per case) without requiring legal domain knowledge upfront.

**Key Strengths:**
1. ✅ **Solves real pain:** Junior lawyers drowning in document chaos
2. ✅ **Achievable in 4 months:** Clear roadmap, proven tech stack
3. ✅ **Affordable:** $75-110 per case (78-91% cheaper than manual review)
4. ✅ **Trustworthy:** Visual verification prevents hallucination issues
5. ✅ **Scalable:** Phase 2-3 add advanced features as product matures

**Key Risks:**
1. ⚠️ **Domain knowledge gap:** Cannot build gap detection without lawyer input (mitigated by phased approach)
2. ⚠️ **Matter isolation security:** Must be 100% airtight (penetration testing required)
3. ⚠️ **OCR quality:** Handwritten documents may have low confidence (quality-based routing mitigates)

**Go/No-Go Decision:**

✅ **GO** - MVP is well-scoped, technically feasible, and solves a validated problem. Risks are manageable with proposed mitigations.

**Next Steps:**
1. Secure funding ($280k for 4-month MVP)
2. Hire team (2 backend devs, 1 frontend dev, 1 DevOps/ML engineer)
3. Kick off Month 1: Infrastructure + OCR implementation
4. Target pilot launch: Month 4, Week 16

---

**Document Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Final - Ready for Implementation
