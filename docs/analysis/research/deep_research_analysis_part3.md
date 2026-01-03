---
📋 **DOCUMENT STATUS: PHASE 2+ VISION - DEFERRED**
This document is part of the Deep Research vision (8 parts). See [deep_research_analysis_part1.md](./deep_research_analysis_part1.md) for full status information.
**For implementation, use:** [Requirements-Baseline-v1.0.md](../../../_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md)
---

⭐ LDIP — Legal Document Intelligence Platform
PART 3 — Core Functional Architecture (Understanding-Based Detection Engines)
3.1 Overview

LDIP operates through eight coordinated detection engines, each responsible for a different dimension of "legal anomaly discovery."

These engines collectively support both modes you require:

✔️ Auto-Scan Mode

“Find any caveats, discrepancies, missing pieces, inconsistencies, suspicious sequences.”

✔️ Question-Driven Mode

“Check this one thing I’m worried about.”

All engines operate on the same RAG-backed understanding layer.

Where entities are involved, engines SHOULD prefer the MIG `entity_id` as the primary reference, and treat raw name strings as display-only fields.

3.2 Why LDIP Must Use Understanding + Pre-Linking (Option 2 → Bounded Adaptive Path)

Unlike a simple rule-based "50 checks" system, LDIP must handle:

process chains with variations

inconsistent naming

alternate spellings

contradictory statements

buried facts across 100+ files

case files that mention events indirectly

timelines that interlock across decades

actors with changing roles (claimant in one case, respondent in another)

authenticity (benami-like claims, recorded ownership inconsistencies across documents, custodial duties)

novel corruption patterns (especially in India context)

hidden connections that don't follow obvious patterns

These cannot be solved by keyword rules alone.

LDIP uses a hybrid approach:

Pre-Linking (Deterministic, During Ingestion):
- Extracts obvious relationships during document ingestion
- Fast, query-time access to pre-computed connections
- Covers standard patterns and obvious links

Understanding-Based Engines (Query-Time):
- Semantic understanding for complex analysis
- Handles variations, contradictions, indirect references
- Requires semantic understanding:
  - of who did what
  - of why something is suspicious
  - of what should have happened vs what happened
  - of how law + procedure interact
  - of how timeline → consequence → duty → breach chain flows

Bounded Adaptive Computation (Phase 2+, For Novel Patterns):
- Discovers hidden connections and novel corruption patterns
- Uses bounded loops with strong stop conditions
- Operates on top of pre-linking and engines

Therefore:

LDIP's Core Architecture = Pre-Linking + Understanding-Based Engines (Option 2)

with a planned evolution to:

Bounded Adaptive Computation (Phase 2+) for novel pattern discovery

3.21 Matter Identity Graph & Pre-Linking Layer (MIG)

LDIP maintains a **Matter Identity Graph (MIG)** as a shared layer used by multiple engines.

MIG is populated through **pre-linking** during document ingestion (see Part 7):

- Pre-linking extracts obvious, deterministic relationships during ingestion
- Creates initial identity nodes and edges in MIG
- Links entities to documents, events, and roles
- Provides fast, query-time access to obvious connections

Purpose:

- Normalize entities inside a single matter
- Resolve aliases (different spellings / formats of the same entity)
- Track roles and relationships over time
- Provide a stable `entity_id` that engines can use instead of raw names
- Enable fast retrieval of pre-computed relationships

Scope:

- MIG is **strictly matter-scoped**
- Every node and edge includes a `matter_id`
- No edges may connect entities from different matters
- Pre-linking is deterministic and immutable (not modified by engines)

Data model (conceptual):

- **Nodes**
  - people (`PERSON`)
  - companies (`ORG`)
  - families/groups (`GROUP`)
  - legal/institutional entities (`INSTITUTION`)
  - optionally assets like accounts, share certificates, ISINs (`ASSET`)

- **Edges**
  - `ALIAS_OF` — different names referring to the same underlying entity in *this matter*
  - `HAS_ROLE` — entity ↔ role in this matter (e.g. custodian, issuer, claimant)
  - `APPEARS_IN` — entity ↔ document (with page ranges)
  - `RELATED_TO` — introducer, family link, director of company, etc. (within this matter only)

Storage:

