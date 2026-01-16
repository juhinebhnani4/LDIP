# Supabase Schema vs Code Implementation Audit Report

**Generated:** 2026-01-16
**Project:** LDIP
**Database:** xmbtcgmjvdouqstiqqom.supabase.co

---

## Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| Live DB Tables | 28 | - |
| Local Migration Files | 37 | - |
| Applied Migrations (tracked) | 37 | ✅ SYNCED |
| Pending Migrations | 0 | ✅ OK |
| Schema Drift Detected | NO | ✅ OK |
| Tables with untracked creation | 0 | ✅ OK |

### Status Update (2026-01-16)
All 37 migrations are now tracked and synced. No pending migrations or schema drift.

### Code Model Fixes Applied (2026-01-16)
The following code model discrepancies have been **RESOLVED**:
1. ✅ `deleted_at` added to `Document` and `Matter` models (backend + frontend)
2. ✅ `ocr_retry_count` added to `Document` model (backend + frontend)
3. ✅ `validation_status` added to `Document` model (backend + frontend)

### Remaining Issues (Low Priority)
- `identity_edges`: `source_node_id`/`target_node_id` naming vs code's `source_entity_id`/`target_entity_id` - This is intentional mapping
- `citations`: `section` vs `section_number` - This is intentional mapping

---

## 1. Migration Status

### 1.1 Applied Migrations (19 tracked)

| # | Version | Migration Name | Status |
|---|---------|----------------|--------|
| 1 | 20260104000000 | create_users_table | ✅ Applied |
| 2 | 20260105000001 | create_matters_table | ✅ Applied |
| 3 | 20260105000002 | create_matter_attorneys_table | ✅ Applied |
| 4 | 20260106000001 | create_documents_table | ✅ Applied |
| 5 | 20260106000002 | create_chunks_table | ✅ Applied |
| 6 | 20260106000003 | create_bounding_boxes_table | ✅ Applied |
| 7 | 20260106000004 | create_findings_table | ✅ Applied |
| 8 | 20260106000005 | create_matter_memory_table | ✅ Applied |
| 9 | 20260106000006 | create_citations_table | ✅ Applied |
| 10 | 20260106000007 | create_act_resolutions_table | ✅ Applied |
| 11 | 20260106000008 | create_events_table | ✅ Applied |
| 12 | 20260106000009 | create_mig_tables | ✅ Applied |
| 13 | 20260106000010 | create_storage_policies | ✅ Applied |
| 14 | 20260106000011 | create_audit_logs_table | ✅ Applied |
| 15 | 20260107000001 | fix_matter_attorneys_rls_recursion | ✅ Applied |
| 16 | 20260107000002 | add_ocr_columns_to_documents | ✅ Applied |
| 17 | 20260108000001 | create_ocr_validation_tables | ✅ Applied |
| 18 | 20260108000002 | add_ocr_quality_columns | ✅ Applied |
| 19 | 20260108000003 | add_bbox_reading_order | ✅ Applied |

### 1.2 Pending Migrations (18 NOT applied)

| # | Version | Migration Name | Status |
|---|---------|----------------|--------|
| 1 | 20260108000004 | add_hybrid_search | ❌ PENDING |
| 2 | 20260112000001 | create_entity_mentions_table | ❌ PENDING* |
| 3 | 20260112000002 | add_entity_type_constraint | ❌ PENDING |
| 4 | 20260113000001 | create_alias_corrections_table | ❌ PENDING* |
| 5 | 20260114000001 | create_processing_jobs_table | ❌ PENDING* |
| 6 | 20260114000002 | enhance_citations_table | ❌ PENDING |
| 7 | 20260114000003 | create_anomalies_table | ❌ PENDING* |
| 8 | 20260114000004 | create_statement_comparisons_table | ❌ PENDING* |
| 9 | 20260114000005 | add_contradiction_classification | ❌ PENDING |
| 10 | 20260114000006 | add_severity_scoring | ❌ PENDING |
| 11 | 20260114000007 | create_matter_query_history | ❌ PENDING* |
| 12 | 20260114000008 | add_archived_session_memory_type | ❌ PENDING |
| 13 | 20260114000009 | create_finding_verifications_table | ❌ PENDING* |
| 14 | 20260115000001 | security_and_indexing_fixes | ❌ PENDING |
| 15 | 20260115000002 | add_documents_soft_delete | ❌ PENDING |
| 16 | 20260116000001 | create_summary_verification_tables | ❌ PENDING* |
| 17 | 20260116000002 | create_activities_table | ❌ PENDING* |
| 18 | 20260116000003 | create_summary_edits_table | ❌ PENDING* |

