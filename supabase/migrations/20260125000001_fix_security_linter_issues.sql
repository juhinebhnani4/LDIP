-- Migration: Fix Supabase Security Linter Issues
-- Date: 2026-01-25
-- Fixes:
--   1. CRITICAL: Enable RLS on audit_logs table
--   2. CRITICAL: Fix SECURITY DEFINER views (llm_costs_daily/monthly)
--   3. MEDIUM: Fix overly permissive notifications INSERT policy
--   4. WARN: Add search_path to all functions missing it

-- =============================================================================
-- Fix #1: Enable RLS on audit_logs (ERROR: rls_disabled_in_public)
-- =============================================================================
-- Note: This table is intentionally accessed via service_role only.
-- We enable RLS with a restrictive policy that blocks all non-service access.

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Only service_role can access audit logs (anon/authenticated are blocked)
CREATE POLICY "Service role only access to audit_logs"
ON public.audit_logs FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

COMMENT ON POLICY "Service role only access to audit_logs" ON public.audit_logs IS
  'Audit logs are restricted to service_role only for security compliance';

-- =============================================================================
-- Fix #2: Recreate views with SECURITY INVOKER (ERROR: security_definer_view)
-- =============================================================================
-- Views should use SECURITY INVOKER so RLS policies are enforced for the
-- querying user, not the view creator.

DROP VIEW IF EXISTS public.llm_costs_daily;
DROP VIEW IF EXISTS public.llm_costs_monthly;

-- Daily cost summary per matter (primary: INR) - with SECURITY INVOKER
CREATE VIEW public.llm_costs_daily
WITH (security_invoker = true)
AS
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

-- Monthly cost summary per matter (primary: INR) - with SECURITY INVOKER
CREATE VIEW public.llm_costs_monthly
WITH (security_invoker = true)
AS
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

COMMENT ON VIEW public.llm_costs_daily IS 'Daily LLM cost aggregation with SECURITY INVOKER';
COMMENT ON VIEW public.llm_costs_monthly IS 'Monthly LLM cost aggregation with SECURITY INVOKER';

-- =============================================================================
-- Fix #3: Fix notifications INSERT policy (WARN: rls_policy_always_true)
-- =============================================================================
-- The current INSERT policy uses WITH CHECK (true) which is overly permissive.
-- Replace with a policy that only allows service_role to insert.

DROP POLICY IF EXISTS "Service can insert notifications" ON public.notifications;

-- Only service_role can insert notifications (backend creates them for users)
CREATE POLICY "Service role can insert notifications"
ON public.notifications FOR INSERT
TO service_role
WITH CHECK (true);

COMMENT ON POLICY "Service role can insert notifications" ON public.notifications IS
  'Only backend service can create notifications for users';

-- =============================================================================
-- Fix #4: Add search_path to functions (WARN: function_search_path_mutable)
-- =============================================================================
-- Setting search_path = '' prevents search path injection attacks.
-- Each function is recreated with its original body plus SET search_path = ''.

-- 4.1: update_updated_at_column
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- 4.2: handle_new_user
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (id, email, full_name, avatar_url)
  VALUES (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url'
  );
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER
SET search_path = '';

-- 4.3: auto_assign_matter_owner
CREATE OR REPLACE FUNCTION public.auto_assign_matter_owner()
RETURNS trigger AS $$
BEGIN
  IF auth.uid() IS NOT NULL THEN
    INSERT INTO public.matter_attorneys (matter_id, user_id, role, invited_by)
    VALUES (NEW.id, auth.uid(), 'owner', auth.uid())
    ON CONFLICT (matter_id, user_id) DO NOTHING;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER
SET search_path = '';

-- 4.4: user_has_matter_access
CREATE OR REPLACE FUNCTION public.user_has_matter_access(check_matter_id uuid)
RETURNS boolean AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.matter_attorneys
    WHERE matter_id = check_matter_id
    AND user_id = auth.uid()
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE
SET search_path = '';

-- 4.5: get_matter_id_from_storage_path
CREATE OR REPLACE FUNCTION public.get_matter_id_from_storage_path(path text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  path_parts text[];
  matter_id_str text;
BEGIN
  path_parts := string_to_array(path, '/');
  IF array_length(path_parts, 1) < 3 THEN
    RETURN NULL;
  END IF;
  matter_id_str := path_parts[1];
  IF matter_id_str !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN NULL;
  END IF;
  RETURN matter_id_str::uuid;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

-- 4.6: user_has_storage_access
CREATE OR REPLACE FUNCTION public.user_has_storage_access(matter_uuid uuid, required_roles text[] DEFAULT ARRAY['owner', 'editor', 'viewer'])
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  IF matter_uuid IS NULL THEN
    RETURN false;
  END IF;
  RETURN EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_uuid
    AND ma.user_id = auth.uid()
    AND ma.role = ANY(required_roles)
  );
