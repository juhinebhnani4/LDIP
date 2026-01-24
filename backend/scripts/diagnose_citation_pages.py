"""Diagnostic script to check citation page data quality.

Identifies citations with missing or incorrect source page data.

Usage:
    python scripts/diagnose_citation_pages.py [--matter-id MATTER_ID]
"""

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY required")
    sys.exit(1)

client = create_client(SUPABASE_URL, SUPABASE_KEY)


def diagnose_matter(matter_id: str | None = None):
    """Run diagnostics on citation page data."""

    print("\n" + "=" * 70)
    print("CITATION PAGE DATA DIAGNOSTIC")
    print("=" * 70)

    # Get matter info if provided
    if matter_id:
        matter_resp = client.table("matters").select("id, title").eq("id", matter_id).single().execute()
        if matter_resp.data:
            print(f"\nMatter: {matter_resp.data['title']} ({matter_id[:8]}...)")
        else:
            print(f"\nMatter ID: {matter_id}")
    else:
        print("\nScope: All matters")

    print("-" * 70)

    # 1. Count citations by source_page
    print("\n1. CITATIONS BY SOURCE PAGE")
    query = client.table("citations").select("source_page", count="exact")
    if matter_id:
        query = query.eq("matter_id", matter_id)

    # Get citations with source_page = 1 (likely default/wrong)
    page1_resp = query.eq("source_page", 1).execute()
    page1_count = page1_resp.count or len(page1_resp.data or [])

    # Get all citations
    all_query = client.table("citations").select("id", count="exact")
    if matter_id:
        all_query = all_query.eq("matter_id", matter_id)
    all_resp = all_query.execute()
    total_count = all_resp.count or len(all_resp.data or [])

    # Get citations with source_page > 1
    other_pages = total_count - page1_count

    print(f"   Total citations: {total_count}")
    print(f"   Citations on page 1: {page1_count} ({page1_count/total_count*100:.1f}%)" if total_count > 0 else "   No citations")
    print(f"   Citations on other pages: {other_pages} ({other_pages/total_count*100:.1f}%)" if total_count > 0 else "")

    if page1_count > total_count * 0.5 and total_count > 10:
        print(f"   [!] WARNING: High % of page 1 citations suggests data quality issue!")

    # 2. Check source_bbox_ids
    print("\n2. SOURCE BBOX LINKAGE")

    # Citations with empty source_bbox_ids
    empty_bbox_query = client.table("citations").select("id", count="exact").or_("source_bbox_ids.is.null,source_bbox_ids.eq.{}")
    if matter_id:
        empty_bbox_query = empty_bbox_query.eq("matter_id", matter_id)
    empty_bbox_resp = empty_bbox_query.execute()
    empty_bbox_count = empty_bbox_resp.count or len(empty_bbox_resp.data or [])

    has_bbox_count = total_count - empty_bbox_count

    print(f"   Citations WITH bbox links: {has_bbox_count} ({has_bbox_count/total_count*100:.1f}%)" if total_count > 0 else "   No citations")
    print(f"   Citations WITHOUT bbox links: {empty_bbox_count} ({empty_bbox_count/total_count*100:.1f}%)" if total_count > 0 else "")

    if empty_bbox_count > total_count * 0.3 and total_count > 10:
        print(f"   [!] WARNING: Many citations missing bbox links - highlights won't work!")

    # 3. Check chunk page_number population
    print("\n3. CHUNK PAGE NUMBER POPULATION")

    # Get documents for this matter
    doc_query = client.table("documents").select("id")
    if matter_id:
        doc_query = doc_query.eq("matter_id", matter_id)
    doc_resp = doc_query.execute()
    doc_ids = [d["id"] for d in (doc_resp.data or [])]

    if doc_ids:
        # Sample first 5 documents
        sample_docs = doc_ids[:5]

        chunks_with_page = 0
        chunks_without_page = 0

        for doc_id in sample_docs:
            # Chunks with page_number
            with_page = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).not_.is_("page_number", "null").execute()
            without_page = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).is_("page_number", "null").execute()

            chunks_with_page += with_page.count or len(with_page.data or [])
            chunks_without_page += without_page.count or len(without_page.data or [])

        total_chunks = chunks_with_page + chunks_without_page
        print(f"   Sample of {len(sample_docs)} documents:")
        print(f"   Chunks WITH page_number: {chunks_with_page} ({chunks_with_page/total_chunks*100:.1f}%)" if total_chunks > 0 else "   No chunks")
        print(f"   Chunks WITHOUT page_number: {chunks_without_page} ({chunks_without_page/total_chunks*100:.1f}%)" if total_chunks > 0 else "")

        if chunks_without_page > chunks_with_page:
            print(f"   [!] WARNING: Many chunks missing page_number - this causes citation page issues!")

    # 4. Specific problematic citations
    print("\n4. SAMPLE PROBLEMATIC CITATIONS (page=1 AND no bbox)")

    problem_query = client.table("citations").select(
        "id, act_name, section, raw_citation_text, source_page, source_bbox_ids"
    ).eq("source_page", 1).or_("source_bbox_ids.is.null,source_bbox_ids.eq.{}")
    if matter_id:
        problem_query = problem_query.eq("matter_id", matter_id)
    problem_resp = problem_query.limit(5).execute()

    if problem_resp.data:
        for i, citation in enumerate(problem_resp.data, 1):
            act = citation.get("act_name", "Unknown")[:30]
            section = citation.get("section", "?")
            raw_text = (citation.get("raw_citation_text") or "")[:50]
            print(f"   {i}. {act} - Section {section}")
            print(f"      Text: \"{raw_text}...\"")
            print(f"      Page: {citation['source_page']}, BBoxes: {len(citation.get('source_bbox_ids') or [])}")
    else:
        print("   No problematic citations found!")

    # 5. Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)

    needs_backfill = False

    if page1_count > total_count * 0.3 and total_count > 10:
        print("\n1. Run citation page backfill:")
        print(f"   python scripts/backfill_citation_pages.py --matter-id {matter_id} --dry-run")
        needs_backfill = True

    if empty_bbox_count > total_count * 0.3 and total_count > 10:
        print("\n2. Run bbox linking backfill:")
        print(f"   python scripts/backfill_citation_source_bboxes.py --matter-id {matter_id} --dry-run")
        needs_backfill = True

    if chunks_without_page > chunks_with_page if 'chunks_without_page' in dir() else False:
        print("\n3. Run chunk page backfill first:")
        print(f"   python scripts/backfill_chunk_page_numbers.py --matter-id {matter_id}")

    if not needs_backfill:
        print("\n[OK] Data quality looks good! Issue may be with specific citations.")

    print("\n")
    return {
        "total_citations": total_count,
        "page1_citations": page1_count,
        "empty_bbox_citations": empty_bbox_count,
    }


def list_matters():
    """List all matters to help user find their matter_id."""
    print("\nAvailable matters:")
    print("-" * 70)

    resp = client.table("matters").select("id, title, created_at").order("created_at", desc=True).limit(20).execute()

    for matter in (resp.data or []):
        print(f"  {matter['id']}  {matter['title']}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Diagnose citation page data quality")
    parser.add_argument("--matter-id", help="Matter ID to diagnose")
    parser.add_argument("--list-matters", action="store_true", help="List available matters")

    args = parser.parse_args()

    if args.list_matters:
        list_matters()
        return

    if not args.matter_id:
        print("No matter_id provided. Listing available matters...\n")
        list_matters()
        print("Run with: python scripts/diagnose_citation_pages.py --matter-id <ID>")
        return

    diagnose_matter(args.matter_id)


if __name__ == "__main__":
    main()
