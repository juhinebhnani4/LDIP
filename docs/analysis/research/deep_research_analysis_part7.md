---
📋 **DOCUMENT STATUS: PHASE 2+ VISION - DEFERRED**
This document is part of the Deep Research vision (8 parts). See [deep_research_analysis_part1.md](./deep_research_analysis_part1.md) for full status information.
**For implementation, use:** [Requirements-Baseline-v1.0.md](../../../_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md)
---

⭐ PART 7 — TECHNICAL ARCHITECTURE

This section defines the full system architecture for LDIP (Legal Document Intelligence Platform). It covers how documents flow, how retrieval operates, how engines are orchestrated, how storage is organized, and how the system ensures correctness, privacy, and performance at scale.

The design follows these principles:

Evidence-first RAG

Matter-isolated data boundaries

Modular engines with strict I/O contracts

Separation of research memory vs AI reasoning memory

Zero-trust cross-matter security

Compatibility with bounded adaptive computation (Option 3)

7.1 High-Level Architecture Overview

System components:

Ingestion & Preprocessing Layer

Document Store & Metadata Store

Vector Store (Matter-Isolated)

Structured Fact Store

Reasoning Engines (Timeline, Process Chain, Consistency, Citation, Pattern)

Orchestrator (Query Pipeline Controller)

Research Journal System (User Workspace)

Caching Layer (Engine + Q&A Cache)

Authorization & Ethical Wall Enforcement Layer

Audit & Observability Layer

Optional Bounded Adaptive Computation Layer (Phase 2/3)

Each layer is modular and replaceable, minimizing coupling.


7.2 Document Ingestion Pipeline

When a document is uploaded:

STEP 1 — Privilege Filter (Part 5 Integration)

Scan for privilege markers

Classify: LOW / MEDIUM / HIGH

HIGH → blocked from LLM until approved

STEP 2 — OCR & Text Normalization

PDF+Image OCR

Page-level segmentation

Layout-aware extraction

Confidence scoring

Store OCR text and per-page metadata

STEP 3 — Metadata Extraction

Document type: affidavit, order, application, judgment, log, email, annexure

Date fields

Parties involved

Mentioned Acts and sections

ISINs, share certificate numbers, financial references

STEP 4 — Chunking (RAG Preparation)

Chunking rules:

per 400–700 tokens

preserve page boundaries

embed page number + document_id in metadata

increase chunk overlap for complex legal paragraphs

STEP 5 — Embedding

Use jurisdiction-configured embedding model

Create vector embeddings

Store embeddings in matter-specific vector namespace

STEP 6 — Structured Artifact Extraction (Part 4.10.1)

Generate:

event tables

entity-role tables

Act citation list

timeline fragments

key-value pairs (amounts, ISINs, share counts)

All stored in Structured Fact Store.

STEP 7 — Pre-Linking (Deterministic Relationship Extraction)

During ingestion, LDIP performs deterministic pre-linking to establish obvious connections:

Entity Pre-Linking:
- Extract all entity mentions (persons, companies, institutions)
- Create initial identity nodes in Matter Identity Graph (MIG)
- Link obvious aliases using deterministic rules (exact name matches, known variations)
- Store entity-to-document mappings

Event Pre-Linking:
- Extract all date-stamped events
- Link events to entities mentioned in the same document/section
- Create initial timeline fragments with entity associations

Relationship Pre-Linking:
- Extract explicit relationships (director_of, introduced_by, beneficial_owner)
- Link entities to roles mentioned in documents
- Store relationship edges in MIG

Citation Pre-Linking:
- Extract all Act/section citations
- Link citations to documents and pages
- Create citation-to-document mappings

All pre-linked relationships are:
- Deterministic (rule-based, not LLM-inferred)
- Matter-scoped (no cross-matter links)
- Stored in Structured Fact Store and MIG
- Available for fast query-time retrieval

Pre-linking enables:
- Fast entity resolution during queries
- Immediate timeline reconstruction
- Efficient cross-document relationship traversal
- Reduced query-time computation for obvious connections

Note: Pre-linking captures only obvious, deterministic relationships. Novel patterns, hidden connections, and corruption detection require query-time adaptive analysis (see Part 4.11 and Part 8).

7.3 Storage Layer Design

LDIP uses several storage systems, each strictly scoped by matter_id.

1. Document Store

Stores:

original documents (encrypted)

OCR text

privilege status

metadata

2. Vector Store (Matter-Isolated)

Options:

Qdrant (recommended for cost-effective and fast HNSW)

Azure AI Search (if Azure ecosystem used)

Pinecone (performance-first)

Milvus (scale-first)

Each matter → its own namespace:

vector_namespace: matter_id

3. Structured Fact Store

A relational database (Postgres recommended).

Tables:

events (matter_id, doc_id, page, date, text, entity_ids[])
entities (matter_id, name, role, entity_id)
citations (matter_id, act, section, doc_id, page)
timeline_fragments
contradiction_pairs
process_chain_items
pre_linked_relationships (matter_id, from_entity_id, to_entity_id, relationship_type, doc_id, page, confidence, link_source)

Matter Identity Graph (MIG):

- Implemented using tables for:
  - identity_nodes (matter_id, node_id, entity_type, canonical_name, metadata)
  - identity_edges (matter_id, edge_id, from_node, to_node, edge_type, metadata)

