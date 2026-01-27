#!/usr/bin/env python3
"""Backfill entities_involved for timeline events.

This script triggers entity linking for all events in a matter,
populating the entities_involved field so that cross-engine
Timeline Journey links work correctly.

Usage:
    python scripts/backfill_event_entities.py <matter_id> [--force]

    --force: Relink all events, even if they already have entities
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import structlog
from app.services.supabase.client import get_service_client
from app.engines.timeline.entity_linker import get_event_entity_linker
from app.services.mig.graph import get_mig_graph_service
from app.services.timeline_service import get_timeline_service
from app.models.entity import EntityNode, EntityType

logger = structlog.get_logger(__name__)


def load_entities_sync(matter_id: str, batch_size: int = 500) -> list[EntityNode]:
    """Load all entities for a matter synchronously using Supabase client."""
    client = get_service_client()
    all_entities: list[EntityNode] = []
    page = 0

    while True:
        offset = page * batch_size
        response = (
            client.table("identity_nodes")
            .select("*")
            .eq("matter_id", matter_id)
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        if not response.data:
            break

        for row in response.data:
            entity = EntityNode(
                id=row["id"],
                matter_id=row["matter_id"],
                canonical_name=row["canonical_name"],
                entity_type=EntityType(row["entity_type"]) if row.get("entity_type") else EntityType.PERSON,
                aliases=row.get("aliases") or [],
                mention_count=row.get("mention_count", 0),
                confidence=row.get("confidence", 0.0),
                first_seen_at=row.get("first_seen_at"),
                last_seen_at=row.get("last_seen_at"),
                source_documents=row.get("source_documents") or [],
                metadata=row.get("metadata") or {},
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
            all_entities.append(entity)

        if len(response.data) < batch_size:
            break
        page += 1

    print(f"  Loaded {len(all_entities)} entities in {page + 1} pages")
    return all_entities


def backfill_event_entities(matter_id: str, force_relink: bool = False) -> dict:
    """Backfill entities_involved for all events in a matter.

    Args:
        matter_id: Matter UUID
        force_relink: If True, reprocess all events (not just unlinked)

    Returns:
        Dict with results summary
    """
    print(f"\n{'='*60}")
    print(f"Backfilling entities_involved for matter: {matter_id}")
    print(f"Force relink: {force_relink}")
    print(f"{'='*60}\n")

    timeline_service = get_timeline_service()
    mig_service = get_mig_graph_service()
    entity_linker = get_event_entity_linker()

    # Get events to process
    if force_relink:
        # Get all events using the reclassification method (which gets all)
        events_to_process = timeline_service.get_all_events_for_reclassification_sync(
            matter_id=matter_id,
            limit=10000,
        )
        print(f"Processing ALL {len(events_to_process)} events (force relink)")
    else:
        # Get only events without entity links
        events_to_process = timeline_service.get_events_for_entity_linking_sync(
            matter_id=matter_id,
            limit=10000,
        )
        print(f"Processing {len(events_to_process)} events without entity links")

    if not events_to_process:
        print("No events to process!")
        return {"status": "no_events", "processed": 0, "updated": 0}

    # Load all entities for the matter
    print("\nLoading entities from MIG...")
    entities = load_entities_sync(matter_id)

    if not entities:
        print("No entities found in matter - cannot link events")
        return {"status": "no_entities", "processed": 0, "updated": 0}

    # Process events in batches
    batch_size = 50
    total_processed = 0
    total_updated = 0

    for i in range(0, len(events_to_process), batch_size):
        batch = events_to_process[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(events_to_process) + batch_size - 1) // batch_size

        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} events)...")

        # Link entities for this batch using parallel sync processing
        event_entities = entity_linker.link_entities_batch_parallel(
            events=batch,
            matter_id=matter_id,
            entities=entities,
            max_workers=10,
        )

        # Update database
        if event_entities:
            updated = timeline_service.bulk_update_event_entities_sync(
                event_entities=event_entities,
                matter_id=matter_id,
            )
            total_updated += updated
            print(f"  Updated {updated} events with entity links")

        total_processed += len(batch)

    print(f"\n{'='*60}")
    print(f"COMPLETED")
    print(f"  Total events processed: {total_processed}")
    print(f"  Total events updated: {total_updated}")
    print(f"{'='*60}\n")

    return {
        "status": "completed",
        "matter_id": matter_id,
        "processed": total_processed,
        "updated": total_updated,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill entities_involved for timeline events"
    )
    parser.add_argument("matter_id", help="Matter UUID to process")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Relink all events, even if they already have entities",
    )

    args = parser.parse_args()

    result = backfill_event_entities(args.matter_id, args.force)

    if result["status"] == "completed":
        print("Backfill completed successfully!")
        return 0
    else:
        print(f"Backfill finished with status: {result['status']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
