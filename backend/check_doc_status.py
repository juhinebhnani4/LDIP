"""Check document status for completed jobs."""
import sys
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Get completed jobs
    jobs = client.table("processing_jobs").select("document_id, status").eq("status", "COMPLETED").execute()
    print(f"Found {len(jobs.data)} COMPLETED jobs\n")

    docs_to_update = []

    for job in jobs.data:
        doc_id = job["document_id"]
        # Get document status
        doc = client.table("documents").select("id, status, filename").eq("id", doc_id).execute()
        if doc.data:
            d = doc.data[0]
            fname = (d["filename"] or "Unknown")[:50]
            status = d["status"]
            if status not in ("searchable", "completed"):
                docs_to_update.append(doc_id)
                print(f"  [UPDATE] {fname:50} -> {status} (should be searchable)")
            else:
                print(f"  [OK]     {fname:50} -> {status}")

    if docs_to_update:
        print(f"\n{len(docs_to_update)} documents need status update to 'searchable'")
        auto_yes = '-y' in sys.argv or '--yes' in sys.argv
        if auto_yes:
            for doc_id in docs_to_update:
                client.table("documents").update({"status": "searchable"}).eq("id", doc_id).execute()
                print(f"  Updated: {doc_id[:12]}...")
            print("\n[DONE]")
        else:
            print("Run with -y to auto-update")
    else:
        print("\nAll documents have correct status!")

if __name__ == "__main__":
    main()
