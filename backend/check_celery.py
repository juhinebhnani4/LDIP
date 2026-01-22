"""Check Celery worker and queue status."""
import os
from dotenv import load_dotenv
from celery import Celery

load_dotenv()

app = Celery('ldip', broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'))

i = app.control.inspect()

print("=== Active Tasks ===")
active = i.active()
if active:
    for worker, tasks in active.items():
        print(f"{worker}: {len(tasks)} active tasks")
        for t in tasks:
            print(f"  - {t.get('name', 'unknown')}: {t.get('id', '?')[:8]}...")
else:
    print("No active tasks or workers not responding")

print("\n=== Reserved Tasks ===")
reserved = i.reserved()
if reserved:
    for worker, tasks in reserved.items():
        print(f"{worker}: {len(tasks)} reserved tasks")
else:
    print("No reserved tasks")

print("\n=== Registered Tasks ===")
registered = i.registered()
if registered:
    for worker, tasks in registered.items():
        print(f"{worker}: {len(tasks)} registered task types")
else:
    print("No registered tasks - workers may be down")

print("\n=== Worker Stats ===")
stats = i.stats()
if stats:
    for worker, stat in stats.items():
        print(f"{worker}:")
        print(f"  Pool: {stat.get('pool', {}).get('implementation', 'N/A')}")
        print(f"  Processes: {len(stat.get('pool', {}).get('processes', []))}")
else:
    print("No worker stats available - workers may not be running")
