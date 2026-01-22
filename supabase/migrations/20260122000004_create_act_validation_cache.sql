-- Create act_validation_cache table for global Act validation
-- Part of Act Validation and Auto-Fetching feature
-- This table caches validation results from India Code to avoid repeated lookups

-- =============================================================================
-- TABLE: act_validation_cache - Global cache for Act validation (shared across matters)
-- =============================================================================

CREATE TABLE public.act_validation_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Act identification (normalized name as key)
  act_name_normalized text NOT NULL UNIQUE,

  -- Canonical display name (if validated)
  act_name_canonical text,

  -- Year of the Act (if known)
  act_year integer,

  -- India Code reference
  india_code_url text,           -- Full URL to the Act on indiacode.nic.in
  india_code_doc_id text,        -- DSpace document ID for PDF download

  -- Validation status
  validation_status text NOT NULL DEFAULT 'unknown'
    CHECK (validation_status IN (
      'valid',            -- Confirmed valid Central Act
      'invalid',          -- Garbage extraction (sentence fragment, etc.)
      'state_act',        -- Valid but a State Act (not on India Code)
      'not_on_indiacode', -- Valid but not available online
      'unknown'           -- Not yet validated
    )),

  -- Cached PDF storage path (global/acts/{name}.pdf)
  cached_storage_path text,

  -- Validation metadata
  validation_source text,        -- 'india_code', 'abbreviations', 'manual', 'garbage_detection'
  validation_confidence float,   -- 0.0 to 1.0 confidence score
  validation_metadata jsonb,     -- Additional metadata from validation

  -- Timestamps
  last_validated_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for validation lookups
-- =============================================================================

-- Primary lookup by normalized name (UNIQUE constraint creates index)
-- Additional index for validation status filtering
CREATE INDEX idx_act_validation_cache_status ON public.act_validation_cache(validation_status);

-- Index for finding cached PDFs
CREATE INDEX idx_act_validation_cache_cached ON public.act_validation_cache(cached_storage_path)
  WHERE cached_storage_path IS NOT NULL;

-- Index for India Code document ID
CREATE INDEX idx_act_validation_cache_indiacode ON public.act_validation_cache(india_code_doc_id)
  WHERE india_code_doc_id IS NOT NULL;

-- Partial index for acts needing validation
CREATE INDEX idx_act_validation_cache_unknown ON public.act_validation_cache(created_at)
  WHERE validation_status = 'unknown';

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE public.act_validation_cache IS 'Global cache for Act validation from India Code and other sources';
COMMENT ON COLUMN public.act_validation_cache.act_name_normalized IS 'Normalized Act name (lowercase, no punctuation) - primary lookup key';
COMMENT ON COLUMN public.act_validation_cache.act_name_canonical IS 'Canonical display name (e.g., "Negotiable Instruments Act, 1881")';
COMMENT ON COLUMN public.act_validation_cache.act_year IS 'Year the Act was enacted (if known)';
COMMENT ON COLUMN public.act_validation_cache.india_code_url IS 'Full URL to the Act page on indiacode.nic.in';
COMMENT ON COLUMN public.act_validation_cache.india_code_doc_id IS 'DSpace document ID for PDF download';
COMMENT ON COLUMN public.act_validation_cache.validation_status IS 'valid (confirmed), invalid (garbage), state_act, not_on_indiacode, unknown';
COMMENT ON COLUMN public.act_validation_cache.cached_storage_path IS 'Supabase Storage path to cached PDF (global/acts/{name}.pdf)';
COMMENT ON COLUMN public.act_validation_cache.validation_source IS 'Source of validation: india_code, abbreviations, manual, garbage_detection';
COMMENT ON COLUMN public.act_validation_cache.validation_confidence IS 'Confidence score 0.0-1.0 for validation result';
COMMENT ON COLUMN public.act_validation_cache.validation_metadata IS 'Additional metadata: search results, garbage patterns matched, etc.';

-- =============================================================================
-- RLS POLICIES: act_validation_cache - Read-only for authenticated users
-- =============================================================================

ALTER TABLE public.act_validation_cache ENABLE ROW LEVEL SECURITY;

