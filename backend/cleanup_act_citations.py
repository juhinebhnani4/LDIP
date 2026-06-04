#!/usr/bin/env python3
"""Cleanup script to delete citations extracted from Act documents.

Citations should only be extracted from case files, not from Act documents.
This script identifies and deletes citations where the source document
has document_type = 'act'.

Usage:
    # Dry run (default) - shows what would be deleted
    python cleanup_act_citations.py

    # Actually delete the citations
    python cleanup_act_citations.py --execute
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.supabase.client import get_service_client


def get_citations_from_act_documents(client):
    """Find all citations where the source document is an Act."""
    # Get all documents with type 'act'
    act_docs_result = (
        client.table("documents")
        .select("id, filename, matter_id")
        .eq("document_type", "act")
        .execute()
    )

    act_doc_ids = [doc["id"] for doc in (act_docs_result.data or [])]

    if not act_doc_ids:
        return [], []

    # Get citations from these Act documents
    citations_to_delete = []
    for doc_id in act_doc_ids:
        citations_result = (
            client.table("citations")
            .select("id, act_name, section, source_document_id, matter_id")
            .eq("source_document_id", doc_id)
            .execute()
        )
        if citations_result.data:
            citations_to_delete.extend(citations_result.data)

    return citations_to_delete, act_docs_result.data or []


def delete_citations(client, citation_ids: list[str]) -> int:
    """Delete citations by ID."""
    if not citation_ids:
        return 0

    deleted_count = 0
    # Delete in batches to avoid query size limits
    batch_size = 100
    for i in range(0, len(citation_ids), batch_size):
        batch = citation_ids[i : i + batch_size]
        result = client.table("citations").delete().in_("id", batch).execute()
        deleted_count += len(result.data) if result.data else len(batch)

    return deleted_count


def main():
    parser = argparse.ArgumentParser(
        description="Delete citations extracted from Act documents"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the citations (default is dry run)",
    )
    args = parser.parse_args()

    client = get_service_client()
    if not client:
        print("ERROR: Could not connect to database")
        sys.exit(1)

    print("Finding citations extracted from Act documents...")
    citations, act_docs = get_citations_from_act_documents(client)

    if not citations:
        print("No citations found from Act documents. Nothing to clean up.")
        sys.exit(0)

    print(f"\nFound {len(citations)} citations from {len(act_docs)} Act documents:\n")

    # Group by source document for display
    by_document: dict[str, list] = {}
    for citation in citations:
        doc_id = citation["source_document_id"]
        if doc_id not in by_document:
            by_document[doc_id] = []
        by_document[doc_id].append(citation)

    for doc_id, doc_citations in by_document.items():
        # Find document info
        doc_info = next((d for d in act_docs if d["id"] == doc_id), None)
        doc_name = doc_info["filename"] if doc_info else "Unknown"
        print(f"  Source Act: {doc_name}")
        print(f"    Citations: {len(doc_citations)}")
        # Show first few citations
        for c in doc_citations[:3]:
            print(f"      - {c['act_name']} Section {c['section']}")
        if len(doc_citations) > 3:
            print(f"      ... and {len(doc_citations) - 3} more")
        print()

    if args.execute:
        print("Deleting citations...")
        citation_ids = [c["id"] for c in citations]
        deleted = delete_citations(client, citation_ids)
        print(f"\nDeleted {deleted} citations from Act documents.")
    else:
        print("=" * 60)
        print("DRY RUN - No changes made.")
        print(f"Run with --execute to delete {len(citations)} citations.")
        print("=" * 60)


if __name__ == "__main__":
    main()
