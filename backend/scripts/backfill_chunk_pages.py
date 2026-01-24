"""Backfill chunk page numbers from bounding boxes.

This script updates chunks with page_number by matching chunk content
to bounding box text. It's more aggressive than the initial linking
and uses fuzzy matching to find the best page for each chunk.

Usage:
    python scripts/backfill_chunk_pages.py [--document-id DOC_ID] [--dry-run]

Examples:
    # Backfill all chunks without page numbers (dry run)
    python scripts/backfill_chunk_pages.py --dry-run

    # Backfill for a specific document
    python scripts/backfill_chunk_pages.py --document-id fc99a995-0bcc-42df-b289-edd31920543e
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from rapidfuzz import fuzz

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


def get_page_text_map(client, document_id: str) -> dict[int, str]:
    """Build a map of page_number -> combined text from bboxes.

    Args:
        client: Supabase client
        document_id: Document UUID

    Returns:
        Dict mapping page number to combined text
    """
    page_texts: dict[int, list[str]] = defaultdict(list)

    offset = 0
    batch_size = 1000

    while True:
        result = (
            client.table("bounding_boxes")
            .select("page_number, text")
            .eq("document_id", document_id)
            .order("page_number")
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        if not result.data:
            break

        for bbox in result.data:
            page = bbox.get("page_number")
            text = bbox.get("text", "") or ""
            if page and text:
                page_texts[page].append(text)

        if len(result.data) < batch_size:
            break
        offset += batch_size

    # Combine texts per page
    return {page: " ".join(texts) for page, texts in page_texts.items()}


def find_best_page_match(chunk_content: str, page_texts: dict[int, str], threshold: float = 40.0) -> tuple[int | None, float]:
    """Find the page that best matches the chunk content.

    Args:
        chunk_content: Chunk text content
        page_texts: Map of page_number -> page text
        threshold: Minimum match score (0-100)

    Returns:
        Tuple of (best_page, score) or (None, 0) if no match
    """
    if not chunk_content or not page_texts:
        return None, 0

    # Clean chunk content for matching
    chunk_clean = chunk_content[:500].lower().strip()  # Use first 500 chars

    best_page = None
    best_score = 0

    for page, page_text in page_texts.items():
        page_clean = page_text.lower()

        # Check if significant portion of chunk appears in page
        score = fuzz.partial_ratio(chunk_clean, page_clean)

        if score > best_score and score >= threshold:
            best_score = score
            best_page = page

    return best_page, best_score


def backfill_document_chunks(document_id: str, client, dry_run: bool = False) -> dict:
    """Backfill page numbers for chunks in a document.

    Args:
        document_id: Document UUID
        client: Supabase client
        dry_run: If True, don't make changes

    Returns:
        Stats dict
    """
    # Get chunks without page numbers
    chunks_result = (
        client.table("chunks")
        .select("id, content, page_number")
        .eq("document_id", document_id)
        .is_("page_number", "null")
        .execute()
    )

    chunks = chunks_result.data or []

    if not chunks:
        return {
            "document_id": document_id,
            "total": 0,
            "updated": 0,
            "skipped": True,
        }

    # Build page text map
    page_texts = get_page_text_map(client, document_id)

    if not page_texts:
        return {
            "document_id": document_id,
            "total": len(chunks),
            "updated": 0,
            "reason": "no_bbox_text",
        }

    print(f"  Found {len(page_texts)} pages with text, {len(chunks)} chunks to process")

    # Match chunks to pages
    updated = 0

    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "")
        if not content:
            continue

        best_page, score = find_best_page_match(content, page_texts)

        if best_page and score >= 50:
            if not dry_run:
                client.table("chunks").update({
                    "page_number": best_page
                }).eq("id", chunk["id"]).execute()

            updated += 1

            if updated % 50 == 0:
                print(f"  Progress: {updated}/{len(chunks)} chunks updated")

    return {
        "document_id": document_id,
        "total": len(chunks),
        "updated": updated,
    }


def backfill_all(document_id: str | None = None, dry_run: bool = False):
    """Backfill chunk page numbers.

    Args:
        document_id: Optional specific document ID
        dry_run: If True, don't make changes
    """
    client = get_service_client()

    if document_id:
        documents = [{"id": document_id}]
    else:
        # Get all documents
        result = (
            client.table("documents")
            .select("id, filename")
            .execute()
        )
        documents = result.data or []

    if not documents:
        print("No documents found")
        return

    print(f"Processing {len(documents)} documents" + (" (DRY RUN)" if dry_run else ""))

    total_updated = 0
    total_chunks = 0

    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        filename = doc.get("filename", doc_id[:8])

        print(f"\n[{i}/{len(documents)}] {filename}")

        try:
            result = backfill_document_chunks(doc_id, client, dry_run)

            if result.get("skipped"):
                print("  Skipped (all chunks have page numbers)")
            elif result.get("reason") == "no_bbox_text":
                print("  Skipped (no bounding box text)")
            else:
                print(f"  Updated {result['updated']}/{result['total']} chunks")
                total_updated += result["updated"]
                total_chunks += result["total"]

        except Exception as e:
            print(f"  Error: {e}")
            logger.exception("backfill_failed", document_id=doc_id)

    action = "Would update" if dry_run else "Updated"
    print(f"\nDone! {action} {total_updated} of {total_chunks} chunks")


def main():
    parser = argparse.ArgumentParser(description="Backfill chunk page numbers from bounding boxes")
    parser.add_argument("--document-id", help="Specific document ID to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")

    args = parser.parse_args()

    backfill_all(document_id=args.document_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
