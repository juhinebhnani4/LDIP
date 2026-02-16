-- Migration: Extend evaluation_results for long-term sustainability
-- Story: RAG Production Gaps - Feature 2: Evaluation Framework (B1/B2/B3 fixes)
-- Description: Adds traceability columns, flexible metric storage, and pipeline versioning
--
-- New columns:
--   expected_answer  - Snapshot of ground truth at eval time (golden item can change later)
--   job_id           - Celery task ID to group batch results
--   chat_message_id  - Link auto-eval to specific chat message
--   metric_scores    - JSONB for all metrics (extensible without migrations)
--   pipeline_config  - JSONB snapshot of what RAG config produced this answer

-- =============================================================================
-- Add new columns
-- =============================================================================

ALTER TABLE evaluation_results
    ADD COLUMN IF NOT EXISTS expected_answer TEXT,
    ADD COLUMN IF NOT EXISTS job_id TEXT,
    ADD COLUMN IF NOT EXISTS chat_message_id TEXT,
    ADD COLUMN IF NOT EXISTS metric_scores JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS pipeline_config JSONB NOT NULL DEFAULT '{}';

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON COLUMN evaluation_results.expected_answer IS 'Ground truth answer at evaluation time (snapshot from golden_dataset)';
COMMENT ON COLUMN evaluation_results.job_id IS 'Celery task ID for grouping batch evaluation results';
COMMENT ON COLUMN evaluation_results.chat_message_id IS 'Links auto-evaluation to the specific chat message';
COMMENT ON COLUMN evaluation_results.metric_scores IS 'All metric scores as JSONB (extensible). Example: {"faithfulness": 0.9, "answer_relevancy": 0.85, "context_recall": 0.7}';
COMMENT ON COLUMN evaluation_results.pipeline_config IS 'Snapshot of RAG pipeline configuration at evaluation time. Example: {"embedding_model": "text-embedding-3-small", "reranker": "rerank-v3.5", "generator_model": "gemini-2.0-flash"}';

-- =============================================================================
-- Indexes for new columns
-- =============================================================================

-- Group results by batch run
CREATE INDEX IF NOT EXISTS idx_evaluation_results_job_id
    ON evaluation_results(job_id)
    WHERE job_id IS NOT NULL;

-- Find evaluation for a specific chat message
CREATE INDEX IF NOT EXISTS idx_evaluation_results_chat_message
    ON evaluation_results(chat_message_id)
    WHERE chat_message_id IS NOT NULL;

-- Query specific metrics from JSONB (e.g. WHERE metric_scores->>'faithfulness' < '0.7')
CREATE INDEX IF NOT EXISTS idx_evaluation_results_metric_scores
    ON evaluation_results USING GIN(metric_scores);
