# Migration Tracking Report - Detailed Analysis

**Generated:** 2026-01-16
**Total Local Migrations:** 37
**Tracked in DB:** 19
**Untracked (Schema Drift):** 18

---

## Summary

| Status | Count | Description |
|--------|-------|-------------|
| ✅ Applied & Tracked | 19 | In `schema_migrations` table |
| ⚠️ Applied but UNTRACKED | 12 | Tables exist, not in `schema_migrations` |
| ❓ Not Applied | 6 | Tables/columns may not exist |

---

## Part 1: Applied & Tracked Migrations (19)

These are properly tracked in `supabase_migrations.schema_migrations`:

| # | Migration | Creates/Modifies | Status |
|---|-----------|------------------|--------|
| 1 | `20260104000000_create_users_table` | `users` table | ✅ Tracked |
| 2 | `20260105000001_create_matters_table` | `matters` table | ✅ Tracked |
| 3 | `20260105000002_create_matter_attorneys_table` | `matter_attorneys` table | ✅ Tracked |
| 4 | `20260106000001_create_documents_table` | `documents` table | ✅ Tracked |
| 5 | `20260106000002_create_chunks_table` | `chunks` table | ✅ Tracked |
| 6 | `20260106000003_create_bounding_boxes_table` | `bounding_boxes` table | ✅ Tracked |
| 7 | `20260106000004_create_findings_table` | `findings` table | ✅ Tracked |
| 8 | `20260106000005_create_matter_memory_table` | `matter_memory` table | ✅ Tracked |
| 9 | `20260106000006_create_citations_table` | `citations` table | ✅ Tracked |
| 10 | `20260106000007_create_act_resolutions_table` | `act_resolutions` table | ✅ Tracked |
| 11 | `20260106000008_create_events_table` | `events` table | ✅ Tracked |
| 12 | `20260106000009_create_mig_tables` | `identity_nodes`, `identity_edges` tables | ✅ Tracked |
| 13 | `20260106000010_create_storage_policies` | Storage RLS policies | ✅ Tracked |
| 14 | `20260106000011_create_audit_logs_table` | `audit_logs` table | ✅ Tracked |
| 15 | `20260107000001_fix_matter_attorneys_rls_recursion` | RLS policy fix | ✅ Tracked |
| 16 | `20260107000002_add_ocr_columns_to_documents` | `extracted_text`, `ocr_confidence`, etc. columns | ✅ Tracked |
| 17 | `20260108000001_create_ocr_validation_tables` | `ocr_validation_log`, `ocr_human_review` tables | ✅ Tracked |
| 18 | `20260108000002_add_ocr_quality_columns` | `ocr_confidence_per_page`, `ocr_quality_status` columns | ✅ Tracked |
| 19 | `20260108000003_add_bbox_reading_order` | `reading_order_index` column on `bounding_boxes` | ✅ Tracked |

---

## Part 2: Untracked Migrations (18) - SCHEMA DRIFT

These migrations exist locally but are NOT in `schema_migrations`. **However, most tables/changes DO exist in the live DB**, indicating they were applied manually.

### 2A: Applied but Untracked (Tables Exist)

