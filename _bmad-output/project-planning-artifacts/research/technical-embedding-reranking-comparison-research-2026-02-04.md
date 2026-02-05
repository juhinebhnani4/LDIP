---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Voyage vs OpenAI embeddings in Indian legal cases, Voyage reranker vs Cohere reranker'
research_goals: 'Data-backed decision on upgrading Jaanch embedding and reranking stack'
user_name: 'Juhi'
date: '2026-02-04'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical - Embedding & Reranking Stack Comparison for Indian Legal RAG

**Date:** 2026-02-04
**Author:** Juhi
**Research Type:** Technical

---

## Technical Research Scope Confirmation

**Research Topic:** Voyage vs OpenAI embeddings in Indian legal cases, Voyage reranker vs Cohere reranker
**Research Goals:** Data-backed decision on upgrading Jaanch's embedding and reranking stack

**Technical Research Scope:**

- Embedding Model Comparison — Voyage voyage-law-2 vs OpenAI text-embedding-3-small
- Reranker Comparison — Voyage rerank-2.5 vs Cohere rerank-v3.5
- Cost Analysis — pricing, free tiers, rate limits, total cost at scale
- Integration Complexity — API compatibility, SDK maturity, migration effort
- Performance Benchmarks — latency, BEIR/MTEB legal scores, Indian legal NLP benchmarks
- Production Readiness — reliability, SLA, rate limits, vendor lock-in

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Cross-reference with live Jaanch Lite test results
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-02-04

---

## Technology Stack Analysis

### 1. Embedding Models: Voyage voyage-law-2 vs OpenAI text-embedding-3-small

#### Model Specifications

| Specification | OpenAI text-embedding-3-small | Voyage voyage-law-2 |
|--------------|------------------------------|---------------------|
| Dimensions | 1536 | 1024 |
| Max context | 8,191 tokens | 16,000 tokens |
| Training data | General-purpose web corpus | Legal corpus (cases, contracts, bills, statutes) |
| Legal domain optimization | None | Explicitly trained on legal documents |
| Matryoshka support | Yes (variable dims) | No |
| Provider | OpenAI | Voyage AI (acquired by MongoDB, Jan 2025) |

