-- Tier 1 #3: Summary pre-generation — persist generated summaries to DB
-- so they survive Redis cache eviction (1-hour TTL). The pipeline now
-- pre-generates summaries after detect_contradictions completes, and this
-- table acts as the durable fallback: Redis → DB → regenerate.

CREATE TABLE IF NOT EXISTS matter_summaries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id   UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    content     JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_matter_summaries_matter_id UNIQUE (matter_id)
);

-- Index for the common lookup: get summary by matter_id
-- The unique constraint already creates an index, so this is redundant
-- but explicit for documentation.
COMMENT ON TABLE matter_summaries IS 'Durable cache for AI-generated matter summaries. One row per matter, upserted on each generation.';
COMMENT ON COLUMN matter_summaries.content IS 'Full MatterSummary JSON (camelCase, matches frontend contract).';
