-- Migration: Unit Economics — Priorities 3, 5, 6
-- P3: DB-backed LLM pricing table (replaces hardcoded PROVIDER_PRICING)
-- P5: user_id column on llm_costs for per-user cost attribution
-- P6: Contradiction savings materialized view (two-tier routing ROI)

-- =============================================================================
-- SECTION A: llm_pricing table (Priority 3)
-- =============================================================================
-- Stores per-provider pricing with effective date ranges.
-- effective_to IS NULL means the row is the currently active price.
-- To update a price: SET effective_to = now() on the old row, INSERT new row.

CREATE TABLE public.llm_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(100) NOT NULL,
    input_cost_per_1k NUMERIC(12,8) NOT NULL,
    output_cost_per_1k NUMERIC(12,8) NOT NULL,
    unit VARCHAR(20) NOT NULL DEFAULT 'tokens',
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    effective_to TIMESTAMPTZ,  -- NULL = currently active
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Only one active price per provider (effective_to IS NULL)
CREATE UNIQUE INDEX idx_llm_pricing_active
ON public.llm_pricing(provider) WHERE effective_to IS NULL;

-- Query pattern: lookup by provider
CREATE INDEX idx_llm_pricing_provider ON public.llm_pricing(provider);

COMMENT ON TABLE public.llm_pricing IS
    'LLM provider pricing. Replaces hardcoded PROVIDER_PRICING dict. Update prices without code deploy.';

-- RLS: service_role full access, authenticated read-only
ALTER TABLE public.llm_pricing ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to llm_pricing"
ON public.llm_pricing
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read llm_pricing"
ON public.llm_pricing
FOR SELECT
TO authenticated
USING (true);

-- Seed with current pricing (matches cost_tracking.py PROVIDER_PRICING, Feb 2026)
INSERT INTO public.llm_pricing (provider, input_cost_per_1k, output_cost_per_1k, unit, notes) VALUES
    -- OpenAI GPT-4 Turbo — $10/$30 per 1M tokens
    ('gpt-4-turbo-preview', 0.01000000, 0.03000000, 'tokens', 'OpenAI GPT-4 Turbo. $10/$30 per 1M tokens.'),
    -- OpenAI GPT-4o — $2.50/$10 per 1M tokens
    ('gpt-4o', 0.00250000, 0.01000000, 'tokens', 'OpenAI GPT-4o. $2.50/$10 per 1M tokens (halved Oct 2024).'),
    -- OpenAI GPT-4o-mini — $0.15/$0.60 per 1M tokens
    ('gpt-4o-mini', 0.00015000, 0.00060000, 'tokens', 'OpenAI GPT-4o-mini. $0.15/$0.60 per 1M tokens.'),
    -- OpenAI GPT-3.5 Turbo — $0.50/$1.50 per 1M tokens
    ('gpt-3.5-turbo', 0.00050000, 0.00150000, 'tokens', 'OpenAI GPT-3.5 Turbo. $0.50/$1.50 per 1M tokens.'),
    -- OpenAI Embeddings (Small) — $0.02 per 1M tokens
    ('text-embedding-3-small', 0.00002000, 0.00000000, 'tokens', 'OpenAI text-embedding-3-small. $0.02 per 1M tokens.'),
    -- OpenAI Embeddings (Large) — $0.13 per 1M tokens
    ('text-embedding-3-large', 0.00013000, 0.00000000, 'tokens', 'OpenAI text-embedding-3-large. $0.13 per 1M tokens.'),
    -- Gemini 2.5 Flash — $0.30/$2.50 per 1M tokens
    ('gemini-2.5-flash', 0.00030000, 0.00250000, 'tokens', 'Gemini 2.5 Flash. $0.30/$2.50 per 1M tokens.'),
    -- Gemini 1.5 Pro — $1.25/$5.00 per 1M tokens
    ('gemini-1.5-pro', 0.00125000, 0.00500000, 'tokens', 'Gemini 1.5 Pro. $1.25/$5.00 per 1M tokens.'),
    -- Cohere Rerank — $2 per 1K searches
    ('rerank-v3.5', 0.00200000, 0.00000000, 'searches', 'Cohere Rerank v3.5. $2 per 1K searches.'),
    -- Google Document AI — ~$0.06/page
    ('document-ai', 60.00000000, 0.00000000, 'pages', 'Google Document AI OCR. $60 per 1K pages ($0.06/page).');


