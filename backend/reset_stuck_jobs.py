"""Reset all stuck jobs and queue them for fresh processing.

This script:
1. Finds all jobs stuck in PROCESSING or with high recovery_attempts
2. Resets their status to QUEUED
3. Clears error messages and recovery attempts
4. Optionally requeues the Celery tasks

Usage:
    python reset_stuck_jobs.py [--requeue]
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client

def main():
    requeue = '--requeue' in sys.argv

    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Find stuck jobs (PROCESSING status)
    response = client.table("processing_jobs").select("*").eq("status", "PROCESSING").execute()
    stuck_jobs = response.data

    # Also find QUEUED jobs that are stale (older than 30 min with no progress)
    response2 = client.table("processing_jobs").select("*").eq("status", "QUEUED").execute()
    queued_jobs = [j for j in (response2.data or []) if j.get('progress_pct', 0) == 0]

    all_stuck = stuck_jobs + queued_jobs

    if not all_stuck:
        print("No stuck jobs found!")
        return

    print(f"\nFound {len(all_stuck)} stuck/stale jobs:")
    for j in all_stuck:
        stage = j.get('current_stage') or 'N/A'
        pct = j.get('progress_pct', 0)
        rec = (j.get('metadata') or {}).get('recovery_attempts', 0)
        print(f"  - {j['id'][:8]}... | {j['status']} | {stage} | {pct}% | recovery: {rec}")

    confirm = input("\nReset all these jobs? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    print("\nResetting jobs...")
    reset_count = 0

    for job in all_stuck:
        job_id = job['id']
        document_id = job.get('document_id')

        # Reset job
        client.table("processing_jobs").update({
            "status": "QUEUED",
            "current_stage": None,
            "completed_stages": 0,
            "progress_pct": 0,
            "error_message": None,
            "error_code": None,
            "retry_count": 0,
            "started_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {},  # Clear recovery attempts
        }).eq("id", job_id).execute()

        # Reset document status
        if document_id:
            client.table("documents").update({
                "status": "PENDING",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", document_id).execute()

        reset_count += 1
        print(f"  Reset: {job_id[:8]}...")

    print(f"\n✓ Reset {reset_count} jobs to QUEUED status")

    if requeue:
        print("\nRequeuing Celery tasks...")
        from app.workers.tasks.document_tasks import process_document

        for job in all_stuck:
            doc_id = job.get('document_id')
            if doc_id:
                process_document.apply_async(args=[doc_id], countdown=2)
                print(f"  Queued: {doc_id[:8]}...")

        print(f"\n✓ Queued {len(all_stuck)} tasks")
    else:
        print("\nRun with --requeue flag to also dispatch Celery tasks")
        print("Or start the Celery worker - it will pick up QUEUED jobs automatically")

    print("\nDone! Make sure Celery worker is running:")
    print("  cd backend && .venv\\Scripts\\celery -A app.workers.celery worker --pool=threads --concurrency=4 -l INFO")

if __name__ == "__main__":
    main()
