# Ask Jaanch RAG/Chat Engine — Architecture Analysis & Long-Term Plan

> **Date:** 2026-02-06
> **Status:** Investigation complete — two specific bugs found (bbox loss, sources always shown); reasoning is shallow; architecture is solid but solving the wrong problem long-term

---

## Part 1: Current Architecture

### Pipeline Overview

Ask Jaanch is a retrieval-augmented generation (RAG) chatbot that answers attorney questions about case documents. The pipeline:

```
User Query
    ↓
Step 0: Safety check + query rewrite
    ↓
Step 0.5: Response cache check (Redis)
    ↓
Step 1: Intent analysis (GPT-3.5 Turbo)
    → Classifies: LOOKUP | SUMMARY | COMPARISON | TIMELINE | CITATION | GENERAL
    → Selects QueryProfile (adaptive retrieval params)
    ↓
Step 2: Engine execution (parallel via asyncio.gather, 30s timeout per engine)
    → RAG engine: Hybrid search → format context → Gemini Flash generation
    → Citation engine: relevant citation lookup
    → Timeline engine: relevant event lookup
    → Contradiction engine: relevant contradiction lookup
    ↓
Step 3: Aggregation + language policing
    → Strategies: single, parallel_merge, weave, sequential
    → Sources merged and deduped
    → Legal neutrality enforced ("states" not "proves")
    ↓
Step 4: SSE streaming to frontend
    → Events: typing → engine_complete → token (simulated) → complete
    → Sources attached to complete event
    ↓
Step 5: Audit logging (non-blocking)
```

### Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `backend/app/engines/orchestrator/orchestrator.py` | Main query pipeline | 751 |
| `backend/app/engines/orchestrator/streaming.py` | SSE streaming wrapper | 650 |
| `backend/app/engines/orchestrator/executor.py` | Parallel engine execution | 311 |
| `backend/app/engines/orchestrator/aggregator.py` | Result combination + source merge | 1314 |
| `backend/app/engines/orchestrator/adapters.py` | Engine wrappers (RAG, timeline, citation, contradiction) | 1575 |
| `backend/app/engines/rag/generator.py` | Gemini Flash answer generation | 369 |
| `backend/app/engines/rag/prompts.py` | System prompts + context formatting | 229 |
| `backend/app/engines/rag/query_profile.py` | Adaptive retrieval params per query type | 202 |
| `backend/app/services/rag/hybrid_search.py` | BM25 + semantic + RRF fusion | ~500 |
| `backend/app/api/routes/chat.py` | Chat API endpoints | 462 |
| `backend/app/engines/summary/prompts.py` | GPT-4 executive summary prompts | 283 |
| `backend/app/services/summary_service.py` | Summary generation + caching | ~300 |

### RAG Retrieval Pipeline

```
Query → Embedding (Voyage AI / text-embedding-3-small, 1536 dims)
    ↓
Hybrid Search (Supabase RPC: hybrid_search_chunks)
    ├─ BM25 (PostgreSQL tsvector full-text search)
    ├─ Semantic (pgvector HNSW index, cosine similarity)
    └─ RRF Fusion (Reciprocal Rank Fusion, k=60)
    ↓
Results with: chunk_id, content, document_id, page_number, bbox_ids, relevance_score
    ↓
Document name resolution (query documents table)
    ↓
Context assembly (top-K chunks, max 1500 chars each, XML boundaries)
    ↓
Gemini Flash generation (grounded answer with inline citations)
```

**Adaptive retrieval per query type:**

| Query Type | Hybrid Limit | Rerank Top-N | Max Context Chunks | Max Chunk Content |
|-----------|-------------|-------------|-------------------|------------------|
| LOOKUP | 50 | 3 | 5 | 1500 chars |
| SUMMARY | 100 | 12 | 12 | 1500 chars |
| COMPARISON | 80 | 8 | 8 | 1500 chars |
| TIMELINE | 50 | 5 | 5 | 1500 chars |
| CITATION | 50 | 5 | 5 | 1500 chars |

### LLM Models Used

