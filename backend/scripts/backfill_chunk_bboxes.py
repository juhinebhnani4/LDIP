"""Backfill script to fix chunk bbox_ids and page_number.

This script fixes chunks that have empty bbox_ids by searching all
document bboxes for the chunk's content text. This is the ROOT FIX
that enables events and entity mentions to get proper bbox_ids.

Usage:
    # Dry run - see what would be fixed
    python scripts/backfill_chunk_bboxes.py --matter-id UUID

    # Execute the fix
    python scripts/backfill_chunk_bboxes.py --matter-id UUID --execute
"""

import asyncio
import os
import sys
from collections import defaultdict

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

# Matching threshold (same as bbox_linker.py)
MATCH_THRESHOLD = 50
MAX_BBOX_WINDOW = 100


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return " ".join(text.lower().split())


async def get_chunks_to_fix(matter_id: str, limit: int = 1000) -> list[dict]:
    """Get chunks with empty bbox_ids.

    Args:
        matter_id: Matter UUID
        limit: Max chunks to process

    Returns:
        List of chunk dicts
    """
    response = supabase.table("chunks").select(
        "id, document_id, content, page_number, bbox_ids"
    ).eq("matter_id", matter_id).or_(
        "bbox_ids.is.null,bbox_ids.eq.{}"
    ).limit(limit).execute()

    return response.data or []


async def get_all_document_bboxes(document_id: str) -> list[dict]:
    """Get ALL bboxes for a document (paginated).

    Args:
        document_id: Document UUID

    Returns:
        List of all bbox dicts for the document
    """
    all_bboxes = []
    page = 1
    batch_size = 1000

    while True:
        response = supabase.table("bounding_boxes").select(
            "id, text, page_number"
        ).eq("document_id", document_id).order(
            "page_number"
        ).order("y").order("x").range(
            (page - 1) * batch_size, page * batch_size - 1
        ).execute()

        batch = response.data or []
        all_bboxes.extend(batch)

        if len(batch) < batch_size:
            break
        page += 1

    return all_bboxes


