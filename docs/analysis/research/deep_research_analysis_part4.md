---
📋 **DOCUMENT STATUS: PHASE 2+ VISION - DEFERRED**
This document is part of the Deep Research vision (8 parts). See [deep_research_analysis_part1.md](./deep_research_analysis_part1.md) for full status information.
**For implementation, use:** [Requirements-Baseline-v1.0.md](../../../_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md)
---

4.1 REASONING PRINCIPLES (Mandatory)

The system must follow these principles for every answer:

1. Evidence First

AI cannot guess.
Every inference must link to:

an extracted text snippet

a document ID

a page number

or a retrieval result

If evidence is missing → state "Not determinable from provided materials."

Three-state logic for all findings:

- "Explicitly stated" — Directly found in document text
- "Implied but not explicit" — Can be inferred from context but not directly stated
- "Not determinable from record" — Cannot be determined from provided materials

Never use:
- "Likely"
- "Must have"
- "Implies intent"

2. Statutory Grounding

If interpreting process chains or duties:

Always cite the specific Act section

Do not interpret intent or liability

Only compare what documents show vs. what the Act states

3. No Legal Advice

The system must not:

declare malpractice

assess wrongdoing

determine liability

suggest strategies

tell users “what will happen” in court

It only identifies factual patterns and discrepancies.

4. Neutral Language

Outputs must avoid:
❌ Should
❌ Must
❌ Likely violated
❌ Strong case
❌ Weak case

Instead use:
✔ “Document A shows…”
✔ “Section 12 states…”
✔ “These timelines differ by…”
✔ “This step is not found in provided materials”

5. Declarative, Transparent Reasoning

Include:

what was found

how it was found

why it may matter

what is unknown

confidence level

4.2 RAG ARCHITECTURE (Document Retrieval Pipeline)

The system retrieves data using matter-isolated retrieval.

User Query
    ↓
Query Guardrails Layer (NEW)
    - Query classification (safe/unsafe/needs rewriting)
    - Query rewriting service
    - Soft warnings for borderline queries
    ↓
Query Classifier (safe vs unsafe)
    ↓
Engine Router (select engines)
    ↓
RAG Layer (matter-specific)
    - vector search
    - metadata filters
    - entity linking
    - page-level chunking
    ↓
Evidence Pack
    ↓
Reasoning Prompt
    ↓
Language Policing Service (NEW)
    - Real-time language linting
    - Blocked word detection
    - Mandatory suffix injection
    ↓
Structured Output

RAG Rules:

Only documents from the same matter may be retrieved

No cross-matter comparisons unless explicitly authorized and anonymized

Every retrieved chunk must be tied to:

matter_id

document_id

page_reference

timestamp

OCR confidence

All retrieval operations MUST include an explicit matter_id.
Retrieval requests without a valid matter_id are rejected.

4.3 REASONING MODES

The system supports multiple reasoning paths depending on the task.

Mode A — Extraction Reasoning (Ground Truth Layer)

Used for:

timelines

events

statements

parties

amounts

dates

Prompt must request:

exact span extraction

page numbers

canonicalization (normalize formats)

Template:
Extract the following factual elements from the Evidence Pack.
Do not infer anything not explicitly stated.

Required:
- Exact dates
- Exact quotes (with page numbers)
- Party names as written
- Document type
- Event labels

If information is missing or ambiguous, explicitly state:
"Not determinable from provided materials."

Mode B — Comparison Reasoning (Cross-document consistency)

Used for:

contradictions

mismatched statements

event order conflicts

Template:
Compare statements across documents.

For each potential inconsistency:
- Quote both statements
- Provide doc ID + page
- Identify the topic (ownership, custody, dates, amounts)
- Describe the nature of inconsistency (date mismatch, fact contradiction)
- Do NOT determine which is correct.

Mode C — Process Chain Reasoning (Understanding-Based)

This is the most advanced mode and central to your system.

It creates:

required steps

actual steps

missing steps

deviations from Act-defined procedure

Template:
Given:
- The statutory process defined in [Act Sections]
- Extracted steps from documents

Construct two chains:
1. Expected Process Chain (Act-based)
2. Observed Process Chain (Document-based)

Compare them:
- Identify missing steps
- Identify reversed order
- Identify unsupported jumps
- Identify inserted steps not appearing in statutes

