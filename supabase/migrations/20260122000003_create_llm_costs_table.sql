-- Migration: Create llm_costs table
-- Purpose: Track and aggregate LLM API costs across all operations
--
-- This table stores individual LLM API calls for cost tracking, billing,
-- and usage analysis. Supports aggregation by matter, document, provider,
-- operation, and time period.
--
-- Primary currency: INR (Indian Rupees)
-- USD stored for reference and conversion

-- =============================================================================
-- Table: llm_costs
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.llm_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID REFERENCES public.matters(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
    entity_id UUID,  -- References mig_entities or other entity tables

    -- Provider and operation info
    provider VARCHAR(100) NOT NULL,  -- e.g., 'gpt-4-turbo-preview', 'gemini-2.5-flash'
    operation VARCHAR(100) NOT NULL,  -- e.g., 'citation_extraction', 'rag_generation'

    -- Token counts
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,

    -- Cost in INR (primary currency)
    input_cost_inr NUMERIC(12,4) NOT NULL DEFAULT 0,
    output_cost_inr NUMERIC(12,4) NOT NULL DEFAULT 0,
    total_cost_inr NUMERIC(12,4) NOT NULL DEFAULT 0,

    -- Cost in USD (for reference)
    input_cost_usd NUMERIC(10,8) NOT NULL DEFAULT 0,
    output_cost_usd NUMERIC(10,8) NOT NULL DEFAULT 0,
    total_cost_usd NUMERIC(10,8) NOT NULL DEFAULT 0,

    -- Exchange rate at time of tracking
    usd_to_inr_rate NUMERIC(6,2) DEFAULT 83.50,

    -- Performance metrics
    duration_ms INTEGER,

    -- Metadata for additional context
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================================================================
-- RLS Policy (CRITICAL - Matter Isolation)
-- =============================================================================

ALTER TABLE public.llm_costs ENABLE ROW LEVEL SECURITY;

-- Users can only access costs for matters they are attorneys on
CREATE POLICY "Users access own matter costs only"
ON public.llm_costs FOR ALL
USING (
    matter_id IS NULL OR  -- Allow null matter_id for system-level costs
    matter_id IN (
        SELECT ma.matter_id
        FROM public.matter_attorneys ma
        WHERE ma.user_id = auth.uid()
    )
);

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- Primary lookup: costs by matter
CREATE INDEX idx_llm_costs_matter
ON public.llm_costs(matter_id, created_at DESC);

-- Filter by provider
CREATE INDEX idx_llm_costs_provider
ON public.llm_costs(provider, created_at DESC);

-- Filter by operation
CREATE INDEX idx_llm_costs_operation
ON public.llm_costs(operation, created_at DESC);

-- Document-level aggregation
CREATE INDEX idx_llm_costs_document
ON public.llm_costs(document_id, created_at DESC);

-- Time-based queries (daily/monthly reports)
CREATE INDEX idx_llm_costs_created_at
ON public.llm_costs(created_at DESC);

-- Composite index for common aggregation queries
CREATE INDEX idx_llm_costs_matter_provider_op
ON public.llm_costs(matter_id, provider, operation, created_at DESC);

-- =============================================================================
-- Aggregation Views
-- =============================================================================

-- Daily cost summary per matter (primary: INR)
CREATE OR REPLACE VIEW public.llm_costs_daily AS
SELECT
    matter_id,
    DATE(created_at) as cost_date,
    provider,
    operation,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_cost_inr) as total_cost_inr,
    SUM(total_cost_usd) as total_cost_usd,
    COUNT(*) as operation_count,
    AVG(duration_ms)::INTEGER as avg_duration_ms
FROM public.llm_costs
GROUP BY matter_id, DATE(created_at), provider, operation;

-- Monthly cost summary per matter (primary: INR)
CREATE OR REPLACE VIEW public.llm_costs_monthly AS
SELECT
    matter_id,
    DATE_TRUNC('month', created_at)::DATE as cost_month,
    provider,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_cost_inr) as total_cost_inr,
    SUM(total_cost_usd) as total_cost_usd,
    COUNT(*) as operation_count
FROM public.llm_costs
GROUP BY matter_id, DATE_TRUNC('month', created_at), provider;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE public.llm_costs IS 'Tracks LLM API costs for billing and usage analysis (primary currency: INR)';
COMMENT ON COLUMN public.llm_costs.provider IS 'LLM provider/model identifier (e.g., gpt-4-turbo-preview)';
COMMENT ON COLUMN public.llm_costs.operation IS 'Operation type (e.g., citation_extraction, rag_generation)';
COMMENT ON COLUMN public.llm_costs.input_tokens IS 'Number of input tokens consumed';
COMMENT ON COLUMN public.llm_costs.output_tokens IS 'Number of output tokens generated';
COMMENT ON COLUMN public.llm_costs.total_cost_inr IS 'Total cost in INR at time of tracking';
COMMENT ON COLUMN public.llm_costs.total_cost_usd IS 'Total cost in USD at time of tracking (for reference)';
COMMENT ON COLUMN public.llm_costs.usd_to_inr_rate IS 'USD to INR exchange rate used at time of tracking';
COMMENT ON COLUMN public.llm_costs.duration_ms IS 'API call duration in milliseconds';
