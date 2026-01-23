#!/usr/bin/env python3
"""Monitor document processing performance and track latency metrics.

Live monitoring script to track:
- Document processing stages and latency
- Entity extraction performance
- Citation extraction costs
- Feature readiness broadcasts
"""

import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from app.services.supabase.client import get_supabase_client


def get_processing_stats():
    """Get current processing statistics."""
    client = get_supabase_client()

    # Document status counts
    docs = client.table("documents").select("status, created_at, updated_at").execute()
    status_counts = {}
    for d in docs.data:
        s = d["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "total_documents": len(docs.data),
        "status_counts": status_counts,
        "documents": docs.data,
    }


def get_job_stats():
    """Get processing job statistics."""
    client = get_supabase_client()

    # Jobs by status
    jobs = (
        client.table("processing_jobs")
        .select("status, current_stage, created_at, started_at, completed_at")
        .execute()
    )

    status_counts = {}
    stage_counts = {}
    latencies = []

    for job in jobs.data:
        s = job["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

        if job.get("current_stage"):
            stage = job["current_stage"]
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        # Calculate latency for completed jobs
        if job.get("started_at") and job.get("completed_at"):
            try:
                started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                completed = datetime.fromisoformat(
                    job["completed_at"].replace("Z", "+00:00")
                )
                latency = (completed - started).total_seconds()
                latencies.append(latency)
            except Exception:
                pass

    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    return {
        "total_jobs": len(jobs.data),
        "status_counts": status_counts,
        "stage_counts": stage_counts,
        "avg_latency_seconds": round(avg_latency, 2),
        "min_latency": round(min(latencies), 2) if latencies else 0,
        "max_latency": round(max(latencies), 2) if latencies else 0,
    }


def get_entity_stats():
    """Get entity extraction statistics."""
    client = get_supabase_client()

    entities = client.table("identity_nodes").select("id", count="exact").execute()
    mentions = client.table("entity_mentions").select("id", count="exact").execute()

    return {
        "identity_nodes": entities.count,
        "entity_mentions": mentions.count,
    }


def get_citation_stats():
    """Get citation extraction statistics."""
    client = get_supabase_client()

    citations = (
        client.table("citations")
        .select("id", count="exact")
        .execute()
    )
    acts = client.table("act_resolutions").select("id", count="exact").execute()

    return {
        "total_citations": citations.count,
        "total_acts": acts.count,
    }


def get_recent_activity(minutes: int = 5):
    """Get documents updated in the last N minutes."""
    client = get_supabase_client()

    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    recent = (
        client.table("documents")
        .select("id, filename, status, updated_at")
        .gte("updated_at", cutoff)
        .order("updated_at", desc=True)
        .limit(10)
        .execute()
    )

    return recent.data


def main():
    """Main monitoring loop."""
    print("=" * 60)
    print("LDIP Processing Monitor - Live Tracking")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Worker: gevent pool with 50 concurrency")
    print("-" * 60)

    # Get initial stats
    doc_stats = get_processing_stats()
    job_stats = get_job_stats()
    entity_stats = get_entity_stats()
    citation_stats = get_citation_stats()

    print("\n=== DOCUMENT STATUS ===")
    for status, count in sorted(doc_stats["status_counts"].items()):
        print(f"  {status}: {count}")
    print(f"  TOTAL: {doc_stats['total_documents']}")

    print("\n=== JOB STATISTICS ===")
    for status, count in sorted(job_stats["status_counts"].items()):
        print(f"  {status}: {count}")
    print(f"  Total jobs: {job_stats['total_jobs']}")
    print(f"  Avg latency: {job_stats['avg_latency_seconds']}s")
    print(f"  Min/Max: {job_stats['min_latency']}s / {job_stats['max_latency']}s")

    if job_stats["stage_counts"]:
        print("\n=== CURRENT STAGES ===")
        for stage, count in sorted(job_stats["stage_counts"].items()):
            print(f"  {stage}: {count}")

    print("\n=== ENTITY STATS ===")
    print(f"  Identity nodes: {entity_stats['identity_nodes']}")
    print(f"  Entity mentions: {entity_stats['entity_mentions']}")

    print("\n=== CITATION STATS ===")
    print(f"  Total citations: {citation_stats['total_citations']}")
    print(f"  Total acts referenced: {citation_stats['total_acts']}")

    print("\n=== RECENT ACTIVITY (last 5 min) ===")
    recent = get_recent_activity(5)
    if recent:
        for doc in recent:
            fname = (doc.get("filename") or "Unknown")[:40]
            status = doc.get("status")
            print(f"  {fname:40} | {status}")
    else:
        print("  No recent activity")

    print("\n" + "=" * 60)
    print("Monitoring complete!")


if __name__ == "__main__":
    main()
