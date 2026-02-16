"""Sync job status based on actual document processing state.

This script checks the actual state of documents (chunks, embeddings, entities, etc.)
and updates the processing_job status to match reality.
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client


def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Get all non-completed jobs
    response = client.table("processing_jobs").select("*").in_(
        "status", ["QUEUED", "PROCESSING"]
    ).execute()
    jobs = response.data

    if not jobs:
        print("No active jobs to sync!")
        return

    print(f"Found {len(jobs)} active jobs to check\n")

    for job in jobs:
        job_id = job['id']
        doc_id = job['document_id']
        matter_id = job['matter_id']
        current_stage = job['current_stage']

        # Check document state
        doc_resp = client.table("documents").select("status").eq("id", doc_id).execute()
        doc_status = doc_resp.data[0]['status'] if doc_resp.data else None

        # Check chunks
        chunks_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).execute()
        chunk_count = chunks_resp.count or 0

        # Check embeddings
        emb_resp = client.table("chunks").select("id", count="exact").eq("document_id", doc_id).not_.is_("embedding", "null").execute()
        embedded_count = emb_resp.count or 0

        # Check entities (by matter since no document_id)
        entity_resp = client.table("identity_nodes").select("id", count="exact").eq("matter_id", matter_id).execute()
        entity_count = entity_resp.count or 0

        # Check citations for this document (column is source_document_id)
        citation_resp = client.table("citations").select("id", count="exact").eq("source_document_id", doc_id).execute()
        citation_count = citation_resp.count or 0

        # Determine actual stage based on data
        actual_stage = None
        completed_stages = 0
        progress_pct = 0

        if chunk_count == 0:
            actual_stage = "chunking"
            completed_stages = 3  # OCR, validation, confidence
            progress_pct = 40
        elif embedded_count < chunk_count:
            actual_stage = "embedding"
            completed_stages = 4  # + chunking
            progress_pct = 60
        elif entity_count == 0:
            actual_stage = "entity_extraction"
            completed_stages = 5  # + embedding
            progress_pct = 70
        elif citation_count == 0 and doc_status != 'indexed':
            # Has entities but no citations yet - at alias_resolution stage
            actual_stage = "alias_resolution"
            completed_stages = 6  # + entity_extraction
            progress_pct = 80
        else:
            # Has entities AND (has citations OR is indexed) - fully complete
            actual_stage = "citation_extraction"
            completed_stages = 8
            progress_pct = 100

        # Update if different
        if current_stage != actual_stage or job['progress_pct'] != progress_pct:
            # Mark as COMPLETED if we're at 100%
            new_status = "COMPLETED" if progress_pct == 100 else "QUEUED"

            client.table("processing_jobs").update({
                "status": new_status,
                "current_stage": actual_stage,
                "completed_stages": completed_stages,
                "progress_pct": progress_pct,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()

            print(f"  [SYNC] {job_id[:12]}... {current_stage}({job['progress_pct']}%) -> {actual_stage}({progress_pct}%) [{new_status}]")
        else:
            print(f"  [OK] {job_id[:12]}... {current_stage}({progress_pct}%) - already synced")

    print("\n[DONE]")


if __name__ == "__main__":
    main()
