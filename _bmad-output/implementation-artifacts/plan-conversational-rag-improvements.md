# Plan: Conversational RAG Improvements

**Created:** 2026-02-16
**Source:** Research doc `technical-conversational-ai-context-management-research-2026-02-05.md` + code review of session memory and streaming orchestrator
**Prerequisite:** NOT required before RAGAS evaluation — these are parallel workstreams
**Total Estimated Effort:** 12-18 days across all phases

---

## Current State — What's Already Built

| Component | Status | File(s) |
|-----------|--------|---------|
| Redis session memory (7-day TTL) | Built (Story 7-1) | `backend/app/services/memory/session.py` |
| Sliding window (20 messages) | Built (Story 7-2) | `backend/app/services/memory/session.py` |
| Entity tracking (pronoun resolution) | Built (Story 7-3) | `backend/app/services/memory/session.py` |
| Session archival to Matter Memory | Built | `backend/app/services/memory/session.py` |
| Session loading in orchestrator | Built | `backend/app/engines/orchestrator/streaming.py:130-210` (`_prepare_session`) |
| SSE streaming protocol | Built | `backend/app/api/routes/chat.py`, `streaming.py` |

**What's NOT built:** Conversation summary injection, query rewriting for follow-ups, citation follow-up support, prompt structure optimization for caching.

---

## Phase 1: Conversation Summary Injection (2-3 days)

**Value:** ~70% of total conversational improvement. Makes follow-up questions actually work.

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| G1 | Build conversation summarizer | New: `backend/app/services/memory/summarizer.py` | Summarize last 5 messages into 2-3 sentence context. Use Gemini Flash (cheap, fast). Called when session has >2 messages. | 4 hours |
| G2 | Inject summary into RAG prompt | `backend/app/engines/rag/prompts.py`, `streaming.py` | Add `<conversation_context>` section to prompt template, between system prompt and retrieved chunks. Orchestrator passes summary from session prep. | 3 hours |
| G3 | Restructure prompt for prefix caching | `backend/app/engines/rag/prompts.py` | Reorder: system prompt (static) → matter context (semi-static) → conversation summary → chunks → user query. Static content first = better cache hits. | 2 hours |
| G4 | Cache conversation summaries in Redis | `backend/app/services/memory/session.py` | Don't re-summarize on every message. Cache summary, invalidate when new message added. Append-only pattern: summarize old messages, keep recent 3 verbatim. | 3 hours |

**How it works:**
```
Current flow:
  User query → load session → retrieve chunks → generate answer

Enhanced flow:
  User query → load session → summarize conversation (cached) →
  inject summary into prompt → retrieve chunks → generate answer
```

**Success metric:** Pronoun resolution accuracy from ~60% → >85% (test with "What about their obligations?" after asking about a specific party).

---

## Phase 2: Query Rewriting (3-4 days)

**Value:** Better retrieval for ambiguous follow-up queries. "What about penalties?" becomes "What penalties does the contract specify for termination?"

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| G5 | Build query rewriter service | New: `backend/app/services/rag/query_rewriter.py` | Use Gemini Flash to rewrite ambiguous queries using conversation context. Input: raw query + conversation summary + entities. Output: self-contained query. | 4 hours |
| G6 | Integrate rewriter into search pipeline | `backend/app/services/rag/hybrid_search.py`, `streaming.py` | Call rewriter BEFORE embedding/BM25 search. Use rewritten query for retrieval, original query for display. | 3 hours |
| G7 | Add rewrite bypass for standalone queries | `backend/app/services/rag/query_rewriter.py` | Detect when query is already self-contained (no pronouns, no implicit references). Skip rewrite to save latency + cost. Simple heuristic first, LLM classification later. | 2 hours |
| G8 | A/B test rewritten vs original queries | `backend/app/engines/orchestrator/streaming.py` | Log both original and rewritten queries. Compare retrieval quality. Feature flag to enable/disable rewriting. | 3 hours |

**How it works:**
```
User: "What does the contract say about termination?"
Assistant: "The contract specifies 30-day notice..."

User: "What about penalties?"
→ Rewriter: "What penalties does the contract specify for termination?"
→ This rewritten query goes to hybrid search
→ Much better retrieval than "What about penalties?" alone
```

**Success metric:** Retrieval relevance (context precision) improvement measurable via RAGAS evaluation.

**Dependency:** Phase 1 (needs conversation summary as rewriter input). Also benefits from RAGAS being operational (to measure improvement).

---

## Phase 3: Citation Follow-up Support (2-3 days)

**Value:** "Tell me more about source 2" or "What else does that document say?" — currently impossible.