> **\* DRIFT DETECTED**: Table exists in live DB but migration not tracked in `schema_migrations`

### 1.3 Schema Drift Analysis

The following tables exist in the live database but their creation is NOT tracked in `schema_migrations`:

| Table | Expected Migration | Exists in DB |
|-------|-------------------|--------------|
| entity_mentions | 20260112000001 | ✅ YES |
| alias_corrections | 20260113000001 | ✅ YES |
| processing_jobs | 20260114000001 | ✅ YES |
| job_stage_history | 20260114000001 | ✅ YES |
| anomalies | 20260114000003 | ✅ YES |
| statement_comparisons | 20260114000004 | ✅ YES |
| matter_query_history | 20260114000007 | ✅ YES |
| finding_verifications | 20260114000009 | ✅ YES |
| summary_verifications | 20260116000001 | ✅ YES |
| summary_notes | 20260116000001 | ✅ YES |
| activities | 20260116000002 | ✅ YES |
| summary_edits | 20260116000003 | ✅ YES |

**Root Cause**: Tables were likely created via direct SQL or Supabase Dashboard without using `supabase db push` or the migration system.

---

## 2. Table-to-Code Mapping Matrix

### 2.1 Complete Mapping

| DB Table | Backend Model | Backend File | Frontend Type | Frontend File | API Routes |
|----------|---------------|--------------|---------------|---------------|------------|
| `users` | - | - | - | - | auth.users (Supabase) |
| `matters` | `Matter` | [matter.py](backend/app/models/matter.py) | `Matter` | [matter.ts](frontend/src/types/matter.ts) | `/api/matters/*` |
| `matter_attorneys` | `MatterMember` | [matter.py](backend/app/models/matter.py) | `MatterMember` | [matter.ts](frontend/src/types/matter.ts) | `/api/matters/{id}/members` |
| `documents` | `Document` | [document.py](backend/app/models/document.py) | `Document` | [document.ts](frontend/src/types/document.ts) | `/api/documents/*` |
| `chunks` | `Chunk` | [chunk.py](backend/app/models/chunk.py) | `Chunk` | [document.ts](frontend/src/types/document.ts) | `/api/documents/{id}/chunks` |
| `bounding_boxes` | - | - | `BoundingBox` | [document.ts](frontend/src/types/document.ts) | `/api/bounding-boxes/*` |
| `findings` | `Finding` | [citation.py](backend/app/models/citation.py) | - | - | - |
| `matter_memory` | - | [memory.py](backend/app/models/memory.py) | - | - | internal |
| `citations` | `Citation` | [citation.py](backend/app/models/citation.py) | `Citation` | [citation.ts](frontend/src/types/citation.ts) | `/api/matters/{id}/citations` |
| `act_resolutions` | `ActResolution` | [citation.py](backend/app/models/citation.py) | `ActResolution` | [citation.ts](frontend/src/types/citation.ts) | `/api/matters/{id}/citations/acts/*` |
| `events` | `RawEvent`, `ClassifiedEvent` | [timeline.py](backend/app/models/timeline.py) | `TimelineEvent` | [timeline.ts](frontend/src/types/timeline.ts) | `/api/matters/{id}/timeline` |
| `identity_nodes` | `EntityNode` | [entity.py](backend/app/models/entity.py) | `Entity` | [entity.ts](frontend/src/types/entity.ts) | `/api/matters/{id}/entities` |
| `identity_edges` | `EntityEdge` | [entity.py](backend/app/models/entity.py) | `EntityEdge` | [entity.ts](frontend/src/types/entity.ts) | `/api/matters/{id}/entities/relationships` |
| `entity_mentions` | `EntityMention` | [entity.py](backend/app/models/entity.py) | `EntityMention` | [entity.ts](frontend/src/types/entity.ts) | `/api/matters/{id}/entities/{id}/mentions` |
| `alias_corrections` | - | - | - | - | `/api/matters/{id}/entities/corrections` |
| `audit_logs` | - | - | - | - | internal |
| `ocr_validation_log` | - | [ocr_validation.py](backend/app/models/ocr_validation.py) | - | - | internal |
| `ocr_human_review` | - | [ocr_validation.py](backend/app/models/ocr_validation.py) | - | - | `/api/documents/{id}/ocr-review` |
| `processing_jobs` | `ProcessingJob` | [job.py](backend/app/models/job.py) | `ProcessingJob` | [job.ts](frontend/src/types/job.ts) | `/api/matters/{id}/jobs` |
| `job_stage_history` | `JobStageHistory` | [job.py](backend/app/models/job.py) | `JobStageHistory` | [job.ts](frontend/src/types/job.ts) | `/api/jobs/{id}/stages` |
| `anomalies` | `Anomaly` | [anomaly.py](backend/app/models/anomaly.py) | - | - | `/api/matters/{id}/timeline/anomalies` |
| `statement_comparisons` | `StatementPairComparison` | [contradiction.py](backend/app/models/contradiction.py) | - | - | `/api/matters/{id}/contradictions` |
| `matter_query_history` | - | [memory.py](backend/app/models/memory.py) | - | - | internal |
| `finding_verifications` | `FindingVerification` | [verification.py](backend/app/models/verification.py) | `FindingVerification` | [verification.ts](frontend/src/types/verification.ts) | `/api/matters/{id}/verifications` |
| `summary_verifications` | `SummaryVerificationRecord` | [summary.py](backend/app/models/summary.py) | - | [summary.ts](frontend/src/types/summary.ts) | `/api/matters/{id}/summary/verifications` |
| `summary_notes` | `SummaryNoteRecord` | [summary.py](backend/app/models/summary.py) | - | [summary.ts](frontend/src/types/summary.ts) | `/api/matters/{id}/summary/notes` |
| `summary_edits` | `SummaryEditRecord` | [summary.py](backend/app/models/summary.py) | - | [summary.ts](frontend/src/types/summary.ts) | `/api/matters/{id}/summary/edits` |
| `activities` | `ActivityRecord` | [activity.py](backend/app/models/activity.py) | `Activity` | [activity.ts](frontend/src/types/activity.ts) | `/api/activities` |

