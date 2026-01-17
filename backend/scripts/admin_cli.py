#!/usr/bin/env python3
"""LDIP Admin CLI for job management operations.

This CLI provides command-line access to admin operations that don't have
a frontend UI. It uses the same API endpoints as would be called from
a hypothetical admin dashboard.

Story 14.17: Admin Endpoints Documentation & Cleanup

Usage:
    python -m scripts.admin_cli --help
    python -m scripts.admin_cli list-failed
    python -m scripts.admin_cli retry-job JOB_ID
    python -m scripts.admin_cli recover-stuck

Environment Variables:
    LDIP_API_URL: API base URL (default: http://localhost:8000)
    LDIP_ADMIN_TOKEN: Bearer token for authentication (required)
"""

import os
import sys
from datetime import datetime

import click
import httpx

# Configuration
API_URL = os.getenv("LDIP_API_URL", "http://localhost:8000")
ADMIN_TOKEN = os.getenv("LDIP_ADMIN_TOKEN", "")


def get_headers() -> dict[str, str]:
    """Get request headers with authentication."""
    if not ADMIN_TOKEN:
        click.echo("Error: LDIP_ADMIN_TOKEN environment variable not set", err=True)
        click.echo("Export your admin JWT token: export LDIP_ADMIN_TOKEN='your-token'", err=True)
        sys.exit(1)
    return {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }


def format_datetime(dt_str: str | None) -> str:
    """Format ISO datetime string for display."""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return dt_str


@click.group()
@click.version_option(version="1.0.0", prog_name="ldip-admin")
def cli():
    """LDIP Admin CLI - Job management and recovery operations."""
    pass


