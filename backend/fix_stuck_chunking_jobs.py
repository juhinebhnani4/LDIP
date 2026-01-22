"""Fix jobs stuck at chunking stage when chunks already exist.

These jobs should be advanced to the embedding stage since chunking
is already complete.
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client

def main():
    requeue = '--requeue' in sys.argv
    dry_run = '--dry-run' in sys.argv

    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Find jobs stuck at chunking
    response = client.table("processing_jobs").select("*").eq("current_stage", "chunking").in_("status", ["PROCESSING", "QUEUED"]).execute()
    stuck_jobs = response.data

    if not stuck_jobs:
        print("No jobs stuck at chunking stage!")
        return

    print(f"Found {len(stuck_jobs)} jobs stuck at chunking stage\n")

    jobs_to_fix = []

    for job in stuck_jobs:
        doc_id = job.get('document_id')
        if not doc_id:
            continue

        # Check if BOTH parent and child chunks exist (complete chunking)
        parent_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).eq("chunk_type", "parent").execute()
        child_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).eq("chunk_type", "child").execute()
        parent_count = parent_resp.count or 0
        child_count = child_resp.count or 0
        total_count = parent_count + child_count

        if parent_count > 0 and child_count > 0:
            # Complete chunking - can skip to embedding
            jobs_to_fix.append({
                'job': job,
                'chunk_count': total_count,
                'parent_count': parent_count,
                'child_count': child_count,
            })
            print(f"  ✓ {job['id'][:12]}... has {parent_count} parent + {child_count} child chunks - COMPLETE, skip to embedding")
        elif parent_count > 0 or child_count > 0:
            # Partial chunking - needs re-chunking
            print(f"  ⚠ {job['id'][:12]}... has PARTIAL chunks (parent={parent_count}, child={child_count}) - needs re-chunking")
        else:
            print(f"  ✗ {job['id'][:12]}... has 0 chunks - needs actual reprocessing")

    if not jobs_to_fix:
        print("\nNo jobs with existing chunks found. Jobs need actual reprocessing.")
        print("Run: python reset_stuck_jobs.py --requeue")
        return

    print(f"\n{len(jobs_to_fix)} jobs have chunks and should skip to embedding stage.")

    if dry_run:
        print("\nDRY RUN - no changes made")
        return

    confirm = input("\nFix these jobs by advancing them to embedding? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    print("\nFixing jobs...")

    for item in jobs_to_fix:
        job = item['job']
        job_id = job['id']
        doc_id = job['document_id']
        matter_id = job['matter_id']

        # Update job to skip chunking and go to embedding
        client.table("processing_jobs").update({
            "status": "QUEUED",
            "current_stage": "embedding",  # Skip chunking, go to embedding
            "completed_stages": 4,  # OCR, validation, confidence, chunking = 4 stages done
            "progress_pct": 60,  # Keep at 60% (embedding is next)
            "error_message": None,
            "error_code": None,
            "retry_count": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"fixed_stuck_chunking": True, "chunks_existed": item['chunk_count']},
        }).eq("id", job_id).execute()

        print(f"  Fixed: {job_id[:12]}... -> embedding stage")

    print(f"\n✓ Fixed {len(jobs_to_fix)} jobs")

    if requeue:
        print("\nRequeuing embedding tasks...")
        from app.workers.tasks.document_tasks import embed_document_chunks

        for item in jobs_to_fix:
            job = item['job']
            doc_id = job['document_id']
            job_id = job['id']

            embed_document_chunks.apply_async(
                kwargs={
                    "document_id": doc_id,
                    "job_id": job_id,
                },
                countdown=2,
            )
            print(f"  Queued embedding: {doc_id[:12]}...")

        print(f"\n✓ Queued {len(jobs_to_fix)} embedding tasks")
    else:
        print("\nRun with --requeue to also dispatch embedding tasks to Celery")
        print("Or use the Celery Beat scheduler to pick them up automatically")

if __name__ == "__main__":
    main()