---

## 3. Discrepancies Found

### 3.1 Name Mismatches (DB vs Code)

| DB Column (snake_case) | Code Property (camelCase) | Table | Severity |
|------------------------|---------------------------|-------|----------|
| `matter_id` | `matterId` | all tables | ✅ OK (expected transform) |
| `document_id` | `documentId` | multiple | ✅ OK (expected transform) |
| `source_node_id` | `sourceEntityId` | identity_edges | ⚠️ MISMATCH |
| `target_node_id` | `targetEntityId` | identity_edges | ⚠️ MISMATCH |
| `section` | `sectionNumber` | citations | ⚠️ MISMATCH |
| `event_date` | `eventDate` | events | ✅ OK |
| `source_bbox_ids` | `sourceBboxIds` | multiple | ✅ OK |

### 3.2 Type Mismatches

| Table | Column | DB Type | Backend Type | Frontend Type | Issue |
|-------|--------|---------|--------------|---------------|-------|
| `citations` | `section` | `text` | `section_number: str` | `sectionNumber: string` | Field name mismatch |
| `identity_edges` | `source_node_id` | `uuid` | `source_entity_id: str` | `sourceEntityId: string` | Field name mismatch |
| `identity_edges` | `target_node_id` | `uuid` | `target_entity_id: str` | `targetEntityId: string` | Field name mismatch |
| `events` | `event_date` | `date` | `event_date: date` | `eventDate: string` | Type: date vs string |
| `statement_comparisons` | `confidence` | `numeric` | `confidence: float` | - | Precision difference |
| `processing_jobs` | `metadata` | `jsonb` | `metadata: dict` | `metadata: Record<string, unknown>` | ✅ OK |

