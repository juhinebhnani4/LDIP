-- Migration: Add unique constraint for evaluation result idempotency
-- Gap 9/10 fix: run_batch_evaluation retries can create duplicate results.
-- This unique partial index enables UPSERT on (job_id, golden_item_id) so
-- retried tasks update existing rows instead of inserting duplicates.
--
-- Partial index: only applies when both columns are NOT NULL (batch evaluations).
-- Auto-evaluations (triggered_by='auto') have NULL golden_item_id and are unaffected.

CREATE UNIQUE INDEX IF NOT EXISTS idx_eval_results_job_golden_unique
    ON evaluation_results(job_id, golden_item_id)
    WHERE job_id IS NOT NULL AND golden_item_id IS NOT NULL;
