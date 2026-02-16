# Citation Engine — Architecture Analysis & Long-Term Plan

> **Date:** 2026-02-06
> **Status:** Investigation complete — most mature engine, no critical bugs; minor gaps identified

---

## Part 1: Current Architecture

### Pipeline Overview

The citation engine extracts legal Act references from case documents, tracks which Acts are available, and verifies citations against actual Act text. It uses a **multi-stage pipeline**:

```
Stage 1: Citation Extraction (Story 3-1)
    → Dual strategy: Regex patterns (free) + Gemini Flash (comprehensive)
    → Chunks text at 5,000 chars with 500 char overlap
    → Dedup key: act_name:section:subsection:clause
    → Saves to citations table with bbox linking
    ↓
Stage 2: Act Resolution & Discovery (Story 3-2)
    → Creates act_resolutions records for each unique Act referenced
    → Checks India Code for auto-fetch availability
    → Generates discovery report: X Acts referenced, Y available, Z missing
    → Real-time WebSocket notifications to frontend
    ↓
Stage 3: Act Upload / Auto-Fetch
    → User uploads missing Act PDFs via ActUploadDropzone
    → Or system auto-fetches from India Code (indiacode.nic.in)
    → Acts routed to shared library (cross-matter reuse)
    ↓
Stage 4: Citation Verification (Story 3-3)
    → Indexes Act document sections (regex + LLM fallback)
    → Finds cited section in Act text
    → Compares quoted text (exact match first, then semantic via Gemini)
    → Status: verified / mismatch / section_not_found / act_unavailable
    ↓
Stage 5: Split-View Display (Story 3-4)
    → Side-by-side: case document (left) + Act (right)
    → Color-coded highlights: yellow (source), blue (verified), red (mismatch)
    → Keyboard navigation, fullscreen mode
```

### Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `backend/app/engines/citation/extractor.py` | Gemini + regex citation extraction | 836 |
| `backend/app/engines/citation/verifier.py` | Citation verification against Acts | 767 |
| `backend/app/engines/citation/discovery.py` | Missing Acts report generation | 509 |
| `backend/app/engines/citation/storage.py` | Database operations (citations, act_resolutions) | 1356 |
| `backend/app/engines/citation/validation.py` | Garbage detection for Act names | 604 |
| `backend/app/engines/citation/act_indexer.py` | Section index building for Acts | 476 |
| `backend/app/engines/citation/india_code.py` | India Code API client (auto-fetch) | 537 |
| `backend/app/engines/citation/abbreviations.py` | 100+ Act name normalizations | ~300 |
| `backend/app/engines/citation/prompts.py` | Extraction prompts with security boundaries | 264 |
| `backend/app/engines/citation/verification_prompts.py` | Verification-specific prompts | ~150 |
| `backend/app/workers/tasks/document_tasks.py:4708+` | `extract_citations` Celery task | — |
| `backend/app/workers/tasks/verification_tasks.py` | 3 verification tasks | 538 |
| `backend/app/api/routes/citations.py` | 12 API endpoints | 1852 |
| `backend/app/services/citation_service.py` | Bbox linking for citations | 327 |
| `backend/app/models/citation.py` | Pydantic models + enums | 477 |

### API Endpoints (12 total)

| # | Method | Path | Purpose |
|---|--------|------|---------|
| 1 | GET | `/matters/{id}/citations` | List with filters + pagination |
| 2 | GET | `/matters/{id}/citations/stats` | Counts (total, verified, pending) |
| 3 | PATCH | `/matters/{id}/citations/bulk-status` | Bulk update (max 100) |
| 4 | GET | `/matters/{id}/citations/{cid}` | Single citation |
| 5 | PATCH | `/matters/{id}/citations/{cid}/status` | Manual status override |
| 6 | GET | `/matters/{id}/citations/summary/by-act` | Grouped by Act |
| 7 | GET | `/matters/{id}/citations/acts/discovery` | Discovery report |
| 8 | POST | `/matters/{id}/citations/acts/mark-uploaded` | Mark Act as uploaded |
| 9 | POST | `/matters/{id}/citations/acts/mark-skipped` | Mark Act as skipped |
| 10 | POST | `/matters/{id}/citations/verify` | Batch verification |
| 11 | POST | `/matters/{id}/citations/{cid}/verify` | Single verification |
| 12 | GET | `/matters/{id}/citations/{cid}/split-view` | Source + target with bboxes |

