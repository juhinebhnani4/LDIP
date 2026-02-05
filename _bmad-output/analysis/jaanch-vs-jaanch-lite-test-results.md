---
date: 2026-01-31
author: Juhi
type: comparative-analysis
documents_tested:
  - TORTS Act 1992.pdf (22 pages, native text PDF)
  - APPLICATION IN MA NO 10 OF 2023 (421 pages, scanned PDF)
---

# Jaanch vs Jaanch Lite: Live Test Results

## Test Summary

| Dimension | Jaanch (Full) | Jaanch Lite | Verdict |
|-----------|--------------|-------------|---------|
| **Document Parsing** | Google Doc AI | Landing AI ADE (DPT-2) | ADE wins on bbox, but credits ran out |
| **Embeddings** | OpenAI text-embedding-3-small (1536d) | Voyage AI voyage-law-2 (1024d) | voyage-law-2 is legal-specific |
| **Reranking** | Cohere rerank-v3.5 | Voyage AI rerank-2.5 | rerank-2.5 has legal instructions |
| **Citation Extraction** | 4-step pipeline (regex + LLM + verification) | Regex-only (8 patterns) | Jaanch far superior |
| **Vector Store** | Supabase pgvector + RLS | ChromaDB (local) | pgvector for production |
| **Search Quality** | Parent-child chunking + Cohere rerank | ADE chunks + Voyage rerank | Both returned relevant results |

---

## 1. Document Parsing

### TORTS Act 1992.pdf (22 pages, native text)

| Metric | Jaanch (Google Doc AI) | Jaanch Lite (Landing AI ADE) |
|--------|----------------------|----------------------------|
| Chunks produced | ~40-60 (parent-child) | 74 chunks |
| Parse time | ~5-8s | ~13s |
| Bounding boxes | Requires 71 separate bbox files | Native on every chunk |
| Tables detected | Yes | Yes (separate chunk type) |
| Cost | $0.001/page ($0.022) | $0.01/page ($0.22) |

**ADE advantage**: Every chunk has a native bounding box. Jaanch's current architecture requires 71 separate bbox coordinate files to achieve the same visual grounding.

**ADE disadvantage**: 10x more expensive per page. On a 421-page scanned document, ADE costs ~$4.21 vs Doc AI ~$0.42.

### APPLICATION document (421 pages, scanned PDF)

| Metric | Jaanch Lite (ADE) | PyMuPDF fallback |
|--------|-------------------|-----------------|
| Chunks from first run | 1,262 chunks (229/421 pages) | 0 (scanned images, no text layer) |
| OCR quality | Successfully OCR'd scanned handwritten/printed legal documents | Cannot OCR at all |
| Pages failed | 192 pages (402 Payment Required - credits exhausted) | All 421 pages |
| Parse time | ~158s for 421-page doc (with failures) | N/A |

**Critical finding**: ADE successfully OCR'd scanned Indian legal documents (affidavits, applications). PyMuPDF extracted zero text. For Jaanch's use case (scanned court documents), OCR is essential.

**Credit exhaustion issue**: Landing AI free tier ran out mid-parse on a 421-page document. Production needs a paid plan or credit monitoring.

---

## 2. Citation Extraction

### TORTS Act 1992 (regex extraction)

| Metric | Result |
|--------|--------|
| Total citations found | 4 |
| Valid citations | 2 (50% precision) |
| False positives | 2 |

**Valid extractions:**
- S. 2, Arbitration and Conciliation Act, 1996
- S. 15, Industrial Disputes Act, 1947

**False positives:**
- "section 3" matched with surrounding text as act name ("has been entered into fraudulently or to...")
- "section 3" matched with garbage text ("either as a principal, conspirator or ab...")

### Comparison with Jaanch's citation pipeline