| Purpose | Model | Cost per Query | Rationale |
|---------|-------|---------------|-----------|
| Intent classification | GPT-3.5 Turbo | ~$0.0002 | Fast, cheap classification |
| Answer generation | Gemini 2.5 Flash | ~$0.0003 | Cost-effective grounded answers |
| Executive summary | GPT-4 | ~$0.03 | Accuracy-critical, user-facing (ADR-002) |
| Embedding | text-embedding-3-small | ~$0.000001 | 1536 dims, good for legal text |
| Reranking | Cohere Rerank v3.5 | ~$0.000002 | Available but NOT used in RAG path |
| Evaluation | GPT-4 Turbo | ~$0.035/eval | RAGAS metrics |

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat/{matter_id}/stream` | SSE streaming chat |
| POST | `/api/chat/{matter_id}/message` | Non-streaming chat |
| POST | `/api/chat/report-sse-error` | Error reporting |
| POST | `/api/chat/report-sse-status` | Status reporting |
| DELETE | `/api/chat/{matter_id}/cache` | Clear response cache |

### Frontend Components (14 components, 3 hooks, 12 test files)

| Component | Purpose |
|-----------|---------|
| `QAPanel.tsx` | Main Q&A panel container |
| `FloatingQAPanel.tsx` | Draggable floating chat window |
| `ChatMessage.tsx` | Message bubbles with markdown + sources |
| `StreamingMessage.tsx` | Live streaming response |
| `StreamingResponse.tsx` | Token accumulation with blinking cursor |
| `SourceReference.tsx` | Clickable citation links |
| `EngineTrace.tsx` | Processing metrics (engines, timing, findings) |
| `ChatInput.tsx` | Auto-growing textarea, Enter to submit |
| `ConversationHistory.tsx` | Scrollable message list with auto-scroll |
| `SuggestedQuestions.tsx` | 6 default questions for empty state |
| `ChatErrorMessage.tsx` | Error with retry + countdown |

**Hooks:** `useSSE.ts` (SSE streaming), `useBoundingBoxes.ts` (bbox fetching), `chatStore.ts` (Zustand state)

### Cost Profile

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Standard lookup query | ~₹0.02 ($0.0003) | Per question |
| Summary query | ~₹0.10 ($0.0012) | Per question |
| Executive summary (GPT-4) | ~₹2.50 ($0.03) | Per matter, cached 1hr |
| Embedding | ~₹0.00008 | Per query |
| RAGAS evaluation | ~₹2.92 ($0.035) | Per QA pair (disabled by default) |

---

## Part 2: What Works Well

1. **Hybrid search** — BM25 + semantic + RRF gives robust retrieval across keyword and semantic queries
2. **Query profiling** — Adaptive retrieval params per query type (LOOKUP gets 5 chunks, SUMMARY gets 12)
3. **Multi-engine orchestration** — RAG + citation + timeline + contradiction engines run in parallel with 30s timeouts
4. **Language policing** — Enforces legal neutrality ("states" not "proves", "indicates" not "clearly shows")
5. **Security boundaries** — XML tags around document content prevent prompt injection
6. **Engine traces** — Frontend shows per-engine timing and findings count (transparency)
7. **Cost tracking** — Full per-query cost tracking with INR/USD, matter attribution, quota monitoring
8. **Response caching** — Redis cache for repeat queries
9. **RAGAS evaluation framework** — Built and operational (Faithfulness, Relevancy, Recall)
10. **Streaming UX** — SSE with typing indicator, engine traces, token accumulation

---

## Part 3: Bugs Found — Sources Without Bbox + Sources Always Shown

### Bug 1: Bbox IDs Lost in RAG Generator (Root Cause of Missing Bboxes)

**Location:** `backend/app/engines/rag/generator.py:274-283`

The RAG generator builds the sources array from chunks but **drops bbox_ids**:

```python
sources = [
    {
        "document_name": c.get("document_name") or c.get("documentName") or "Unknown",
        "document_id": c.get("document_id") or c.get("documentId"),
        "page_number": c.get("page_number") or c.get("pageNumber"),
        "chunk_id": c.get("chunk_id") or c.get("chunkId") or c.get("id"),
        # bbox_ids NOT INCLUDED — this is the bug
    }
    for c in chunks_to_use
]
```

The hybrid search results DO contain `bbox_ids` (from the chunks table), and the aggregator (`aggregator.py:940-962`) tries to re-extract them from the full result. But the generator's sources — which are what the streaming pipeline primarily uses — are missing bbox_ids.

**Fix:** Add `"bbox_ids": c.get("bbox_ids")` to the sources dict.

**Additional issue:** Library document chunks always have `bbox_ids=None` (`hybrid_search.py:1010`). Acts/statutes from the shared library will never have bbox highlighting regardless of this fix.

### Bug 2: Sources Always Shown Regardless of Relevance

**Location:** `backend/app/engines/rag/generator.py:274-283`

ALL chunks passed to the LLM are returned as sources. There is no filtering based on whether the model actually cited each source in its answer.

**The problem:** If 5 chunks are retrieved and the model only uses information from 2 of them, all 5 appear as sources in the UI. The attorney sees irrelevant source links.

**Why this happens:** The system prompt instructs the model to cite sources inline as `(Document Name, p. X)`, but there's no post-processing step that:
1. Parses inline citations from the generated answer
2. Matches them back to source chunks
3. Filters the sources array to only include actually-cited chunks

**Fix approach:**
```python
# After generation, parse which sources were actually cited
cited_docs = set()
for match in re.finditer(r'\(([^,]+),\s*p\.\s*(\d+)\)', answer_text):
    cited_docs.add((match.group(1).strip(), int(match.group(2))))

