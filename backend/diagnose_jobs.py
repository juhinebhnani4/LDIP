"""Detailed diagnosis of stuck jobs."""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client

client = get_supabase_client()

# Get all non-completed jobs
response = client.table("processing_jobs").select("*").in_("status", ["PROCESSING", "QUEUED", "FAILED"]).order("updated_at", desc=True).execute()
jobs = response.data

print("="*80)
print("DETAILED JOB DIAGNOSIS")
print("="*80)

for j in jobs:
    job_id = j['id']
    doc_id = j.get('document_id', 'N/A')

    print(f"\nJob: {job_id[:12]}...")
    print(f"  Document: {doc_id[:12] if doc_id != 'N/A' else 'N/A'}...")
    print(f"  Status: {j['status']}")
    print(f"  Stage: {j.get('current_stage', 'N/A')}")
    print(f"  Progress: {j.get('progress_pct', 0)}%")
    print(f"  Retries: {j.get('retry_count', 0)}/{j.get('max_retries', 3)}")
    print(f"  Error: {j.get('error_message', 'None')}")
    print(f"  Error Code: {j.get('error_code', 'None')}")
    print(f"  Celery Task ID: {j.get('celery_task_id', 'None')}")

    # Check document status
    if doc_id and doc_id != 'N/A':
        doc_resp = client.table("documents").select("status, filename").eq("id", doc_id).limit(1).execute()
        if doc_resp.data:
            doc = doc_resp.data[0]
            print(f"  Document Status: {doc.get('status', 'N/A')}")
            print(f"  Filename: {doc.get('filename', 'N/A')}")
        else:
            print(f"  Document: NOT FOUND IN DB!")

    # Check metadata
    metadata = j.get('metadata', {})
    if metadata:
        print(f"  Metadata:")
        for k, v in metadata.items():
            val_str = str(v)[:80]
            print(f"    {k}: {val_str}")

print("\n" + "="*80)
print("RECOMMENDATIONS:")
print("="*80)

stuck_in_processing = [j for j in jobs if j['status'] == 'PROCESSING' and j.get('current_stage') == 'chunking']
if stuck_in_processing:
    print(f"\n{len(stuck_in_processing)} jobs stuck at chunking stage.")
    print("These jobs have recovery_attempts >= 3 and won't auto-recover.")
    print("\nTo reset them, run:")
    print("  python reset_stuck_jobs.py --requeue")
