"""Dispatch QUEUED jobs to Celery worker.

This script finds jobs that are QUEUED but not being processed
and dispatches them to the Celery queue.
"""

import sys

sys.path.insert(0, ".")

from app.services.supabase.client import get_supabase_client


def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Find QUEUED jobs
    response = (
        client.table("processing_jobs").select("*").eq("status", "QUEUED").execute()
    )
    queued_jobs = response.data

    if not queued_jobs:
        print("No QUEUED jobs found!")
        return

    print(f"Found {len(queued_jobs)} QUEUED jobs\n")

    # Import Celery tasks
    from app.workers.tasks.document_tasks import (
        embed_chunks,
        extract_entities,
        process_document,
        resolve_aliases,
    )

    for job in queued_jobs:
        job_id = job["id"]
        doc_id = job.get("document_id")
        stage = job.get("current_stage")

        if not doc_id:
            print(f"  [SKIP] {job_id[:12]}... - no document_id")
            continue

        # Dispatch based on current stage
        if stage == "embedding":
            embed_chunks.apply_async(
                kwargs={"document_id": doc_id, "force": True},
                countdown=1,
            )
            print(f"  [QUEUED] {job_id[:12]}... -> embed_chunks")
        elif stage == "entity_extraction":
            extract_entities.apply_async(
                kwargs={"document_id": doc_id, "force": True},
                countdown=1,
            )
            print(f"  [QUEUED] {job_id[:12]}... -> extract_entities")
        elif stage == "alias_resolution":
            resolve_aliases.apply_async(
                kwargs={"document_id": doc_id},
                countdown=1,
            )
            print(f"  [QUEUED] {job_id[:12]}... -> resolve_aliases")
        elif stage is None or stage == "":
            # Fresh job - start from beginning
            process_document.apply_async(
                args=[doc_id],
                countdown=1,
            )
            print(f"  [QUEUED] {job_id[:12]}... -> process_document (full)")
        else:
            print(f"  [SKIP] {job_id[:12]}... - unknown stage: {stage}")

    print("\n[DONE] Dispatched jobs to Celery")


if __name__ == "__main__":
    main()
