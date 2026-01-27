#!/usr/bin/env python3
"""Re-extract timeline events with improved prompts.

This script deletes existing extracted events and re-runs the date/event
extraction with the new improved prompts that:
- Generate meaningful event descriptions
- Classify events during extraction
- Filter out non-events (date ranges, citations, etc.)

Usage:
    python scripts/reextract_timeline_events.py --matter-id <UUID> --sync-linking
    python scripts/reextract_timeline_events.py --matter-id <UUID> --dry-run
    python scripts/reextract_timeline_events.py --matter-id <UUID> --keep-manual

Options:
    --matter-id: Process events for a specific matter (required)
    --dry-run: Show what would be done without making changes
    --keep-manual: Keep manually added events (is_manual=true)
    --batch-size: Number of chunks to process per batch (default: 10)
    --sync-linking: Run entity linking synchronously (RECOMMENDED - does not depend on Celery worker)
"""

import argparse
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase.client import get_supabase_client
from app.engines.timeline.date_extractor import get_date_extractor
from app.services.timeline_service import get_timeline_service


def get_matter_info(client, matter_id: str) -> dict | None:
    """Get matter information."""
    result = client.table('matters').select('id, title').eq('id', matter_id).execute()
    if result.data:
        # Normalize to use 'name' for compatibility
        data = result.data[0]
        data['name'] = data.get('title', 'Unknown')
        return data
    return None


def count_events(client, matter_id: str, include_manual: bool = True) -> dict:
    """Count events for a matter."""
    query = client.table('events').select('id, is_manual', count='exact').eq('matter_id', matter_id)
    result = query.execute()

    total = len(result.data)
    manual = sum(1 for e in result.data if e.get('is_manual'))
    extracted = total - manual

    return {
        "total": total,
        "manual": manual,
        "extracted": extracted,
    }


def delete_extracted_events(client, matter_id: str, keep_manual: bool = True, dry_run: bool = False) -> int:
    """Delete extracted (non-manual) events for a matter."""
    query = client.table('events').select('id').eq('matter_id', matter_id)

    if keep_manual:
        query = query.eq('is_manual', False)

    events = query.execute()
    event_ids = [e['id'] for e in events.data]

    print(f"Found {len(event_ids)} events to delete")

    if dry_run:
        print("[DRY RUN] Would delete these events")
        return 0

    if not event_ids:
        return 0

    # Delete in batches to avoid timeout
    batch_size = 100
    deleted = 0
    for i in range(0, len(event_ids), batch_size):
        batch = event_ids[i:i + batch_size]
        client.table('events').delete().in_('id', batch).execute()
        deleted += len(batch)
        print(f"  Deleted {deleted}/{len(event_ids)} events...")

    return deleted


def get_document_chunks(client, matter_id: str) -> list[dict]:
    """Get all chunks for documents in a matter."""
    # Get documents for the matter
    docs = client.table('documents').select('id, filename').eq('matter_id', matter_id).execute()

    if not docs.data:
        print("No documents found for this matter")
        return []

    print(f"Found {len(docs.data)} documents")

    # Get chunks for all documents
    doc_ids = [d['id'] for d in docs.data]
    doc_names = {d['id']: d['filename'] for d in docs.data}

    all_chunks = []
    for doc_id in doc_ids:
        chunks = client.table('chunks').select(
            'id, document_id, content, page_number, bbox_ids'
        ).eq('document_id', doc_id).order('created_at').execute()

        for chunk in chunks.data:
            chunk['document_name'] = doc_names.get(doc_id, 'Unknown')

        all_chunks.extend(chunks.data)

    print(f"Found {len(all_chunks)} chunks to process")
    return all_chunks


def extract_events_from_chunks(
    chunks: list[dict],
    matter_id: str,
    batch_size: int = 10,
    dry_run: bool = False
) -> dict:
    """Extract events from chunks using the improved prompts."""
    extractor = get_date_extractor()
    timeline_service = get_timeline_service()

    total_events = 0
    total_chunks = len(chunks)
    events_by_type = {}

    print(f"\nProcessing {total_chunks} chunks in batches of {batch_size}...")

    for i in range(0, total_chunks, batch_size):
        batch = chunks[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_chunks + batch_size - 1) // batch_size

        print(f"\nBatch {batch_num}/{total_batches}:")

        for chunk in batch:
            content = chunk.get('content', '')
            if not content or len(content) < 20:
                continue

            doc_id = chunk['document_id']
            doc_name = chunk.get('document_name', 'Unknown')[:30]
            page = chunk.get('page_number')

            try:
                # Extract dates/events using the improved prompts
                result = extractor.extract_dates_sync(
                    text=content,
                    document_id=doc_id,
                    matter_id=matter_id,
                    page_number=page,
                    bbox_ids=chunk.get('bbox_ids') or [],
                )

                if result.dates:
                    print(f"  [{doc_name}] p{page}: {len(result.dates)} events")

                    for date_obj in result.dates:
                        event_type = getattr(date_obj, 'event_type', 'unclassified')
                        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

                    if not dry_run:
                        # Save to database
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                timeline_service.save_extracted_dates(
                                    matter_id=matter_id,
                                    document_id=doc_id,
                                    dates=result.dates,
                                )
                            )
                        finally:
                            loop.close()

                    total_events += len(result.dates)

            except Exception as e:
                print(f"  [ERROR] {doc_name} p{page}: {e}")

        # Small delay between batches to avoid rate limiting
        if i + batch_size < total_chunks:
            time.sleep(1)

    return {
        "total_events": total_events,
        "events_by_type": events_by_type,
        "chunks_processed": total_chunks,
    }


