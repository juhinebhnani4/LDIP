---
stepsCompleted: [1]
inputDocuments: []
workflowType: 'research'
lastStep: 2
research_type: 'technical'
research_topic: 'RAG Chat Quality Improvements for Legal Document Platform'
research_goals: 'Improve RAG answer quality with query-type-aware retrieval, optimal chunk/context sizing, contested fact distinction, and party attribution'
user_name: 'Juhi'
date: '2026-02-04'
web_research_enabled: true
source_verification: true
---

# Technical Research: RAG Chat Quality Improvements for Legal Document Platform

**Date:** 2026-02-04
**Author:** Juhi
**Research Type:** Technical
**Platform:** jaanch.ai (LDIP)

---

## Research Overview

This research investigates practical, implementation-ready approaches to improve RAG chat answer quality in a legal document analysis platform. The current system uses hybrid search (BM25 + pgvector), Cohere reranking, and Gemini 2.5 Flash for generation. The research focuses on four areas that can be implemented within the existing architecture without requiring agentic RAG or graph-based approaches.

**Methodology:** Web research with source verification across academic papers, industry best practices, and production RAG system documentation. All claims cited.

---

## Technical Research Scope Confirmation

**Research Topic:** RAG Chat Quality Improvements for Legal Document Platform
**Research Goals:** Improve RAG answer quality with query-type-aware retrieval, optimal chunk/context sizing, contested fact distinction, and party attribution

**Technical Research Scope:**

- Architecture Analysis - query-type-aware parameter routing within existing intent classifier
- Implementation Approaches - dynamic retrieval/generation config per query type
- Technology Stack - staying within current stack (Gemini Flash, hybrid search, Cohere rerank, Supabase pgvector)
- Integration Patterns - wiring intent classification output to retrieval parameters
- Performance Considerations - cost/latency tradeoffs with larger context windows

**Out of Scope:** Agentic RAG, graph-based query routing, RAPTOR-lite (Phase 2+)

**Scope Confirmed:** 2026-02-04

---

## 1. Query-Type Detection & Adaptive Retrieval Strategy

### Current State (LDIP)

LDIP already implements multi-intent classification (Story 6-1) with 5 intents: CITATION, TIMELINE, CONTRADICTION, RAG_SEARCH, MULTI_ENGINE. The intent analyzer uses fast-path regex patterns + GPT-3.5 fallback. However, **the classified intent does not currently influence retrieval parameters** — all queries use the same `MAX_CONTEXT_CHUNKS=5`, `RERANK_TOP_N=3`, and `MAX_ANSWER_LENGTH=2000`.

### Industry Best Practice: Adaptive RAG (2025-2026)

The trend in 2025-2026 is clear: **one-size-fits-all retrieval is being replaced by query-aware, adaptive pipelines**. [High Confidence]