- Edge types include:
  - ALIAS_OF (same entity in this matter)
  - HAS_ROLE (entity ↔ role in this matter)
  - RELATED_TO (introducer, director, family link, etc., within this matter)

- Every row is tagged with `matter_id` and obeys matter isolation and
  the retention/destruction rules from Part 2.

  The MIG provides canonical entity resolution, role mapping, and alias relationships for the reasoning engines. It is generated and maintained exclusively by Engine 6 and is used by all other engines to ensure consistent entity interpretation across documents in the same matter.

4. Research Journal Store (User-Specific)

per-user

per-matter

encrypted

journal entries never used as RAG input

referenced in the UI only

Schema:

journal_entries
    id
    matter_id
    user_id
    question
    structured_answer (json)
    notes (text)
    created_at
    shared_with_team (bool)

5. Engine Cache Store

Stores outputs from timeline, consistency, chain, pattern engines:

engine_cache
    matter_id
    engine_type
    input_hash
    output_json
    timestamp
    engine_version


Allows reusing expensive computations.

7.4 Reasoning Engine Architecture

LDIP uses independent, stateless, deterministic engines with strict input/output formats.

Engines:

Extraction Engine

Timeline Engine

Consistency Engine

Process Chain Engine

Citation Engine

Pattern/Anomaly Engine

Authenticity/Naming Graph Engine (Phase 2)

Each engine receives:

{
  "matter_id": "...",
  "evidence_pack": [...],
  "task_instructions": "...",
  "context_block": {...}
}


Engine outputs MUST contain:

factual findings

citations

limitations

confidence scores

no legal conclusions

no strategies

Engines do not talk to each other directly.
They are orchestrated (see 7.5).

The Authenticity/Naming Graph Engine (Engine 6) is the only engine permitted to write updates to the Matter Identity Graph (MIG), including creating alias links, merging entities, and assigning canonical entity IDs. All other engines may only read from MIG and never modify it.

7.5 Orchestrator: Query Pipeline Controller

This component runs the pipeline described in Part 4.11:

Pipeline Steps:

Auth + ethical wall

Safety classification

Context building

Hierarchical retrieval

Engine execution

Validation

Journal logging (optional)

Response formatting

Audit logging

The orchestrator enforces:

matter isolation

privilege protections

safe memory

allowed engine usage

It is also the entry point for future bounded adaptive computation planning.

7.6 Research Journal Architecture (Critical New Component)

The Research Journal is a separate subsystem dedicated to:

continuity

user-specific context

personal research tracking

MUST NOT:

influence RAG retrieval

influence engine reasoning

allow cross-user leakage

allow cross-matter leakage

Journal entries only enhance UX, not AI accuracy.

How journal integrates with system:

Orchestrator → saves structured outputs

UI → shows journal timeline

Matter memory → stores journal artifacts by reference

Bounded adaptive computation → can view journal entries only when explicitly requested

The Journal is your solution to long-term interaction without LLM memory.

The Research Journal is strictly excluded from all retrieval, RAG operations, vector indexing, and engine reasoning. Journal entries are never embedded, never chunked, and never used as model input unless the user explicitly pastes them into a query.

Relationship with Matter Memory Files:

The Research Journal and Matter-Scoped Analytical Memory (including Matter Memory Files) serve different purposes:

- **Matter Memory Files** (section 6.3.1): System-generated, matter-scoped, shared across all users with matter access. Contains query summaries, timeline summaries, entity mappings. Automatically injected into context for continuity.

- **Research Journal**: User-specific, personal notes and insights. Not automatically injected, only shown in UI. User controls what goes into journal.

Key distinction: Matter Memory Files provide system-level continuity (what the system "remembers" about the matter). Research Journal provides user-level continuity (what the lawyer personally notes and tracks). They complement each other but remain separate to maintain clear boundaries between system memory and personal notes.

7.7 Caching & Performance Architecture

Two caches:

1. Engine Cache

Reuses outputs from heavy analyses like:

timelines

process chains

entity mapping

Cache invalidated on:

new document upload

privilege override

engine version change

2. Q&A Cache

Per matter.

key = normalized user question

value = structured answer

A cache hit displays:

“This answer was returned from cache (same evidence, same documents).”

No cached answer can be used if:

new documents added

privilege status changed

user lacks access

### Cache Invalidation Rules (MVP)

Cached engine outputs MUST be invalidated when:

- New documents are added to the Matter
- Privilege classification of any document changes
- The Matter Identity Graph is updated

Cache entries MUST NOT be reused across Matters or across privilege states.


7.8 Bounded Adaptive Computation Layer (Phase 2+)

Architecture supports bounded adaptive computation for:

Novel Pattern Discovery:
- Corruption pattern detection (hidden connections, manipulation patterns)
- Cross-matter network analysis (when authorized)
- Anomaly clustering beyond pre-linked relationships

Adaptive Planning (One-Time):
- Query-time analysis planning (not iterative)
- Determines which engines to call and in what order
- Identifies when bounded loops are needed for connection discovery

Bounded Loop Execution:
- Real loops with explicit stop conditions:
  - Maximum iterations (e.g., max 5 connection hops)
  - No new findings threshold (stop if no new connections found)
  - Time limits (e.g., max 30 seconds per loop)
  - User checkpoints (pause for approval at critical steps)
