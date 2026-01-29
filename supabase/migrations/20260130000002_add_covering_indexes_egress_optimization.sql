-- ============================================================================
-- COVERING INDEXES FOR EGRESS OPTIMIZATION
-- ============================================================================
-- Based on PostgreSQL covering index best practices (INCLUDE keyword)
-- These indexes include commonly-selected columns to avoid table lookups
-- Reference: https://www.postgresql.org/docs/current/indexes-index-only-scans.html
--
-- IMPORTANT: This migration works in conjunction with selective column queries
-- in the application code. The following files have been optimized:
--   - backend/app/services/job_tracking/tracker.py (JOB_LIST_COLUMNS, JOB_LIST_ITEM_COLUMNS)
--   - backend/app/engines/citation/storage.py (CITATION_LIST_COLUMNS, CITATION_STATS_COLUMNS)
--   - backend/app/services/bounding_box_service.py (BBOX_COLUMNS_NO_TEXT - already optimized)
-- ============================================================================

-- ============================================================================
-- CITATIONS TABLE (High egress due to Python-side filtering)
-- ============================================================================
-- Matches CITATION_LIST_COLUMNS in storage.py (excludes quoted_text, raw_citation_text, extraction_metadata)

-- Covering index for get_citations_by_document queries
-- NOTE: Cannot include 'quoted_text', 'source_bbox_ids' (array) - may be too large for B-tree
DROP INDEX IF EXISTS idx_citations_doc_covering;
CREATE INDEX idx_citations_doc_covering ON public.citations(source_document_id, matter_id)
INCLUDE (id, act_name, act_name_original, section, subsection, clause, source_page, verification_status, confidence, created_at, updated_at);

-- Covering index for get_citations_by_matter queries with filtering
DROP INDEX IF EXISTS idx_citations_matter_covering;
CREATE INDEX idx_citations_matter_covering ON public.citations(matter_id, verification_status)
INCLUDE (id, act_name, act_name_original, section, subsection, clause, source_document_id, source_page, confidence, created_at, updated_at);

-- Covering index for act aggregation query (get_act_verification_stats)
DROP INDEX IF EXISTS idx_citations_act_stats_covering;
CREATE INDEX idx_citations_act_stats_covering ON public.citations(matter_id)
INCLUDE (act_name, verification_status);

-- ============================================================================
-- BOUNDING_BOXES TABLE (89 MB - Largest table, high egress)
-- ============================================================================
-- NOTE: Cannot include 'text' column - too large for B-tree index (max 2704 bytes)
-- The text column must be fetched from the table, but coordinates can be index-only

-- Covering index for page-based bbox retrieval (document viewer) - coordinates only
DROP INDEX IF EXISTS idx_bboxes_page_covering;
CREATE INDEX idx_bboxes_page_covering ON public.bounding_boxes(document_id, page_number)
INCLUDE (id, x, y, width, height, reading_order_index, confidence);

-- Covering index for matter-level bbox queries - metadata only
DROP INDEX IF EXISTS idx_bboxes_matter_covering;
CREATE INDEX idx_bboxes_matter_covering ON public.bounding_boxes(matter_id, document_id)
INCLUDE (id, page_number, confidence);

-- ============================================================================
-- CHUNKS TABLE (31 MB - Second largest, used in RAG/search)
-- ============================================================================
-- NOTE: Cannot include 'content' column - text too large for B-tree index

-- Covering index for document chunks (non-vector queries) - metadata only
DROP INDEX IF EXISTS idx_chunks_doc_covering;
CREATE INDEX idx_chunks_doc_covering ON public.chunks(document_id, chunk_index)
INCLUDE (id, matter_id, chunk_type, page_number, token_count, created_at);

-- Covering index for matter chunks listing
DROP INDEX IF EXISTS idx_chunks_matter_covering;
CREATE INDEX idx_chunks_matter_covering ON public.chunks(matter_id, document_id)
INCLUDE (id, chunk_type, page_number, token_count, created_at);

-- ============================================================================
-- ENTITY_MENTIONS TABLE (8.7 MB - Joins heavily with identity_nodes)
-- ============================================================================

-- Covering index for entity lookups
-- NOTE: Cannot include 'mention_text' or 'context' - may be too large
DROP INDEX IF EXISTS idx_entity_mentions_covering;
CREATE INDEX idx_entity_mentions_covering ON public.entity_mentions(entity_id, document_id)
INCLUDE (id, chunk_id, page_number, confidence, created_at);

