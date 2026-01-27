-- Migration: Add user adoption features
-- Epic 6: User Adoption
-- Stories 6.1, 6.2, 6.4

-- =============================================================================
-- Story 6.1 & 6.2: User adoption preferences
-- =============================================================================

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS power_user_mode BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS onboarding_stage VARCHAR(20) DEFAULT NULL;

-- Add constraint for onboarding_stage values
ALTER TABLE user_preferences
DROP CONSTRAINT IF EXISTS user_preferences_onboarding_stage_check;

ALTER TABLE user_preferences
ADD CONSTRAINT user_preferences_onboarding_stage_check
CHECK (onboarding_stage IS NULL OR onboarding_stage IN (
  'dashboard', 'upload', 'settings', 'summary', 'timeline',
  'entities', 'contradictions', 'citations', 'qa', 'verification'
));

-- Backward compatibility: existing users get power_user_mode = true
-- This ensures existing workflows are not disrupted
UPDATE user_preferences
SET power_user_mode = true
WHERE created_at < '2026-02-01';

-- For users without preferences row yet (edge case)
-- Insert with power_user_mode = true for existing users
INSERT INTO user_preferences (user_id, power_user_mode)
SELECT id, true FROM auth.users
WHERE id NOT IN (SELECT user_id FROM user_preferences)
AND created_at < '2026-02-01'
ON CONFLICT (user_id) DO NOTHING;

-- Add comments for documentation
COMMENT ON COLUMN user_preferences.power_user_mode IS
  'When false, hides advanced features (bulk ops, keyboard shortcuts). New users default to false.';

COMMENT ON COLUMN user_preferences.onboarding_completed IS
  'True after user completes the 10-step onboarding wizard.';

COMMENT ON COLUMN user_preferences.onboarding_stage IS
  'Current wizard step: dashboard|upload|settings|summary|timeline|entities|contradictions|citations|qa|verification';

-- =============================================================================
-- Story 6.4: Analysis mode for matters
-- =============================================================================

ALTER TABLE matters
ADD COLUMN IF NOT EXISTS analysis_mode VARCHAR(20) NOT NULL DEFAULT 'deep_analysis';

-- Add constraint for analysis_mode values
ALTER TABLE matters
DROP CONSTRAINT IF EXISTS matters_analysis_mode_check;

ALTER TABLE matters
ADD CONSTRAINT matters_analysis_mode_check
CHECK (analysis_mode IN ('quick_scan', 'deep_analysis'));

-- Add comment for documentation
COMMENT ON COLUMN matters.analysis_mode IS
  'quick_scan skips contradiction engine, reduces chunk overlap; deep_analysis runs all engines';

-- Index for potential filtering by analysis mode
CREATE INDEX IF NOT EXISTS idx_matters_analysis_mode ON matters(analysis_mode);