# Filter sources to only include cited ones
sources = [s for s in all_sources if (s["document_name"], s["page_number"]) in cited_docs]

# Fallback: if no citations parsed, include all (graceful degradation)
if not sources:
    sources = all_sources
```

### Bug 3: Document Names Sometimes Show as "Unknown"

**Location:** `backend/app/engines/orchestrator/adapters.py:686-744`

Extensive debug logging (lines 604-734) was added to trace this active bug. The `_get_document_names()` method queries the documents table but can fail silently, returning an empty dict. When this happens, sources show "Unknown Document".

**Root cause:** Race condition or RLS filtering when document_id is valid but user doesn't have access via the service account's query path.

---

## Part 4: Reasoning Quality Assessment

### Current Reasoning: Single-Shot Grounding (Shallow)

The current system uses **single-shot prompting** with grounding instructions. The model is told to:
- Only use information from provided excerpts
- Cite every fact inline
- Never make legal conclusions

**What it does well:**
- Factual extraction ("Who is Respondent No. 5?" → accurate, well-cited)
- Simple lookups ("What is the case number?" → direct answer)
- Key details aggregation ("What are the dates mentioned?" → bullet list)

**What it does poorly:**

1. **No multi-hop reasoning.** Cannot combine facts across chunks with logical inference.
   - "Was the notice sent within the statutory period?" requires: (a) finding the notice date, (b) finding the statutory deadline, (c) calculating the difference. The model gets chunks but can't reliably chain these steps.

2. **No chain-of-thought.** Single-shot generation with no explicit reasoning steps. The model doesn't "think" before answering.

3. **No confidence estimation.** Gemini doesn't return per-statement confidence. The model can't say "I'm 90% sure about the date but only 60% sure about the party name."

4. **No citation verification.** Model is instructed to cite but there's no post-hoc check. It can hallucinate a page number and the system won't catch it.

5. **No contradiction awareness.** The chat engine runs the contradiction engine in parallel but doesn't use its findings to qualify the answer. If Document A says Jan 15 and Document B says Jan 16, the chat should flag this — it doesn't.

6. **Token streaming is simulated.** The full response is generated first, then streamed in 3-char batches with 5ms delay. No latency benefit — just UX illusion. (`streaming.py:459-488`)

7. **Cohere Rerank not used in RAG path.** The `search_with_rerank()` method exists but the RAG adapter uses plain RRF fusion instead (`adapters.py:781`). Missing quality boost.

8. **Context window is small.** Default 5 chunks × 1500 chars = 7,500 chars of context. For complex legal questions spanning multiple documents, this is insufficient.

---

## Part 5: Known Gaps & Issues

### From Architecture Investigation

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | Bbox IDs dropped in generator → sources can't highlight | High | `generator.py:274-283` |
| 2 | All chunks returned as sources, not just cited ones | High | `generator.py:274-283` |
| 3 | Document names sometimes "Unknown" | Medium | `adapters.py:686-744` |
| 4 | Token streaming simulated, not real | Medium | `streaming.py:459-488` |
| 5 | Cohere Rerank not used in RAG path | Medium | `adapters.py:781` |
| 6 | Library chunks always have bbox_ids=None | Low | `hybrid_search.py:1010` |
| 7 | BM25 fallback is silent (user doesn't know) | Low | `hybrid_search.py:430-452` |
| 8 | Post-processing regex may match valid content | Low | `generator.py:233-258` |

### From Gap Analysis

| Gap # | Description | Phase |
|--------|-------------|-------|
| #29 | No completeness verification — can't detect missed content | Phase 8 |
| #30 | No citation granularity (chunk-level, not sentence-level) | Phase 8 |
| #31 | No synonym expansion in search | Phase 8 |
| #32 | No adaptive search fusion (fixed BM25/semantic ratio) | Phase 8 |
| #33 | No search learning from user behavior | Backlog |

### From Phase 2 Backlog (Deferred)

| Feature | Description | Effort |
|---------|-------------|--------|
| Table Extraction (Docling) | Tables not searchable/retrievable correctly | 1-2 weeks |
| RAG Evaluation Dashboard | Visual quality tracking over time | 2-3 weeks |
| Lawyer Verification UI | Attorney marks answers Correct/Wrong/Partial/Hallucinated | 1-2 weeks |
| Adaptive Query Profiles | QueryProfile-based RAG tuning per query type | 1-2 weeks |

### From Tech Specs (Ready for Dev, Not Implemented)

| Tech Spec | Description | Status |
|-----------|-------------|--------|
| `tech-spec-rag-production-gaps.md` | Table extraction + RAGAS evaluation + Inspector/Debug mode | Ready for dev |
| `tech-spec-rag-chat-quality.md` | Adaptive context window (4,500 chars is too small), query-type awareness | Ready for dev |

---

## Part 6: First-Principles Thinking — What Is a Legal Q&A System, Really?

### The Fundamental Question

A legal Q&A system's job is not "retrieve relevant chunks and generate a grounded answer." That's what the current implementation does. But it's solving a **librarian problem** when attorneys need a **reasoning partner**.

**The real question:** What does an attorney need when they ask a question about a case?

### What an Attorney Actually Does When Asking Questions

1. **Fact finding** — "When was the notice sent?" → Simple lookup. Current system handles this well.

2. **Fact synthesis** — "Was the notice sent within the statutory period?" → Requires combining facts from multiple sources + legal knowledge. Current system struggles.

3. **Argument analysis** — "What are the strongest arguments for the petitioner?" → Requires understanding legal frameworks, identifying supporting evidence, and structuring arguments. Current system can't do this.

4. **Risk assessment** — "What are the weaknesses in our case?" → Requires adversarial thinking, identifying contradictions, gaps in evidence, and potential counter-arguments. Current system doesn't attempt this.

5. **Strategic planning** — "What should we focus on in the next hearing?" → Requires understanding case trajectory, timeline, pending issues, and practical priorities. Entirely out of scope today.

The current engine handles #1. It partially handles #2 when all facts are in the same chunk. It cannot do #3, #4, or #5.

### The 10-Year Question: What Kills This Engine?

**Scenario 1: LLMs get cheap and long-context.** When Gemini can process 1M tokens at $0.0001, there's no need for chunking, retrieval, or RAG at all. You just dump all documents into context and ask. The entire retrieval pipeline becomes obsolete. **Survival strategy:** The value shifts from "find the right chunks" to "reason about what the chunks mean." Invest in reasoning, not retrieval.

**Scenario 2: Competing legal AI products.** Harvey, CoCounsel, Westlaw AI all solve the same problem. If Ask Jaanch is just another "search and summarize" tool, it has no moat. **Survival strategy:** Deep integration with Indian legal frameworks, jurisdiction-specific knowledge, vernacular language support — things global competitors won't build.

**Scenario 3: Attorneys trust AI answers.** Today attorneys verify every AI-generated answer. In 10 years, if they trust AI for routine queries, the value shifts to edge cases — contradictions, nuances, ambiguities. A system that says "I found the answer but there's a contradiction in Document 3 you should review" is more valuable than one that just gives the answer. **Survival strategy:** Invest in contradiction-aware, uncertainty-quantifying answers.

**Scenario 4: The question changes.** Today: "What does the document say?" Tomorrow: "What should we do about it?" The gap between information retrieval and legal reasoning is where the real value lies. **Survival strategy:** Build toward legal reasoning, not just legal search.

### First Principles: What Must Be True?

1. **Answers must be provably grounded.** Not "probably grounded" — provably. Every claim in the answer must trace to a specific sentence in a specific document on a specific page. The current system approximates this with inline citations but doesn't verify them.

2. **Uncertainty must be quantified.** "The notice was sent on Jan 15" is not the same as "Document A says Jan 15 but Document B says Jan 16." The system must distinguish between certain facts, contested facts, and missing facts.

3. **Context must be sufficient.** 5 chunks of 1,500 chars is not enough for complex questions. The system needs to adaptively retrieve more context for harder questions, and use document structure (headings, sections) to provide coherent excerpts, not arbitrary chunk boundaries.

4. **Reasoning must be explicit.** The attorney needs to see HOW the answer was derived, not just WHAT the answer is. "I found the notice date in Document A (p.3), the statutory deadline in the NI Act Section 138, and calculated that 47 days exceeds the 30-day limit" — this chain of reasoning builds trust.

5. **The system must know what it doesn't know.** "I couldn't find information about X in the uploaded documents. This might be in a document not yet uploaded, or the information may not have been recorded." Knowing the limits of your own knowledge is the mark of a trustworthy assistant.

---

## Part 7: Long-Term Vision (3-Year Architecture)

### Year 1: From Search to Grounded Reasoning

#### 1A. Citation Verification Pipeline

After generating an answer, verify every inline citation:
- Parse `(Document Name, p. X)` references from the answer
- Check: does the cited page actually contain the claimed fact?
- If not: either fix the citation or flag it
- Filter sources to only show actually-cited documents

**Impact:** Sources become trustworthy. Attorneys stop second-guessing every reference.

#### 1B. Contradiction-Aware Answers

The orchestrator already runs the contradiction engine in parallel. Use its findings:

```
Q: "When was the notice sent?"
A: "According to the Affidavit in Reply (p. 3), the notice was sent on **January 15, 2024**.

