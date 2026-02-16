#!/usr/bin/env python3
"""Check pipeline status - documents and entity stats."""
import sys
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

client = get_supabase_client()

# Check document status
docs = client.table('documents').select('status').execute()
status_counts = {}
for d in docs.data:
    s = d['status']
    status_counts[s] = status_counts.get(s, 0) + 1

print('=== DOCUMENT STATUS ===')
for status, count in sorted(status_counts.items()):
    print(f'  {status}: {count}')
print(f'  TOTAL: {len(docs.data)}')

# Check entity counts
entities = client.table('identity_nodes').select('id', count='exact').execute()
mentions = client.table('entity_mentions').select('id', count='exact').execute()

print()
print('=== ENTITY STATS ===')
print(f'  Identity nodes: {entities.count}')
print(f'  Entity mentions: {mentions.count}')

print()
print('Pipeline verification complete!')
