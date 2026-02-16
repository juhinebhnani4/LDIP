"""Fix FAILED jobs that have complete chunks and should continue.

These jobs failed at chunking but actually have complete chunks.
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client

def main():
    requeue = '--requeue' in sys.argv
    auto_yes = '-y' in sys.argv or '--yes' in sys.argv

    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Find FAILED jobs at chunking stage
    response = client.table("processing_jobs").select("*").eq("status", "FAILED").eq("current_stage", "chunking").execute()
    failed_jobs = response.data

    if not failed_jobs:
        print("No FAILED jobs at chunking stage!")
        return

    print(f"Found {len(failed_jobs)} FAILED jobs at chunking stage\n")

    jobs_to_fix = []

    for job in failed_jobs:
        doc_id = job.get('document_id')
        if not doc_id:
            continue

        # Check if BOTH parent and child chunks exist
        parent_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).eq("chunk_type", "parent").execute()
        child_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).eq("chunk_type", "child").execute()
        parent_count = parent_resp.count or 0
        child_count = child_resp.count or 0

        if parent_count > 0 and child_count > 0:
            jobs_to_fix.append({
                'job': job,
                'parent_count': parent_count,
                'child_count': child_count,
            })
            print(f"  [OK] {job['id'][:12]}... has {parent_count} parent + {child_count} child - CAN RECOVER")
        else:
            print(f"  [SKIP] {job['id'][:12]}... has incomplete chunks (p={parent_count}, c={child_count})")

    if not jobs_to_fix:
        print("\nNo recoverable jobs found.")
        return

    print(f"\n{len(jobs_to_fix)} jobs can be recovered to embedding stage.")

    if not auto_yes:
        confirm = input("\nFix these jobs? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

    print("\nFixing jobs...")

    for item in jobs_to_fix:
        job = item['job']
        job_id = job['id']
        doc_id = job['document_id']

        client.table("processing_jobs").update({
            "status": "QUEUED",
            "current_stage": "embedding",
            "completed_stages": 4,
            "progress_pct": 60,
            "error_message": None,
            "error_code": None,
            "retry_count": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"recovered_from_failed": True},
        }).eq("id", job_id).execute()

        # Also update document status
        client.table("documents").update({
            "status": "processing",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", doc_id).execute()

        print(f"  Fixed: {job_id[:12]}...")

    print(f"\n[DONE] Fixed {len(jobs_to_fix)} jobs")

    if requeue:
        print("\nRequeuing embedding tasks...")
        from app.workers.tasks.document_tasks import embed_document_chunks

        for item in jobs_to_fix:
            job = item['job']
            embed_document_chunks.apply_async(
                kwargs={"document_id": job['document_id'], "job_id": job['id']},
                countdown=2,
            )
            print(f"  Queued: {job['document_id'][:12]}...")

        print(f"\n[DONE] Queued {len(jobs_to_fix)} tasks")

if __name__ == "__main__":
    main()
