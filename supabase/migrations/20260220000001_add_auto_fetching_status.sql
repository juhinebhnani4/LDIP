-- Add 'auto_fetching' status to act_resolutions for in-progress auto-fetch tracking
-- This intermediate state prevents the race condition where acts appear as "Missing"
-- while the system is actively fetching them from India Code.

-- =============================================================================
-- ALTER resolution_status CHECK constraint to include 'auto_fetching'
-- =============================================================================

ALTER TABLE public.act_resolutions
DROP CONSTRAINT IF EXISTS act_resolutions_resolution_status_check;

ALTER TABLE public.act_resolutions
ADD CONSTRAINT act_resolutions_resolution_status_check
CHECK (resolution_status IN (
  'available',        -- Has document (manual upload)
  'auto_fetched',     -- Auto-fetched from India Code (complete)
  'auto_fetching',    -- Auto-fetch in progress from India Code
  'missing',          -- Needs manual upload
  'invalid',          -- Garbage extraction (hidden from user)
  'not_on_indiacode', -- Valid but not available online (needs manual upload)
  'skipped'           -- User chose to skip
));

-- =============================================================================
-- Partial index for polling auto_fetching acts efficiently
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_act_resolutions_auto_fetching
  ON public.act_resolutions(matter_id, act_name_normalized)
  WHERE resolution_status = 'auto_fetching';