- Backed by the Structured Fact Store described in Part 7, using tables like:
  - `identity_nodes(matter_id, node_id, entity_type, canonical_name, metadata)`
  - `identity_edges(matter_id, edge_id, from_node, to_node, edge_type, metadata)`

Ownership:

- **Engine 6 — Entity Authenticity & Role Stability** is the primary builder/updater of MIG
- Other engines (Timeline, Process Chain, Contradiction, Pattern) are **readers** of MIG

Safety:

- MIG inherits all matter isolation, retention, and destruction rules from Part 2 and Part 5
- When a matter is destroyed, all MIG nodes/edges for that `matter_id` are also destroyed


3.3 The Eight Detection Engines (Core to LDIP)

### Engine Purity Rule (MVP)

All Engines are pure, read-only computation units.

- Engines MUST NOT mutate system state.
- Engines MUST NOT write to databases.
- Engines MUST NOT directly modify the Matter Identity Graph (MIG).

Any state mutation (including identity resolution, alias creation, or entity merging) must occur through a dedicated stateful service invoked explicitly by the Orchestrator.


These engines are the spine of the system.

Engine 1 — Citation Verification Engine

Purpose:
Check if statutory references are quoted fairly, accurately, and completely.

Detects:

misquoted statutory text

selectively omitted provisos

missing explanations

misaligned paraphrasing

citations that do not match the actual Act

overbroad interpretation

Output format (always neutral):

“Claimed text vs Actual text difference”

“Provisos not included in citation”

“Semantic deviation”

“Similarity Score”

This engine never says:
“wrongdoing,” “illegal,” “fraud,” “malpractice.”

Engine 2 — Timeline Construction & Deviation Engine

Purpose:
Reconstruct every procedural event in chronological order across all documents.

This includes:

applications

notices

correspondence

objections

custodian filings

dematerialisation requests

company actions

sale transactions

judicial dates

It also detects:

✔️ Missing events

"Notification not found in provided materials"

"No custodian acknowledgement present"

✔️ Suspicious durations

"Dematerialisation took 290 days (baseline 80 days)"

"Sale happened before verification step completed"

✔️ Causal red flags

"Share sale occurred before recorded ownership inconsistencies across documents were resolved"

"No document evidencing custodian action during an 8-month gap was found"

✔️ Silence, Delay & Absence Intelligence (Enhanced)

Indian cases hinge on what was not done.

LDIP must highlight:

- Unexplained delays
- Long gaps between steps
- Missing responses where response is expected
- Asymmetrical urgency (one party rushing, other silent)

This is not contradiction — it's procedural smell detection.

Three-state logic only:

- Present: Documented in record
- Explicitly absent: Document explicitly states non-occurrence
- Not determinable from record: Cannot determine from provided materials

Never uses:

- "Likely"
- "Must have"
- "Implies intent"

This protects against:

Nirav Jobalia–type demat-to-sale sequences

unnoticed benami shares being sold

custodial lapses

backdated document complications

Again: Never a legal conclusion.
Only factual timeline anomalies.

**Integration with MIG:**

- Uses MIG `entity_id`s instead of raw names when building per-party timelines
- Groups events by canonical entity (e.g. “Nirav D. Jobalia”, “N.D. Jobalia”, “Mr. Jobalia” → same timeline band)
- Reads from `identity_nodes` and `identity_edges(HAS_ROLE, APPEARS_IN)` to:
  - attach roles (custodian, company, claimant, etc.)
  - avoid double-counting the same person with different spellings

Engine 3 — Consistency & Contradiction Engine

Purpose:
Locate all contradictory statements across:

affidavits

filings

declarations

replies

company responses

custodian reports

earlier vs later filings

Detects:

conflicting dates

conflicting ownership claims

process contradictions

incompatible stories

changing positions of the same party

Example:

Party A states “we sent notice on 12 June” in Doc 5,
but earlier says “notice pending” in Doc 3.

Engine outputs:

contradiction summary

document references

page numbers

extracted statements

nature of conflict

**Integration with MIG:**

- Uses MIG `entity_id`s to detect contradictions made by the **same** party across multiple documents
- Example: “Nirav D. Jobalia” vs “Nirav Jobalia” vs “Mr. N. Jobalia” are treated as the same speaker
- Contradiction pairs are stored using `entity_id`, doc_id, and page so that future queries can ask:
  “Show me all inconsistent statements made by this entity in this matter.”