-- =============================================================================
-- SECTION B: user_id on llm_costs (Priority 5)
-- =============================================================================
-- Enables per-user cost attribution for billing/quotas.
-- Celery worker tasks (no auth context) will have NULL user_id.

ALTER TABLE public.llm_costs
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_llm_costs_user_id
ON public.llm_costs(user_id, created_at DESC);

COMMENT ON COLUMN public.llm_costs.user_id IS
    'Authenticated user who triggered this cost. NULL for background/worker tasks.';


-- =============================================================================
-- SECTION C: Contradiction savings materialized view (Priority 6)
-- =============================================================================
-- Shows how much the two-tier contradiction routing saves vs all-GPT-4o.
-- Compares actual cost (Gemini screening + GPT-4o escalation) against
-- hypothetical cost if all screening tokens went through GPT-4o.

CREATE MATERIALIZED VIEW public.contradiction_savings_report AS
SELECT
    DATE_TRUNC('month', c.created_at)::DATE AS month,
    c.matter_id,

    -- Screening tier (Gemini Flash)
    COUNT(*) FILTER (WHERE c.operation = 'contradiction_screening') AS screening_calls,
    COALESCE(SUM(c.total_cost_usd) FILTER (WHERE c.operation = 'contradiction_screening'), 0) AS screening_cost_usd,
    COALESCE(SUM(c.input_tokens) FILTER (WHERE c.operation = 'contradiction_screening'), 0) AS screening_input_tokens,
    COALESCE(SUM(c.output_tokens) FILTER (WHERE c.operation = 'contradiction_screening'), 0) AS screening_output_tokens,

    -- Escalated tier (GPT-4o comparison + classification)
    COUNT(*) FILTER (WHERE c.operation IN ('contradiction_comparison', 'contradiction_classification')) AS escalated_calls,
    COALESCE(SUM(c.total_cost_usd) FILTER (WHERE c.operation IN ('contradiction_comparison', 'contradiction_classification')), 0) AS escalated_cost_usd,

    -- Actual total cost across all contradiction operations
    COALESCE(SUM(c.total_cost_usd) FILTER (
        WHERE c.operation IN ('contradiction_screening', 'contradiction_comparison', 'contradiction_classification')
    ), 0) AS actual_total_cost_usd,

    -- Escalation rate: how many screenings got escalated to GPT-4o
    CASE WHEN COUNT(*) FILTER (WHERE c.operation = 'contradiction_screening') > 0
         THEN ROUND(
             COUNT(*) FILTER (WHERE c.operation = 'contradiction_comparison')::NUMERIC
             / COUNT(*) FILTER (WHERE c.operation = 'contradiction_screening'),
             4
         )
         ELSE NULL
    END AS escalation_rate,

    -- Hypothetical: what if screening tokens went through GPT-4o instead of Gemini?
    -- GPT-4o rates: $2.50/1M input ($0.0025/1K), $10/1M output ($0.01/1K)
    COALESCE(
        (SUM(c.input_tokens) FILTER (WHERE c.operation = 'contradiction_screening') / 1000.0) * 0.0025
      + (SUM(c.output_tokens) FILTER (WHERE c.operation = 'contradiction_screening') / 1000.0) * 0.01,
        0
    ) AS hypothetical_screening_as_gpt4o_usd,

    -- Total contradiction API calls
    COUNT(*) FILTER (
        WHERE c.operation IN ('contradiction_screening', 'contradiction_comparison', 'contradiction_classification')
    ) AS total_calls

FROM public.llm_costs c
WHERE c.operation IN ('contradiction_screening', 'contradiction_comparison', 'contradiction_classification')
GROUP BY DATE_TRUNC('month', c.created_at)::DATE, c.matter_id
WITH NO DATA;

-- Unique index for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_contradiction_savings_pk
ON public.contradiction_savings_report(matter_id, month);

COMMENT ON MATERIALIZED VIEW public.contradiction_savings_report IS
    'Two-tier contradiction routing savings analysis. Compare actual vs hypothetical all-GPT-4o cost.';


-- =============================================================================
-- SECTION D: Update refresh function to include new view
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
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.contradiction_savings_report;
END;
$$;

COMMENT ON FUNCTION public.refresh_unit_economics_views IS
    'Refresh all unit economics materialized views (cost-per-page, monthly COGS, contradiction savings). Call daily or after batch ingestion.';


-- =============================================================================
-- Initial data population for new view
-- =============================================================================
REFRESH MATERIALIZED VIEW public.contradiction_savings_report;
