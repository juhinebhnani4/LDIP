"""Fix document status for completed jobs.

Sets document status to 'ocr_complete' for documents whose jobs are COMPLETED
but document status is still 'processing'.
"""

import sys

sys.path.insert(0, ".")

from datetime import UTC, datetime

from app.services.supabase.client import get_supabase_client


def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Get completed jobs
    jobs = (
        client.table("processing_jobs")
        .select("document_id")
        .eq("status", "COMPLETED")
        .execute()
    )
    completed_doc_ids = [j["document_id"] for j in jobs.data]

    print(f"Found {len(completed_doc_ids)} COMPLETED jobs\n")

    # Get documents with processing status that have completed jobs
    docs = (
        client.table("documents")
        .select("id, filename, status")
        .in_("id", completed_doc_ids)
        .eq("status", "processing")
        .execute()
    )

    if not docs.data:
        print("No documents need fixing!")
        return

    print(
        f"Found {len(docs.data)} documents with status='processing' but COMPLETED jobs:\n"
    )

    for d in docs.data:
        fname = (d["filename"] or "Unknown")[:55]
        print(f"  {fname}")

    auto_yes = "-y" in sys.argv or "--yes" in sys.argv
    if not auto_yes:
        print("\nRun with -y to fix these documents")
        return

    print("\nFixing documents...")
    for d in docs.data:
        doc_id = d["id"]
        try:
            client.table("documents").update(
                {
                    "status": "ocr_complete",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", doc_id).execute()
            print(f"  Fixed: {d['filename'][:40]}...")
        except Exception as e:
            print(f"  FAILED {d['filename'][:40]}: {e}")

    print("\n[DONE]")


if __name__ == "__main__":
    main()