Engine 4 — Documentation Completeness & Gap Engine

Purpose:
Check if the set of provided documents contains:

all expected filings

all required custodian notices

all demat process documents

all chain-of-ownership proofs

all payment proofs

all company acknowledgements

Detects:

missing proofs

missing notice confirmations

missing signatures

missing transfer forms

missing demat instructions

steps you expect in a process but don’t see anywhere

Output:

“5 expected document types not found in ingested material.”

Again:
Missing does NOT mean “it doesn’t exist,” only:
not found in what was ingested into LDIP’s RAG index.

Engine 5 — Process Chain Integrity Engine (Your most unique requirement)

This engine is your competitive advantage.

Purpose:

reconstruct ANY process, even if corrupt, defective, or incomplete

understand multi-step legal/procedural workflows from data itself

detect deviations or manipulations in process flow

Works for:

dematerialisation

share transfers

custodian procedure

company verification

exchange filings

judicial sequences

notices and counter-notices

✔️ It does NOT rely solely on rigid templates.

It learns the chain from:

evidence in the documents

the statute

baseline patterns (if present)

**Process-Chain Templates (Domain-Specific)**

LDIP includes domain-specific templates for common processes:

- Demat / securities
- Company law filings
- Employment termination
- Regulatory notices
- Tender / procurement
- Arbitration timelines

Each template includes composite structure:

- **Required steps** (MUST occur) - Strict check, missing = CRITICAL
- **Optional steps** (CAN occur) - Flexible check, allows variants
- **Order flexible steps** - Order doesn't matter, handles sequence variations
- **Timing constraints** - Step-to-step timing requirements (e.g., Step1_to_Step3: "< 30 days")
- Mandatory documents
- Statutory deadlines
- Typical actors/roles

Templates are used as baselines but do not override evidence from documents.

Composite template structure handles 70-80% of variants without new templates:
- Check required steps (strict)
- Allow flexible ordering on optional steps
- Flag timing deviations with confidence
- No overhead, accuracy maintained

If documents show a different sequence, LDIP flags it as deviation while still recognizing what actually occurred.

**Important:** LDIP does not learn or generate new process templates. Template expansion follows strategic quarterly review process:
- Phase 1 MVP: 5-8 core templates
- Phase 1.5 (Month 3-4): Analyze actual user queries, add 2-3 templates for high-frequency case types (data-driven, not guessed)
- Phase 2: Add 2-3 more templates as patterns emerge, quarterly reviews (analyze 1000 queries every 3 months, add template only if 10%+ of cases need it)
- Phase 3: Bounded adaptive computation with learned baselines

In Phase 2 (Post-MVP), LDIP may learn aggregate statistics such as typical durations, common blockages, and frequency of missing documents, but processes themselves remain pre-defined institutional workflows, not learned behavior.

### What LDIP Means by "Process"

In LDIP, a "process" refers to a repeatable, institutionally enforced execution workflow that occurs outside the courtroom and can be blocked or unblocked by documents.

Processes are pre-defined and versioned by the LDIP team.

User documents never create new processes; they only activate, block, or contextualize existing ones.

### Template Selection Logic

When multiple process templates are available for a given matter, LDIP must prefer the template version in force at the time the relevant real-world action should have occurred, not the most recent version. This avoids retroactive law application, which is a major litigation risk.

For example, if a matter involves actions from 2020, LDIP should use the template version that was in force in 2020, even if a newer version exists in 2024.

✔️ It handles corrupt/missing processes.

If documents show:

steps done out of order

steps skipped

steps backdated

steps replaced with improper alternatives

steps done by wrong party

steps done too fast or too slow

LDIP will detect it.

This engine is what catches:

Nirav selling shares before rightful owners were notified

company approving demat without KYC-proof

custodian not blocking benami shares

contradictory handling between two similar cases

Output examples with confidence scoring:

"Sale executed before dematerialisation completed."
  Confidence: 92% - Required step sequence violation

"Ownership verification step missing."
  Confidence: 95% - Required step per template. Missing in only 2% of authorized matters.
  See evidence: Page 5, Line 12.

"Custodian acknowledgment absent before transfer."
  Confidence: 88% - Required step missing. Present in 98% of similar cases.

