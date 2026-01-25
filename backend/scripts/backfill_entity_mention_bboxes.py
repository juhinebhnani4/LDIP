"""Backfill script to fix entity_mentions bbox_ids and page_number.

This script fixes entity mentions that have empty bbox_ids by:
1. Getting the mention's chunk bbox_ids
2. Filtering to only bboxes containing the mention text
3. Updating the mention with filtered bbox_ids and detected page

Usage:
    # Dry run - see what would be fixed
    python scripts/backfill_entity_mention_bboxes.py

    # Execute the fix
    python scripts/backfill_entity_mention_bboxes.py --execute

    # Limit to specific matter
    python scripts/backfill_entity_mention_bboxes.py --matter-id UUID --execute
"""

import asyncio
import os
import sys
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

from app.core.bbox_search import search_bboxes_for_text

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


async def get_mentions_to_fix(matter_id: str | None = None, limit: int = 5000) -> list[dict]:
    """Get entity mentions with empty bbox_ids.

    Args:
        matter_id: Optional matter ID to filter by (via entity join)
        limit: Max mentions to process

    Returns:
        List of mention dicts
    """
    # Get mentions with empty bbox_ids
    query = supabase.table("entity_mentions").select(
        "id, entity_id, chunk_id, mention_text, context, page_number, bbox_ids"
    ).or_("bbox_ids.is.null,bbox_ids.eq.{}")

    response = query.limit(limit).execute()
    mentions = response.data or []

    if matter_id and mentions:
        # Filter by matter_id via entity lookup
        entity_ids = list(set(m["entity_id"] for m in mentions if m.get("entity_id")))
        if entity_ids:
            entities = supabase.table("identity_nodes").select(
                "id"
            ).eq("matter_id", matter_id).in_("id", entity_ids[:500]).execute()
            valid_entity_ids = set(e["id"] for e in entities.data or [])
            mentions = [m for m in mentions if m.get("entity_id") in valid_entity_ids]

    return mentions


async def get_chunk_with_bboxes(chunk_id: str) -> dict | None:
    """Get chunk data including bbox_ids.

    Args:
        chunk_id: Chunk UUID

    Returns:
        Chunk dict or None
    """
    response = supabase.table("chunks").select(
        "id, document_id, page_number, bbox_ids"
    ).eq("id", chunk_id).single().execute()

    return response.data


async def get_bboxes_by_ids(bbox_ids: list[str], document_id: str) -> list[dict]:
    """Fetch bboxes by their IDs.

    Args:
        bbox_ids: List of bbox UUIDs
        document_id: Document UUID for ordering

    Returns:
        List of bbox dicts
    """
    if not bbox_ids:
        return []

    # Batch fetch (limit to 100 for safety)
    response = supabase.table("bounding_boxes").select(
        "id, text, page_number"
    ).in_("id", bbox_ids[:100]).execute()

    return response.data or []


async def update_mention(
    mention_id: str,
    bbox_ids: list[str],
    page_number: int | None = None,
) -> bool:
    """Update a mention's bbox_ids and optionally page_number.

    Args:
        mention_id: Mention UUID
        bbox_ids: New bbox IDs to set
        page_number: Optional new page_number

    Returns:
        True if update succeeded
    """
    try:
        update_data = {"bbox_ids": bbox_ids}
        if page_number is not None:
            update_data["page_number"] = page_number

        response = supabase.table("entity_mentions").update(
            update_data
        ).eq("id", mention_id).execute()

        return len(response.data or []) > 0
    except Exception as e:
        print(f"  Error updating mention {mention_id[:8]}...: {e}")
        return False


