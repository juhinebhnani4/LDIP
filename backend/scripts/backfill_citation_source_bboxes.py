"""Backfill script to populate source_bbox_ids for citations.

This script finds citations missing source_bbox_ids and links them to
bounding boxes in the source document that contain the citation text.

Usage:
    python scripts/backfill_citation_source_bboxes.py [--dry-run] [--matter-id UUID]
"""

import asyncio
import os
import sys
from collections import Counter
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from rapidfuzz import fuzz
from supabase import create_client

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return " ".join(text.lower().split())


def find_matching_bboxes(
    citation_text: str,
    page_bboxes: list[dict],
    max_bboxes: int = 20,
    min_overlap_words: int = 2,
) -> list[str]:
    """Find bboxes that contain parts of the citation text.

    Args:
        citation_text: The raw citation text to match
        page_bboxes: Bboxes on the same page as the citation
        max_bboxes: Maximum number of bboxes to return
        min_overlap_words: Minimum word overlap for a match

    Returns:
        List of matching bbox IDs
    """
    if not citation_text or not page_bboxes:
        return []

    citation_normalized = normalize_text(citation_text)
    citation_words = set(citation_normalized.split())

    # Score each bbox by word overlap
    scored_bboxes: list[tuple[dict, int]] = []

    for bbox in page_bboxes:
        bbox_text = bbox.get("text", "")
        if not bbox_text:
            continue

        bbox_normalized = normalize_text(bbox_text)
        bbox_words = set(bbox_normalized.split())

        # Count word overlap
        overlap = citation_words & bbox_words
        overlap_count = len(overlap)

        if overlap_count >= min_overlap_words:
            scored_bboxes.append((bbox, overlap_count))

    # Sort by overlap count descending
    scored_bboxes.sort(key=lambda x: x[1], reverse=True)

    # Return top matching bbox IDs
    matched_ids = []
    for bbox, _ in scored_bboxes[:max_bboxes]:
        bbox_id = bbox.get("id")
        if bbox_id:
            matched_ids.append(bbox_id)

    return matched_ids


def find_matching_bboxes_fuzzy(
    citation_text: str,
    page_bboxes: list[dict],
    max_bboxes: int = 15,
    score_threshold: int = 60,
) -> list[str]:
    """Find bboxes using fuzzy text matching.

    Uses sliding window to find sequence of bboxes that best match citation.

    Args:
        citation_text: The raw citation text to match
        page_bboxes: Bboxes on the same page as the citation
        max_bboxes: Maximum number of bboxes to return
        score_threshold: Minimum fuzzy match score (0-100)

    Returns:
        List of matching bbox IDs
    """
    if not citation_text or not page_bboxes:
        return []

    citation_normalized = normalize_text(citation_text)

    # Pre-normalize bbox texts
    bbox_texts = [normalize_text(bbox.get("text", "")) for bbox in page_bboxes]

    # Try sliding window of various sizes
    best_score = 0
    best_start = -1
    best_window = 5

    for window_size in [5, 10, 15, 20]:
        if window_size > len(page_bboxes):
            continue

        for start_idx in range(len(page_bboxes) - window_size + 1):
            window_text = " ".join(bbox_texts[start_idx:start_idx + window_size])
            score = fuzz.partial_ratio(citation_normalized[:200], window_text[:500])

            if score > best_score:
                best_score = score
                best_start = start_idx
                best_window = window_size

            if score >= 90:
                break

    # If good match found, return those bboxes
    if best_score >= score_threshold and best_start >= 0:
        matched_ids = []
        end_idx = min(best_start + best_window, len(page_bboxes))

        for idx in range(best_start, end_idx):
            bbox = page_bboxes[idx]
            bbox_id = bbox.get("id")
            if bbox_id:
                matched_ids.append(bbox_id)

            if len(matched_ids) >= max_bboxes:
                break

        return matched_ids

    return []


async def get_citations_missing_bboxes(matter_id: str | None = None) -> list[dict]:
    """Get citations that have empty source_bbox_ids."""
    query = supabase.table("citations").select(
        "id, source_document_id, source_page, raw_citation_text, source_bbox_ids"
    ).or_("source_bbox_ids.is.null,source_bbox_ids.eq.{}")

    if matter_id:
        query = query.eq("matter_id", matter_id)

    response = query.limit(1000).execute()
    return response.data or []


