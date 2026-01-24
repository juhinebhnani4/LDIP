"""Backfill citation page numbers from chunks.

This script updates existing citations with correct source_page and source_bbox_ids
by finding the chunk that contains the citation text.

Usage:
    python scripts/backfill_citation_pages.py [--matter-id MATTER_ID] [--limit N] [--dry-run]

Examples:
    # Backfill all citations (dry run first)
    python scripts/backfill_citation_pages.py --dry-run

    # Backfill only for a specific matter
    python scripts/backfill_citation_pages.py --matter-id 91a4a4db-bc3d-40df-8dcc-49179ac49108

    # Limit to first 10 citations
    python scripts/backfill_citation_pages.py --limit 10
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from rapidfuzz import fuzz

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


def find_page_from_bboxes(citation_text: str, bboxes: list[dict]) -> int | None:
    """Find the actual page number where citation text appears in bboxes.

    When chunks span multiple pages, this finds the exact page.

    Args:
        citation_text: The raw citation text to locate.
        bboxes: List of bounding box dicts with 'text' and 'page_number'.

    Returns:
        Page number where the citation appears, or None if not found.
    """
    if not citation_text or not bboxes:
        return None

    citation_lower = citation_text.lower().strip()

    # Strategy 1: Exact substring match
    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        if citation_lower in bbox_text:
            return bbox.get("page_number")

    # Strategy 2: Key phrase matching (section numbers)
    import re

    section_match = re.search(r"section\s+\d+(?:\s*\([^)]+\))?", citation_lower)
    if section_match:
        section_phrase = section_match.group(0)
        for bbox in bboxes:
            bbox_text = (bbox.get("text") or "").lower()
            if section_phrase in bbox_text:
                return bbox.get("page_number")

    # Strategy 3: Word overlap
    citation_words = set(citation_lower.split())
    if len(citation_words) >= 3:
        best_page = None
        best_overlap = 0
        for bbox in bboxes:
            bbox_text = (bbox.get("text") or "").lower()
            bbox_words = set(bbox_text.split())
            overlap = len(citation_words & bbox_words)
            if overlap > best_overlap and overlap >= 3:
                best_overlap = overlap
                best_page = bbox.get("page_number")
        return best_page

    return None


def find_matching_chunk(citation_text: str, chunks: list[dict], threshold: float = 70.0) -> dict | None:
    """Find the chunk that best matches the citation text.

    Args:
        citation_text: The raw citation text to match
        chunks: List of chunk dicts with content, page_number, bbox_ids
        threshold: Minimum fuzzy match score (0-100)

    Returns:
        Best matching chunk or None if no match above threshold
    """
    if not citation_text or not chunks:
        return None

    best_match = None
    best_score = 0

    # Clean up citation text for matching
    citation_clean = citation_text.lower().strip()

    for chunk in chunks:
        content = chunk.get("content", "").lower()

        # Check if citation text appears in chunk content
        if citation_clean in content:
            # Exact substring match - high confidence
            return chunk

        # Try fuzzy matching for partial matches
        score = fuzz.partial_ratio(citation_clean, content)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = chunk

    return best_match


def backfill_document_citations(document_id: str, client, dry_run: bool = False) -> dict:
    """Backfill citation pages for a single document.

    Args:
        document_id: Document UUID
        client: Supabase client
        dry_run: If True, don't make changes

    Returns:
        Stats dict with counts
    """
    # Get citations for this document that need backfill
    citations_resp = (
        client.table("citations")
        .select("id, raw_citation_text, source_page, source_bbox_ids")
        .eq("source_document_id", document_id)
        .eq("source_page", 1)  # Default value indicates it wasn't set
        .execute()
    )

    citations = citations_resp.data or []

    # Filter to only citations with empty bbox_ids (indicating they weren't properly linked)
    citations_to_update = [
        c for c in citations
        if not c.get("source_bbox_ids") or len(c.get("source_bbox_ids", [])) == 0
    ]

    if not citations_to_update:
        return {"document_id": document_id, "updated": 0, "skipped": True, "total": 0}

    # Get chunks for this document with page numbers
    chunks_resp = (
        client.table("chunks")
        .select("id, content, page_number, bbox_ids, chunk_type")
        .eq("document_id", document_id)
        .not_.is_("page_number", "null")
        .execute()
    )

    chunks = chunks_resp.data or []

    if not chunks:
        return {
            "document_id": document_id,
            "updated": 0,
            "skipped": False,
            "total": len(citations_to_update),
            "reason": "no_chunks_with_pages"
        }

    # Match citations to chunks
    updated_count = 0

    for citation in citations_to_update:
        citation_text = citation.get("raw_citation_text", "")

        if not citation_text:
            continue

        matching_chunk = find_matching_chunk(citation_text, chunks)

        if matching_chunk and matching_chunk.get("page_number"):
            bbox_ids = matching_chunk.get("bbox_ids") or []

            # Try bbox-level page detection for more accuracy
            page_number = matching_chunk["page_number"]  # Default to chunk page
            if bbox_ids:
                try:
                    # Fetch bboxes to find exact page
                    bbox_resp = (
                        client.table("bounding_boxes")
                        .select("id, page_number, text")
                        .in_("id", bbox_ids)
                        .execute()
                    )
                    bboxes = bbox_resp.data or []
                    detected_page = find_page_from_bboxes(citation_text, bboxes)
                    if detected_page is not None:
                        page_number = detected_page
                except Exception:
                    pass  # Fall back to chunk page

            if not dry_run:
                # Update the citation
                client.table("citations").update({
                    "source_page": page_number,
                    "source_bbox_ids": bbox_ids,
                }).eq("id", citation["id"]).execute()

            updated_count += 1
            logger.info(
                "citation_matched",
                citation_id=citation["id"][:8],
                page=page_number,
                bbox_count=len(bbox_ids),
                dry_run=dry_run
            )

    return {
        "document_id": document_id,
        "total": len(citations_to_update),
        "updated": updated_count,
        "skipped": False,
    }


def backfill_all(matter_id: str | None = None, limit: int | None = None, dry_run: bool = False):
    """Backfill citation pages for all documents.

    Args:
        matter_id: Optional matter ID to filter documents
        limit: Optional limit on number of documents to process
        dry_run: If True, don't make changes
    """
    client = get_service_client()

    # Build query for documents
    query = client.table("documents").select("id, filename, matter_id")

    if matter_id:
        query = query.eq("matter_id", matter_id)

    doc_result = query.execute()
    documents = doc_result.data or []

    if not documents:
        print(f"No documents found" + (f" for matter {matter_id}" if matter_id else ""))
        return

    if limit:
        documents = documents[:limit]

    print(f"Found {len(documents)} documents to process" + (" (DRY RUN)" if dry_run else ""))

    # Process each document
    total_updated = 0
    total_citations = 0

    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        filename = doc.get("filename", "unknown")

        print(f"[{i}/{len(documents)}] Processing {filename[:50]}...")

        try:
            result = backfill_document_citations(doc_id, client, dry_run)

            if result["skipped"]:
                print(f"  Skipped (no citations need backfill)")
            elif result.get("reason") == "no_chunks_with_pages":
                print(f"  Skipped (no chunks with page numbers)")
            else:
                print(f"  Updated {result['updated']}/{result['total']} citations")
                total_updated += result["updated"]
                total_citations += result["total"]

        except Exception as e:
            print(f"  Error: {e}")
            logger.exception("backfill_document_failed", document_id=doc_id)

    action = "Would update" if dry_run else "Updated"
    print(f"\nDone! {action} {total_updated} of {total_citations} citations across {len(documents)} documents")


def main():
    parser = argparse.ArgumentParser(description="Backfill citation page numbers from chunks")
    parser.add_argument("--matter-id", help="Filter to specific matter ID")
    parser.add_argument("--limit", type=int, help="Limit number of documents to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just show what would be done")

    args = parser.parse_args()

    backfill_all(matter_id=args.matter_id, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
