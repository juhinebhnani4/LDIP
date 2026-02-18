-- Migration: Create unit economics views for cost-per-page and monthly COGS
-- Purpose: Foundation for pricing decisions and per-matter profitability analysis
--
-- Two materialized views:
--   1. cost_per_document_page — What does it cost to process one page?
--   2. monthly_cogs_by_matter — What does each matter cost us per month?
--
-- Both are materialized for dashboard performance. Refresh via:
--   REFRESH MATERIALIZED VIEW CONCURRENTLY public.cost_per_document_page;
--   REFRESH MATERIALIZED VIEW CONCURRENTLY public.monthly_cogs_by_matter;

-- =============================================================================
-- VIEW 1: cost_per_document_page
-- =============================================================================
-- Answers: "What is our cost-per-page for document processing?"
-- This is the fundamental unit for pricing document ingestion.
--
-- Only includes completed documents with known page counts.
-- Breaks down costs into: OCR, Gemini (entities/citations/timeline), OpenAI
-- (embeddings/contradictions), and Cohere (reranking during ingestion queries).

CREATE MATERIALIZED VIEW public.cost_per_document_page AS
SELECT
    d.id AS document_id,
    d.matter_id,
    d.filename,
    d.document_type,
    d.page_count,
    d.status AS document_status,
    d.processing_completed_at,

    -- Total cost for this document
    COALESCE(SUM(c.total_cost_usd), 0) AS total_cost_usd,
    COALESCE(SUM(c.total_cost_inr), 0) AS total_cost_inr,

    -- Cost per page (the key metric)
    CASE
        WHEN d.page_count > 0
        THEN ROUND(COALESCE(SUM(c.total_cost_usd), 0) / d.page_count, 6)
        ELSE NULL
    END AS cost_per_page_usd,
    CASE
        WHEN d.page_count > 0
        THEN ROUND(COALESCE(SUM(c.total_cost_inr), 0) / d.page_count, 4)
        ELSE NULL
    END AS cost_per_page_inr,

    -- Breakdown by cost category
    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.operation = 'ocr_document_ai'
    ), 0) AS ocr_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider = 'gemini-2.5-flash'
    ), 0) AS gemini_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider IN ('gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo-preview')
    ), 0) AS openai_llm_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider = 'text-embedding-3-small'
    ), 0) AS embedding_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider = 'rerank-v3.5'
    ), 0) AS rerank_cost_usd,

    -- Token totals
    COALESCE(SUM(c.input_tokens), 0) AS total_input_tokens,
    COALESCE(SUM(c.output_tokens), 0) AS total_output_tokens,

    -- API call count
    COUNT(c.id) AS api_call_count

FROM public.documents d
LEFT JOIN public.llm_costs c ON c.document_id = d.id
WHERE d.page_count IS NOT NULL
  AND d.page_count > 0
  AND d.status = 'completed'
GROUP BY d.id, d.matter_id, d.filename, d.document_type,
         d.page_count, d.status, d.processing_completed_at
WITH NO DATA;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_cost_per_doc_page_doc_id
ON public.cost_per_document_page(document_id);

-- Query patterns: filter by matter, sort by cost
CREATE INDEX idx_cost_per_doc_page_matter
ON public.cost_per_document_page(matter_id);

CREATE INDEX idx_cost_per_doc_page_cpp
ON public.cost_per_document_page(cost_per_page_usd DESC NULLS LAST);

COMMENT ON MATERIALIZED VIEW public.cost_per_document_page IS
    'Unit economics: cost breakdown per document page. Refresh after ingestion completes.';


-- =============================================================================
-- VIEW 2: monthly_cogs_by_matter
-- =============================================================================
-- Answers: "What does each matter cost us per month?"
-- This is the foundation for per-customer profitability.
--
-- Includes ALL costs (ingestion + query), broken down by:
--   - Cost category (OCR, Gemini, OpenAI LLM, Embeddings, Rerank)
--   - Ingestion vs query split
--   - Document and query volume

