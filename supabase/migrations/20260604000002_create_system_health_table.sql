-- system_health: app-wide invariant-audit results (silent-failure detection).
--
-- Every P0/P1 incident in LDIP's history shares one shape: a claimed terminal /
-- success state NOT backed by the data it promises (GAP-2 completed+0-chunks,
-- GAP-3 embedded+NULL-emb, GAP-11 cost "tracked"+0-rows, GAP-23 write "ok"+
-- rejected, GAP-24 pipeline "complete"+0%-verified). The audit_system_invariants
-- beat task asserts `claimed_state => required_data_exists` across a declarative
-- catalog and REPORTS here (it never heals — that complements the silent-healing
-- reconcilers like recover_stuck_documents / sync_citation_statuses_with_resolutions,
-- which fix-and-forget and so leave no evidence that reality drifted).
--
-- One row per invariant (name is PK, upserted on each run) — a single convergence
-- point, deliberately NOT one-row-per-violation (that would be unbounded churn and
-- re-create the matter-scoped two-engine framing of consistency_issues, which is a
-- bad fit for system-wide invariants; see ARCH-001). The latest run overwrites the
-- previous; `sample` holds a few violating ids for triage; a stale `checked_at` is
-- itself an observable signal (the auditor stopped running).

CREATE TABLE IF NOT EXISTS public.system_health (
    name            text PRIMARY KEY,
    severity        text NOT NULL DEFAULT 'warning'
                      CHECK (severity = ANY (ARRAY['critical'::text, 'warning'::text, 'info'::text])),
    ok              boolean NOT NULL DEFAULT true,
    violating_count integer NOT NULL DEFAULT 0,
    sample          jsonb NOT NULL DEFAULT '[]'::jsonb,
    message         text,
    checked_at      timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.system_health IS
  'Latest result per app-wide invariant (silent-failure detection). Written by '
  'audit_system_invariants beat task; read by GET /health/invariants. One row '
  'per invariant name (upserted). ok=false => claimed_state not backed by data.';

-- Service-role only: this is operational/admin data, not matter-scoped user data.
-- The auditor (worker) and the read endpoint both use the service client, which
-- bypasses RLS. Enabling RLS with no anon/authenticated policy denies everyone
-- else by default (consistent with the SEC002 anon-hardening posture).
ALTER TABLE public.system_health ENABLE ROW LEVEL SECURITY;
