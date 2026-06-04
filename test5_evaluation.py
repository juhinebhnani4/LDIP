"""Test 5: Evaluation Baselines & Regression."""
import requests
import json
import time
import sys

API = "https://jaanch-ai.up.railway.app"
MATTER_ID = "91a4a4db-bc3d-40df-8dcc-49179ac49108"
TOKEN = open("E:/Career coaching/100x/LDIP/.token_tmp").read().strip()
HEADERS = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}

def check_status(msg, resp):
    status = "OK" if resp.status_code < 400 else "FAIL"
    print(f"[{status}] {msg}: {resp.status_code}")
    return resp

# Step 1: Verify golden items exist
print("=" * 60)
print("TEST 5: EVALUATION BASELINES & REGRESSION")
print("=" * 60)

print("\n--- Step 1: Verify golden items ---")
r = requests.get(f"{API}/api/matters/{MATTER_ID}/evaluation/golden-dataset", headers=HEADERS)
items = r.json().get("data", [])
print(f"Golden items: {len(items)}")
if len(items) < 5:
    print("ERROR: Need at least 5 golden items")
    sys.exit(1)

# Step 2: Trigger batch evaluation
print("\n--- Step 2: Trigger batch evaluation ---")
r = requests.post(
    f"{API}/api/matters/{MATTER_ID}/evaluation/evaluate/batch",
    headers=HEADERS,
    json={"tags": []}
)
check_status("Batch eval trigger", r)
resp_data = r.json()
print(f"Response: {json.dumps(resp_data, indent=2)[:500]}")

if r.status_code >= 400:
    print(f"\nFull error: {r.text[:1000]}")
    # Try without tags
    print("\nRetrying without tags field...")
    r = requests.post(
        f"{API}/api/matters/{MATTER_ID}/evaluation/evaluate/batch",
        headers=HEADERS,
        json={}
    )
    check_status("Batch eval trigger (no tags)", r)
    resp_data = r.json()
    print(f"Response: {json.dumps(resp_data, indent=2)[:500]}")

task_id = resp_data.get("data", {}).get("task_id", resp_data.get("task_id"))
job_id = resp_data.get("data", {}).get("job_id", resp_data.get("job_id"))
run_id = resp_data.get("data", {}).get("run_id", resp_data.get("run_id"))
print(f"task_id={task_id}, job_id={job_id}, run_id={run_id}")

# Step 3: Poll for completion (if async)
if task_id or job_id:
    print("\n--- Step 3: Polling for completion ---")
    poll_id = task_id or job_id or run_id
    for i in range(30):
        time.sleep(10)
        # Try various status endpoints
        for endpoint in [
            f"{API}/api/matters/{MATTER_ID}/evaluation/status/{poll_id}",
            f"{API}/api/matters/{MATTER_ID}/evaluation/runs/{poll_id}",
            f"{API}/api/tasks/{poll_id}",
        ]:
            r = requests.get(endpoint, headers=HEADERS)
            if r.status_code == 200:
                data = r.json().get("data", r.json())
                status = data.get("status", "unknown")
                print(f"  [{i+1}/30] {endpoint.split('/')[-1]}: status={status}")
                if status in ("completed", "failed", "error"):
                    print(f"  Final: {json.dumps(data, indent=2)[:800]}")
                    break
        else:
            continue
        break
    else:
        print("  Timed out waiting for completion")

# Step 4: Check baseline
print("\n--- Step 4: Check baseline ---")
r = requests.get(f"{API}/api/matters/{MATTER_ID}/evaluation/baselines/active", headers=HEADERS)
check_status("Active baseline", r)
if r.status_code == 200:
    baseline = r.json().get("data", r.json())
    print(f"Baseline: {json.dumps(baseline, indent=2)[:600]}")
else:
    print(f"No active baseline: {r.text[:300]}")

# Step 5: Check trends
print("\n--- Step 5: Check trends ---")
r = requests.get(f"{API}/api/matters/{MATTER_ID}/evaluation/trends?days=30", headers=HEADERS)
check_status("Trends", r)
if r.status_code == 200:
    print(f"Trends: {json.dumps(r.json(), indent=2)[:400]}")

# Step 6: Idempotency test (C3 fix)
print("\n--- Step 6: Idempotency test (re-run batch eval) ---")
r = requests.post(
    f"{API}/api/matters/{MATTER_ID}/evaluation/evaluate/batch",
    headers=HEADERS,
    json={"tags": []}
)
check_status("Idempotent re-run", r)
if r.status_code < 400:
    print(f"Re-run response: {json.dumps(r.json(), indent=2)[:300]}")
else:
    print(f"Re-run error: {r.text[:300]}")

print("\n--- Test 5 Complete ---")