def find_matching_bboxes(
    chunk_content: str,
    all_bboxes: list[dict],
    max_bboxes: int = 50,
) -> tuple[list[str], int | None]:
    """Find bboxes matching chunk content using sliding window.

    Uses the same algorithm as bbox_linker.py but searches all document bboxes.

    Args:
        chunk_content: Chunk text content
        all_bboxes: All bboxes for the document
        max_bboxes: Maximum bboxes to return

    Returns:
        Tuple of (matching bbox_ids, detected page_number)
    """
    if not chunk_content or not all_bboxes:
        return [], None

    chunk_text_normalized = normalize_text(chunk_content)
    chunk_sample = chunk_text_normalized[:500]

    # Pre-compute normalized bbox texts
    bbox_texts = [normalize_text(bbox.get("text", "")) for bbox in all_bboxes]

    # Sliding window search
    best_match_score = 0
    best_match_start = -1
    window_size = min(MAX_BBOX_WINDOW, len(all_bboxes))

    # Search with larger step for efficiency
    step_size = max(1, window_size // 4)

    for start_idx in range(0, len(all_bboxes) - window_size + 1, step_size):
        window_text = " ".join(bbox_texts[start_idx:start_idx + window_size])
        match_score = fuzz.partial_ratio(chunk_sample, window_text[:1500])

        if match_score > best_match_score:
            best_match_score = match_score
            best_match_start = start_idx

        if match_score >= 95:
            break

    # Fine-grained search around best match
    if best_match_score >= MATCH_THRESHOLD - 10 and best_match_start >= 0:
        fine_start = max(0, best_match_start - step_size)
        fine_end = min(len(all_bboxes) - window_size + 1, best_match_start + step_size)

        for start_idx in range(fine_start, fine_end):
            window_text = " ".join(bbox_texts[start_idx:start_idx + window_size])
            match_score = fuzz.partial_ratio(chunk_sample, window_text[:1500])

            if match_score > best_match_score:
                best_match_score = match_score
                best_match_start = start_idx

            if match_score >= 95:
                break

    # Extract matching bboxes
    matched_bbox_ids: list[str] = []
    page_counts: dict[int, int] = defaultdict(int)

    if best_match_score >= MATCH_THRESHOLD and best_match_start >= 0:
        chunk_words = set(chunk_text_normalized.split()[:50])

        for idx in range(best_match_start, min(best_match_start + window_size, len(all_bboxes))):
            bbox = all_bboxes[idx]
            bbox_text = bbox_texts[idx]

            bbox_words = set(bbox_text.split())
            overlap = chunk_words & bbox_words

            if overlap and len(overlap) >= min(2, len(bbox_words)):
                bbox_id = bbox.get("id")
                if bbox_id:
                    matched_bbox_ids.append(str(bbox_id))
                    page = bbox.get("page_number")
                    if page is not None:
                        page_counts[page] += 1

            if len(matched_bbox_ids) >= max_bboxes:
                break

    # Determine most common page
    most_common_page = None
    if page_counts:
        most_common_page = max(page_counts, key=page_counts.get)

    return matched_bbox_ids, most_common_page


async def update_chunk(
    chunk_id: str,
    bbox_ids: list[str],
    page_number: int | None = None,
) -> bool:
    """Update a chunk's bbox_ids and optionally page_number.

    Args:
        chunk_id: Chunk UUID
        bbox_ids: New bbox IDs to set
        page_number: Optional new page_number

    Returns:
        True if update succeeded
    """
    try:
        update_data = {"bbox_ids": bbox_ids}
        if page_number is not None:
            update_data["page_number"] = page_number

        response = supabase.table("chunks").update(
            update_data
        ).eq("id", chunk_id).execute()

        return len(response.data or []) > 0
    except Exception as e:
        print(f"  Error updating chunk {chunk_id[:8]}...: {e}")
        return False


async def backfill_chunks(
    dry_run: bool = True,
    matter_id: str | None = None,
) -> dict:
    """Main backfill function.

    Args:
        dry_run: If True, only report what would be done
        matter_id: Matter ID (required)

    Returns:
        Statistics about the backfill
    """
    if not matter_id:
        print("Error: --matter-id is required")
        return {}

    stats = {
        "total_chunks": 0,
        "chunks_checked": 0,
        "chunks_fixed": 0,
        "chunks_no_match": 0,
        "documents_processed": 0,
    }

    print(f"\n{'='*70}")
    print(f"Chunk BBox Backfill {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*70}\n")

    # Get chunks to fix
    print("Fetching chunks with empty bbox_ids...")
    chunks = await get_chunks_to_fix(matter_id)
    stats["total_chunks"] = len(chunks)
    print(f"Found {len(chunks)} chunks to process\n")

    if not chunks:
        return stats

    # Group by document for efficient bbox loading
    chunks_by_doc: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        doc_id = chunk.get("document_id")
        if doc_id:
            chunks_by_doc[doc_id].append(chunk)

    print(f"Chunks span {len(chunks_by_doc)} documents\n")

    # Process each document
    for doc_id, doc_chunks in chunks_by_doc.items():
        print(f"\nDocument {doc_id[:8]}... ({len(doc_chunks)} chunks)")
        stats["documents_processed"] += 1

        # Load ALL bboxes for this document
        all_bboxes = await get_all_document_bboxes(doc_id)
        print(f"  Loaded {len(all_bboxes)} bboxes across {len(set(b.get('page_number') for b in all_bboxes))} pages")

        if not all_bboxes:
            print(f"  WARNING: No bboxes found for document!")
            stats["chunks_no_match"] += len(doc_chunks)
            continue

        # Process each chunk
        fixed_count = 0
        for chunk in doc_chunks:
            stats["chunks_checked"] += 1
            chunk_id = chunk["id"]
            content = chunk.get("content", "")

            if not content:
                stats["chunks_no_match"] += 1
                continue

            # Find matching bboxes
            matched_ids, matched_page = find_matching_bboxes(content, all_bboxes)

            if matched_ids:
                if dry_run:
                    content_preview = content[:40].replace('\n', ' ')
                    print(f"    Would fix: \"{content_preview}...\" -> {len(matched_ids)} bboxes, page {matched_page}")
                else:
                    # Use detected page or keep existing
                    page = matched_page if matched_page is not None else chunk.get("page_number")
                    success = await update_chunk(
                        chunk_id=chunk_id,
                        bbox_ids=matched_ids,
                        page_number=page,
                    )
                    if success:
                        stats["chunks_fixed"] += 1
                        fixed_count += 1
                    else:
                        stats["chunks_no_match"] += 1
            else:
                stats["chunks_no_match"] += 1

        if not dry_run and fixed_count > 0:
            print(f"  Fixed {fixed_count} chunks")

    # Print summary
    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Total chunks:            {stats['total_chunks']}")
    print(f"Chunks checked:          {stats['chunks_checked']}")
    print(f"Documents processed:     {stats['documents_processed']}")
    print(f"Chunks fixed:            {stats['chunks_fixed']}")
    print(f"Chunks no match found:   {stats['chunks_no_match']}")

    if dry_run:
        print(f"\nThis was a DRY RUN. Run with --execute to apply changes.")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill bbox_ids for chunks (ROOT FIX for events/mentions)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the backfill (default is dry run)",
    )
    parser.add_argument(
        "--matter-id",
        type=str,
        required=True,
        help="Matter ID to process (required)",
    )

    args = parser.parse_args()

    dry_run = not args.execute

    asyncio.run(backfill_chunks(
        dry_run=dry_run,
        matter_id=args.matter_id,
    ))


if __name__ == "__main__":
    main()