Use only evidence provided.
Do NOT conclude wrongdoing.

Mode D — Pattern Analysis Reasoning

Used for:

time gaps

anomaly detection

selective citation patterns

outlier timelines

Template:
Compute:
- Average duration for each step (from baseline corpus)
- Current matter’s duration
- Standard deviation

Report:
"[Step] took X days. Baseline is Y ± Z. Deviation: N standard deviations."

Do NOT interpret why deviation occurred.

4.4 Language Policing Service

Purpose:

Enforce neutral language at generation time, not post-processing.

This is critical for legal safety and stress test compliance.

Functionality:

Real-time language linting during LLM generation:

- Monitors output as it's generated
- Detects blocked words/phrases
- Triggers rewrite if blocked language detected
- Injects mandatory disclaimers

Blocked words (absolute prohibition):

- "violates"
- "illegal"
- "liable"
- "guilty"
- "fraud"
- "malpractice"
- "wrongdoing"
- "forged"
- "fake"
- "fabricated"
- "fraudulent"

Blocked phrases:

- "constitutes a violation"
- "is illegal"
- "is liable"
- "is guilty"
- "committed fraud"
- "violated the law"

Mandatory suffix on all findings:

"This is a factual signal requiring attorney review."

Enforcement:

- Applied at generation time (not post-processing)
- LLM prompts include language restrictions
- Output validation layer checks before returning to user
- Failed outputs trigger automatic rewrite

Integration:

- Runs after reasoning prompt but before structured output
- Integrated with all engines
- Logs all blocked language attempts for audit

This ensures LDIP never crosses the legal advice boundary.

4.5 Explainability Mode (Judge-Safe)

Purpose:

Provide complete transparency for every finding.

If a senior asks "Where did this come from?", LDIP must show the complete reasoning chain.

Requirements:

Every finding must show:

- Exact text
  - Full quote from source document
  - No summarization that changes meaning
  - Exact location (document ID, page, paragraph/line)

- Exact location
  - Document identifier
  - Page number
  - Paragraph number (if available)
  - Line number (if available)
  - Section/chapter reference (if applicable)

- Why it was flagged
  - Plain English explanation
  - What pattern was detected
  - What anomaly was observed
  - What comparison was made

- What rule/template triggered it
  - Engine name
  - Detection rule ID
  - Template name (if applicable)
  - Statutory reference (if applicable)

Display format:

"Finding: [description]"

"Source: Document [ID], Page [X], Paragraph [Y]"

"Exact Text: '[quote]'"

"Detection Rule: [Engine Name] - [Rule ID]"

"Reason: [plain English explanation]"

"Confidence: [High/Medium/Low]"
"Confidence Score: [0-100]%"
"Confidence Reasoning: [explanation of why this confidence level]"
"Baseline Comparison: [how this compares to similar cases, if available]"

For Process Chain Engine findings specifically:
- Confidence based on template component type (required_steps = higher confidence, optional_steps = lower confidence)
- Confidence adjusted by baseline statistics (if available in Phase 2+)
- Confidence includes reasoning: "Required step per template. Missing in only 2% of authorized matters."

"If any component is missing → finding downgrades to:"

"'Low confidence – informational only'"

Use cases:

- Senior attorney verification
- Court defensibility
- Bar Council review
- Internal audit
- Junior lawyer learning

No black boxes.

Every finding must be fully traceable and defensible.

4.6 Query Guardrails System

Purpose:

Prevent junior lawyers from accidentally asking questions that imply legal conclusions.

Query Classification:

- Safe queries (allowed):
  - Factual retrieval
  - Pattern analysis
  - Timeline queries
  - Citation verification
  - Consistency checks

- Unsafe queries (blocked):
  - Legal strategy questions
  - Outcome prediction
  - Fault/liability questions
  - Legal advice requests

- Needs rewriting:
  - Questions that can be reframed as factual inquiries
  - Borderline questions that need clarification

Query Rewriting Service:

- Automatically rewrites unsafe queries
- Provides explanation for rewrite
- Suggests safe alternatives
- Logs all rewrites for audit

Soft Warnings:

- "This question may imply a legal conclusion"
- "Consider reframing as a factual inquiry"
- "This requires attorney judgment"

Integration:

- Runs before query classifier
- Integrates with orchestrator
- All blocked/rewritten queries logged

This prevents misuse and builds trust.

