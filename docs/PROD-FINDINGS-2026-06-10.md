# Production Findings — 2026-06-10 (live E2E + DB/Railway sweep)

Context: full E2E upload of `3. Affidavit in reply of Respondent No. 2 Hero Honda
Dated 01.09.2023.pdf` (38 pp) to a fresh matter on production
(`ebe2f0bc-7bde-4858-ab12-a43a7241b5c9`, doc `85a23e8d`), to exercise the GAP-26
citation-verification fix end-to-end on the deployed worker. The pipeline ran
**clean** (no crashes/errors; OCR→chunk 38.7s→tables 20s→embed→entities→citations
→resolve→contradiction; DOCUMENT_PROCESSING + SUMMARY_GENERATION both COMPLETED;
llm_cost tracked). But it surfaced several real logic/quality bugs.

Status legend: 🔴 P1 · 🟠 P2 · 🟡 P3 · ✅ healthy

---

## ✅ What worked (deployed-system live verification)
- Full pipeline completed with **zero errors** in Railway worker logs.
- `llm_costs` tracked the embedding call (₹0.039, operation=embedding_batch) — GAP-11 shape healthy on this path.
- The new GAP-26 watchman is live: `/api/health/invariants` returns `verified_citation_vintage_mismatch viol=32`, written by the deployed beat at 10:29 UTC.
- DB anomaly scan: **0 documents stuck >1h**, **0 processing_jobs FAILED in 7d**.

---

## 🔴 FINDING-1 (P1) — Citation extraction mangles section + act name. CONFIRMED LIVE.
On the fresh deployed upload, raw `"Section 205A of the Companies Act, 1956"` was
extracted as **`section="205"`** (the `A` dropped) and **`act_name="A of the
Companies Act"`** (the `A` bled into the act name). Evidence (E2E matter citations):

| raw_citation_text | stored section | stored act_name | status |
|---|---|---|---|
| `Section\n205A of the Companies Act, 1956` | `205` | `A of the Companies Act` | act_unavailable |
| `Section 205(C) of the Companies Act` | `205` | `Companies Act, 2013` | act_unavailable |

Impact (compounding):
1. **Section corruption** — `205A`→`205` is the upstream source of GAP-26's bare-section residual; a `205A` citation can never verify correctly once stored as `205`.
2. **Act-name corruption** — `"A of the Companies Act"` doesn't match the matter's resolved `companies_act_2013` resolution, so the citation orphans to `act_unavailable` (see FINDING-2).
3. **Non-deterministic** — the *same* raw text yielded a clean `act_name` in the historical matter `91a4a4db` (where these verified against the 2013 doc) but a mangled one here. Extraction is unstable across runs.

Root area: citation extraction (LLM parse of section/act_name), upstream of `engines/citation`. This is the real root of GAP-26's residual; the GAP-26 fix only addressed the *verifier* (correctly, per scope). **Highest-value real bug found.**

---

