# LDIP Admin Operations Runbook

This document describes administrative operations available for LDIP system maintenance.

## Prerequisites

Admin access is required for all operations. Users must either:
1. Have their email listed in the `ADMIN_EMAILS` environment variable
2. Have the `admin` role assigned in the system

## Authentication

All admin API calls require a valid Bearer token:

```bash
# Get token via Supabase Auth (example)
export TOKEN="your-jwt-token"
export API_URL="http://localhost:8000"
```

## Job Recovery Operations

### Get Recovery Statistics

View information about stale jobs and recovery configuration.

```bash
curl -X GET "$API_URL/api/jobs/recovery/stats" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "stale_jobs_count": 2,
  "stale_jobs": [
    {
      "job_id": "uuid-here",
      "document_id": "doc-uuid",
      "matter_id": "matter-uuid",
      "stuck_since": "2024-01-15T10:00:00Z",
      "recovery_attempts": 1
    }
  ],
  "configuration": {
    "stale_timeout_minutes": 30,
    "max_recovery_retries": 3,
    "recovery_enabled": true
  },
  "recovered_last_hour": 5
}
```

### Recover All Stale Jobs

Trigger recovery for all jobs stuck in PROCESSING state.

```bash
curl -X POST "$API_URL/api/jobs/recovery/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "recovered": 2,
  "failed": 0,
  "jobs": [
    {
      "job_id": "uuid",
      "document_id": "doc-uuid",
      "success": true,
      "message": "Job queued for reprocessing",
      "recovery_attempt": 1
    }
  ]
}
```

### Recover Single Job

Recover a specific stale job by ID.

```bash
curl -X POST "$API_URL/api/jobs/recovery/{job_id}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "job_id": "uuid",
  "document_id": "doc-uuid",
  "success": true,
  "message": "Job queued for reprocessing",
  "recovery_attempt": 1
}
```

### Retry a Failed Job

Retry a job that has failed processing.

```bash
curl -X POST "$API_URL/api/jobs/{job_id}/retry" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reset_retry_count": true}'
```

**Response:**
```json
{
  "job_id": "uuid",
  "message": "Job has been queued for retry",
  "new_status": "PENDING"
}
```

## Job Status Operations

### List Jobs

List jobs with optional filtering.

```bash
# List all jobs
curl -X GET "$API_URL/api/jobs" \
  -H "Authorization: Bearer $TOKEN"

# List failed jobs only
curl -X GET "$API_URL/api/jobs?status=failed" \
  -H "Authorization: Bearer $TOKEN"

# List jobs for a specific matter
curl -X GET "$API_URL/api/jobs?matter_id={matter_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### Get Job Details

Get detailed information about a specific job.

```bash
curl -X GET "$API_URL/api/jobs/{job_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### Cancel a Job

Cancel a pending or processing job.

```bash
curl -X POST "$API_URL/api/jobs/{job_id}/cancel" \
  -H "Authorization: Bearer $TOKEN"
```

### Skip a Job

Mark a job as skipped (will not be retried).

```bash
curl -X POST "$API_URL/api/jobs/{job_id}/skip" \
  -H "Authorization: Bearer $TOKEN"
```

## Rate Limiting

Admin endpoints are rate-limited to 10 requests per minute per user.
This is configured via `RATE_LIMIT_ADMIN` environment variable.

## Logging

All admin operations are logged with:
- User ID and email
- Operation type
- Timestamp
- Request path
- IP address

Logs are sent to Axiom (if configured) and local structured logs.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_EMAILS` | Comma-separated list of admin emails | (empty) |
| `RATE_LIMIT_ADMIN` | Admin rate limit per minute | 10 |
| `JOB_STALE_TIMEOUT_MINUTES` | Minutes before job is considered stale | 30 |
| `JOB_MAX_RECOVERY_RETRIES` | Max auto-recovery attempts | 3 |
| `JOB_RECOVERY_ENABLED` | Enable automatic job recovery | true |

## Troubleshooting

### Job Stuck in Processing

1. Check recovery stats: `GET /api/jobs/recovery/stats`
2. If job is listed as stale, run: `POST /api/jobs/recovery/{job_id}`
3. If recovery fails repeatedly, investigate logs for root cause
4. Consider skipping job if document is corrupt: `POST /api/jobs/{job_id}/skip`

### High Number of Failed Jobs

1. List failed jobs: `GET /api/jobs?status=failed`
2. Check job error messages for patterns
3. Fix underlying issue (e.g., LLM rate limits, storage issues)
4. Batch retry: Use recovery endpoint to retry all

### Recovery Disabled

If `JOB_RECOVERY_ENABLED=false`, manual recovery still works but automatic
periodic recovery is disabled. Use manual endpoints to recover individual jobs.

## Security Notes

- Admin endpoints do not bypass matter access control
- Jobs can only be managed if user has access to the associated matter
- All admin actions are audited
- Rate limiting prevents abuse