### Database Tables

**`citations` table:**
- Core: `id`, `matter_id`, `document_id`, `act_name`, `section_number`
- Source location: `source_page`, `source_bbox_ids`
- Target location: `target_act_document_id`, `target_page`, `target_bbox_ids`
- Verification: `verification_status` (PENDING/VERIFIED/MISMATCH/SECTION_NOT_FOUND/ACT_UNAVAILABLE), `confidence`
- Text: `raw_citation_text`, `quoted_text`, `extraction_metadata`

**`act_resolutions` table:**
- `act_name_normalized`, `act_name_display`
- `act_document_id` (link to uploaded/fetched Act)
- `resolution_status` (AVAILABLE/AUTO_FETCHED/MISSING/INVALID/NOT_ON_INDIACODE/SKIPPED)
- `user_action` (UPLOADED/SKIPPED/AUTO_FETCHED/PENDING)
- `citation_count`

### Frontend Components (29 files)

| Component | Purpose | Story |
|-----------|---------|-------|
| `CitationsContent.tsx` | Main container, view modes, filter state | 10C.3 |
| `CitationsHeader.tsx` | Stats bar, filters, view mode toggle | 10C.3 |
| `CitationsList.tsx` | Table view with sorting | 10C.3 |
| `CitationsByActView.tsx` | Grouped by Act, expandable sections | 10C.3 |
| `CitationsByDocumentView.tsx` | Grouped by source document | 10C.3 |
| `CitationsAttentionBanner.tsx` | Issue count banner | 10C.3 |
| `MissingActsCard.tsx` | Missing Acts with upload/skip actions | 10C.3 |
| `ActDiscoveryModal.tsx` | Full discovery report modal | 3-2 |
| `ActDiscoveryItem.tsx` | Individual Act status item | 3-2 |
| `ActDiscoveryTrigger.tsx` | Realtime subscription, auto-open modal | 3-2 |
| `ActUploadDropzone.tsx` | PDF upload for Acts (100MB limit) | 3-2 |
| `SplitViewCitationPanel.tsx` | Resizable side-by-side panels | 3-4 |
| `SplitViewHeader.tsx` | Citation details, navigation, mismatch alert | 3-4 |
| `SplitViewModal.tsx` | Fullscreen modal wrapper | 3-4 |
| `MismatchExplanation.tsx` | Diff highlights for mismatches | 3-4 |

**Hooks:** `useCitations.ts` (7 exported hooks), `useActDiscovery.ts`, `useVerificationActions.ts`

**Tests:** 20 test files with comprehensive coverage across all components and hooks.

### Celery Task Configuration

| Task | Timeout | Retries | Pipeline Position |
|------|---------|---------|-------------------|
| `extract_citations` | 600s (10 min) | 3 + exponential backoff | After embedding, parallel with entity extraction |
| `verify_citations_for_act` | — | 3, 60s delay | Triggered by Act upload |
| `verify_single_citation` | — | 3, 60s delay | On-demand |
| `trigger_verification_on_act_upload` | — | 1, 30s delay | Auto-triggered |

### Cost Profile

| Operation | Model | Cost per Unit | Notes |
|-----------|-------|---------------|-------|
| Citation extraction | Gemini Flash | ~₹0.02/chunk (~$0.00024) | 5,000 char chunks |
| Citation verification | Gemini Flash | ~₹0.008/citation (~$0.00010) | Section search + comparison |
| Act auto-fetch | HTTP only | $0 (no LLM) | Rate-limited to 5 req/min |
| Garbage detection | Rule-based | $0 (no LLM) | Pattern matching + structure validation |
| Severity scoring | N/A | N/A | Citation engine doesn't score severity |

**Estimated cost per matter:** ~$0.50-1.50 depending on document count and citation density.

---

## Part 2: What Works Well

The citation engine is **the most complete and feature-rich engine** in the system:

1. **All 6 stories complete** (3-1, 3-2, 3-3, 3-4, 10C.3, 10C.4) — fully in MVP scope, nothing deferred
2. **Dual extraction** — regex (free, reliable for standard formats) + Gemini (catches complex citations)
3. **100+ Act abbreviations** — NI Act → Negotiable Instruments Act, 1881; IPC → Indian Penal Code, 1860
4. **Garbage detection** — validates Act names structurally before saving (min 2 meaningful words, pattern checks)
5. **India Code auto-fetch** — automatically downloads Act PDFs from government site
6. **Split-view verification** — side-by-side case vs Act with color-coded highlights (best UX in the app)
7. **Real-time progress** — WebSocket broadcasts verification progress to frontend
8. **Shared Acts Library** — Acts reused across matters, avoiding duplicate downloads
9. **Security boundaries** — XML boundaries in prompts prevent prompt injection
10. **Comprehensive frontend** — 3 view modes (list, by Act, by document), filters, attention banners, discovery workflow

---

## Part 3: Known Gaps & Issues

### 3.1 No Cost Tracking in Verification (Medium)

**Problem:** `verifier.py` makes Gemini API calls but doesn't use `CostTracker`.

**Location:** `backend/app/engines/citation/verifier.py:612-673` — API calls without cost logging.

**Impact:** Cannot measure verification cost, no cost alerts, ROI of verification feature unmeasurable.

**Fix:** Add `CostTracker` to verification calls, same pattern as `extractor.py:507-511`.

### 3.2 No Cross-Document Citation Dedup (Medium)

**Problem:** Deduplication is per-document only. Same citation extracted from multiple documents creates duplicates.

**Location:** `backend/app/engines/citation/extractor.py:755-794` — merge is per-extraction-run.

**Impact:** Inflated citation counts. "Section 138 NI Act" appearing in 5 documents = 5 citation records.

**Mitigation:** Matter-level dedup could group by (act_name, section, subsection) and show document sources.

### 3.3 No Distributed Rate Limiting (Medium)

**Problem:** Rate limiter is process-local (in-memory semaphore). Multiple Celery workers each make 3 concurrent Gemini calls.

**Location:** `backend/app/core/llm_rate_limiter.py:43-140`

**Impact:** With 5 workers = 15 concurrent calls, may exceed Gemini free tier limits, causing 429 errors.

**Fix:** Redis-based distributed rate limiter for production.

### 3.4 Citation Granularity — Chunk-Level Not Sentence-Level (Gap #30)

**Problem:** Citations link to chunks, not exact sentences. "Section 138 of NI Act" points to a ~5000 char chunk.

**Impact:** In split-view, the highlighted region is too broad. Attorney must scan to find exact reference.

**Gap reference:** First-principles gap analysis #30, FR8.4 (Phase 8).

### 3.5 Citation Spoofing Attack Vector (Gap #193)

**Problem:** Act resolution process doesn't validate Act authenticity. User could upload a fake Act PDF with a similar name to deceive verification.

**Impact:** Verification would mark citations as "verified" against fake Act text.

**Gap reference:** First-principles gap analysis #193 (Red Team identified).

**Fix:** Hash-based verification against India Code canonical PDFs; flag user-uploaded Acts vs auto-fetched.

### 3.6 Deprecated Sync Wrapper in Verifier (Low)

**Problem:** `verifier.py:728-751` has `verify_citation_sync()` creating a new event loop per call.

**Impact:** Works but suboptimal. Should use `run_async()` at task level.

### 3.7 No Circuit Breaker for Verification (Low)

**Problem:** India Code client has circuit breaker, but the verifier doesn't. If Gemini is down, verification retries 3x per citation, accumulating a massive retry queue.

**Fix:** Add circuit breaker pattern to `verifier.py`, same as contradiction engine's `comparator.py`.

---

## Part 4: Future Phases — Pending Work

### Completed Stories (All in MVP)

| Story | Description | Status |
|-------|-------------|--------|
| 3-1 | Act Citation Extraction | Review (code complete) |
| 3-2 | Act Discovery Report UI | Done |
| 3-3 | Citation Verification | Done |
| 3-4 | Split-View Citation Highlighting | Done |
| 10C.3 | Citations Tab List and Act Discovery | Review |
| 10C.4 | Citations Tab Split-View Integration | Complete |

**Nothing was deferred to Phase 2 for citations.** This is the only engine where all planned features shipped in MVP.

### From First-Principles Gap Analysis

| Gap # | Description | Phase | Priority |
|--------|-------------|-------|----------|
| #30 | Citation granularity (sentence-level, not chunk-level) | Phase 8 (Optional) | Medium |
| #50 | Cross-engine consistency checking (timeline dates vs citation dates) | Phase 4 | High |
| #15 | Cross-engine correlation (citations linked to entities and timeline) | Phase 4 | High |
| #153 | Citation extractor garbage output — no automatic rejection threshold | Not mapped | Medium |
| #193 | Citation spoofing attack — fake Act uploads | Not mapped | Security |

