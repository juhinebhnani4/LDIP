"""Retry the stuck processing job."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# Get all jobs for the matter to find the stuck one
matter_id = "44309951-44c3-4b9a-acfd-8ea82000c4df"
jobs = client.table("processing_jobs").select("*").eq("matter_id", matter_id).eq("status", "PROCESSING").execute()

if not jobs.data:
    print("No stuck PROCESSING jobs found!")
    exit(1)

job_data = jobs.data[0]
job_id = job_data['id']
document_id = job_data['document_id']

print(f"Found stuck job:")
print(f"  Job ID: {job_id}")
print(f"  Document ID: {document_id}")
print(f"  Status: {job_data['status']}")
print(f"  Stage: {job_data['current_stage']}")
print(f"  Progress: {job_data['progress_pct']}%")
print(f"  Completed stages: {job_data['completed_stages']}/{job_data['total_stages']}")

# Reset job to re-queue it
print("\nResetting job to QUEUED status to trigger re-processing...")

result = client.table("processing_jobs").update({
    "status": "QUEUED",
    "celery_task_id": None,
    "error_message": None,
    "error_code": None,
}).eq("id", job_id).execute()

print("Job reset to QUEUED.")

# Now trigger the task
from app.workers.tasks.document_tasks import process_document

print(f"\nQueuing process_document task for document: {document_id}")
task = process_document.delay(document_id)
print(f"Task queued with ID: {task.id}")

# Update job with new task ID
client.table("processing_jobs").update({
    "celery_task_id": task.id
}).eq("id", job_id).execute()

print("\nDone! Check Celery logs for processing.")
