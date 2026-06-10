"""GAP-28 backfill — repair citations whose stored section was corrupted by the
old digit-only extraction regex, then re-verify the ones that falsely verified.

Context (BUGS.md GAP-28 + docs/PROD-FINDINGS-2026-06-10.md): the old regex stored
"Section 205A…" as section="205" and "Section 205(C)…" as "205". Where such a
citation resolved to a library Act, it FALSELY verified against that Act's real
§205. The `verified_section_token_mismatch` watchman counts the live population
(~146). The L2 code fix only prevents NEW corruption — this repairs existing rows.

What it does (mirrors the GAP-26 data fix; churn-safe):
  1. Find citations whose raw_citation_text section token canonicalizes to a
     DIFFERENT value than the stored `section`, on the SAME base number
     (e.g. raw "205A"/"205(C)" but stored "205").
  2. Repair section/subsection/clause to the canonical value.
  3. For any that were `verified`, reset to `pending` (repairing alone would hide
     the false positive from the watchman while leaving the wrong verdict) and
     re-trigger verify_citations_for_act so they reach the correct verdict
     (205A/205C -> section_not_found against the 2013 Act).

ORDERING: deploy the worker WITH the L2 fix FIRST (so re-verification runs the
fixed indexer + canonicalize_section), THEN run this with --apply.

Usage:
    python backfill_gap28_repair_sections.py            # dry-run (default)
    python backfill_gap28_repair_sections.py --apply
"""

from __future__ import annotations

import sys

from app.engines.citation.extractor import _RAW_SECTION_RE, canonicalize_section
from app.services.supabase.client import get_service_client


def _base(s: str) -> str:
    import re

    m = re.match(r"\d+", s or "")
    return m.group(0) if m else ""


def _find_corrupted(client) -> list[dict]:
    """Rows where the raw-text section identity differs from stored `section`
    on the same base number (a dropped suffix/uppercase-paren)."""
    out: list[dict] = []
    offset, page = 0, 1000
    while True:
        resp = (
            client.table("citations")
            .select(
                "id, matter_id, act_name, section, subsection, clause, "
                "raw_citation_text, verification_status, target_act_document_id"
            )
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        for c in batch:
            m = _RAW_SECTION_RE.search(c.get("raw_citation_text") or "")
            if not m:
                continue
            sec, sub, cl = canonicalize_section(m.group(1))
            stored = (c.get("section") or "").strip()
            stored_id = canonicalize_section(stored)[0]
            # Repair only a TRUE identity corruption (bare "205" lost its "205A"
            # suffix), on the same base number. Skip cosmetic paren-normalisations
            # ("3(3)"/"205(C)" already canonicalize correctly via the verifier).
            if sec and sec != stored_id and _base(sec) == _base(stored):
                c["_fix"] = {"section": sec, "subsection": sub, "clause": cl}
                out.append(c)
        if len(batch) < page:
            break
        offset += page
    return out


def main(apply: bool) -> None:
    client = get_service_client()
    if client is None:
        print("ERROR: Supabase service client not configured.")
        sys.exit(1)

    rows = _find_corrupted(client)
    verified = [r for r in rows if r.get("verification_status") == "verified"]
    print(f"Corrupted-section citations to repair: {len(rows)}")
    print(f"  of which currently 'verified' (need re-verify): {len(verified)}")
    for r in rows[:15]:
        print(
            f"  {str(r['section'])!r:8} -> {r['_fix']['section']!r:8} "
            f"[{r['verification_status']:16}] raw={str(r['raw_citation_text'])[:42]!r}"
        )
    if len(rows) > 15:
        print(f"  ... and {len(rows) - 15} more")

    # (matter, act_name, doc) tuples to re-trigger (verified rows with a target doc)
    tuples = sorted(
        {
            (r["matter_id"], r.get("act_name") or "", r["target_act_document_id"])
            for r in verified
            if r.get("target_act_document_id")
        }
    )
    print(f"\nRe-verification tuples (matter, act, doc): {len(tuples)}")

    if not apply:
        print("\nDRY RUN — no changes. Re-run with --apply AFTER the worker is deployed.")
        return

    # 1) Repair section/subsection/clause; reset verified -> pending.
    for r in rows:
        update = dict(r["_fix"])
        if r.get("verification_status") == "verified":
            update["verification_status"] = "pending"
        client.table("citations").update(update).eq("id", r["id"]).execute()
    print(f"\nAPPLIED — repaired {len(rows)} citation(s); reset {len(verified)} to pending.")

    # 2) Re-trigger verification through the deployed (fixed) worker.
    from app.workers.tasks.verification_tasks import verify_citations_for_act

    for matter_id, act_name, doc_id in tuples:
        verify_citations_for_act.apply_async(
            kwargs={
                "matter_id": matter_id,
                "act_name": act_name,
                "act_document_id": doc_id,
            },
            queue="default",
        )
        print(f"  dispatched verify: matter={matter_id[:8]} act={act_name!r}")
    print(
        "\nDone. Re-verification re-derives verdicts (205A/205C -> section_not_found). "
        "Confirm: verified_section_token_mismatch watchman should drop toward 0."
    )


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
