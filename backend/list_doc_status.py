"""List all document statuses for a matter."""

import sys

sys.path.insert(0, ".")

from app.services.supabase.client import get_supabase_client


def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    matter_id = "91a4a4db-bc3d-40df-8dcc-49179ac49108"

    docs = (
        client.table("documents")
        .select("filename, status")
        .eq("matter_id", matter_id)
        .order("filename")
        .execute()
    )

    print("Documents and statuses:\n")
    for d in docs.data:
        fname = (d["filename"] or "Unknown")[:55]
        status = d["status"]
        print(f"  {fname:55} | {status}")


if __name__ == "__main__":
    main()