"Sequence inconsistent with typical compliance chain."
  Confidence: 65% - Optional step order variation. Present in 40% of cases.

**Integration with MIG:**

- Uses MIG to understand **which entity performed which step** in the process
- When verifying required steps, associates each step with a stable `entity_id`
  (e.g. custodian vs company vs registrar) based on `HAS_ROLE` edges
- This ensures process-chain checks remain correct even if entity names vary across documents


Engine 6 — Entity Authenticity & Role Stability Engine

Purpose:

Identity authenticity (benami risk patterns)

Role evolution (claimant → beneficiary → seller across different filings)

Corporate alias detection (inside the same matter)

Surname/relationship-based inference

Appearance tracking across documents

Detects:

persons appearing with multiple company names

beneficiaries who contradict themselves

parties whose claims change over time

entity relationships (Payal–Ashwin–Jobalia network)

unexplained possession of shares

This is the key engine for:

“How did Nirav get these shares?”

“Who actually holds beneficial ownership?”

“Who has changing positions across filings?”

Output is factual, not legal.


**Integration with MIG (Primary Owner):**

- Engine 6 is the **primary builder and maintainer** of the Matter Identity Graph (MIG)
- Inputs:
  - extracted entities from documents (names, roles, addresses, IDs where present)
  - document metadata (matter_id, doc_id, page ranges)
  - heuristic/LLM-proposed alias candidates (e.g. fuzzy name matches)

- Responsibilities:
  - Create `identity_nodes` for new entities within a matter
  - Propose and, where confidence is high, create `ALIAS_OF` edges between nodes
  - Create `HAS_ROLE` edges (entity ↔ role) scoped by matter and optionally time
  - Create `APPEARS_IN` edges linking entities to documents/pages

- Outputs:
  - a stable `entity_id` that other engines use instead of raw names
  - an audit trail of alias decisions and role assignments (with confidence scores)

- Safety Constraints:
  - All node/edge operations scoped to a single `matter_id`
  - No cross-matter aliasing or linking
  - Low-confidence alias suggestions may be surfaced to users for review but are not auto-committed without a threshold

Engine 6 produces identity resolution suggestions only.

- Outputs consist of proposed entities, aliases, and relationships.
- Engine 6 MUST NOT write directly to the Matter Identity Graph.
- All MIG updates derived from Engine 6 outputs require Orchestrator approval and are applied via the MIG Update Service.


3.4 How the Engines Work Together

When the user asks:

"Find anything that can backfire on us regarding the custodial process."

LDIP runs:

Timeline Engine — sequence check, silence/delay detection

Process Chain Engine — deviation detection, template comparison

Documentation Gap Engine — missing notices

Consistency Engine — contradictory statements

Citation Engine — statutory mismatch

Entity Authenticity Engine — role irregularities

Admissions Detector — explicit/partial admissions, non-denials

Pleading Mismatch Engine — document-pleading disconnects

Then synthesizes:

factual anomalies

missing pieces

contradictory claims

deviations from expected patterns

admissions and non-denials

pleading-document mismatches

WITHOUT labeling anything "wrongdoing."

3.5 Auto-Scan Mode (Full Case Scan)

Auto-scan includes:

timeline reconstruction (with silence/delay detection)

contradictions

missing docs

process integrity (with template comparison)

citation comparison

entity authenticity

admissions and non-denials

pleading-document mismatches

anomaly clustering

Output is a neutral findings report, e.g.:

"Sale executed 14 days before demat acknowledgment."

"Custodian did not issue notice (not found in ingested docs)."

"Claim of ownership inconsistent with earlier affidavit."

"Company stated X in 2018 filing but Y in 2020 filing."

"Party A admitted [fact] in Document X, page Y."

"Pleading claims X but supporting document only shows Y."

3.6 Question-Driven Mode (User Inquiry)

Examples:

Q:
“Did any party act outside the Torts Act process chain?”

A:
LDIP runs only:

process chain engine

timeline engine

citation engine

Q:
“What contradictions exist in Jobalia filings?”

A:
LDIP runs the contradictions engine and entity authenticity engine.

Q:
“Any missing notices during dematerialisation?”

A:
LDIP runs the documentation gap engine and timeline engine.

3.7 Guaranteed Safety Interlocks in Engine Behavior

All engines must enforce:

✔️ No legal conclusions
✔️ No strategy suggestions
✔️ No assigning blame
✔️ No cross-matter reasoning
✔️ No prediction of outcomes
✔️ Neutral language only
✔️ Citation binding
✔️ Evidence traceability
3.8 How Option 2 Evolves to Option 3
Option 2 (Understanding Engine) supports:

factual extraction

process inference

anomaly detection

identity linking

multi-document cross-reference (within matter)

Option 3 (Bounded Adaptive Computation) adds:

enhanced orchestration with bounded iterative execution

deterministic query planning (one-time strategy generation)

bounded loops for multi-hop relationship discovery

iterative pattern clustering with explicit stop conditions

task decomposition via deterministic planning ("first build timeline → then check chain → then find contradictions")

automatic re-checking when new documents appear (via bounded loops)

Because LDIP is built around the 8 engines, the upgrade path is natural.

Engine functions remain the same.
Only orchestration gains bounded adaptive capabilities (deterministic planning + bounded loops).

For full details on bounded adaptive computation, see Part 8.

PART 3.9 — ENGINE INTERFACE CONTRACTS 
(This makes all engines compatible with future MCP tools, orchestrators, and bounded adaptive computation)

Each analytical engine in the system MUST behave as a pure function:

Inputs are explicit

No side effects

Outputs are structured, predictable JSON

Errors and limitations are clearly reported

All findings include citations + confidence + boundaries

This section defines the universal contract all engines follow.

3.9 ENGINE INTERFACE CONTRACTS
1. Input Contract (Required for ALL Engines)

Every engine must accept input parameters in this exact shape:

{
  "matter_id": "string",
  "engine": "string", 
  "filters": {
    "document_ids": ["doc-1", "doc-2"],
    "entity_ids": ["party-1", "custodian"],
    "date_range": {
      "start": "YYYY-MM-DD",
      "end": "YYYY-MM-DD"
    },
    "process_type": "string",
    "topic": "string"
  }
}

Notes:

matter_id is mandatory (prevents cross-matter leakage).

filters are optional.

If filters restrict too much → engine must gracefully report insufficient data.

2. Output Contract (Universal for ALL Engines)

Each engine returns results in this EXACT JSON shape:

{
  "findings": [],
  "documents_considered": [],
  "limitations": [],
  "confidence_assessment": "",
  "engine_metadata": {
    "engine_name": "string",
    "version": "v1",
    "processing_time_ms": 0
  }
}

Components:
A. findings[]

Engine-specific structured findings (timeline events, anomalies, contradictions, citation mismatches, missing documents, etc.)

B. documents_considered[]

List of:

document ID

page numbers

excerpts/snippets

C. limitations[]

The engine must declare what it could NOT determine. Examples:

“Custodian logs missing for 2018–2019”

“Timeline reconstruction incomplete due to OCR errors”

“Process chain step ‘verification of beneficial ownership’ found in Act but missing in documents provided”

This is critical for legal safety and avoids hallucinations.

D. confidence_assessment

One of:

VERIFIED

HIGH_CONFIDENCE

MODERATE

LOW_CONFIDENCE

UNCERTAIN

E. engine_metadata

For audit + future bounded adaptive computation orchestration.

3. Error Contract

If an engine cannot perform its function, it returns:

{
  "error": {
    "code": "NO_DOCUMENTS" | "INSUFFICIENT_DATA" | "INVALID_FILTER" | "ENGINE_FAILURE",
    "message": "Human-readable explanation",
    "suggested_next_steps": ["optional list of safe follow-ups"]
  }
}


Examples:

"NO_DOCUMENTS": "Matter contains 0 ingestible documents."

"INSUFFICIENT_DATA": "Process chain confirmation requires at least one procedural document, but none found."

This prevents the AI from guessing or hallucinating missing facts.

4. Engine-Specific Finding Shapes (Examples)
4.1 Timeline Engine
{
  "event_id": "evt-001",
  "date": "2020-05-01",
  "type": "demat_request_filed",
  "source": {
    "document_id": "doc-3",
    "page": 12,
    "snippet": "On 1 May 2020, Nirav Jobalia submitted..."
  }
}

4.2 Contradiction Engine
{
  "topic": "ownership_claim",
  "statement_a": { "doc": "doc-1", "page": 5, "text": "These shares belong to Mehta family" },
  "statement_b": { "doc": "doc-9", "page": 2, "text": "These shares are solely held by Nirav Jobalia" },
  "conflict_type": "factual",
  "conflict_point": "beneficial ownership"
}

