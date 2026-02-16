# Acts Library Architecture - Design Document

**Status:** Decision Made, Not Yet Implemented
**Date:** 2026-02-06
**Decision Makers:** Party Mode Session (Winston, Mary, John, Dr. Quinn, Amelia)

---

## Problem Statement

Acts (Indian statutes) are shared reference documents that:
- Don't belong to any user or matter
- Need to be searchable, verifiable against citations
- Get amended over time by Parliament
- Are cited across hundreds of matters
- Must support admin bulk upload in a future phase

Currently, Acts either go to the `documents` table (gets processed but not shared) or `library_documents` table (shared but not processed). Neither works fully.

---

## Core Principles

1. **Acts are immutable reference documents** - like a dictionary, you reference it, you don't copy it
2. **Sections are the atomic unit** - not chunks. "Section 138" is meaningful; "Chunk 47" is not
3. **Separate what's stable from what changes:**
   - Stable: PDF, section text, section boundaries
   - Changes: embeddings, search indexes, models
4. **Temporal awareness** - Acts get amended; old citations must verify against old versions
5. **Content-addressed storage** - hash PDFs to avoid duplicate processing
6. **Honest failures** - if a version isn't available, say so; never guess

---

## Architecture Decision: Option 9 + Option 11

**Option 9:** Chunks/sections table owns the relationship (via `library_document_id`)
**Option 11:** Pre-seeded Acts database for common statutes

---

## Schema Design

### Table: `library_documents` (Existing - Enhanced)

The book itself.

```sql
library_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(500) NOT NULL,           -- 'Negotiable Instruments Act, 1881'
  short_title VARCHAR(100),              -- 'NI Act'
  year INT,                              -- 1881
  jurisdiction VARCHAR(20) DEFAULT 'central',  -- 'central', 'state'
  state_code VARCHAR(10),                -- 'MH', 'DL', NULL for central

  -- Storage
  filename VARCHAR(500) NOT NULL,
  storage_path VARCHAR(500) NOT NULL,
  file_size INT DEFAULT 0,
  page_count INT,
  pdf_hash VARCHAR(64),                  -- SHA-256 for deduplication

  -- Lifecycle
  status VARCHAR(20) DEFAULT 'active',   -- 'active', 'repealed', 'superseded'
  replaced_by UUID REFERENCES library_documents(id),
  last_amended DATE,                     -- Last amendment date

  -- Source
  source VARCHAR(50) DEFAULT 'user_upload',  -- 'user_upload', 'india_code', 'admin', 'pre_seeded'
  source_url VARCHAR(500),
  added_by UUID,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
)
```

### Table: `library_act_aliases` (New)

Maps all variations of Act names to the canonical record.

```sql
library_act_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  library_document_id UUID NOT NULL REFERENCES library_documents(id) ON DELETE CASCADE,
  alias VARCHAR(200) NOT NULL,           -- 'NI Act', 'N.I. Act', 'Negotiable Instruments Act'
  is_canonical BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMPTZ DEFAULT now(),

  UNIQUE(alias)  -- No two Acts can share an alias
)
```

**Example data:**
| library_document_id | alias | is_canonical |
|---------------------|-------|--------------|
| abc-123 | Negotiable Instruments Act, 1881 | true |
| abc-123 | NI Act | false |
| abc-123 | N.I. Act | false |
| abc-123 | Negotiable Instruments Act | false |

### Table: `library_sections` (New)

The permanent index card. Section-level text extraction with temporal versioning.

```sql
library_sections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  library_document_id UUID NOT NULL REFERENCES library_documents(id) ON DELETE CASCADE,

  -- Section identity
  section_type VARCHAR(20) NOT NULL DEFAULT 'section',  -- 'section', 'schedule', 'appendix', 'proviso', 'definition', 'explanation'
  section_number VARCHAR(50) NOT NULL,   -- '138', '138A', '138(1)(a)', 'Schedule-I-Entry-42'
  section_title VARCHAR(500),            -- 'Dishonour of cheque for insufficiency'
  section_text TEXT NOT NULL,            -- Full section text

  -- Location in PDF
  page_start INT,
  page_end INT,

  -- Temporal versioning (for amendments)
  valid_from DATE NOT NULL,              -- When this version started
  valid_to DATE,                         -- NULL = current version
  amendment_reference VARCHAR(200),      -- 'Banking Laws (Amendment) Act, 2015'

  -- Repeal tracking
  is_repealed BOOLEAN DEFAULT FALSE,
  repealed_date DATE,
  repealed_by VARCHAR(200),              -- 'Amendment Act 2025'

  -- Quality
  quality_score FLOAT,                   -- OCR quality indicator

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),

  -- Constraints
  UNIQUE(library_document_id, section_number, valid_from)
)

-- Index for fast lookups
CREATE INDEX idx_section_lookup
  ON library_sections(library_document_id, section_number);

-- Index for temporal queries
CREATE INDEX idx_section_temporal
  ON library_sections(library_document_id, section_number, valid_from, valid_to);
```

### Table: `library_embeddings` (New)

The replaceable finding helper. Can be regenerated when embedding models change.

```sql
library_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  section_id UUID NOT NULL REFERENCES library_sections(id) ON DELETE CASCADE,

  -- Embedding
  embedding VECTOR(1536),                -- Dimension matches current model
  model_version VARCHAR(50) NOT NULL,    -- 'text-embedding-3-small'

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),

  -- Constraint: one embedding per section per model
  UNIQUE(section_id, model_version)
)

CREATE INDEX idx_embedding_model
  ON library_embeddings(model_version);
```

