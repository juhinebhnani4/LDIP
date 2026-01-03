---
📋 **DOCUMENT STATUS: PHASE 2+ VISION - DEFERRED**
This document is part of the Deep Research vision (8 parts). See [deep_research_analysis_part1.md](./deep_research_analysis_part1.md) for full status information.
**For implementation, use:** [Requirements-Baseline-v1.0.md](../../../_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md)
---

PART 2 — Ethics, Isolation & Compliance Architecture
2.1 Core Ethical Premise

LDIP is built for high-risk legal environments, meaning:

privileged documents

confidential case files

overlapping parties across decades

sensitive litigation histories

expert-finding tasks that must never guess

Therefore, LDIP must behave like a high-discipline research assistant, not an advisor, and it must enforce absolute matter isolation, prevent leakage, and restrict all conclusions.

LDIP NEVER:

forms legal opinions

recommends legal strategy

determines misconduct or liability

Does NOT determine ownership, entitlement, compliance, or legality.

predicts case outcomes

aggregates information across isolated matters

LDIP ALWAYS:

cites evidence

shows where an insight came from

stays neutral (“pattern detected,” not “wrongdoing”)

requires attorney verification

logs all sensitive access

This ethical foundation drives all technical architecture.

2.2 Matter-Centric Isolation (Hard Boundaries)
The system must behave as if each matter is its own universe.

This means:

✔️ Each matter has its own:

document corpus

RAG namespace

embeddings

privilege markers

timeline events

entity list

role mappings

intermediate reasoning context

✔️ Users must be explicitly assigned to a matter.

No access =

no metadata

no embeddings

no existence acknowledgement

✔️ LDIP must deny the existence of other matters.

Even if internally the vector store contains:

cases with same parties

cases with correlated facts

cases with overlapping issues

LDIP behaves as if they do not exist unless the attorney explicitly requests cross-matter analysis and confirms permissions.

2.2.1 File Organization Strategy

For multi-lawsuit scenarios (e.g., client defending against multiple lawsuits), LDIP follows a **"One Matter Per Lawsuit"** approach:

**Use Case Scenario:**
- **Context:** Client was involved in a scam (allegedly). Client is defending against multiple lawsuits. Some lawsuits are legitimate, some are benami (fraudulent/fake). Lawyers have acquired files over years from:
  - Client's own files
  - Opposing parties' files (acquired through discovery/court filings)
- **Goal:** Find anomalies to prove which cases are legitimate vs benami.

**MVP Approach: Option 1 - One Matter Per Lawsuit (Recommended)**

**Structure:**
- Matter: "Client vs Opposing Party A"
  - Files: Client files + Opposing Party A files (exchanged in discovery)
- Matter: "Client vs Opposing Party B"
  - Files: Client files + Opposing Party B files
- Matter: "Client vs Opposing Party C"
  - Files: Client files + Opposing Party C files

**Analysis Scope:**
- Within each matter: Find contradictions, timeline issues, process deviations
- Cross-matter comparison: Requires explicit authorization (Phase 2)

**Pros:**
- ✅ Simple mental model - one case = one matter
- ✅ Clear isolation - each lawsuit analyzed separately
- ✅ Matches LDIP's current matter isolation model
- ✅ Conflict checking works naturally
- ✅ Easy to understand and implement

**Cons:**
- ⚠️ Cross-lawsuit pattern comparison requires cross-matter analysis
- ⚠️ Client files duplicated across matters (but this is acceptable)

**Technical Implementation:**
- Matter creation: Lawyer creates matter per lawsuit
- File upload: All files (client + opposing party) tagged with `matter_id`
- Analysis: Works within matter boundary
- Cross-matter: Explicit authorization required for pattern comparison

**Alternative Approaches (Not Recommended for MVP):**

**Option 2: All Lawsuits in One Matter**
- **Structure:** Matter: "All Cases Against Client" contains all files mixed together
- **Cons:** ❌ Violates matter isolation principle, complex conflict checking, ethical risk