### From Epics Gap Remediation

| Reference | Description | Phase |
|-----------|-------------|-------|
| FR4.3 (Gap #15) | Cross-engine correlation — timeline to citation to entity links | Phase 4 (Week 7-8) |
| FR4.4 (Gap #50) | Cross-engine consistency — compare timeline dates vs citation dates, flag conflicts | Phase 4 (Week 7-8) |
| FR8.4 (Gap #30) | Citation granularity — sentence-level positions | Phase 8 (Week 15-16, optional) |

### From Phase 2 Backlog

**No citation features deferred.** However, related engines are deferred:
- **Documentation Gap Engine** — detects missing documents based on expected process (requires process templates from Juhi)
- **Process Chain Integrity Engine** — validates event sequences (e.g., notice → reply → hearing → order)

Both of these would leverage citation data if built.

---

## Part 5: First-Principles Thinking — What Is a Citation Engine, Really?

### The Fundamental Question

A citation engine's job is not "extract text patterns that look like legal references." That's what the current implementation does, and it works — but it's solving the wrong problem at the wrong altitude.

**The real question:** What does an attorney need from citations, and what will they need in 10 years?

### What an Attorney Actually Does with Citations

1. **Verify accuracy** — "Does the opposing counsel's brief actually say what they claim Section 138 says?"
2. **Check applicability** — "Is this Section still in force? Was it amended? Does this court's jurisdiction apply?"
3. **Find precedent** — "What other cases cited this Section? How did courts interpret it?"
4. **Build arguments** — "Which Sections support my client's position? What's the strongest chain of authority?"
5. **Detect omissions** — "The opposing brief cites Section 138 but conveniently ignores Section 141 (liability of directors). Should we raise this?"

The current engine handles #1 well (extraction + verification + split-view). It touches #5 lightly (Act Discovery shows missing Acts). It doesn't address #2, #3, or #4 at all.

### The 10-Year Question: What Kills This Engine?

**Scenario 1: India Code goes offline or restructures.** The auto-fetch feature breaks. Acts Library becomes the only source. User-uploaded Acts have no verification. Citation spoofing becomes trivial.

**Scenario 2: New legislation formats.** India is digitizing rapidly. Act formats will change — structured XML/JSON instead of PDFs. The current PDF-based pipeline (OCR → chunk → regex/LLM) becomes obsolete for new-format Acts while still needed for legacy Acts.

**Scenario 3: Lawyers want reasoning, not just extraction.** "You cited Section 138. But Section 138 was amended in 2018 to add proviso (b). Your citation predates the amendment." The current engine can't reason about legislative history.

**Scenario 4: Multi-jurisdiction.** Indian law is just the starting point. State Acts, rules, notifications, circulars, SEBI regulations, RBI guidelines — each has different citation formats, different sources, different validity rules.

**Scenario 5: AI-native law firms.** In 10 years, junior associates won't manually verify citations. They'll expect the system to say "This citation is verified, current, applicable to this jurisdiction, and 47 High Court judgments have interpreted this section favorably for your position."

### First Principles: What Must Be True?

1. **Citations are not flat text — they're structured references into a knowledge graph.** A citation is a pointer from Document A, Section B, to Act C, Section D, Subsection E, as amended by Act F on Date G. The current model (`act_name + section_number`) is too flat.

2. **Acts are not static PDFs — they're versioned legal documents.** Section 138 of NI Act in 1988 is different from Section 138 in 2018 (after amendments). The current engine treats all Acts as immutable. This will break for any serious legal analysis.

3. **Citation validity is temporal.** A citation is only useful if the cited provision was in force on the date relevant to the case. "Section 66A of IT Act" was struck down by the Supreme Court in 2015 — citing it in 2024 is an error. The engine can't detect this.

4. **Citation context matters more than citation text.** "Section 138 NI Act" appears 50 times in a matter. But the *reason* it's cited differs each time — sometimes for the offence definition, sometimes for the limitation period, sometimes for the presumption of dishonesty. Context-aware extraction would be transformative.

5. **The Acts Library is not a document store — it's a legal knowledge base.** Currently it stores PDFs. Long-term it should store structured, versioned, cross-referenced legal provisions that can be queried ("Show me all amendments to NI Act Section 138 since 2010").

---

## Part 6: Long-Term Vision (3-Year Architecture)

### Year 1: From Text Extraction to Structured Legal References

#### 1A. Structured Citation Model

Replace flat `act_name + section_number` with a structured reference:

```
Citation {
    act: {
        name: "Negotiable Instruments Act, 1881"
        canonical_id: "ni-act-1881"          // Stable identifier
        jurisdiction: "Central"
        status: "in_force"                    // in_force | repealed | partially_repealed
    }
    provision: {
        section: "138"
        subsection: null
        clause: null
        proviso: null
        explanation: null
    }
    context: {
        purpose: "offence_definition"         // Why is this cited here?
        argument_role: "supporting"           // supporting | opposing | distinguishing | obiter
        quoted_text: "..."
        paraphrase: "..."
    }
    validity: {
        as_of_date: "2024-01-15"             // Relevant date in case
        was_in_force: true
        amendments_since: [...]
        struck_down: false
    }
    source: {
        document_id: "..."
        page: 3
        sentence_offsets: [1240, 1380]       // Exact location
    }
}
```

This model enables: "Is this citation valid?", "What's the current version of this section?", "Why was this section cited?"

#### 1B. Legislative History Awareness

Build a `legislative_provisions` table that tracks:
- Act → Section → Version history (original, amendments, repeals)
- Amendment relationships: "Section 138 was substituted by Act 55 of 2002, w.e.f. 01.02.2003"
- Repeal status: "Section 66A IT Act struck down by Shreya Singhal v UOI (2015)"

**Data source:** India Code provides amendment histories. Parse and structure them during Act indexing.

**Impact:** "This citation references a provision that was amended after the relevant date in your case. The current version differs in [these ways]."

#### 1C. Citation Purpose Classification

Currently extraction captures *what* is cited. Add *why* it's cited:

| Purpose | Example |
|---------|---------|
| offence_definition | "Section 138 defines dishonour of cheque..." |
| limitation_period | "Section 142(b) requires complaint within 30 days..." |
| procedure | "Section 145(2) allows affidavit evidence..." |
| presumption | "Section 139 presumes dishonesty..." |
| penalty | "Section 138 provides for imprisonment up to 2 years..." |
| exemption | "Proviso to Section 138 provides a defence if..." |

**Implementation:** Enhanced Gemini prompt that classifies citation purpose. Cost: minimal — one extra field in existing extraction call.

### Year 2: From Verification to Legal Reasoning

#### 2A. Cross-Citation Argument Graph

Citations don't exist in isolation. They form argument chains:

```
Prosecution's argument chain:
    Section 138 (offence) → Section 139 (presumption) → Section 142 (limitation)
    "The cheque was dishonoured (S.138), so dishonesty is presumed (S.139),
     and the complaint was filed within 30 days (S.142)"

Defence's counter-chain:
    Section 138 proviso (notice) → Section 138 explanation (insufficient funds)
    "Notice was not served within 30 days of dishonour (S.138 proviso),
     and the account had funds at the time of presentation (S.138 explanation)"
```

Build this graph automatically by:
1. Grouping citations by entity (prosecution vs defence)
2. Detecting sequential citations within the same paragraph
3. LLM-based argument chain extraction

**Impact:** "The prosecution relies on Sections 138, 139, 142. The defence counters with 138 proviso. There is no response to the 139 presumption — this may be a gap in the defence."

#### 2B. Precedent Awareness

When a citation is extracted, search for:
- How have courts interpreted this section?
- Are there conflicting High Court interpretations?
- Is there a Supreme Court ruling that settles the interpretation?

**Data source:** Indian Kanoon API, SCC Online, or build your own judgments database.

**Implementation:** After citation extraction, query precedent database for relevant interpretations. Store as `citation_precedents` linking citations to judgment references.

**Impact:** "Section 138 NI Act — 47 High Court judgments support the prosecution's interpretation. See Dashrath Rupsingh Rathod v. State of Maharashtra (2014) for the leading Supreme Court judgment."

#### 2C. Omission Detection (Smart Discovery)

Current Act Discovery finds missing *Acts*. Smarter discovery finds missing *arguments*:

- "The opposing brief cites Section 138 but does not address Section 141 (director liability). Given that the accused is a company, Section 141 is likely relevant."
- "The petition cites Section 397 CrPC for revision but doesn't cite Section 401 (powers of revision). Both are typically cited together."

**Implementation:** Co-citation analysis — "Sections that are typically cited together" learned from a corpus of judgments. Flag when expected co-citations are missing.

### Year 3: From Tool to Legal Intelligence Platform

#### 3A. Multi-Jurisdiction Support

Expand beyond Central Acts:
- State Acts (e.g., Maharashtra Stamp Act vs Karnataka Stamp Act)
- Rules and Notifications (subsidiary legislation)
- SEBI/RBI/IRDAI regulations
- International treaties and conventions (for cross-border matters)

Each jurisdiction has different:
- Citation formats ("Rule 5 of Order XXI" vs "Regulation 11(1)(a)")
- Sources (state gazette vs central gazette)
- Amendment tracking mechanisms

**Architecture:** Pluggable jurisdiction adapters. Each adapter handles extraction patterns, validation rules, and source lookup for its jurisdiction.

#### 3B. Living Legal Knowledge Base

Transform Acts Library from a document store to a queryable legal knowledge base:

```
Query: "What are the current requirements for filing a cheque bounce complaint?"
Answer: "Under Section 142 of NI Act (as amended 2018):
  1. Written complaint to Magistrate (S.142(a))
  2. Within 30 days of cause of action (S.142(b)) — earlier 1 month
  3. After notice period of 15 days expired (S.138 proviso (c))
  Note: The limitation period was changed from 1 month to 30 days
  by Amendment Act 55 of 2002."
```

This requires: structured provisions, amendment tracking, semantic search over legal text, and natural language generation from structured data.

#### 3C. Predictive Citation Analysis

Using historical case data:
- "In cheque bounce cases in [Court X], matters where Section 139 presumption was raised had a 73% success rate for prosecution."
- "The judge assigned to your case has historically interpreted Section 138 strictly — consider strengthening your Section 139 argument."

**Caveat:** Predictive analysis in legal tech is controversial. Frame as "insights" not "predictions." Always show confidence intervals and sample sizes.

#### 3D. Citation-Driven Document Assembly

The reverse of extraction — generation:
- Attorney drafts a petition
- System suggests: "You should cite Section 138 NI Act here to support your claim of dishonesty"
- Auto-generates citation text with correct format for the relevant court
- Links to verified Act text in library

**Impact:** From "verify what was cited" to "suggest what should be cited."

---

## Part 7: Quick Wins (1-2 weeks)

### 7.1 Add Cost Tracking to Verification

Add `CostTracker` to `verifier.py` Gemini calls. Pattern already exists in `extractor.py:507-511`.

**Effort:** 2-3 hours. **Impact:** Full cost visibility.

### 7.2 Cross-Document Citation Dedup

Add matter-level dedup view: group citations by `(act_name_normalized, section, subsection)` and show source documents as a list.

**Effort:** 1 day. **Impact:** Cleaner citation stats, less noise.

### 7.3 Circuit Breaker for Verification

Add circuit breaker to `verifier.py` Gemini calls. Pattern exists in contradiction engine.

**Effort:** Half day. **Impact:** Prevents retry storms during outages.

### 7.4 Distributed Rate Limiting

Replace process-local semaphore with Redis-based distributed rate limiter.

**Effort:** 2-3 days. **Impact:** Prevents 429 errors in multi-worker production.

---

## Part 8: Medium-Term Improvements (2-8 weeks)

### 8.1 Cross-Engine Consistency Checking (Gap #50, FR4.4)

Compare dates across engines — timeline event dates vs citation dates. Flag conflicts.

**Effort:** 2 weeks. **Impact:** Core lawyer workflow.

### 8.2 Cross-Engine Correlation (Gap #15, FR4.3)

Link citations to entities and timeline events. Entity detail panel shows related citations.

**Depends on:** Entity linking fix (see entities engine doc).

### 8.3 Sentence-Level Citation Granularity (Gap #30, FR8.4)

Store exact sentence offsets. Split-view highlights exact sentence, not entire chunk.

**Effort:** 1-2 weeks.

### 8.4 Citation Spoofing Protection (Gap #193)

Distinguish auto-fetched (trusted) vs user-uploaded (unverified) Acts. Hash comparison.

**Effort:** 1 week.

### 8.5 Citation Purpose Classification (Year 1 stepping stone)

Add `purpose` field to extraction: offence_definition, limitation, procedure, presumption, penalty, exemption. Minimal cost — one extra field in existing Gemini call.

**Effort:** 1 week. **Impact:** Foundation for argument graph (Year 2).

---

## Part 9: Comparison with Other Engines

| Dimension | Timeline | Entities/MIG | Contradiction | **Citation** |
|-----------|----------|-------------|---------------|-------------|
| **Stories complete** | 3 (4-1 to 4-3) | 4 (2C.1, 2C.2, 10C.1, 10C.2) | 4 (5-1 to 5-4) | **6 (3-1 to 3-4, 10C.3, 10C.4)** |
| **Critical bugs** | 4 | 1 | 0 | **0** |
| **Test coverage** | Moderate | Moderate | High (136 tests) | **Highest (20 test files)** |
| **Features deferred** | None listed | None listed | CT-1 to CT-4 | **None** |
| **Cost efficiency** | Moderate (3 LLM calls/chunk) | Good (batch extraction) | Excellent (two-tier routing) | **Good (regex + LLM dual strategy)** |
| **Cross-engine links** | Broken | Broken | Limited by other engines | **Not yet implemented** |
| **UX completeness** | Basic timeline view | Graph + detail panel | Filtering + grouping | **Best (3 views + split-view + discovery)** |
| **Long-term readiness** | Needs Phase 2 overhaul | Needs relationship persistence fix | Ready for incremental enhancement | **Ready for incremental enhancement** |

**Key insight:** The citation engine is the gold standard for this codebase. Other engines should adopt its patterns:
- Dual extraction strategy (cheap first, LLM second)
- Comprehensive frontend with multiple view modes
- Real-time progress notifications
- Garbage detection before database writes
- Complete story coverage with nothing deferred

---

## Part 10: Cost Optimization Opportunities

| Optimization | Description | Savings |
|-------------|-------------|---------|
| Regex-first extraction (already done) | Regex catches ~40% of citations for free | Already saving ~40% |
| Cache Act indices across workers | Currently per-worker in-memory; Redis-shared would avoid re-indexing | ~30% reduction in verification time |
| Skip re-verification on reprocess | If citation + Act haven't changed, reuse previous verification result | ~50% reduction on reprocessing |
| Batch Gemini verification calls | Send 3-5 citation verifications per Gemini call instead of 1 | ~60% token overhead reduction |

**Current estimated cost:** ~$0.50-1.50/matter
**Optimized estimated cost:** ~$0.20-0.60/matter

---

## Summary

The citation engine is the **most complete, most tested, and best-designed engine** in the system. Unlike timeline (4 critical bugs), entities (1 critical bug), and contradiction (missing features), the citation engine has no critical bugs, no deferred features, and the best frontend UX.

**But the engine solves the wrong problem at the wrong altitude.** It extracts and verifies text patterns. Attorneys need a system that understands legislative structure, tracks amendments, reasons about applicability, and eventually suggests what to cite — not just verify what was cited.

### What to Build and When

**Now (1-2 weeks):** Cost tracking, circuit breaker, dedup view, distributed rate limiting. These are hygiene.

**Next quarter (Phase 4):** Cross-engine consistency (Gap #50) and correlation (Gap #15). These connect citation data to the rest of the system.

**Year 1:** Structured citation model, legislative history awareness, citation purpose classification. These transform citations from text references into structured legal knowledge.

**Year 2:** Argument graph, precedent awareness, omission detection. These enable legal reasoning, not just legal data extraction.

**Year 3:** Multi-jurisdiction, living knowledge base, predictive analysis, document assembly. These make the system an indispensable legal intelligence platform.

### The Key Architectural Bet

The biggest decision is whether to evolve the current flat model (`act_name + section_number` in a `citations` table) toward a structured legal knowledge graph (`legislative_provisions` → `provision_versions` → `citation_references` → `argument_chains`).

This is not a refactor — it's a paradigm shift. But it's the difference between "a tool that checks citations" and "a platform that understands the law."

**Critical dependency:** Cross-engine work (items in next quarter) benefits from fixing the entity engine's relationship persistence bug and timeline's entity linking. Those fixes (documented in companion analysis docs) should be prioritized first.