-- Covering index for document-based entity queries
DROP INDEX IF EXISTS idx_entity_mentions_doc_covering;
CREATE INDEX idx_entity_mentions_doc_covering ON public.entity_mentions(document_id, page_number)
INCLUDE (id, entity_id, chunk_id, confidence);

-- ============================================================================
-- EVENTS TABLE (7.8 MB - Timeline queries)
-- ============================================================================
-- NOTE: Cannot include 'description' or 'entities_involved' - may be too large

-- Covering index for timeline queries - metadata only
DROP INDEX IF EXISTS idx_events_timeline_covering;
CREATE INDEX idx_events_timeline_covering ON public.events(matter_id, event_date)
INCLUDE (id, event_type, document_id, is_manual, event_date_precision, created_at);

-- ============================================================================
-- DOCUMENTS TABLE (3.3 MB - Frequently queried)
-- ============================================================================

-- Covering index for document listings
DROP INDEX IF EXISTS idx_documents_list_covering;
CREATE INDEX idx_documents_list_covering ON public.documents(matter_id, status)
INCLUDE (id, filename, document_type, file_size, page_count, uploaded_at, uploaded_by)
WHERE deleted_at IS NULL;

-- ============================================================================
-- PROCESSING_JOBS TABLE (Polled every 5 seconds!)
-- ============================================================================
-- Matches JOB_LIST_COLUMNS and JOB_LIST_ITEM_COLUMNS in tracker.py

-- Covering index for job status polling (reduces polling egress dramatically)
-- NOTE: Cannot include 'error_message', 'metadata' - may be too large
-- IMPORTANT: Column order is (matter_id, status) for matter-scoped queries
DROP INDEX IF EXISTS idx_jobs_polling_covering;
CREATE INDEX idx_jobs_polling_covering ON public.processing_jobs(matter_id, status)
INCLUDE (id, document_id, job_type, progress_pct, current_stage, retry_count, max_retries,
         celery_task_id, started_at, completed_at, created_at, updated_at, estimated_completion);

-- Additional covering index for document-level job queries
DROP INDEX IF EXISTS idx_jobs_document_covering;
CREATE INDEX idx_jobs_document_covering ON public.processing_jobs(document_id, status)
INCLUDE (id, matter_id, job_type, progress_pct, current_stage, retry_count, created_at, updated_at);

-- ============================================================================
-- ACTIVITIES TABLE (User feeds)
-- ============================================================================

-- Covering index for activity feeds
-- NOTE: Cannot include 'description' or 'metadata' - may be too large
DROP INDEX IF EXISTS idx_activities_feed_covering;
CREATE INDEX idx_activities_feed_covering ON public.activities(user_id, created_at DESC)
INCLUDE (id, type, matter_id, is_read);

-- ============================================================================
-- IDENTITY_NODES TABLE (Entity resolution)
-- ============================================================================

-- Covering index for entity listings
-- NOTE: Cannot include 'aliases' or 'metadata' - JSONB may be too large
DROP INDEX IF EXISTS idx_identity_nodes_list_covering;
CREATE INDEX idx_identity_nodes_list_covering ON public.identity_nodes(matter_id, entity_type)
INCLUDE (id, canonical_name, mention_count, created_at)
WHERE merged_into_id IS NULL;

-- ============================================================================
-- ANALYZE TABLES TO UPDATE STATISTICS
-- ============================================================================

ANALYZE public.citations;
ANALYZE public.bounding_boxes;
ANALYZE public.chunks;
ANALYZE public.entity_mentions;
ANALYZE public.events;
ANALYZE public.documents;
ANALYZE public.processing_jobs;
ANALYZE public.activities;
ANALYZE public.identity_nodes;

-- ============================================================================
-- NOTES:
-- ============================================================================
-- 1. Covering indexes use more storage but dramatically reduce egress
-- 2. The INCLUDE columns are stored in the index but NOT used for searching
-- 3. This enables "index-only scans" - data served directly from index
-- 4. Run EXPLAIN ANALYZE on your queries to verify index-only scans
-- 5. Estimate: These indexes may add ~50-100MB storage but save GBs of egress
-- ============================================================================