- Used for:
  - Multi-hop relationship traversal
  - Iterative pattern discovery
  - Cross-document connection chains

Architecture Support:

all adaptive computation calls the Orchestrator

strict I/O (JSON only)

never sees privilege-blocked items

cannot request cross-matter data without authorization

all actions logged with loop iteration counts and stop conditions

This ensures adaptive workflows stay safe, reproducible, and bounded.

7.9 Integration Layer (MCP Tools, APIs, Event Hooks)

LDIP exposes APIs/tools:

Tools for bounded adaptive computation and external integrations:

get_matter_documents(matter_id)

retrieve_evidence(query, matter_id)

run_engine(engine_type, evidence_pack)

write_journal_entry(user_id, matter_id)

fetch_journal_entries(user_id, matter_id)

get_timeline(matter_id)

get_process_chain(matter_id)

MCP Integration:

Allows:

live code execution

controlled environment for bounded iterative workflows

strictly scoped tool calls

Bounded adaptive computation cannot bypass matter isolation.

7.10 Compliance Enforcement Layer

This layer enforces:

matter_id constraints

data residency

encryption policies

privilege restrictions

cross-matter approvals

jurisdictional flags

retention schedules

When a document or analysis changes status:

privileges propagate

caches purge

bounded adaptive computation results flagged obsolete

7.11 Phased Implementation Plan

7.11.1 Philosophy

Start simple, validate, then add complexity only when needed.

**Phase 1 (MVP):** Months 1-3 - Core functionality with pre-linking, 5-8 core templates
**Phase 1.5:** Months 3-4 - Strategic template expansion based on usage data
**Phase 2:** Months 4-6 - Enhanced engines, cross-matter analysis, confidence scoring
**Phase 3:** Months 7-9 - Bounded adaptive computation, advanced features

7.11.2 Phase 1: MVP (Months 1-3)

**Goal:** Deliver a working system that lawyers can use to analyze legal documents within a single matter, with basic pattern detection and conflict checking.

**Core Features:**

1. **Matter Management**
   - Create Matter: Lawyer creates matter with flexible naming
   - Upload Documents: Bulk upload (100s of files)
   - Conflict Check: Fast pre-check + background deep check
   - Matter Isolation: Strict enforcement, no cross-matter access

2. **Pre-Linking Engine**
   - Deterministic Extraction: Rule-based entity, event, citation extraction
   - MIG Population: Create identity nodes and edges
   - Relationship Storage: Store pre-linked relationships in Structured Fact Store

3. **Analysis Engines (Pre-Linking Based)**
   - Timeline Engine: Chronological event reconstruction
   - Process Chain Engine: Expected vs actual process comparison
   - Consistency Engine: Contradiction detection
   - Citation Engine: Act text verification
   - Pattern Engine (Basic): Anomaly clustering from other engines

4. **RAG System (Matter-Isolated)**
   - Vector Store: Qdrant with matter namespaces
   - Hierarchical Retrieval: Document → Section → Chunk
   - Hybrid Search: Keyword + semantic
   - Evidence Packaging: Structured evidence packs for engines

5. **Research Journal**
   - Personal Notes: Encrypted storage per user, per matter
   - Auto-Save Option: User can accept/reject saving analysis
   - Isolation: Never used in RAG, never visible across matters

6. **Basic UI**
   - Matter Workspace: Document tree, analysis panel, journal
   - Query Interface: Natural language questions
   - Results Display: Structured findings with citations
   - Evidence Viewer: Click-through to source documents

**Technical Stack (MVP):**
- Backend: Python (FastAPI) or Node.js (Express)
- Database: PostgreSQL
- Vector Store: Qdrant
- Object Storage: S3-compatible
- Cache: Redis
- Authentication: Keycloak or Auth0

**Success Criteria:**
- Lawyer can create matter and upload 100+ files
- Conflict check completes in <5 seconds (pre-check)
- Timeline accuracy: 85%+ vs manual review
- Citation verification: 90%+ accuracy
- Response time: <5 minutes per query
- Zero cross-matter data leakage
- 5-8 core process templates implemented with composite structure

7.11.2.5 Phase 1.5: Strategic Template Expansion (Months 3-4)

**Goal:** Expand templates strategically based on actual usage data, not guesses.

**Activities:**
1. **Usage Data Analysis**
   - Analyze actual user queries from first 3 months
   - Document patterns in user requests
   - Identify high-frequency case types
   - Review 1000+ queries for patterns

2. **Template Expansion**
   - Add 2-3 new templates for high-frequency case types
   - Only add templates if 10%+ of cases need them (data-driven threshold)
   - Maintain composite template structure (required/optional/flexible-order steps)

3. **Quarterly Review Process**
   - Template team reviews data quarterly (not continuous)
   - Cost: Template team reviews data quarterly
   - Benefit: Accuracy stays high. Templates expand only when needed.

**Success Criteria:**
- 2-3 new templates added based on usage data
- Template expansion criteria met (10%+ usage threshold)
- Quarterly review process established
- No template overhead increase (composite structure handles variants)

7.11.3 Phase 2: Enhanced Capabilities (Months 4-6)

**Goal:** Add cross-matter analysis, enhanced engines, and improved performance.

**New Features:**

