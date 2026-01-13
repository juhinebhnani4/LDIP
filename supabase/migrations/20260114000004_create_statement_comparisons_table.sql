-- Migration: Create statement_comparisons table
-- Story 5-2: Statement Pair Comparison
-- Epic 5: Consistency & Contradiction Engine
--
-- This table stores GPT-4 comparison results for statement pairs,
-- enabling caching, audit trails, and later retrieval of comparisons.

-- =============================================================================
-- Table: statement_comparisons
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.statement_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL,
    statement_a_id UUID NOT NULL,  -- References chunks.chunk_id
    statement_b_id UUID NOT NULL,  -- References chunks.chunk_id
    result VARCHAR(20) NOT NULL CHECK (result IN ('contradiction', 'consistent', 'uncertain', 'unrelated')),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reasoning TEXT NOT NULL,
    evidence JSONB DEFAULT '{}'::jsonb,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT now(),

    -- Ensure unique pairs per matter (prevents duplicate comparisons)
    CONSTRAINT unique_statement_pair UNIQUE (matter_id, statement_a_id, statement_b_id)
);

-- =============================================================================
-- RLS Policy (CRITICAL - Matter Isolation)
-- =============================================================================

ALTER TABLE public.statement_comparisons ENABLE ROW LEVEL SECURITY;

-- Users can only access comparisons for matters they are attorneys on
CREATE POLICY "Users access own matter comparisons only"
ON public.statement_comparisons FOR ALL
USING (
    matter_id IN (
        SELECT ma.matter_id
        FROM public.matter_attorneys ma
        WHERE ma.user_id = auth.uid()
    )
);

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- Primary lookup: all comparisons for an entity within a matter
CREATE INDEX idx_statement_comparisons_entity
ON public.statement_comparisons(matter_id, entity_id);

-- Filter by result type (find all contradictions)
CREATE INDEX idx_statement_comparisons_result
ON public.statement_comparisons(matter_id, result);

-- Time-based queries (recent comparisons)
CREATE INDEX idx_statement_comparisons_created
ON public.statement_comparisons(matter_id, created_at DESC);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE public.statement_comparisons IS 'Story 5-2: Stores GPT-4 statement pair comparison results for contradiction detection';
COMMENT ON COLUMN public.statement_comparisons.id IS 'Unique identifier for this comparison';
COMMENT ON COLUMN public.statement_comparisons.matter_id IS 'Matter this comparison belongs to (for RLS)';
COMMENT ON COLUMN public.statement_comparisons.entity_id IS 'Entity the compared statements are about';
COMMENT ON COLUMN public.statement_comparisons.statement_a_id IS 'First statement chunk_id';
COMMENT ON COLUMN public.statement_comparisons.statement_b_id IS 'Second statement chunk_id';
COMMENT ON COLUMN public.statement_comparisons.result IS 'Comparison result: contradiction, consistent, uncertain, unrelated';
COMMENT ON COLUMN public.statement_comparisons.confidence IS 'GPT-4 confidence score (0-1)';
COMMENT ON COLUMN public.statement_comparisons.reasoning IS 'Chain-of-thought reasoning from GPT-4';
COMMENT ON COLUMN public.statement_comparisons.evidence IS 'JSON evidence: {type, value_a, value_b, page_refs}';
COMMENT ON COLUMN public.statement_comparisons.input_tokens IS 'Input tokens used for cost tracking';
COMMENT ON COLUMN public.statement_comparisons.output_tokens IS 'Output tokens used for cost tracking';
COMMENT ON COLUMN public.statement_comparisons.cost_usd IS 'Total GPT-4 API cost in USD';
