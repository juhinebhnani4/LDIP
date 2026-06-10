"""Shared derived-state helpers for Act citation verification.

The definition of "a library Act document is fully embedded" is correctness-
critical and is used in two places that MUST agree:

  1. ``sync_citation_statuses_with_resolutions`` (the RISK-1 reconciler) — gates
     whether to DISPATCH verification for an Act.
  2. ``audit_system_invariants`` (silent-failure detection) — gates whether a
     zero-verified Act is a real violation or is legitimately still embedding.

If those two used different definitions of "fully embedded" they would drift:
the auditor could cry wolf on Acts the reconciler considers not-yet-ready, or
stay silent on Acts the reconciler thinks are done. To keep exactly one
definition (and avoid the ARCH-001 parallel-implementation shape), both import
``act_doc_fully_embedded`` from here.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def act_doc_fully_embedded(
    client,
    lib_doc_id: str | None,
    cache: dict[str, bool] | None = None,
) -> bool:
    """True iff the library Act doc is COMPLETED with >=1 chunk and 0 NULL
    embeddings — the GAP-21 derived-state definition of "fully embedded".

    Verifying against partial embeddings yields false ``section_not_found``
    (RISK-1(b)), so this gate must pass before verification is dispatched, and
    is the same gate the auditor uses to decide an Act *should* have produced
    verified citations by now.

    Args:
        client: Supabase service client.
        lib_doc_id: ``act_resolutions.act_document_id`` (a ``library_documents.id``).
        cache: optional dict reused across calls within one task run to avoid
            re-querying the same Act doc; mutated in place.

    Returns:
        bool — whether the Act is fully embedded.
    """
    if not lib_doc_id:
        return False
    if cache is not None and lib_doc_id in cache:
        return cache[lib_doc_id]

    ok = False
    try:
        doc = (
            client.table("library_documents")
            .select("status")
            .eq("id", lib_doc_id)
            .limit(1)
            .execute()
        )
        if doc.data and doc.data[0].get("status") == "completed":
            total = (
                client.table("library_chunks")
                .select("id", count="exact")
                .eq("library_document_id", lib_doc_id)
                .limit(1)
                .execute()
            )
            if (total.count or 0) > 0:
                null_emb = (
                    client.table("library_chunks")
                    .select("id", count="exact")
                    .eq("library_document_id", lib_doc_id)
                    .is_("embedding", "null")
                    .limit(1)
                    .execute()
                )
                ok = (null_emb.count or 0) == 0
    except Exception as e:
        logger.warning(
            "act_doc_embed_gate_check_failed",
            library_document_id=lib_doc_id,
            error=str(e),
        )
        ok = False

    if cache is not None:
        cache[lib_doc_id] = ok
    return ok


def get_deleted_matter_ids(client) -> set[str]:
    """Return the ids of all soft-deleted matters (``matters.deleted_at`` set).

    Background tasks that read per-matter data (the RISK-1 reconciler and the
    watchman invariants) must DERIVE liveness rather than trust that a delete was
    signalled to every child row. Matter soft-delete only stamps
    ``matters.deleted_at`` — the children (citations have no soft-delete column at
    all) are reclaimed later by the 30-day hard-delete via Postgres ON DELETE
    CASCADE. In that window, any reader keyed on ``matter_id`` that does not
    exclude soft-deleted matters processes "zombie" rows: the reconciler would
    re-dispatch verification for deleted matters and the watchmen would count
    their citations as live invariant violations (PROD-004).

    This is the single shared exclusion gate (sibling to ``act_doc_fully_embedded``
    above) so the reconciler and the auditor exclude the SAME set — avoiding the
    ARCH-001 parallel-implementation shape. Fetched once per task run; callers
    test ``matter_id in get_deleted_matter_ids(client)``.

    Fail-open: on any error returns an empty set (process everything, today's
    behaviour) — never risks excluding a LIVE matter's data from reconciliation.
    """
    deleted: set[str] = set()
    try:
        offset, page = 0, 1000
        while True:
            resp = (
                client.table("matters")
                .select("id")
                .not_.is_("deleted_at", "null")
                .range(offset, offset + page - 1)
                .execute()
            )
            batch = resp.data or []
            if not batch:
                break
            deleted.update(r["id"] for r in batch)
            if len(batch) < page:
                break
            offset += page
    except Exception as e:
        logger.warning("get_deleted_matter_ids_failed", error=str(e))
        return set()
    return deleted