| Feature | Jaanch (Full) | Jaanch Lite |
|---------|--------------|-------------|
| Extraction method | 4-step: regex pre-filter -> LLM extraction -> abbreviation resolution -> verification against act text | Regex only (8 patterns) |
| Precision | ~95% (post-verification) | ~50% (many false positives) |
| Recall | High (LLM catches what regex misses) | Low-medium (only common patterns) |
| Abbreviation handling | Known acts database + LLM resolution | Basic abbreviation map (50+ acts) |
| Verification | Cross-references against actual act text in DB | Broken (ChromaDB query bug) |
| Hindi/regional patterns | Limited | Has dhara pattern but untested |

**Verdict**: Jaanch's citation pipeline is significantly more accurate. The regex-only approach produces too many false positives for production use. The LLM extraction + verification loop is essential for the 95% accuracy requirement.

---

## 3. RAG Search Quality

### Voyage AI voyage-law-2 + rerank-2.5 (TORTS Act)

**Query: "What are the powers of the Special Court?"**
| Rank | Page | Rerank Score | Content Match |
|------|------|-------------|---------------|
| #1 | 11 | 0.828 | "Procedure and powers of Special Court..." - Direct hit |
| #2 | 14 | 0.797 | "Powers of the Special Court in arbitration matters..." - Direct hit |
| #3 | 12 | 0.773 | "Jurisdiction, powers, authority and procedure of Special Court in civil matters..." - Direct hit |

**Query: "What is the procedure for attachment of property?"**
| Rank | Page | Rerank Score | Content Match |
|------|------|-------------|---------------|
| #1 | 4 | 0.711 | "Notwithstanding anything contained in the Code...notification under sub-sect" - Relevant |
| #2 | 4 | 0.562 | "The property attached under sub-section (3) shall be dealt with by the Custodian..." - Direct hit |
| #3 | 5 | 0.562 | "Contracts entered into fraudulently may be cancelled..." - Tangentially related |

**Query: "Who is the Custodian and what are their duties?"**
| Rank | Page | Rerank Score | Content Match |
|------|------|-------------|---------------|
| #1 | 3 | 0.688 | "Appointment of Custodian by the Central Government" - Direct hit |
| #2 | 4 | 0.594 | Property attachment duties - Related |
| #3 | 3 | 0.578 | Powers of custodian - Related |

### Assessment

- **Top-1 precision**: 3/3 queries returned the most relevant chunk first
- **Rerank scores**: 0.56-0.83 range, showing good differentiation
- **Legal instruction-following**: rerank-2.5 was given the instruction "Prioritize chunks containing statutory provisions, section numbers, or legal definitions that directly address the query" — and it correctly prioritized statutory text

### Comparison notes with Jaanch

Jaanch uses Cohere rerank-v3.5 without domain-specific instructions. Voyage rerank-2.5 supports instruction-following, which means we can tune reranking for legal document types (statutes vs affidavits vs judgments vs contracts).

The research data shows Voyage rerank-2.5 scores +8-13% over Cohere v3.5 on legal benchmarks (BEIR-legal), at 40x lower cost ($0.05 vs $2.00 per 1M tokens).

---

## 4. Embedding Quality

| Feature | Jaanch (OpenAI) | Jaanch Lite (Voyage) |
|---------|----------------|---------------------|
| Model | text-embedding-3-small | voyage-law-2 |
| Dimensions | 1536 | 1024 |
| Legal benchmark advantage | General-purpose | +6-10% on legal datasets |
| Cost | $0.02/1M tokens | $0.12/1M tokens (6x more) |
| Free tier | None | 50M tokens free |
| Indexing speed (74 chunks) | ~2-3s | ~3s |

**Trade-off**: Voyage is 6x more expensive per token but specifically trained on legal text. For a legal platform, the accuracy advantage likely justifies the cost. Storage is also 33% smaller (1024 vs 1536 dims).

---

## 5. Infrastructure & Production Readiness