4.3 Documentation Gap Engine
{
  "expected_document": "Proof of purchase (payment receipt)",
  "status": "MISSING",
  "typical_location": "Custodian > Acquisition folder"
}

4.4 Process Chain Integrity Engine
{
  "step": "Verify beneficial ownership before dematerialisation",
  "status": "NOT_FOUND_IN_DOCUMENTS",
  "act_reference": "Torts Act Section 12(3)",
  "potential_impact": "Cannot confirm legitimacy of demat request"
}

5. Side-Effect Policy

Engines MUST NOT:

write to DB

modify memory

update matter

create new entities

They must be stateless.

This ensures safe MCP tool execution later.

6. Audit Requirements

Each engine invocation must automatically log:

engine name

matter_id

filters used

document IDs accessed

timestamp

processing duration

This supports:

reproducibility

safety audits

bounded adaptive computation handoff

rollback & traceability

🚀 Why this section matters

By adding this section:

Your whole architecture becomes ready for bounded adaptive computation.

MCP tools can wrap each engine cleanly.

Future bounded adaptive computation (Option 3) can orchestrate engines safely via deterministic planning and bounded loops.

Debugging becomes predictable.

You eliminate hallucination pathways because engines must return:

“I don’t know”

“I couldn’t infer this”

“Missing documents X and Y”

This is the foundation of a robust legal intelligence system.

3.10 Matter Identity Graph (MIG) Layer — Shared Engine Resource

LDIP maintains a **Matter Identity Graph (MIG)** for each matter.  
This graph creates a stable representation of people, companies, families, institutions, and assets mentioned in that matter.

Purpose:
- Normalize entities inside a single matter
- Link aliases (different spellings / variations)
- Track roles (custodian, company, registrar, claimant, etc.)
- Track appearances in documents and pages
- Provide a stable `entity_id` usable by all engines

Scope:
- MIG is **strictly matter-scoped**. No cross-matter edges.
- All nodes/edges include a `matter_id`.
- MIG obeys all retention/destruction rules.

Data Model:
- **Nodes**: PERSON, ORG, GROUP, INSTITUTION, ASSET (optional)
- **Edges**:
  - `ALIAS_OF`
  - `HAS_ROLE`
  - `APPEARS_IN` (entity → document/page)
  - `RELATED_TO` (director_of, introduced_by, beneficial_owner, etc.)

Ownership:
- **Engine 6 (Entity Authenticity & Role Stability)** is the primary builder/maintainer of MIG.
- Other engines (Timeline, Process Chain, Contradiction) are **read-only consumers**.

Storage:
- Represented in the Structured Fact Store (see Part 7):
  - `identity_nodes(matter_id, node_id, entity_type, canonical_name, metadata)`
  - `identity_edges(matter_id, edge_id, from_node, to_node, edge_type, metadata)`


### Mandatory Evidence Rule (MVP)

Any engine output that makes a factual claim MUST include:

- Source Document ID
- Page number or structured location reference
- Exact text snippet used as supporting evidence

Engines MUST NOT return conclusions or factual assertions without populated evidence fields.

Engine 7 — Admissions & Non-Denial Detector

Purpose:

Flag explicit admissions, partial admissions, and non-denial patterns that juniors often miss.

This is critical in Indian litigation where admissions are gold.

Detects:

- Explicit admissions
  - Direct statements accepting facts
  - Unqualified acknowledgments
  - Clear acceptance of claims

- Partial admissions
  - Qualified acceptances
  - Admissions with conditions
  - Partial acceptance of facts

- "Para denied for want of knowledge" patterns
  - Standard boilerplate denials
  - Denials that don't actually deny
  - Non-specific denials

- Silent non-denials
  - Missing responses where response is expected
  - Failure to deny specific allegations
  - Absence of denial in context where denial would be expected

Output format (always neutral):

"Document X, page Y: Party A states '[exact quote]' which appears to acknowledge [factual claim]."

"Document X, page Y: Party A denies para 12 'for want of knowledge' — this is a boilerplate denial pattern (low confidence)."

"Document X references allegation Y, but no denial found in response document Z."

Confidence calibration:

- High: Explicit, unambiguous admission
- Medium: Partial admission or qualified acceptance
- Low: Possible admission but boilerplate denial pattern detected, or ambiguous language

**Integration with MIG:**

- Uses MIG `entity_id` to track admissions by the same party across multiple documents
- Detects changing positions: admission in one document, denial in another
- Links admissions to specific entities even when names vary

**Indian Drafting Tolerance:**

- Recognizes common boilerplate phrases
- Lowers confidence when boilerplate patterns detected
- Weighs silence only when response was legally expected
- Does not over-interpret standard denial language

This engine never says:

- "Party admitted liability"
- "Party is guilty"
- "This proves fault"

Only:

- "Party stated X which may be interpreted as acknowledging Y"
- "No denial found for allegation Z"
- "Party's position changed from Document A to Document B"

Engine 8 — Pleading-vs-Document Mismatch Engine

Purpose:

Detect when pleadings claim X but supporting documents only support Y.

This goes beyond simple contradictions — it catches over-broad claims and document-pleading disconnects.

Detects:

- Pleadings claiming X, document only supports Y
  - Over-broad legal claims backed by narrow facts
  - Claims in pleadings not substantiated by annexures
  - Disconnect between pleading narrative and document evidence

- Annexures that don't say what pleading says they say
  - Pleading references document as proof of X, but document shows Y
  - Mischaracterization of document contents
  - Selective citation of document portions

- Over-broad legal claims backed by narrow facts
  - Pleading makes sweeping claim, documents only support specific instance
  - Legal theory broader than factual support
  - General allegations without specific document backing

Output format:

Side-by-side comparison:

"Pleading (Doc X, para Y) claims: '[exact quote]'"

"Supporting document (Doc Z, page W) states: '[exact quote]'"

"Disconnect: Pleading claims [X] but document only shows [Y]."

"Annexure A referenced in para 12 does not contain the statement claimed."

**Integration with other engines:**

- Works with Engine 3 (Consistency) to detect contradictions
- Works with Engine 4 (Documentation Gap) to identify missing supporting documents
- Uses Engine 1 (Citation) to verify statutory claims against actual Act text

**Evidence binding:**

Every mismatch must show:

- Exact pleading text with document ID, paragraph, page
- Exact document text with document ID, page
- Nature of disconnect (factual, legal claim, scope mismatch)
- Confidence level

This engine never says:

- "Pleading is false"
- "Document contradicts pleading"
- "This is misleading"

Only:

- "Pleading claims X, document shows Y"
- "Annexure A does not contain the statement referenced in para 12"
- "Legal claim in pleading appears broader than factual support in documents"

3.11 Case Orientation Layer (Day-Zero Clarity)

Purpose:

Provide immediate, explicit orientation to any matter.

Indian juniors need this on day one — not implicit, not buried in documents.

Answers immediately:

- Court & jurisdiction
  - Which court (High Court, District Court, Tribunal, etc.)
  - Which bench/division
  - Jurisdiction details

- Case type
  - Writ petition
  - Suit
  - Appeal
  - Application
  - Miscellaneous Application
  - Other

- Current stage
  - Pleadings stage
  - Arguments stage
  - Evidence stage
  - Final hearing
  - Reserved for judgment
  - Other

- Last effective order
  - Date of last order
  - Order type (interim, final, procedural)
  - Key directions from last order

- Next date + purpose
  - Next hearing date
  - Purpose of next hearing
  - Compliance deadlines

Implementation:

- Automatic extraction from:
  - Latest order documents
  - Cause title
  - Case number format
  - Document metadata

- Manual override available for:
  - Complex matters
  - Unclear documents
  - Attorney corrections

Display:

- Always visible orientation panel
- Updates automatically when new orders uploaded
- Historical tracking of stage progression

This is workflow-critical — juniors read the last order first, and LDIP must make this immediately accessible.

3.12 Operative Directions Extractor

Purpose:

Extract and highlight operative directions from the latest order.

Indian juniors always read the last order first to understand what needs to be done.

Functionality:

- Automatic identification of latest order
  - Date-based sorting
  - Order type detection
  - Most recent effective order

- Extraction of:
  - Directions (what must be done)
  - Deadlines (when it must be done)
  - Compliance requirements (how it must be done)
  - Parties responsible (who must do it)