-- Anyone authenticated can read the cache (it's global)
CREATE POLICY "Authenticated users can view validation cache"
ON public.act_validation_cache FOR SELECT
TO authenticated
USING (true);

-- Only service role can insert/update (via backend workers)
-- No INSERT/UPDATE/DELETE policies for authenticated users
-- Service role bypasses RLS automatically

-- =============================================================================
-- TRIGGER: Auto-update updated_at on modification
-- =============================================================================

CREATE TRIGGER set_act_validation_cache_updated_at
  BEFORE UPDATE ON public.act_validation_cache
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- ALTER act_resolutions: Add new status and auto-fetch tracking
-- =============================================================================

-- Add new resolution statuses for auto-fetching
ALTER TABLE public.act_resolutions
DROP CONSTRAINT IF EXISTS act_resolutions_resolution_status_check;

ALTER TABLE public.act_resolutions
ADD CONSTRAINT act_resolutions_resolution_status_check
CHECK (resolution_status IN (
  'available',        -- Has document (manual upload or auto-fetched)
  'auto_fetched',     -- Auto-fetched from India Code
  'missing',          -- Needs manual upload
  'invalid',          -- Garbage extraction (hidden from user)
  'not_on_indiacode', -- Valid but not available online (needs manual upload)
  'skipped'           -- User chose to skip
));

-- Add user_action options for auto-fetch
ALTER TABLE public.act_resolutions
DROP CONSTRAINT IF EXISTS act_resolutions_user_action_check;

ALTER TABLE public.act_resolutions
ADD CONSTRAINT act_resolutions_user_action_check
CHECK (user_action IN (
  'uploaded',     -- User manually uploaded
  'skipped',      -- User chose to skip
  'auto_fetched', -- System auto-fetched
  'pending'       -- Awaiting action
));

-- Add column to link to global validation cache
ALTER TABLE public.act_resolutions
ADD COLUMN IF NOT EXISTS validation_cache_id uuid REFERENCES public.act_validation_cache(id);

-- Add column for validation status at matter level
ALTER TABLE public.act_resolutions
ADD COLUMN IF NOT EXISTS is_valid boolean DEFAULT true;

-- Index for filtering invalid acts
CREATE INDEX IF NOT EXISTS idx_act_resolutions_is_valid
ON public.act_resolutions(matter_id, is_valid)
WHERE is_valid = false;

-- Index for validation cache link
CREATE INDEX IF NOT EXISTS idx_act_resolutions_validation_cache
ON public.act_resolutions(validation_cache_id)
WHERE validation_cache_id IS NOT NULL;

COMMENT ON COLUMN public.act_resolutions.validation_cache_id IS 'FK to global validation cache entry';
COMMENT ON COLUMN public.act_resolutions.is_valid IS 'Whether this is a valid act (false = garbage extraction, hidden from UI)';

-- =============================================================================
-- HELPER FUNCTION: Get or create validation cache entry
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_or_create_validation_cache(
  p_act_name_normalized text,
  p_act_name_canonical text DEFAULT NULL,
  p_act_year integer DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  -- Try to find existing entry
  SELECT id INTO v_id
  FROM public.act_validation_cache
  WHERE act_name_normalized = p_act_name_normalized;

  IF v_id IS NOT NULL THEN
    RETURN v_id;
  END IF;

  -- Create new entry
  INSERT INTO public.act_validation_cache (
    act_name_normalized,
    act_name_canonical,
    act_year,
    validation_status
  )
  VALUES (
    p_act_name_normalized,
    p_act_name_canonical,
    p_act_year,
    'unknown'
  )
  ON CONFLICT (act_name_normalized) DO NOTHING
  RETURNING id INTO v_id;

  -- If insert failed due to race condition, fetch the existing row
  IF v_id IS NULL THEN
    SELECT id INTO v_id
    FROM public.act_validation_cache
    WHERE act_name_normalized = p_act_name_normalized;
  END IF;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.get_or_create_validation_cache IS 'Get or create a validation cache entry for an Act';

-- =============================================================================
-- HELPER FUNCTION: Update validation cache status
-- =============================================================================

CREATE OR REPLACE FUNCTION public.update_validation_cache(
  p_act_name_normalized text,
  p_validation_status text,
  p_validation_source text DEFAULT NULL,
  p_india_code_url text DEFAULT NULL,
  p_india_code_doc_id text DEFAULT NULL,
  p_cached_storage_path text DEFAULT NULL,
  p_validation_confidence float DEFAULT NULL,
  p_validation_metadata jsonb DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.act_validation_cache
  SET
    validation_status = p_validation_status,
    validation_source = COALESCE(p_validation_source, validation_source),
    india_code_url = COALESCE(p_india_code_url, india_code_url),
    india_code_doc_id = COALESCE(p_india_code_doc_id, india_code_doc_id),
    cached_storage_path = COALESCE(p_cached_storage_path, cached_storage_path),
    validation_confidence = COALESCE(p_validation_confidence, validation_confidence),
    validation_metadata = COALESCE(p_validation_metadata, validation_metadata),
    last_validated_at = now(),
    updated_at = now()
  WHERE act_name_normalized = p_act_name_normalized;
END;
$$;

COMMENT ON FUNCTION public.update_validation_cache IS 'Update validation cache entry with new status and metadata';