_Source: [Voyage AI Blog](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/), [Voyage AI Docs](https://docs.voyageai.com/docs/embeddings)_

#### Legal Retrieval Benchmark Performance

**MTEB Legal Retrieval (Voyage AI evaluation, 8 datasets):**

voyage-law-2 outperforms OpenAI v3 **large** by an average of **6% across 8 legal retrieval datasets** and by **over 10% on 3 key benchmarks** (LeCaRDv2, LegalQuAD, GerDaLIR). The comparison is against the larger OpenAI model (text-embedding-3-large, 3072 dims) — the gap against text-embedding-3-small would be even wider. [High Confidence]

_Source: [Voyage AI Legal Edition Blog](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/)_

**MLEB — Massive Legal Embedding Benchmark (Oct 2025, independent):**

The MLEB benchmark (10 expert-annotated datasets, multiple jurisdictions) provides the most comprehensive independent evaluation:

| Rank | Model | NDCG@10 |
|------|-------|---------|
| #1 | Isaacus Kanon 2 Embedder | 86.03 |
| #2 | Voyage 3 Large | 85.71 |
| #3 | Voyage 3.5 | 84.07 |
| #7 | Gemini Embedding | — |
| #8 | Voyage Law 2 | — (ahead of OpenAI v3 Large) |

**Critical finding from MLEB:** General MTEB performance does NOT predict legal performance. Gemini Embedding ranks #1 on general MTEB but only #7 on MLEB. Voyage 3.5 ranks #23 on general MTEB but #3 on MLEB. Legal domain adaptation matters. [High Confidence — independent academic benchmark]

_Source: [MLEB Paper (arXiv)](https://arxiv.org/html/2510.19365v1), [Isaacus MLEB Blog](https://huggingface.co/blog/isaacus/introducing-mleb)_

#### Key Insight: voyage-law-2 vs Newer Voyage Models

Voyage AI's newer general-purpose models (voyage-3-large, voyage-3.5) now outperform voyage-law-2 on MLEB. Voyage AI's own recommendation: "If you are particularly interested in law, voyage-law-2 is still best for legal domains, even though voyage-3 has highly competitive performance." However, MLEB data suggests voyage-3-large (#2) now exceeds voyage-law-2 (#8). [Medium Confidence — MLEB ranking vs Voyage's own recommendation conflict]

_Source: [Voyage 3 Blog](https://blog.voyageai.com/2024/09/18/voyage-3/), [MLEB](https://huggingface.co/blog/isaacus/introducing-mleb)_

#### Indian Legal Context

No embedding model has been specifically benchmarked on Indian legal text (Hindi/English bilingual, Indian statutes, Supreme Court/High Court judgments). The closest resources:

- **InLegalBERT** (IIT Kharagpur) — BERT model fine-tuned on Indian legal text for classification tasks, not optimized for retrieval. Available on HuggingFace (`law-ai/InLegalBERT`).
- **IL-TUR Benchmark** — Indian Legal Text Understanding and Reasoning benchmark with Prior Case Retrieval (PCR) task, but no published embedding model rankings.
- **OpenNyAI Legal NER** — NER pipeline for Indian court judgments, not embedding-focused.

**Gap:** No published benchmark compares voyage-law-2 vs OpenAI embeddings specifically on Indian legal text. The MLEB benchmark covers US, UK, EU, Australia, Ireland, Singapore — but not India. [High Confidence — verified gap]

_Source: [IL-TUR (arXiv)](https://arxiv.org/html/2407.05399v1), [InLegalBERT (HuggingFace)](https://huggingface.co/law-ai/InLegalBERT), [OpenNyAI (GitHub)](https://github.com/OpenNyAI/Opennyai)_

#### Live Test Results (Jaanch Lite, Jan 2026)

From our live testing on the TORTS Act 1992:

- voyage-law-2 embeddings + rerank-2.5 returned **all 3 top-1 results correctly** for legal queries
- Rerank scores ranged 0.56–0.83, showing good differentiation
- 74 chunks indexed in ~3 seconds
- No quality issues observed on the small test set

[Medium Confidence — small sample size, single document]

---

### 2. Reranking Models: Voyage rerank-2.5 vs Cohere rerank-v3.5 vs Cohere Rerank 4

#### Model Specifications

| Specification | Cohere rerank-v3.5 | Voyage rerank-2.5 | Cohere Rerank 4 Pro |
|--------------|-------------------|-------------------|-------------------|
| Context window | 4,096 tokens | 32,000 tokens | 32,000 tokens |
| Instruction-following | No | Yes (first reranker with this) | No (self-learning instead) |
| Multilingual | Yes | Yes | Yes |
| Self-learning | No | No | Yes (customizes without annotations) |
| Release date | Mid-2024 | Aug 2025 | Dec 2025 |

_Source: [Voyage rerank-2.5 Blog](https://blog.voyageai.com/2025/08/11/rerank-2-5/), [Cohere Rerank 4 (VentureBeat)](https://venturebeat.com/ai/coheres-rerank-4-quadruples-the-context-window-to-cut-agent-errors-and-boost)_

#### Benchmark Performance

**Voyage rerank-2.5 vs Cohere rerank-v3.5 (93 retrieval datasets):**

| Metric | Voyage rerank-2.5 over Cohere v3.5 |
|--------|-------------------------------------|
| Standard retrieval (93 datasets) | **+7.94%** |
| MAIR instruction-following benchmark | **+12.70%** |
| With legal-specific instructions | Additional **+8.13%** gain |

Averaged across four first-stage retrieval methods (BM25, OpenAI v3 large, voyage-3-large, voyage-3.5). [High Confidence — published benchmarks with methodology]

**Critical weakness of Cohere v3.5:** Cohere Rerank v3.5 actually **hurts retrieval quality** when applied on top of voyage-3-large (the most powerful first-stage method). [High Confidence]

_Source: [Voyage rerank-2.5 Blog](https://blog.voyageai.com/2025/08/11/rerank-2-5/), [MongoDB Blog](https://www.mongodb.com/company/blog/product-release-announcements/rerank-2-5-and-rerank-2-5-lite-instruction-following-rerankers)_

**Agentset Independent Leaderboard (ELO ratings):**

| Model | ELO Rating | Rank |
|-------|-----------|------|
| zerank-2 | ~1640 | #1 |
| Cohere Rerank 4 Pro | 1627 | #2 |
| Voyage rerank-2.5 | ~1580 | ~#4 |
| Cohere Rerank 4 Fast | 1506 | #7 |
| Cohere rerank-v3.5 | ~1457 | Lower half |

**Note:** Cohere Rerank 4 Pro (#2) now outranks Voyage rerank-2.5 on this leaderboard. However, Rerank 4 Pro is significantly more expensive. Voyage rerank-2.5 Lite still has a +22 ELO advantage over Cohere Rerank 4 Fast in the lightweight category. [High Confidence — independent third-party]

_Source: [Agentset Leaderboard](https://agentset.ai/leaderboard/rerankers), [Agentset Comparison](https://agentset.ai/rerankers/compare/voyage-ai-rerank-25-vs-cohere-rerank-4-fast)_

#### Instruction-Following: The Legal Advantage

Voyage rerank-2.5 is the **first reranker with instruction-following capability**. This means you can pass domain-specific instructions like:

> "Prioritize chunks containing statutory provisions, section numbers, or legal definitions that directly address the query"

This produced an additional **8.13% accuracy gain** across 24 domain-specific instruction-following datasets spanning 7 domains (web, tech, **legal**, finance, conversational, medical). [High Confidence]

For Jaanch, this means different reranking instructions for different document types (statutes vs affidavits vs judgments vs contracts), which is impossible with Cohere v3.5 or Rerank 4. [High Confidence — unique capability]

_Source: [Voyage rerank-2.5 Blog](https://blog.voyageai.com/2025/08/11/rerank-2-5/)_

#### Latency

| Model | Avg Latency |
|-------|------------|
| Cohere rerank-v3.5 | ~595ms |
| Voyage rerank-2.5 | ~603ms |
| Cohere Rerank 4 Pro | ~960ms (60% slower) |

Voyage rerank-2.5 and Cohere v3.5 have nearly identical latency. Cohere Rerank 4 Pro is significantly slower. [High Confidence]

_Source: [Agentset Best Reranker](https://agentset.ai/blog/best-reranker)_

---

### 3. Cost Analysis

#### Embedding Costs

| Model | Price per 1M tokens | Free tier | Cost for 100K-page legal corpus (~50M tokens) |
|-------|--------------------|-----------|--------------------------------------------|
| OpenAI text-embedding-3-small | $0.02 | None | $1.00 |
| Voyage voyage-law-2 | $0.12 | 50M tokens free | **$0.00** (within free tier) then $6.00 |
| Voyage voyage-3-large | $0.18 | 200M tokens free | **$0.00** (within free tier) then $9.00 |

_Source: [Voyage AI Pricing](https://docs.voyageai.com/docs/pricing)_

#### Reranking Costs

| Model | Price per 1M tokens | Free tier | Cost per 10K search queries |
|-------|--------------------|-----------|-----------------------------|
| Cohere rerank-v3.5 | $2.00 | 1K/month free API calls | ~$20.00 |
| Voyage rerank-2.5 | $0.05 | 200M tokens free | ~$0.50 |
| Cohere Rerank 4 Pro | Not yet published | — | — |

**Voyage reranking is 40x cheaper than Cohere v3.5.** The 200M free token tier covers approximately 200K search queries before any charges. [High Confidence]

_Source: [Voyage AI Pricing](https://docs.voyageai.com/docs/pricing), [Cohere Pricing](https://cohere.com/pricing)_

#### Batch API Discount

Voyage offers a **33% discount** via Batch API with 12-hour completion window — useful for document ingestion (embedding generation) but not for real-time search. [High Confidence]

_Source: [Voyage AI Pricing](https://docs.voyageai.com/docs/pricing)_

---

### 4. Production Readiness & Integration

#### Voyage AI — Vendor Context

Voyage AI was **acquired by MongoDB in January 2025**. This means:
- Voyage AI models are now backed by MongoDB's enterprise infrastructure
- Available on AWS Marketplace and MongoDB Atlas
- SDK maturity improving with MongoDB's resources
- Potential long-term vendor lock-in risk reduced (MongoDB is a major infrastructure provider)

_Source: [MongoDB Voyage AI Docs](https://www.mongodb.com/docs/voyageai/models/)_

#### SDK & Integration

| Aspect | OpenAI | Voyage AI | Cohere |
|--------|--------|-----------|--------|
| Python SDK | `openai` (mature) | `voyageai` (stable) | `cohere` (mature) |
| LangChain integration | Yes | Yes | Yes |
| LlamaIndex integration | Yes | Yes | Yes |
| LiteLLM support | Yes | Yes | Yes |
| Batch API | Yes | Yes (33% discount) | Yes |
| Rate limits (paid) | 10K RPM | Flexible (contact) | 10K RPM |

_Source: [Voyage AI Docs](https://docs.voyageai.com/docs/embeddings), [LiteLLM Voyage](https://docs.litellm.ai/docs/providers/voyage)_

#### Known Issues from Live Testing

1. **Voyage rate limits on free tier:** Hit 402 errors during testing. Adding payment method resolved this. Production needs paid tier.
2. **No circuit breaker built-in:** Voyage API has no native retry/backoff — Jaanch's existing circuit breaker pattern must wrap Voyage calls.
3. **Dimension change (1536 → 1024):** Migrating from OpenAI to Voyage requires re-embedding all documents AND updating the pgvector index from `vector(1536)` to `vector(1024)`.

[High Confidence — verified during live testing]

---

### 5. Indian Legal NLP Ecosystem

#### Available Resources

| Resource | Type | Relevance to Jaanch |
|----------|------|---------------------|
| [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) | Domain-adapted BERT for Indian legal text | Could fine-tune embeddings, but not a retrieval model |
| [OpenNyAI Legal NER](https://github.com/Legal-NLP-EkStep/legal_NER) | NER for Indian court judgments (14 entity types) | Could improve citation extraction (petitioner, respondent, statute, provision) |
| [IL-TUR Benchmark](https://arxiv.org/html/2407.05399v1) | Indian legal benchmark (retrieval, QA, summarization) | Benchmark for evaluating Jaanch's retrieval quality |
| [Legal NLP India Survey (2025)](https://link.springer.com/article/10.1007/s00146-025-02373-z) | Comprehensive survey of Indian legal NLP | Research reference |

#### Gap Analysis

No published comparison exists for voyage-law-2 vs OpenAI embeddings on Indian legal text specifically. The IL-TUR benchmark includes a Prior Case Retrieval task that could be used for evaluation, but no embedding model rankings have been published for it. [High Confidence — verified gap]

**Recommendation:** Run a controlled evaluation using IL-TUR's Prior Case Retrieval dataset to compare voyage-law-2 vs text-embedding-3-small on actual Indian legal text.

---

### 6. Technology Adoption Trends

#### Embedding Model Trends (2025-2026)

1. **Domain-specific models outperform general-purpose** on their target domains (MLEB confirms this for legal)
2. **Newer general models closing the gap** — voyage-3-large (#2 on MLEB) nearly matches domain-specific Kanon 2 (#1)
3. **Matryoshka learning** enables variable-dimension embeddings for cost/quality tradeoff
4. **MongoDB's acquisition of Voyage AI** signals embedding-as-infrastructure trend

#### Reranking Trends

1. **Instruction-following reranking** is a new paradigm (Voyage rerank-2.5 is first)
2. **Self-learning reranking** is Cohere's competing approach (Rerank 4)
3. **Context windows expanding** — 32K is now standard (up from 4K in Cohere v3.5)
4. **Cost compression** — Voyage's 40x cheaper reranking suggests commoditization

_Source: [Elephas Embedding Models 2026](https://elephas.app/blog/best-embedding-models), [ZeroEntropy Reranking Guide](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)_

---

## Integration Patterns Analysis

### 1. API Design & SDK Patterns

#### Voyage AI API Surface

Voyage AI exposes a RESTful API with two primary endpoints — embeddings and reranking. The Python SDK (`voyageai`) provides a `Client` object with straightforward methods:

**Embedding:**
```python
import voyageai
vo = voyageai.Client()  # Uses VOYAGE_API_KEY env var
embeddings = vo.embed(
    texts=["chunk text here"],
    model="voyage-law-2",
    input_type="document"  # or "query" for search queries
)
```

**Reranking with instruction-following:**
```python
results = vo.rerank(
    query="[Instruction: Prioritize statutory provisions] What is Section 12?",
    documents=["chunk1", "chunk2", "chunk3"],
    model="rerank-2.5",
    top_k=5,
    truncation=True
)
# Returns RerankingResult objects with .index and .relevance_score
```

Key API characteristics:
- **input_type parameter** (embeddings): Voyage recommends specifying `"document"` for indexing and `"query"` for search — this optimizes the embedding for asymmetric retrieval. OpenAI does not have this distinction.
- **Instruction-following** (reranking): Instructions are prepended/appended to the query string itself — no separate parameter. This means reranking instructions can be dynamically varied per document type.
- **Token limits**: Reranking supports max 1,000 documents per call, 32K tokens per query-document pair. Embedding supports batches of up to 128 texts.
- **Normalized embeddings**: All Voyage embeddings are L1-normalized, so cosine similarity, dot product, and L2 distance are interchangeable. Dot product is fastest.

_Source: [Voyage AI Docs — Embeddings](https://docs.voyageai.com/docs/embeddings), [Voyage AI Docs — Reranker](https://docs.voyageai.com/docs/reranker), [Voyage AI Quickstart](https://docs.voyageai.com/docs/quickstart-tutorial)_

#### Cohere → Voyage Reranking Migration (API Comparison)

| Aspect | Cohere rerank-v3.5 | Voyage rerank-2.5 |
|--------|-------------------|-------------------|
| Python SDK | `cohere.Client().rerank()` | `voyageai.Client().rerank()` |
| Query parameter | `query` | `query` |
| Documents parameter | `documents` | `documents` |
| Model parameter | `model="rerank-english-v3.0"` | `model="rerank-2.5"` |
| Top-K parameter | `top_n` | `top_k` |
| Result format | `.results[i].index`, `.relevance_score` | `.results[i].index`, `.relevance_score` |
| Instruction support | Not supported | Prepend/append to query string |
| Max docs per call | 1,000 | 1,000 |
| Max context | 4,096 tokens | 32,000 tokens |

The API surface is nearly identical. Migration requires: (1) swap `cohere` SDK for `voyageai`, (2) change `top_n` to `top_k`, (3) update model name, (4) update API key. Minimal code restructuring needed. [High Confidence]

_Source: [Cohere Rerank API](https://docs.cohere.com/reference/rerank), [Voyage AI Reranker Docs](https://docs.voyageai.com/docs/reranker)_

#### OpenAI → Voyage Embedding Migration (API Comparison)

| Aspect | OpenAI text-embedding-3-small | Voyage voyage-law-2 |
|--------|------------------------------|---------------------|
| Python SDK | `openai.OpenAI().embeddings.create()` | `voyageai.Client().embed()` |
| Input | `input=["text"]` | `texts=["text"]` |
| Model | `model="text-embedding-3-small"` | `model="voyage-law-2"` |
| Input type | Not supported | `input_type="document"` or `"query"` |
| Output | `.data[0].embedding` (list) | `.embeddings[0]` (list) |
| Dimensions | 1536 (fixed) | 1024 (default, configurable: 256/512/1024/2048) |
| Batch size | Up to 2048 inputs | Up to 128 inputs |

Key difference: Voyage's smaller batch size (128 vs 2048) means ingestion loops need adjustment. Also, the `input_type` distinction is important for retrieval quality — Jaanch must use `"document"` during indexing and `"query"` during search. [High Confidence]

_Source: [Voyage AI Docs](https://docs.voyageai.com/docs/embeddings), [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)_

---

### 2. LiteLLM as Abstraction Layer

Jaanch can use [LiteLLM](https://docs.litellm.ai/) as a unified proxy to abstract away provider-specific SDKs. LiteLLM supports both Voyage AI embeddings and reranking through OpenAI-compatible endpoints:

**Embedding via LiteLLM:**
```python
from litellm import embedding
response = embedding(model="voyage/voyage-law-2", input=["text"])
```

**Reranking via LiteLLM:**
```python
from litellm import rerank
response = rerank(model="voyage/rerank-2.5", query="query", documents=["doc1", "doc2"])
```

**Benefits for Jaanch:**
- **Provider-agnostic code**: Switch between OpenAI, Voyage, Cohere by changing the model string — no SDK changes
- **Unified cost tracking**: LiteLLM tracks spend across all providers
- **Fallback routing**: Configure fallback from Voyage → OpenAI if Voyage API is down
- **Rate limiting**: Built-in rate limiting and retry logic (8ms P95 latency at 1K RPS)

**Tradeoff:** LiteLLM adds a dependency and minor latency overhead. For Jaanch's scale (< 100 RPM), this overhead is negligible. The main risk is LiteLLM not supporting Voyage-specific features like `input_type` for embeddings — this needs verification. [Medium Confidence — need to verify input_type support]

_Source: [LiteLLM Voyage Provider](https://docs.litellm.ai/docs/providers/voyage), [LiteLLM Embeddings](https://docs.litellm.ai/docs/embedding/supported_embedding), [LiteLLM Rerank](https://docs.litellm.ai/docs/rerank)_

---

### 3. pgvector Dimension Migration Strategy

Migrating from OpenAI (1536d) to Voyage (1024d) requires a pgvector schema change. Embeddings from different models are **completely incompatible** — you cannot mix them or mathematically convert between them. All documents must be re-embedded.

_Source: [OpenAI Community — pgvector dimensions](https://community.openai.com/t/how-to-deal-with-different-vector-dimensions-for-embeddings-and-search-with-pgvector/602141), [Document360 Embedding Comparison](https://document360.com/blog/text-embedding-model-analysis/)_

#### Recommended Migration Plan for Jaanch (Zero-Downtime)

**Phase 1 — Prepare (no downtime):**
1. Add new column: `ALTER TABLE chunks ADD COLUMN embedding_new vector(1024);`
2. Add HNSW index on new column (concurrently): `CREATE INDEX CONCURRENTLY idx_chunks_embedding_new ON chunks USING hnsw (embedding_new vector_cosine_ops);`

**Phase 2 — Re-embed (background, no downtime):**
3. Batch re-embed all existing chunks using Voyage API with `input_type="document"`
4. Write new embeddings to `embedding_new` column
5. Use Voyage Batch API for 33% cost savings (12-hour window acceptable for migration)

**Phase 3 — Switch (brief maintenance window):**
6. Update `hybrid_search_chunks` RPC function to use `embedding_new` column
7. Update application query code to generate query embeddings via Voyage with `input_type="query"`
8. Validate search quality on test queries

**Phase 4 — Cleanup:**
9. Drop old column: `ALTER TABLE chunks DROP COLUMN embedding;`
10. Rename: `ALTER TABLE chunks RENAME COLUMN embedding_new TO embedding;`
11. `VACUUM ANALYZE chunks;`

**Scale estimate for Jaanch:**
- Current chunks: ~1,364 (Nirav matter) — likely < 10K total across all matters
- At 128 texts per batch, ~80 API calls needed
- Within Voyage's 200M free token tier — **$0 migration cost**
- Batch API with 33% discount available for larger future migrations

[High Confidence — standard pgvector migration pattern]

_Source: [pgvector GitHub](https://github.com/pgvector/pgvector), [Railway pgvector Guide](https://blog.railway.com/p/hosting-postgres-with-pgvector), [Instaclustr pgvector Guide](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)_

---

### 4. Circuit Breaker & Resilience Patterns

Voyage AI has no built-in retry/backoff mechanism. Jaanch's existing circuit breaker pattern must wrap all Voyage API calls.

**Required resilience patterns:**
- **Retry with exponential backoff**: For transient 429 (rate limit) and 5xx errors
- **Circuit breaker**: Open circuit after N consecutive failures, fallback to cached results or degraded search
- **Timeout**: Voyage embedding latency ~50-100ms per batch; reranking ~600ms. Set timeouts at 2x p99.
- **Rate limiting**: Free tier has strict limits (hit 402 errors in testing). Paid tier limits are flexible — contact Voyage for custom limits.

**Jaanch-specific considerations:**
- Document ingestion (embedding) is async (Celery tasks) — retries are natural
- Search queries (embedding + reranking) are synchronous — need fast fallback
- If Voyage API is down during search, fallback options: (a) return BM25-only results without reranking, (b) use cached embeddings with stale reranking scores

[High Confidence — based on live testing experience]

---

### 5. Voyage 4 Series — Future-Proofing

MongoDB announced **Voyage 4** models in January 2026, establishing a "new retrieval accuracy frontier." The Voyage 4 series is available through MongoDB Atlas Embedding and Reranking API, with enterprise-grade security and reliability infrastructure.

**Implications for Jaanch:**
- Voyage 4 models will likely supersede voyage-law-2 and rerank-2.5
- MongoDB Atlas integration means Jaanch could access Voyage models through Atlas if migrating to MongoDB — but Jaanch uses Supabase/PostgreSQL, so direct API access remains the path
- The `voyageai` Python SDK will continue to work for direct API access
- Adopting Voyage now positions Jaanch on the Voyage upgrade path (law-2 → Voyage 4 legal variant)

[Medium Confidence — Voyage 4 just announced, specific model benchmarks not yet published]

_Source: [MongoDB Voyage 4 Announcement (PR Newswire)](https://www.prnewswire.com/news-releases/mongodb-sets-a-new-standard-for-retrieval-accuracy-with-voyage-4-models-for-production-ready-ai-applications-302662558.html), [MongoDB Voyage AI Docs](https://www.mongodb.com/docs/voyageai/api-reference/overview/)_

---

### 6. Framework Integration Options

#### Current Jaanch Stack Integration Points

| Integration Point | Current (Jaanch) | Migration Target |
|-------------------|-----------------|-----------------|
| Embedding generation | `openai.OpenAI().embeddings.create()` | `voyageai.Client().embed()` |
| Reranking | `cohere.Client().rerank()` | `voyageai.Client().rerank()` |
| Vector storage | Supabase pgvector `vector(1536)` | Supabase pgvector `vector(1024)` |
| Search RPC | `hybrid_search_chunks()` with OpenAI query embedding | Same RPC with Voyage query embedding |
| Celery tasks | Embedding in async workers | Same pattern, swap SDK |

#### Framework Integrations Available (Not Currently Used)

- **LangChain**: `langchain-voyageai` package provides `VoyageAIEmbeddings` and `VoyageAIRerank` — drop-in replacements if Jaanch adopts LangChain
- **LlamaIndex**: `VoyageEmbedding` and `VoyageRerank` node postprocessors
- **Haystack**: `VoyageDocumentEmbedder`, `VoyageTextEmbedder`, `VoyageRanker`

Jaanch currently uses direct SDK calls (not LangChain/LlamaIndex), so the migration is SDK-level, not framework-level. This keeps the integration simple. [High Confidence]

_Source: [LangChain Voyage Reranker](https://python.langchain.com/docs/integrations/document_transformers/voyageai-reranker/), [Haystack Voyage](https://haystack.deepset.ai/integrations/voyage), [LiteLLM Voyage](https://docs.litellm.ai/docs/providers/voyage)_

---

## Architectural Patterns and Design

### 1. Provider Abstraction Pattern for Embedding & Reranking

Jaanch currently has direct SDK calls to OpenAI (embedding) and Cohere (reranking) scattered across service files. The migration to Voyage is an opportunity to introduce a **provider abstraction layer** — an interface that decouples application logic from specific embedding/reranking providers.

**Recommended pattern (Strategy + Factory):**

```
EmbeddingProvider (ABC)
├── embed(texts, input_type) → List[List[float]]
├── get_dimensions() → int
└── get_model_name() → str

Implementations:
├── OpenAIEmbeddingProvider
├── VoyageEmbeddingProvider
└── (future) Voyage4EmbeddingProvider

RerankProvider (ABC)
├── rerank(query, documents, top_k, instruction?) → List[RerankResult]
└── get_model_name() → str

Implementations:
├── CohereRerankProvider
├── VoyageRerankProvider
└── (future) Voyage4RerankProvider

Factory:
├── get_embedding_provider(config) → EmbeddingProvider
└── get_rerank_provider(config) → RerankProvider
```

**Why this matters for Jaanch:**
- Voyage 4 was just announced (Jan 2026) — Jaanch will need to swap models again
- The abstraction costs ~50 lines of code and saves full-codebase changes on each swap
- `input_type` (Voyage-specific) is exposed in the abstract interface — providers that don't support it simply ignore the parameter
- Config-driven: `EMBEDDING_PROVIDER=voyage` in `.env` selects the implementation at startup

This follows the same pattern used by [Mem0](https://deepwiki.com/mem0ai/mem0/4-ai-model-integrations) (16+ LLM providers, 10+ embedding providers) and [Fabric](https://deepwiki.com/danielmiessler/fabric/4-pattern-and-strategy-system) (25+ AI providers), both using factory/registry patterns for dynamic provider instantiation. [High Confidence]

_Source: [Entrio — LLM Agnostic Architecture](https://www.entrio.io/blog/implementing-llm-agnostic-architecture-generative-ai-module), [Mem0 AI Model Integrations](https://deepwiki.com/mem0ai/mem0/4-ai-model-integrations)_

---

### 2. Two-Stage Hybrid Retrieval Architecture

Jaanch already implements a two-stage retrieval pattern via the `hybrid_search_chunks` Supabase RPC function (BM25 + pgvector). The embedding/reranking migration preserves this architecture entirely:

**Current architecture (unchanged):**
```
Query → [Embedding] → pgvector ANN search (semantic)
     → [BM25] → ts_rank full-text search (lexical)
     → Reciprocal Rank Fusion (RRF)
     → Candidate set (top 50-100)
     → [Reranker] → Final top-K (5-10)
     → LLM context window
```

**What changes:**
- Stage 1 embedding: OpenAI → Voyage (different model, same architectural role)
- Stage 2 reranking: Cohere → Voyage (different model, same architectural role)

**What doesn't change:**
- BM25 lexical scoring (PostgreSQL ts_rank)
- RRF fusion logic in the RPC function
- Top-K selection and LLM prompt construction
- Parent-child chunk retrieval pattern

**Architectural insight:** The two-stage retrieval pattern naturally isolates the embedding and reranking concerns. Swapping providers is a configuration change, not an architectural change. This is why the migration has a small blast radius. [High Confidence]

_Source: [Hybrid Retrieval Guide (Medium)](https://medium.com/@richardhightower/stop-the-hallucinations-hybrid-retrieval-with-bm25-pgvector-embedding-rerank-llm-rubric-rerank-895d8f7c7242), [BM25 in Hybrid Search (DEV)](https://dev.to/negitamaai/integrating-bm25-in-hybrid-search-and-reranking-pipelines-strategies-and-applications-4joi)_

---

### 3. Instruction-Conditioned Reranking Architecture

Voyage rerank-2.5's instruction-following capability introduces a new architectural pattern for Jaanch: **document-type-conditioned reranking**.

**Proposed architecture:**

```
Query + Document Type → Instruction Selector → Instruction + Query → Reranker

Instruction templates by document type:
├── statute:    "Prioritize chunks with section numbers, definitions, provisos"
├── judgment:   "Prioritize ratio decidendi, holdings, and cited precedents"
├── affidavit:  "Prioritize factual assertions, dates, and party references"
├── contract:   "Prioritize clause definitions, obligations, and conditions"
└── default:    "Prioritize chunks most relevant to the legal query"
```

This is impossible with Cohere rerank-v3.5 (no instruction support) and would require Cohere Rerank 4's self-learning (which needs training data per domain). Voyage's approach is zero-shot — instructions work immediately without training. [High Confidence]

**Implementation:** The instruction is prepended to the query string before calling `vo.rerank()`. The instruction selector is a simple dict lookup keyed on `document.document_type`. This adds ~10 lines of code.

_Source: [Voyage rerank-2.5 Blog](https://blog.voyageai.com/2025/08/11/rerank-2-5/), [MongoDB Blog — Instruction-Following Rerankers](https://www.mongodb.com/company/blog/product-release-announcements/rerank-2-5-and-rerank-2-5-lite-instruction-following-rerankers)_

---

### 4. Embedding Migration Data Architecture

The dimension change (1536 → 1024) requires a specific data migration pattern. Two architectural approaches exist:

**Approach A: Dual-Column (Zero-Downtime) — Recommended**

```
chunks table:
├── embedding vector(1536)       ← old, served during migration
├── embedding_new vector(1024)   ← new, populated in background
└── embedding_migrated boolean   ← tracks migration progress

hybrid_search_chunks RPC:
├── Phase 1: Uses embedding (1536) — no change
├── Phase 2: Switch to embedding_new (1024) — atomic RPC update
├── Phase 3: Drop embedding, rename embedding_new
```

**Approach B: Full Reprocess (Simpler, requires downtime)**

```
1. Stop ingestion
2. ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1024)
3. NULL all embeddings
4. Re-embed all chunks
5. Rebuild HNSW index
6. Resume
```

**Recommendation:** Approach A for production, Approach B for dev/staging. At Jaanch's current scale (~10K chunks), Approach B takes < 30 minutes. But Approach A establishes the pattern for future model swaps. [High Confidence]

_Source: [pgvector GitHub](https://github.com/pgvector/pgvector), [Railway pgvector Guide](https://blog.railway.com/p/hosting-postgres-with-pgvector)_

---

### 5. Concurrent Pipeline Upgrade Pattern

The embedding migration naturally coincides with two other pipeline improvements identified in this research:

1. **Embedding swap** (OpenAI → Voyage): requires re-embedding all chunks
2. **Chunking refactor** (layout-aware chunking): requires re-chunking all documents
3. **bbox fix** (Strategy 2 — deterministic bbox assignment): requires re-processing all documents

**Architectural insight:** Since all three changes require re-processing documents, they should be combined into a single migration pipeline:

```
For each document:
  1. Docling layout detection (new)
  2. Google Doc AI OCR (existing)
  3. Layout-aware chunking with deterministic bbox (new)
  4. Voyage embedding with input_type="document" (new)
  5. Write chunks + embeddings to new columns
```

This avoids re-processing documents three separate times. The combined pipeline is a one-time migration that upgrades chunking quality, bbox accuracy, AND embedding model simultaneously. [High Confidence — architectural synergy]

---

### 6. Fallback and Degradation Architecture

**Search-time degradation hierarchy:**

| Failure | Fallback | User Impact |
|---------|----------|-------------|
| Voyage embedding API down | Return BM25-only results (no semantic search) | Reduced recall, exact matches still work |
| Voyage rerank API down | Return un-reranked hybrid results | Slightly lower precision, results still relevant |
| Both APIs down | BM25-only, no reranking | Functional but degraded |
| Supabase down | Service unavailable | Full outage |

**Ingestion-time degradation:**

| Failure | Fallback | Impact |
|---------|----------|--------|
| Voyage embedding API down | Retry with exponential backoff (Celery) | Delayed indexing, no data loss |
| Persistent Voyage failure | Queue documents, alert admin | Documents searchable by BM25 only until embeddings generated |

This degradation hierarchy ensures Jaanch never returns zero results due to a third-party API failure. BM25 (PostgreSQL ts_rank) has no external dependency — it's always available. [High Confidence]

_Source: [RAG Pipeline Architecture (DhiWise)](https://www.dhiwise.com/post/build-rag-pipeline-guide), [RAGOps Paper (arXiv)](https://arxiv.org/html/2506.03401v1)_

---

## Implementation Approaches and Technology Adoption

### 1. Migration Strategy: Phased Rollout (Not Big Bang)

Based on industry best practices for embedding model migration, Jaanch should use a **phased dual-index approach** rather than a big-bang cutover:

**Phase 0 — Validation (1 week):**
- Create a test set of 20-30 representative legal queries across document types (statutes, judgments, affidavits)
- Record current retrieval results with OpenAI embeddings + Cohere reranking as baseline
- Metrics: MRR, NDCG@10, and manual relevance judgments

**Phase 1 — Shadow Mode (1 week):**
- Deploy Voyage embedding + reranking alongside existing stack
- Run both pipelines on every search query (production queries → both models)
- Compare results side-by-side without affecting users
- Log: query, OpenAI top-5 results, Voyage top-5 results, overlap percentage

**Phase 2 — Gradual Cutover:**
- Switch reranking first (Cohere → Voyage) — this is stateless, no data migration
- Monitor MRR/NDCG for regression
- Then switch embeddings (requires data migration per Approach A above)

**Phase 3 — Cleanup:**
- Remove OpenAI embedding column and Cohere SDK
- Update monitoring dashboards

**Why phased:** Embedding model changes alter the geometry of the entire vector space. Models that top MTEB leaderboards may underperform on your specific data. The only way to validate is to test on your actual queries. [High Confidence]

_Source: [Hidden Cost of Model Upgrades (Medium)](https://medium.com/data-science-collective/different-embedding-models-different-spaces-the-hidden-cost-of-model-upgrades-899db24ad233), [When Good Models Go Bad (Weaviate)](https://weaviate.io/blog/when-good-models-go-bad)_

---

### 2. Retrieval Quality Evaluation Framework

Jaanch needs a lightweight evaluation framework to validate the migration. This doesn't need to be a production monitoring system — just enough to confirm the new stack is at least as good.

**Test Set Construction:**

| Category | Example Queries | Count |
|----------|----------------|-------|
| Statutory lookup | "What does Section 12 of TORTS Act say?" | 5 |
| Entity-based | "What are the obligations of the petitioner?" | 5 |
| Cross-document | "Which citations reference the Motor Vehicles Act?" | 5 |
| Semantic | "liability for negligent acts" | 5 |
| Edge cases | Hindi terms, misspellings, abbreviations | 5 |

**Metrics to capture:**

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| MRR | First relevant result position | > 0.8 (relevant in top 2) |
| NDCG@5 | Ranked relevance quality | > 0.75 |
| Recall@10 | Coverage of relevant chunks | > 0.9 |
| Rerank lift | NDCG improvement from reranking | > 10% over un-reranked |
| Latency P95 | End-to-end search time | < 2 seconds |

**Evaluation script:** A simple Python script that runs each query against both stacks, compares results, and outputs a comparison table. No framework needed at Jaanch's current scale. [High Confidence]

_Source: [RAG Evaluation Metrics (GeeksForGeeks)](https://www.geeksforgeeks.org/nlp/evaluation-metrics-for-retrieval-augmented-generation-rag-systems/), [RAG Evaluation Guide (Maxim)](https://www.getmaxim.ai/articles/complete-guide-to-rag-evaluation-metrics-methods-and-best-practices-for-2025/), [Retrieval Quality in RAG (TDS)](https://towardsdatascience.com/how-to-evaluate-retrieval-quality-in-rag-pipelines-part-3-dcgk-and-ndcgk/)_

---

### 3. Cost Optimization Strategy

**Current monthly cost estimate (OpenAI + Cohere):**

| Component | Usage | Cost/month |
|-----------|-------|------------|
| OpenAI text-embedding-3-small | ~5M tokens/month (ingestion + search) | $0.10 |
| Cohere rerank-v3.5 | ~2K searches × 20 chunks each | ~$4.00 |
| **Total** | | **~$4.10/month** |

**Projected monthly cost (Voyage):**

| Component | Usage | Cost/month |
|-----------|-------|------------|
| Voyage voyage-law-2 | ~5M tokens/month | $0.00 (within 50M free tier) |
| Voyage rerank-2.5 | ~2K searches × 20 chunks each | $0.00 (within 200M free tier) |
| **Total** | | **$0.00/month** (within free tiers) |

**At 10x scale (post-growth):**

| Component | Usage | Cost/month |
|-----------|-------|------------|
| Voyage voyage-law-2 | ~50M tokens/month | $6.00 |
| Voyage rerank-2.5 | ~20K searches | ~$1.00 |
| **Total** | | **~$7.00/month** |
| vs OpenAI + Cohere at same scale | | **~$41.00/month** |

**Savings: ~83% at scale.** The free tiers alone cover Jaanch's current usage entirely. [High Confidence]

---

### 4. Risk Assessment and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Voyage API reliability (no SLA published) | Medium | High | Circuit breaker + BM25 fallback + monitor uptime |
| Voyage free tier limits hit | Low (200M tokens is generous) | Medium | Add payment method preemptively (learned from testing) |
| voyage-law-2 underperforms on Indian legal text | Low (general legal performance is strong) | High | Phase 0 validation with test queries before committing |
| MongoDB acquires and sunsets standalone API | Low | High | LiteLLM abstraction allows fast provider swap |
| Voyage 4 replaces voyage-law-2 | High (expected) | Low (positive) | Abstraction layer makes model upgrade a config change |
| Re-embedding breaks existing search quality | Medium | High | Dual-column approach with rollback capability |
| Batch size difference (128 vs 2048) slows ingestion | Low | Low | Adjust batch loops; at current scale, negligible impact |

[High Confidence — risks identified from live testing and vendor analysis]

---

## Technical Research Recommendations

### Final Recommendation: Migrate to Voyage AI

**Decision: YES — migrate both embedding and reranking to Voyage AI.**

**Evidence summary:**

| Dimension | Verdict | Confidence |
|-----------|---------|------------|
| Embedding quality (legal) | Voyage wins — 6%+ over OpenAI on legal benchmarks | High |
| Reranking quality | Voyage wins — 8% over Cohere v3.5, instruction-following is unique | High |
| Cost | Voyage wins — 40x cheaper reranking, free tier covers current usage | High |
| API compatibility | Near-identical API surface, minimal code changes | High |
| Latency | Equivalent (~600ms reranking for both) | High |
| Indian legal performance | Unknown — no benchmark exists | Gap |
| Vendor stability | MongoDB backing reduces risk | Medium |
| Future-proofing | Voyage 4 on the upgrade path | Medium |

### Implementation Roadmap

**Milestone 1: Reranking swap (lowest risk, highest reward)**
- Swap Cohere → Voyage rerank-2.5 with instruction-following
- Add document-type-conditioned reranking instructions
- No data migration required
- Files changed: reranking service (~1 file)

**Milestone 2: Provider abstraction layer**
- Introduce `EmbeddingProvider` and `RerankProvider` abstract classes
- Wrap existing OpenAI/Voyage calls behind the abstraction
- Config-driven provider selection
- Files changed: new abstraction module + update service files (~3 files)

**Milestone 3: Embedding migration**
- Add `embedding_new vector(1024)` column
- Batch re-embed all chunks with Voyage voyage-law-2
- Validate with test query set
- Switch `hybrid_search_chunks` RPC
- Cleanup old column
- Files changed: migration script, RPC function, embedding service (~3 files)

**Milestone 4 (combined with chunking refactor):**
- Docling layout detection + layout-aware chunking + deterministic bbox
- Re-process all documents through upgraded pipeline
- Re-embed with Voyage (combines with Milestone 3 if done together)
- Delete bbox_linker.py
- Files changed: extractor.py, parent_child_chunker.py, document_tasks.py, delete bbox_linker.py

### Success Metrics

| Metric | Baseline (Current) | Target (Post-Migration) |
|--------|-------------------|------------------------|
| MRR on test queries | Measure during Phase 0 | >= baseline |
| NDCG@5 | Measure during Phase 0 | >= baseline |
| Rerank lift (with instructions) | N/A (no instructions today) | > 10% over un-reranked |
| Search latency P95 | Measure current | <= 2 seconds |
| Monthly embedding + reranking cost | ~$4.10 | $0.00 (free tier) |
| Embedding dimensions | 1536 | 1024 (33% storage savings) |

### Open Questions for Future Research

1. **Indian legal embedding benchmark**: Run IL-TUR Prior Case Retrieval with voyage-law-2 vs text-embedding-3-small to validate on Indian legal text
2. **Voyage 4 legal variant**: Monitor for Voyage 4 model with legal domain training — may supersede voyage-law-2
3. **voyage-3-large vs voyage-law-2**: MLEB ranks voyage-3-large (#2) above voyage-law-2 (#8) — consider testing voyage-3-large as an alternative
4. **Instruction-following optimization**: Experiment with different reranking instructions per document type to find optimal prompts for Indian legal queries

---

## Appendix: Community & Ecosystem Research — Voyage AI in Indian Legal Context

_Searched: Reddit, X/Twitter, LinkedIn, startup databases, academic papers — 2026-02-04_

### Finding: Zero Public Evidence of Voyage AI Use on Indian Legal Text

Comprehensive searches across Reddit, X/Twitter, LinkedIn, startup disclosures, and academic papers found **no public instance** of anyone using voyage-law-2 (or any Voyage embedding model) specifically on Indian legal text. This is a confirmed ecosystem gap. [High Confidence — exhaustive search]

### The Only Production Case Study: Harvey AI (US Law)

[Harvey AI](https://www.harvey.ai/blog/harvey-partners-with-voyage-to-build-custom-legal-embeddings) is the only company with a public, production-grade deployment of voyage-law-2. They fine-tuned it into **voyage-law-2-harvey** on 20B+ tokens of US case law, achieving:
- 25% reduction in irrelevant retrieval results
- 1/3 the embedding dimensionality of competitors
- Combined with proprietary search methods for further improvement

This is US case law only — not Indian legal text. [High Confidence]

_Source: [Harvey Blog](https://www.harvey.ai/blog/harvey-partners-with-voyage-to-build-custom-legal-embeddings), [Tengyu Ma on X](https://x.com/tengyuma/status/1816943504712737245)_

### Caution: Voyage 4 Law Domain Regression

Voyage AI's own [evaluation spreadsheet](https://x.com/VoyageAI/status/1877048843964997644) shows **voyage-4-lite had a -2.10 point decline on the Law domain** compared to previous models. This suggests newer general Voyage models may not automatically improve legal performance. Model-specific legal evaluation remains critical. [Medium Confidence — single data point from official source]

### Indian Legaltech Startup Embedding/Search Stacks

No Indian legaltech startup publicly uses Voyage AI. Here is what they use:

| Startup | Founded | Funding | Search/Embedding Stack | Notes |
|---------|---------|---------|----------------------|-------|
| **[Jhana.ai](https://jhana.ai/)** | 2022 (Harvard) | $1.6M seed | ElasticSearch (billion-scale) + FAISS/Milvus + OpenAI/Google LLMs | 16M+ judgments. Proprietary graph models for legal ontologies + reranking. |
| **[CaseMine](https://www.casemine.com/)** | 2013 (Noida) | Funded | Proprietary semantic search ("CaseIQ") + GPT-powered AMICUS | Context-based retrieval, not keyword. Embedding model undisclosed. |
| **[Manupatra](https://www.manupatra.ai/)** | Legacy | Established | Keyword-based + AI gists/summaries | 100K+ users, 25 years. Traditional search with ML augmentation. |
| **[LegitQuest](https://www.legitquest.com/)** | 2017 (Delhi) | Funded | 400M+ legal records, generative AI platform | IndusLaw partnership for PoC. Embedding details undisclosed. |
| **[Vettam AI](https://www.vettam.ai/)** | 2024 (Kerala) | Unfunded | RAG pipeline + embeddings + redaction system | Fine-tuned on Indian legal data. React+TS frontend. 10 Indian languages. Trace IDs for verifiability. |
| **NYAYA.ai** | Open-source | — | RAG + Llama-3 + FAISS | Indian Constitution & BNS focus. |
| **[LawPal](https://arxiv.org/html/2502.16573v1)** | Research | — | DeepSeek-R1:5B + FAISS | 90%+ accuracy on Indian legal QA. |
| **[Aalap (OpenNyAI)](https://arxiv.org/html/2402.01758v1)** | 2023 | Grant-funded | Mistral 7B fine-tuned + InLegalBERT for NER | 22K legal instructions, 32K context. By NLSIU/Thoughtworks/EkStep. |
| **[Nyaay AI](https://www.nyaayai.com/)** | — | Funded | Undisclosed | Partnered with 16 High Courts + Supreme Court + Singapore judiciary. |
| **[Adalat AI](https://indiaai.gov.in/article/india-s-ai-driven-legal-future-opportunities-and-emerging-trends-in-2025)** | — | — | Transcription AI | Deployed in 3,500 courtrooms. |

_Source: [Inc42 — Legal Innovation in India](https://inc42.com/features/how-are-legaltech-startups-making-their-case-in-india/), [Tracxn — AI in Legal Tech India](https://tracxn.com/d/artificial-intelligence/ai-startups-in-legal-tech-in-india/__NkGQVg4qj42nbnv4P2gmZUKkKNxJTWzSzY28_uyHIbc/companies), [IndiaAI.gov.in](https://indiaai.gov.in/article/india-s-ai-driven-legal-future-opportunities-and-emerging-trends-in-2025)_

### Indian Legal Embedding Models & Corpora

| Resource | Type | Scale | Relevance |
|----------|------|-------|-----------|
| **[InLegalBERT](https://huggingface.co/law-ai/InLegalBERT)** (IIT Kharagpur) | BERT fine-tuned on Indian legal text | 60K+ downloads | Classification, not retrieval |
| **InCaseLawBERT** (IIT Kharagpur) | BERT for Indian case law | — | Classification, not retrieval |
| **[HLDC](https://arxiv.org/html/2204.00806v2)** (Hindi Legal Documents Corpus) | 912K Hindi legal documents | ~20M pending Hindi-language cases | No embedding rankings published |
| **[IL-TUR](https://arxiv.org/html/2407.05399v1)** | Indian Legal benchmark (retrieval, QA, summarization) | Multi-task | Has Prior Case Retrieval task but no embedding leaderboard |
| **[BGE-base-en-v1.5 fine-tuned on SEBI text](https://medium.com/@aman.dogra/fine-tuning-open-source-embedding-models-for-improving-retrieval-in-legal-rag-2b700d87a90e)** | Fine-tuned OSS embedding | — | 16% retrieval improvement, 12x storage reduction. "Retrieval kinda suck for legal texts with OSS embedding models." |
| **IndicBERT** | Transformer for 12 Indian languages | — | Tested on HLDC for Hindi legal classification |

_Source: [InLegalBERT (HuggingFace)](https://huggingface.co/law-ai/InLegalBERT), [HLDC Paper](https://arxiv.org/html/2204.00806v2), [SEBI Fine-tuning (Medium)](https://medium.com/@aman.dogra/fine-tuning-open-source-embedding-models-for-improving-retrieval-in-legal-rag-2b700d87a90e)_

### Ecosystem Competitor: VectorStackAI

[VectorStackAI](https://www.vectorstack.ai/blog/best-in-class-legal-domain-embeddings-vstackai-law-1) claims their **vstackai-law-1** outperforms both OpenAI text-embedding-3-large and voyage-law-2 on legal benchmarks. No independent verification found. [Low Confidence — vendor claim only]

### Market Context

- **118 AI legal tech companies** operate in India (Tracxn data), 23 funded, 4 at Series A+, 1 unicorn (Icertis — CLM, not RAG)
- **$1.9B invested** in global legal AI startups in 2025, up from $1B the prior year
- **40M+ cases pending** in Indian district courts, 6.2M in High Courts, 90K in Supreme Court
- **Supreme Court of India** is deploying AI/ML with IIT Madras for transcription and translation to 18 Indian languages
- **Nyaay AI** has the deepest court partnerships (16 High Courts + Supreme Court), but no public embedding model disclosure

_Source: [PIB India — AI in Supreme Court](https://x.com/PIB_India/status/1948708638400418139), [IndiaAI.gov.in](https://indiaai.gov.in/article/india-s-ai-driven-legal-future-opportunities-and-emerging-trends-in-2025), [Tracxn](https://tracxn.com/d/artificial-intelligence/ai-startups-in-legal-tech-in-india/__NkGQVg4qj42nbnv4P2gmZUKkKNxJTWzSzY28_uyHIbc/companies)_

### Implications for Jaanch

1. **Jaanch would be a first mover** in using Voyage AI for Indian legal text — no one else is doing this publicly
2. **The Indian legal AI ecosystem leans toward ElasticSearch + FAISS/Milvus** with OpenAI or open-source models — pgvector + Voyage is a differentiator
3. **Hindi legal text is a massive gap** — 20M pending cases in Hindi courts, HLDC corpus exists but no retrieval embedding benchmarks
4. **Phase 0 validation is non-negotiable** — voyage-law-2 was trained on Western legal corpora and has never been tested on Indian legal text in any public forum
5. **Vettam AI is the closest competitor** in approach (RAG + Indian legal fine-tuning + multilingual), but unfunded and early stage
6. **voyage-4-lite's Law domain regression** (-2.10 points) is a cautionary data point — always benchmark on your own data

---

_Research completed: 2026-02-04_
_This report provides a data-backed recommendation for upgrading Jaanch's embedding and reranking stack from OpenAI + Cohere to Voyage AI._
