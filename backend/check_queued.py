"""Check QUEUED job details."""
import sys
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

def main():
    client = get_supabase_client()

    queued = client.table("processing_jobs").select("*").eq("status", "QUEUED").execute()
    if queued.data:
        j = queued.data[0]
        print("QUEUED Job Details:")
        print(f"  job_id: {j['id']}")
        print(f"  document_id: {j['document_id']}")
        print(f"  current_stage: {j['current_stage']}")
        print(f"  progress_pct: {j['progress_pct']}%")
        print(f"  error_message: {j.get('error_message', 'None')}")
        print(f"  updated_at: {j['updated_at']}")

        # Get document info
        doc = client.table("documents").select("filename, file_size").eq("id", j["document_id"]).execute()
        if doc.data:
            d = doc.data[0]
            size_mb = d["file_size"] / (1024 * 1024)
            print(f"\n  Document: {d['filename']}")
            print(f"  Size: {size_mb:.1f} MB")

        # Check chunks
        chunks = client.table("chunks").select("id", count="exact").eq("document_id", j["document_id"]).execute()
        embedded = client.table("chunks").select("id", count="exact").eq("document_id", j["document_id"]).not_.is_("embedding", "null").execute()
        print(f"\n  Chunks: {chunks.count} total, {embedded.count} embedded")
    else:
        print("No QUEUED jobs found")

if __name__ == "__main__":
    main()