⚠️ Note: The Reply Notice (p. 1) states the notice was dated **January 16, 2024**.
This one-day discrepancy may be worth reviewing."
```

**Implementation:** After RAG generates an answer, cross-reference with contradiction engine findings. If any contradiction involves entities or dates mentioned in the answer, append a warning.

#### 1C. Multi-Hop Reasoning with Chain-of-Thought

Replace single-shot generation with structured reasoning:

```
Step 1: Identify what the question requires
    → "Was the notice sent within the statutory period?"
    → Requires: notice date, statutory period length, case filing date

Step 2: Find each required fact
    → Notice date: Jan 15, 2024 (Affidavit, p. 3)
    → Statutory period: 30 days (NI Act Section 138 proviso (c))
    → Case filing: Feb 20, 2024 (Filing document, p. 1)

Step 3: Reason
    → Jan 15 to Feb 20 = 36 days
    → 36 > 30 → Exceeds statutory period

Step 4: Answer with confidence
    → "The notice was sent on Jan 15, 2024, and the case was filed on Feb 20, 2024 —
       36 days later. This exceeds the 30-day statutory period under Section 138
       proviso (c) of the NI Act."
```

**Implementation:** Use a planning prompt that decomposes the question, then sequential retrieval for each sub-question, then a synthesis prompt.

#### 1D. Real LLM Streaming

Replace simulated 3-char-batch streaming with real token streaming from Gemini:

```python
# Current (simulated):
for i in range(0, len(response), 3):
    yield response[i:i+3]
    await asyncio.sleep(0.005)