| ID | What | File(s) | Why | Effort |
|----|------|---------|-----|--------|
| G9 | Track citations in session | `backend/app/services/memory/session.py`, `streaming.py` | After generating answer, store citation metadata (document_id, page_number, chunk_id) in session. Map citation numbers [1], [2] to actual sources. | 3 hours |
| G10 | Detect citation reference queries | New: `backend/app/services/rag/citation_followup.py` | Pattern detection: "tell me more about source/citation/reference X", "what else does document Y say", "expand on point 3". Returns citation index or None. | 3 hours |
| G11 | Implement source-specific deep retrieval | `backend/app/services/rag/hybrid_search.py` | When citation follow-up detected: retrieve more chunks from the SAME document, expanding around the original citation's page. Skip broad search, go deep on one source. | 4 hours |
| G12 | Update frontend to show clickable citations | `frontend/src/components/chat/` | Make citation numbers [1], [2] clickable. On click, auto-fill "Tell me more about [X]" in chat input. Visual feedback that citations are interactive. | 3 hours |

**How it works:**
```
User: "What are the termination clauses?"
Assistant: "The contract specifies... [1] ... also mentions... [2]"
  Session stores: {1: {doc: "contract.pdf", page: 5}, 2: {doc: "amendment.pdf", page: 2}}

User: "Tell me more about [2]"
→ Detector identifies citation reference to [2]
→ Deep retrieval from amendment.pdf, pages 1-4 (expanded window)
→ Answer with more detail from that specific source
```

**Dependency:** Phase 1 (conversation context), session citation tracking.

---

## Phase 4: Advanced — Future (5+ days)

Not planned in detail. Implement after Phases 1-3 prove value.

| ID | What | Why | Effort |
|----|------|-----|--------|
| G13 | Semantic caching for repeated queries | If 10 users ask "What is Section 138?", cache the answer. Vector similarity on query embeddings to detect near-duplicates. | 3 days |
| G14 | Topic detection and proactive suggestions | Detect when user is exploring a topic (e.g., "termination") and suggest related questions: "You might also want to ask about notice periods, penalties, or force majeure." | 2 days |
| G15 | Cross-session long-term memory | Remember user preferences across sessions: "Last time you asked about termination clauses in Contract A. Would you like to compare with Contract B?" Uses Matter Memory archival (already built). | 3 days |

---

## Priority & Sequencing

```
Phase 1 (G1-G4)  →  2-3 days  →  70% of value, no dependencies
    ↓
Phase 2 (G5-G8)  →  3-4 days  →  Better retrieval, needs Phase 1
    ↓
Phase 3 (G9-G12) →  2-3 days  →  Citation UX, needs Phase 1
    ↓
Phase 4 (G13-G15) → 5+ days   →  Polish, needs all above
```

**When to start:** After RAG pipeline fixes (Groups A-C from fix plan) are done. Conversation improvements build ON TOP of the RAG pipeline — fixing the pipeline first means the improvements work correctly from day one.

---

## Relationship to RAGAS Evaluation

These are **parallel workstreams**, not sequential:

- RAGAS measures single Q&A quality (faithfulness, relevancy, recall)
- Conversational improvements change the INPUT to RAG (better queries via rewriting, richer context via summaries)
- Do RAGAS first → get baseline metrics → implement conversational improvements → measure impact with RAGAS
- Phase 2 (query rewriting) specifically BENEFITS from RAGAS being operational — you can A/B test rewritten vs original queries using RAGAS scores

---

## Files to Create/Modify

### New Files
- `backend/app/services/memory/summarizer.py` — Conversation summarizer (G1)
- `backend/app/services/rag/query_rewriter.py` — Context-aware query rewriter (G5)
- `backend/app/services/rag/citation_followup.py` — Citation reference detector (G10)

### Modified Files
- `backend/app/engines/rag/prompts.py` — Add conversation context section, restructure for caching (G2, G3)
- `backend/app/engines/orchestrator/streaming.py` — Wire summary injection, rewriter, citation tracking (G2, G6, G8, G9)
- `backend/app/services/memory/session.py` — Cache summaries, store citation metadata (G4, G9)
- `backend/app/services/rag/hybrid_search.py` — Accept rewritten queries, source-specific deep retrieval (G6, G11)
- `frontend/src/components/chat/` — Clickable citations (G12)

---

## Research Source

| Document | Path |
|----------|------|
| Conversational AI Research | `_bmad-output/project-planning-artifacts/research/technical-conversational-ai-context-management-research-2026-02-05.md` |
| Session Memory Implementation | `backend/app/services/memory/session.py` |
| Streaming Orchestrator | `backend/app/engines/orchestrator/streaming.py` |
| RAG Prompts | `backend/app/engines/rag/prompts.py` |
| RAG Pipeline Fix Plan | `_bmad-output/implementation-artifacts/fix-plan-rag-pipeline-and-evaluation.md` |