**5 RAG Query Patterns** identified by [Nirant Kasliwal](https://nirantk.com/writing/rag-query-types/):
1. **Synthesis queries** — straightforward factoid retrieval with light transformation (e.g., "Who is Respondent No. 5?")
2. **Lookup queries** — specific information retrieval, often with time/comparative elements (e.g., "When was the affidavit filed?")
3. **Multi-hop queries** — need decomposition into sub-questions (e.g., "Compare Respondent 2's claims with Respondent 10's claims")
4. **Insufficient context queries** — system should admit it can't answer
5. **Creative/generative queries** — where LLM hallucination is desired (not applicable to legal)

**Adaptive RAG** analyzes query type and determines retrieval strategy accordingly. For simple queries, it might skip deep retrieval; for complex questions, it triggers multi-source search. This is implemented via lightweight classifiers or small LLMs at the front of the pipeline. ([Meilisearch - Adaptive RAG](https://www.meilisearch.com/blog/adaptive-rag)) [High Confidence]

**Production-scale query routing** (2026): A query classifier determines complexity and routes to appropriate pipeline configuration. RAGServe demonstrates dramatic gains by adapting per query. ([Production RAG Systems Guide](https://brlikhon.engineer/blog/building-production-rag-systems-in-2026-complete-architecture-guide)) [High Confidence]

### Recommended Configuration for LDIP

Based on research, the following query-type-to-parameter mapping is recommended:

| Query Type | LDIP Intent | Chunks Retrieved | Rerank Top-N | Max Answer Length | Chunk Content Limit |
|-----------|-------------|-----------------|-------------|-------------------|-------------------|
| **Lookup** (who/what/when) | RAG_SEARCH | 50 (default) | 3 | 2000 chars | 1500 chars |
| **Summary** (summarize/key findings) | RAG_SEARCH + detected "summarize" | 100 | 10-15 | 5000 chars | 2000 chars |
| **Comparison** (compare/contrast) | MULTI_ENGINE | 80 | 8 | 4000 chars | 2000 chars |
| **Timeline** | TIMELINE | 50 | 5 | 3000 chars | 1500 chars |
| **Citation** | CITATION | 50 | 5 | 3000 chars | 1500 chars |

**Implementation approach:** Add a `QueryProfile` dataclass that maps intent → retrieval parameters, and pass it through the orchestrator to the hybrid search and RAG generator.

---

## 2. Optimal Chunk Count & Context Window Sizing

### Research Findings

**Optimal chunk size for legal documents:** 400-1024 tokens, with semantic or adaptive chunking preserving clause-level context. ([LangCopilot - Chunking Strategies](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide)) [High Confidence]

**Key findings from multi-dataset analysis** ([arXiv - Rethinking Chunk Size](https://arxiv.org/html/2505.21700v2)):
- Smaller chunks (64-128 tokens) are optimal for fact-based answers
- Larger chunks (512-1024 tokens) improve retrieval for broader contextual understanding
- **This directly supports different chunk content limits per query type**

**Top-K retrieval recommendations:**
- Rerank top 20-50 retrieved documents down to 5-10 for the LLM ([AWS - Cohere Rerank](https://aws.amazon.com/blogs/machine-learning/improve-rag-performance-using-cohere-rerank/)) [High Confidence]
- For summary queries spanning multiple documents, increasing to top 10-15 is recommended
- Cohere's `top_n` parameter can be varied per call, making dynamic configuration straightforward ([Cohere Rerank Docs](https://docs.cohere.com/docs/reranking-with-cohere)) [High Confidence]

**Context window budget for Gemini 2.5 Flash:**
- Gemini 2.5 Flash supports 1M token context window
- Current usage: ~4,500 chars (3 chunks × 1500 chars) = ~1,125 tokens — **using <0.1% of available context**
- For summary queries: 15 chunks × 2000 chars = 30,000 chars (~7,500 tokens) — still <1% of context window
- **There is enormous headroom to increase context without hitting model limits**

### Recommendation for LDIP

1. **Lookup queries:** Keep current 3 chunks × 1500 chars (precision-focused)
2. **Summary queries:** Expand to 10-15 chunks × 2000 chars (recall-focused)
3. **Comparison queries:** Use 8 chunks × 2000 chars, ensure chunks come from different documents
4. **Answer length:** Remove hard 2000-char truncation for summary/comparison queries; increase to 5000 chars
5. **Cohere reranking:** Pass dynamic `top_n` per query type (already supported by API)

---

## 3. Distinguishing Contested vs. Uncontested Facts

### The Core Problem

In multi-party legal proceedings (like LDIP's use case), different parties file different documents making contradictory claims. The RAG system currently treats all chunks as equivalent flat text — it doesn't know whether "Respondent No. 10 discovered physical share certificates" is an undisputed fact or one party's claim that the other party denies.

### Research Findings

**Stanford study (2025):** The law is described as an "essentially contested" concept, making deciding what to retrieve challenging in a legal setting. RAG systems must locate information from multiple sources across time and place to properly answer. Even commercial legal AI tools (LexisNexis, Thomson Reuters) hallucinate 17-33% of the time. ([Stanford - Legal RAG Hallucinations](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf)) [High Confidence]

**CoCounsel (Thomson Reuters) approach:** Uses a "Litigation Document Analyzer" that identifies potential mischaracterizations of the law throughout documents. Requires attorney review at multiple checkpoints, particularly for cross-document analysis. ([Harvey AI vs CoCounsel](https://www.aline.co/post/harvey-ai-vs-cocounsel)) [Medium Confidence]

**Argument Mining in Legal NLP:** The field of Legal Argument Mining (LAM) attributes claims to specific parties (applicant, respondent, third parties, court). The ECHR annotation scheme includes sixteen categories of arguments. Current NLP models achieve 43-82% F1 on argument type classification depending on task complexity. ([Legal Argument Mining Survey](https://ceur-ws.org/Vol-4089/paper1.pdf), [ECHR Mining](https://arxiv.org/html/2208.06178)) [High Confidence]

**Key insight:** No public research was found on a RAG system that dynamically separates contested from uncontested facts at generation time. This is a novel challenge specific to litigation analysis tools. [High Confidence — gap confirmed]

### Practical Approach for LDIP (No ML Model Required)

Since LDIP already stores document metadata (filename, document type), the most practical approach is:

1. **Enrich chunk metadata with filer/party info** — Add a `filed_by` or `party_role` field to the `documents` table (e.g., "Respondent No. 2", "Applicant", "Court"). This is a manual or semi-automated step when documents are uploaded.

2. **Pass party metadata to the RAG prompt** — When formatting chunks for the LLM, include the party attribution:
   ```
   [Excerpt 1] From: "Affidavit in Reply of Respondent No. 2" (filed by Respondent No. 2), p. 30
   ```
   Instead of just:
   ```
   [Excerpt 1] From: "Affidavit in Reply of Respondent No. 2", p. 30
   ```

3. **Add a summary-specific prompt** that instructs the model to:
   - Group facts by party
   - Label claims as "according to [Party]" vs. "undisputed"
   - Flag procedural defenses (like limitation) prominently
   - Separate factual narrative from legal arguments

4. **Leverage existing contradiction engine** — LDIP already has a contradiction detection engine. For summary queries, include contradiction findings as additional context to help the model identify contested areas.

---

## 4. Legal Document Summarization with Party Attribution

### Research Findings

**Dynamic RAG for Legal Summarization (2025):** BM25 retriever with top-3 chunk selection, optimized with Legal NER. Best model (LLaMA 3.1-8B) achieves BERTScore of 0.89. ([MDPI - Legal Summarization](https://www.mdpi.com/2073-8994/17/5/633)) [High Confidence]

**Summary Augmented Chunks (SAC):** Retrieval using SAC selects fewer wrong documents across all top-k retrieved snippets compared to standard RAG on LegalBench-RAG. ([NLLP 2025](https://aclanthology.org/2025.nllp-1.3.pdf)) [High Confidence]

**Multi-Round RAG (2025):** Iteratively refines queries and aggregates context. Achieves 78.67% recall vs 57.33% baseline. ([ICMR 2025](https://dl.acm.org/doi/10.1145/3731715.3733451)) [Medium Confidence]

**Comprehensive Legal Summarization Survey (Jan 2025):** Reviews 120+ papers on legal summarization. Key finding: legal summarization requires domain-specific approaches due to unique structure, terminology, and multi-party dynamics. ([arXiv Survey](https://arxiv.org/html/2501.17830v1)) [High Confidence]

### Recommended Summary Prompt Template for LDIP

Based on research, here's a summary-specific prompt that addresses the attorney's needs:

```
You are a legal research assistant summarizing case documents for an attorney.

TASK: Synthesize key findings across all provided excerpts.

STRUCTURE YOUR RESPONSE AS:

**Case Overview:**
[1-2 sentence overview of the matter type and parties]

**Undisputed Facts:**
- Facts that appear consistently across multiple parties' filings (cite sources)

**Disputed Issues:**
- For each contested point:
  - [Party A]'s position: [claim] (Document, p. X)
  - [Party B]'s position: [claim] (Document, p. Y)

**Procedural Defenses:**
- Any limitation, jurisdiction, or procedural objections raised (these are potentially case-dispositive — flag prominently)

**Gaps in Available Documents:**
- Key information not covered in the provided excerpts

RULES:
- Attribute EVERY claim to the party who made it
- Use "according to [Party]" for contested claims
- Use "undisputed" only when multiple parties' documents agree
- Flag procedural defenses (limitation, jurisdiction) with **[PROCEDURAL DEFENSE]** tag
- Do NOT make legal conclusions or predictions
```

---

## 5. Implementation Roadmap (Aligned with LDIP Phases)

### Quick Wins (Config Changes Only)

| Change | Files | Impact |
|--------|-------|--------|
| Add `QueryProfile` with per-intent parameters | `prompts.py`, `generator.py`, orchestrator | High — fixes truncation, context window issues |
| Increase `MAX_ANSWER_LENGTH` to 5000 for summary queries | `generator.py` | High — fixes "It is alleged tha..." truncation |
| Pass dynamic `top_n` to Cohere reranker | `reranker.py`, `hybrid_search.py` | Medium — better chunk selection for summaries |
| Add summary-specific prompt template | `prompts.py` | High — structured output with party attribution |

### Medium Effort (Schema + Prompt Changes)

| Change | Files | Impact |
|--------|-------|--------|
| Add `filed_by` / `party_role` to documents table | Migration, upload API | Medium — enables party attribution |
| Include party metadata in chunk formatting | `prompts.py` `_format_context()` | High — LLM can attribute claims correctly |
| Add "summarize" sub-intent detection | `intent_analyzer.py` | Medium — routes to summary-specific pipeline |

### Phase 2 Alignment

These changes are **fully forward-compatible** with planned Phase 2/3 features:
- **RAPTOR-lite** would replace the summary path (the QueryProfile routing layer stays)
- **Adaptive search fusion (Gap #32)** tunes the parameters we're making configurable
- **Search learning (Gap #33)** learns optimal per-query configs from the foundation we build
- **RAG Evaluation Framework** gets better baseline answers to evaluate against

---

## Sources

1. [Nirant Kasliwal - 5 RAG Query Patterns](https://nirantk.com/writing/rag-query-types/)
2. [Meilisearch - Adaptive RAG Explained (2026)](https://www.meilisearch.com/blog/adaptive-rag)
3. [Production RAG Systems Guide (2026)](https://brlikhon.engineer/blog/building-production-rag-systems-in-2026-complete-architecture-guide)
4. [LangCopilot - Document Chunking Strategies (2025)](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide)
5. [arXiv - Rethinking Chunk Size for Long-Document Retrieval](https://arxiv.org/html/2505.21700v2)
6. [AWS - Improve RAG with Cohere Rerank](https://aws.amazon.com/blogs/machine-learning/improve-rag-performance-using-cohere-rerank/)
7. [Cohere Rerank Documentation](https://docs.cohere.com/docs/reranking-with-cohere)
8. [Stanford - Legal RAG Hallucinations Study (2025)](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf)
9. [Harvey AI vs CoCounsel Comparison](https://www.aline.co/post/harvey-ai-vs-cocounsel)
10. [Legal Argument Mining - Recent Trends (2025)](https://ceur-ws.org/Vol-4089/paper1.pdf)
11. [Mining Legal Arguments in ECHR Court Decisions](https://arxiv.org/html/2208.06178)
12. [MDPI - Dynamic RAG for Legal Summarization (2025)](https://www.mdpi.com/2073-8994/17/5/633)
13. [NLLP 2025 - Summary Augmented Chunks](https://aclanthology.org/2025.nllp-1.3.pdf)
14. [ICMR 2025 - Multi-Round RAG for Legal Documents](https://dl.acm.org/doi/10.1145/3731715.3733451)
15. [Comprehensive Survey on Legal Summarization (2025)](https://arxiv.org/html/2501.17830v1)
16. [arXiv - Enhancing RAG Best Practices Study (2025)](https://arxiv.org/abs/2501.07391)
17. [Medium - Adaptive RAG Query Classification](https://medium.com/@piash.tanjin/optimizing-rag-systems-query-classification-with-metadata-vector-search-2540401b9601)
18. [n8n - Adaptive RAG Workflow with Query Classification](https://n8n.io/workflows/3459-adaptive-rag-strategy-with-query-classification-and-retrieval-gemini-and-qdrant/)
19. [Vals AI - Legal AI Benchmark (2025)](https://www.lawnext.com/2025/10/vals-ais-latest-benchmark-finds-legal-and-general-ai-now-outperform-lawyers-in-legal-research-accuracy.html)
20. [AMELR 2025 - Argument Mining Workshop](https://easychair.org/cfp/amelr2025)