4.7 PROMPT FRAMEWORK

Every engine receives a reasoning prompt with:

1. System Instructions

Hard safety rules
Evidence-binding
Allowed operations
Forbidden inferences

2. Context Block

Act sections (retrieved)

Definitions

Entity mappings

Relationship graph

3. Evidence Pack

Extracted document chunks

OCR text

Metadata

Previous engine outputs (if allowed)

4. Task Instructions

Engine-specific steps (timeline, consistency, chain, gap-checker)

5. Output Schema

JSON-only
Follows Part 3's engine contracts

4.5 EVIDENCE BINDING (Mandatory Citations)

Every finding MUST include:

"evidence": {
    "document_id": "doc-12",
    "page": 8,
    "snippet": "…exact quoted text…",
    "retrieval_confidence": 0.92
}

For Process Chain Engine findings, additionally include:

"confidence": {
    "score": 0.92,
    "level": "High",
    "reasoning": "Required step per template. Missing in only 2% of authorized matters.",
    "baseline_comparison": "Present in 98% of similar cases",
    "template_component": "required_steps"
}

AI is forbidden from:

paraphrasing without snippet

summarizing without citation

referring to missing documents

creating synthetic evidence

4.6 UNCERTAINTY HANDLING

The model must explicitly state limitations:

- “OCR confidence low for 7 pages.”
- “Date unclear due to scan quality.”
- “Custodian log incomplete for 2015–2018.”


If inference cannot be made:

"determination": "Not possible from provided materials"

4.7 REASONING SAFEGUARDS (Critical)
Prevent:

❌ hallucinated law
❌ hallucinated facts
❌ cross-matter leakage
❌ strategic advice
❌ liability conclusions
❌ causation statements (“because they did X…”)

Force:

✔ step-by-step transparency
✔ explicit use of evidence
✔ separate "found vs. not found"
✔ disclaimers
✔ confidence scoring
✔ human-in-the-loop confirmation

4.8 OPTION 2 → OPTION 3 ALIGNMENT (Future-Proofing)

Because engines follow a strict IO contract and prompts follow strict templates, the system can evolve into:

Option 3 — Bounded Adaptive Orchestration

Where:

Orchestrator Component → performs deterministic query planning (one-time strategy generation)

Timeline Engine → builds event graphs (same deterministic engine)

Citation Engine → verifies statutory accuracy (same deterministic engine)

Process Chain Engine → finds deviations (same deterministic engine)

Consistency Engine → compares statements (same deterministic engine)

Authenticity Engine → maps identity changes (same deterministic engine)

Pattern Engine → finds anomalies (same deterministic engine)

Bounded adaptive orchestration uses deterministic planning and bounded loops to coordinate engine calls. The reasoning rules from Part 4 remain unchanged.

Bounded adaptive orchestration will only orchestrate engine calls via deterministic planning and bounded iterative execution, not replace them.

For full details on bounded adaptive computation, see Part 8.


4.9 WHEN TO STOP THE MODEL FROM REASONING (Revised with Authorization Logic)

The system must refuse and return a safety fallback when:

evidence is insufficient

question requires legal conclusions

question asks for strategy

question requests cross-matter inference without authorization

privilege-risky content is involved

Revised Fallback Template (with authorization instruction)
This question requires information from another matter or file that you
are not currently authorized to access.

To maintain ethical walls and prevent cross-matter leakage, I can only
analyze documents and facts within the current matter: [Matter Code].

If you *do* have authorization for the other matter(s), please specify:

• The exact matter codes you want included
• Confirmation that the firm has granted you cross-matter access
• Whether the comparison should include only:
    - Public judgments, or
    - Confidential documents from authorized matters

Without explicit authorization, I will restrict analysis to the current
matter only.

🔍 Why this is important
✔️ Removes ambiguity

Users understand exactly why the system stopped.

✔️ Gives a clear path forward

If the user is authorized, they now know what to specify.

✔️ Prevents unsafe "silent failures"

The system never pretends nothing is missing.

✔️ Lawyer-friendly UX

Senior partners expect clean procedural clarity.

✔️ Perfectly aligned with ethical walls

The system never guesses, never pulls forbidden data.

🔐 Bonus: A second variant for PUBLIC judgments

Sometimes a user wants to compare with public cases only.

Add this variant:

I can compare this matter with PUBLIC court judgments without any
special authorization, since these documents are not confidential.

Please confirm:
• Should I compare only statutory logic?
• Or also compare patterns from public judgments?

I will not access or reference confidential documents from other
matters unless explicit authorization is provided.


This avoids unnecessary blocking in research mode.

4.10 RAG OPTIMIZATION & CACHING STRATEGY

The system MUST use Retrieval-Augmented Generation (RAG) in a cost-efficient, accuracy-preserving way.
This section defines which optimizations are in-scope for MVP and which are Phase 2+.

The goals are:

Minimize token usage per query

Avoid re-computing the same work

Improve retrieval quality (get the right context, not just more context)

Preserve strict matter isolation and evidence binding

4.10.1 Document-Level Preprocessing (MVP)

For every ingested document, LDIP MUST perform the following one-time steps:

Document Summary (1–2 pages)

Parties and roles

Key dates and events

Acts and sections cited

Main issues and relief sought

Procedural posture (if determinable)

Section-Level Summaries (for large documents)

For major sections (e.g., “Facts”, “Arguments”, “Order”, “Affidavits”)

Short summaries that capture:

what this section covers

who is involved

which Acts/sections are discussed

Structured Fact Tables
For each document and matter, LDIP MUST extract and store:

Parties & roles (custodian, company, claimant, respondent, judge, counsel, etc.)

Events:

date, type, description, document_id, page

Act/section citations:

act_name, section_number, document_id, page

Monetary amounts, share counts, ISINs/certificate numbers where present

Basic document classification (order, application, reply, judgment, etc.)

These precomputed artifacts are stored as structured data and are accessible to engines without invoking the LLM repeatedly.

4.10.2 Hierarchical Retrieval (MVP)

RAG retrieval MUST be hierarchical, not flat:

Step 1 – Document Selection

Use:

document summaries

metadata (dates, party, doc type, Act sections)

Select a small set of candidate documents relevant to:

the user’s question

the selected engine (timeline, process chain, etc.)

Step 2 – Section / Region Selection

Within candidate documents, use:

section-level summaries

keyword search (e.g., section numbers, names, “demat”, “benami”, etc.)

Narrow to relevant sections/pages.

Step 3 – Chunk-Level Retrieval

Within selected sections, use:

vector search over chunks

Apply relevance + redundancy control (see 4.10.4).

Only the final set of highly relevant chunks forms the Evidence Pack for reasoning.

4.10.3 Hybrid Search (MVP)

LDIP MUST support hybrid retrieval:

Lexical / keyword search (BM25 or equivalent) for:

section numbers (e.g., “Section 12”, “Sec. 15(3)”)

party names and aliases

explicit phrases (“benami shareholder”, “dematerialisation request”)

Vector / semantic search for:

paraphrased concepts

indirect references (“wrongfully holding shares”, “disputed ownership”)

Retrieval MUST combine both signals, with tuneable weighting.
This is especially critical for legal text where exact formats (citations, names) matter.

4.10.4 Redundancy & Diversity Control (Phase 2)

To avoid flooding the LLM with repetitive content, LDIP SHOULD (Phase 2):

Use Maximal Marginal Relevance (MMR) or equivalent to:

prioritize relevance

penalize near-duplicate chunks

Ensure the Evidence Pack includes:

coverage of all key events/positions

minimal repetition of the same paragraph across documents

This improves clarity and reduces tokens.

4.10.5 Role-Aware Retrieval (Phase 2)

LDIP SHOULD support role-aware retrieval using metadata on party roles:

Filter or weight evidence by:

custodian actions

company actions

Mehta family actions

registrar, depository, exchange, etc.

Example:

For a query: “Any lapses on the custodian’s part under the Torts Act?”, retrieval SHOULD:

prefer documents/sections tagged with role = “custodian”

include relevant Act sections defining custodian duties

This improves precision for party-specific analysis.

4.10.6 Engine Result Caching (MVP)

LDIP MUST cache engine outputs at the matter level:

Per matter, per engine, per configuration, store:

inputs (filters, parameters)

outputs (findings, limitations, documents_considered)

timestamp and engine version

Engines MUST:

Check for a valid cached result before recomputing.

Recompute only when:

new documents are added

engine version changes

filters materially differ

Examples:

Timeline engine result reused by:

process chain engine

pattern/anomaly engine

user queries about dates and event sequences