async def get_bboxes_for_document_page(
    document_id: str,
    page_number: int,
) -> list[dict]:
    """Get all bboxes for a document on a specific page."""
    response = supabase.table("bounding_boxes").select(
        "id, text, page_number, x, y, width, height"
    ).eq("document_id", document_id).eq("page_number", page_number).order(
        "y"
    ).order("x").limit(500).execute()

    return response.data or []


async def update_citation_source_bboxes(
    citation_id: str,
    bbox_ids: list[str],
) -> bool:
    """Update a citation with source_bbox_ids."""
    try:
        response = supabase.table("citations").update({
            "source_bbox_ids": bbox_ids
        }).eq("id", citation_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error updating citation {citation_id}: {e}")
        return False


async def backfill_citations(
    dry_run: bool = True,
    matter_id: str | None = None,
) -> dict:
    """Main backfill function.

    Args:
        dry_run: If True, only report what would be done
        matter_id: Optional matter ID to limit scope

    Returns:
        Statistics about the backfill
    """
    stats = {
        "total_citations": 0,
        "citations_processed": 0,
        "citations_updated": 0,
        "citations_no_match": 0,
        "bboxes_linked": 0,
    }

    print(f"\n{'='*60}")
    print(f"Citation Source BBox Backfill {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}\n")

    # Get citations missing source_bbox_ids
    print("Fetching citations with missing source_bbox_ids...")
    citations = await get_citations_missing_bboxes(matter_id)
    stats["total_citations"] = len(citations)
    print(f"Found {len(citations)} citations to process\n")

    if not citations:
        return stats

    # Group citations by source_document_id and page for efficient bbox loading
    citations_by_doc_page: dict[tuple[str, int], list[dict]] = {}
    for citation in citations:
        key = (citation["source_document_id"], citation["source_page"])
        if key not in citations_by_doc_page:
            citations_by_doc_page[key] = []
        citations_by_doc_page[key].append(citation)

    print(f"Citations span {len(citations_by_doc_page)} document-page combinations\n")

    # Process each document-page group
    for (doc_id, page_num), page_citations in citations_by_doc_page.items():
        print(f"Processing document {doc_id[:8]}... page {page_num} ({len(page_citations)} citations)")

        # Load bboxes for this page
        page_bboxes = await get_bboxes_for_document_page(doc_id, page_num)

        if not page_bboxes:
            print(f"  No bboxes found for page {page_num}")
            stats["citations_no_match"] += len(page_citations)
            continue

        print(f"  Found {len(page_bboxes)} bboxes on page")

        # Process each citation
        for citation in page_citations:
            stats["citations_processed"] += 1
            citation_text = citation.get("raw_citation_text", "")

            if not citation_text:
                stats["citations_no_match"] += 1
                continue

            # Try fuzzy matching first
            matched_ids = find_matching_bboxes_fuzzy(
                citation_text,
                page_bboxes,
                max_bboxes=15,
            )

            # Fallback to word overlap matching
            if not matched_ids:
                matched_ids = find_matching_bboxes(
                    citation_text,
                    page_bboxes,
                    max_bboxes=15,
                    min_overlap_words=2,
                )

            if matched_ids:
                if dry_run:
                    print(f"    Would link citation {citation['id'][:8]}... to {len(matched_ids)} bboxes")
                else:
                    success = await update_citation_source_bboxes(
                        citation["id"],
                        matched_ids,
                    )
                    if success:
                        print(f"    Linked citation {citation['id'][:8]}... to {len(matched_ids)} bboxes")
                        stats["citations_updated"] += 1
                        stats["bboxes_linked"] += len(matched_ids)
                    else:
                        print(f"    Failed to update citation {citation['id'][:8]}...")
                        stats["citations_no_match"] += 1
            else:
                stats["citations_no_match"] += 1

    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Total citations found:     {stats['total_citations']}")
    print(f"Citations processed:       {stats['citations_processed']}")
    print(f"Citations updated:         {stats['citations_updated']}")
    print(f"Citations with no match:   {stats['citations_no_match']}")
    print(f"Total bboxes linked:       {stats['bboxes_linked']}")

    if dry_run:
        print(f"\nThis was a DRY RUN. Run with --execute to apply changes.")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill source_bbox_ids for citations"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the backfill (default is dry run)",
    )
    parser.add_argument(
        "--matter-id",
        type=str,
        help="Limit to specific matter ID",
    )

    args = parser.parse_args()

    dry_run = not args.execute

    asyncio.run(backfill_citations(
        dry_run=dry_run,
        matter_id=args.matter_id,
    ))


if __name__ == "__main__":
    main()