---

## Edge Cases Handled

### 1. Section Numbering Chaos
**Problem:** `138`, `138A`, `138(1)(a)(ii)`, `Schedule-I-Entry-42`
**Solution:** `section_number` is VARCHAR(50), not INT. Normalized on insert.

### 2. Amended Acts
**Problem:** Companies Act 2013 amended 47 times. Which version?
**Solution:** Temporal versioning with `valid_from` / `valid_to`. Query by date returns the version valid at that time.

```sql
-- Get Section 138 as it existed in 2016
SELECT section_text
FROM library_sections
WHERE library_document_id = :act_id
  AND section_number = '138'
  AND valid_from <= '2016-01-01'
  AND (valid_to IS NULL OR valid_to > '2016-01-01')
```

### 3. Same Act, Different Names
**Problem:** 'NI Act' = 'Negotiable Instruments Act' = 'N.I. Act'
**Solution:** `library_act_aliases` table. Citation lookup goes through alias first.

### 4. Section Doesn't Exist
**Problem:** User cites 'Section 999 of Contract Act'
**Solution:** Query returns empty. Verification status: `UNVERIFIABLE`, reason: `SECTION_NOT_FOUND`.

### 5. Repealed Acts
**Problem:** IPC 1860 replaced by BNS 2023. Old cases still cite IPC.
**Solution:** Both exist. IPC has `status: 'repealed'`, `replaced_by: BNS_id`. Old citations still verify. New citations get warning.

### 6. Huge Sections
**Problem:** Section 2 of Companies Act is 15 pages of definitions.
**Solution:** Store full text in `library_sections`. For embeddings, the embedding layer can split into sub-chunks internally. Section text is truth, embeddings are derived.

### 7. Schedules and Appendices
**Problem:** 'First Schedule, Entry 42' is a valid citation.
**Solution:** `section_type` enum covers: section, schedule, appendix, proviso, definition, explanation.

### 8. Same Name, Different Years
**Problem:** 'Arbitration Act 1940' vs 'Arbitration Act 1996'
**Solution:** `UNIQUE(title, year)` on `library_documents`. Query must include year or return multiple matches for disambiguation.

### 9. State vs Central Acts
**Problem:** Maharashtra Rent Control Act != Delhi Rent Control Act
**Solution:** `jurisdiction` + `state_code` on `library_documents`.

### 10. OCR Garbage
**Problem:** Poor PDF quality producing garbled text
**Solution:** `quality_score` on sections. Low scores flagged for human review.

### 11. Two Acts Have Same Section Numbers
**Problem:** Section 138 of NI Act != Section 138 of Companies Act
**Solution:** `library_document_id` is the namespace. Query always scoped by Act. Composite key: `(library_document_id, section_number)`.

### 12. Duplicate PDF Uploads
**Problem:** Same Act uploaded multiple times
**Solution:** `pdf_hash` (SHA-256) on `library_documents`. Check hash before processing. Same hash = reuse existing record.

---

## Verification Flow (Updated)

```
1. Extract citation from user document:
   "Section 138 of the Negotiable Instruments Act, 1881"

2. Resolve Act:
   alias lookup: "Negotiable Instruments Act" → library_document_id: abc-123

3. Get document date (if available):
   Affidavit dated 2018-03-15

4. Query section with temporal awareness:
   WHERE act = abc-123 AND section = '138' AND valid_in(2018)

5. Compare user's quoted text against section_text

6. Return verdict:
   - VERIFIED: Quote matches
   - MISQUOTED: Quote differs (show diff)
   - UNVERIFIABLE: Section/version not in library
   - SECTION_NOT_FOUND: Section doesn't exist in this Act
   - ACT_REPEALED: Act has been repealed (with replacement reference)
```

---

## What's Stable vs Replaceable

| Layer | Data | Lifespan | Regenerable? |
|-------|------|----------|--------------|
| Storage | PDF files | Permanent | No (source) |
| Metadata | library_documents | Permanent | No (source) |
| Aliases | library_act_aliases | Permanent | No (curated) |
| Sections | library_sections | Permanent | From PDF (expensive) |
| Embeddings | library_embeddings | Temporary | Yes (anytime, cheap) |

---

## Implementation Phases

### Phase 1: Foundation (Now)
- Create `library_sections` table
- Create `library_embeddings` table
- Create `library_act_aliases` table
- Modify `ActIndexer` to query `library_sections` instead of chunks
- Uploaded Acts: process into sections (not arbitrary chunks)
- Use current version only (`valid_from` = Act year, `valid_to` = NULL)

### Phase 2: Admin Upload (Next)
- Admin UI for bulk Act upload
- Section extraction pipeline (OCR PDF → detect section boundaries → split)
- Pre-seed top 50 common Indian Acts
- Alias management UI
- Content-addressed deduplication via `pdf_hash`

### Phase 3: Temporal Versioning (Future)
- Support multiple versions per section
- Amendment upload: specify which sections changed
- Date-aware verification (use document date for lookup)
- Historical version tracking

### Phase 4: Scale (Long-term)
- Separate Acts database/service
- Central Acts API: `GET /acts/{id}/sections/{number}?as_of=2018-01-01`
- Embedding model migration tool (regenerate all embeddings with new model)
- State Acts support with jurisdiction scoping

---

## Migration Notes

- `library_documents` table already exists with data
- New tables are purely additive (no breaking changes)
- Existing `document_ocr_chunks` continues to work for regular documents
- `ActIndexer` needs a code change to prefer `library_sections` over chunks
- Existing library links (`matter_library_links`) remain unchanged