1. **Cross-Matter Analysis (Authorized)**
   - Same-client pattern detection
   - Cross-matter identity resolution (query-time with optional cache)
   - Research Collections for authorized cross-matter comparison

2. **Enhanced Engines**
   - Entity Authenticity Engine (Engine 6) - full implementation
   - Admissions & Non-Denial Detector (Engine 7)
   - Pleading-vs-Document Mismatch Engine (Engine 8)
   - Improved pattern detection with semantic analysis
   - Multi-hop relationship discovery
   - **Confidence Scoring:** Add pattern confidence scores to all findings output
     - Process Chain Engine findings include confidence scores
     - Confidence based on template component type (required_steps = higher confidence)
     - Confidence includes reasoning and baseline comparison
     - Example: "Step 2 missing. Confidence this is anomalous: 92%. Reasoning: Required step per template. Missing in only 2% of authorized matters."

3. **Performance Improvements**
   - Document ingestion: <1 min per 100-page PDF
   - Query response: <3 minutes for complex queries
   - Support 100+ concurrent users
   - Support 10,000+ documents per matter

4. **Integration APIs**
   - REST API for document management systems
   - Webhook support for document uploads
   - Case management system integration

**Success Criteria:**
- Cross-matter pattern detection with authorization
- Performance targets met
- API integration working with at least one DMS
- 100+ concurrent users supported
- Confidence scoring implemented for all Process Chain Engine findings
- 2-3 additional templates added as new patterns emerge (quarterly review process)

7.11.4 Phase 3: Advanced Features (Months 7-9)

**Goal:** Add bounded adaptive computation and advanced pattern discovery.

**New Features:**

1. **Bounded Adaptive Computation**
   - Novel pattern discovery with explicit stop conditions
   - Multi-hop connection discovery
   - Iterative pattern clustering
   - Adaptive planning (one-time query-time analysis)

2. **Advanced Analytics**
   - Statistical baselines for process chains
   - Predictive document gap detection
   - Research hypothesis generation

3. **Enhanced UX**
   - Visual reasoning chains
   - Interactive evidence exploration
   - Advanced reporting and export

**Success Criteria:**
- Bounded adaptive computation discovers novel patterns
- Stop conditions prevent infinite loops
- Advanced analytics provide actionable insights
- User satisfaction: 80%+ positive feedback

7.11.5 Implementation Guidelines

**Development Approach:**
- Agile sprints (2-week cycles)
- Continuous integration and deployment
- Regular stakeholder reviews
- User feedback integration

**Testing Strategy:**
- Unit tests for each component
- Integration tests for end-to-end flows
- Security tests for matter isolation
- Performance tests for scalability
- User acceptance testing with real lawyers

**Risk Management:**
- Feature flags for gradual rollout
- Rollback procedures for each phase
- Monitoring and alerting from day one
- Regular security audits

7.12 Complete Backend Flow: Document Upload → Query Response

This section provides a detailed, step-by-step technical flow showing how LDIP processes documents from upload through query response. This complements the high-level architecture described in sections 7.1-7.11.

7.12.1 Phase 1: Document Ingestion Pipeline

When a user uploads documents, LDIP follows this complete flow:

**Step 1: File Upload & Validation**

```
User uploads PDF → API receives file
  ↓
Assign unique document_id
  ↓
Store original file in Supabase Storage: documents-{tenant_id}/{matter_id}/originals/{document_id}.pdf
  ↓
Create database record in documents table:
  - document_id (UUID)
  - matter_id (UUID) ← CRITICAL: Links to matter
  - file_name, file_path, file_size
  - uploaded_by (user_id)
  - uploaded_at (timestamp)
```

**Storage Location:**
- **Supabase Storage:** `documents-{tenant_id}/{matter_id}/originals/{document_id}.pdf`
- **Database Table:** `documents` (PostgreSQL)

**Key Fields:**
- `document_id`: Unique identifier for the document
- `matter_id`: Links document to specific matter (enforces isolation)
- `file_path`: Reference to storage location

**Step 2: Privilege Scanning**

```
Scan document for privilege markers:
  - "attorney-client privilege" headers
  - Counsel email signatures
  - Strategy discussion keywords
  ↓
Assign privilege_score (0-10):
  - 0-3: LOW → Full processing allowed
  - 4-6: MEDIUM → Processing with audit flag
  - 7-10: HIGH → BLOCKED from LLM until MatterLead approval
  ↓
Store privilege_level in documents table
```

**Privilege Levels:**
- **LOW (0-3):** Full processing allowed, no restrictions
- **MEDIUM (4-6):** Processing allowed with audit flag, MatterLead notification optional
- **HIGH (7-10):** Blocked from all LLM analysis, vector embedding, and RAG retrieval until MatterLead approval

**Storage:**
- `documents.privilege_level` (LOW/MEDIUM/HIGH)
- `documents.privilege_score` (0-10)
- `documents.privilege_markers` (JSON array of detected markers)

**Step 3: Text Extraction (Hybrid OCR + LLM Strategy)**

