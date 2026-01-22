#!/usr/bin/env python3
"""Consolidate duplicate act resolutions in the database.

This script cleans up act_resolutions table by:
1. Identifying act resolutions that are variations of the same act
2. Merging them into a single canonical resolution
3. Updating citation references to point to the canonical act name

Run this after fixing the citation extraction to clean up existing data.

Usage:
    python consolidate_act_resolutions.py [--dry-run] [--matter-id UUID]
"""

import argparse
import asyncio
import os
import re
import sys
from collections import defaultdict

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from app.engines.citation.abbreviations import (
    clean_act_name,
    get_canonical_name,
    normalize_act_name,
)
from app.services.supabase.client import get_service_client


def is_garbage_act_name(act_name: str) -> bool:
    """Check if an act name is garbage (sentence fragment, etc.)."""
    if not act_name:
        return True

    # Too long - likely contains sentence fragments
    if len(act_name) > 120:
        return True

    # Contains sentence patterns
    garbage_patterns = [
        r"\.\s+[A-Z]",  # Period followed by capital (new sentence)
        r"\.\s+[a-z]",  # Period followed by lowercase
        r"\s+accordingly\s+",
        r"\s+Respondent\s+",
        r"\s+Petitioner\s+",
        r"\s+Hon'ble\s+",
        r"\s+Court\s+",
        r"TRUE\s+COPY",
        r"NOTARY",
        r"\s+u/s\s+",  # Section reference in name
        r"\s+directed\s+",
        r"\s+ordered\s+",
    ]

    for pattern in garbage_patterns:
        if re.search(pattern, act_name, re.IGNORECASE):
            return True

    return False


async def get_all_act_resolutions(client, matter_id: str | None = None):
    """Get all act resolutions, optionally filtered by matter."""
    query = client.table("act_resolutions").select("*")
    if matter_id:
        query = query.eq("matter_id", matter_id)

    result = query.execute()
    return result.data or []


async def get_citations_for_act(client, matter_id: str, act_name: str):
    """Get all citations referencing a specific act name."""
    result = (
        client.table("citations")
        .select("id, act_name, act_name_original")
        .eq("matter_id", matter_id)
        .eq("act_name", act_name)
        .execute()
    )
    return result.data or []


async def update_citations_act_name(
    client, citation_ids: list[str], new_act_name: str, dry_run: bool = True
):
    """Update citations to use the canonical act name."""
    if dry_run:
        print(f"  [DRY RUN] Would update {len(citation_ids)} citations to '{new_act_name}'")
        return

    for cid in citation_ids:
        client.table("citations").update({"act_name": new_act_name}).eq("id", cid).execute()

    print(f"  Updated {len(citation_ids)} citations to '{new_act_name}'")


async def delete_act_resolution(client, resolution_id: str, dry_run: bool = True):
    """Delete an act resolution."""
    if dry_run:
        print(f"  [DRY RUN] Would delete act_resolution {resolution_id}")
        return

    client.table("act_resolutions").delete().eq("id", resolution_id).execute()
    print(f"  Deleted act_resolution {resolution_id}")


async def consolidate_resolutions(dry_run: bool = True, matter_id: str | None = None):
    """Main consolidation logic."""
    client = get_service_client()
    if not client:
        print("ERROR: Could not connect to Supabase")
        return

    print("=" * 60)
    print("ACT RESOLUTION CONSOLIDATION")
    print("=" * 60)
    if dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    else:
        print("MODE: LIVE (changes will be committed)")
    print()

    # Get all act resolutions
    resolutions = await get_all_act_resolutions(client, matter_id)
    print(f"Found {len(resolutions)} act resolutions")
    print()

    # Group resolutions by matter_id and normalized name
    # Key: (matter_id, canonical_normalized_name)
    # Value: list of resolutions that should be merged
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for res in resolutions:
        matter = res["matter_id"]
        display_name = res.get("act_name_display") or ""
        normalized = res.get("act_name_normalized") or ""

        # Clean the display name
        cleaned = clean_act_name(display_name)

        # Get canonical name
        canonical = get_canonical_name(cleaned)
        if canonical:
            canonical_name, year = canonical
            target_normalized = normalize_act_name(canonical_name + (f", {year}" if year else ""))
        else:
            target_normalized = normalize_act_name(cleaned)

        groups[(matter, target_normalized)].append(res)

    # Process each group
    total_to_delete = 0
    total_to_update = 0

    for (matter, target_normalized), group_resolutions in groups.items():
        if len(group_resolutions) <= 1:
            continue  # No duplicates

        print(f"\n--- Matter: {matter[:8]}... ---")
        print(f"Canonical: {target_normalized}")
        print(f"Found {len(group_resolutions)} duplicates:")

        # Find the best resolution to keep (highest citation count, or first available)
        best = max(group_resolutions, key=lambda r: (
            r.get("resolution_status") == "available",  # Prefer available
            r.get("citation_count", 0),  # Then highest count
        ))

        # Get canonical display name
        canonical = get_canonical_name(clean_act_name(best.get("act_name_display", "")))
        if canonical:
            canonical_display = f"{canonical[0]}, {canonical[1]}" if canonical[1] else canonical[0]
        else:
            canonical_display = clean_act_name(best.get("act_name_display", ""))

        print(f"  Keeping: {best['id'][:8]}... ({best.get('act_name_display', '')[:50]})")
        print(f"  Canonical display name: {canonical_display}")

        # Process duplicates to delete
        for res in group_resolutions:
            if res["id"] == best["id"]:
                continue

            display = res.get("act_name_display", "")
            print(f"  Merging: {res['id'][:8]}... ({display[:60]}{'...' if len(display) > 60 else ''})")

            # Update citations from this resolution to use canonical name
            citations = await get_citations_for_act(client, matter, display)
            if citations:
                citation_ids = [c["id"] for c in citations]
                await update_citations_act_name(client, citation_ids, canonical_display, dry_run)
                total_to_update += len(citation_ids)

            # Delete the duplicate resolution
            await delete_act_resolution(client, res["id"], dry_run)
            total_to_delete += 1

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Act resolutions to delete: {total_to_delete}")
    print(f"Citations to update: {total_to_update}")

    if dry_run:
        print()
        print("This was a DRY RUN. To apply changes, run with --live")


async def main():
    parser = argparse.ArgumentParser(description="Consolidate duplicate act resolutions")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually make changes (default is dry-run)",
    )
    parser.add_argument(
        "--matter-id",
        type=str,
        help="Only process a specific matter",
    )

    args = parser.parse_args()

    await consolidate_resolutions(
        dry_run=not args.live,
        matter_id=args.matter_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
