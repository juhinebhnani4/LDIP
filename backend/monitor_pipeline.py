import os
import sys
import time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')

client = create_client(url, key)
doc_id = 'ed3313dc-0ff4-4079-8aee-656b48dad9e7'

print('=== Monitoring Pipeline Progress ===')
print()

last_status = ''
for i in range(60):
    doc = client.table('documents').select('status, page_count').eq('id', doc_id).single().execute()
    status = doc.data['status']

    chunks = client.table('chunks').select('id, embedding', count='exact').eq('document_id', doc_id).execute()
    chunk_count = chunks.count if hasattr(chunks, 'count') else len(chunks.data)
    with_embedding = sum(1 for c in chunks.data if c.get('embedding')) if chunks.data else 0

    entities = client.table('entity_mentions').select('id', count='exact').eq('document_id', doc_id).execute()
    entity_count = entities.count if hasattr(entities, 'count') else 0

    status_line = f'[{i+1}] Status: {status} | Chunks: {chunk_count} | Embeddings: {with_embedding} | Entities: {entity_count}'

    if status_line != last_status:
        print(status_line)
        last_status = status_line

    if status in ['completed', 'failed']:
        print(f'Pipeline reached terminal state: {status}')
        break

    time.sleep(5)

print()
print('=== Final Status ===')
doc = client.table('documents').select('status, page_count, validation_status').eq('id', doc_id).single().execute()
print(f'Document Status: {doc.data["status"]}')
print(f'Pages: {doc.data["page_count"]}')

chunks = client.table('chunks').select('*', count='exact').eq('document_id', doc_id).execute()
print(f'Chunks: {chunks.count if hasattr(chunks, "count") else len(chunks.data)}')
with_emb = sum(1 for c in chunks.data if c.get('embedding'))
print(f'Chunks with embeddings: {with_emb}')

entities = client.table('entity_mentions').select('id', count='exact').eq('document_id', doc_id).execute()
print(f'Entities: {entities.count if hasattr(entities, "count") else 0}')
