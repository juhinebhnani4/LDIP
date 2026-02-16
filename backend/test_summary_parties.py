"""Test summary API returns parties correctly."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.summary_service import get_summary_service
from app.services.supabase.client import get_supabase_client

async def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured")
        sys.exit(1)

    service = get_summary_service()

    # Get first matter
    matters = client.table("matters").select("id, title").limit(1).execute()
    if not matters.data:
        print("No matters found")
        sys.exit(1)

    matter_id = matters.data[0]["id"]
    matter_title = matters.data[0].get("title", "Unnamed")
    print(f"Testing matter: {matter_title}")
    print(f"Matter ID: {matter_id}")
    print("=" * 60)

    # Get summary with force_refresh to bypass any cache
    print("\nFetching summary (force_refresh=True)...")
    summary = await service.get_summary(matter_id, force_refresh=True)

    print(f"\nParties: {len(summary.parties)}")
    for party in summary.parties:
        print(f"  - [{party.role.value:10}] {party.entity_name}")
        print(f"      entity_id: {party.entity_id[:12]}...")
        print(f"      source: {party.source_document}, p.{party.source_page}")
        print(f"      verified: {party.is_verified}")

    print("\n" + "=" * 60)
    print(f"Summary generated at: {summary.generated_at}")

    # Show the full JSON that would be sent to frontend
    print("\n" + "=" * 60)
    print("JSON output (parties section):")
    import json
    parties_json = summary.model_dump(by_alias=True)["parties"]
    print(json.dumps(parties_json, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
