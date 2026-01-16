# LDIP Database Schema Documentation

**Last Updated:** 2026-01-16
**Database:** Supabase PostgreSQL (xmbtcgmjvdouqstiqqom)
**Total Tables:** 28
**Total Migrations:** 37

---

## Table of Contents

1. [Overview](#overview)
2. [Tables by Domain](#tables-by-domain)
3. [Table-to-Code Mapping](#table-to-code-mapping)
4. [Known Issues & Discrepancies](#known-issues--discrepancies)
5. [Enums](#enums)
6. [Key Functions](#key-functions)
7. [Migration History](#migration-history)

---

## Overview

LDIP uses Supabase PostgreSQL with:
- **Row Level Security (RLS)** on all tables for matter isolation
- **pgvector** extension for semantic search
- **4-layer matter isolation**: RLS → Vector namespace → Redis keys → API middleware

### Security Model

All tables enforce matter isolation via RLS policies that check `matter_attorneys` membership:
```sql
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
)
```

---

## Tables by Domain

### Core Domain

| Table | Purpose | RLS |
|-------|---------|-----|
| `users` | User profiles (extends auth.users) | ✅ |
| `matters` | Case/matter records | ✅ |
| `matter_attorneys` | User-matter memberships with roles | ✅ |
| `documents` | Uploaded documents with OCR metadata | ✅ |
| `bounding_boxes` | OCR text positions for highlighting | ✅ |
| `chunks` | Document text chunks for RAG | ✅ |

### Entity Graph (MIG)

| Table | Purpose | RLS |
|-------|---------|-----|
| `identity_nodes` | Canonical entities (persons, orgs, etc.) | ✅ |
| `identity_edges` | Relationships between entities | ✅ |
| `entity_mentions` | Where entities appear in documents | ✅ |
| `alias_corrections` | Manual alias corrections audit trail | ✅ |

### Citation Engine

| Table | Purpose | RLS |
|-------|---------|-----|
| `citations` | Extracted Act citations from documents | ✅ |
| `act_resolutions` | Act discovery and resolution status | ✅ |
| `findings` | Engine-generated findings | ✅ |

### Timeline Engine

| Table | Purpose | RLS |
|-------|---------|-----|
| `events` | Extracted timeline events | ✅ |
| `anomalies` | Timeline anomaly detections | ✅ |

### Contradiction Engine

| Table | Purpose | RLS |
|-------|---------|-----|
| `statement_comparisons` | Statement pair comparison results | ✅ |

### Verification & Safety

| Table | Purpose | RLS |
|-------|---------|-----|
| `finding_verifications` | Attorney verification decisions | ✅ |
| `summary_verifications` | Summary section verifications | ✅ |
| `summary_notes` | Attorney notes on summaries | ✅ |
| `summary_edits` | Edited summary content | ✅ |

### Processing & Jobs

| Table | Purpose | RLS |
|-------|---------|-----|
| `processing_jobs` | Background job tracking | ✅ |
| `job_stage_history` | Stage-level job progress | ✅ |

### Memory & Audit

| Table | Purpose | RLS |
|-------|---------|-----|
| `matter_memory` | Persistent matter context | ✅ |
| `matter_query_history` | Query audit trail (append-only) | ✅ |
| `audit_logs` | Security audit logs | ❌ (service role only) |
| `activities` | User activity feed | ✅ (per-user) |

### OCR Validation

| Table | Purpose | RLS |
|-------|---------|-----|
| `ocr_validation_log` | OCR correction audit trail (immutable) | ✅ |
| `ocr_human_review` | Human review queue for low-confidence OCR | ✅ |

---

## Table-to-Code Mapping

### Complete Mapping Matrix

| DB Table | Backend Model | Backend File | Frontend Type | Frontend File |
|----------|---------------|--------------|---------------|---------------|
| `users` | - | - | - | - |
| `matters` | `Matter` | `models/matter.py` | `Matter` | `types/matter.ts` |
| `matter_attorneys` | `MatterMember` | `models/matter.py` | `MatterMember` | `types/matter.ts` |
| `documents` | `Document` | `models/document.py` | `Document` | `types/document.ts` |
| `chunks` | `Chunk` | `models/chunk.py` | `Chunk` | `types/document.ts` |
| `bounding_boxes` | - | - | `BoundingBox` | `types/document.ts` |
| `identity_nodes` | `EntityNode` | `models/entity.py` | `Entity` | `types/entity.ts` |
| `identity_edges` | `EntityEdge` | `models/entity.py` | `EntityEdge` | `types/entity.ts` |
| `entity_mentions` | `EntityMention` | `models/entity.py` | `EntityMention` | `types/entity.ts` |
| `citations` | `Citation` | `models/citation.py` | `Citation` | `types/citation.ts` |
| `act_resolutions` | `ActResolution` | `models/citation.py` | `ActResolution` | `types/citation.ts` |
| `events` | `RawEvent`, `ClassifiedEvent` | `models/timeline.py` | `TimelineEvent` | `types/timeline.ts` |
| `anomalies` | `Anomaly` | `models/anomaly.py` | ❌ Missing | - |
| `statement_comparisons` | `StatementPairComparison` | `models/contradiction.py` | ❌ Missing | - |
| `finding_verifications` | `FindingVerification` | `models/verification.py` | `FindingVerification` | `types/verification.ts` |
| `processing_jobs` | `ProcessingJob` | `models/job.py` | `ProcessingJob` | `types/job.ts` |
| `activities` | `ActivityRecord` | `models/activity.py` | `Activity` | `types/activity.ts` |

---

## Known Issues & Discrepancies

### 1. Missing Code Model Fields

These DB columns exist but are NOT in the code models:

| Table | Column | Type | Notes |
|-------|--------|------|-------|
| `documents` | `deleted_at` | `timestamptz` | Soft delete support |
| `documents` | `ocr_retry_count` | `integer` | OCR retry tracking |
| `documents` | `validation_status` | `text` | OCR validation status |

**Impact:** Soft delete works at DB level but code doesn't filter/expose it properly.

**Fix:** Add fields to `Document` model in both backend and frontend.

### 2. Field Name Mismatches

These DB columns have different names in code:

| Table | DB Column | Code Field | Notes |
|-------|-----------|------------|-------|
| `identity_edges` | `source_node_id` | `source_entity_id` | Aliased in queries |
| `identity_edges` | `target_node_id` | `target_entity_id` | Aliased in queries |
| `citations` | `section` | `section_number` | Aliased in queries |

**Impact:** Queries work via aliasing but inconsistent naming causes confusion.

**Fix:** Either rename DB columns or update code to match DB names.

### 3. Missing Frontend Types

These backend models have NO corresponding frontend TypeScript types:

| Backend Model | File | Needed For |
|---------------|------|------------|
| `Anomaly` | `models/anomaly.py` | Timeline anomaly display |
| `StatementPairComparison` | `models/contradiction.py` | Contradiction display |

**Impact:** Frontend can't properly type these responses.

**Fix:** Create `types/anomaly.ts` and `types/contradiction.ts`.

### 4. Type Mismatches

| Table | Column | DB Type | Code Type | Issue |
|-------|--------|---------|-----------|-------|
| `events` | `event_date` | `date` | `string` (FE) | FE uses string instead of Date |
| `*` | `*_at` timestamps | `timestamptz` | `string` (FE) | FE uses string instead of Date |

**Impact:** No runtime issues but loses type safety.

---

## Enums

### Database Enums

```sql
-- Summary verification decision
CREATE TYPE summary_verification_decision AS ENUM ('verified', 'flagged');

-- Summary section types
CREATE TYPE summary_section_type AS ENUM ('parties', 'subject_matter', 'current_status', 'key_issue');

-- Activity types
CREATE TYPE activity_type AS ENUM (
  'processing_complete', 'processing_started', 'processing_failed',
  'contradictions_found', 'verification_needed', 'matter_opened'
);
```

### Code Enums (should match)

- `DocumentStatus`: pending, processing, ocr_complete, ocr_failed, completed, failed
- `MatterStatus`: active, archived
- `MatterRole`: owner, editor, viewer
- `VerificationDecision`: pending, approved, rejected, flagged
- `AnomalyType`: gap, sequence_violation, duplicate, outlier
- `AnomalySeverity`: low, medium, high, critical

---

## Key Functions

### Search Functions

| Function | Purpose |
|----------|---------|
| `bm25_search_chunks(query, matter_id, limit)` | BM25 keyword search |
| `semantic_search_chunks(embedding, matter_id, limit)` | Vector similarity search |
| `hybrid_search_chunks(query, embedding, matter_id, ...)` | RRF fusion search |

### Helper Functions

| Function | Purpose |
|----------|---------|
| `user_has_matter_access(matter_id)` | Check user access (avoids RLS recursion) |
| `resolve_or_create_entity(matter_id, type, name)` | Entity resolution with alias matching |
| `merge_entities(matter_id, keep_id, merge_id)` | Merge two entities |
| `get_job_queue_stats(matter_id)` | Job queue statistics |

---

## Migration History

All 37 migrations are tracked in `supabase_migrations.schema_migrations`.

### Migration Groups

| Date Range | Migrations | Description |
|------------|------------|-------------|
| 2026-01-04 | 1 | Users table |
| 2026-01-05 | 2 | Matters, matter_attorneys |
| 2026-01-06 | 11 | Core tables (documents, chunks, citations, events, MIG) |
| 2026-01-07 | 2 | RLS fix, OCR columns |
| 2026-01-08 | 4 | OCR validation, quality, hybrid search |
| 2026-01-12 | 2 | Entity mentions, type constraints |
| 2026-01-13 | 1 | Alias corrections |
| 2026-01-14 | 9 | Jobs, anomalies, contradictions, verifications |
| 2026-01-15 | 2 | Security fixes, soft delete |
| 2026-01-16 | 3 | Summary tables, activities |

### Latest Migrations

```
20260116000001_create_summary_verification_tables
20260116000002_create_activities_table
20260116000003_create_summary_edits_table
```

---

## Maintenance Notes

### Running Migrations

Always use Supabase CLI to maintain tracking:
```bash
# Create new migration
supabase migration new my_feature

# Apply migrations
supabase db push

# Check status
supabase db diff
```

### Schema Drift Detection

If tables exist but aren't tracked, insert into `schema_migrations`:
```sql
INSERT INTO supabase_migrations.schema_migrations (version, name)
VALUES ('YYYYMMDDHHMMSS', 'migration_name')
ON CONFLICT (version) DO NOTHING;
```

---

## Related Documents

- [Architecture Decision Document](_bmad-output/architecture.md)
- [Supabase Schema Audit Report](_bmad-output/reports/supabase-audit-report.md)
- [Migration Tracking Detailed](_bmad-output/reports/migration-tracking-detailed.md)