**Option 3: Hybrid - Matter Per Lawsuit + Cross-Matter Analysis (Phase 2)**
- **Structure:** One matter per lawsuit + Research Collections for cross-matter analysis
- **Pros:** ✅ Maintains matter isolation, enables cross-lawsuit comparison when needed
- **Implementation:** Phase 2 feature for authorized cross-matter pattern comparison

**File Source Classification:**

**Assumption for MVP: Public/Discovery Documents**
- Files acquired "over the course of years" through discovery/court filings
- These are typically public court documents or properly exchanged discovery
- Safe to analyze together within same matter

**If Privileged Documents Present:**
- Use LDIP's existing privilege detection (Section 2.5)
- Files tagged with privilege level (LOW/MEDIUM/HIGH)
- HIGH privilege files blocked from analysis until approved
- Privilege protection applies per file, not per matter

**Handling Files from Multiple Opposing Parties:**

**Within Single Lawsuit Matter:**
- **Scenario:** Matter "Client vs Opposing Party A"
  - Files from Client
  - Files from Opposing Party A (exchanged in discovery)
- **Handling:**
  - All files tagged with same `matter_id`
  - Analysis works across all files in matter
  - System doesn't need to know "which side" - all files are part of same case
  - No ethical issue - these files were properly exchanged in discovery