This avoids repeated full scans of the same matter.

4.10.7 Q&A Cache per Matter (MVP)

LDIP MUST maintain a Q&A cache per matter:

Cache entries include:

normalized question

answer (in structured format)

engines used

evidence citations

timestamp

When a new question arrives, the system MUST:

Check for an exact match → return cached answer (with a “from cache” indicator).

Optionally (Phase 2), check for semantically similar questions:

If similarity is high, MAY:

reuse the answer, or

show:

“A similar question was answered earlier. Reuse this result or run a fresh analysis?”

All cached answers remain subject to:

matter isolation

versioning (Act versions / engines)

basic staleness checks (e.g., new documents added since)

4.10.8 Multi-Hop Retrieval (Phase 2)

For complex queries, LDIP MAY perform multi-hop retrieval:

First hop:

Retrieve all mentions of a key concept (e.g., “benami status of Nirav”, specific share certificates).

Second hop:

From those references, retrieve:

all events involving that asset

all custodian actions around those dates

cross-file mentions in the same matter

Optional third hop:

Retrieve judgments or other matters (where authorized) involving the same party/asset for pattern comparison.

All hops remain matter-scoped unless explicit cross-matter authorization is provided (see ethics & isolation sections).

4.10.9 Cross-Matter Baseline Statistics (Phase 2+, Restricted)

For anomaly/pattern detection, LDIP MAY compute baselines across:

public judgments, and/or

explicitly authorized internal matters.

These baselines may include:

typical duration of dematerialisation

typical notification timelines

distribution of processing times by custodian

common patterns of section usage (e.g., Sections 12 + 15 often cited together)

Strict rules:

Baselines MUST be aggregated and anonymized

No individual client details exposed

No confidential document content reused verbatim

No specific other matter may be named unless:

it is a public judgment, or

explicit cross-matter authorization exists.

Outputs MUST be phrased as:

“In N comparable matters, the median duration was X days (IQR: A–B).
This matter: Y days.”

No cross-matter factual leakage beyond what is ethically allowed.

4.10.10 Alignment with Engine Architecture

All RAG optimization and caching strategies MUST:

Respect the engine I/O contracts defined in Part 3

Respect matter isolation and ethical walls

Preserve evidence traceability (documents_considered, citations)

Avoid changing engine semantics (only retrieval efficiency and quality)

Engines remain stateless, read-only analyzers.
RAG + caching determine what evidence they see, not how they reason.


4.11 QUERY ORCHESTRATION PIPELINE (NEW)

This section explains how the system executes a user query end-to-end, using all rules defined in 4.1–4.10.

The orchestrator MUST follow these steps in sequence.

STEP 0 — INPUT & MATTER CONTEXT LOADING

Inputs captured:

user_id

matter_id

user_query

optional: filters (date ranges, doc type, party)

session metadata

The orchestrator MUST:

Verify that the matter exists

Load matter metadata:

party dictionary

document inventory

precomputed summaries (Part 4.10.1)

act sections relevant to this matter

Load Matter Memory Files from `/memories/{matter_id}/`:

Check for `recent_queries.xml` (query summaries for continuity)

Check for `timeline_summary.xml` (pre-computed timeline)

Check for `entity_mapping.xml` (party and role summaries)

Validate all paths to prevent directory traversal (must stay within `/memories/{matter_id}/`)

Memory files will be included in context building (STEP 3)

Apply matter isolation immediately (no external data visible)

If the matter is frozen (conflict, privilege, admin lock), return a safety refusal.

STEP 1 — AUTHORIZATION & ETHICAL WALL CHECK

Before any retrieval occurs:

Check that the user has access to this matter

Check whether the query mentions entities tied to other matters

If cross-matter access is needed:

Reject request per 4.9

Provide fallback prompt with authorization instructions

If the user includes explicit authorization:

Load only the authorized additional matters

Apply anonymization rules (4.10.9)

STEP 2 — QUESTION CLASSIFICATION (Safety Router)

Apply the framework in Part 3:

SAFE types → proceed

UNSAFE types → trigger the fallback template (4.9)

Classification outputs:

{
  "question_type": "timeline" | "citation" | "consistency" | "process_chain" | "pattern" | "disallowed_strategy" | "legal_conclusion" | ...
  "required_engine": "timeline_engine" | "citation_engine" | ...
}

