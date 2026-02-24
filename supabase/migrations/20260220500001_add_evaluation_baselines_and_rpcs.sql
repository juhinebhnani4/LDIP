-- Migration: Evaluation Baselines + Quality Monitoring RPC Functions
-- Gap 9: Automated RAGAS Regression — Baseline tracking, trend analysis, quality alerts
--
-- This migration adds:
-- 1. evaluation_baselines table — stores known-good score snapshots per matter
-- 2. get_evaluation_trends() — daily score aggregation for trend analysis
-- 3. get_evaluation_quality_summary() — admin dashboard: per-matter quality + alerts
--
-- IMPORTANT: Baselines are the anchor for regression detection. A batch eval run
-- is compared against the active baseline to detect quality drops. Without baselines,
-- there's no reference point and no regression detection.

-- =============================================================================
-- 1. evaluation_baselines table
-- =============================================================================

CREATE TABLE IF NOT EXISTS evaluation_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,

    -- Snapshot of aggregate scores at baseline time
    avg_overall FLOAT NOT NULL CHECK (avg_overall >= 0.0 AND avg_overall <= 1.0),
    avg_faithfulness FLOAT CHECK (avg_faithfulness >= 0.0 AND avg_faithfulness <= 1.0),
    avg_relevancy FLOAT CHECK (avg_relevancy >= 0.0 AND avg_relevancy <= 1.0),
    avg_recall FLOAT CHECK (avg_recall >= 0.0 AND avg_recall <= 1.0),

    -- Per-item scores for granular regression detection
    -- Structure: { "golden_item_id": {"overall": 0.85, "faithfulness": 0.9, ...}, ... }
    -- This enables per-question regression detection, not just aggregate comparison
    per_item_scores JSONB NOT NULL DEFAULT '{}',

    -- Traceability
    total_items INTEGER NOT NULL DEFAULT 0,
    successful_items INTEGER NOT NULL DEFAULT 0,
    promoted_from_job_id TEXT,              -- Celery task ID of the batch run that was promoted
    pipeline_config JSONB NOT NULL DEFAULT '{}',  -- RAG config snapshot at baseline time
    created_by TEXT,                        -- 'system' for auto-promote, user_id for manual
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Soft-active flag: only the latest baseline per matter is used for comparison
    -- Older baselines are kept for historical reference (never deleted)
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Only one active baseline per matter (enforced via partial unique index)
CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluation_baselines_active_matter
    ON evaluation_baselines(matter_id)
    WHERE is_active = TRUE;

-- Query baselines by matter (all, including inactive for history)
CREATE INDEX IF NOT EXISTS idx_evaluation_baselines_matter
    ON evaluation_baselines(matter_id, created_at DESC);

-- Find baseline from a specific batch job
CREATE INDEX IF NOT EXISTS idx_evaluation_baselines_job
    ON evaluation_baselines(promoted_from_job_id)
    WHERE promoted_from_job_id IS NOT NULL;

COMMENT ON TABLE evaluation_baselines IS 'Known-good score snapshots per matter. Active baseline is the reference for regression detection.';
COMMENT ON COLUMN evaluation_baselines.per_item_scores IS 'Per golden item scores. Enables per-question regression detection, not just aggregate.';
COMMENT ON COLUMN evaluation_baselines.is_active IS 'Only one active baseline per matter. Creating a new baseline deactivates the previous one.';