| # | Migration | Creates/Modifies | DB Status | Needs Tracking |
|---|-----------|------------------|-----------|----------------|
| 20 | `20260108000004_add_hybrid_search` | `fts` column, search functions | ✅ Exists | ⚠️ YES |
| 21 | `20260112000001_create_entity_mentions_table` | `entity_mentions` table | ✅ Exists | ⚠️ YES |
| 22 | `20260112000002_add_entity_type_constraint` | CHECK constraints | ❓ Check | ⚠️ YES |
| 23 | `20260113000001_create_alias_corrections_table` | `alias_corrections` table | ✅ Exists | ⚠️ YES |
| 24 | `20260114000001_create_processing_jobs_table` | `processing_jobs`, `job_stage_history` tables | ✅ Exists | ⚠️ YES |
| 25 | `20260114000002_enhance_citations_table` | New columns on `citations`, `act_resolutions` | ❓ Check | ⚠️ YES |
| 26 | `20260114000003_create_anomalies_table` | `anomalies` table | ✅ Exists | ⚠️ YES |
| 27 | `20260114000004_create_statement_comparisons_table` | `statement_comparisons` table | ✅ Exists | ⚠️ YES |
| 28 | `20260114000005_add_contradiction_classification` | `contradiction_type`, `extracted_values` columns | ❓ Check | ⚠️ YES |
| 29 | `20260114000006_add_severity_scoring` | `severity`, `severity_reasoning`, `explanation` columns | ❓ Check | ⚠️ YES |
| 30 | `20260114000007_create_matter_query_history` | `matter_query_history` table | ✅ Exists | ⚠️ YES |
| 31 | `20260114000008_add_archived_session_memory_type` | ALTER constraint on `matter_memory` | ❓ Check | ⚠️ YES |
| 32 | `20260114000009_create_finding_verifications_table` | `finding_verifications` table | ✅ Exists | ⚠️ YES |
| 33 | `20260115000001_security_and_indexing_fixes` | RLS fixes, multilingual FTS | ❓ Check | ⚠️ YES |
| 34 | `20260115000002_add_documents_soft_delete` | `deleted_at` column on `documents` | ❓ Check | ⚠️ YES |
| 35 | `20260116000001_create_summary_verification_tables` | `summary_verifications`, `summary_notes` tables | ✅ Exists | ⚠️ YES |
| 36 | `20260116000002_create_activities_table` | `activities` table | ✅ Exists | ⚠️ YES |
| 37 | `20260116000003_create_summary_edits_table` | `summary_edits` table | ✅ Exists | ⚠️ YES |

---

## Part 3: Detailed Migration Content Analysis

### Migration 20: `20260108000004_add_hybrid_search`
**Purpose:** Add full-text search capability for RAG pipeline
**Creates:**
- `chunks.fts` - tsvector column (GENERATED ALWAYS)
- `idx_chunks_fts` - GIN index
- `bm25_search_chunks()` function
- `semantic_search_chunks()` function
- `hybrid_search_chunks()` function (RRF fusion)

**Check:** `SELECT column_name FROM information_schema.columns WHERE table_name='chunks' AND column_name='fts'`

---

### Migration 21: `20260112000001_create_entity_mentions_table`
**Purpose:** Track entity mentions with source locations for highlighting
**Creates:**
- `entity_mentions` table
- Multiple indexes
- RLS policies

**Check:** `SELECT * FROM information_schema.tables WHERE table_name='entity_mentions'`

---

### Migration 22: `20260112000002_add_entity_type_constraint`
**Purpose:** Enforce valid entity types
**Creates:**
- CHECK constraint `identity_nodes_entity_type_check`
- CHECK constraint `identity_edges_relationship_type_check`

**Check:**
```sql
SELECT constraint_name FROM information_schema.table_constraints
WHERE table_name='identity_nodes' AND constraint_type='CHECK'
```

---

### Migration 23: `20260113000001_create_alias_corrections_table`
**Purpose:** Track manual corrections to aliases
**Creates:**
- `alias_corrections` table
- Helper functions `get_correction_stats()`, `get_recent_corrections()`
- RLS policies

---

### Migration 24: `20260114000001_create_processing_jobs_table`
**Purpose:** Background job tracking
**Creates:**
- `processing_jobs` table
- `job_stage_history` table
- `get_job_queue_stats()` function
- Multiple indexes and RLS policies

---

### Migration 25: `20260114000002_enhance_citations_table`
**Purpose:** Additional citation columns
**Adds to `citations`:**
- `act_name_original`
- `subsection`
- `clause`
- `raw_citation_text`
- `extraction_metadata`

**Adds to `act_resolutions`:**
- `act_name_display`

---

### Migration 26: `20260114000003_create_anomalies_table`
**Purpose:** Timeline anomaly detection
**Creates:**
- `anomalies` table with types: gap, sequence_violation, duplicate, outlier
- Severity levels: low, medium, high, critical

---

### Migration 27: `20260114000004_create_statement_comparisons_table`
**Purpose:** Contradiction detection
**Creates:**
- `statement_comparisons` table
- Result types: contradiction, consistent, uncertain, unrelated

---

### Migration 28: `20260114000005_add_contradiction_classification`
**Purpose:** Contradiction type classification
**Adds to `statement_comparisons`:**
- `contradiction_type` - semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch
- `extracted_values` - JSONB