STEP 3 — CONTEXT BUILDER

Using the question classification, the orchestrator MUST load:

relevant Act sections

relevant definitions

party-role mappings

relationship graph (same individual across alias variations)

precomputed summaries (document-level, section-level, facts tables)

This block becomes the top part of the reasoning prompt (see 4.4).

STEP 4 — RETRIEVAL LAYER (Hierarchical RAG + Pre-Linking)

Using rules from 4.2 and 4.10, the system MUST perform:

Step 4A — Pre-Linked Relationship Retrieval (Fast Path)

First, check pre-linked relationships:

If query involves entities/relationships that were pre-linked during ingestion:
  - Retrieve pre-linked relationships from Structured Fact Store
  - Use pre-linked entity mappings from MIG
  - Use pre-linked event-entity associations
  - Use pre-linked citation-document mappings

This provides:
  - Fast retrieval for obvious connections
  - Deterministic results
  - Reduced query-time computation

If pre-linking covers the query needs:
  - Proceed directly to engine execution (skip 4B-4D)
  - Use pre-linked data as Evidence Pack

If query requires novel pattern discovery:
  - Use pre-linking as starting point
  - Proceed to hierarchical RAG (4B-4D) for additional context

Step 4B — Document Selection

Use:

metadata

section numbers

entity matches (from pre-linking and MIG)

doc-type relevance (citations, affidavits, orders, logs)

pre-linked relationships (as hints for document relevance)

Filter down to the smallest possible set.

Step 4C — Section Selection

For each selected document:

fetch section-level summaries

match keywords, legal terms, entity references

use pre-linked entity-document mappings

identify relevant pages/regions

Step 4D — Chunk-Level Vector Search

Over the identified regions only:

apply semantic retrieval

ensure chunk deduplication (Phase 2 MMR rules)

Step 4E — Evidence Packaging

Construct an Evidence Pack:

{
  "chunks": [...],
  "document_ids": [...],
  "page_refs": [...],
  "pre_linked_relationships": [...],
  "entity_mappings": [...],
  "ocr_confidence": {...},
  "retrieval_confidence": {...}
}


Every item MUST include matter_id, document_id, page.

No evidence from unauthorized matters may appear.

Pre-linked relationships are included to provide fast context for engines.

STEP 5A — ADAPTIVE PLANNING (One-Time, Phase 2+)

For complex queries requiring novel pattern discovery or cross-matter analysis:

The orchestrator performs one-time adaptive planning:

Analyze query complexity:
  - Does query require novel connection discovery?
  - Does query require cross-matter analysis?
  - Does query require iterative pattern clustering?

Determine execution strategy:
  - Which engines to call
  - In what order
  - Whether bounded loops are needed
  - What stop conditions apply

Define bounded loops (if needed):
  - Loop type (connection discovery, pattern clustering, multi-hop traversal)
  - Stop conditions (max iterations, no new findings, time limits, user checkpoints)
  - Seed data (starting entities, documents, relationships)

Planning is:
  - One-time (not iterative)
  - Deterministic (same query → same plan, given same context)
  - Fast (<2 seconds typically)

If query is simple (uses only pre-linked relationships):
  - Skip adaptive planning
  - Proceed directly to engine execution

STEP 5B — ENGINE EXECUTION (Reasoning Layer)

Based on classification result and adaptive plan (if any), the orchestrator calls one of:

Extraction Engine

Consistency Engine

Process Chain Engine
  - Composite template matching:
    - Check required_steps (strict - MUST occur)
    - Check optional_steps (flexible - CAN occur)
    - Check order_flexible steps (order-independent)
    - Check timing_constraints (timing deviation detection)
    - Generate confidence scores for all findings

Pattern Engine

Citation Engine

(Future) Authenticity Engine

Mode A–D from 4.3 define the exact reasoning template used.

The prompt includes:

System instructions (4.1 + 4.7)

Context Block (Step 3)

Evidence Pack (Step 4)

Pre-linked relationships (from ingestion)

Task Instructions (engine-specific)

Output Schema (Part 3 formats)

ENGINE MUST NOT hallucinate missing evidence.
If evidence is insufficient:
→ Return "not_determinable" fields as defined in 4.6.

STEP 5C — BOUNDED LOOP EXECUTION (Phase 2+, If Planned)

If adaptive planning determined bounded loops are needed:

Execute loops with explicit stop conditions:

Connection Discovery Loop:
  - Start from pre-linked entities
  - Traverse multi-hop connections
  - Stop on: max iterations, no new findings, time limit, user checkpoint

Pattern Clustering Loop:
  - Cluster anomalies and patterns
  - Stop on: max iterations, cluster stability, time limit

Cross-Matter Analysis Loop (if authorized):
  - Match entities across authorized matters
  - Stop on: max matters, max entities, no new connections, time limit, user checkpoint

Each loop iteration:
  - Logs iteration count
  - Checks stop conditions
  - Records findings
  - Respects matter isolation and privilege filters

When stop condition triggers:
  - Loop terminates immediately
  - Partial results returned (if applicable)
  - Stop condition logged for audit

All loop executions are:
  - Deterministic (same inputs → same outputs, given same stop conditions)
  - Logged for audit (iterations, termination reason, findings)
  - Subject to all safety rules from Parts 3, 4, 5, 6, 7

STEP 6 — POST-PROCESSING & VALIDATION

The orchestrator MUST:

✔ Validate citations

Check that every fact references a snippet + doc + page.

✔ Validate safety

Ensure no forbidden language (4.1.4, 4.7):

no “violation”, “wrongdoing”, “liable”, “they should have…”

✔ Add disclaimers

Inject standard Part-1 disclaimers automatically.

✔ Compute confidence score

Using Part 3’s confidence framework or Part 4.6 limitations.

✔ Normalize output schema

Ensure consistency across engines.

If validation fails → block output and re-run with a stricter prompt template.

STEP 7 — JOURNAL LOGGING (NEW — Connected to Part 6 & 7)

After producing the answer:

Check if the user has enabled Journal Logging

If YES:

Store:

the query

the structured output

citations

engine used

timestamp

Allow user to add optional notes

Journals are:

private to the user

matter-scoped

non-influential on future reasoning (not training data)

retained or destroyed per Part 5 retention rules

This gives lawyers continuity without corrupting evidence-based reasoning.

### Snippet Revalidation Step (MVP)

Before returning any answer to the user, the Orchestrator must:

- Re-fetch each cited snippet directly from the document store
- Verify that the retrieved text matches the snippet provided by the engine
- If any mismatch occurs, terminate the response with a "Not Determinable" outcome and log the inconsistency


STEP 8 — RESPONSE FORMATTING

Output packaged into:

Structured JSON

Followed by a formatted human-readable view

Disclaimer footer

Confidence section

Limitations section

"Documents considered" section

Always include:

query_id (for audit trail)

documents_considered (for transparency)

STEP 8.5 — MATTER MEMORY FILES UPDATE

After response formatting, update Matter Memory Files:

