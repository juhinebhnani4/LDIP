"""App-wide invariant catalog for silent-failure detection.

Every P0/P1 incident in LDIP's history is the same shape: a *claimed terminal /
success state not backed by the data it promises*:

    GAP-2   documents.status='completed'        but 0 chunks
    GAP-3   library doc 'embedded'              but chunks have NULL embeddings
    GAP-11  cost "tracked"                       but 0 llm_costs rows
    GAP-23  citation write "ok"                  but rejected by CHECK constraint
    GAP-24  Act pipeline "complete"              but 0% of its citations verified

This is the inverse of ARCH-003: instead of deriving state from reality, the
system *claims* a state and trusts convention to keep reality in step. The cure
is one continuous audit that asserts ``claimed_state => required_data_exists``
and REPORTS violations (it never heals — healing is the job of the reconcilers,
which fix-and-forget and so hide drift).

Each invariant is a Python ``check`` callable that returns the rows VIOLATING it
(claim success, lack the data). ``violating_count == 0`` means healthy.

WHY ALL-PYTHON (not SQL strings): two constraints, both verified live 2026-06-04.
  1. The flagship GAP-24 invariant's citation->Act join needs
     ``normalize_act_name`` (abbreviation/backronym resolution). A lower/trim SQL
     approximation matched ZERO rows — i.e. it would be a dead guard that always
     reports "healthy".
  2. There is no clean raw-SQL execution path in the app runtime: no exec_sql
     RPC (and a generic one contradicts the SEC002 RPC-hardening), and DATABASE_URL
     is not surfaced in config. The ONLY DB-access path is the Supabase/postgrest
     client. So every invariant runs through that one client — adding a second
     DB-access path just to run audit SQL would be its own architectural smell.

To add a new invariant: write a ``_check_*`` function returning an
``InvariantResult`` and append one ``Invariant`` to ``INVARIANTS``. New shape =
new row, never a new code path in the runner or the beat task.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# Max violating ids stored in system_health.sample (triage hint, not a full list).
SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class InvariantResult:
    """Outcome of evaluating one invariant against the live DB."""

    violating_count: int
    sample: list = field(default_factory=list)
    message: str = ""


# A check callable takes the Supabase service client and returns an InvariantResult.
CheckFn = Callable[[object], InvariantResult]


@dataclass(frozen=True)
class Invariant:
    """One assertion of the form `claimed_state => required_data_exists`.

    ``check`` is a Python callable taking the Supabase service client and
    returning an ``InvariantResult`` of the violating rows.
    """

    name: str
    severity: str  # 'critical' | 'warning' | 'info'
    description: str
    check: CheckFn


# =============================================================================
# Check implementations
# =============================================================================


def _check_completed_docs_zero_chunks(client) -> InvariantResult:
    """GAP-2: a document the pipeline marked 'completed' must have produced chunks.

    'act' documents chunk into library_chunks (not chunks), so they are excluded
    — a completed Act legitimately has 0 rows in `chunks`.
    """
    docs = (
        client.table("documents")
        .select("id, filename, document_type")
        .is_("deleted_at", "null")
        .eq("status", "completed")
        .neq("document_type", "act")
        .execute()
    )
    violations = []
    for d in docs.data or []:
        cnt = (
            client.table("chunks")
            .select("id", count="exact")
            .eq("document_id", d["id"])
            .limit(1)
            .execute()
        )
        if (cnt.count or 0) == 0:
            violations.append({"document_id": d["id"], "filename": d.get("filename")})
    msg = ""
    if violations:
        msg = f"{len(violations)} document(s) marked 'completed' have 0 chunks (GAP-2 shape)."
    return InvariantResult(len(violations), violations[:SAMPLE_LIMIT], msg)


def _check_embedded_library_docs_null_embeddings(client) -> InvariantResult:
    """GAP-3: a library doc marked 'completed' (embedded) must not have any chunk
    with a NULL embedding — that is a partially-embedded Act masquerading as done.

    Derived from reality: find library_chunks with NULL embedding, dedupe to their
    library_document_id, then keep only those whose doc claims status='completed'.
    """
    null_doc_ids: set[str] = set()
    offset, page = 0, 1000
    while True:
        resp = (
            client.table("library_chunks")
            .select("library_document_id")
            .is_("embedding", "null")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        for r in batch:
            if r.get("library_document_id"):
                null_doc_ids.add(r["library_document_id"])
        if len(batch) < page:
            break
        offset += page

    violations = []
    for doc_id in null_doc_ids:
        doc = (
            client.table("library_documents")
            .select("id, title, status")
            .eq("id", doc_id)
            .limit(1)
            .execute()
        )
        if doc.data and str(doc.data[0].get("status", "")).lower() == "completed":
            violations.append(
                {"library_document_id": doc_id, "title": doc.data[0].get("title")}
            )
    msg = ""
    if violations:
        msg = (
            f"{len(violations)} library doc(s) marked 'completed' have chunks with NULL "
            f"embeddings (GAP-3 shape)."
        )
    return InvariantResult(len(violations), violations[:SAMPLE_LIMIT], msg)


def _check_acts_resolved_embedded_zero_verified(client) -> InvariantResult:
    """Flagship (GAP-24): a resolved (act_resolutions available/auto_fetched) AND
    fully-embedded Act SHOULD have verified citations. If it has >=1 citation still
    ``pending`` and ZERO verified, verification fired but never converged — the exact
    silent failure where the pipeline reports "complete" at 0% verified.

    Carved known-good (or this cries wolf — see false_section_not_found memory):
      * ``act_unavailable`` citations are EXCLUDED. They are legitimate when the Act
        is not (yet) uploaded — e.g. doc a65f4b17, whose 867 citations are correctly
        act_unavailable. Only ``pending`` (Act IS available, verification owed) counts.
      * The Act must be FULLY embedded (shared act_doc_fully_embedded gate). An Act
        mid-embedding legitimately has 0 verified — not a violation.
      * Only ``pending`` citations older than the grace window count, so an Act
        uploaded seconds ago (normal verification latency) does not alarm.

    Reuses the SAME join/normalisation/embed-gate as the RISK-1 reconciler
    (sync_citation_statuses_with_resolutions) so the auditor and the dispatcher
    agree on which (matter, Act) pairs are "owed verification".
    """
    from datetime import UTC, datetime, timedelta

    from app.engines.citation.abbreviations import normalize_act_name
    from app.services.act_verification_state import act_doc_fully_embedded

    GRACE_MINUTES = 60
    cutoff = (datetime.now(UTC) - timedelta(minutes=GRACE_MINUTES)).isoformat()
    embed_cache: dict[str, bool] = {}

    resolutions = (
        client.table("act_resolutions")
        .select("matter_id, act_name_normalized, act_name_display, act_document_id")
        .not_.is_("act_document_id", "null")
        .in_("resolution_status", ["available", "auto_fetched"])
        .execute()
    )

    # matter_id -> {normalized_act_name: act_document_id}
    by_matter: dict[str, dict[str, str]] = {}
    for r in resolutions.data or []:
        by_matter.setdefault(r["matter_id"], {})[r["act_name_normalized"]] = r[
            "act_document_id"
        ]

    violations: list[dict] = []

    for matter_id, norm_to_doc in by_matter.items():
        verified_norms: set[str] = set()
        pending_norms: set[str] = set()
        offset, page = 0, 1000
        while True:
            resp = (
                client.table("citations")
                .select("act_name, verification_status, updated_at")
                .eq("matter_id", matter_id)
                .in_("verification_status", ["verified", "pending"])
                .range(offset, offset + page - 1)
                .execute()
            )
            batch = resp.data or []
            if not batch:
                break
            for c in batch:
                norm = normalize_act_name(c.get("act_name", ""))
                if norm not in norm_to_doc:
                    continue
                status = c.get("verification_status")
                if status == "verified":
                    verified_norms.add(norm)
                elif status == "pending" and (c.get("updated_at") or "") < cutoff:
                    pending_norms.add(norm)
            if len(batch) < page:
                break
            offset += page

        for norm in pending_norms - verified_norms:
            act_doc_id = norm_to_doc[norm]
            if not act_doc_fully_embedded(client, act_doc_id, cache=embed_cache):
                continue
            violations.append(
                {"matter_id": matter_id, "act_document_id": act_doc_id, "act": norm}
            )

    msg = ""
    if violations:
        msg = (
            f"{len(violations)} fully-embedded resolved Act(s) have pending citations "
            f"(>{GRACE_MINUTES}m) but ZERO verified — verification dispatched but not converging "
            f"(GAP-24 shape)."
        )
    return InvariantResult(len(violations), violations[:SAMPLE_LIMIT], msg)


def _check_verified_citation_vintage_mismatch(client) -> InvariantResult:
    """GAP-26 / L3-trigger: a citation marked ``verified`` must not be verified
    against an Act document whose vintage (year) contradicts the year the citation
    itself names. "s.205 of the Companies Act, 1956" verified against the 2013 Act
    is a false positive — the section numbers coincide but the provisions do not.

    This is the residual the GAP-26 L2 section-match fix CANNOT catch: the citation
    resolved to the wrong-VINTAGE document. The clean structural cure is L3
    (vintage-safe binding in the resolver); until then this invariant makes the
    residual VISIBLE instead of letting it hide for months (the GAP-2/3/11/23/24
    pattern). A non-zero, growing count is the agreed trigger to do L3.

    Conservative by design (an invariant that cries wolf gets ignored): it fires
    ONLY when the citation text carries an EXPLICIT 4-digit year that differs from
    the target doc's ``year``. A citation that names no year is never guessed at,
    and a target doc with no recorded ``year`` is skipped (cannot assert).
    """
    import re

    YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
    doc_year: dict[str, object] = {}

    def _target_year(doc_id: str):
        if doc_id not in doc_year:
            resp = (
                client.table("library_documents")
                .select("year")
                .eq("id", doc_id)
                .limit(1)
                .execute()
            )
            doc_year[doc_id] = resp.data[0].get("year") if resp.data else None
        return doc_year[doc_id]

    violations: list[dict] = []
    offset, page = 0, 1000
    while True:
        resp = (
            client.table("citations")
            .select(
                "id, matter_id, act_name_original, raw_citation_text, "
                "target_act_document_id"
            )
            .eq("verification_status", "verified")
            .not_.is_("target_act_document_id", "null")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        for c in batch:
            ty = _target_year(c["target_act_document_id"])
            if ty is None:
                continue  # doc has no recorded vintage -> cannot assert mismatch
            # Read the citation's ORIGINAL claim only. ``act_name`` is the
            # POST-resolution name (it already carries the wrong binding's year, e.g.
            # "Companies Act, 2013") and would mask the mismatch; ``act_name_original``
            # + ``raw_citation_text`` carry the year the citation actually names.
            # quoted_text is excluded to keep incidental years out of the signal.
            text = " ".join(
                str(c.get(f) or "")
                for f in ("act_name_original", "raw_citation_text")
            )
            years = {int(y) for y in YEAR.findall(text)}
            if years and int(ty) not in years:
                violations.append(
                    {
                        "citation_id": c["id"],
                        "matter_id": c.get("matter_id"),
                        "cited_years": sorted(years),
                        "verified_against_year": int(ty),
                    }
                )
        if len(batch) < page:
            break
        offset += page

    msg = ""
    if violations:
        msg = (
            f"{len(violations)} citation(s) marked 'verified' against an Act of a "
            f"DIFFERENT year than the citation names (GAP-26 wrong-vintage; L3 trigger)."
        )
    return InvariantResult(len(violations), violations[:SAMPLE_LIMIT], msg)


def _check_verified_section_token_mismatch(client) -> InvariantResult:
    """GAP-26 sibling (2026-06-10): a citation marked ``verified`` whose stored
    ``section`` disagrees with the section token in its OWN ``raw_citation_text``
    was verified against the wrong provision because extraction corrupted the
    section ("Section 205(C)…" stored as ``205`` → falsely verified against the
    2013 Act's §205). The year-based ``verified_citation_vintage_mismatch`` watchman
    is blind to these (the citation names no year), so this is its complement.

    Conservative: fires only when raw_citation_text clearly contains a section token
    that canonicalizes DIFFERENTLY from the stored section. Properly-extracted
    citations (stored section already == canonical raw token) never fire.
    """
    from app.engines.citation.extractor import _RAW_SECTION_RE, canonicalize_section

    violations: list[dict] = []
    offset, page = 0, 1000
    while True:
        resp = (
            client.table("citations")
            .select("id, matter_id, section, raw_citation_text")
            .eq("verification_status", "verified")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        for c in batch:
            raw = c.get("raw_citation_text") or ""
            # Collect EVERY section identity in the raw text — a citation's raw can
            # name multiple sections ("Sec.3(3) r/w Sec.13"), and the stored section
            # legitimately equals any one of them. Comparing IDENTITIES (canonicalize
            # both sides) avoids flagging cosmetic forms ("138(1)" vs "138").
            raw_ids = {
                canonicalize_section(mm.group(1))[0]
                for mm in _RAW_SECTION_RE.finditer(raw)
            }
            stored_id = canonicalize_section((c.get("section") or "").strip())[0]
            # Flag only when the stored section matches NONE of the raw's sections —
            # i.e. it was corrupted (raw "205A" but stored bare "205").
            if raw_ids and stored_id and stored_id not in raw_ids:
                violations.append(
                    {
                        "citation_id": c["id"],
                        "matter_id": c.get("matter_id"),
                        "raw_sections": sorted(raw_ids),
                        "stored_section": c.get("section"),
                    }
                )
        if len(batch) < page:
            break
        offset += page

    msg = ""
    if violations:
        msg = (
            f"{len(violations)} citation(s) 'verified' whose stored section differs "
            f"from the section in their raw text (extraction-corruption false positive)."
        )
    return InvariantResult(len(violations), violations[:SAMPLE_LIMIT], msg)


# =============================================================================
# The catalog — append one Invariant per shape. New shape = new row, not new code.
# =============================================================================

INVARIANTS: list[Invariant] = [
    Invariant(
        name="completed_docs_zero_chunks",
        severity="critical",
        description="documents.status='completed' (non-act) but no rows in chunks (GAP-2).",
        check=_check_completed_docs_zero_chunks,
    ),
    Invariant(
        name="embedded_library_docs_null_embeddings",
        severity="critical",
        description="library_documents.status='completed' but >=1 library_chunk has NULL embedding (GAP-3).",
        check=_check_embedded_library_docs_null_embeddings,
    ),
    Invariant(
        name="acts_resolved_embedded_zero_verified",
        severity="critical",
        description="Resolved + fully-embedded Act with pending citations (>1h) but 0 verified (GAP-24).",
        check=_check_acts_resolved_embedded_zero_verified,
    ),
    Invariant(
        name="verified_citation_vintage_mismatch",
        severity="warning",
        description="Citation 'verified' against an Act of a different year than it names (GAP-26 wrong-vintage; L3 trigger).",
        check=_check_verified_citation_vintage_mismatch,
    ),
    Invariant(
        name="verified_section_token_mismatch",
        severity="warning",
        description="Citation 'verified' whose stored section differs from its raw-text section (extraction-corruption false positive; GAP-26 sibling).",
        check=_check_verified_section_token_mismatch,
    ),
]


def run_invariant(client, inv: Invariant) -> dict:
    """Evaluate one invariant; never raises. Returns a system_health-shaped dict."""
    try:
        result = inv.check(client)
        return {
            "name": inv.name,
            "severity": inv.severity,
            "ok": result.violating_count == 0,
            "violating_count": result.violating_count,
            "sample": result.sample,
            "message": result.message or inv.description,
        }
    except Exception as e:
        # An invariant that errors is itself a signal (don't let it silently
        # vanish) — record it as not-ok with severity 'warning' so the dashboard
        # shows the audit couldn't evaluate this assertion.
        logger.warning("invariant_check_failed", invariant=inv.name, error=str(e))
        return {
            "name": inv.name,
            "severity": "warning",
            "ok": False,
            "violating_count": -1,
            "sample": [],
            "message": f"invariant check errored: {e}",
        }


def run_all_invariants(client) -> list[dict]:
    """Evaluate the full catalog. Returns one system_health-shaped dict per entry."""
    return [run_invariant(client, inv) for inv in INVARIANTS]
