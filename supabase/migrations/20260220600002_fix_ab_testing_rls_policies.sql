-- =============================================================================
-- Fix: Correct A/B Testing RLS Policies
-- Gap 10 Code Review Fix
-- Date: 2026-02-20
--
-- Fixes:
-- 1. RLS policies referenced `matter_members` (doesn't exist) — should be `matter_attorneys`
-- 2. Service role policy missing `WITH CHECK` clause
-- 3. Remove UPDATE grant from authenticated (only service_role should update runs)
-- =============================================================================

-- 1. Drop and recreate SELECT policy with correct table reference
DROP POLICY IF EXISTS "ab_test_runs_select" ON ab_test_runs;
CREATE POLICY "ab_test_runs_select"
    ON ab_test_runs FOR SELECT
    USING (
        matter_id IN (
            SELECT matter_id FROM matter_attorneys WHERE user_id = auth.uid()
        )
    );

-- 2. Drop and recreate INSERT policy with correct table reference
DROP POLICY IF EXISTS "ab_test_runs_insert" ON ab_test_runs;
CREATE POLICY "ab_test_runs_insert"
    ON ab_test_runs FOR INSERT
    WITH CHECK (
        matter_id IN (
            SELECT matter_id FROM matter_attorneys WHERE user_id = auth.uid()
        )
    );

-- 3. Drop and recreate service role policy with explicit WITH CHECK
DROP POLICY IF EXISTS "ab_test_runs_service_role" ON ab_test_runs;
CREATE POLICY "ab_test_runs_service_role"
    ON ab_test_runs FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- 4. Fix grants — remove UPDATE from authenticated (only service_role should update)
REVOKE UPDATE ON ab_test_runs FROM authenticated;
GRANT SELECT, INSERT ON ab_test_runs TO authenticated;
