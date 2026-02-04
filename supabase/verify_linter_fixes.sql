-- =============================================================================
-- Verify all linter fixes applied in migrations 20260204000001 and 20260204000002
-- Run this in the Supabase SQL Editor - returns all results in one table
-- =============================================================================

SELECT test_name, status, detail FROM (

  -- 1. No duplicate indexes
  SELECT
    '1. Duplicate indexes' AS test_name,
    CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status,
    CASE WHEN count(*) = 0 THEN 'No duplicates found'
         ELSE count(*)::text || ' duplicate index groups remain'
    END AS detail,
    1 AS sort_order
  FROM (
    SELECT tablename
    FROM pg_indexes
    WHERE schemaname = 'public'
    GROUP BY schemaname, tablename, indexdef
    HAVING count(*) > 1
  ) dupes

  UNION ALL

  -- 2. Specific dropped indexes are gone
  SELECT
    '2. Dropped indexes (3 specific)',
    CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    CASE WHEN count(*) = 0 THEN 'All 3 duplicate indexes dropped'
         ELSE 'Still found: ' || string_agg(indexname, ', ')
    END,
    2
  FROM pg_indexes
  WHERE indexname IN (
    'idx_llm_quota_limits_provider',
    'idx_statement_comparisons_stmt_a',
    'idx_statement_comparisons_stmt_b'
  )

  UNION ALL

  -- 3. "Prevent deletion of auto-fetched documents" is RESTRICTIVE
  SELECT
    '3. Restrictive delete policy',
    CASE WHEN permissive = 'RESTRICTIVE' THEN 'PASS' ELSE 'FAIL (' || permissive || ')' END,
    CASE WHEN permissive = 'RESTRICTIVE' THEN 'Policy is RESTRICTIVE'
         ELSE 'Policy permissive value: ' || permissive
    END,
    3
  FROM pg_policies
  WHERE tablename = 'documents'
    AND policyname = 'Prevent deletion of auto-fetched documents'

  UNION ALL

  -- 4. "Users can view own memberships" dropped from matter_attorneys
  SELECT
    '4. Dropped redundant policy',
    CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    CASE WHEN count(*) = 0 THEN '"Users can view own memberships" dropped'
         ELSE 'Policy still exists!'
    END,
    4
  FROM pg_policies
  WHERE tablename = 'matter_attorneys'
    AND policyname = 'Users can view own memberships'

  UNION ALL

  -- 5. toc_pages: no FOR ALL policy, has separate per-action policies
  SELECT
    '5. toc_pages policy split',
    CASE
      WHEN count(*) FILTER (WHERE cmd = 'ALL') = 0
       AND count(*) FILTER (WHERE cmd = 'SELECT') >= 1
       AND count(*) FILTER (WHERE cmd = 'INSERT') >= 1
       AND count(*) FILTER (WHERE cmd = 'UPDATE') >= 1
       AND count(*) FILTER (WHERE cmd = 'DELETE') >= 1
      THEN 'PASS' ELSE 'FAIL'
    END,
    'Policies: ' || string_agg(cmd || '=' || policyname, ', ' ORDER BY cmd),
    5
  FROM pg_policies
  WHERE tablename = 'toc_pages'

  UNION ALL

  -- 6. Views are security_invoker
  SELECT
    '6. Security invoker views',
    CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END,
    CASE WHEN count(*) = 2 THEN 'Both views are security_invoker'
         ELSE count(*)::text || '/2 views fixed'
    END,
    6
  FROM pg_class c
  JOIN pg_namespace n ON c.relnamespace = n.oid
  WHERE n.nspname = 'public'
    AND c.relname IN ('active_identity_nodes', 'practice_group_costs')
    AND c.relkind = 'v'
    AND EXISTS (
      SELECT 1 FROM pg_options_to_table(c.reloptions)
      WHERE option_name = 'security_invoker'
        AND option_value IN ('true', 'on', 'yes', '1')
    )

  UNION ALL

  -- 7. Functions have search_path set
  SELECT
    '7. Function search_path',
    CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END,
    CASE WHEN count(*) = 2 THEN 'Both functions have search_path'
         ELSE count(*)::text || '/2 functions fixed'
    END,
    7
  FROM pg_proc p
  JOIN pg_namespace n ON p.pronamespace = n.oid
  WHERE n.nspname = 'public'
    AND p.proname IN ('get_monthly_cost_report', 'update_llm_quota_limits_updated_at')
    AND p.proconfig IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM unnest(p.proconfig) c WHERE c LIKE 'search_path=%'
    )

  UNION ALL

  -- 8. No bare auth.uid() in USING clauses
  -- Postgres decompiles (select auth.uid()) as "( SELECT auth.uid())" with extra parens/spaces
  -- So we check: has auth.uid() but NOT "SELECT auth.uid()" anywhere (case insensitive)
  SELECT
    '8a. auth.uid() initplan (USING)',
    CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    CASE WHEN count(*) = 0 THEN 'All USING clauses use (select auth.uid())'
         ELSE count(*)::text || ' policies have bare auth.uid() in USING'
    END,
    8
  FROM pg_policies
  WHERE schemaname = 'public'
    AND qual ~* 'auth\.uid\(\)'
    AND qual !~* 'SELECT\s+auth\.uid\(\)'

  UNION ALL

  -- 9. No bare auth.uid() in WITH CHECK clauses
  SELECT
    '8b. auth.uid() initplan (WITH CHECK)',
    CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
    CASE WHEN count(*) = 0 THEN 'All WITH CHECK clauses use (select auth.uid())'
         ELSE count(*)::text || ' policies have bare auth.uid() in WITH CHECK'
    END,
    9
  FROM pg_policies
  WHERE schemaname = 'public'
    AND with_check ~* 'auth\.uid\(\)'
    AND with_check !~* 'SELECT\s+auth\.uid\(\)'

) results
ORDER BY sort_order;