```
Check document type:
  ↓
Native PDF? → Direct text extraction (no OCR needed)
  ↓
Scanned PDF? → OCR processing:
  - Run OCR (Tesseract or cloud service)
  - Get OCR confidence score per page
  - Store OCR text in Supabase Storage: documents-{tenant_id}/{matter_id}/ocr/{document_id}.txt
  ↓
OCR confidence < 70% OR complex structure detected?
  ↓ YES
LLM text extraction:
  - Extract actual text (not just structure)
  - Store LLM-extracted text separately
  - Also extract structure annotations (tables, multi-column layouts)
  ↓
Final document representation:
  - OCR text = legal record (always preserved, never deleted)
  - LLM text = extracted when OCR confidence <70% (stored separately)
  - Selected text = attorney chooses which to use for analysis
```

**Storage Locations:**
- **OCR Text:** `documents-{tenant_id}/{matter_id}/ocr/{document_id}.txt` (legal record, always preserved)
- **LLM Text:** `documents-{tenant_id}/{matter_id}/llm/{document_id}.txt` (when OCR confidence <70%)
- **LLM Annotations:** `documents-{tenant_id}/{matter_id}/metadata/{document_id}_annotations.json` (structure metadata)

**Database Fields:**
- `documents.ocr_text_path`: Reference to OCR text file (legal record)
- `documents.llm_text_path`: Reference to LLM-extracted text file (when confidence <70%)
- `documents.ocr_confidence`: Per-page confidence scores (JSON)
- `documents.selected_text_source`: Which text source attorney selected (OCR/LLM/SELECTED)
- `documents.text_selection_timestamp`: When attorney made selection
- `documents.text_selected_by`: User ID who selected text source
- `documents.llm_annotations`: Structure annotations (JSON, metadata)

**Evidence Binding:**
- **OCR text is legal record** - Always preserved, never deleted, used for legal citations
- **LLM text is analysis aid** - Extracted when OCR confidence <70%, stored separately
- **Selected text** - Attorney chooses which text source (OCR or LLM) to use for analysis
- **Citations include text_source** - "OCR" (legal) or "SELECTED" (analysis)

**Step 4: Metadata Extraction**

```
Extract structured metadata:
  - Document type (affidavit, order, application, judgment)
  - Dates mentioned
  - Parties involved (Nirav Jobalia, Mehta family, etc.)
  - Acts and sections cited
  - ISINs, share certificate numbers
  ↓
Store in documents.metadata (JSONB column):
{
  "document_type": "affidavit",
  "dates": ["2023-09-29", "2023-02-27"],
  "parties": ["Nirav Jobalia", "Mehta family"],
  "acts_cited": ["TORTS Act 1992"],
  "sections_cited": ["Section 12", "Section 15"]
}
```

**Extracted Metadata:**
- Document type classification
- Date fields (all dates mentioned)
- Party names (persons, companies, institutions)
- Act/section citations
- Financial references (ISINs, share certificates, amounts)

**Storage:**
- `documents.metadata` (JSONB column in PostgreSQL)

**Step 5: Chunking for RAG**

```
Split document into chunks:
  - 400-700 tokens per chunk
  - Preserve page boundaries
  - 100-200 word overlap between chunks
  ↓
Create chunk records:
  - chunk_id (UUID)
  - document_id (links to parent document)
  - matter_id (for isolation)
  - page_range ("3-7")
  - text (actual content)
  - chunk_index (position in document)
```

**Chunking Strategy:**
- **Primary:** Logical sections (identified by headings)
- **Secondary:** Page-based chunks (1-2 pages per chunk)
- **Tertiary:** Paragraph-based (for dense documents)

**Chunk Size:** 500-1000 words optimal
**Overlap:** 100-200 words between chunks

**Storage:**
- `document_chunks` table:
  - `chunk_id` (UUID, primary key)
  - `document_id` (foreign key → documents)
  - `matter_id` (for isolation)
  - `page_range` (e.g., "3-7")
  - `text` (actual content from selected text source)
  - `text_source` (OCR/LLM/SELECTED - which text source was chunked)
  - `chunk_index` (ordinal position)
  - `position` (start/end character offsets)

**Step 6: Vector Embedding Generation**

```
For each chunk:
  ↓
Generate embedding using OpenAI ada-002 (1536 dimensions)
  ↓
Store in Supabase pgvector:
  - Table: document_embeddings
  - Namespace: matter_id (CRITICAL for isolation)
  - Metadata includes: document_id, page_number, chunk_index
  ↓
```

**Embedding Model:** OpenAI text-embedding-ada-002 (1536 dimensions)

**Storage:**
- **Table:** `document_embeddings` (Supabase pgvector)
- **Index:** HNSW index for fast similarity search
- **Namespace:** `matter_id` (enforces matter isolation)

**Schema:**
```sql
CREATE TABLE document_embeddings (
  id UUID PRIMARY KEY,
  matter_id UUID NOT NULL,
  document_id UUID NOT NULL,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),  -- OpenAI ada-002 dimension
  metadata JSONB,
  created_at TIMESTAMPTZ
);

-- HNSW index for fast similarity search
CREATE INDEX ON document_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- RLS policy for matter isolation
CREATE POLICY matter_isolation ON document_embeddings
  FOR SELECT USING (matter_id = current_setting('app.matter_id')::UUID);
```

**Key Points:**
- Each chunk gets a 1536-dimensional vector
- Vectors stored with `matter_id` for isolation
- Metadata includes `document_id`, `page_number`, `text_source` for citation linking
- Embeddings generated from selected text source (OCR or LLM)