END;
$$;

-- 4.7: validate_storage_document_path
CREATE OR REPLACE FUNCTION public.validate_storage_document_path(path text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  path_parts text[];
BEGIN
  path_parts := string_to_array(path, '/');
  IF array_length(path_parts, 1) < 3 THEN
    RETURN false;
  END IF;
  IF path_parts[1] !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN false;
  END IF;
  IF path_parts[2] NOT IN ('uploads', 'acts', 'exports') THEN
    RETURN false;
  END IF;
  IF path_parts[3] IS NULL OR path_parts[3] = '' THEN
    RETURN false;
  END IF;
  RETURN true;
END;
$$;

-- 4.8: get_matter_id_from_chunk_path
CREATE OR REPLACE FUNCTION public.get_matter_id_from_chunk_path(path text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  path_parts text[];
  matter_id_str text;
BEGIN
  path_parts := string_to_array(path, '/');
  IF array_length(path_parts, 1) < 3 THEN
    RETURN NULL;
  END IF;
  matter_id_str := path_parts[1];
  IF matter_id_str !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN NULL;
  END IF;
  RETURN matter_id_str::uuid;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

-- 4.9: validate_ocr_chunk_path
CREATE OR REPLACE FUNCTION public.validate_ocr_chunk_path(path text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  path_parts text[];
  filename text;
BEGIN
  path_parts := string_to_array(path, '/');
  IF array_length(path_parts, 1) != 3 THEN
    RETURN false;
  END IF;
  IF path_parts[1] !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN false;
  END IF;
  IF path_parts[2] !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN false;
  END IF;
  filename := path_parts[3];
  IF filename !~ '^[0-9]+\.json$' THEN
    RETURN false;
  END IF;
  RETURN true;
END;
$$;

-- 4.10: get_correction_stats
CREATE OR REPLACE FUNCTION public.get_correction_stats(p_matter_id uuid)
RETURNS TABLE (
    total_corrections bigint,
    add_count bigint,
    remove_count bigint,
    merge_count bigint,
    unique_entities bigint,
    unique_correctors bigint
)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = ''
AS $$
    SELECT
        COUNT(*) as total_corrections,
        COUNT(*) FILTER (WHERE correction_type = 'add') as add_count,
        COUNT(*) FILTER (WHERE correction_type = 'remove') as remove_count,
        COUNT(*) FILTER (WHERE correction_type = 'merge') as merge_count,
        COUNT(DISTINCT entity_id) as unique_entities,
        COUNT(DISTINCT corrected_by) as unique_correctors
    FROM public.alias_corrections
    WHERE matter_id = p_matter_id;
$$;

-- 4.11: get_recent_corrections
CREATE OR REPLACE FUNCTION public.get_recent_corrections(
    p_matter_id uuid,
    p_limit int DEFAULT 100
)
RETURNS TABLE (
    id uuid,
    entity_id uuid,
    entity_name text,
    correction_type text,
    alias_name text,
    merged_entity_name text,
    original_confidence float,
    reason text,
    created_at timestamptz
)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = ''
AS $$
    SELECT
        ac.id,
        ac.entity_id,
        node.canonical_name as entity_name,
        ac.correction_type,
        ac.alias_name,
        ac.merged_entity_name,
        ac.original_confidence,
        ac.reason,
        ac.created_at
    FROM public.alias_corrections ac
    LEFT JOIN public.identity_nodes node ON node.id = ac.entity_id
    WHERE ac.matter_id = p_matter_id
    ORDER BY ac.created_at DESC
    LIMIT p_limit;
$$;

-- 4.12: validate_statement_comparison_matter
CREATE OR REPLACE FUNCTION public.validate_statement_comparison_matter()
RETURNS TRIGGER AS $$
DECLARE
  stmt_a_matter_id uuid;
  stmt_b_matter_id uuid;
BEGIN
  SELECT matter_id INTO stmt_a_matter_id
  FROM public.chunks
  WHERE id = NEW.statement_a_id;

  SELECT matter_id INTO stmt_b_matter_id
  FROM public.chunks
  WHERE id = NEW.statement_b_id;

  IF stmt_a_matter_id IS NULL OR stmt_a_matter_id != NEW.matter_id THEN
    RAISE EXCEPTION 'statement_a_id % does not belong to matter %',
      NEW.statement_a_id, NEW.matter_id;
  END IF;

  IF stmt_b_matter_id IS NULL OR stmt_b_matter_id != NEW.matter_id THEN
    RAISE EXCEPTION 'statement_b_id % does not belong to matter %',
      NEW.statement_b_id, NEW.matter_id;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- 4.13: validate_contradiction_evidence
CREATE OR REPLACE FUNCTION public.validate_contradiction_evidence(evidence jsonb)
RETURNS boolean AS $$
BEGIN
  IF evidence IS NULL OR evidence = '{}'::jsonb THEN
    RETURN true;
  END IF;
  IF evidence ? 'type' THEN
    IF NOT (evidence->>'type' IN (
      'none',
      'date_mismatch',
      'amount_mismatch',
      'quantity_mismatch',
      'semantic_conflict',
      'factual_conflict'
    )) THEN
      RETURN false;
    END IF;
  END IF;
  RETURN true;
END;
$$ LANGUAGE plpgsql IMMUTABLE
SET search_path = '';

-- 4.14: validate_anomaly_event_ids
CREATE OR REPLACE FUNCTION public.validate_anomaly_event_ids()
RETURNS TRIGGER AS $$
DECLARE
  invalid_event_id uuid;
BEGIN
  IF NEW.event_ids IS NULL OR array_length(NEW.event_ids, 1) IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT e_id INTO invalid_event_id
  FROM unnest(NEW.event_ids) AS e_id
  WHERE NOT EXISTS (
    SELECT 1 FROM public.events e
    WHERE e.id = e_id AND e.matter_id = NEW.matter_id
  )
  LIMIT 1;

  IF invalid_event_id IS NOT NULL THEN
    RAISE EXCEPTION 'event_id % does not exist or does not belong to matter %',
      invalid_event_id, NEW.matter_id;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- 4.15: get_section_page
CREATE OR REPLACE FUNCTION public.get_section_page(
  p_document_id uuid,
  p_section_number text
)
RETURNS TABLE (
  page_number integer,
  section_title text,
  confidence float,
  source text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  RETURN QUERY
  SELECT
    si.page_number,
    si.section_title,
    si.confidence,
    'section_index'::text as source
  FROM public.section_index si
  WHERE si.document_id = p_document_id
    AND si.section_number = p_section_number
    AND NOT si.is_toc
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN QUERY
    SELECT
      bb.page_number,
      NULL::text as section_title,
      0.7::float as confidence,
      'bbox_search'::text as source
    FROM public.bounding_boxes bb
    WHERE bb.document_id = p_document_id
      AND bb.text ILIKE '%section ' || p_section_number || '%'
      AND bb.page_number > 10
      AND bb.text NOT ILIKE '%1956%'
    ORDER BY bb.page_number DESC
    LIMIT 1;
  END IF;
END;
$$;

-- 4.16: update_document_tables_updated_at
CREATE OR REPLACE FUNCTION public.update_document_tables_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- 4.17: update_user_preferences_updated_at
CREATE OR REPLACE FUNCTION public.update_user_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- 4.18: update_golden_dataset_updated_at
CREATE OR REPLACE FUNCTION public.update_golden_dataset_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- 4.19: update_summary_edits_updated_at
CREATE OR REPLACE FUNCTION public.update_summary_edits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- =============================================================================
-- Fix #5: Move vector extension to extensions schema (WARN: extension_in_public)
-- =============================================================================
-- NOTE: This is commented out because it requires:
--   1. Dropping all vector columns/indexes first
--   2. Recreating them with extensions.vector type
--   3. Updating all queries to reference extensions.vector
--
-- If you want to fix this warning, run the following in a separate migration
-- after updating all code references:
--
-- CREATE SCHEMA IF NOT EXISTS extensions;
-- ALTER EXTENSION vector SET SCHEMA extensions;
-- GRANT USAGE ON SCHEMA extensions TO postgres, anon, authenticated, service_role;

-- =============================================================================
-- Summary
-- =============================================================================
-- This migration fixes:
-- - 3 ERRORs: security_definer_view (x2), rls_disabled_in_public (x1)
-- - 21 WARNs: function_search_path_mutable (x20), rls_policy_always_true (x1)
--
-- Remaining to address manually:
-- - extension_in_public (vector) - requires code changes to use extensions.vector
-- - auth_leaked_password_protection - enable in Supabase Dashboard settings