### 3.3 Nullable Mismatches

| Table | Column | DB Nullable | Backend Nullable | Frontend Optional | Issue |
|-------|--------|-------------|------------------|-------------------|-------|
| `documents` | `page_count` | YES | YES (`int \| None`) | YES (`number \| null`) | ✅ OK |
| `citations` | `quoted_text` | YES | YES | YES | ✅ OK |
| `events` | `document_id` | YES | YES | YES | ✅ OK |
| `findings` | `verified_by` | YES | YES | - | ✅ OK |
| `activities` | `matter_id` | YES | YES | YES | ✅ OK |

### 3.4 Orphaned Entities

#### Tables in DB with NO code references:
| Table | Status | Notes |
|-------|--------|-------|
| `audit_logs` | ⚠️ Orphaned | No backend/frontend model - internal logging only |

#### Code models with NO corresponding DB table:
| Model | File | Status | Notes |
|-------|------|--------|-------|
| `ExportRecord` | [export.py](backend/app/models/export.py) | ❓ Check | May use file storage, not DB |

---

## 4. Detailed Column Analysis by Table

### 4.1 `matters` Table

| DB Column | DB Type | Nullable | Backend | Frontend |
|-----------|---------|----------|---------|----------|
| id | uuid | NO | `id: str` | `id: string` |
| title | text | NO | `title: str` | `title: string` |
| description | text | YES | `description: str \| None` | `description: string \| null` |
| status | text | NO | `status: MatterStatus` | `status: MatterStatus` |
| created_at | timestamptz | YES | `created_at: datetime` | `createdAt: string` |
| updated_at | timestamptz | YES | `updated_at: datetime` | `updatedAt: string` |
| deleted_at | timestamptz | YES | ✅ `deleted_at: datetime \| None` | ✅ `deletedAt: string \| null` |

> ✅ **FIXED (2026-01-16)**: `deleted_at` field added to both backend and frontend models

### 4.2 `documents` Table

| DB Column | DB Type | Nullable | Backend | Frontend |
|-----------|---------|----------|---------|----------|
| id | uuid | NO | ✅ | ✅ |
| matter_id | uuid | NO | ✅ | ✅ |
| filename | text | NO | ✅ | ✅ |
| storage_path | text | NO | ✅ | ✅ |
| file_size | bigint | NO | ✅ `int` | ✅ `number` |
| page_count | integer | YES | ✅ | ✅ |
| document_type | text | NO | ✅ | ✅ |
| is_reference_material | boolean | YES | ✅ | ✅ |
| uploaded_by | uuid | NO | ✅ | ✅ |
| uploaded_at | timestamptz | YES | ✅ | ✅ |
| status | text | NO | ✅ | ✅ |
| extracted_text | text | YES | ✅ | ✅ |
| ocr_confidence | double precision | YES | ✅ | ✅ |
| ocr_quality_score | double precision | YES | ✅ | ✅ |
| ocr_error | text | YES | ✅ | ✅ |
| ocr_retry_count | integer | YES | ✅ `ocr_retry_count: int` | ✅ `ocrRetryCount: number` |
| validation_status | text | YES | ✅ `validation_status: str \| None` | ✅ `validationStatus: OCRValidationStatus \| null` |
| ocr_confidence_per_page | jsonb | YES | ✅ | ✅ |
| ocr_quality_status | text | YES | ✅ | ✅ |
| deleted_at | timestamptz | YES | ✅ `deleted_at: datetime \| None` | ✅ `deletedAt: string \| null` |

> ✅ **ALL FIXED (2026-01-16)**:
> - `ocr_retry_count` added to backend and frontend models
> - `validation_status` added to backend and frontend models
> - `deleted_at` added to backend and frontend models

### 4.3 `identity_edges` Table

| DB Column | DB Type | Backend Field | Issue |
|-----------|---------|---------------|-------|
| source_node_id | uuid | `source_entity_id` | ⚠️ NAME MISMATCH |
| target_node_id | uuid | `target_entity_id` | ⚠️ NAME MISMATCH |

