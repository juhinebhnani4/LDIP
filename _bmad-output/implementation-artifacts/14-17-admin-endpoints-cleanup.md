# Story 14.17: Admin Endpoints Documentation & Cleanup

Status: ready-for-dev

## Story

As a **developer maintaining LDIP**,
I want **admin/recovery endpoints to be properly documented or removed**,
so that **the codebase is clean and maintainable without orphaned functionality**.

## Acceptance Criteria

1. **AC1: Audit admin endpoints**
   - List all admin/recovery endpoints currently in codebase
   - Identify which have frontend UI vs. are API-only
   - Document intended use cases

2. **AC2: Document necessary admin endpoints**
   - Add OpenAPI documentation to retained endpoints
   - Create admin operations runbook in docs/
   - Include curl examples for common operations

3. **AC3: Create admin CLI or script (alternative to UI)**
   - If no UI needed, create management commands
   - Or create simple admin script for job recovery
   - Document usage in README

4. **AC4: Remove truly orphaned endpoints**
   - Remove endpoints with no use case
   - Remove associated service code if unused
   - Update route registrations

5. **AC5: Add admin endpoint protection**
   - Ensure admin endpoints require elevated permissions
   - Add rate limiting to admin endpoints
   - Log all admin endpoint usage

## Tasks / Subtasks

- [ ] **Task 1: Audit current admin endpoints** (AC: #1)
  - [ ] 1.1 Search codebase for admin/recovery/internal endpoints
  - [ ] 1.2 List endpoints with their purpose and usage
  - [ ] 1.3 Check for any frontend references
  - [ ] 1.4 Document findings in this story

- [ ] **Task 2: Document retained endpoints** (AC: #2)
  - [ ] 2.1 Add detailed docstrings to retained admin endpoints
  - [ ] 2.2 Add OpenAPI tags and descriptions
  - [ ] 2.3 Create `docs/admin-operations.md` runbook
  - [ ] 2.4 Include examples for each operation

- [ ] **Task 3: Create admin management script** (AC: #3)
  - [ ] 3.1 Create `backend/scripts/admin_cli.py`
  - [ ] 3.2 Add commands: retry-job, list-failed-jobs, clear-stuck-jobs
  - [ ] 3.3 Add --help and usage documentation
  - [ ] 3.4 Test with real scenarios

- [ ] **Task 4: Remove orphaned endpoints** (AC: #4)
  - [ ] 4.1 Identify endpoints to remove based on audit
  - [ ] 4.2 Remove route definitions
  - [ ] 4.3 Remove unused service methods
  - [ ] 4.4 Update tests

- [ ] **Task 5: Add admin protection** (AC: #5)
  - [ ] 5.1 Create `require_admin_role` dependency
  - [ ] 5.2 Apply to all admin endpoints
  - [ ] 5.3 Add rate limiting (10 req/min)
  - [ ] 5.4 Add audit logging for admin actions

- [ ] **Task 6: Update documentation** (AC: #2, #3)
  - [ ] 6.1 Update API documentation
  - [ ] 6.2 Add admin section to main README
  - [ ] 6.3 Document environment variables needed

## Dev Notes

### Known Admin Endpoints (from Audit)

From the frontend-backend audit, these endpoints have no UI:

```
POST /api/jobs/{job_id}/retry - Retry a failed job
POST /api/jobs/stuck/recover - Recover stuck jobs
GET /api/jobs/admin/stats - Admin job statistics
DELETE /api/jobs/{job_id} - Delete a job record
```

### Decision Matrix

| Endpoint | Has UI? | Use Case | Decision |
|----------|---------|----------|----------|
| POST /jobs/{id}/retry | No | Recover failed processing | Keep + CLI |
| POST /jobs/stuck/recover | No | Fix stuck jobs | Keep + CLI |
| GET /jobs/admin/stats | No | Monitoring | Keep + docs |
| DELETE /jobs/{id} | No | Cleanup | Keep + CLI |

### Admin CLI Example

```python
# backend/scripts/admin_cli.py
#!/usr/bin/env python3
"""LDIP Admin CLI for job management operations."""

import click
import httpx
from app.core.config import settings

@click.group()
def cli():
    """LDIP Admin CLI"""
    pass

@cli.command()
@click.argument('job_id')
def retry_job(job_id: str):
    """Retry a failed job."""
    response = httpx.post(
        f"{settings.API_URL}/api/jobs/{job_id}/retry",
        headers={"Authorization": f"Bearer {get_admin_token()}"}
    )
    click.echo(f"Job {job_id} retry: {response.status_code}")

@cli.command()
def recover_stuck():
    """Recover all stuck jobs."""
    response = httpx.post(
        f"{settings.API_URL}/api/jobs/stuck/recover",
        headers={"Authorization": f"Bearer {get_admin_token()}"}
    )
    data = response.json()
    click.echo(f"Recovered {data['recovered_count']} jobs")

@cli.command()
def list_failed():
    """List all failed jobs."""
    response = httpx.get(
        f"{settings.API_URL}/api/jobs?status=failed",
        headers={"Authorization": f"Bearer {get_admin_token()}"}
    )
    for job in response.json()['data']:
        click.echo(f"{job['id']}: {job['error_message']}")

if __name__ == '__main__':
    cli()
```

### Admin Role Protection

```python
# backend/app/api/deps.py
from fastapi import HTTPException, status

async def require_admin_role(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require user to have admin role."""
    # Check if user is in admin list or has admin role
    admin_emails = settings.ADMIN_EMAILS.split(",") if settings.ADMIN_EMAILS else []

    if current_user.email not in admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ADMIN_REQUIRED", "message": "Admin access required"}}
        )
    return current_user
```

### File Structure

```
backend/
├── scripts/
│   └── admin_cli.py (CREATE)
├── docs/
│   └── admin-operations.md (CREATE)
├── app/api/
│   ├── deps.py (MODIFY - add require_admin_role)
│   └── routes/
│       └── jobs.py (MODIFY - add protection)
```

### References

- [Source: backend/app/api/routes/jobs.py] - Job management endpoints
- [Source: backend/app/services/job_tracking_service.py] - Job service
