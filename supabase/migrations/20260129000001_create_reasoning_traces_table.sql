-- Reasoning Traces table for legal defensibility (Story 4.1)
-- Epic 4: Legal Defensibility (Gap Remediation)
-- This migration creates the table for storing AI reasoning chains

-- =============================================================================
-- TABLE: reasoning_traces - Stores AI reasoning chains for legal defensibility
-- =============================================================================

CREATE TABLE public.reasoning_traces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  finding_id uuid REFERENCES public.findings(id) ON DELETE SET NULL,

  -- Source identification
  engine_type text NOT NULL CHECK (engine_type IN ('citation', 'timeline', 'contradiction', 'rag', 'entity')),
  model_used text NOT NULL, -- e.g., 'gpt-4', 'gemini-1.5-flash'

  -- The reasoning content
  reasoning_text text NOT NULL, -- Chain-of-thought explanation
  reasoning_structured jsonb, -- Optional structured breakdown

  -- Context that produced this reasoning
  input_summary text, -- What was fed to the LLM (truncated)
  prompt_template_version text, -- Which prompt version was used

  -- Metadata
  confidence_score float CHECK (confidence_score >= 0 AND confidence_score <= 1), -- 0-1 scale
  tokens_used integer,
  cost_usd numeric(10, 6),

  -- Timestamps
  created_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz DEFAULT NULL, -- Set when moved to cold storage
  archive_path text DEFAULT NULL, -- Supabase Storage path when archived

  -- Constraints
  CONSTRAINT reasoning_not_empty CHECK (length(reasoning_text) > 0)
);

-- =============================================================================
-- INDEXES: Optimized for reasoning trace queries
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_reasoning_traces_matter ON public.reasoning_traces(matter_id);
CREATE INDEX idx_reasoning_traces_finding ON public.reasoning_traces(finding_id) WHERE finding_id IS NOT NULL;
CREATE INDEX idx_reasoning_traces_engine ON public.reasoning_traces(matter_id, engine_type);

-- Archival query index - find traces eligible for archival
CREATE INDEX idx_reasoning_traces_archival ON public.reasoning_traces(created_at) WHERE archived_at IS NULL;

-- Created_at for ordering
CREATE INDEX idx_reasoning_traces_created ON public.reasoning_traces(matter_id, created_at DESC);

-- =============================================================================
-- RLS POLICIES: reasoning_traces table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.reasoning_traces ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can view reasoning from their matters
CREATE POLICY "Users can view reasoning from their matters"
ON public.reasoning_traces FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: System can insert (via service role - bypasses RLS)
-- No explicit INSERT policy needed as service role bypasses RLS

-- Policy 3: No UPDATE allowed (immutable by design for audit integrity)
-- Intentionally omitted to enforce immutability

-- Policy 4: No DELETE allowed (archival only via service role)
-- Intentionally omitted to enforce immutability

-- =============================================================================
-- COMMENTS: Documentation for schema
-- =============================================================================

COMMENT ON TABLE public.reasoning_traces IS 'Stores AI reasoning chains for legal defensibility (Story 4.1). Immutable once created.';
COMMENT ON COLUMN public.reasoning_traces.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.reasoning_traces.finding_id IS 'Optional FK to findings - links reasoning to specific finding';
COMMENT ON COLUMN public.reasoning_traces.engine_type IS 'Source engine: citation, timeline, contradiction, rag, or entity';
COMMENT ON COLUMN public.reasoning_traces.model_used IS 'LLM model identifier (e.g., gpt-4, gemini-1.5-flash)';
COMMENT ON COLUMN public.reasoning_traces.reasoning_text IS 'Chain-of-thought explanation from LLM';
COMMENT ON COLUMN public.reasoning_traces.reasoning_structured IS 'Optional structured breakdown (evidence, factors, limitations)';
COMMENT ON COLUMN public.reasoning_traces.input_summary IS 'Truncated summary of input context sent to LLM';
COMMENT ON COLUMN public.reasoning_traces.prompt_template_version IS 'Version identifier for the prompt template used';
COMMENT ON COLUMN public.reasoning_traces.confidence_score IS 'Confidence score from LLM (0-1 scale)';
COMMENT ON COLUMN public.reasoning_traces.tokens_used IS 'Total tokens consumed for this reasoning';
COMMENT ON COLUMN public.reasoning_traces.cost_usd IS 'Estimated cost in USD for this LLM call';
COMMENT ON COLUMN public.reasoning_traces.archived_at IS 'When trace was moved to cold storage (Story 4.2)';
COMMENT ON COLUMN public.reasoning_traces.archive_path IS 'Supabase Storage path for archived content';
