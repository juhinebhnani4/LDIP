# E2E Verification & Pipeline Optimization Research — 2026-04-17/18

> Complete findings from a deep-dive session covering: E2E production verification of 4 documents, architectural pattern analysis of all findings, contradiction detection optimization research, competitive landscape analysis, and NLI model assessment for Indian legal text.

---

## Table of Contents

1. [E2E Verification Results](#1-e2e-verification-results)
2. [DPP-002 / WPS-001 / DPP-014 Verification](#2-dpp-002--wps-001--dpp-014-verification)
3. [Railway Metrics During E2E](#3-railway-metrics-during-e2e)
4. [8 Bugs Found During E2E](#4-8-bugs-found-during-e2e)
5. [Architectural Pattern Analysis — Wall vs Sticky Note](#5-architectural-pattern-analysis--wall-vs-sticky-note)
6. [Root Cause Analysis](#6-root-cause-analysis)
7. [Corrections After Code Review](#7-corrections-after-code-review)
8. [Pipeline Parallelism Analysis](#8-pipeline-parallelism-analysis)
9. [Contradiction Detection Deep Dive](#9-contradiction-detection-deep-dive)
10. [Optimization Options — What We Gain and Give Up](#10-optimization-options--what-we-gain-and-give-up)
11. [Current LLM Pricing Landscape (April 2026)](#11-current-llm-pricing-landscape-april-2026)
12. [Competitive Landscape — Legal AI Contradiction Detection](#12-competitive-landscape--legal-ai-contradiction-detection)
13. [NLI Models for Indian Legal Context](#13-nli-models-for-indian-legal-context)
14. [Recommended Path Forward](#14-recommended-path-forward)
15. [Commits Made This Session](#15-commits-made-this-session)

---

## 1. E2E Verification Results

**Test setup**: 4 real documents uploaded across 2 matters by 2 users. Both pipeline paths tested concurrently (small-doc chain + chunked chord).

| Doc | Pages | Path | Total Time | Chunks | Entities | Dates | Contradictions | Cost (contradictions) |
|-----|-------|------|-----------|--------|----------|-------|----------------|----------------------|
| Nirav Respo 2 | 16 | small | 16.2 min | 15 | 59 | 8 | 2 | $0.33 |
| Nirav Rejoinder | 33 | chunked | 24.5 min | 31 | 98 | 20 | 20 | $0.87 |
| Rejoinder JHM | 54 | chunked | 22.8 min | 63 | 267 | 51 | 23 | $1.48 |
| Custodian | 25 | small | 18.6 min | 23 | 101 | 33 | 20 | $1.26 |

**Key observations**:
- All 4 documents completed successfully through the full pipeline
- Zero chain errors, zero PipelineTaskError raises
- Both pipeline paths (small-doc chain and chunked chord) worked correctly
- Total contradiction detection cost for 4 docs: **$3.94**
- Doc 3 (54 pages, 267 entities) took LESS time than Doc 2 (33 pages, 98 entities) — explained by the 50-entity cap flattening the curve for large documents

---

## 2. DPP-002 / WPS-001 / DPP-014 Verification

All three fixes verified as **PASSED**:

- **DPP-002** (chain stops on failure): Zero `pipeline_chain_error` events, zero `PipelineTaskError` raises. All pipeline stages fired in correct order for both paths.
- **WPS-001** (dual worker + prefetch): No queue starvation. Concurrent processing worked across 2 matters. `ldip-worker` (default+llm) and `ldip-worker-slow` (heavy+low) both online.
- **DPP-014** (citations dispatch failure): `_mark_job_completed` fired for all 4 docs. No orphaned jobs.

---

## 3. Railway Metrics During E2E

**LDIP (API service)**:
- Requests: Peak of 77 requests around 3:41 PM, mostly 2xx (green)
- Request Error Rate: Flat 0.0% — zero API errors
- Response Time: One spike to ~25s (p99) around 3:50 PM, most requests (p50) under 1s
- Public Network Traffic: Spike to ~2 MB during uploads + polling

**ldip-worker**:
- CPU: Spike to ~3.0 vCPU during peak processing (3:30-4:00 PM), drops to near-zero after
- Memory: Spike to ~3.0 GB during peak, then settles at ~1 GB
- Public Network Traffic: Spike to ~500 MB egress — worker calling Document AI, Gemini, OpenAI, Voyage, Supabase

**Key takeaways from metrics**:
- Worker is I/O-bound, not CPU-bound (3 vCPU for 4 concurrent docs)
- 500 MB egress for 4 documents — mostly LLM API calls and embedding requests
- Memory at 3 GB peak — gevent with 50 greenlets holding connections to multiple external APIs

---

## 4. 8 Bugs Found During E2E

### E2E-001: Summary generation too slow (UX)
- **Severity**: P2
- **Pattern**: Product architecture gap (not an ARCH entry)
- **Finding**: Summary is a Celery background task (`generate_summary`), makes 3 parallel GPT-4o calls, cached in Redis with 1-hour TTL (NOT persisted to DB). 3-5 min typical duration. Frontend polls every 3 seconds. Users expect immediate results after 15-25 min pipeline wait.
- **Deep dive findings**: No structural link between "pipeline complete" and "summary available." The 1-hour Redis TTL means every cache eviction = full re-generation.

### E2E-002: Document AI OCR cold start (252s for 16-page doc)
- **Severity**: P3
- **Pattern**: Vendor platform behavior, tactical fix
- **Finding**: Doc 1 took 252s for OCR vs 14s for Doc 4. Cold start penalty on first Document AI call after deploy.

### E2E-003: Library documents missing from storage
- **Severity**: P2
- **Pattern**: Data quality issue, tactical fix
- **Finding**: ~10 `ocr_and_process_library_document` tasks failed with `storage_missing` errors. Affected: arbitration_and_conciliation_act_1996.pdf, indian_contract_act_1872.pdf, constitution_of_india_1950.pdf, etc.
- **CORRECTION (from code review)**: Initial analysis said "retries indefinitely" — WRONG. The task sets status to FAILED with `quality_flags=["storage_missing"]` on first failure. `resume_stuck_pipelines` only queries `status IN ('pending', 'processing')` — so FAILED docs are NOT re-dispatched. This was a one-time burst.

### E2E-004: Contradiction detection is the pipeline bottleneck
- **Severity**: P2
- **Pattern**: ARCH-004 instance (gateway bypass)
- **Finding**: Consumed 40-70% of total processing time. O(n²) pair generation capped at 50 entities × 25 pairs = 1,250 LLM calls per document max. Entity concurrency semaphore = 3, batch size = 5.

### E2E-005: Excessive GPT-4o escalation in contradiction screening
- **Severity**: P3
- **Pattern**: Leaf-node tuning
- **Finding**: Escalation threshold already lowered from 0.80 → 0.65 (BUG-003). Most escalations return "consistent/unrelated" — GPT-4o call was confirming what Gemini Flash already said.

### E2E-006: Redis beat scheduler lock extension warning
- **Severity**: P2 (upgraded from P3 after code review)
- **Pattern**: **ARCH-002 instance** (P3 — routing without process isolation)
- **Finding**: RedBeat with `redbeat_lock_timeout=300` (5 min). Beat runs in same process as worker. 16+ periodic tasks in beat schedule. 13 of 16 maintenance tasks have NO timeout decorators. When heavy tasks saturate worker, beat's lock extension gets starved → lock expires → `LockNotOwnedError` → beat crashes → **all 16 periodic tasks stop firing silently**.
- Related to INF-010.

### E2E-007: Finalize runs on act documents with no OCR text
- **Severity**: P3
- **Pattern**: **ARCH-003 instance** (non-converging recovery sweep)
- **Finding**: Three independent dispatchers for `finalize_chunked_document`: (1) chord callback, (2) `trigger_pending_merges` every 5 min, (3) `recover_stuck_documents` every 15 min. ACT documents end up COMPLETED with no `extracted_text`. Beat tasks dispatch finalize, finalize skips with `finalize_skipping_no_text`, beat finds them again next cycle. Forever. **The "reconciler" never converges.**

### E2E-008: OpenAI transient 429 retries during contradiction detection
- **Severity**: P3 (downgraded from P2 after verifying actual evidence)
- **Pattern**: ARCH-004 instance (gateway bypass — asymmetric rate-limiter enforcement)
- **Finding**: Exactly **1 transient OpenAI retry** observed in 5,000 lines of logs. Gemini hit **zero 429s**. The rate limiter infrastructure exists at `core/llm_rate_limiter.py` — Gemini calls use it, OpenAI calls in `comparator.py` do NOT. Same system, two providers, asymmetric enforcement. Not a problem at 4-doc concurrency, but the structural gap will surface at higher load.

---

## 5. Architectural Pattern Analysis — Wall vs Sticky Note

### Initial analysis (surface-level, from summaries)
First pass categorized E2E findings as mostly tactical. This was **wrong** — too surface-level, didn't read the code.

### Revised analysis (after reading all code)

| Bug | First Analysis | Revised After Code Review | Pattern |
|-----|---------------|--------------------------|---------|
| E2E-001 | "Missing feature, tactical" | Product architecture gap — no structural link between pipeline and summary | None (product) |
| E2E-002 | "Tactical" | Unchanged — vendor behavior | None |
| E2E-003 | "Retries indefinitely" | **WRONG** — fails once, sets FAILED, stops. Data quality issue. | None |
| E2E-004 | "ARCH-004 instance" | Confirmed + deeper: 1,250 LLM calls/doc ceiling, OpenAI unrate-limited | ARCH-004, P3b |
| E2E-005 | "Threshold tuning" | Confirmed: threshold already at 0.65 | Leaf-node tuning |
| E2E-006 | "Config fix, tactical" | **Instance of ARCH-002**: beat shares process with worker, kills all 16 periodic tasks silently | ARCH-002 (P3) |
| E2E-007 | "Instance of ARCH-003" | Confirmed + deeper: 13 of 16 beat tasks are non-converging recovery sweeps | ARCH-003 |
| E2E-008 | "Instance of P3b, P2 severity" | **Overstated**: only 1 retry observed, downgraded to P3 | ARCH-004 |

### New observations added to ARCH entries

**ARCH-002**: Beat process shares worker process; lock starvation kills all periodic tasks silently. OpenAI is a second unpartitioned upstream (P3b applies to both Gemini AND OpenAI, though only 1 retry at current scale).

**ARCH-003**: **13 of 16 beat tasks are non-converging recovery sweeps** — the system has accumulated compensating mechanisms instead of fixing root causes. E2E-007 (finalize on acts dispatched forever) is proof these sweeps don't converge. Operational cost: 13 sweeps × every 5-30 min × unbounded DB scans with no task timeouts.

**ARCH-004**: OpenAI calls in contradiction engine bypass rate limiter entirely. Gemini calls are rate-limited; OpenAI calls are not. Same system, asymmetric enforcement.

**No new ARCH entries needed** — all E2E findings are new concrete instances of existing debts.

---

## 6. Root Cause Analysis

All 8 E2E issues share one root cause: **features designed for single-document, low-volume usage haven't been tuned for concurrent multi-document processing.**

- Summary generation: designed for one user viewing one matter at a time
- Contradiction detection: designed for one document, not four simultaneous
- Beat scheduler: designed for low-load background sweeps, not under concurrent pipeline pressure
- Library documents: orphan records from data setup, not runtime failures

---

## 7. Corrections After Code Review

### What the initial analysis got WRONG:

1. **E2E-003**: Said "Worker wastes time retrying them on every startup." Code shows task sets FAILED status → beat task only queries PENDING/PROCESSING → no re-dispatch. One-time burst, not infinite loop.

2. **E2E-008**: Said "multiple concurrent retries, P2 severity." Actual logs show exactly 1 retry in 0.47s. Gemini hit zero 429s (paid tier 1000 RPM has ample headroom). Downgraded to P3.

3. **E2E-004 O(n²) claim**: Partially wrong. `itertools.combinations` generates all pairs, but caps at 25 per entity by suspiciousness score. With 50-entity cap, max is 1,250 pairs — not unbounded O(n²). Stage 2.3 incremental detection reduces to O(n) for new document uploads.

4. **Summary generation**: Not "on-demand only" — it's a Celery background task dispatched by API endpoint. 3 parallel GPT-4o calls. Redis cache with 1-hour TTL. NOT stored in database.

---

## 8. Pipeline Parallelism Analysis

### Actual dependency graph (not the current chain shape)

```
OCR (14-252s)
  └→ validate_ocr (1s) + calculate_confidence (1s)  [no downstream dep]
  └→ chunk_document (2-4s)
        ├→ extract_tables (1-2s)      [needs chunks]
        ├→ embed_chunks (5-15s)       [needs chunks — NOT entities]
        ├→ extract_entities (10-30s)  [needs chunks]
        ├→ extract_citations (30-120s)[needs chunks — NOT entities]
        └→ extract_dates (10-30s)     [needs chunks — NOT entities]

extract_entities →
        ├→ resolve_aliases (30-180s)  [needs entities]
        └→ detect_contradictions      [needs entities + chunks]
              └→ _mark_job_completed
```

**Key insight**: `extract_citations`, `extract_dates`, and `embed_chunks` all only need chunks — they don't need entities. Currently forced to wait because they're sequential in the chain or dispatched after entity extraction.

### Time savings from parallelism

| Approach | Time saved | Pipeline goes from → to |
|---|---|---|
| Parallelize stages after chunking | ~90s | 20 min → 18.5 min |
| Reduce contradiction pairs + trust Flash more | 5-8 min | 20 min → 12-15 min |
| Batch contradiction pairs per LLM call | 4-7 min | 20 min → 13-16 min |
| All three combined | 10-15 min | 20 min → **5-10 min** |
| Pre-generate summary as pipeline stage | 3-5 min perceived wait saved | N/A (UX) |

**Conclusion**: Parallelism helps (~90s) but is the smallest lever. Reducing contradiction detection work (fewer pairs, batched LLM calls) is 5-10x more impactful.

**ARCH-001 intersection**: Restructuring the chain for parallelism is the same work as fixing ARCH-001 (two parallel pipelines). Should be done together to avoid making the optimization twice.

---

## 9. Contradiction Detection Deep Dive

### Current architecture

```
Regex suspiciousness scoring → Gemini 2.5 Flash screening → GPT-4o full analysis
```

### How it actually works (from code review)

**Pair generation**: `itertools.combinations(all_statements, 2)` generates ALL pairs, scores by suspiciousness (regex-extracted dates/amounts), takes top 25 per entity. With 50-entity cap: max 1,250 pairs per document.

**Stage 2.3 optimization**: When `source_chunk_ids` is passed (new doc upload), only pairs involving the new document are generated — reduces O(n²) to O(n).

**Gemini Flash screening** ($0.0004/pair):
- Uses `get_rate_limiter(LLMProvider.GEMINI)` — rate-limited
- Prompt biased toward "needs_review" ("cost of missing is 100x worse than false positive")
- Confidence threshold: 0.65 (lowered from 0.80 per BUG-003)
- Skip GPT-4o if result is "consistent"/"unrelated" AND confidence ≥ 0.65

**GPT-4o full analysis** ($0.007/pair):
- Uses `AsyncOpenAI` directly — **NO rate limiter** (ARCH-004 gap)
- Circuit breaker protection via `@with_circuit_breaker(OPENAI_CHAT)`
- OpenAI prompt caching: ~50-70% hit rate on system prompt
- Returns: reasoning, result enum, confidence, evidence type, extracted values

**Concurrency**: 3 entities in parallel (asyncio.Semaphore), 5 pairs per batch (asyncio.gather)

**Caching**: Redis cache with 48-hour TTL, key = SHA256(sorted content + entity name + prompt version)

**Cost tracking**: Both Gemini and GPT-4o costs tracked via `CostTracker` → `llm_costs` table

### Token counts per call

- Gemini screening: ~500-800 input, ~50-100 output tokens
- GPT-4o analysis: ~1,000-2,000 input, ~200-400 output tokens

---

## 10. Optimization Options — What We Gain and Give Up

### Safe optimizations

| Optimization | Time saved | Cost saved | Risk | What we give up |
|---|---|---|---|---|
| **Batch 10 pairs per Gemini screening call** | 5-6 min | ~Same | Low | Position bias (mitigable), debugging granularity |
| **Switch Flash → Flash Lite for screening** | Same | 67% cheaper | Low | More escalations (costs more Tier 2, no accuracy loss) |
| **Skip entities with 1 total mention** | 1-2 min | 20-30% | None | Nothing — can't form pairs anyway |

### Needs validation first

| Optimization | Time saved | Cost saved | Risk | What we give up |
|---|---|---|---|---|
| **Raise Flash threshold 0.65 → 0.50** | 1-2 min | 30-40% GPT-4o | Unknown | Must audit: for past comparisons where Flash said "consistent" at 0.50-0.65, what did GPT-4o say? |

### Risky for the product

| Optimization | Time saved | Cost saved | Risk | What we give up |
|---|---|---|---|---|
| **GPT-4o → GPT-4o-mini for analysis** | Same | 94% cheaper | **High** | Reasoning quality on edge cases. "Matches GPT-4o on binary classification" but contradiction detection isn't purely binary — subtle semantic conflicts need nuance. The reasoning text IS the feature for lawyers. |
| **Embedding pre-filter at >0.92** | -40% pairs | -40% cost | **Dangerous** | Contradictions LIVE in semantically similar text. "Property worth 50 lakhs" vs "property valued at 80 lakhs" = high cosine similarity. May skip the most important contradictions. |

### Corrected filter

**Skip entities with ≤2 mentions**: WRONG as originally stated. Entities mentioned once per document across 2+ documents can absolutely contradict. Correct filter: skip entities with only 1 mention TOTAL across all documents (can't form a pair).

---

## 11. Current LLM Pricing Landscape (April 2026)

### Pricing per 1M tokens (verified via web search)

| Model | Input | Output | Batch Input | Batch Output | Context |
|---|---|---|---|---|---|
| GPT-4o | $2.50 | $10.00 | $1.25 | $5.00 | 128K |
| GPT-4.1 | $2.00 | $8.00 | $1.00 | $4.00 | 1M |
| GPT-4o-mini | $0.15 | $0.60 | $0.075 | $0.30 | 128K |
| GPT-4.1 nano | $0.10 | $0.40 | $0.05 | $0.20 | 1M |
| Gemini 2.5 Flash | $0.30 | $2.50 | $0.15 | $1.25 | 1M |
| Gemini 2.5 Flash Lite | $0.10 | $0.40 | $0.05 | $0.20 | 1M |
| Gemini 2.5 Flash (thinking) | $0.30 | $3.50 | — | — | 1M |
| Gemini 2.5 Pro | $1.25 | $10.00 | $0.625 | $5.00 | 1M |

### Key findings

- **GPT-4o is overkill for classification**: GPT-4o-mini "matches GPT-4o closely on binary classification" at 94% lower cost
- **Gemini 2.5 Flash Lite**: 3x cheaper than Flash, adequate for screening
- **Batch APIs**: Both OpenAI and Google offer 50% discount with 24-hour turnaround
- **Structured JSON output**: GPT-4o 99.9%+ schema compliance, Gemini 99.7%
- **Batch classification research**: Sweet spot at 8-32 items per prompt; batch size 32 yielded BEST results in some models

### Sources

- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- [Gemini Developer API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [GPT-4o-mini classification](https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/)
- [Batch classification research](https://chuniversiteit.nl/papers/classifying-requirements-using-llms)
- [Structured output reliability](https://tokenmix.ai/blog/structured-output-json-guide)

---

## 12. Competitive Landscape — Legal AI Contradiction Detection

### How competitors handle it

**Tier 1 — Enterprise platforms (Harvey, CoCounsel)**:
- Harvey uses contradictions as an **on-demand query**, not an automated pipeline stage
- Lawyer asks: "Analyze these documents for contradictions" → Harvey runs large-context LLM call → returns analysis
- CoCounsel: similar query-driven approach
- Neither does entity-by-entity pairwise comparison automatically

**Tier 2 — Deposition tools (Filevine Depo CoPilot, DepoIQ, NexLaw, Deposely, Paxton)**:
- Focus on within-testimony and testimony-vs-evidence contradictions
- Filevine: real-time transcription → cross-reference against documents → flag inconsistencies
- Document-level comparison, not entity-level

**Tier 3 — Academic research (LegalWiz, 2025)**:
- Closest to what Jaanch does
- Three-stage pipeline: Semantic filtering (embeddings) → NLI classification (BART-large-mnli) → LLM judgment (GPT-4o)
- Performance: 89.5% F1 on self-contradictions, 70.9% F1 on cross-document
- Key finding: **Hybrid (NLI + LLM) beats LLM-only** (75.3% and 46.9% F1 respectively)
- Tested on synthetic English legal documents, NOT Indian court filings

### What Jaanch does that NOBODY else does

**Automated entity-centric cross-document contradiction detection as a pipeline stage.** Every document uploaded automatically gets its entities compared. No user query needed. Contradictions are pre-computed and waiting.

### What Jaanch does WORSE than state of the art

- **Pre-filtering is primitive**: No embedding pre-filter (we have the embeddings but don't use them here), no NLI model stage. Goes straight to Gemini Flash (API call) then GPT-4o.
- **LegalWiz's hybrid achieves 89.5% F1 vs LLM-only 75.3%** — the NLI stage catches things LLMs miss.
- **O(n²) pair generation is brute-force**: LegalWiz uses embedding similarity to filter to top-5 candidates BEFORE classification.

### What Jaanch does BETTER than competitors

1. **Entity-centric grouping**: Compares statements grouped by canonical entity name (with alias resolution) — more focused than arbitrary document-pair comparison
2. **Six-type evidence extraction**: Extracts specific types (date_mismatch, amount_mismatch, factual_conflict, semantic_conflict) with values
3. **Automatic pipeline integration**: Just runs. No user needs to think to ask.

### Sources

- [LegalWiz Paper](https://arxiv.org/html/2510.03418)
- [Harvey AI Litigation](https://www.harvey.ai/solutions/litigation)
- [Filevine Depo CoPilot](https://www.filevine.com/depo-copilot/)
- [Filevine: Catch Inconsistencies Faster](https://www.filevine.com/blog/catch-inconsistencies-faster-how-ai-enhances-your-legal-analysis/)

---

## 13. NLI Models for Indian Legal Context

### Critical gap discovered

**No NLI model exists that's trained on both Indian legal text AND NLI tasks.**

- **InLegalBERT** knows Indian legal language (5.4M court docs) but has NO NLI training
- **mDeBERTa-xnli** can do NLI in Hindi/Marathi (76.9% accuracy) but has NO legal domain knowledge
- **IL-TUR benchmark** (authoritative Indian legal NLP benchmark) **does not include an NLI task** — covers NER, judgment prediction, bail prediction, statute identification, but NOT contradiction detection

### Available models

**Best available for our use case**:

| Model | Languages | NLI Capable? | Legal Domain? | Hindi Accuracy | Size |
|---|---|---|---|---|---|
| [mDeBERTa-v3-base-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7) | 27 inc. Hindi, Marathi | **YES** | No | 76.9% | 300M |
| [L3Cube IndicSBERT-NLI](https://huggingface.co/l3cube-pune/indic-sentence-bert-nli) | 12 Indian languages | Similarity only | No | Not published | ~470M |
| [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) | English (Indian legal) | **No** — needs fine-tuning | **YES** (5.4M docs) | N/A | ~400M |
| [cross-encoder/nli-deberta-v3-large](https://huggingface.co/cross-encoder/nli-deberta-v3-large) | English only | **YES** | No | N/A | 900M |
| BART-large-mnli (LegalWiz) | English only | **YES** | No | N/A | 400M |

### Indian legal text challenges

- High Courts and Supreme Court use English; district courts in north India use Hindi
- Real litigation records are multilingual: pleadings in English, annexures in Hindi, local-language revenue records
- Code-switching is common (Hindi-English mixed text in same document)
- Indian legal phrasing: "petitioner states that", "whereas the respondent contends" — domain-specific patterns

### Options assessed

| Option | Description | Pros | Cons | Effort |
|---|---|---|---|---|
| **A** | Use mDeBERTa-xnli as-is | Hindi + Marathi + English; 76.9% accuracy | Not trained on legal text; may struggle with jargon | 2-3 weeks |
| **B** | Fine-tune InLegalBERT on NLI | Understands Indian legal English | English-only; needs fine-tuning work | 3-4 weeks |
| **C** | Fine-tune mDeBERTa-xnli on our data | Combines multilingual NLI with legal domain; we have labeled data in `statement_comparisons` | Needs GPU, MLOps; 3-4 week project | 3-4 weeks |
| **D** | Skip NLI; use embedding similarity + batched Gemini Flash Lite | No new deps; no torch; no container size increase; most of the speed benefit via batching | Doesn't get the NLI accuracy boost (89.5% vs 75.3% F1 in LegalWiz) | 1-2 weeks |

### Assessment of NLI viability

- **76.9% Hindi NLI accuracy** on general text is significantly lower than 90%+ English — using this on legal text it's never seen is risky
- Adding torch + transformers + model = **~700MB-1.1GB container size increase** (800MB → 1.5-2.1GB)
- Worker memory goes from ~3GB peak to ~4.5GB peak (NLI model loaded in memory)
- Model loading takes 10-30s on cold start
- **The riskiest assumption**: a general-purpose English NLI model works well on Indian legal documents. If it doesn't, the entire effort is wasted.

### Sources

- [mDeBERTa-v3-base-xnli-multilingual](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7)
- [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT)
- [IL-TUR Benchmark](https://arxiv.org/html/2407.05399v1)
- [L3Cube IndicSBERT-NLI](https://huggingface.co/l3cube-pune/indic-sentence-bert-nli)
- [INDICXNLI](https://aclanthology.org/2022.emnlp-main.755.pdf)

---

## 14. Recommended Path Forward

### Immediate (Option D — 1-2 weeks, safe)

1. **Batch Gemini screening** (10 pairs per call): 1,250 calls → 125 calls. **8 min → ~1-2 min.** No new dependencies.
2. **Switch Flash → Flash Lite** for screening: 67% cheaper per call. $0.10/1M input vs $0.30/1M.
3. **Skip entities with 1 total mention**: Can't form pairs. Free filter.
4. **Embedding pre-filter at conservative thresholds** (>0.98 skip, <0.15 skip): Safe thresholds that only skip truly duplicate or completely unrelated text. ~10-20% pair reduction at zero cost.

**Expected result**: 8 min → ~1-2 min contradiction detection. $3.94 → ~$1.50 for 4 docs. No accuracy risk.

### After validation (threshold audit — 1 week)

5. **Audit escalation threshold**: Query `statement_comparisons` for cases where Flash said "consistent" at 0.50-0.65 confidence AND GPT-4o was available. Check agreement rate. If >95% agree, lower threshold to 0.50.

### Future (Option C — after accumulating training data)

6. **Fine-tune mDeBERTa-xnli on our `statement_comparisons` data**: Every GPT-4o verdict is a training label. After 10,000+ labeled pairs, fine-tune a model that knows Indian legal contradiction patterns. This gives the NLI accuracy boost (89.5% F1 in LegalWiz) with domain-specific knowledge.

### Architecture note

The immediate optimizations (batching, Flash Lite, embedding filter) should be implemented **inside the existing `comparator.py`** engine, not as new pipeline stages. This avoids touching the orchestration layer and doesn't conflict with ARCH-001 unification work.

---

## 15. Freemium Strategy Analysis (2026-04-21)

> Added in follow-up session. Analyzes what Jaanch can give away free, based on per-document cost data from the E2E test and competitive research on Indian legal AI pricing models.

### Per-document cost breakdown (from E2E, real data)

| Stage | Cost/doc | % of total | Marginal cost driver |
|---|---|---|---|
| OCR (Document AI) | $0.02-0.08 | ~3% | $1.50/1000 pages |
| Chunking + validation | ~$0.00 | 0% | CPU only |
| Embeddings (Voyage) | $0.01-0.03 | ~2% | Per-chunk embedding call |
| Entity extraction (Gemini) | $0.03-0.10 | ~5% | Per-chunk LLM call |
| Citation extraction (Gemini) | $0.05-0.15 | ~7% | Per-chunk LLM call |
| Date extraction (Gemini) | $0.02-0.08 | ~3% | Per-chunk LLM call |
| **Contradiction detection** | **$0.33-1.48** | **60-75%** | O(n^2) pairs, Gemini Flash + GPT-4o escalation |
| Summary (3x GPT-4o) | $0.05-0.15 | ~5% | 3 parallel calls |
| **TOTAL** | **$0.50-2.00** | 100% | **Dominated by contradiction detection** |

**Key insight**: Without contradiction detection, a document costs ~$0.15-0.50. With it, $0.50-2.00. Contradictions are 60-75% of the per-document cost.

### Competitor research: DraftBot Pro

Source: [draftbotpro.com](https://www.draftbotpro.com/), [pricing page](https://app.draftbotpro.com/checkout/pricing)

- **102,000+ lawyers** (per Instagram, April 2026)
- Built by [Rare Labs](https://www.rarelabs.co/draftbotpro), India-focused
- Access to **2.4 crore+ judgments, orders**
- Features: AI legal drafting (petitions, agreements, notices), legal research, case law analysis, document summarization

**Pricing**:

| Plan | Price | Includes |
|---|---|---|
| Free forever | ₹0 | Legal research (judgment search), limited features |
| Monthly | ₹999/mo | 1.2 lakh words in drafts, 35-page uploads, Word/PDF export, 1 GB storage |
| Yearly | ₹9,990/yr (2 months free) | 16 lakh words in drafts, 35-page uploads, 5 GB storage |

**Their model**: Give away **search** (zero marginal cost — index lookup over pre-indexed corpus). Charge for **AI drafting** (LLM cost per draft). The free feature hooks lawyers into the ecosystem; the paid feature is where the LLM cost lives.

### Competitor research: Harvey AI, CoCounsel, Indian legal tech

**Harvey AI**: No free tier. Enterprise-only, sales-driven. ~$150-500/user/month (estimated). 15,000+ lawyers across elite firms (A&O Shearman, PwC). Contradictions are an on-demand query, not an automated pipeline.

**CoCounsel (Thomson Reuters)**: No standalone free tier. Bundled into Westlaw Precision. "CoCounsel Core" free for all Westlaw subscribers. Post-acquisition model: AI built into tools you already pay for.

**CaseMine**: Free basic search + case summaries. Paid: CaseIQ (upload brief → find relevant cases you missed). 500K+ users (including free). Their aha moment: "CaseIQ found authorities I didn't know about."

**NearLaw**: Free basic Indian case law search. Paid: advanced filters, full-text. Budget-friendly (INR 5,000-15,000/year). Targets solo practitioners.

**Indian Kanoon**: Entirely free (ad-supported). Full case law search. Proves Indian lawyers use free digital tools. Monetizes via ads + API access.

**Key pattern across all**: Free = search/discovery (zero marginal cost). Paid = AI analysis (LLM cost per use). The conversion trigger is always: **"the AI found something you missed, on your own document."**

### What Jaanch can give away (near-zero marginal cost)

| Feature | Cost | Value to lawyer |
|---|---|---|
| OCR + text extraction | ~$0.02-0.08/doc | Read scanned PDFs on any device |
| Basic metadata (parties, court, case number) | ~$0.00 | Auto-fills case index (regex extraction) |
| Timeline view (dates from text) | ~$0.00 | See all dates at a glance |
| Document search within matter | ~$0.00 | Full-text search on OCR text |
| Statute/section lookup | ~$0.00 | Quick reference |

### What Jaanch must charge for

| Feature | Cost | Value to lawyer |
|---|---|---|
| Entity extraction | $0.03-0.10/doc | See all people, companies, addresses |
| Citation verification | $0.05-0.15/doc | Know if opposing counsel cited correctly |
| Contradiction detection | $0.33-1.48/doc | Find inconsistencies across affidavits |
| AI Summary | $0.05-0.15/doc | Case brief in 30 seconds |
| Q&A / RAG | $0.01-0.05/query | Ask questions about your case |

### Three strategies evaluated

**Strategy A — "Preview, Not Analysis"** (DraftBot model):
- Free: OCR + text search + timeline + metadata
- Paid: Everything LLM-powered
- Free cost: ~$0.05/doc
- Problem: **Aha moment is too weak.** Indian Kanoon already offers free text search. Doesn't show Jaanch's differentiation.

**Strategy B — "First Taste Free"** (credits model):
- Free: **Full pipeline for first 3 documents/month**
- Paid: More documents
- Free cost: ~$1.50-6.00/user/month (at current prices) → **$0.50-1.50/user/month after Tier 1 optimization**
- Strength: **Strongest possible aha moment.** Lawyer sees contradictions on their own documents.
- Conversion path: Upload 3 docs (one matter), see the value, need to add more → hits limit → upgrades

**Strategy C — "Show, Don't Give"** (teaser model):
- Free: Full pipeline runs, results partially gated (show contradiction count + first 1, blur the rest)
- Paid: See all results
- Free cost: Same as B (pipeline still runs)
- Problem: Same cost as B, plus user frustration at being teased

### Recommendation: Strategy B with contradiction optimization first

1. **Do Tier 1 item #1** (contradiction optimization) — reduce per-doc cost from $0.50-2.00 to $0.15-0.50
2. **Then launch free tier**: 3 docs/month, full pipeline
3. Free cost per user: ~$0.50-1.50/month (sustainable)
4. At 1000 free users: ~$500-1,500/month
5. At 5-10% conversion to ₹999/mo: ₹50K-100K/month revenue

**Pricing structure**:

| Plan | Price | Docs/month | Target |
|---|---|---|---|
| Free | ₹0 | 3 docs (full pipeline) | Acquisition, aha moment |
| Pro | ₹999/mo | 25 docs | Solo practitioners |
| Unlimited | ₹1,999/mo | Unlimited | Small firms |
| Enterprise | Custom | Custom + SLA | Large firms, legal departments |

### The aha moment

From PLG research: top companies hit 65%+ activation by optimizing time-to-value to 3-5 minutes. For lawyers, the aha moment is **"it found something I missed."**

Jaanch's natural aha moment: Upload 2 documents → see "Found 3 contradictions between Respondent's Affidavit and Rejoinder" → lawyer is hooked. **Nobody else does this automatically** — not Harvey (on-demand query), not CoCounsel (within Westlaw), not DraftBot Pro (drafting focus, no contradiction detection).

**This is why contradiction optimization is the #1 priority**: it's simultaneously the biggest time reduction (20 min → 8 min), the biggest cost reduction ($2 → $0.50), AND the prerequisite for a viable free tier that showcases Jaanch's unique feature.

### Existing infrastructure for free tier gate

Per-user usage tracking already exists:
- **Backend**: `/api/usage/summary` endpoint (`backend/app/api/routes/usage.py`) counts documents, pages, and queries per user, grouped by matter
- **Frontend**: `/usage` page, `useUsageSummary` hook, `useUsageDashboard` hook
- **Admin**: Cost monitoring, LLM quota widgets, cost report per matter

**What's still needed** (~1 day):
- `user_plans` table (plan_type, docs_per_month, created_at)
- Upload-time check in `documents.py`: count docs this month, reject if >= limit
- Frontend: usage bar ("2 of 3 free documents used") + upgrade CTA

### Sources

- [DraftBot Pro Homepage](https://www.draftbotpro.com/)
- [DraftBot Pro Pricing](https://app.draftbotpro.com/checkout/pricing)
- [DraftBot Pro - Rare Labs](https://www.rarelabs.co/draftbotpro)
- [CaseMine CaseIQ](https://www.casemine.com/caseiq)
- [Best Legal AI Tools 2026 - Spellbook](https://www.spellbook.legal/learn/legal-ai-tools)
- [Aha Moment Guide - Userpilot](https://userpilot.com/blog/aha-moment/)
- [PLG Conversion Rates - SlashExperts](https://slashexperts.com/post/plg-conversion-rates-and-optimization-guide/)
- [Freemium Model Design 2026 - Rework](https://resources.rework.com/libraries/saas-growth/freemium-model-design)
- [Top AI Tools for Indian Lawyers 2026 - VIDUR](https://vidur.in/top-10-ai-tools-for-lawyers-in-india/)
- [Best Legal Research Tools India 2026 - CaseMine Blog](https://www.casemine.com/blog/best-legal-research-tools-2026-india-ai)

---

## 16. Priority Roadmap Summary (2026-04-21)

> Business-driven sequencing. Full details in [BUGS.md](BUGS.md) Priority Roadmap section.

**Tier 1 (weeks 1-4, prerequisite for free tier launch)**:
1. Contradiction optimization — 8 min → 1-2 min, $2 → $0.50/doc
2. UX loading state cluster — 5 "flash wrong state" bugs
3. Summary pre-generation — ready when user arrives
4. Q&A processing guard — "processing" instead of "no results"

**Tier 2 (weeks 3-5, reliability)**:
5. Beat process isolation
6. Non-converging sweep fix
7. Library document cleanup
8. Escalation threshold audit

**Tier 3 (weeks 5-10, structural)**:
9. LLM domain gateway (ARCH-004)
10. API type codegen (ARCH-006)
11. Reconciler (ARCH-003)

**Tier 4 (long-term)**:
12-15. Pipeline unification, worker isolation, NLI model, RPC versioning

---

## 17. Commits Made This Session

| Commit | Message |
|---|---|
| `19517e9` | `docs: add E2E verification results + 8 new bugs from 4-doc concurrent test` |
| `6bb3cef` | `docs: cross-reference E2E findings to ARCH-002/003/004 with code-grounded evidence` |
| `8a078ab` | `docs: correct E2E-008 severity P2→P3 based on actual evidence (1 retry, not multiple)` |

### Files modified this session

- `BUGS.md` — Added Section 7 (E2E Verification Findings), 8 new bugs, updated ARCH-002/003/004 with E2E evidence, corrected E2E-003/006/007/008
- `ARCH-PATTERNS.md` — Updated P3b with OpenAI as second concrete instance