-- RLS: Same pattern as evaluation_results — matter isolation
ALTER TABLE evaluation_baselines ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view baselines in their matters"
    ON evaluation_baselines FOR SELECT
    USING (
        matter_id IN (
            SELECT ma.matter_id FROM matter_attorneys ma
            WHERE ma.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role has full access to baselines"
    ON evaluation_baselines FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Grant to service_role (admin operations go through service key)
GRANT ALL ON evaluation_baselines TO service_role;
GRANT SELECT ON evaluation_baselines TO authenticated;

-- =============================================================================
-- 2. get_evaluation_trends() — Daily score aggregation for trend charts
-- =============================================================================
-- Returns one row per day with averaged scores for a specific matter.
-- Used by frontend to render score trend lines over time.

CREATE OR REPLACE FUNCTION get_evaluation_trends(
    p_matter_id UUID,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    eval_date DATE,
    avg_overall FLOAT,
    avg_faithfulness FLOAT,
    avg_relevancy FLOAT,
    avg_recall FLOAT,
    eval_count INTEGER,
    triggered_by TEXT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT
        DATE(er.evaluated_at) AS eval_date,
        ROUND(AVG(er.overall_score)::NUMERIC, 4)::FLOAT AS avg_overall,
        ROUND(AVG(er.faithfulness)::NUMERIC, 4)::FLOAT AS avg_faithfulness,
        ROUND(AVG(er.answer_relevancy)::NUMERIC, 4)::FLOAT AS avg_relevancy,
        ROUND(AVG(er.context_recall)::NUMERIC, 4)::FLOAT AS avg_recall,
        COUNT(*)::INTEGER AS eval_count,
        -- Most common trigger type that day (useful for understanding data source)
        MODE() WITHIN GROUP (ORDER BY er.triggered_by) AS triggered_by
    FROM evaluation_results er
    WHERE er.matter_id = p_matter_id
      AND er.evaluated_at >= (NOW() - (GREATEST(p_days, 1) || ' days')::INTERVAL)
    GROUP BY DATE(er.evaluated_at)
    ORDER BY eval_date DESC;
$$;

COMMENT ON FUNCTION get_evaluation_trends IS 'Daily aggregated evaluation scores for trend analysis. Gap 9: Automated RAGAS Regression.';

GRANT EXECUTE ON FUNCTION get_evaluation_trends TO service_role;
GRANT EXECUTE ON FUNCTION get_evaluation_trends TO authenticated;

-- =============================================================================
-- 3. get_evaluation_quality_summary() — Admin dashboard global view
-- =============================================================================
-- Returns per-matter quality summary: latest batch scores, baseline comparison,
-- alert flags. Used by admin dashboard QualityMetricsWidget.
--
-- Returns one row per matter that has evaluation data (golden dataset + results).

CREATE OR REPLACE FUNCTION get_evaluation_quality_summary()
RETURNS TABLE (
    matter_id UUID,
    matter_title TEXT,
    -- Latest batch evaluation scores
    latest_overall FLOAT,
    latest_faithfulness FLOAT,
    latest_relevancy FLOAT,
    latest_recall FLOAT,
    latest_eval_date TIMESTAMPTZ,
    latest_job_id TEXT,
    latest_eval_count INTEGER,
    -- Active baseline scores (NULL if no baseline)
    baseline_overall FLOAT,
    baseline_date TIMESTAMPTZ,
    baseline_item_count INTEGER,
    -- Golden dataset info
    golden_item_count BIGINT,
    -- Regression detection (simple: latest vs baseline)
    overall_delta FLOAT,  -- negative = regression
    has_regression BOOLEAN,
    -- Eval frequency
    total_evals_30d INTEGER,
    last_eval_age_hours FLOAT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    WITH matters_with_golden AS (
        -- Only include matters that have golden dataset items (evaluation-ready)
        SELECT
            gd.matter_id,
            m.title AS matter_title,
            COUNT(gd.id) AS golden_item_count
        FROM golden_dataset gd
        JOIN matters m ON m.id = gd.matter_id
        WHERE m.deleted_at IS NULL
        GROUP BY gd.matter_id, m.title
    ),
    latest_batch AS (
        -- Most recent batch evaluation per matter (by job_id grouping)
        SELECT DISTINCT ON (er.matter_id)
            er.matter_id,
            er.job_id AS latest_job_id,
            er.evaluated_at AS latest_eval_date
        FROM evaluation_results er
        WHERE er.triggered_by = 'batch'
          AND er.job_id IS NOT NULL
        ORDER BY er.matter_id, er.evaluated_at DESC
    ),
    latest_batch_scores AS (
        -- Aggregate scores for the latest batch job
        SELECT
            lb.matter_id,
            lb.latest_job_id,
            lb.latest_eval_date,
            ROUND(AVG(er.overall_score)::NUMERIC, 4)::FLOAT AS latest_overall,
            ROUND(AVG(er.faithfulness)::NUMERIC, 4)::FLOAT AS latest_faithfulness,
            ROUND(AVG(er.answer_relevancy)::NUMERIC, 4)::FLOAT AS latest_relevancy,
            ROUND(AVG(er.context_recall)::NUMERIC, 4)::FLOAT AS latest_recall,
            COUNT(*)::INTEGER AS latest_eval_count
        FROM latest_batch lb
        JOIN evaluation_results er
            ON er.matter_id = lb.matter_id
           AND er.job_id = lb.latest_job_id
        GROUP BY lb.matter_id, lb.latest_job_id, lb.latest_eval_date
    ),
    active_baselines AS (
        SELECT
            eb.matter_id,
            eb.avg_overall AS baseline_overall,
            eb.created_at AS baseline_date,
            eb.total_items AS baseline_item_count
        FROM evaluation_baselines eb
        WHERE eb.is_active = TRUE
    ),
    eval_frequency AS (
        -- Count evaluations in last 30 days per matter
        SELECT
            er.matter_id,
            COUNT(*)::INTEGER AS total_evals_30d,
            ROUND(
                EXTRACT(EPOCH FROM (NOW() - MAX(er.evaluated_at))) / 3600.0
            , 1)::FLOAT AS last_eval_age_hours
        FROM evaluation_results er
        WHERE er.evaluated_at >= (NOW() - INTERVAL '30 days')
        GROUP BY er.matter_id
    )
    SELECT
        mg.matter_id,
        mg.matter_title,
        -- Latest scores
        lbs.latest_overall,
        lbs.latest_faithfulness,
        lbs.latest_relevancy,
        lbs.latest_recall,
        lbs.latest_eval_date,
        lbs.latest_job_id,
        lbs.latest_eval_count,
        -- Baseline
        ab.baseline_overall,
        ab.baseline_date,
        ab.baseline_item_count,
        -- Golden dataset
        mg.golden_item_count,
        -- Regression: delta and flag (> 10% drop = regression)
        CASE
            WHEN ab.baseline_overall IS NOT NULL AND lbs.latest_overall IS NOT NULL
            THEN ROUND((lbs.latest_overall - ab.baseline_overall)::NUMERIC, 4)::FLOAT
            ELSE NULL
        END AS overall_delta,
        CASE
            WHEN ab.baseline_overall IS NOT NULL AND lbs.latest_overall IS NOT NULL
            THEN lbs.latest_overall < (ab.baseline_overall * 0.90)  -- 10% relative drop
            ELSE FALSE
        END AS has_regression,
        -- Frequency
        COALESCE(ef.total_evals_30d, 0) AS total_evals_30d,
        ef.last_eval_age_hours
    FROM matters_with_golden mg
    LEFT JOIN latest_batch_scores lbs ON lbs.matter_id = mg.matter_id
    LEFT JOIN active_baselines ab ON ab.matter_id = mg.matter_id
    LEFT JOIN eval_frequency ef ON ef.matter_id = mg.matter_id
    ORDER BY mg.matter_title;
$$;

COMMENT ON FUNCTION get_evaluation_quality_summary IS 'Admin dashboard: per-matter quality summary with baseline comparison and regression alerts. Gap 9.';

GRANT EXECUTE ON FUNCTION get_evaluation_quality_summary TO service_role;