# New (real streaming):
async for chunk in gemini_client.aio.models.generate_content_stream(...):
    yield chunk.text
```

**Impact:** First-token latency drops from "wait for full generation" to ~200ms.

#### 1E. Enable Cohere Rerank in RAG Path

The reranking infrastructure exists but isn't wired into the RAG adapter. Enable it:

**Location:** `adapters.py:781` — change from `hybrid_search.search()` to `hybrid_search.search_with_rerank()`.

**Impact:** Better relevance ranking, especially for ambiguous queries.

### Year 2: From Grounded Answers to Legal Analysis

#### 2A. Structured Legal Reasoning Engine

Move beyond "find and cite" to "analyze and conclude":

```
Q: "What are the grounds for quashing under Section 482 CrPC?"

Answer (current): Lists facts from documents with citations.

Answer (Year 2):

"Based on the case documents, there are **3 potential grounds for quashing**:

1. **Inherent improbability** — The complaint alleges the cheque was issued on
   Jan 15, 2024, but the accused's bank statement (Annexure C, p. 7) shows the
   account was closed on Dec 30, 2023. *Strength: Strong — documentary evidence
   directly contradicts the complaint.*

2. **Non-compliance with Section 138 proviso** — The statutory notice was sent
   after 35 days (see timeline analysis above). *Strength: Moderate — depends on
   court's interpretation of "reasonable cause".*

