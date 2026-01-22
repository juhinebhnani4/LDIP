"""Check chunk status for stuck documents."""
import sys
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

client = get_supabase_client()

# Document IDs from stuck jobs
doc_ids = [
    "ae3103b0-e54e-493a-b17e-85e9cb075f7a",
    "6b708dab-99a9-4f64-8c3f-7f54f7f54f7f",  # may be truncated
    "a2afd6de-3d0e-4a5e-8c3f-7f54f7f54f7f",  # may be truncated
]

# Get actual doc IDs from jobs
response = client.table("processing_jobs").select("document_id").in_("status", ["PROCESSING"]).eq("current_stage", "chunking").execute()
doc_ids = [j['document_id'] for j in response.data if j.get('document_id')]

print(f"Checking {len(doc_ids)} stuck documents for chunks...\n")

for doc_id in doc_ids:
    # Get chunks for this document
    chunk_resp = client.table("chunks").select("id, chunk_type, page_number", count="exact").eq("document_id", doc_id).execute()
    chunk_count = chunk_resp.count or 0

    # Get document info
    doc_resp = client.table("documents").select("filename, status, extracted_text").eq("id", doc_id).limit(1).execute()
    doc = doc_resp.data[0] if doc_resp.data else {}

    text_len = len(doc.get('extracted_text') or '') if doc.get('extracted_text') else 0

    print(f"Document: {doc_id[:12]}...")
    print(f"  Filename: {doc.get('filename', 'N/A')[:50]}")
    print(f"  Status: {doc.get('status', 'N/A')}")
    print(f"  Extracted text length: {text_len:,} chars")
    print(f"  Chunks in DB: {chunk_count}")

    if chunk_count > 0:
        # Get chunk breakdown
        parent_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).eq("chunk_type", "parent").execute()
        child_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).eq("chunk_type", "child").execute()
        print(f"    - Parent chunks: {parent_resp.count or 0}")
        print(f"    - Child chunks: {child_resp.count or 0}")

    print()

print("="*60)
print("ANALYSIS:")
print("="*60)
print("\nIf chunks exist, the chunking stage may be failing because")
print("it's trying to re-create chunks that already exist.")
print("\nSOLUTION: Skip chunking for these documents and move to embedding.")