@cli.command("list-failed")
@click.option("--matter-id", "-m", help="Filter by matter ID")
@click.option("--limit", "-l", default=50, help="Maximum jobs to list")
def list_failed(matter_id: str | None, limit: int):
    """List all failed jobs."""
    url = f"{API_URL}/api/jobs?status=failed&per_page={limit}"
    if matter_id:
        url += f"&matter_id={matter_id}"

    try:
        response = httpx.get(url, headers=get_headers(), timeout=30.0)
        response.raise_for_status()
        data = response.json()

        jobs = data.get("data", [])
        if not jobs:
            click.echo("No failed jobs found.")
            return

        click.echo(f"\n{'='*80}")
        click.echo(f"FAILED JOBS ({len(jobs)} total)")
        click.echo(f"{'='*80}\n")

        for job in jobs:
            click.echo(f"Job ID: {job.get('id')}")
            click.echo(f"  Document: {job.get('document_id')}")
            click.echo(f"  Matter: {job.get('matter_id')}")
            click.echo(f"  Step: {job.get('step')}")
            click.echo(f"  Error: {job.get('error_message', 'No error message')}")
            click.echo(f"  Failed at: {format_datetime(job.get('updated_at'))}")
            click.echo(f"  Retries: {job.get('retry_count', 0)}")
            click.echo()

    except httpx.HTTPStatusError as e:
        click.echo(f"API Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


@cli.command("list-stale")
def list_stale():
    """List stale jobs (stuck in PROCESSING)."""
    url = f"{API_URL}/api/jobs/recovery/stats"

    try:
        response = httpx.get(url, headers=get_headers(), timeout=30.0)
        response.raise_for_status()
        data = response.json()

        stale_jobs = data.get("stale_jobs", [])
        config = data.get("configuration", {})

        click.echo(f"\n{'='*80}")
        click.echo("STALE JOB STATISTICS")
        click.echo(f"{'='*80}\n")

        click.echo(f"Stale job count: {data.get('stale_jobs_count', 0)}")
        click.echo(f"Recovered last hour: {data.get('recovered_last_hour', 0)}")
        click.echo(f"\nConfiguration:")
        click.echo(f"  Stale timeout: {config.get('stale_timeout_minutes', 30)} minutes")
        click.echo(f"  Max retries: {config.get('max_recovery_retries', 3)}")
        click.echo(f"  Recovery enabled: {config.get('recovery_enabled', True)}")

        if stale_jobs:
            click.echo(f"\n{'='*80}")
            click.echo("STALE JOBS")
            click.echo(f"{'='*80}\n")

            for job in stale_jobs:
                click.echo(f"Job ID: {job.get('job_id')}")
                click.echo(f"  Document: {job.get('document_id')}")
                click.echo(f"  Matter: {job.get('matter_id')}")
                click.echo(f"  Stuck since: {format_datetime(job.get('stuck_since'))}")
                click.echo(f"  Recovery attempts: {job.get('recovery_attempts', 0)}")
                click.echo()
        else:
            click.echo("\nNo stale jobs found.")

    except httpx.HTTPStatusError as e:
        click.echo(f"API Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


@cli.command("retry-job")
@click.argument("job_id")
@click.option("--reset-count/--no-reset-count", default=True, help="Reset retry count")
def retry_job(job_id: str, reset_count: bool):
    """Retry a failed job by ID."""
    url = f"{API_URL}/api/jobs/{job_id}/retry"

    try:
        response = httpx.post(
            url,
            headers=get_headers(),
            json={"reset_retry_count": reset_count},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        click.echo(f"\n✓ Job {job_id} queued for retry")
        click.echo(f"  New status: {data.get('new_status', 'PENDING')}")
        click.echo(f"  Message: {data.get('message', 'Success')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"✗ Failed to retry job: {e.response.status_code}", err=True)
        try:
            error_data = e.response.json()
            click.echo(f"  Error: {error_data.get('error', {}).get('message', e.response.text)}", err=True)
        except Exception:
            click.echo(f"  Response: {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


@cli.command("recover-stuck")
@click.option("--dry-run", is_flag=True, help="Show what would be recovered without doing it")
def recover_stuck(dry_run: bool):
    """Recover all stale/stuck jobs."""
    if dry_run:
        # Just show stats
        url = f"{API_URL}/api/jobs/recovery/stats"
        try:
            response = httpx.get(url, headers=get_headers(), timeout=30.0)
            response.raise_for_status()
            data = response.json()

            stale_count = data.get("stale_jobs_count", 0)
            click.echo(f"\n[DRY RUN] Would recover {stale_count} stale job(s)")

            for job in data.get("stale_jobs", []):
                click.echo(f"  - {job.get('job_id')} (stuck since {format_datetime(job.get('stuck_since'))})")

            return
        except Exception as e:
            click.echo(f"Error checking stale jobs: {e}", err=True)
            sys.exit(1)

    url = f"{API_URL}/api/jobs/recovery/run"

    try:
        response = httpx.post(url, headers=get_headers(), timeout=60.0)
        response.raise_for_status()
        data = response.json()

        recovered = data.get("recovered", 0)
        failed = data.get("failed", 0)

        click.echo(f"\n{'='*80}")
        click.echo("RECOVERY RESULTS")
        click.echo(f"{'='*80}\n")

        click.echo(f"Recovered: {recovered}")
        click.echo(f"Failed: {failed}")

        for job in data.get("jobs", []):
            status = "✓" if job.get("success") else "✗"
            click.echo(f"\n{status} Job {job.get('job_id')}")
            click.echo(f"    Document: {job.get('document_id')}")
            click.echo(f"    Message: {job.get('message')}")
            if job.get("recovery_attempt"):
                click.echo(f"    Recovery attempt: {job.get('recovery_attempt')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"API Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


@cli.command("recover-job")
@click.argument("job_id")
def recover_job(job_id: str):
    """Recover a specific stale job by ID."""
    url = f"{API_URL}/api/jobs/recovery/{job_id}"

    try:
        response = httpx.post(url, headers=get_headers(), timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            click.echo(f"\n✓ Job {job_id} recovered successfully")
            click.echo(f"  Message: {data.get('message')}")
            click.echo(f"  Recovery attempt: {data.get('recovery_attempt')}")
        else:
            click.echo(f"\n✗ Job {job_id} recovery failed")
            click.echo(f"  Message: {data.get('message')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"✗ Failed to recover job: {e.response.status_code}", err=True)
        try:
            error_data = e.response.json()
            click.echo(f"  Error: {error_data.get('error', {}).get('message', e.response.text)}", err=True)
        except Exception:
            click.echo(f"  Response: {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


@cli.command("skip-job")
@click.argument("job_id")
@click.option("--reason", "-r", default="Skipped via admin CLI", help="Skip reason")
def skip_job(job_id: str, reason: str):
    """Skip a job (mark as permanently skipped)."""
    url = f"{API_URL}/api/jobs/{job_id}/skip"

    try:
        response = httpx.post(
            url,
            headers=get_headers(),
            json={"reason": reason},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        click.echo(f"\n✓ Job {job_id} marked as skipped")
        click.echo(f"  Reason: {reason}")

    except httpx.HTTPStatusError as e:
        click.echo(f"✗ Failed to skip job: {e.response.status_code}", err=True)
        try:
            error_data = e.response.json()
            click.echo(f"  Error: {error_data.get('error', {}).get('message', e.response.text)}", err=True)
        except Exception:
            click.echo(f"  Response: {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


@cli.command("cancel-job")
@click.argument("job_id")
def cancel_job(job_id: str):
    """Cancel a pending or processing job."""
    url = f"{API_URL}/api/jobs/{job_id}/cancel"

    try:
        response = httpx.post(url, headers=get_headers(), timeout=30.0)
        response.raise_for_status()
        data = response.json()

        click.echo(f"\n✓ Job {job_id} cancelled")
        click.echo(f"  New status: {data.get('new_status', 'CANCELLED')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"✗ Failed to cancel job: {e.response.status_code}", err=True)
        try:
            error_data = e.response.json()
            click.echo(f"  Error: {error_data.get('error', {}).get('message', e.response.text)}", err=True)
        except Exception:
            click.echo(f"  Response: {e.response.text}", err=True)
        sys.exit(1)
    except httpx.RequestError as e:
        click.echo(f"Request Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