---

### Migration 29: `20260114000006_add_severity_scoring`
**Purpose:** Severity scoring for contradictions
**Adds to `statement_comparisons`:**
- `severity` - high, medium, low
- `severity_reasoning`
- `explanation`

---

### Migration 30: `20260114000007_create_matter_query_history`
**Purpose:** Forensic audit trail
**Creates:**
- `matter_query_history` table (APPEND-ONLY)
- RLS policies preventing UPDATE/DELETE

---

### Migration 31: `20260114000008_add_archived_session_memory_type`
**Purpose:** Session TTL support
**Modifies:**
- `matter_memory.memory_type` constraint to include 'archived_session'
- New partial unique index

---

### Migration 32: `20260114000009_create_finding_verifications_table`
**Purpose:** Attorney verification workflow
**Creates:**
- `finding_verifications` table
- Decision types: pending, approved, rejected, flagged
- Tiered thresholds: >90% optional, 70-90% suggested, <70% required

---

### Migration 33: `20260115000001_security_and_indexing_fixes`
**Purpose:** Code review fixes
**Modifies:**
- `ocr_validation_log` RLS (immutable audit logs)
- `bounding_boxes` index (multilingual)
- `chunks.fts` (multilingual)
- Search functions (multilingual support)

---

### Migration 34: `20260115000002_add_documents_soft_delete`
**Purpose:** Soft delete support
**Adds to `documents`:**
- `deleted_at` column
- Index for soft-delete filtering
- RLS policy updates

---

### Migration 35: `20260116000001_create_summary_verification_tables`
**Purpose:** Summary verification
**Creates:**
- `summary_verification_decision` enum
- `summary_section_type` enum
- `summary_verifications` table
- `summary_notes` table

---

### Migration 36: `20260116000002_create_activities_table`
**Purpose:** Activity feed
**Creates:**
- `activity_type` enum
- `activities` table

---

### Migration 37: `20260116000003_create_summary_edits_table`
**Purpose:** Summary editing
**Creates:**
- `summary_edits` table

---

## Part 4: Fix Script

To fix the schema drift, run this SQL to insert missing migration records:

```sql
-- Insert missing migration records for already-applied changes
INSERT INTO supabase_migrations.schema_migrations (version, name) VALUES
  ('20260108000004', 'add_hybrid_search'),
  ('20260112000001', 'create_entity_mentions_table'),
  ('20260112000002', 'add_entity_type_constraint'),
  ('20260113000001', 'create_alias_corrections_table'),
  ('20260114000001', 'create_processing_jobs_table'),
  ('20260114000002', 'enhance_citations_table'),
  ('20260114000003', 'create_anomalies_table'),
  ('20260114000004', 'create_statement_comparisons_table'),
  ('20260114000005', 'add_contradiction_classification'),
  ('20260114000006', 'add_severity_scoring'),
  ('20260114000007', 'create_matter_query_history'),
  ('20260114000008', 'add_archived_session_memory_type'),
  ('20260114000009', 'create_finding_verifications_table'),
  ('20260115000001', 'security_and_indexing_fixes'),
  ('20260115000002', 'add_documents_soft_delete'),
  ('20260116000001', 'create_summary_verification_tables'),
  ('20260116000002', 'create_activities_table'),
  ('20260116000003', 'create_summary_edits_table')
ON CONFLICT (version) DO NOTHING;
```

---

## Part 5: Verification Queries

Run these to verify what actually exists in the DB:

```sql
-- Check all tables in public schema
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Check all tracked migrations
SELECT version, name FROM supabase_migrations.schema_migrations
ORDER BY version;

-- Check specific columns exist
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('documents', 'chunks', 'statement_comparisons')
ORDER BY table_name, ordinal_position;

-- Check functions exist
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name LIKE '%search%';

-- Check enums exist
SELECT typname FROM pg_type
WHERE typtype = 'e'
  AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
```

---

## Recommendations

1. **Immediate:** Run the fix script to sync `schema_migrations` with reality
2. **Verify:** Run verification queries to confirm all expected objects exist
3. **Process:** Always use `supabase db push` or CLI for future migrations
4. **Monitor:** Set up alerts for schema drift detection
