"""Backfill section index for existing Act documents.

This script indexes sections for Act documents that were processed
before section indexing was implemented.

Usage:
    python scripts/backfill_section_index.py [--matter-id MATTER_ID] [--limit N] [--dry-run]

Examples:
    # Backfill all Act documents (dry run)
    python scripts/backfill_section_index.py --dry-run

    # Backfill only for a specific matter
    python scripts/backfill_section_index.py --matter-id 91a4a4db-bc3d-40df-8dcc-49179ac49108

    # Limit to first 5 documents
    python scripts/backfill_section_index.py --limit 5
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from app.services.supabase.client import get_service_client
from app.services.section_index_service import SectionIndexService

logger = structlog.get_logger(__name__)


def backfill_all(matter_id: str | None = None, limit: int | None = None, dry_run: bool = False):
    """Backfill section index for Act documents.

    Args:
        matter_id: Optional matter ID to filter documents
        limit: Optional limit on number of documents to process
        dry_run: If True, don't make changes
    """
    client = get_service_client()
    section_service = SectionIndexService(client)

    # Get Act documents that have bounding boxes (i.e., have been OCR'd)
    query = (
        client.table("documents")
        .select("id, filename, matter_id")
        .eq("document_type", "act")
    )

    if matter_id:
        query = query.eq("matter_id", matter_id)

    doc_result = query.execute()
    documents = doc_result.data or []

    if not documents:
        print(f"No Act documents found" + (f" for matter {matter_id}" if matter_id else ""))
        return

    # Filter to documents with bounding boxes
    docs_with_bboxes = []
    for doc in documents:
        bbox_count = (
            client.table("bounding_boxes")
            .select("id", count="exact")
            .eq("document_id", doc["id"])
            .execute()
        )
        if bbox_count.count and bbox_count.count > 0:
            docs_with_bboxes.append(doc)

    if not docs_with_bboxes:
        print("No Act documents with bounding boxes found")
        return

    if limit:
        docs_with_bboxes = docs_with_bboxes[:limit]

    print(f"Found {len(docs_with_bboxes)} Act documents to index" + (" (DRY RUN)" if dry_run else ""))

    # Process each document
    total_sections = 0

    for i, doc in enumerate(docs_with_bboxes, 1):
        doc_id = doc["id"]
        filename = doc.get("filename", "unknown")
        doc_matter_id = doc.get("matter_id")

        print(f"\n[{i}/{len(docs_with_bboxes)}] {filename[:60]}...")

        # Check if already indexed
        existing = (
            client.table("section_index")
            .select("id", count="exact")
            .eq("document_id", doc_id)
            .execute()
        )

        if existing.count and existing.count > 0:
            print(f"  Already indexed ({existing.count} sections)")
            continue

        if dry_run:
            print("  Would index sections (dry run)")
            continue

        try:
            section_count = section_service.index_document_sections(
                document_id=doc_id,
                matter_id=doc_matter_id,
            )

            print(f"  Indexed {section_count} sections")
            total_sections += section_count

        except Exception as e:
            print(f"  Error: {e}")
            logger.exception("backfill_document_failed", document_id=doc_id)

    action = "Would index" if dry_run else "Indexed"
    print(f"\nDone! {action} {total_sections} sections across {len(docs_with_bboxes)} documents")


def main():
    parser = argparse.ArgumentParser(description="Backfill section index for Act documents")
    parser.add_argument("--matter-id", help="Filter to specific matter ID")
    parser.add_argument("--limit", type=int, help="Limit number of documents to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just show what would be done")

    args = parser.parse_args()

    backfill_all(matter_id=args.matter_id, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