- Highlighting "failure to comply" risks (factual only)
  - "Direction X has deadline Y (date)"
  - "No document found showing compliance with direction X"
  - "Document Z appears to address direction X (needs verification)"

Language requirements:

❌ "Party failed to comply"
❌ "Direction violated"
❌ "Deadline missed"

✅ "Direction X requires [action] by [date]"
✅ "No record found of compliance with direction X"
✅ "Document Y dated [date] may address direction X (requires attorney verification)"

Output format:

"Latest Order: [Order Date]"

"Directions:"
1. "[Direction text]" — Deadline: [date] — Status: [Complied / Not found / Needs verification]
2. "[Direction text]" — Deadline: [date] — Status: [Complied / Not found / Needs verification]

"Compliance Status:"
- Direction 1: [Evidence found / No evidence found / Ambiguous]
- Direction 2: [Evidence found / No evidence found / Ambiguous]

This is workflow-critical for juniors who need to track compliance immediately.

3.13 Query Guardrails System

Purpose:

Prevent junior lawyers from accidentally asking questions that imply legal conclusions or cross ethical boundaries.

Indian juniors ask dangerous questions accidentally — LDIP must protect them and itself.

Query Classification:

- Safe queries (allowed):
  - "What steps were skipped in the demat process?"
  - "Show me all contradictions in party statements"
  - "What documents are missing?"
  - "When did event X occur?"

- Unsafe queries (blocked):
  - "Who is at fault?"
  - "Who is liable?"
  - "What should we argue?"
  - "Will we win this case?"
  - "Is this illegal?"

- Needs rewriting:
  - "Who did wrong?" → "What actions were taken by each party?"
  - "Is this fraud?" → "What inconsistencies exist in the documents?"

Query Rewriting Service:

- Automatically rewrites unsafe queries to safe alternatives
- Explains why query was rewritten
- Provides suggested safe alternatives

Soft Warnings:

- "This question may imply a legal conclusion"
- "Consider reframing as a factual inquiry"
- "This question requires attorney judgment"

Language Policing:

- Real-time language linting during generation
- Blocks words:
  - "violates"
  - "illegal"
  - "liable"
  - "guilty"
  - "fraud"
  - "malpractice"
  - "wrongdoing"

- Mandatory suffix on all outputs:
  - "This is a factual signal requiring attorney review."

Integration:

- Runs before RAG retrieval
- Integrates with orchestrator pipeline
- Logs all blocked/rewritten queries for audit

This prevents misuse and builds trust with seniors.

3.14 Document Authenticity & Integrity Checks

Purpose:

Flag inconsistencies in document formatting, signatures, and structure that may indicate issues.

Especially important in India where document fabrication is a concern.

Detects:

- Inconsistent letterheads
  - Different letterhead styles for same organization
  - Letterhead changes over time without explanation
  - Mismatched letterhead and content

- Signature/date mismatches
  - Signature style differs from other instances
  - Date inconsistencies (document dated before event occurred)
  - Signature appears inconsistent with known signatures

- Sudden font/layout changes
  - Font changes mid-document
  - Layout inconsistencies
  - Formatting anomalies

- Scanned-copy anomalies
  - Poor scan quality in specific sections
  - Evidence of editing in scanned documents
  - Inconsistent scan quality

- Missing enclosures referenced in letters
  - Letter references attachment not found
  - Enclosure list doesn't match actual attachments
  - Referenced documents missing

Language requirements (CRITICAL):

❌ "Forged"
❌ "Fake signature"
❌ "Fabricated document"
❌ "Fraudulent"

✅ "Inconsistent formatting compared to other documents"
✅ "Signature style differs from other instances in record"
✅ "Font changes detected at page X"
✅ "Referenced enclosure not found in provided materials"

Always ends with:

"No conclusion drawn. This is an observational signal requiring attorney review."

Output format:

"Inconsistency detected: [type]"

"Location: Document X, page Y"

"Observation: [neutral description]"

"Comparison: [how it differs from other documents]"

"Confidence: [High / Medium / Low]"

"No conclusion drawn."

**Integration:**

- Works with Engine 6 (Entity Authenticity) for signature analysis
- Works with Engine 4 (Documentation Gap) for missing enclosures
- Uses document metadata for formatting analysis

This catches quiet fabrication without making accusations.