## 🟠 FINDING-2 (P2, context) — The GAP-26 fix was NOT exercised by this E2E.
Because FINDING-1 mangles the act_name, the 205A citations stopped at
`act_unavailable` (mangled name ≠ resolved act) **before** reaching the
section-index verifier where the GAP-26 fix lives. So this E2E did not test
`205A→section_not_found` on fresh data. (GAP-26 remains proven correct via the
`audit_act_index.py` tool — 2013 index has §205, no §205A — and the existing
`91a4a4db` data; it just wasn't re-exercised here.)
Open question: the clean `companies_act_2013 / 205(C)` citation has a valid
resolution (`auto_fetched`, doc=`4f2a53e4`) — it *should* move
`act_unavailable→pending→section_not_found` on the next reconciler tick. Watch it.

---

## 🟠 FINDING-3 (P2, observation) — Severe under-extraction: 8 vs ~149.
The fresh upload extracted **8 citations**; the historical processing of the same
document (`b6375533`) holds **149** Companies citations. A 95% drop. Likely
extraction non-determinism/incompleteness (or the historical count accumulated
over re-runs). Needs a controlled re-run to confirm whether extraction is
systematically dropping citations or the historical number was inflated by retries.

---

## 🟠 FINDING-4 (P2) — Citations to library Acts sit `act_unavailable`/`pending`; the global library isn't auto-used for verification.
A citation to `"Companies Act, 2013"` — which **exists and is `completed` in the
global library** (`4f2a53e4`) — comes back `act_unavailable` on a fresh matter
until/unless a per-matter `act_resolution` auto-fetch links it. System-wide there
are **~35 `pending` citations whose Act IS in the library** (Constitution 9, CCP
9, Companies 6, Contract 4, BNS 3, Income Tax 3, Env 1) not draining to a verdict.
Overlaps the known **reconciler library-binding coverage gap** (GAP-26 follow-up:
`sync_citation_statuses_with_resolutions` only selects resolutions WHERE
`act_document_id IS NOT NULL`). The product *has* the Acts but doesn't reliably
verify against them.

---

## 🟡 FINDING-5 (P3) — 3 act_resolutions stuck in `auto_fetching` for 7 days.
Matter `91a4a4db`, since 2026-06-03: `spatialmappertest`, `testtabledocument`,
`2_application_in_ma_no_10_of...` (a document title mis-parsed as an Act name).
`auto_fetching` is a transient state with no convergence/timeout → stuck forever
(ARCH-003 shape). Low severity (junk/test act names), but the *pattern* (transient
state never reconciled) is the concern. Fix: a sweep that fails/expires
`auto_fetching` older than N hours.

---

## 🟡 FINDING-6 (P3) — 2 library_documents stuck `failed` (`zero_chunks`).
`Test_Unique_Act_2026`, `test-doc-1` (both test data, 2026-05-25). Sitting in
`failed`; cosmetic, but candidates for cleanup.

---

## 🔴 ROOT CAUSE (blast-radius Phase 1, 2026-06-10) — buggy regex in a parallel extraction path
FINDING-1/3/4 share one upstream root: **a regex whose section group captures
DIGITS ONLY**, so every `NNN+alpha` section (205A, 138A, 39A) is truncated and the
stray letter bleeds into the act name.

- **The smoking gun** — `extractor.py:73-76`, `CITATION_PATTERNS[0]`:
  ```python
  r"[Ss]ection\s+(\d+(?:\s*\(\s*\d+\s*\))?(?:\s*\(\s*[a-z]\s*\))?)"   # group1 = \d+ (+ optional (n)/(a)) — NO trailing alpha
  r"(?:\s+(?:of\s+)?(?:the\s+)?)?([A-Z][A-Za-z\s,&]+(?:Act|Code|Rules))" # group2 = act_name, starts where group1 stopped
  ```
  `"Section 205A of the Companies Act, 1956"` → group1=`205` (the `A` unconsumed) → group2=`A of the Companies Act`. **Deterministic** for the regex path.
- **ARCH-001 shape (the real disease).** Extraction runs TWO parallel paths for the same logical work — `_extract_with_regex` (deterministic, BUGGY) **and** Gemini (`prompts.py` instructs it correctly) — then `_merge_citations` dedups. Same raw text yields `"A of the Companies Act"` (regex) OR `"Companies Act, 2013"` (Gemini) depending on which wins the merge → **this is the "non-determinism."** Live proof: the identical raw `"Section 205A of the Companies Act"` is stored under **2 distinct act_names** across rows.
- **Live prevalence (system-wide).**
  - **125** citations: digit-only `section` while their raw text has `NNN+letter` (the 205A→205 corruption class).
  - act_name garbage: `"A of the Companies Act"` ×37, `"A of TORTS Act"` ×13, `"the Act"` ×54, `"said Act"` ×8, `"and"` ×11, `"Act"` ×10, plus dozens of sentence-fragment act_names (`"the Torts Act\nupon notification of a per…"` ×12, `"has been entered into fraudulently…"` ×8, …).
- **Why this is the master root.** It explains: GAP-26's bare-section residual (205A stored as 205 → matches 2013 §205), FINDING-4's `act_unavailable` orphaning (mangled act_name ≠ resolved act → no match), and a large slice of citation-data pollution. GAP-26's verifier fix is correct but downstream of this.
- **Under-extraction (FINDING-3) — separate hypothesis, NOT confirmed:** Gemini output capped at `max_output_tokens=8192` with no retry on truncation (`extractor.py:486`); a verbose batch could silently drop later citations. Needs its own Phase 2.
- **Scope:** ONE entry path (`extract_citations` task → `CitationExtractor`), so a fix lands in one place. The choice (fix the regex `\d+[A-Za-z]?` vs subordinate/remove the regex path in favour of Gemini vs validate-and-reject mangled output) is an **architecture-guard / choose-solution** decision — regex-vs-LLM is the ARCH-001 parallel-path question. NOT decided here (Phase 1 only).

## 🔴 E2E CAPSTONE (2026-06-10 11:14) — fresh upload produced a NEW false-positive on the deployed worker
The reconciler tick verified the one clean-named citation — and it's **WRONG**:
- raw `"Section 205(C) of the Companies Act"` (a **1956** provision, IEPF/unpaid-dividend)
- extraction stored `section="205"` (the `(C)` dropped), `act_name_original="Companies Act"` (no year)
- → **`verified`** against the **2013** Act (`target_doc=4f2a53e4`, §205 = company-secretary functions)

This single result proves the whole chain end-to-end on production:
1. **Extraction** collapsed `205(C)`→`205` (FINDING-1, fresh repro).
2. **GAP-26 fix is powerless here** — stored `205` is a *real* 2013 section, so the verifier legitimately matches it. The fix only stops `205A`-suffix fuzziness; it cannot recover a section extraction already destroyed.
3. **Watchman is blind** — no explicit year in the citation text → `verified_citation_vintage_mismatch` does not flag it.

Implications:
- **FINDING-1 (extraction) is confirmed as the master root** — it defeats the downstream verifier fix.
- **Watchman gap (new):** it catches only *year-explicit* wrong-vintage verifies, not *section-corruption-induced* false positives (no-year citations). A second invariant is warranted (e.g. flag `verified` citations whose `raw_citation_text` section token (incl. suffix/paren) ≠ the stored `section`).
- Minor anomaly: the `companies_act_2013` resolution flipped `auto_fetched`(doc=4f2a53e4) → `missing`(doc=None) at 11:14 while the citation kept `target_act_document_id`; verification binds the doc on the citation directly. Note, not chased.

**Verdict on the E2E goal:** the deployed pipeline + reconciler WORK; but the test meant to "confirm GAP-26" instead proved GAP-26 alone is insufficient and the **extraction L2 fix is essential** — with a reproducible production false-positive as evidence.

## Cleanup owed
- Test matter `ebe2f0bc-7bde-4858-ab12-a43a7241b5c9` (this E2E) — delete after
  investigation, OR keep as the live repro for FINDING-1.
