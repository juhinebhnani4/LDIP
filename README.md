# Jaanch Lite - Simplified Legal Document Intelligence

A proof-of-concept implementation of Jaanch using modern AI tools for a 10x simpler architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    JAANCH LITE STACK                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PARSING          → Landing AI ADE (grounded chunks + bboxes)   │
│  EMBEDDINGS       → Voyage AI voyage-law-2 (legal-specific)     │
│  RERANKING        → Voyage AI rerank-2.5 (instruction-following)│
│  CITATION EXTRACT → Instructor + Pydantic (schema-enforced)     │
│  VECTOR STORE     → ChromaDB (simple, local)                    │
│  ACTS LIBRARY     → Pre-indexed Indian acts (one-time setup)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Comparison with Full Jaanch

| Aspect | Full Jaanch | Jaanch Lite |
|--------|-------------|-------------|
| Lines of Code | ~50,000 | ~1,000 |
| Services | 60 | 6 |
| Bbox linking | 71 files (fuzzy match) | 0 (native from ADE) |
| Citation extraction | Gemini LLM | Regex + Instructor hybrid |
| Embedding model | OpenAI ada-002 | Voyage voyage-law-2 |
| Reranking | Cohere | Voyage rerank-2.5 |

## Project Structure

```
jaanch-lite/
├── src/
│   ├── core/              # Configuration, models, utilities
│   │   ├── config.py      # Environment and settings
│   │   ├── models.py      # Pydantic models
│   │   └── utils.py       # Helper functions
│   │
│   ├── parsers/           # Document parsing
│   │   └── ade_parser.py  # Landing AI ADE integration
│   │
│   ├── embeddings/        # Vector embeddings
│   │   └── voyage.py      # Voyage AI embeddings + reranking
│   │
│   ├── citations/         # Citation extraction
│   │   ├── extractor.py   # Hybrid regex + LLM extraction
│   │   ├── patterns.py    # Indian legal citation patterns
│   │   └── abbreviations.py # Act abbreviation mappings
│   │
│   ├── search/            # RAG search
│   │   └── rag.py         # Hybrid search with reranking
│   │
│   └── acts/              # Acts library
│       ├── indexer.py     # One-time act indexing
│       ├── verifier.py    # Citation verification
│       └── india_code.py  # India Code downloader
│
├── data/
│   ├── acts/              # Downloaded act PDFs
│   ├── samples/           # Sample documents for testing
│   └── known_acts.json    # Act metadata from Jaanch
│
├── notebooks/
│   ├── 01_parse_document.ipynb
│   ├── 02_extract_citations.ipynb
│   ├── 03_build_acts_library.ipynb
│   └── 04_full_pipeline.ipynb
│
├── scripts/
│   ├── index_acts.py      # Build acts vector DB
│   └── demo.py            # Full pipeline demo
│
├── tests/
│   └── test_*.py          # Unit tests
│
├── vectordb/              # ChromaDB storage
│   ├── acts/              # Acts collection
│   └── documents/         # User documents collection
│
├── pyproject.toml         # Dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Build acts library (one-time):**
   ```bash
   python scripts/index_acts.py
   ```

4. **Run demo:**
   ```bash
   python scripts/demo.py path/to/legal_document.pdf
   ```

## API Keys Required

- **Landing AI**: https://landing.ai/ (for ADE parsing)
- **Voyage AI**: https://www.voyageai.com/ (for embeddings + reranking)
- **OpenAI**: https://platform.openai.com/ (for Instructor extraction)

## Features

### 1. Document Parsing with Visual Grounding
Every chunk comes with bounding box coordinates from ADE - no fuzzy matching needed.

### 2. Legal-Specific Embeddings
Voyage AI's `voyage-law-2` model understands legal terminology better than generic models.

### 3. Instruction-Following Reranking
Tell the reranker what type of legal documents to prioritize:
```python
reranker.rerank(
    query="cheque bounce punishment",
    instruction="Retrieve statutory provisions from Central Acts, not case commentary"
)
```

### 4. Schema-Enforced Citation Extraction
Pydantic models ensure structured, validated citation data:
```python
class Citation(BaseModel):
    act_name: str          # "Negotiable Instruments Act, 1881"
    section: str           # "138"
    subsection: str | None # "(1)(a)"
    confidence: float      # 0.0 - 1.0
```

### 5. Pre-Indexed Acts Library
50+ Indian Central Acts indexed for instant citation verification.