**Step 7: Document Summary Generation**

```
Send document to LLM with summary prompt:
  ↓
Generate 1-2 page summary covering:
  - Parties mentioned
  - Key dates
  - Main claims
  - Sections cited
  - Procedural status
  ↓
Store in document_summaries table:
  - document_id
  - matter_id
  - summary_text
  - summary_metadata (JSON)
  - text_source (which text source was used: OCR/LLM/SELECTED)
```

**Summary Content:**
- Parties mentioned (all entities)
- Key dates (all dates extracted)
- Main claims (primary assertions)
- Sections cited (all Act/section references)
- Procedural status (document type, filing date, etc.)

**Storage:**
- `document_summaries` table:
  - `document_id` (foreign key)
  - `matter_id` (for isolation)
  - `summary_text` (1-2 pages of text)
  - `summary_metadata` (JSON with structured data)

**Purpose:**
- Used in query-first approach to identify relevant documents
- Reduces context from 30K+ tokens to ~500 tokens for document selection

**Step 8: Pre-Linking (Deterministic Relationship Extraction)**

This step extracts obvious, deterministic relationships during ingestion. See section 7.2 for detailed pre-linking architecture.

**Pre-Linking Types:**

1. **Entity Pre-Linking:**
   - Extract all entity mentions (persons, companies, institutions)
   - Create MIG nodes for each unique entity
   - Link obvious aliases (exact name matches, known variations)
   - Store entity-to-document mappings

2. **Event Pre-Linking:**
   - Extract all date-stamped events
   - Link events to entities mentioned in same document/section
   - Create initial timeline fragments with entity associations

3. **Citation Pre-Linking:**
   - Extract all Act/section citations
   - Link citations to documents and pages
   - Create citation-to-document mappings

4. **Relationship Pre-Linking:**
   - Extract explicit relationships (director_of, introduced_by, beneficial_owner)
   - Link entities to roles mentioned in documents
   - Store relationship edges in MIG

**Storage Tables:** See section 7.3 for complete schema definitions.

**Key Characteristics:**
- **Deterministic:** Rule-based, not LLM-inferred
- **Matter-scoped:** No cross-matter links
- **Fast retrieval:** Available immediately at query time
- **Obvious connections only:** Novel patterns require query-time analysis

**Step 9: Structured Fact Extraction**

```
Extract structured artifacts:
  - Event tables
  - Entity-role tables
  - Timeline fragments
  - Key-value pairs (amounts, ISINs)
  ↓
Store in Structured Fact Store (PostgreSQL):
  - events table
  - entities table
  - citations table
  - timeline_fragments table
  - pre_linked_relationships table
  ↓
All tables have matter_id column for isolation
```

**Structured Artifacts:**
- Event tables (chronological events with dates)
- Entity-role tables (who has what role)
- Timeline fragments (partial timelines)
- Key-value pairs (amounts, ISINs, share counts)

**Storage:**
- All stored in PostgreSQL (Structured Fact Store)
- Every table has `matter_id` column for isolation
- Enables fast query-time retrieval without LLM calls

7.12.2 Phase 2: Query Processing (When User Asks a Question)

**Step 0: Input & Matter Context Loading**

```
User query: "Who actually owns the shares: Nirav or Mehta?"
  ↓
API receives:
  - user_id
  - matter_id ← CRITICAL: Determines which data to access
  - user_query
  ↓
Verify matter exists
  ↓
Load matter metadata:
  - Party dictionary (all entities in this matter)
  - Document inventory (all documents in this matter)
  - Pre-computed summaries
  - Act sections relevant to this matter
  ↓
Apply matter isolation:
  - Only data with matter_id = "matter-456" is accessible
  - All queries filtered by matter_id
```

**Input Validation:**
- Verify `matter_id` exists
- Verify `user_id` has access to `matter_id`
- Reject query if `matter_id` is missing

**Matter Context:**
- Party dictionary: All entities mentioned in this matter
- Document inventory: List of all documents in this matter
- Pre-computed summaries: Document summaries generated during ingestion
- Act sections: Relevant statutory sections for this matter type

**Matter Isolation:**
- All subsequent queries MUST include `matter_id`
- Database queries filtered by `matter_id`
- Vector search scoped to matter namespace
- No cross-matter data visible

**Step 1: Authorization & Ethical Wall Check**

```
Check user access:
  - Does user_id have access to matter_id?
  - What role? (FirmAdmin, MatterLead, MatterMember, ReadOnly)
  ↓
Check for cross-matter requests:
  - Does query mention entities from other matters?
  - If yes → REJECT (unless authorized)
  ↓
If matter is frozen (conflict, privilege lock):
  → Return safety refusal
```

**Access Control:**
- **FirmAdmin:** Global policies, conflict overrides, user management
- **MatterLead:** Matter creation, privilege overrides, team assignment
- **MatterMember:** Document upload, query execution, analysis review
- **ReadOnly:** View analyses, read documents, no modifications

**Ethical Wall Enforcement:**
- Check if query mentions entities from other matters
- If cross-matter access needed → REJECT (unless Phase 2 with authorization)
- Maintain "silent wall" - system denies existence of other matters

**Matter Status Checks:**
- Conflict detected → Blocked pending review
- Privilege lock → Blocked until MatterLead approval
- Admin lock → Blocked by FirmAdmin

