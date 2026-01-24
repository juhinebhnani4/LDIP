"""Test script to verify citation page detection accuracy.

Tests the _find_citation_page_from_bboxes function and measures
accuracy against real data.

Usage:
    python scripts/test_citation_page_detection.py [--matter-id UUID]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

from app.engines.citation.storage import _find_citation_page_from_bboxes

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

client = create_client(SUPABASE_URL, SUPABASE_KEY)


def test_helper_function():
    """Unit tests for _find_citation_page_from_bboxes."""
    print("\n" + "=" * 70)
    print("UNIT TESTS: _find_citation_page_from_bboxes")
    print("=" * 70)

    # Test case 1: Exact match
    bboxes = [
        {"text": "Some random text on page 1", "page_number": 1},
        {"text": "Section 205(C) of the Companies Act is important", "page_number": 8},
        {"text": "More text on page 9", "page_number": 9},
    ]
    result = _find_citation_page_from_bboxes("Section 205(C) of the Companies Act", bboxes)
    assert result == 8, f"Test 1 FAILED: Expected 8, got {result}"
    print("[PASS] Test 1: Exact substring match")

    # Test case 2: Section phrase match
    bboxes = [
        {"text": "The provisions under section 138 are strict", "page_number": 5},
        {"text": "Other content", "page_number": 6},
    ]
    result = _find_citation_page_from_bboxes("Section 138 of NI Act", bboxes)
    assert result == 5, f"Test 2 FAILED: Expected 5, got {result}"
    print("[PASS] Test 2: Section phrase match")

    # Test case 3: Word overlap match
    bboxes = [
        {"text": "unrelated content here", "page_number": 1},
        {"text": "Companies Act provisions and regulations apply", "page_number": 10},
    ]
    result = _find_citation_page_from_bboxes("provisions of Companies Act regulations", bboxes)
    assert result == 10, f"Test 3 FAILED: Expected 10, got {result}"
    print("[PASS] Test 3: Word overlap match")

    # Test case 4: No match returns None
    bboxes = [
        {"text": "completely unrelated text", "page_number": 1},
    ]
    result = _find_citation_page_from_bboxes("Section 999 of Unknown Act", bboxes)
    assert result is None, f"Test 4 FAILED: Expected None, got {result}"
    print("[PASS] Test 4: No match returns None")

    # Test case 5: Empty inputs
    result = _find_citation_page_from_bboxes("", [])
    assert result is None, f"Test 5 FAILED: Expected None, got {result}"
    print("[PASS] Test 5: Empty inputs return None")

    # Test case 6: Case insensitive matching
    bboxes = [
        {"text": "SECTION 205(C) OF THE COMPANIES ACT", "page_number": 12},
    ]
    result = _find_citation_page_from_bboxes("section 205(c) of the companies act", bboxes)
    assert result == 12, f"Test 6 FAILED: Expected 12, got {result}"
    print("[PASS] Test 6: Case insensitive matching")

    print("\nAll unit tests passed!")
    return True


def test_accuracy_on_real_data(matter_id: str | None = None, sample_size: int = 50):
    """Test accuracy on real citations from database.

    For citations that have both chunk page and bbox data, compare:
    - Old method: chunk.page_number
    - New method: _find_citation_page_from_bboxes result

    Manual verification needed to determine which is correct.
    """
    print("\n" + "=" * 70)
    print("ACCURACY TEST: Real Data Comparison")
    print("=" * 70)

    # Get citations with bbox_ids for testing
    query = client.table("citations").select(
        "id, raw_citation_text, source_page, source_bbox_ids, source_document_id"
    ).not_.is_("source_bbox_ids", "null")

    if matter_id:
        query = query.eq("matter_id", matter_id)

    citations_resp = query.limit(sample_size).execute()
    citations = citations_resp.data or []

    print(f"\nTesting {len(citations)} citations with bbox links...")

    results = {
        "total": 0,
        "same_page": 0,  # Old and new method agree
        "different_page": 0,  # Old and new method disagree
        "new_found_page": 0,  # New method found a page, old was different
        "new_no_match": 0,  # New method couldn't find page
    }

    different_examples = []

    for citation in citations:
        results["total"] += 1

        citation_text = citation.get("raw_citation_text", "")
        old_page = citation.get("source_page")
        bbox_ids = citation.get("source_bbox_ids") or []

        if not citation_text or not bbox_ids:
            results["new_no_match"] += 1
            continue

        # Fetch bboxes
        try:
            bbox_resp = client.table("bounding_boxes").select(
                "id, page_number, text"
            ).in_("id", bbox_ids[:50]).execute()  # Limit to 50 bboxes
            bboxes = bbox_resp.data or []
        except Exception as e:
            print(f"  Error fetching bboxes: {e}")
            results["new_no_match"] += 1
            continue

        # Run new detection
        new_page = _find_citation_page_from_bboxes(citation_text, bboxes)

        if new_page is None:
            results["new_no_match"] += 1
        elif new_page == old_page:
            results["same_page"] += 1
        else:
            results["different_page"] += 1
            results["new_found_page"] += 1

            # Save example for review
            if len(different_examples) < 10:
                different_examples.append({
                    "citation_id": citation["id"][:8],
                    "text": citation_text[:60],
                    "old_page": old_page,
                    "new_page": new_page,
                    "doc_id": citation["source_document_id"][:8],
                })

    # Print results
    print("\n" + "-" * 70)
    print("RESULTS")
    print("-" * 70)
    print(f"Total citations tested: {results['total']}")
    print(f"Same page (agree):      {results['same_page']} ({results['same_page']/results['total']*100:.1f}%)")
    print(f"Different page:         {results['different_page']} ({results['different_page']/results['total']*100:.1f}%)")
    print(f"New method no match:    {results['new_no_match']} ({results['new_no_match']/results['total']*100:.1f}%)")

    if different_examples:
        print("\n" + "-" * 70)
        print("EXAMPLES WHERE NEW METHOD FOUND DIFFERENT PAGE")
        print("-" * 70)
        print("(Manual verification needed to confirm which is correct)")
        print()

        for ex in different_examples:
            print(f"Citation: {ex['citation_id']}... | Doc: {ex['doc_id']}...")
            print(f"  Text: \"{ex['text']}...\"")
            print(f"  Old page: {ex['old_page']} -> New page: {ex['new_page']}")
            print()

    return results


def verify_specific_citation(citation_id: str):
    """Deep dive into a specific citation to verify page detection."""
    print("\n" + "=" * 70)
    print(f"DEEP DIVE: Citation {citation_id[:8]}...")
    print("=" * 70)

    # Get citation
    citation = client.table("citations").select("*").eq("id", citation_id).single().execute().data

    if not citation:
        print(f"Citation not found: {citation_id}")
        return

    print(f"\nCitation Text: \"{citation['raw_citation_text']}\"")
    print(f"Act: {citation['act_name']}")
    print(f"Section: {citation['section']}")
    print(f"Current source_page: {citation['source_page']}")

    bbox_ids = citation.get("source_bbox_ids") or []
    print(f"Linked bboxes: {len(bbox_ids)}")

    if not bbox_ids:
        print("\nNo bboxes linked - cannot verify")
        return

    # Get bboxes
    bbox_resp = client.table("bounding_boxes").select(
        "id, page_number, text"
    ).in_("id", bbox_ids).order("page_number").execute()
    bboxes = bbox_resp.data or []

    # Show bbox pages
    pages = set(b["page_number"] for b in bboxes if b.get("page_number"))
    print(f"Bbox pages: {sorted(pages)}")

    # Run detection
    new_page = _find_citation_page_from_bboxes(citation["raw_citation_text"], bboxes)
    print(f"\nNew detection result: {new_page}")

    if new_page != citation["source_page"]:
        print(f"\n[!] MISMATCH: Current={citation['source_page']}, Detected={new_page}")
    else:
        print(f"\n[OK] Pages match")

    # Show relevant bboxes
    print("\n" + "-" * 70)
    print("BBOXES CONTAINING CITATION TEXT (or parts of it)")
    print("-" * 70)

    citation_lower = citation["raw_citation_text"].lower()

    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        if any(word in bbox_text for word in citation_lower.split() if len(word) > 3):
            print(f"\nPage {bbox['page_number']}:")
            print(f"  \"{bbox['text'][:200]}...\"")


def main():
    parser = argparse.ArgumentParser(description="Test citation page detection accuracy")
    parser.add_argument("--matter-id", help="Matter ID to test")
    parser.add_argument("--citation-id", help="Specific citation ID for deep dive")
    parser.add_argument("--sample-size", type=int, default=50, help="Number of citations to test")
    parser.add_argument("--skip-unit-tests", action="store_true", help="Skip unit tests")

    args = parser.parse_args()

    # Run unit tests
    if not args.skip_unit_tests:
        try:
            test_helper_function()
        except AssertionError as e:
            print(f"\n[FAIL] {e}")
            return

    # Deep dive into specific citation
    if args.citation_id:
        verify_specific_citation(args.citation_id)
        return

    # Run accuracy test on real data
    test_accuracy_on_real_data(
        matter_id=args.matter_id,
        sample_size=args.sample_size,
    )


if __name__ == "__main__":
    main()
