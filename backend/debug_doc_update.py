"""Debug document status update."""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client

def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    # Get a document that needs update
    doc_id = "1841c18c-60c3-42dc-87f8-58c34759e26d"  # 9. Affidavit...

    # Get current doc state
    doc = client.table("documents").select("*").eq("id", doc_id).execute()
    if not doc.data:
        print("Document not found")
        return

    d = doc.data[0]
    print("Current document state:")
    print(f"  id: {d['id']}")
    print(f"  status: {d.get('status')}")
    print(f"  page_count: {d.get('page_count')}")
    print(f"  processing_completed_at: {d.get('processing_completed_at')}")
    print(f"  ocr_quality: {d.get('ocr_quality')}")
    print(f"  validation_status: {d.get('validation_status')}")

    print("\nTrying to update status to 'searchable'...")
    try:
        result = client.table("documents").update({
            "status": "searchable",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", doc_id).execute()
        print("SUCCESS!")
        print(f"Updated: {result.data}")
    except Exception as e:
        print(f"FAILED: {e}")

        # Try with page_count set
        print("\nTrying with page_count...")
        try:
            # Get page count from chunks
            chunks = client.table("chunks").select("page_number").eq("document_id", doc_id).execute()
            max_page = max(c["page_number"] for c in chunks.data) if chunks.data else 1

            result = client.table("documents").update({
                "status": "searchable",
                "page_count": max_page,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", doc_id).execute()
            print("SUCCESS with page_count!")
        except Exception as e2:
            print(f"FAILED again: {e2}")

if __name__ == "__main__":
    main()
