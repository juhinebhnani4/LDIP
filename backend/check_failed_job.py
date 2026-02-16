"""Check FAILED job's document."""
import sys
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

def main():
    client = get_supabase_client()

    # Get FAILED job
    failed_job = client.table("processing_jobs").select("document_id").eq("status", "FAILED").execute()
    if failed_job.data:
        doc_id = failed_job.data[0]["document_id"]
        doc = client.table("documents").select("filename, status").eq("id", doc_id).execute()
        if doc.data:
            print("FAILED job document:")
            print(f"  filename: {doc.data[0]['filename']}")
            print(f"  status: {doc.data[0]['status']}")

if __name__ == "__main__":
    main()
