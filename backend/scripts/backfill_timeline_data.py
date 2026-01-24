#!/usr/bin/env python3
"""Backfill timeline event data (source_page, classification, entity linking).

This script fixes existing events that have NULL source_page, are unclassified
(raw_date), or missing entity links.

Usage:
    python scripts/backfill_timeline_data.py --matter-id <UUID>
    python scripts/backfill_timeline_data.py --all
    python scripts/backfill_timeline_data.py --dry-run --all

Options:
    --matter-id: Process events for a specific matter
    --all: Process all matters
    --dry-run: Show what would be done without making changes
    --skip-page-backfill: Skip source_page backfill
    --skip-classification: Skip event classification
    --skip-entity-linking: Skip entity linking
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase.client import get_supabase_client


def backfill_source_pages(client, matter_id: str, dry_run: bool = False) -> dict:
    """Backfill source_page for events by matching descriptions to chunks.

    Strategy: For each event, find chunks from the same document that contain
    the event's date_text. Use the chunk's page_number for the event.
    """
    print(f"\n=== Backfilling source_page for matter {matter_id[:8]}... ===")

    # Get events with NULL source_page
    events = client.table('events').select(
        'id, document_id, event_date_text, description'
    ).eq('matter_id', matter_id).is_('source_page', 'null').execute()

    print(f"Found {len(events.data)} events with NULL source_page")

    if not events.data:
        return {"events_checked": 0, "events_updated": 0}

    # Get all chunks for this matter with page_number
    chunks = client.table('chunks').select(
        'id, document_id, content, page_number, bbox_ids'
    ).eq('matter_id', matter_id).not_.is_('page_number', 'null').execute()

    print(f"Found {len(chunks.data)} chunks with page_number")

    # Build document -> chunks mapping
    doc_chunks = {}
    for chunk in chunks.data:
        doc_id = chunk['document_id']
        if doc_id not in doc_chunks:
            doc_chunks[doc_id] = []
        doc_chunks[doc_id].append(chunk)

    updates = []
    for event in events.data:
        doc_id = event['document_id']
        if not doc_id or doc_id not in doc_chunks:
            continue

        # Find chunk containing the date_text
        date_text = event.get('event_date_text', '')
        if not date_text:
            continue

        for chunk in doc_chunks[doc_id]:
            if date_text in chunk['content']:
                updates.append({
                    'event_id': event['id'],
                    'source_page': chunk['page_number'],
                    'source_bbox_ids': chunk.get('bbox_ids') or [],
                })
                break

    print(f"Found {len(updates)} events that can be updated")

    if dry_run:
        print("[DRY RUN] Would update these events:")
        for u in updates[:5]:
            print(f"  Event {u['event_id'][:8]}... -> page {u['source_page']}")
        if len(updates) > 5:
            print(f"  ... and {len(updates) - 5} more")
        return {"events_checked": len(events.data), "events_updated": 0, "would_update": len(updates)}

    # Apply updates
    updated = 0
    for u in updates:
        try:
            client.table('events').update({
                'source_page': u['source_page'],
                'source_bbox_ids': u['source_bbox_ids'],
            }).eq('id', u['event_id']).execute()
            updated += 1
        except Exception as e:
            print(f"  Error updating event {u['event_id'][:8]}...: {e}")

    print(f"Updated {updated} events with source_page")
    return {"events_checked": len(events.data), "events_updated": updated}


def trigger_classification(matter_id: str, dry_run: bool = False) -> dict:
    """Trigger classification for all raw_date events."""
    print(f"\n=== Triggering classification for matter {matter_id[:8]}... ===")

    if dry_run:
        print("[DRY RUN] Would trigger classify_events_for_matter task")
        return {"status": "dry_run"}

    from app.workers.tasks.engine_tasks import classify_events_for_matter

    task = classify_events_for_matter.delay(
        matter_id=matter_id,
        force_reclassify=False,  # Only classify raw_date events
    )

    print(f"Classification task queued: {task.id}")
    return {"status": "queued", "task_id": task.id}


def trigger_entity_linking(matter_id: str, dry_run: bool = False) -> dict:
    """Trigger entity linking for all events without entities."""
    print(f"\n=== Triggering entity linking for matter {matter_id[:8]}... ===")

    if dry_run:
        print("[DRY RUN] Would trigger link_entities_for_matter task")
        return {"status": "dry_run"}

    from app.workers.tasks.engine_tasks import link_entities_for_matter

    task = link_entities_for_matter.delay(
        matter_id=matter_id,
    )

    print(f"Entity linking task queued: {task.id}")
    return {"status": "queued", "task_id": task.id}


def get_all_matters(client) -> list[str]:
    """Get all matter IDs that have events."""
    result = client.table('events').select('matter_id').execute()
    return list(set(e['matter_id'] for e in result.data))


def main():
    parser = argparse.ArgumentParser(description='Backfill timeline event data')
    parser.add_argument('--matter-id', help='Process specific matter')
    parser.add_argument('--all', action='store_true', help='Process all matters')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--skip-page-backfill', action='store_true', help='Skip source_page backfill')
    parser.add_argument('--skip-classification', action='store_true', help='Skip classification')
    parser.add_argument('--skip-entity-linking', action='store_true', help='Skip entity linking')

    args = parser.parse_args()

    if not args.matter_id and not args.all:
        parser.error("Either --matter-id or --all must be specified")

    client = get_supabase_client()

    if args.all:
        matter_ids = get_all_matters(client)
        print(f"Found {len(matter_ids)} matters with events")
    else:
        matter_ids = [args.matter_id]

    total_results = {
        "matters_processed": 0,
        "page_backfill": {"events_checked": 0, "events_updated": 0},
        "classification": [],
        "entity_linking": [],
    }

    for matter_id in matter_ids:
        print(f"\n{'='*60}")
        print(f"Processing matter: {matter_id}")
        print('='*60)

        # Step 1: Backfill source_page
        if not args.skip_page_backfill:
            result = backfill_source_pages(client, matter_id, args.dry_run)
            total_results["page_backfill"]["events_checked"] += result.get("events_checked", 0)
            total_results["page_backfill"]["events_updated"] += result.get("events_updated", 0)

        # Step 2: Classification (only if not dry run for tasks)
        if not args.skip_classification:
            result = trigger_classification(matter_id, args.dry_run)
            total_results["classification"].append(result)

        # Step 3: Entity linking (only if not dry run for tasks)
        if not args.skip_entity_linking:
            result = trigger_entity_linking(matter_id, args.dry_run)
            total_results["entity_linking"].append(result)

        total_results["matters_processed"] += 1

    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Matters processed: {total_results['matters_processed']}")
    print(f"Page backfill: {total_results['page_backfill']['events_updated']}/{total_results['page_backfill']['events_checked']} events updated")
    print(f"Classification tasks: {len([r for r in total_results['classification'] if r.get('status') == 'queued'])} queued")
    print(f"Entity linking tasks: {len([r for r in total_results['entity_linking'] if r.get('status') == 'queued'])} queued")


if __name__ == "__main__":
    main()