| Feature | Jaanch (Full) | Jaanch Lite |
|---------|--------------|-------------|
| Vector store | Supabase pgvector (PostgreSQL) | ChromaDB (local) |
| Multi-tenancy | 4-layer RLS isolation | None |
| Caching | Redis (embeddings, results) | None |
| Task queue | Celery + Redis | None |
| Circuit breakers | All external API calls | None |
| Rate limiting | Per-user, per-endpoint | None |
| Error handling | Comprehensive with retries | Basic try/catch |
| Monitoring | Structured logging + metrics | structlog only |

**Verdict**: Jaanch Lite is a POC, not production-ready. The full Jaanch infrastructure (RLS, circuit breakers, task queues, caching) is essential for multi-tenant production use.

---

## 6. Bugs Found in Jaanch Lite

1. **ChromaDB multi-field where clause** (`src/acts/verifier.py`): Uses `where={"act_name": "...", "section_number": "3"}` but ChromaDB requires `$and` operator. Breaks citation verification entirely.

2. **BoundingBox attribute naming**: Code uses `bbox.x` but the Pydantic model has `bbox.x0`. Display/export code crashes.

3. **Instructor + Gemini SDK mismatch**: Code imports `google.generativeai` (old SDK) but `google-genai` (new SDK) is installed. `instructor.from_gemini()` doesn't exist. LLM extraction falls back to regex-only silently.

4. **Regex false positives**: "Section X" pattern captures surrounding text as the act name when no explicit act is mentioned nearby. Needs negative lookahead or context window limiting.

5. **No error handling for ADE credit exhaustion**: 402 errors are logged but parsing continues, wasting time on API calls that will all fail.

---

## 7. Key Takeaways for Architecture Decision

### What to adopt from Jaanch Lite into Jaanch:
1. **Voyage AI voyage-law-2 embeddings** — legal-specific, measurably better on legal benchmarks
2. **Voyage AI rerank-2.5** — instruction-following reranking, cheaper, better on legal tasks
3. **Landing AI ADE for bounding boxes** — eliminates 71 bbox files, native grounding per chunk
4. **Regex pre-filter for citations** — fast first pass before LLM extraction (hybrid approach)
5. **Pre-indexed acts library** — one-time indexing of 50+ Indian acts for citation verification

### What to keep from Jaanch (non-negotiable):
1. **LLM citation extraction + verification loop** — regex alone gets ~50% precision
2. **Supabase pgvector + 4-layer RLS** — ChromaDB has no multi-tenancy
3. **Parent-child chunking (1750/550)** — proven chunking strategy for legal docs
4. **Celery + Redis task queue** — async processing for large documents
5. **Circuit breakers on all external APIs** — ADE credit exhaustion proved this is critical
6. **Model routing rules** — never GPT-4 for ingestion, never Gemini for user-facing

### What needs more testing:
1. **ADE vs Google Doc AI OCR quality** — need side-by-side on same scanned documents (blocked by ADE credits)
2. **Voyage vs OpenAI embedding quality** — need same queries on same documents with both
3. **Cost at scale** — ADE is 10x more expensive per page; Voyage is 6x more expensive per token
4. **ADE handling of Hindi/regional language documents** — untested

---

## 8. Cost Comparison (per 100-page document)

| Component | Jaanch (Current) | Jaanch + Upgrades |
|-----------|-----------------|-------------------|
| Parsing | Google Doc AI: $0.10 | Landing AI ADE: $1.00 |
| Embedding | OpenAI: $0.004 | Voyage: $0.024 |
| Reranking (per search) | Cohere: $0.004 | Voyage: $0.0001 |
| LLM extraction | Gemini 2.5-flash: $0.02 | Gemini 2.5-flash: $0.02 |
| **Total (ingestion)** | **~$0.13** | **~$1.05** |
| **Total (per search)** | **~$0.004** | **~$0.0001** |

ADE increases ingestion cost 8x but search cost drops 40x. For a platform where documents are ingested once but searched many times, this trade-off may be favorable.