def main():
    parser = argparse.ArgumentParser(description='Re-extract timeline events with improved prompts')
    parser.add_argument('--matter-id', required=True, help='Matter ID to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--keep-manual', action='store_true', help='Keep manually added events')
    parser.add_argument('--batch-size', type=int, default=10, help='Chunks per batch')
    parser.add_argument('--sync-linking', action='store_true',
                        help='Run entity linking synchronously (recommended - does not depend on Celery)')

    args = parser.parse_args()

    client = get_supabase_client()

    # Get matter info
    matter = get_matter_info(client, args.matter_id)
    if not matter:
        print(f"Error: Matter {args.matter_id} not found")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Re-extracting Timeline Events")
    print(f"Matter: {matter['name']}")
    print(f"ID: {args.matter_id}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Keep manual events: {args.keep_manual}")
    print('='*60)

    # Count existing events
    counts = count_events(client, args.matter_id)
    print(f"\nExisting events:")
    print(f"  Total: {counts['total']}")
    print(f"  Manual: {counts['manual']}")
    print(f"  Extracted: {counts['extracted']}")

    # Step 1: Delete extracted events
    print(f"\n--- Step 1: Delete existing extracted events ---")
    deleted = delete_extracted_events(
        client,
        args.matter_id,
        keep_manual=args.keep_manual,
        dry_run=args.dry_run
    )

    if not args.dry_run:
        print(f"Deleted {deleted} extracted events")

    # Step 2: Get document chunks
    print(f"\n--- Step 2: Get document chunks ---")
    chunks = get_document_chunks(client, args.matter_id)

    if not chunks:
        print("No chunks to process")
        return

    # Step 3: Re-extract events
    print(f"\n--- Step 3: Extract events with improved prompts ---")
    result = extract_events_from_chunks(
        chunks,
        args.matter_id,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Chunks processed: {result['chunks_processed']}")
    print(f"Events extracted: {result['total_events']}")
    print(f"\nEvents by type:")
    for event_type, count in sorted(result['events_by_type'].items(), key=lambda x: -x[1]):
        print(f"  {event_type}: {count}")

    if args.dry_run:
        print("\n[DRY RUN] No changes were made to the database")
    elif args.sync_linking:
        # Run entity linking synchronously (recommended - doesn't depend on Celery)
        print("\n--- Step 4: Run entity linking synchronously ---")
        try:
            from app.engines.timeline.entity_linker import get_event_entity_linker
            from app.models.entity import EntityNode, EntityType

            entity_linker = get_event_entity_linker()

            # Load entities for the matter
            print("Loading entities from MIG...")
            entities_result = client.table("identity_nodes").select("*").eq("matter_id", args.matter_id).execute()
            entities = []
            for row in entities_result.data or []:
                entities.append(EntityNode(
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
                ))
            print(f"Loaded {len(entities)} entities")

            if entities:
                # Get all events for the matter
                events_result = client.table("events").select("*").eq("matter_id", args.matter_id).execute()
                from app.models.timeline import TimelineRawEvent

                events = []
                for row in events_result.data or []:
                    events.append(TimelineRawEvent(
                        id=row["id"],
                        matter_id=row["matter_id"],
                        document_id=row.get("document_id"),
                        event_date=row.get("event_date"),
                        event_type=row.get("event_type", "raw_date"),
                        description=row.get("description", ""),
                        confidence=row.get("confidence", 1.0),
                        source_page=row.get("source_page"),
                        is_manual=row.get("is_manual", False),
                        entities_involved=row.get("entities_involved") or [],
                    ))
                print(f"Found {len(events)} events to link")

                # Process in batches
                batch_size = 50
                total_updated = 0
                for i in range(0, len(events), batch_size):
                    batch = events[i:i + batch_size]
                    event_entities = entity_linker.link_entities_batch_parallel(
                        events=batch,
                        matter_id=args.matter_id,
                        entities=entities,
                        max_workers=10,
                    )
                    if event_entities:
                        updated = timeline_service.bulk_update_event_entities_sync(
                            event_entities=event_entities,
                            matter_id=args.matter_id,
                        )
                        total_updated += updated
                    print(f"  Batch {i // batch_size + 1}: linked {len(event_entities)} events")

                print(f"Entity linking complete: {total_updated} events updated")
            else:
                print("No entities found - skipping entity linking")

        except Exception as e:
            print(f"Entity linking failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        # Trigger classification and entity linking via Celery (requires worker running)
        print("\n--- Step 4: Trigger classification and entity linking (async) ---")
        print("WARNING: This requires Celery worker to be running. Use --sync-linking for guaranteed execution.")
        try:
            from app.workers.tasks.engine_tasks import classify_events_for_matter, link_entities_for_matter

            task1 = classify_events_for_matter.delay(matter_id=args.matter_id, force_reclassify=True)
            print(f"Classification task queued: {task1.id}")

            task2 = link_entities_for_matter.delay(matter_id=args.matter_id)
            print(f"Entity linking task queued: {task2.id}")
        except Exception as e:
            print(f"Could not queue background tasks: {e}")
            print("You may need to run the classification and entity linking manually")
            print("TIP: Use --sync-linking to run entity linking synchronously")


if __name__ == "__main__":
    main()