**Step 2: Query Guardrails**

```
Send query to guardrails system:
  "Who actually owns the shares: Nirav or Mehta?"
  ↓
Query Guardrails Check:
  - Classify as safe/unsafe/needs rewriting
  - If unsafe ("Who is at fault?") → Block with explanation
  - If needs rewriting → Rewrite automatically
  - If safe → Proceed to classification
  ↓
Example rewrite:
  "Who is at fault?" → "What actions were taken by each party?"
  ↓
Proceed to Question Classification
```

**Query Guardrails Functions:**
- Block unsafe queries (legal strategy, outcome prediction, fault/liability)
- Rewrite dangerous questions to safe alternatives
- Provide soft warnings for borderline queries
- Log all blocked/rewritten queries for audit

**Step 3: Question Classification (Safety Router)**

```
Send query to classification LLM:
  "What actions were taken by each party regarding share ownership?"
  ↓
Classification output:
{
  "question_type": "consistency",  // Ownership question = consistency check
  "required_engine": "consistency_engine",
  "safety": "SAFE"  // Not asking for legal advice, asking for facts
}
  ↓
Route to: Consistency Engine
```

**Classification Types:**
- `timeline` → Timeline Engine
- `citation` → Citation Engine
- `consistency` → Consistency Engine
- `process_chain` → Process Chain Engine
- `pattern` → Pattern Engine
- `entity_authenticity` → Entity Authenticity Engine
- `admissions` → Admissions & Non-Denial Detector
- `pleading_mismatch` → Pleading-vs-Document Mismatch Engine
- `disallowed_strategy` → REJECT (unsafe query)
- `legal_conclusion` → REJECT (unsafe query)

**Safety Check:**
- **SAFE types:** Proceed to engine execution
- **UNSAFE types:** Trigger fallback template, refuse to answer

**Step 4: Context Builder**

```
Load relevant context based on classification:
  ↓
Load from Structured Fact Store:
  - Party-role mappings (Nirav Jobalia, Mehta family roles)
  - Relationship graph (MIG) - same individual across aliases
  - Relevant Act sections (TORTS Act 1992)
  - Pre-computed document summaries
  ↓
This becomes the "Context Block" for the engine prompt
```

**Context Components:**

1. **Relevant Act Sections:**
   - Load Act sections mentioned in documents
   - For ownership questions → Load relevant property/share ownership sections

2. **Party-Role Mappings:**
   - Load from MIG: Who is Nirav Jobalia? What roles does he have?
   - Load from MIG: Who is Mehta family? What roles do they have?

3. **Relationship Graph:**
   - Load MIG edges: How are entities related?
   - Load alias mappings: "Nirav D Jobalia" = "Nirav Jobalia"

4. **Pre-Computed Summaries:**
   - Document-level summaries (1-2 pages each)
   - Section-level summaries (for large documents)
   - Facts tables (structured data)

**Step 5: Retrieval Layer (Hierarchical RAG + Pre-Linking)**

The retrieval layer uses a hybrid approach combining fast pre-linking with hierarchical RAG:

**Step 5A: Pre-Linked Relationship Retrieval (Fast Path)**

```
Check pre-linked relationships:
  ↓
Query Structured Fact Store:
  SELECT * FROM pre_linked_relationships 
  WHERE matter_id = 'matter-456' 
  AND (from_entity_id IN ('entity-nirav', 'entity-mehta') 
       OR to_entity_id IN ('entity-nirav', 'entity-mehta'))
  AND relationship_type LIKE '%ownership%'
  ↓
If found:
  - Retrieve pre-linked ownership claims
  - Use as starting point for Evidence Pack
```

**Fast Path Decision:**
- If pre-linking covers query needs → Proceed directly to engine execution (skip 5B-5D)
- If query requires novel pattern discovery → Use pre-linking as starting point, proceed to hierarchical RAG

**Step 5B: Document Selection (Query-First Approach)**

```
Use query-first approach:
  ↓
Send to LLM (~500 tokens):
  Query: "Who actually owns the shares: Nirav or Mehta?"
  + Document summaries (all documents in matter)
  ↓
LLM identifies relevant documents:
  - Doc-12: "Affidavit in reply of Respondent No. 2 Hero Honda"
  - Doc-28: "Affidavit in Rply on Nirav D Jobalia"
  - Doc-9: "Affidavit in Rply of the Nirav D Jobalia"
  ↓
Filter document set to smallest possible
```

**Query-First Approach:**
- **Input:** Query + Document summaries (~500 tokens total)
- **Output:** List of relevant document IDs
- **Purpose:** Identify relevant documents before expensive chunk retrieval

**Step 5C: Section Selection**

```
For each selected document:
  ↓
Fetch section-level summaries
  ↓
Match keywords: "ownership", "shares", "Nirav", "Mehta"
  ↓
Use pre-linked entity-document mappings:
  - Which pages mention Nirav?
  - Which pages mention Mehta?
  - Which pages mention ownership?
  ↓
Identify relevant pages/regions:
  - Doc-12, Pages 5-7: Ownership claims
  - Doc-28, Pages 2-4: Ownership statements
```

**Step 5D: Chunk-Level Vector Search**

