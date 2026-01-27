-- Migration: Create llm_quota_limits table
-- Story: gap-5.2 - LLM Quota Monitoring Dashboard
-- Purpose: Store quota limits for LLM providers to enable monitoring and alerting
--
-- This table stores configurable quota limits per LLM provider.
-- Used by the quota monitoring dashboard and Celery alerting task.

-- =============================================================================
-- Table: llm_quota_limits
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.llm_quota_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provider identification
    provider VARCHAR(50) NOT NULL UNIQUE,  -- 'gemini', 'openai'

    -- Token limits (NULL = unlimited)
    daily_token_limit BIGINT,
    monthly_token_limit BIGINT,

    -- Cost limits in INR (primary currency)
    daily_cost_limit_inr NUMERIC(12,4),
    monthly_cost_limit_inr NUMERIC(12,4),

    -- Alert configuration
    alert_threshold_pct INTEGER NOT NULL DEFAULT 80,  -- Percentage at which to trigger alert

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- RLS Policy (Admin-only access)
-- =============================================================================

ALTER TABLE public.llm_quota_limits ENABLE ROW LEVEL SECURITY;

-- Admin users can read quota limits
-- Note: For read access in dashboard, we allow authenticated users to view
-- but only admins can modify (handled at API level)
CREATE POLICY "Authenticated users can read quota limits"
ON public.llm_quota_limits FOR SELECT
TO authenticated
USING (true);

-- Service role can manage quota limits (used by admin API)
CREATE POLICY "Service role can manage quota limits"
ON public.llm_quota_limits FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Primary lookup by provider
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_quota_limits_provider
ON public.llm_quota_limits(provider);

-- =============================================================================
-- Updated_at trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION public.update_llm_quota_limits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_llm_quota_limits_updated_at
    BEFORE UPDATE ON public.llm_quota_limits
    FOR EACH ROW
    EXECUTE FUNCTION public.update_llm_quota_limits_updated_at();

-- =============================================================================
-- Seed default limits for providers
-- =============================================================================

-- Gemini limits (conservative free tier defaults)
INSERT INTO public.llm_quota_limits (
    provider,
    daily_token_limit,
    monthly_token_limit,
    daily_cost_limit_inr,
    monthly_cost_limit_inr,
    alert_threshold_pct
) VALUES (
    'gemini',
    1000000,        -- 1M tokens/day (free tier ~1.5M/day)
    25000000,       -- 25M tokens/month
    500.00,         -- ~$6 INR/day limit
    10000.00,       -- ~$120 INR/month limit
    80              -- Alert at 80%
) ON CONFLICT (provider) DO NOTHING;

-- OpenAI limits (tier 1 defaults)
INSERT INTO public.llm_quota_limits (
    provider,
    daily_token_limit,
    monthly_token_limit,
    daily_cost_limit_inr,
    monthly_cost_limit_inr,
    alert_threshold_pct
) VALUES (
    'openai',
    500000,         -- 500K tokens/day
    10000000,       -- 10M tokens/month
    2500.00,        -- ~$30 INR/day limit
    50000.00,       -- ~$600 INR/month limit
    80              -- Alert at 80%
) ON CONFLICT (provider) DO NOTHING;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE public.llm_quota_limits IS 'LLM provider quota limits for monitoring and alerting (Story gap-5.2)';
COMMENT ON COLUMN public.llm_quota_limits.provider IS 'LLM provider identifier (gemini, openai)';
COMMENT ON COLUMN public.llm_quota_limits.daily_token_limit IS 'Maximum tokens allowed per day (NULL = unlimited)';
COMMENT ON COLUMN public.llm_quota_limits.monthly_token_limit IS 'Maximum tokens allowed per month (NULL = unlimited)';
COMMENT ON COLUMN public.llm_quota_limits.daily_cost_limit_inr IS 'Maximum daily cost in INR (NULL = unlimited)';
COMMENT ON COLUMN public.llm_quota_limits.monthly_cost_limit_inr IS 'Maximum monthly cost in INR (NULL = unlimited)';
COMMENT ON COLUMN public.llm_quota_limits.alert_threshold_pct IS 'Percentage of limit at which to trigger alert (default 80)';
