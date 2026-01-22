"""Clear existing chunks for a document to allow retry."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

document_id = "bf5c0442-3482-47c3-9477-c9806c8ab8c5"

# Check existing chunks
chunks = client.table("document_ocr_chunks").select("id, chunk_index, status").eq("document_id", document_id).order("chunk_index").execute()

print(f"Found {len(chunks.data)} existing chunks for document {document_id[:8]}...\n")

if chunks.data:
    for chunk in chunks.data[:10]:  # Show first 10
        print(f"  Chunk {chunk['chunk_index']}: {chunk['status']}")
    if len(chunks.data) > 10:
        print(f"  ... and {len(chunks.data) - 10} more")

    print("\nDeleting all existing chunks...")
    result = client.table("document_ocr_chunks").delete().eq("document_id", document_id).execute()
    print(f"Deleted {len(result.data)} chunks")
else:
    print("No chunks to delete")

# Also reset the job status
print("\nResetting job status...")
job_result = client.table("processing_jobs").update({
    "status": "QUEUED",
    "current_stage": None,
    "progress_pct": 0,
    "completed_stages": 0,
    "celery_task_id": None,
    "error_message": None,
    "error_code": None,
}).eq("document_id", document_id).execute()

print(f"Reset {len(job_result.data)} job(s)")
print("\nReady to retry processing!")