CREATE MATERIALIZED VIEW public.monthly_cogs_by_matter AS
SELECT
    DATE_TRUNC('month', c.created_at)::DATE AS month,
    c.matter_id,
    m.title AS matter_title,

    -- Total COGS
    SUM(c.total_cost_usd) AS total_cogs_usd,
    SUM(c.total_cost_inr) AS total_cogs_inr,

    -- Ingestion vs Query split
    -- Ingestion operations: everything document-processing related
    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.operation IN (
            'ocr_document_ai', 'ocr_validation',
            'entity_extraction', 'entity_extraction_batch',
            'entity_alias_resolution', 'entity_alias_resolution_batch',
            'citation_extraction', 'citation_extraction_batch', 'citation_extraction_sync',
            'citation_verification', 'citation_act_validation',
            'date_extraction', 'date_extraction_sync',
            'event_classification', 'timeline_entity_linking',
            'contradiction_screening', 'contradiction_comparison', 'contradiction_classification',
            'summary_subject_matter', 'summary_subject_matter_retry',
            'summary_key_issues', 'summary_current_status',
            'security_injection_scan', 'embedding_batch'
        )
    ), 0) AS ingestion_cost_usd,

    -- Query operations: per-user-chat costs
    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.operation IN (
            'intent_classification', 'multi_intent_refine',
            'query_rewrite', 'conversation_summarization',
            'embedding_single', 'search_rerank',
            'rag_generation',
            'safety_subtle_detection', 'safety_language_policing'
        )
    ), 0) AS query_cost_usd,

    -- Cost by provider category
    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.operation = 'ocr_document_ai'
    ), 0) AS ocr_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider = 'gemini-2.5-flash'
    ), 0) AS gemini_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider IN ('gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo', 'gpt-4-turbo-preview')
    ), 0) AS openai_llm_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider = 'text-embedding-3-small'
    ), 0) AS embedding_cost_usd,

    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.provider = 'rerank-v3.5'
    ), 0) AS rerank_cost_usd,

    -- Volume metrics
    COUNT(DISTINCT c.document_id) FILTER (
        WHERE c.document_id IS NOT NULL
    ) AS documents_processed,

    -- Approximate query count (distinct correlation IDs)
    COUNT(DISTINCT c.metadata->>'correlation_id') FILTER (
        WHERE c.metadata->>'correlation_id' IS NOT NULL
    ) AS query_count,

    -- Total API calls
    COUNT(c.id) AS total_api_calls,

    -- Token totals
    SUM(c.input_tokens) AS total_input_tokens,
    SUM(c.output_tokens) AS total_output_tokens

FROM public.llm_costs c
LEFT JOIN public.matters m ON m.id = c.matter_id
WHERE c.matter_id IS NOT NULL
GROUP BY DATE_TRUNC('month', c.created_at)::DATE, c.matter_id, m.title
WITH NO DATA;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_monthly_cogs_matter_month
ON public.monthly_cogs_by_matter(matter_id, month);

-- Query patterns: filter by month, sort by cost
CREATE INDEX idx_monthly_cogs_month
ON public.monthly_cogs_by_matter(month DESC);

CREATE INDEX idx_monthly_cogs_total
ON public.monthly_cogs_by_matter(total_cogs_usd DESC NULLS LAST);

COMMENT ON MATERIALIZED VIEW public.monthly_cogs_by_matter IS
    'Unit economics: monthly COGS per matter with ingestion/query split. Refresh daily or after batch processing.';


-- =============================================================================
-- HELPER: Refresh function (call from Celery beat or manual trigger)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.refresh_unit_economics_views()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.cost_per_document_page;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.monthly_cogs_by_matter;
END;
$$;

COMMENT ON FUNCTION public.refresh_unit_economics_views IS
    'Refresh both unit economics materialized views. Call daily or after batch ingestion.';


-- =============================================================================
-- Initial data population
-- =============================================================================
-- Populate with existing data (non-concurrent since first time)
REFRESH MATERIALIZED VIEW public.cost_per_document_page;
REFRESH MATERIALIZED VIEW public.monthly_cogs_by_matter;