**Across Multiple Lawsuits:**
- **Scenario:** Compare patterns across "Client vs Party A" and "Client vs Party B"
- **Handling:**
  - Each lawsuit is separate matter
  - Cross-matter analysis requires explicit authorization
  - System checks: Are matters adverse? (They're not - both are against same client)
  - Authorization: Lawyer confirms "I want to compare patterns across these matters"
  - Analysis: Pattern comparison across authorized matters only

**Implementation Guidelines:**

**Matter Creation Workflow:**
1. **Lawyer creates matter:** "Client vs Opposing Party A"
2. **Upload files:**
   - Client files related to this lawsuit
   - Opposing Party A files (from discovery)
3. **Conflict check:** Fast pre-check + background deep check
4. **Analysis:** Works within matter boundary

**Cross-Matter Pattern Comparison (Phase 2):**
1. **Lawyer requests:** "Compare patterns across Matter A, B, C"
2. **System checks:**
   - Are all matters for same client? ✅
   - Are any matters adverse? ❌ (No - all against same client)
   - Does lawyer have authorization? ✅
3. **Analysis:** Pattern comparison across authorized matters
4. **Output:** "Pattern detected: Similar timeline anomalies in 3 of 5 matters. See evidence: [citations]"

**Conclusion:**

**MVP Approach:**
- One matter per lawsuit
- Files from both sides (client + opposing party) in same matter
- Analysis within matter boundary
- Cross-matter comparison deferred to Phase 2

**Phase 2 Enhancement:**
- Add Research Collections for cross-matter analysis
- Enable pattern comparison across authorized matters
- Maintain strict matter isolation and authorization gates

This approach balances simplicity, safety, and functionality while allowing future expansion.

2.3 Identity Resolution Without Violating Isolation

You raised the critical edge case:

“One person may have differently named companies. Then LDIP cannot perform true analysis.”

The resolution is:

LDIP supports two identity systems:
🔷 A. Matter Identity Graph (MIG) — Matter-Scoped (Allowed)

Inside a matter, LDIP can:

Inside a matter, LDIP maintains a **Matter Identity Graph (MIG)**.

MIG is a real data structure, not just loose logic:

- **Nodes** = entities mentioned in this matter
  - people (e.g. “Nirav Jobalia”)
  - companies (e.g. “Shreenath Securities Pvt Ltd”)
  - groups/families (e.g. “Jobalia family”)
  - institutional roles (custodian, company, registrar, etc.)

- **Alias edges** = “same underlying entity in THIS matter”
  - alternate spellings
  - name changes in filings
  - abbreviations / expansions
  - “Mr. N. Jobalia” ↔ “Nirav Jobalia”

- **Role edges** = “what this entity is doing in THIS matter”
  - Nirav Jobalia → (role: applicant, respondent, benami holder)
  - Company → (role: issuer, registrar)
  - Custodian → (role: intermediary, record-keeper)

- **Relationship edges** (inside this matter only)
  - “introducer of X”
  - “beneficial owner of Y”
  - “director of Company Z”

This enables, **within a single matter**:

- understanding “who is who” even with spelling variations  
- linking actions across multiple documents  
- building consistent timelines per person/company  
- catching contradictions in positions across filings  

Hard boundary:

- MIG is **strictly matter-scoped**:
  - every node and edge has a `matter_id`
  - **no edges may connect entities across different `matter_id`s**
  - MIG for Matter A is logically a different graph from MIG for Matter B

Lifecycle:

- MIG lives in the Structured Fact Store
- It obeys **the same retention/destruction rules as the matter**
  - when a matter is destroyed, all MIG nodes/edges for that `matter_id` are also destroyed

🔷 B. Cross-Matter Identity Graph (DISALLOWED by default)

By default, LDIP **does not** build any identity graph that spans multiple matters.

LDIP must not:

- guess that “Shreenath Securities Pvt Ltd” in Matter A = “Shreenath Holdings LLC” in Matter B  
- connect Nirav Jobalia’s actions across different matters  
- detect patterns of misconduct across multiple matters  
- aggregate “lifetime behaviour” of a person or company across clients  

Any cross-matter linkage is only allowed in **highly controlled modes**, for example:

- comparing **public judgments only**, or  
- intra-client analysis explicitly authorized by the firm

Even then:

- cross-matter links live in a **separate, restricted “Public / Cross-Matter Index”**, not in the per-matter MIG
- every cross-matter link must be:
  - explicitly requested (user passes both matter IDs or “public judgments only”)  
  - conflict-checked  
  - logged with who requested, when, and why  

This separation protects against:

- privilege breach  
- unintentional inference ("this person often does X")  
- false allegations based on incomplete history  
- illegal or unethical strategic conclusions  

2.3.1 Cross-Matter Identity Resolution (Phase 2+)

**Problem Statement:**

For same-client pattern detection (Phase 2), the system needs to identify when the same entity appears across multiple matters. For example:
- "Nirav D. Jobalia" in Matter A
- "N.D. Jobalia" in Matter B  
- "Nirav Jobalia" in Matter C

The system needs to recognize these are the same person to enable pattern comparison across matters.

**Constraint:** Must maintain strict matter isolation - MIG (Matter Identity Graph) is matter-scoped and cannot have cross-matter edges.

**Recommended Approach: Option D - Hybrid - Query-Time with Cached Matches**

**Rationale:**

1. **Safety First:**
   - Query-time matching is default (no persistent cross-matter data)
   - Cache is optional and requires explicit approval
   - Maintains matter isolation principle

2. **Real-World Acceptance:**
   - Lawyers can approve matches they trust
   - System learns from approvals
   - No approval needed for one-time queries

3. **Technical Feasibility:**
   - Query-time matching: Simple, stateless service
   - Cache: Optional optimization layer
   - Can be implemented incrementally

4. **Performance:**
   - First query: Full matching (acceptable for pattern analysis)
   - Subsequent queries: Use cached matches (faster)
   - Balance between safety and efficiency

**Technical Implementation:**

**1. Query-Time Matching (Default):**

**Entity Matching Service:**
- **Input:**
  ```json
  {
    "matter_ids": ["matter_a", "matter_b"],
    "entities_matter_a": [
      {"entity_id": "e1", "name": "Nirav D. Jobalia", "aliases": ["N.D. Jobalia"]}
    ],
    "entities_matter_b": [
      {"entity_id": "e2", "name": "N.D. Jobalia", "aliases": []}
    ]
  }
  ```

- **Matching Algorithm:**
  1. **Exact match:** Name or alias matches exactly
  2. **Fuzzy match:** Levenshtein distance < threshold (e.g., 2)
  3. **Phonetic match:** Soundex/Metaphone similarity
  4. **Context match:** Same role, similar dates, same relationships

- **Output:**
  ```json
  {
    "matches": [
      {
        "entity_a": "e1",
        "entity_b": "e2",
        "confidence": 0.92,
        "match_type": "fuzzy_name",
        "evidence": "Name similarity: 'Nirav D. Jobalia' vs 'N.D. Jobalia'"
      }
    ],
    "uncertain": [
      {
        "entity_a": "e3",
        "entity_b": "e4",
        "confidence": 0.65,
        "match_type": "context",
        "requires_review": true
      }
    ]
  }
  ```

- **Flow:**
  1. User requests pattern comparison: Matter A + Matter B
  2. System extracts entities from both matters (using MIG)
  3. Real-time fuzzy matching
  4. Temporary resolution cache (cleared after query)
  5. Pattern analysis using resolved entities
  6. Results returned, cache cleared

**2. Optional Persistent Cache:**

**Cache Schema:**
```sql
approved_entity_matches:
  - match_id (primary key)
  - matter_id_a
  - entity_id_a (from MIG in Matter A)
  - matter_id_b
  - entity_id_b (from MIG in Matter B)
  - canonical_entity_id (cross-matter identifier)
  - confidence_score
  - approved_by (user_id)
  - approved_at (timestamp)
  - match_evidence (JSON: why this match was approved)
  - is_active (boolean: can be deactivated)
```

**Authorization Workflow:**
1. Query-time matching: System finds candidate matches
2. Display to lawyer: "Found potential matches. Review?"
3. Lawyer reviews: Approves/rejects each match
4. Cache update: Approved matches stored in cache
5. Future queries: Use cached matches automatically

**Flow:**
1. Query requests pattern comparison
2. Check cache for pre-approved matches
3. Use cached matches + query-time matching for new entities
4. Show lawyer: "Entity X in Matter A matches Entity Y in Matter B (confidence: 85%)"
5. Lawyer can approve → cache entry created
6. Future queries use cached match

**Audit Trail:**

All entity matching operations logged:
```sql
entity_matching_log:
  - log_id
  - query_id
  - matter_ids[]
  - matches_found[]
  - matches_used_from_cache[]
  - matches_approved[]
  - execution_time
  - timestamp
```

**Safety Safeguards:**

1. **No automatic matching:** All matches require review (or very high confidence threshold)
2. **Matter isolation maintained:** MIG stays matter-scoped, cross-matter index is separate
3. **Authorization required:** Cache entries require explicit approval
4. **Audit trail:** All matching operations logged
5. **Can be disabled:** Lawyers can disable cross-matter matching per matter

**Alternative Approaches (Not Recommended):**

**Option A: Separate Cross-Matter Identity Index**
- **Pros:** Clear separation from MIG, explicit authorization
- **Cons:** Additional storage layer, requires user approval workflow, more complex

**Option B: Extended MIG with Cross-Matter Edges**
- **Cons:** ❌ Violates matter isolation principle, more complex isolation enforcement, higher risk of bugs/leakage

**Option C: Query-Time Resolution Only (No Persistent Graph)**
- **Pros:** ✅ Safest - no persistent cross-matter data, simple
- **Cons:** ⚠️ Slower - matching happens every query, less efficient

**Implementation Timeline:**

**Phase 1 Implementation (MVP):**
- **For MVP:** Skip cross-matter identity resolution entirely
- **Rationale:**
  - MVP focuses on pre-linking within matters only
  - Cross-matter pattern detection is Phase 2 feature
  - Can implement identity resolution when needed
- **MVP Approach:**
  - Matter-scoped MIG only
  - No cross-matter entity matching
  - Pattern context from same-client matters uses entity names (not resolved identities)

**Phase 2 Implementation:**
- **When adding same-client pattern detection:**
  1. Implement query-time matching service
  2. Add cache schema (optional optimization)
  3. Build approval workflow UI
  4. Add audit logging
  5. Test with real data
- **Rollout:**
  - Start with query-time only (safest)
  - Add cache after validating matching accuracy
  - Learn from lawyer approvals to improve matching

**Conclusion:**

**Recommended Approach:** Option D (Hybrid - Query-Time with Cached Matches)

**Implementation Timeline:**
- **MVP:** No cross-matter identity resolution (matter-scoped only)
- **Phase 2:** Query-time matching service
- **Phase 2.5:** Add optional cache with approval workflow

This approach balances safety, efficiency, and real-world usability while maintaining strict matter isolation.

2.4 Conflict Checking (Mandatory Gate Before Analysis)

Before ANY new matter is created:

LDIP extracts:

all parties

all counsel

all corporate entities

all associated persons

all beneficiaries

all known aliases

Then compares them across every existing matter, even those the user can’t see.

If conflicts exist:

LDIP blocks matter creation

returns the conflict set (only non-privileged metadata)

requests senior attorney resolution

If no conflicts:

matter is created

ethical wall established

This ensures:

LDIP is safe to use in large firms

no accidental leakage

clean compartmentalization

2.41 MVP Enforcement Rule: Matter-Scoped Identity Graph

For MVP, the Matter Identity Graph (MIG) is strictly scoped to a single Matter.

- Each Matter owns an isolated MIG instance.
- No identity resolution, alias matching, or entity linkage is performed across Matters.
- Cross-matter identity analysis is explicitly out of scope for MVP and must be implemented as a separate, opt-in Phase-2 service.

Conflict checking at Matter creation may compare against existing Matters using non-privileged metadata only (e.g., matter name or public identifiers) and must not disclose the existence or contents of other Matters beyond a boolean or abstract conflict indicator.

Note: Matter-scoped identity isolation does not prevent the system from
surfacing non-binding cross-matter signals (e.g., shared public identifiers,
similar entity names, common legal citations).

Such signals MUST NOT merge or link identities across Matters and MUST be
presented as informational prompts requiring human interpretation.


2.5 Privilege Detection & Protection

Every uploaded document undergoes:

A. Automatic Privilege Scan

LDIP looks for:

“attorney-client privilege” markings

legal advisories

litigation strategy

internal memos

counsel email signatures

privileged headers

B. Privilege Score (0–10)

LDIP assigns:

Low risk → allow

Medium risk → warn

High risk → block processing

C. Privileged Segments Masking

If a document contains privileged paragraphs:

LDIP extracts non-privileged portions only

Privileged paragraphs are masked, not embedded

Vector store never sees privileged content

D. Privilege Logging

Required for:

audit

compliance

post-incident analysis

This also supports disciplinary review if a breach is alleged.

2.6 Data Retention & Destruction Protocols

LDIP implements:

✔️ Retention schedules (jurisdiction-specific)

Typical:

7 years after matter closure

10 years for audit logs

indefinite for public judgments

✔️ Scheduled destruction

LDIP:

deletes all embeddings

purges documents

destroys privilege logs

invalidates identity graph nodes

✔️ Destruction certificates

Generated for:

courts

auditors

compliance reports

✔️ Attorney notifications

To verify no case is accidentally killed.

2.7 Jurisdictional Compliance Layer

LDIP must adapt to:

🇮🇳 India — DPDP Act (2023)

data fiduciary obligations

localization rules

consent tracking

🇺🇸 US — State privacy + ABA rules

72-hour breach notification

privilege preservation

🇪🇺 EU — GDPR

right to erasure

data portability

DPA notifications

LDIP auto-enforces:

regional storage

jurisdiction-aware deletion

compliance alerts

2.8 Safety Principles That Directly Affect Reasoning

LDIP’s reasoning layer must follow:

✔️ Neutrality

Never jumps to:

“wrongdoing”

“malpractice”

“violation”

“fraud”

Instead:

“pattern inconsistent with baseline”

“missing documentation in uploaded set”

“timeline deviation observed”

✔️ Evidence binding

Every claim must be tied to:

a page

a document

a line

a statutory clause

If no evidence:

LDIP must answer “insufficient data.”

✔️ No guessing

If ambiguous:

LDIP marks uncertainty

lists alternative interpretations

requires attorney review

✔️ No knowledge of other matters (by default)

Even if LDIP internally stores the embeddings, it must act as if they do not exist.

✔️ No legal conclusions

All determinations belong to a human lawyer.

LDIP only surfaces:

patterns

gaps

contradictions

anomalies

factual discrepancies

All tools and engines MUST log inputs, outputs, and matter_id to support audit and future bounded adaptive computation orchestration.

✔️ End of PART 2

This completes the full Ethics, Isolation, Privilege, Compliance, and Safety Framework.