---

## 5. Recommendations

### 5.1 Critical Actions - ✅ COMPLETED

1. ~~**Fix Migration Tracking**~~ ✅ DONE - All 37 migrations now tracked

2. ~~**Apply Remaining Migrations**~~ ✅ DONE - No pending migrations

3. ~~**Add Missing Fields to Code Models**~~ ✅ FIXED (2026-01-16)
   - ✅ `deleted_at` added to `Matter`, `Document` models
   - ✅ `ocr_retry_count`, `validation_status` added to `Document` model

### 5.2 High Priority - Intentional Design Decisions (No Action Needed)

4. **Field Name Mappings** - These are intentional transformations, not bugs:
   - `identity_edges`: DB `source_node_id`/`target_node_id` → Code `source_entity_id`/`target_entity_id`
   - `citations`: DB `section` → Code `section_number`
   - These mappings are handled by the data access layer

5. ~~**Add Soft Delete Support**~~ ✅ FIXED (2026-01-16)
   - ✅ Backend: `deleted_at` field added to models
   - Frontend already filters soft-deleted records via RLS
   - API already respects soft delete in queries

### 5.3 Medium Priority

6. **Create Missing Frontend Types**
   - `Anomaly` type for timeline anomalies
   - `StatementComparison` type for contradictions

7. **Document Table Purposes**
   - Add comments to `audit_logs` explaining its internal-only use

### 5.4 Best Practices Going Forward

8. **Always use migration system**
   ```bash
   # Create new migration
   supabase migration new my_feature

   # Apply migrations
   supabase db push
   ```

9. **Sync types automatically**
   - Consider using Supabase's `supabase gen types typescript` to auto-generate frontend types

---

## 6. Appendix

### A. Live Database Tables (28 total)

```
act_resolutions      activities           alias_corrections
anomalies            audit_logs           bounding_boxes
chunks               citations            documents
entity_mentions      events               finding_verifications
findings             identity_edges       identity_nodes
job_stage_history    matter_attorneys     matter_memory
matter_query_history matters              ocr_human_review
ocr_validation_log   processing_jobs      statement_comparisons
summary_edits        summary_notes        summary_verifications
users
```

### B. Local Migration Files (37 total)

```
20260104000000_create_users_table.sql
20260105000001_create_matters_table.sql
20260105000002_create_matter_attorneys_table.sql
20260106000001_create_documents_table.sql
20260106000002_create_chunks_table.sql
20260106000003_create_bounding_boxes_table.sql
20260106000004_create_findings_table.sql
20260106000005_create_matter_memory_table.sql
20260106000006_create_citations_table.sql
20260106000007_create_act_resolutions_table.sql
20260106000008_create_events_table.sql
20260106000009_create_mig_tables.sql
20260106000010_create_storage_policies.sql
20260106000011_create_audit_logs_table.sql
20260107000001_fix_matter_attorneys_rls_recursion.sql
20260107000002_add_ocr_columns_to_documents.sql
20260108000001_create_ocr_validation_tables.sql
20260108000002_add_ocr_quality_columns.sql
20260108000003_add_bbox_reading_order.sql
20260108000004_add_hybrid_search.sql
20260112000001_create_entity_mentions_table.sql
20260112000002_add_entity_type_constraint.sql
20260113000001_create_alias_corrections_table.sql
20260114000001_create_processing_jobs_table.sql
20260114000002_enhance_citations_table.sql
20260114000003_create_anomalies_table.sql
20260114000004_create_statement_comparisons_table.sql
20260114000005_add_contradiction_classification.sql
20260114000006_add_severity_scoring.sql
20260114000007_create_matter_query_history.sql
20260114000008_add_archived_session_memory_type.sql
20260114000009_create_finding_verifications_table.sql
20260115000001_security_and_indexing_fixes.sql
20260115000002_add_documents_soft_delete.sql
20260116000001_create_summary_verification_tables.sql
20260116000002_create_activities_table.sql
20260116000003_create_summary_edits_table.sql
```

---

*Report generated by Supabase Schema Audit Tool*
