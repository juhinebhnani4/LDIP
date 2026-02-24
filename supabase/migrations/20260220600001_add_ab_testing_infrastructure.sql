-- =============================================================================
-- Migration: Add A/B Testing Infrastructure for Voyage Provider Comparison
-- Gap 10: Automated Voyage A/B Testing
-- Date: 2026-02-20
--
-- Creates the ab_test_runs table to track provider comparison experiments.
-- Each run evaluates the same golden dataset with two provider configurations
-- (control: OpenAI+Cohere vs treatment: Voyage+Voyage) and stores aggregated
-- scores, latency metrics, cost data, and automated decision outcomes.
--
-- Individual per-question results are stored in evaluation_results (existing table)
-- linked by job_id. This table stores experiment-level metadata and aggregated
-- comparison results for dashboard display and automated decision-making.
-- =============================================================================

-- 1. Create ab_test_runs table
CREATE TABLE IF NOT EXISTS ab_test_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES matters(id) ON DELETE CASCADE,

    -- Experiment status lifecycle:
    -- pending → running_control → running_treatment → comparing → completed
    -- Any state can transition to → failed or cancelled
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'running_control', 'running_treatment',
            'comparing', 'completed', 'failed', 'cancelled'
        )),

    -- Provider configurations (control = incumbent, treatment = challenger)
    control_embedding text NOT NULL DEFAULT 'openai',
    control_reranker text NOT NULL DEFAULT 'cohere',
    treatment_embedding text NOT NULL DEFAULT 'voyage',
    treatment_reranker text NOT NULL DEFAULT 'voyage',

    -- Links to evaluation_results via job_id (one batch eval job per arm)
    control_job_id text,
    treatment_job_id text,

    -- Aggregated RAGAS scores per arm
    -- Schema: {context_recall, faithfulness, answer_relevancy, overall, count}
    control_scores jsonb,
    treatment_scores jsonb,

    -- Latency percentiles per arm (milliseconds)
    control_latency_p50_ms integer,
    control_latency_p95_ms integer,
    treatment_latency_p50_ms integer,
    treatment_latency_p95_ms integer,

    -- Cost per arm (USD, from llm_costs aggregation)
    control_cost_usd numeric(10, 6) DEFAULT 0,
    treatment_cost_usd numeric(10, 6) DEFAULT 0,

    -- Automated decision
    decision text CHECK (decision IN (
        'control_wins', 'treatment_wins',
        'no_significant_difference', 'insufficient_data'
    )),
    decision_confidence float,
    decision_reasoning text,

    -- Statistical test results (Welch's t-test)
    -- Schema: {t_statistic, p_value, degrees_of_freedom, effect_size_cohens_d}
    statistical_test jsonb,

    -- Experiment metadata
    golden_item_count integer,
    tags text[] DEFAULT '{}',
    error_message text,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

-- 2. Enable RLS
ALTER TABLE ab_test_runs ENABLE ROW LEVEL SECURITY;

-- 3. RLS policies
-- Users can view experiments for matters they belong to
CREATE POLICY "ab_test_runs_select"
    ON ab_test_runs FOR SELECT
    USING (
        matter_id IN (
            SELECT matter_id FROM matter_attorneys WHERE user_id = auth.uid()
        )
    );

-- Users can insert experiments for matters they belong to
CREATE POLICY "ab_test_runs_insert"
    ON ab_test_runs FOR INSERT
    WITH CHECK (
        matter_id IN (
            SELECT matter_id FROM matter_attorneys WHERE user_id = auth.uid()
        )
    );

-- Service role bypasses RLS (for Celery tasks)
CREATE POLICY "ab_test_runs_service_role"
    ON ab_test_runs FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- 4. Indexes
CREATE INDEX idx_ab_test_runs_matter ON ab_test_runs(matter_id);
CREATE INDEX idx_ab_test_runs_status ON ab_test_runs(status);
CREATE INDEX idx_ab_test_runs_created ON ab_test_runs(created_at DESC);

-- 5. Grant permissions
GRANT SELECT, INSERT ON ab_test_runs TO authenticated;
GRANT ALL ON ab_test_runs TO service_role;

-- 6. Add provider tracking columns to evaluation_results
-- These allow per-result attribution of which provider produced the answer
ALTER TABLE evaluation_results
    ADD COLUMN IF NOT EXISTS embedding_provider text DEFAULT 'openai',
    ADD COLUMN IF NOT EXISTS rerank_provider text DEFAULT 'cohere',
    ADD COLUMN IF NOT EXISTS search_latency_ms integer;

-- 7. Index for fast provider-grouped queries on evaluation_results
CREATE INDEX IF NOT EXISTS idx_eval_results_provider
    ON evaluation_results(matter_id, embedding_provider, rerank_provider);

CREATE INDEX IF NOT EXISTS idx_eval_results_job_provider
    ON evaluation_results(job_id, embedding_provider);

-- 8. RPC: Aggregate evaluation scores by job_id for fast comparison
CREATE OR REPLACE FUNCTION get_ab_test_scores(p_job_id text)
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT jsonb_build_object(
        'count', COUNT(*)::int,
        'context_recall', ROUND(AVG(context_recall)::numeric, 4),
        'faithfulness', ROUND(AVG(faithfulness)::numeric, 4),
        'answer_relevancy', ROUND(AVG(answer_relevancy)::numeric, 4),
        'overall', ROUND(AVG(overall_score)::numeric, 4),
        'scores', jsonb_agg(
            jsonb_build_object(
                'golden_item_id', golden_item_id,
                'overall_score', overall_score,
                'context_recall', context_recall,
                'faithfulness', faithfulness,
                'answer_relevancy', answer_relevancy,
                'search_latency_ms', search_latency_ms
            )
            ORDER BY golden_item_id
        )
    )
    FROM evaluation_results
    WHERE job_id = p_job_id
      AND overall_score IS NOT NULL;
$$;

GRANT EXECUTE ON FUNCTION get_ab_test_scores(text) TO service_role;
