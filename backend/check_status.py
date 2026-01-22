"""Check processing job status."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# Get the processing job for the matter
matter_id = "44309951-44c3-4b9a-acfd-8ea82000c4df"
jobs = client.table("processing_jobs").select("*").eq("matter_id", matter_id).execute()

print(f"Found {len(jobs.data)} jobs:\n")
for job in jobs.data:
    print(f"Job ID: {job['id'][:8]}...")
    print(f"  Document ID: {job['document_id'][:8]}...")
    print(f"  Status: {job['status']}")
    print(f"  Current Stage: {job['current_stage']}")
    print(f"  Progress: {job['progress_pct']}%")
    print(f"  Completed Stages: {job['completed_stages']}/{job['total_stages']}")
    print(f"  Celery Task ID: {job.get('celery_task_id', 'N/A')}")
    print(f"  Created: {job['created_at']}")
    print(f"  Updated: {job['updated_at']}")
    if job.get('error_message'):
        print(f"  Error: {job['error_message'][:100]}...")
    print()
