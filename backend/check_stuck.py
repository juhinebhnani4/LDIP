"""Check stuck chunking jobs."""
import sys
sys.path.insert(0, '.')
from app.services.supabase.client import get_supabase_client

client = get_supabase_client()

# Get detailed info on the failing jobs
response = client.table("processing_jobs").select("*").eq("current_stage", "chunking").order("updated_at", desc=True).limit(5).execute()

for j in response.data:
    print("="*60)
    print(f"Job ID: {j['id'][:8]}...")
    print(f"Document ID: {j.get('document_id', 'N/A')[:8] if j.get('document_id') else 'N/A'}...")
    print(f"Status: {j['status']}")
    print(f"Stage: {j['current_stage']}")
    print(f"Progress: {j['progress_pct']}%")
    print(f"Error: {j.get('error_message', 'None')}")
    print(f"Error code: {j.get('error_code', 'None')}")
    print(f"Retry count: {j.get('retry_count', 0)}/{j.get('max_retries', 3)}")
    metadata = j.get('metadata', {})
    print(f"Metadata keys: {list(metadata.keys()) if metadata else 'None'}")
    if metadata:
        for k, v in metadata.items():
            val_str = str(v)[:100] if v else 'None'
            print(f"  {k}: {val_str}")
    print()
