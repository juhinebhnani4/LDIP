"""Backfill chunk page numbers from bounding boxes.

This script links existing chunks to their bounding boxes to populate
the page_number field, which was previously skipped for performance.

Usage:
    python scripts/backfill_chunk_page_numbers.py [--matter-id MATTER_ID] [--limit N]

Examples:
    # Backfill all chunks without page numbers
    python scripts/backfill_chunk_page_numbers.py

    # Backfill only for a specific matter
    python scripts/backfill_chunk_page_numbers.py --matter-id 91a4a4db-bc3d-40df-8dcc-49179ac49108

    # Limit to first 10 documents
    python scripts/backfill_chunk_page_numbers.py --limit 10
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

import structlog

from app.services.bounding_box_service import get_bounding_box_service
from app.services.chunking.bbox_linker import link_chunks_to_bboxes
from app.services.chunking.parent_child_chunker import ChunkData
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


async def backfill_document_chunks(document_id: str, client, bbox_service) -> dict:
    """Backfill chunk page numbers for a single document.

    Args:
        document_id: Document UUID
        client: Supabase client
        bbox_service: Bounding box service

    Returns:
        Stats dict with counts
    """
    # Get chunks without page_number
    response = (
        client.table("chunks")
        .select(
            "id, content, chunk_type, chunk_index, parent_chunk_id, token_count, bbox_ids, page_number"
        )
        .eq("document_id", document_id)
        .is_("page_number", "null")
        .execute()
    )

    chunks_to_update = response.data or []

    if not chunks_to_update:
        return {"document_id": document_id, "updated": 0, "skipped": True}

    # Convert to ChunkData objects
    chunk_data_list = []
    for row in chunks_to_update:
        chunk = ChunkData(
            id=UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
            content=row["content"],
            chunk_type=row["chunk_type"],
            chunk_index=row.get("chunk_index", 0),
            parent_id=UUID(row["parent_chunk_id"])
            if row.get("parent_chunk_id")
            else None,
            token_count=row.get("token_count", 0),
        )
        chunk_data_list.append(chunk)

    # Link chunks to bboxes
    await link_chunks_to_bboxes(chunk_data_list, document_id, bbox_service)

    # Update chunks in database
    updated_count = 0
    for chunk, original in zip(chunk_data_list, chunks_to_update, strict=False):
        if chunk.page_number is not None:
            # Update the chunk with page_number and bbox_ids
            await asyncio.to_thread(
                lambda c=chunk, oid=original["id"]: client.table("chunks")
                .update(
                    {
                        "page_number": c.page_number,
                        "bbox_ids": [str(bid) for bid in c.bbox_ids]
                        if c.bbox_ids
                        else None,
                    }
                )
                .eq("id", oid)
                .execute()
            )
            updated_count += 1

    return {
        "document_id": document_id,
        "total_chunks": len(chunks_to_update),
        "updated": updated_count,
        "skipped": False,
    }


async def backfill_all(matter_id: str | None = None, limit: int | None = None):
    """Backfill chunk page numbers for all documents.

    Args:
        matter_id: Optional matter ID to filter documents
        limit: Optional limit on number of documents to process
    """
    client = get_service_client()
    bbox_service = get_bounding_box_service()

    # Build query for documents with chunks missing page_number
    query = (
        client.table("chunks")
        .select("document_id", count="exact")
        .is_("page_number", "null")
    )

    if matter_id:
        # Need to filter by matter_id through documents table
        doc_query = client.table("documents").select("id").eq("matter_id", matter_id)
        doc_result = doc_query.execute()
        doc_ids = [d["id"] for d in doc_result.data or []]

        if not doc_ids:
            print(f"No documents found for matter {matter_id}")
            return

        query = query.in_("document_id", doc_ids)

    # Get distinct document IDs with missing page numbers
    # Using raw query since Supabase client doesn't support DISTINCT
    response = query.execute()

    if not response.data:
        print("No chunks found with missing page_number")
        return

    # Get unique document IDs
    document_ids = list(set(row["document_id"] for row in response.data))

    if limit:
        document_ids = document_ids[:limit]

    print(f"Found {len(document_ids)} documents to process")

    # Process each document
    total_updated = 0
    for i, doc_id in enumerate(document_ids, 1):
        print(f"[{i}/{len(document_ids)}] Processing document {doc_id}...")

        try:
            result = await backfill_document_chunks(doc_id, client, bbox_service)

            if result["skipped"]:
                print("  Skipped (no chunks without page_number)")
            else:
                print(f"  Updated {result['updated']}/{result['total_chunks']} chunks")
                total_updated += result["updated"]

        except Exception as e:
            print(f"  Error: {e}")
            logger.exception("backfill_document_failed", document_id=doc_id)

    print(
        f"\nDone! Updated {total_updated} chunks across {len(document_ids)} documents"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Backfill chunk page numbers from bounding boxes"
    )
    parser.add_argument("--matter-id", help="Filter to specific matter ID")
    parser.add_argument(
        "--limit", type=int, help="Limit number of documents to process"
    )

    args = parser.parse_args()

    asyncio.run(backfill_all(matter_id=args.matter_id, limit=args.limit))


if __name__ == "__main__":
    main()
