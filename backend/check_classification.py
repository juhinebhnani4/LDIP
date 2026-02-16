"""Check document classification status."""
import sys
sys.path.insert(0, '.')

from app.services.supabase.client import get_supabase_client

def main():
    client = get_supabase_client()

    matter_id = "91a4a4db-bc3d-40df-8dcc-49179ac49108"

    # Get all documents with their classification status
    docs = client.table("documents").select("id, filename, status, document_type").eq("matter_id", matter_id).order("filename").execute()

    print("=== Document Status and Classification ===\n")
    needs_class = 0
    for d in docs.data:
        fname = (d["filename"] or "Unknown")[:45]
        status = d["status"]
        doc_type = d.get("document_type") or "None"
        conf = 0
        if doc_type and doc_type != "None":
            class_status = "Classified"
        else:
            class_status = "Needs classification"
            needs_class += 1
        print(f"{fname:45} | {status:15} | {class_status}")

    print(f"\nTotal: {len(docs.data)} documents")
    print(f"Needs classification: {needs_class}")

if __name__ == "__main__":
    main()
