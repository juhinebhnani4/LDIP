"""Invalidate summary cache for all matters to pick up parties fix."""

import asyncio
import sys

sys.path.insert(0, ".")

from app.services.summary_service import get_summary_service
from app.services.supabase.client import get_supabase_client


async def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    service = get_summary_service()

    # Get all matters
    matters = client.table("matters").select("id, title").execute()
    print(f"Found {len(matters.data or [])} matters")

    for matter in matters.data or []:
        matter_id = matter["id"]
        matter_title = (matter.get("title") or "Unnamed")[:40]

        result = await service.invalidate_cache(matter_id)
        status = "invalidated" if result else "no cache"
        print(f"  [{status:12}] {matter_title}")

    print("\nCache invalidation complete!")
    print("Frontend will now fetch fresh summaries with updated parties.")


if __name__ == "__main__":
    asyncio.run(main())
