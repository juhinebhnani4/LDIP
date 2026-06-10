"""GAP-26 L2 data fix — reset wrong 'verified' Companies citations to 'pending'.

Context (see BUGS.md GAP-26 + the choose-solution L2 plan):
  ~213/226 citations 'verified' against the Companies Act **2013** doc are false
  positives — their own text names a 1956-era provision (s.205A/205(C)/206A, the
  unpaid-dividend regime) or the year 1956 / "Indian Companies Act". They got a
  green check because the old section matcher let "205A" match the 2013 Act's
  unrelated section 205 at 100% confidence (no text was ever compared).

What this script does:
  Resets the provably-wrong rows to 'pending' so the RISK-1 reconciler
  (sync_citation_statuses_with_resolutions) RE-DERIVES them through the
  now-fixed indexer (act_indexer._section_core). After re-derivation:
    * "205A"/"205(C)" -> section_not_found (terminal; the 2013 Act has no such
      section) — the false positive is gone.
    * a bare "205" whose text says 1956 may re-verify against 2013's real s.205
      (the L3 residual) — that is EXPECTED and is what the new
      `verified_citation_vintage_mismatch` watchman now flags.

ORDERING (critical — GAP-25 churn-trap safety):
  Deploy the worker WITH the act_indexer fix FIRST, THEN run this with --apply.
  Resetting before the fix is live would just let the reconciler re-verify the
  same wrong rows again. Because the fix drives "205A" to a TERMINAL state
  (section_not_found, in the reconciler's exclude set), there is no
  pending<->terminal churn — the reset is safe and idempotent.

Usage:
    python fix_gap26_reverify_companies.py            # dry-run (default): report only
    python fix_gap26_reverify_companies.py --apply    # perform the reset
"""

from __future__ import annotations

import re
import sys

from app.services.supabase.client import get_service_client


def _wrong_companies_2013_verifications(client) -> tuple[list[dict], list[str]]:
    """Return (rows, doc_ids) of provably-wrong 'verified' Companies-2013 citations.

    Provably-wrong = verified against a 2013 Companies doc AND either:
      * stored section has an alpha suffix (205A / 205A(8) / 205C-form), which the
        2013 Act does not contain — it only coincidentally matched bare 205; or
      * the citation text explicitly names 1956 / "Indian Companies Act".
    The 2013-genuine verifies (real s.205, s.102, s.124, no vintage signal) are
    left untouched so we don't briefly un-verify correct citations.
    """
    docs = (
        client.table("library_documents")
        .select("id, title, year")
        .eq("year", 2013)
        .ilike("title", "%companies%")
        .execute()
    )
    doc_ids = [d["id"] for d in (docs.data or [])]
    if not doc_ids:
        return [], []

    alpha = re.compile(r"[0-9][A-Za-z]")  # 205A, 205A(8)
    vintage_1956 = re.compile(r"\b1956\b|indian\s+companies", re.IGNORECASE)
    paren_letter = re.compile(r"\([A-Za-z]\)")  # 205(C)

    wrong: list[dict] = []
    offset, page = 0, 1000
    while True:
        resp = (
            client.table("citations")
            .select("id, section, act_name, raw_citation_text, verification_status")
            .in_("target_act_document_id", doc_ids)
            .eq("verification_status", "verified")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        for c in batch:
            sec = str(c.get("section") or "")
            raw = str(c.get("raw_citation_text") or "")
            if alpha.search(sec) or paren_letter.search(sec) or vintage_1956.search(raw):
                wrong.append(c)
        if len(batch) < page:
            break
        offset += page
    return wrong, doc_ids


def main(apply: bool) -> None:
    client = get_service_client()
    if client is None:
        print("ERROR: Supabase service client not configured (check env).")
        sys.exit(1)
    wrong, doc_ids = _wrong_companies_2013_verifications(client)

    print(f"2013 Companies doc id(s): {doc_ids}")
    print(f"Provably-wrong 'verified' rows to reset -> pending: {len(wrong)}")
    for c in wrong[:15]:
        print(f"  sec={c.get('section')!r:10} raw={str(c.get('raw_citation_text'))[:55]!r}")
    if len(wrong) > 15:
        print(f"  ... and {len(wrong) - 15} more")

    if not apply:
        print("\nDRY RUN — no rows changed. Re-run with --apply AFTER the worker is")
        print("deployed with the act_indexer fix. The reconciler will re-derive them.")
        return

    ids = [c["id"] for c in wrong]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        client.table("citations").update({"verification_status": "pending"}).in_(
            "id", chunk
        ).execute()
    print(f"\nAPPLIED — reset {len(ids)} citation(s) to 'pending'.")
    print("The RISK-1 reconciler will re-verify them through the fixed indexer on its")
    print("next beat tick. Confirm with the verified_citation_vintage_mismatch watchman.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
