"""Audit tool — inspect the citation-verifier's in-memory section index for an Act.

WHY THIS EXISTS (GAP-26 / section-index L1, 2026-06-10):
  Citation verification builds its section index (section_number -> chunk_ids) in
  memory from the Act's chunks and then discards it — nothing persistent to open.
  That made it impossible to answer "what sections does the verifier think this Act
  has?" when auditing the 144 `section_not_found` Companies citations. This script
  rebuilds that exact index on demand (read-only) and prints it, so the verifier's
  view is inspectable without changing the (correct, in-memory) verification path.

  This is the deliberately-small L1. Persisting the index (L2) and unifying it with
  the UI's `section_index` table (L3) are tracked in BUGS.md (GAP-26 follow-ups);
  they are gated on real scale / a reported split-view divergence, not built yet.

READ-ONLY: builds the index via the SAME ActIndexer the verifier uses. Writes nothing.

Usage:
    python audit_act_index.py <act_document_id>                 # list all sections
    python audit_act_index.py <act_document_id> --section 205A  # check one section
    python audit_act_index.py <act_document_id> --section 21
"""

from __future__ import annotations

import asyncio
import sys

from app.engines.citation.act_indexer import ActIndexerError, get_act_indexer
from app.services.supabase.client import get_service_client


def _act_title(client, doc_id: str) -> str:
    for table, label in (("library_documents", "library"), ("documents", "matter")):
        col = "title" if table == "library_documents" else "filename"
        resp = client.table(table).select(col).eq("id", doc_id).limit(1).execute()
        if resp.data:
            return f"{resp.data[0].get(col)!r} ({label})"
    return "<unknown doc>"


async def main(doc_id: str, section: str | None) -> None:
    client = get_service_client()
    if client is None:
        print("ERROR: Supabase service client not configured.")
        sys.exit(1)

    title = _act_title(client, doc_id)
    print(f"Act document: {doc_id}\n  title: {title}\n")

    indexer = get_act_indexer()
    try:
        index = await indexer.index_act_document(doc_id, matter_id="audit")
    except ActIndexerError as e:
        print(f"NOT INDEXABLE — {e}")
        print("(The verifier would return ACT_UNAVAILABLE for every citation here.)")
        return

    sections = sorted(index.sections.keys(), key=lambda s: (len(s), s))
    total_chunks = len(index.chunks_by_id)
    print(f"Sections the verifier sees: {len(sections)}  (over {total_chunks} chunks)")
    print("  " + ", ".join(sections) if sections else "  <none>")

    if section is not None:
        print(f"\n--- Checking section {section!r} ---")
        chunks = await indexer.get_section_chunks(doc_id, section)
        if chunks:
            print(f"PRESENT — matched {len(chunks)} chunk(s). First 200 chars:")
            text = (chunks[0].content or "")[:200].replace("\n", " ")
            # Console-safe: Windows cp1252 can't encode chars like U+2033 (the
            # double-prime in legal text); strip to the console's encoding.
            enc = sys.stdout.encoding or "utf-8"
            print("  " + text.encode(enc, errors="replace").decode(enc))
        else:
            print(
                f"NOT FOUND — section {section!r} is not in this Act's index. "
                "A citation to it would correctly verify as 'section_not_found'."
            )


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: python audit_act_index.py <act_document_id> [--section <NNN>]")
        sys.exit(1)
    sec = None
    if "--section" in sys.argv:
        i = sys.argv.index("--section")
        if i + 1 < len(sys.argv):
            sec = sys.argv[i + 1]
    asyncio.run(main(args[0], sec))
