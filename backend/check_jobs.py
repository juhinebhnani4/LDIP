"""Quick script to check job status."""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.services.supabase.client import get_supabase_client

client = get_supabase_client()
if not client:
    print("ERROR: Supabase client not configured")
    sys.exit(1)

# Fetch recent jobs
response = client.table("processing_jobs").select("*").order("updated_at", desc=True).limit(30).execute()
jobs = response.data

print('=== Recent Jobs Status ===')
for j in jobs:
    updated = j.get('updated_at', '')
    age = ''
    if updated:
        try:
            updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
            diff = datetime.now(timezone.utc) - updated_dt
            age = f'{int(diff.total_seconds() // 60)} min ago'
        except:
            pass
    err_msg = (j.get('error_message') or '')[:60]
    status = j.get('status', 'N/A')
    stage = j.get('current_stage') or 'N/A'
    pct = j.get('progress_pct', 0)
    print(f'{status:12} | {stage:20} | {pct:3}% | {age:12} | {err_msg}')

print()
print('=== Summary ===')
# Get counts by status
statuses = ['QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED']
for status in statuses:
    resp = client.table("processing_jobs").select("id", count="exact").eq("status", status).execute()
    count = resp.count if resp.count else 0
    print(f'{status}: {count}')