3. **Absence of legally enforceable debt** — No underlying agreement or invoice
   is attached. *Strength: Weak — this is a factual defense that may not warrant
   quashing at this stage.*

⚠️ **Counter-arguments to consider:**
- The complainant may argue the account closure was after the cheque was presented
- Section 139 presumption places the burden on the accused"
```

**Implementation:** Structured legal analysis prompts with argument/counter-argument framework. Uses citation engine data (which Acts are cited), timeline data (event sequence), and contradiction data (conflicting facts).

#### 2B. Confidence-Calibrated Answers

Every factual claim gets a confidence qualifier:

| Confidence | Display | Criteria |
|-----------|---------|---------|
| High (>0.9) | No qualifier | Multiple documents agree, exact quote available |
| Medium (0.7-0.9) | "appears to be" | Single document source, paraphrased |
| Low (0.5-0.7) | "possibly" + citation needed | Inferred from context, not directly stated |
| Uncertain (<0.5) | "not clearly established" | Conflicting info or no direct source |

**Implementation:** Per-claim verification against source text. Similarity score between generated claim and source passage determines confidence.

#### 2C. Adaptive Context Window

Replace fixed 5-chunk / 1500-char limits with question-aware context:

```
Simple lookup: 3 chunks, 1000 chars each = 3,000 chars context
Complex synthesis: 15 chunks, 2000 chars each = 30,000 chars context
Cross-document comparison: 20 chunks, 2500 chars each = 50,000 chars context
```

Use Gemini's long-context capability (1M tokens) for complex questions. Cost increase is justified by answer quality.

#### 2D. Memory Across Conversations

Current chat has no long-term memory. Each conversation starts fresh. Add:
- **Matter memory:** Key facts extracted from previous conversations
- **User preferences:** Attorney's areas of focus, terminology preferences
- **Follow-up awareness:** "Earlier you asked about the notice date. Now you're asking about the filing date — should I calculate the interval?"

### Year 3: From Legal Analysis to Case Intelligence

#### 3A. Proactive Insights

Don't wait for questions. When new documents are uploaded:
- "New document uploaded: Reply Notice. I noticed it contradicts the date in the original complaint. See contradiction #47."
- "The timeline now has 15 events. 3 key deadlines are approaching within 30 days."
- "The opposing party cited Section 141 NI Act for director liability. This was not addressed in your reply."

#### 3B. Comparative Case Analysis

"How does this case compare to similar matters in our firm?"
- Citation patterns across matters
- Success rates by argument type
- Judge-specific tendencies

#### 3C. Vernacular Language Support

Indian attorneys work in English, Hindi, Marathi, Gujarati, and other regional languages. Documents may mix languages. The system needs:
- Multilingual retrieval (same query in Hindi finds English documents)
- Transliterated name matching ("Nirav" = "नीरव" = "નીરવ")
- Response in the attorney's preferred language

#### 3D. Expert System Integration

For specific case types (cheque bounce, property dispute, matrimonial), integrate domain-specific reasoning:
- Required elements for each cause of action
- Standard timelines and procedures
- Common defenses and counter-arguments
- Jurisdiction-specific variations

---

## Part 8: Quick Wins (1-2 weeks)

### 8.1 Fix Bbox IDs in Generator Sources

Add `bbox_ids` to the sources dict in `generator.py:274-283`.

**Effort:** 30 minutes. **Impact:** Sources can now highlight text in PDF viewer.

### 8.2 Filter Sources to Only Cited Documents

After generation, parse inline citations from the answer, match to sources, filter.

**Effort:** 1 day. **Impact:** No more irrelevant source links.

### 8.3 Enable Cohere Rerank in RAG Path

Wire `search_with_rerank()` into the RAG adapter.

**Effort:** 2-3 hours. **Impact:** Better relevance ranking for ambiguous queries.

### 8.4 Real LLM Streaming

Replace simulated token streaming with Gemini's streaming API.

**Effort:** 1-2 days. **Impact:** First-token latency drops dramatically.

### 8.5 Fix "Unknown Document" Names

Add error handling and retry logic in `_get_document_names()`. Log document_id on failure for debugging.

**Effort:** Half day. **Impact:** Sources always show correct document names.

---

## Part 9: Medium-Term Improvements (2-8 weeks)

### 9.1 Contradiction-Aware Answers

Cross-reference chat answers with contradiction engine findings. Append warnings when contradictions are relevant.

**Effort:** 1-2 weeks. **Impact:** Attorneys alerted to conflicting information.

### 9.2 Chain-of-Thought Reasoning

Planning prompt → sequential sub-question retrieval → synthesis prompt.

**Effort:** 2-3 weeks. **Impact:** Multi-hop questions become answerable.

### 9.3 Adaptive Context Window

Increase context for complex queries. Use Gemini long-context for synthesis questions.

**Effort:** 1 week. **Impact:** Better answers for complex questions.

### 9.4 Table Extraction (Docling Integration)

Extract tables from PDFs into searchable Markdown. Currently tables are not retrievable.

**Effort:** 1-2 weeks. **Impact:** Financial data, party lists, and dates in tables become searchable.

### 9.5 Citation Verification Pipeline

Post-generation verification of every inline citation.

**Effort:** 2 weeks. **Impact:** Provably grounded answers.

---

## Part 10: Completed Stories & Future Phases

### Completed Stories

| Story | Description | Status |
|-------|-------------|--------|
| 14-11 | Global Search RAG (Q&A Panel) | Done |
| 10a-3 | Content Area QA Panel | Done |
| 10b-1 | Summary Tab | Done |
| 10b-2 | Summary Inline Verification | Done |
| 14-1 | Summary API Endpoint | Done |
| 14-4 | Summary Verification API | Done |
| 14-6 | Summary FE Integration | Done |
| 12-4 | Partner Executive Summary | Done |
| 17-7 | Downstream RAG Trigger | Done |
| 18-8 | RAG Pipeline Integration Tests | Done |

### Tech Specs (Ready for Dev, Not Started)

| Spec | Features | Status |
|------|----------|--------|
| `tech-spec-rag-production-gaps.md` | Table extraction (Docling), RAGAS evaluation, Inspector/Debug mode | Ready |
| `tech-spec-rag-chat-quality.md` | Adaptive context window, query-type awareness | Ready |

### Phase 2 Backlog (Deferred)

| Feature | Stories | Effort |
|---------|---------|--------|
| Table Extraction | TE-1 to TE-4 | 1-2 weeks |
| RAG Evaluation Framework | EF-1 to EF-5 | 2-3 weeks |

### Gap Analysis Items

| Gap # | Description | Phase | Effort |
|--------|-------------|-------|--------|
| #29 | No completeness verification | Phase 8 | High |
| #30 | No citation granularity (sentence-level) | Phase 8 | Medium |
| #31 | No synonym expansion in search | Phase 8 | Medium |
| #32 | No adaptive search fusion | Phase 8 | Medium |
| #33 | No search learning from behavior | Backlog | High |

### Epics Gap Remediation (Phase 8 — Optional for MVP)

| Story | Description | Gap # |
|-------|-------------|-------|
| 9.2 | Synonym expansion in search | #31 |
| 9.4 | Citation granularity | #30 |
| 9.5 | Completeness verification | #29 |

---

## Part 11: Comparison with Other Engines

| Dimension | Timeline | Entities | Contradiction | Citation | **Ask Jaanch RAG** |
|-----------|----------|----------|---------------|----------|-------------------|
| **Stories complete** | 3 | 4 | 4 | 6 | **10** |
| **Critical bugs** | 4 | 1 | 0 | 0 | **2 (bbox loss, irrelevant sources)** |
| **Test coverage** | Moderate | Moderate | High (136) | Highest (20 files) | **High (12 test files)** |
| **Cost efficiency** | Moderate | Good | Excellent | Good | **Excellent (~₹0.02/query)** |
| **Reasoning depth** | N/A | N/A | Rule-based scoring | Extraction only | **Shallow (single-shot)** |
| **Cross-engine integration** | Broken | Broken | Limited | Isolated | **Parallel orchestration (but doesn't use other engines' findings)** |

---

## Part 12: Cost Optimization Opportunities

| Optimization | Current | Projected | Savings |
|-------------|---------|-----------|---------|
| Response caching (already done) | N/A | N/A | Already saving ~30-40% of repeat queries |
| Real streaming (skip full generation first) | ~2s first token | ~200ms first token | UX improvement, not cost |
| Adaptive context (fewer chunks for simple queries) | 5 chunks always | 3 chunks for lookups | ~40% token reduction |
| Intent-based model routing | Gemini Flash for all | GPT-3.5 for lookups, Gemini for complex | ~20% cost reduction |
| Batch embedding queries | 1 embedding per query | Cache common queries | ~50% embedding cost |

**Current estimated cost:** ~₹0.02-0.10/query (~$0.0003-0.0012)
**Already very cheap.** Cost optimization is lower priority than quality improvement.

---

## Summary

Ask Jaanch has **solid retrieval infrastructure** (hybrid search, query profiling, multi-engine orchestration) but **shallow reasoning** (single-shot generation, no multi-hop, no contradiction awareness, no confidence estimation).

**Two specific bugs answer the user's questions:**
1. **Sources without bbox:** `generator.py:274-283` drops `bbox_ids` when building sources. Fix: add the field. Library documents will still lack bboxes.
2. **Unnecessary sources:** All retrieved chunks become sources, regardless of whether the model actually cited them. Fix: parse inline citations from the answer and filter.

**The engine solves a librarian problem when attorneys need a reasoning partner.** It finds relevant text and quotes it back. It doesn't analyze, synthesize, or reason about what the text means.

### What to Build and When

**Now (1-2 weeks):** Fix bbox bug, filter sources to cited-only, enable Cohere Rerank, real streaming, fix "Unknown Document" names. These are bugs and low-hanging fruit.

**Next quarter:** Contradiction-aware answers, chain-of-thought reasoning, adaptive context window, table extraction. These transform the chatbot from "search and quote" to "search, reason, and explain."

**Year 1:** Citation verification pipeline, confidence-calibrated answers, memory across conversations.

**Year 2:** Structured legal reasoning, comparative case analysis, expert system integration.

**Year 3:** Proactive insights, vernacular language support, case intelligence platform.

### The Key Architectural Bet

The biggest question is whether to invest in **better retrieval** (more chunks, better ranking, table extraction) or **better reasoning** (chain-of-thought, multi-hop, contradiction awareness).

The answer is reasoning. Retrieval will become a commodity as LLM context windows grow. A system that can reason about legal documents — identify contradictions, assess argument strength, detect gaps in evidence — will have lasting value. A system that just retrieves and quotes will be replaced by a 1M-token-context LLM.