async def backfill_mentions(
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
        "total_mentions": 0,
        "mentions_checked": 0,
        "mentions_fixed": 0,
        "mentions_no_chunk": 0,
        "mentions_no_match": 0,
    }

    print(f"\n{'='*70}")
    print(f"Entity Mention BBox Backfill {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*70}\n")

    # Get mentions to fix
    print("Fetching mentions with empty bbox_ids...")
    mentions = await get_mentions_to_fix(matter_id)
    stats["total_mentions"] = len(mentions)
    print(f"Found {len(mentions)} mentions to process\n")

    if not mentions:
        return stats

    # Group by chunk for efficient processing
    mentions_by_chunk: dict[str, list[dict]] = defaultdict(list)
    for mention in mentions:
        chunk_id = mention.get("chunk_id")
        if chunk_id:
            mentions_by_chunk[chunk_id].append(mention)
        else:
            stats["mentions_no_chunk"] += 1

    print(f"Mentions span {len(mentions_by_chunk)} chunks\n")

    # Process each chunk
    for chunk_id, chunk_mentions in mentions_by_chunk.items():
        stats["mentions_checked"] += len(chunk_mentions)

        # Get chunk data
        chunk = await get_chunk_with_bboxes(chunk_id)
        if not chunk:
            stats["mentions_no_chunk"] += len(chunk_mentions)
            continue

        chunk_bbox_ids = chunk.get("bbox_ids") or []
        document_id = chunk.get("document_id")
        chunk_page = chunk.get("page_number")

        if not chunk_bbox_ids:
            stats["mentions_no_match"] += len(chunk_mentions)
            continue

        # Get bbox data for filtering
        bboxes = await get_bboxes_by_ids(chunk_bbox_ids, document_id)
        if not bboxes:
            stats["mentions_no_match"] += len(chunk_mentions)
            continue

        # Process each mention in this chunk
        for mention in chunk_mentions:
            mention_id = mention["id"]
            mention_text = mention.get("mention_text", "")
            context = mention.get("context", "")

            # Build search text
            search_text = mention_text
            if context:
                search_text = context  # Context usually contains the mention

            if not search_text:
                stats["mentions_no_match"] += 1
                continue

            # Search for matches in chunk's bboxes
            matched_ids, matched_page = search_bboxes_for_text(
                search_text=search_text,
                bboxes=bboxes,
                min_word_overlap=2,
                max_results=15,
            )

            if matched_ids:
                # Use detected page or fall back to chunk page
                page = matched_page if matched_page is not None else chunk_page

                if dry_run:
                    mention_preview = mention_text[:30].replace('\n', ' ')
                    print(f"  Would fix: \"{mention_preview}...\" -> {len(matched_ids)} bboxes, page {page}")
                else:
                    success = await update_mention(
                        mention_id=mention_id,
                        bbox_ids=matched_ids,
                        page_number=page,
                    )
                    if success:
                        stats["mentions_fixed"] += 1
                    else:
                        stats["mentions_no_match"] += 1
            else:
                # No match - use chunk's bbox_ids as fallback
                if dry_run:
                    mention_preview = mention_text[:30].replace('\n', ' ')
                    print(f"  Would use chunk bboxes for: \"{mention_preview}...\" -> {len(chunk_bbox_ids)} bboxes")
                else:
                    success = await update_mention(
                        mention_id=mention_id,
                        bbox_ids=[str(b) for b in chunk_bbox_ids],
                        page_number=chunk_page,
                    )
                    if success:
                        stats["mentions_fixed"] += 1
                    else:
                        stats["mentions_no_match"] += 1

    # Print summary
    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Total mentions:          {stats['total_mentions']}")
    print(f"Mentions checked:        {stats['mentions_checked']}")
    print(f"Mentions fixed:          {stats['mentions_fixed']}")
    print(f"Mentions no chunk:       {stats['mentions_no_chunk']}")
    print(f"Mentions no match:       {stats['mentions_no_match']}")

    if dry_run:
        print(f"\nThis was a DRY RUN. Run with --execute to apply changes.")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill bbox_ids for entity mentions"
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

    asyncio.run(backfill_mentions(
        dry_run=dry_run,
        matter_id=args.matter_id,
    ))


if __name__ == "__main__":
    main()