Append query summary to `recent_queries.xml`:
  - Timestamp (ISO 8601 format)
  - Query snippet (user's question, truncated if needed)
  - Engine(s) used (comma-separated list)
  - Key finding (one-line summary of result)
  - Maintain FIFO: remove oldest query if limit (15-20) reached

Update `timeline_summary.xml` if timeline was modified by this query

Update `entity_mapping.xml` if new entities were discovered or entity relationships changed

Invalidate memory files if:
  - New documents were added to matter during this session
  - Privilege classification of any document changed
  - Matter Identity Graph was updated
  - Matter metadata was modified

All memory file operations:
  - Restricted to `/memories/{matter_id}/` directory
  - Path validated to prevent directory traversal
  - Logged for audit

STEP 9 — AUDIT LOGGING

Every query MUST log:

user_id

matter_id

question_type

engines invoked

documents_considered

time taken

whether journal entry was created

whether authorization was used

This supports compliance (Part 5).

4.12 ERROR HANDLING & EDGE CASE BEHAVIOR (NEW)
Case 1 — Missing Evidence

Output:

“Not determinable from provided materials.”

Never hallucinate missing parts.

Case 2 — Privileged / High-Risk Files

If a document is flagged HIGH (from Part 5 privilege scanner):

Block analysis

Require attorney override

If override missing → return safety refusal.

Case 3 — Unsafe Questions

Follow the fallback template from 4.9.

Case 4 — Cross-Matter Leakage Attempt

If the user mentions another case or party found in other matters:

AI must respond:

that access is restricted

authorization instructions

option to use public judgments only

Never reveal even the existence of confidential other-matter files.

Case 5 — OCR Failure or Ambiguity

If OCR < threshold:

Mark specific pages as low-confidence

Reduce confidence score

Insert limitation in output

Case 6 — Inconsistent Metadata

If timestamps, parties, or doc types conflict:

Engines surface contradictions (Mode B)

Orchestrator highlights ambiguity

Never guess which is correct.

Case 7 — Engine Error / Timeout

Fallback:

"The system could not complete the analysis due to an internal processing issue. No conclusions have been drawn."

No partial reasoning shown.

4.12.1 Engine Failure Recovery (Enhanced)

**Strategy: Graceful Degradation**

If one engine fails, other engines continue execution:

- **Partial Results:** Return findings from successful engines with clear indication of what failed
- **Retry Logic:** Automatic retry for transient failures (network timeout, rate limit, temporary service unavailability)
- **Circuit Breaker:** Stop calling failing engine after N consecutive failures
- **Error Types:**
  - **Transient Errors:** Network timeout, rate limit, temporary service unavailability → Retry once
  - **Permanent Errors:** Invalid input, corrupted data, engine bug → Skip with notification
  - **Partial Errors:** Engine returns partial results → Include with confidence adjustment

**Implementation Pattern:**
```python
class EngineOrchestrator:
    def run_engines(self, matter_id, query):
        results = {}
        failed_engines = []
        
        for engine in self.engines:
            try:
                result = engine.analyze(matter_id, query)
                results[engine.name] = result
            except TransientError as e:
                # Retry once
                result = engine.analyze(matter_id, query, retry=True)
                results[engine.name] = result
            except PermanentError as e:
                failed_engines.append(engine.name)
                log_error(f"{engine.name} failed: {e}")
        
        return {
            "findings": results,
            "failed_engines": failed_engines,
            "completeness": len(results) / len(self.engines)
        }
```

**Output Format:**
All engine results must include:
- `engine_status`: "success" | "failed" | "partial"
- `failed_engines`: List of engines that failed
- `completeness_score`: Percentage of engines that succeeded
- `warnings`: Any warnings about partial results

4.12.2 Privilege Detection Error Handling

**False Positive Handling:**
- **User Override:** Attorney can mark content as non-privileged
- **Confidence Threshold:** Only mask if confidence > 80%
- **Context Review:** Show masked content in context for attorney review
- **Learning:** Track overrides to improve detection (matter-scoped only)

**False Negative Handling:**
- **Post-Processing Review:** Attorney can manually flag privileged content
- **Audit Trail:** Log all privilege decisions for compliance
- **Escalation:** High-confidence privilege detection requires attorney approval before masking

**Implementation Priority:** MVP (Critical for safety)

4.13 MODEL VERSIONING & OUTPUT VALIDATION

4.13.1 Model Versioning Strategy

**Version Pinning:**
- **Fixed Model Versions:** Pin specific model versions (e.g., GPT-4-0613, Claude-3-Opus-20240229)
- **Version Registry:** Track which model version used for each analysis
- **Gradual Rollout:** Test new models on non-production matters first
- **Rollback Capability:** Ability to revert to previous model version

**Implementation:**
```python
class ModelVersionManager:
    def __init__(self):
        self.current_version = "gpt-4-0613"
        self.previous_versions = ["gpt-4-0314"]
        self.version_history = {}
    
    def get_model(self, version=None):
        version = version or self.current_version
        return LLMClient(version=version)
    
    def analyze_with_version(self, query, model_version=None):
        model = self.get_model(model_version)
        result = model.analyze(query)
        result.metadata["model_version"] = model_version or self.current_version
        return result
```

4.13.2 Output Validation

**Consistency Checks:**
- **Regression Testing:** Run test suite with new model version, compare outputs
- **Confidence Calibration:** Ensure confidence scores remain consistent
- **Output Format Validation:** Ensure structured outputs match expected schema
- **Citation Validation:** Verify citations remain accurate

**A/B Testing:**
- **Parallel Execution:** Run same query with old and new model versions
- **Comparison:** Compare outputs for significant differences
- **Approval Workflow:** Require attorney approval before switching models

**Implementation Priority:** Phase 2 (MVP can use fixed model version)

PART 4 Completed

This is your AI brain layer — the precise rules that make LDIP competent, safe, and scalable into a bounded adaptive computation future.