```
Over identified regions only:
  ↓
Generate query embedding:
  "Who actually owns the shares: Nirav or Mehta?"
  → embedding: [0.789, -0.234, ...]
  ↓
Search vector store (matter-scoped):
  SELECT * FROM document_embeddings
  WHERE matter_id = 'matter-456'
  AND document_id IN ('doc-12', 'doc-28', 'doc-9')
  AND page_number BETWEEN 2 AND 7
  ORDER BY embedding <-> query_embedding
  LIMIT 10
  ↓
Retrieve top-k most relevant chunks (~5K tokens total)
```

**Vector Search Process:**

1. **Generate Query Embedding:**
   - Use same model as document embeddings (OpenAI ada-002)
   - Generate 1536-dimensional vector for query

2. **Matter-Scoped Search:**
   - Search only within matter namespace
   - Filter by document IDs and page ranges
   - Use HNSW index for fast similarity search

3. **Result:**
   - Top 10 most relevant chunks
   - Total ~5K tokens (instead of 30K+)
   - Each chunk includes `document_id`, `page_number` for citation

**Key Optimization:**
- Search only over identified page regions (not entire documents)
- Reduces context from 30K+ tokens to ~5K tokens
- Maintains accuracy while reducing cost and latency

**Step 6: Evidence Pack Assembly**

```
Combine all retrieved evidence:
  ↓
Evidence Pack = {
  - Pre-linked relationships (from Step 5A)
  - Relevant chunks (from Step 5D)
  - Context block (from Step 4)
  - Act sections (from Step 4)
  - MIG relationships (from Step 4)
}
  ↓
Package for engine consumption
```

**Evidence Pack Structure:**
- Pre-linked relationships (fast path)
- Vector-retrieved chunks (semantic search)
- Context block (party mappings, Act sections)
- MIG relationships (entity graph)

**Step 7: Engine Execution**

```
Send to Consistency Engine:
  - Evidence Pack
  - Task instructions
  - Context Block
  ↓
Engine analyzes:
  - Compare ownership claims across documents
  - Identify contradictions
  - Extract evidence for each claim
  ↓
Engine output:
{
  "findings": [
    {
      "finding": "Document A claims Nirav owns shares, Document B claims Mehta owns shares",
      "confidence": 0.85,
      "citations": [
        {"document_id": "doc-28", "page": 2, "line": 15},
        {"document_id": "doc-12", "page": 5, "line": 8}
      ],
      "evidence": "...",
      "limitations": "Cannot determine actual ownership from provided documents"
    }
  ],
  "confidence": 0.85,
  "limitations": "..."
}
```

**Engine Output Requirements:**
- Factual findings (no legal conclusions)
- Citations (document, page, line)
- Confidence scores (with reasoning and baseline comparison for Process Chain Engine)
- Limitations
- Evidence snippets

For Process Chain Engine specifically:
- Confidence scores based on template component type (required_steps = higher confidence, optional_steps = lower confidence)
- Confidence reasoning: "Required step per template. Missing in only 2% of authorized matters."
- Baseline comparison: "Present in 98% of similar cases"

**Step 8: Response Formatting & Delivery**

```
Format engine output:
  ↓
Structure response:
  - Executive summary
  - Detailed findings with citations
  - Confidence indicators
  - Limitations
  - Evidence links
  ↓
Return to user:
  - Formatted response
  - Clickable citations
  - Evidence viewer links
```

**Response Format:**
- Executive summary (1-2 sentences)
- Detailed findings with citations
- Confidence indicators (High/Medium/Low)
- Limitations section
- Evidence links (clickable to source documents)

**Step 9: Optional Journal Logging**

```
If user opts to save:
  ↓
Store in Research Journal:
  - question
  - structured_answer
  - citations
  - engine_used
  - matter_id
  - user_id
  ↓
Journal entry is:
  - Encrypted
  - Matter-isolated
  - Never used in RAG
  - User-specific
```

**Journal Entry:**
- Question and answer stored
- Citations preserved
- Engine metadata included
- Encrypted and matter-isolated
- Never used in RAG or cross-matter analysis

**Step 10: Audit Logging**

```
Log all operations:
  - Query received
  - Authorization check
  - Engines executed
  - Documents accessed
  - Response generated
  - User actions
  ↓
Store in audit_logs table:
  - timestamp
  - user_id
  - matter_id
  - action_type
  - details (JSON)
```

**Audit Trail:**
- All queries logged
- All document access logged
- All engine executions logged
- All privilege decisions logged
- Complete traceability for compliance

7.12.3 Key Technical Details

**Matter Isolation Enforcement:**
- Every database query includes `WHERE matter_id = ?`
- Vector search scoped to matter namespace
- No cross-matter data visible without explicit authorization
- RLS policies enforce isolation at database level

**Performance Optimizations:**
- Query-first document selection reduces context size
- Pre-linking provides fast path for obvious queries
- Hierarchical retrieval (document → section → chunk) minimizes token usage
- Engine result caching for identical queries
- Incremental processing during ingestion

**Error Handling:**
- Graceful degradation if engine fails
- Retry logic for transient failures
- Circuit breaker for persistent failures
- Partial results when possible
- Clear error messages to users

**Security & Compliance:**
- Privilege detection blocks HIGH privilege documents from LLM
- Matter isolation enforced at every layer
- Audit logging for all operations
- Encryption at rest and in transit
- Role-based access control

✔️ End of PART 7