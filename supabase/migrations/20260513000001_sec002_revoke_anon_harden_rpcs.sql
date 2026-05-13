-- SEC-002 A+B+C: Security hardening for Supabase linter warnings
-- A: Revoke PUBLIC + anon EXECUTE on all SECURITY DEFINER functions
-- B: Set search_path on 4 functions missing it
-- C: Revoke access on 3 admin materialized views
-- D: Fix default privileges so future functions don't auto-grant to anon
-- All signatures verified against live database (pg_proc) on 2026-05-13
--
-- KEY INSIGHT: Supabase default setup grants EXECUTE to PUBLIC on all functions
-- in the public schema. REVOKE FROM anon alone is insufficient — must also
-- REVOKE FROM PUBLIC. The =X/postgres ACL entry (PUBLIC grant) takes precedence.

-- ============================================================
-- SEC-002 D: Fix default privileges FIRST (prevents future functions from
-- auto-granting to anon/PUBLIC)
-- ============================================================

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM anon;

-- ============================================================
-- SEC-002 A: REVOKE EXECUTE FROM PUBLIC AND anon on all SECURITY DEFINER functions
-- Safety verification:
--   - handle_new_user is a trigger (runs as owner, not callable via PostgREST)
--   - user_has_matter_access / user_has_storage_access are RLS policy helpers
--   - All others are called from backend via service_role key (bypasses permissions)
--   - Frontend makes zero .rpc() calls
--   - authenticated + service_role retain EXECUTE via their explicit grants
-- ============================================================

-- Simple functions (0-1 args)
REVOKE EXECUTE ON FUNCTION public.auto_assign_matter_owner() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_chunk_metrics() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_evaluation_quality_summary() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_global_chunk_count() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.refresh_unit_economics_views() FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_ab_test_scores(text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_matter_id_from_chunk_path(text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_matter_id_from_storage_path(text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.validate_ocr_chunk_path(text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.validate_storage_document_path(text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.user_has_matter_access(uuid) FROM PUBLIC, anon;

-- 2-arg functions
REVOKE EXECUTE ON FUNCTION public.upsert_act_resolution(uuid, text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_consistency_issue_counts(uuid) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_correction_stats(uuid) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.count_queries_per_matter(uuid[]) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_evaluation_trends(uuid, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_recent_corrections(uuid, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_section_page(uuid, text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_job_queue_stats(uuid) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_monthly_cost_report(integer, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.user_has_storage_access(uuid, text[]) FROM PUBLIC, anon;

-- 3-arg functions
REVOKE EXECUTE ON FUNCTION public.unmerge_entity(uuid, uuid, uuid) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.upsert_matter_memory(uuid, text, jsonb) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.find_library_duplicates(text, integer, double precision) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_or_create_validation_cache(text, text, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.bm25_search_library_chunks(text, uuid, integer) FROM PUBLIC, anon;

-- 4-arg functions
REVOKE EXECUTE ON FUNCTION public.adjust_bbox_text_offsets(uuid, integer, integer, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.merge_entities(uuid, uuid, uuid, uuid) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.resolve_or_create_entity(uuid, text, text, jsonb) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.get_matter_memory_entries(uuid, text, text, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.append_to_matter_memory(uuid, text, text, jsonb) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.append_to_matter_memory(uuid, text, text, jsonb, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.match_library_chunks_for_matter(vector, uuid, integer, double precision) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.match_library_chunks_for_matter_voyage(vector, uuid, integer, double precision) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.semantic_search_chunks_voyage(vector, uuid, double precision, integer) FROM PUBLIC, anon;

-- 5+ arg functions
REVOKE EXECUTE ON FUNCTION public.semantic_search_chunks(vector, uuid, integer) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.semantic_search_chunks(vector, uuid, double precision, integer, text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.match_chunks(vector, integer, uuid, uuid[], text, double precision) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.update_validation_cache(text, text, text, text, text, text, double precision, jsonb) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.bm25_search_chunks(text, uuid, integer, uuid[], text[], integer, integer, uuid[]) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector, uuid, integer, double precision, double precision, integer, text, uuid[], text[], integer, integer, uuid[]) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector, uuid, integer, double precision, double precision, integer, uuid[], text[], integer, integer, uuid[]) FROM PUBLIC, anon;

-- ============================================================
-- SEC-002 B: SET search_path on 4 functions missing it
-- Prevents search_path injection attacks
-- ============================================================

ALTER FUNCTION public.get_consistency_issue_counts(uuid) SET search_path = public;
ALTER FUNCTION public.update_consistency_issues_updated_at() SET search_path = public;
ALTER FUNCTION public.count_queries_per_matter(uuid[]) SET search_path = public;
ALTER FUNCTION public.adjust_bbox_text_offsets(uuid, integer, integer, integer) SET search_path = public;

-- ============================================================
-- SEC-002 C: REVOKE access on admin-only materialized views
-- These are cost/economics views — no frontend or user-facing usage
-- Backend accesses via service_role which bypasses these grants
-- ============================================================

REVOKE ALL ON public.contradiction_savings_report FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.monthly_cogs_by_matter FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.cost_per_document_page FROM PUBLIC, anon, authenticated;
