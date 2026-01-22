-- Migration: Create evaluation tables for RAGAS framework
-- Story: RAG Production Gaps - Feature 2: Evaluation Framework
-- Description: Creates golden_dataset and evaluation_results tables

-- =============================================================================
-- Golden Dataset Table
-- Stores verified QA pairs used as ground truth for evaluation
-- =============================================================================

CREATE TABLE IF NOT EXISTS golden_dataset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    relevant_chunk_ids UUID[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add table comments
COMMENT ON TABLE golden_dataset IS 'Ground truth QA pairs for RAG quality evaluation';
COMMENT ON COLUMN golden_dataset.question IS 'Test question to evaluate';
COMMENT ON COLUMN golden_dataset.expected_answer IS 'Expected correct answer (ground truth)';
COMMENT ON COLUMN golden_dataset.relevant_chunk_ids IS 'UUIDs of chunks that should be retrieved';
COMMENT ON COLUMN golden_dataset.tags IS 'Tags for filtering (citation, timeline, contradiction, etc.)';

-- =============================================================================
-- Evaluation Results Table
-- Stores historical evaluation results for tracking quality over time
-- =============================================================================

CREATE TABLE IF NOT EXISTS evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    golden_item_id UUID REFERENCES golden_dataset(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    contexts TEXT[] DEFAULT '{}',
    context_recall FLOAT,
    faithfulness FLOAT,
    answer_relevancy FLOAT,
    overall_score FLOAT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_by TEXT NOT NULL DEFAULT 'manual',

    -- Constraints for score ranges
    CONSTRAINT context_recall_range CHECK (context_recall IS NULL OR (context_recall >= 0 AND context_recall <= 1)),
    CONSTRAINT faithfulness_range CHECK (faithfulness IS NULL OR (faithfulness >= 0 AND faithfulness <= 1)),
    CONSTRAINT answer_relevancy_range CHECK (answer_relevancy IS NULL OR (answer_relevancy >= 0 AND answer_relevancy <= 1)),
    CONSTRAINT overall_score_range CHECK (overall_score >= 0 AND overall_score <= 1)
);

-- Add table comments
COMMENT ON TABLE evaluation_results IS 'Historical RAG quality evaluation results';
COMMENT ON COLUMN evaluation_results.context_recall IS 'RAGAS context recall score (0-1)';
COMMENT ON COLUMN evaluation_results.faithfulness IS 'RAGAS faithfulness score (0-1)';
COMMENT ON COLUMN evaluation_results.answer_relevancy IS 'RAGAS answer relevancy score (0-1)';
COMMENT ON COLUMN evaluation_results.triggered_by IS 'Who/what triggered: manual, auto, batch';

-- =============================================================================
-- Row Level Security
-- =============================================================================

ALTER TABLE golden_dataset ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_results ENABLE ROW LEVEL SECURITY;

-- Users can only access golden dataset items in their matters
CREATE POLICY "Users access own matter golden dataset"
ON golden_dataset FOR ALL
USING (
    matter_id IN (
        SELECT matter_id FROM matter_attorneys
        WHERE user_id = auth.uid()
    )
);

-- Users can only access evaluation results in their matters
CREATE POLICY "Users access own matter evaluation results"
ON evaluation_results FOR ALL
USING (
    matter_id IN (
        SELECT matter_id FROM matter_attorneys
        WHERE user_id = auth.uid()
    )
);

-- Service role bypass for backend operations
CREATE POLICY "Service role full access to golden_dataset"
ON golden_dataset FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Service role full access to evaluation_results"
ON evaluation_results FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Golden dataset indexes
CREATE INDEX idx_golden_dataset_matter ON golden_dataset(matter_id);
CREATE INDEX idx_golden_dataset_tags ON golden_dataset USING GIN(tags);
CREATE INDEX idx_golden_dataset_created_by ON golden_dataset(created_by);

-- Evaluation results indexes
CREATE INDEX idx_evaluation_results_matter ON evaluation_results(matter_id);
CREATE INDEX idx_evaluation_results_date ON evaluation_results(evaluated_at DESC);
CREATE INDEX idx_evaluation_results_golden_item ON evaluation_results(golden_item_id);
CREATE INDEX idx_evaluation_results_triggered_by ON evaluation_results(triggered_by);

-- Index for finding low-quality results
CREATE INDEX idx_evaluation_results_overall_score ON evaluation_results(overall_score)
WHERE overall_score < 0.7;

-- =============================================================================
-- Triggers
-- =============================================================================

-- Update timestamp trigger for golden_dataset
CREATE OR REPLACE FUNCTION update_golden_dataset_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER golden_dataset_updated_at
    BEFORE UPDATE ON golden_dataset
    FOR EACH ROW
    EXECUTE FUNCTION update_golden_dataset_updated_at();
