# Tech-Spec: Epic 10 - Governance & Compliance (MVP)

**Created:** 2026-01-28
**Status:** Ready for Development
**Epic:** 10 - Governance & Compliance (Phase 9, Week 17-18)
**Gaps Addressed:** #51, #53, #54, #55, #56, #57

---

## Overview

### Problem Statement

LDIP lacks governance features required for enterprise compliance:

1. **No SLA visibility** - Clients can't see uptime or performance commitments
2. **No data retention automation** - Soft-deleted data accumulates indefinitely
3. **No algorithm transparency** - Regulatory bodies may require documentation
4. **No self-service restore** - Admins must manually fix accidental deletions
5. **No deletion notifications** - Matter owners unaware when members delete
6. **No backup visibility** - No documented recovery procedures

### Solution

Implement 6 governance features leveraging existing infrastructure:

| Category | Stories | Approach |
|----------|---------|----------|
| **Transparency** | 10.1, 10.3 | SLA dashboard + algorithm docs |
| **Data Lifecycle** | 10.2, 10.6 | Retention purge job + PITR config |
| **User Trust** | 10.4, 10.5 | Matter restore + deletion alerts |

### Scope

**In Scope (MVP):**
- FR9.1: SLA documentation and monitoring
- FR9.2: Data retention policy with auto-purge
- FR9.3: Algorithm documentation for transparency
- FR9.4: Self-service matter restore
- FR9.5: Deletion alert to owner
- FR9.7: Point-in-time backup configuration

**Deferred (per Party Mode consensus):**
- FR9.6: Conflict of interest detection (breaks matter isolation, needs architecture spike)
- FR9.8: Bias testing framework (no demographic data, no industry standards)

### Design Constraints

| Constraint | Approach |
|------------|----------|
| **Leverage existing infra** | Build on soft-delete, email, Celery beat |
| **Low effort** | 15 SP total across 6 stories |
| **No new dependencies** | Use Supabase, Resend, existing patterns |

---

## Context for Development

### Codebase Patterns

**Soft Delete Pattern (already exists):**
```python
# backend/app/services/matter_service.py line 424
async def delete_matter(self, matter_id: str, user_id: str) -> bool:
    # Sets deleted_at timestamp, doesn't hard delete
    await client.table("matters").update({
        "deleted_at": datetime.utcnow().isoformat()
    }).eq("id", matter_id).execute()
```

**Celery Beat Job Pattern:**
```python
# backend/app/workers/celery.py
beat_schedule = {
    "job-name": {
        "task": "app.workers.tasks.module.function",
        "schedule": crontab(hour=0, minute=0),  # Daily midnight
        "options": {"queue": "low"},
    }
}
```

**Email Service Pattern:**
```python
# backend/app/services/email_service.py
async def send_email(self, to: str, subject: str, html: str, text: str) -> bool:
    # Uses Resend API with retry logic
```

**Admin Route Pattern:**
```python
# backend/app/api/routes/admin/
@router.get("/admin/endpoint")
async def admin_endpoint(
    current_user: AuthenticatedUser = Depends(require_admin_access),
) -> dict:
    ...
```

### Files to Reference

| File | Purpose | Stories |
|------|---------|---------|
| `backend/app/services/matter_service.py` | Matter CRUD + soft delete | 10.4 |
| `backend/app/services/document_service.py` | Document soft delete + cascade | 10.2 |
| `backend/app/services/email_service.py` | Email infrastructure | 10.5 |
| `backend/app/workers/celery.py` | Beat schedule config | 10.2 |
| `backend/app/workers/tasks/maintenance_tasks.py` | Scheduled job patterns | 10.2 |
| `backend/app/api/routes/admin/` | Admin endpoints | 10.1, 10.4 |
| `frontend/src/app/(dashboard)/admin/page.tsx` | Admin dashboard | 10.1, 10.4 |

---

## Implementation Plan

### Story 10.1: SLA Documentation and Monitoring (FR9.1)

**Goal:** Define SLAs and provide uptime/performance visibility

**Task 10.1.1:** Create SLA documentation page
- File: `docs/sla.md` (new)
- Define: Uptime target (99.5%), response times, support SLAs
- Include: Measurement methodology, exclusions, remedies

```markdown
# LDIP Service Level Agreement

## Uptime Commitment
- **Target:** 99.5% monthly uptime
- **Measurement:** Automated health checks every 60 seconds
- **Exclusions:** Scheduled maintenance (announced 48h ahead)

## Response Time SLAs
| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Search | 200ms | 500ms | 1s |
| Document upload | 2s | 5s | 10s |
| Q&A response | 3s | 8s | 15s |

## Support SLAs
| Priority | Response Time | Resolution Time |
|----------|---------------|-----------------|
| Critical | 1 hour | 4 hours |
| High | 4 hours | 24 hours |
| Normal | 24 hours | 72 hours |
```

**Task 10.1.2:** Create SLA monitoring widget
- File: `frontend/src/components/features/admin/SLAMonitoringWidget.tsx` (new)
- Display: Current month uptime %, incident count, response time P95

**Task 10.1.3:** Add health check endpoint for uptime monitoring
- File: `backend/app/api/routes/health.py`
- Endpoint: `GET /health/detailed`
- Returns: DB status, Redis status, Celery status, response time

**Task 10.1.4:** Configure external uptime monitoring
- Use: Supabase's built-in monitoring or external service (UptimeRobot, etc.)
- Alert: Email to admin when downtime detected

**Task 10.1.5:** Add SLA status to admin dashboard
- File: `frontend/src/app/(dashboard)/admin/page.tsx`
- Add: SLAMonitoringWidget to dashboard grid

**Acceptance Criteria:**
- [ ] Given an admin views the dashboard
- [ ] When they check the SLA widget
- [ ] Then they see current month uptime percentage
- [ ] And they see response time metrics (P50, P95)
- [ ] And they see any active incidents

---

### Story 10.2: Data Retention Policy with Auto-Purge (FR9.2)

**Goal:** Automatically purge soft-deleted data after retention period

**Task 10.2.1:** Add retention configuration
- File: `backend/app/core/config.py`
- Add: `data_retention_days: int = 30`
- Add: `data_retention_purge_enabled: bool = True`

**Task 10.2.2:** Create data retention purge task
- File: `backend/app/workers/tasks/data_retention_tasks.py` (new)

```python
from celery import shared_task
from datetime import datetime, timedelta

@celery_app.task(
    name="app.workers.tasks.data_retention_tasks.purge_soft_deleted_data",
    bind=True,
    max_retries=1,
)
def purge_soft_deleted_data(self) -> dict:
    """Permanently delete soft-deleted records older than retention period."""
    if not settings.data_retention_purge_enabled:
        return {"status": "disabled"}

    cutoff = datetime.utcnow() - timedelta(days=settings.data_retention_days)

    # Purge matters (cascades to documents)
    matters_purged = await purge_expired_matters(cutoff)

    # Purge orphaned documents
    documents_purged = await purge_expired_documents(cutoff)

    # Purge storage files
    storage_purged = await purge_expired_storage(cutoff)

    logger.info("data_retention_purge_complete",
                matters=matters_purged,
                documents=documents_purged,
                storage_files=storage_purged)

    return {
        "status": "complete",
        "matters_purged": matters_purged,
        "documents_purged": documents_purged,
        "storage_purged": storage_purged,
    }
```

**Task 10.2.3:** Add purge job to Celery beat schedule
- File: `backend/app/workers/celery.py`

```python
"purge-soft-deleted-data": {
    "task": "app.workers.tasks.data_retention_tasks.purge_soft_deleted_data",
    "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    "options": {"queue": "low"},
}
```

**Task 10.2.4:** Add cascade purge logic
- File: `backend/app/services/data_retention_service.py` (new)
- Purge order: Documents → Chunks → Embeddings → Citations → Storage files → Matters

**Task 10.2.5:** Add retention status to admin dashboard
- File: `frontend/src/components/features/admin/DataRetentionWidget.tsx` (new)
- Display: Items pending purge, last purge run, next scheduled

**Acceptance Criteria:**
- [ ] Given a matter was soft-deleted 31 days ago
- [ ] When the nightly purge job runs at 3 AM
- [ ] Then the matter and all related data are permanently deleted
- [ ] And storage files are removed from Supabase
- [ ] And purge metrics are logged

---

### Story 10.3: Algorithm Documentation (FR9.3)

**Goal:** Document each engine's logic for regulatory transparency

**Task 10.3.1:** Create algorithm documentation
- File: `docs/algorithms/index.md` (new)
- Structure: Overview + per-engine documentation

**Task 10.3.2:** Document Citation Engine
- File: `docs/algorithms/citation-engine.md` (new)

```markdown
# Citation Extraction Engine

## Purpose
Extracts legal citations (Acts, Sections) from uploaded documents.

## Algorithm Overview
1. **Regex Extraction** (Primary)
   - Pattern matching for "Section X of Y Act"
   - Confidence: 75% (high precision)

2. **LLM Extraction** (Secondary)
   - Model: Gemini 3 Flash
   - Confidence: Variable (0-100%)
   - Cost: ~$0.001 per document

## Deduplication
- Combines results from both methods
- Removes exact duplicates
- Preserves highest confidence match

## Verification
- Cross-references India Code database
- Status: VERIFIED, PENDING, MISMATCH

## Limitations
- Regional acts may not be in database
- Handwritten citations may have lower accuracy
```

**Task 10.3.3:** Document Contradiction Engine
- File: `docs/algorithms/contradiction-engine.md` (new)
- Include: Two-tier routing, evidence types, severity scoring

**Task 10.3.4:** Document Entity Resolution
- File: `docs/algorithms/entity-resolution.md` (new)
- Include: Similarity algorithms, confidence thresholds, transitive closure

**Task 10.3.5:** Document Timeline Engine
- File: `docs/algorithms/timeline-engine.md` (new)
- Include: Date extraction, event classification, entity linking

**Task 10.3.6:** Add documentation link to app footer
- File: `frontend/src/components/layout/Footer.tsx`
- Add: "How our AI works" link to `/docs/algorithms`

**Acceptance Criteria:**
- [ ] Given a regulator requests algorithm documentation
- [ ] When they access the documentation
- [ ] Then they see clear explanations of each engine
- [ ] And they understand inputs, outputs, and limitations
- [ ] And confidence scoring methodology is explained

---

### Story 10.4: Self-Service Matter Restore (FR9.4)

**Goal:** Allow admins to restore soft-deleted matters

**Task 10.4.1:** Add restore method to matter service
- File: `backend/app/services/matter_service.py`

```python
async def restore_matter(
    self,
    matter_id: str,
    user_id: str
) -> Matter | None:
    """Restore a soft-deleted matter."""
    # Verify admin access
    if not await self.is_admin(user_id):
        raise PermissionError("Admin access required")

    # Find soft-deleted matter
    result = await self.client.table("matters")\
        .select("*")\
        .eq("id", matter_id)\
        .not_.is_("deleted_at", "null")\
        .single()\
        .execute()

    if not result.data:
        return None

    # Restore matter
    await self.client.table("matters")\
        .update({"deleted_at": None})\
        .eq("id", matter_id)\
        .execute()

    # Log restoration
    logger.info("matter_restored", matter_id=matter_id, restored_by=user_id)

    return Matter(**result.data)
```

**Task 10.4.2:** Add restore API endpoint
- File: `backend/app/api/routes/admin/matters.py` (new)
- Endpoint: `POST /admin/matters/{matter_id}/restore`

**Task 10.4.3:** Add deleted matters list endpoint
- File: `backend/app/api/routes/admin/matters.py`
- Endpoint: `GET /admin/matters/deleted`
- Returns: List of soft-deleted matters with deletion date, deleter info

**Task 10.4.4:** Create admin matter management UI
- File: `frontend/src/components/features/admin/DeletedMattersWidget.tsx` (new)
- Display: Table of deleted matters
- Actions: Restore button, permanent delete button (with confirmation)

**Task 10.4.5:** Add to admin dashboard
- File: `frontend/src/app/(dashboard)/admin/page.tsx`
- Add: DeletedMattersWidget to dashboard

**Acceptance Criteria:**
- [ ] Given a matter was accidentally deleted 5 days ago
- [ ] When an admin views the deleted matters list
- [ ] Then they see the matter with deletion date and who deleted it
- [ ] And they can click "Restore" to recover it
- [ ] And the matter becomes accessible to original members

---

### Story 10.5: Deletion Alert to Owner (FR9.5)

**Goal:** Email matter owner when a member deletes content

**Task 10.5.1:** Create deletion alert email template
- File: `backend/app/services/email/templates/deletion_alert.py` (new)

```python
def render_deletion_alert_email(
    owner_name: str,
    matter_name: str,
    deleted_item: str,  # "document" or "matter"
    deleted_by: str,
    deleted_at: str,
    item_name: str,
) -> tuple[str, str, str]:
    subject = f"[LDIP] {deleted_item.title()} deleted from {matter_name}"

    html = f"""
    <h2>Deletion Alert</h2>
    <p>Hi {owner_name},</p>
    <p>A {deleted_item} has been deleted from your matter:</p>
    <ul>
        <li><strong>Matter:</strong> {matter_name}</li>
        <li><strong>Deleted item:</strong> {item_name}</li>
        <li><strong>Deleted by:</strong> {deleted_by}</li>
        <li><strong>Deleted at:</strong> {deleted_at}</li>
    </ul>
    <p>This item will be permanently deleted after 30 days.</p>
    <p>If this was a mistake, contact your administrator to restore it.</p>
    """

    text = f"..."  # Plain text version

    return subject, html, text
```

**Task 10.5.2:** Add deletion alert to email service
- File: `backend/app/services/email_service.py`

```python
async def send_deletion_alert(
    self,
    owner_email: str,
    owner_name: str,
    matter_name: str,
    deleted_item: str,
    deleted_by: str,
    item_name: str,
) -> bool:
    subject, html, text = render_deletion_alert_email(...)
    return await self.send_email(owner_email, subject, html, text)
```

**Task 10.5.3:** Create deletion alert Celery task
- File: `backend/app/workers/tasks/email_tasks.py`

```python
@celery_app.task(
    name="app.workers.tasks.email_tasks.send_deletion_alert",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def send_deletion_alert_task(
    self,
    owner_email: str,
    owner_name: str,
    matter_name: str,
    deleted_item: str,
    deleted_by: str,
    item_name: str,
) -> dict:
    ...
```

**Task 10.5.4:** Trigger alert on document/matter deletion
- File: `backend/app/services/document_service.py`
- Add: After soft_delete_document(), queue deletion alert task

- File: `backend/app/services/matter_service.py`
- Add: After delete_matter(), queue deletion alert task (if deleter != owner)

**Task 10.5.5:** Add user preference for deletion alerts
- File: `backend/app/models/user_preferences.py`
- Add: `email_notifications_deletion: bool = True`

**Acceptance Criteria:**
- [ ] Given User A owns a matter and User B is a member
- [ ] When User B deletes a document from the matter
- [ ] Then User A receives an email notification
- [ ] And the email includes: matter name, document name, who deleted, when
- [ ] And User A can opt out of these notifications in settings

---

### Story 10.6: Point-in-Time Recovery Configuration (FR9.7)

**Goal:** Enable and document PITR for disaster recovery

**Task 10.6.1:** Document Supabase PITR configuration
- File: `docs/operations/backup-recovery.md` (new)

```markdown
# Backup and Recovery Procedures

## Supabase Point-in-Time Recovery (PITR)

### Configuration
PITR is enabled via the Supabase dashboard:
1. Go to Project Settings → Database
2. Enable "Point in Time Recovery"
3. Select retention period (7 days standard, 30 days pro)

### Recovery Procedure
1. Go to Supabase Dashboard → Database → Backups
2. Select "Restore to point in time"
3. Choose timestamp to restore to
4. Confirm restoration (creates new project or restores existing)

### Backup Frequency
- Continuous WAL archiving (every transaction logged)
- Daily automated snapshots at 00:00 UTC
- Manual backups available via CLI

### Recovery Time Objectives
- RPO (Recovery Point Objective): < 5 minutes
- RTO (Recovery Time Objective): < 1 hour

## Storage Backup

Document files in Supabase Storage are backed up:
- Automatic replication across availability zones
- Manual export: `supabase storage download`

## Testing Recovery

Monthly recovery drills:
1. Create test matter with documents
2. Delete test matter
3. Perform PITR to 1 hour before deletion
4. Verify data restored correctly
```

**Task 10.6.2:** Add backup status to admin dashboard
- File: `frontend/src/components/features/admin/BackupStatusWidget.tsx` (new)
- Display: PITR enabled status, last backup time, retention period

**Task 10.6.3:** Create backup status API endpoint
- File: `backend/app/api/routes/admin/backup.py` (new)
- Endpoint: `GET /admin/backup/status`
- Returns: PITR enabled, last backup timestamp, retention days

**Task 10.6.4:** Add recovery runbook to operations docs
- File: `docs/operations/disaster-recovery-runbook.md` (new)
- Include: Step-by-step recovery procedures, contacts, escalation

**Acceptance Criteria:**
- [ ] Given a catastrophic data loss occurs
- [ ] When an admin follows the recovery runbook
- [ ] Then they can restore to any point within retention period
- [ ] And the process is documented step-by-step
- [ ] And recovery can be completed within 1 hour (RTO)

---

## Additional Context

### Dependencies

| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| No new dependencies | - | All features use existing stack | ✅ |

### Testing Strategy

**Unit Tests:**
- `test_matter_restore.py` - Verify restore functionality
- `test_data_retention_purge.py` - Verify purge job logic
- `test_deletion_alert.py` - Verify email trigger

**Integration Tests:**
- End-to-end matter restore flow
- Purge job with cascade deletion
- Email delivery for deletion alerts

**Manual Tests:**
- Monthly PITR recovery drill
- SLA monitoring accuracy check

### Database Migrations

```sql
-- No schema changes required
-- All stories use existing columns:
-- - matters.deleted_at
-- - documents.deleted_at
-- Soft delete pattern already implemented
```

### Configuration Changes

```python
# Add to backend/app/core/config.py

# Story 10.2: Data retention
data_retention_days: int = 30
data_retention_purge_enabled: bool = True
data_retention_purge_hour: int = 3  # 3 AM UTC

# Story 10.5: Deletion alerts
deletion_alerts_enabled: bool = True
```

### New Files Summary

| File | Purpose |
|------|---------|
| `docs/sla.md` | SLA documentation |
| `docs/algorithms/` | Algorithm documentation |
| `docs/operations/backup-recovery.md` | Recovery procedures |
| `backend/app/workers/tasks/data_retention_tasks.py` | Purge job |
| `backend/app/services/data_retention_service.py` | Purge logic |
| `backend/app/api/routes/admin/matters.py` | Restore endpoint |
| `backend/app/api/routes/admin/backup.py` | Backup status |
| `backend/app/services/email/templates/deletion_alert.py` | Email template |
| `frontend/src/components/features/admin/SLAMonitoringWidget.tsx` | SLA widget |
| `frontend/src/components/features/admin/DataRetentionWidget.tsx` | Retention widget |
| `frontend/src/components/features/admin/DeletedMattersWidget.tsx` | Restore UI |
| `frontend/src/components/features/admin/BackupStatusWidget.tsx` | Backup widget |

### Notes

- **No LLM costs** - All features are infrastructure/documentation
- **Leverage existing patterns** - Soft delete, email, Celery beat
- **Low risk** - Building on proven infrastructure
- **Regulatory ready** - Algorithm docs satisfy transparency requirements

### Egress Optimization Pattern (CRITICAL)

**All new database queries MUST follow the selective column pattern:**

```python
# BAD - causes excessive egress
.select("*")

# GOOD - use predefined column lists
MATTER_LIST_COLUMNS = "id, name, status, created_at, ..."
.select(MATTER_LIST_COLUMNS)
```

**Story 10.2 (Data retention purge):** When querying soft-deleted records for purging, use selective columns. Create `DELETED_MATTER_COLUMNS` constant excluding large metadata fields.

**Story 10.4 (Matter restore):** Consider adding a covering index for deleted matters queries:
```sql
CREATE INDEX idx_matters_deleted_covering ON public.matters(deleted_at)
INCLUDE (id, name, created_at, deleted_by)
WHERE deleted_at IS NOT NULL;
```

**Reference:** See migration `20260130000002_add_covering_indexes_egress_optimization.sql` for covering index patterns.

---

## Story Priority Order

| Priority | Story | Reason |
|----------|-------|--------|
| P0 | 10.2 | Data retention - compliance requirement |
| P0 | 10.4 | Matter restore - user trust |
| P1 | 10.5 | Deletion alerts - transparency |
| P1 | 10.1 | SLA monitoring - enterprise requirement |
| P2 | 10.6 | PITR config - disaster recovery |
| P2 | 10.3 | Algorithm docs - regulatory transparency |

---

## Deferred Stories (Future Epic)

### FR9.6: Conflict of Interest Detection
**Deferred Reason:** Breaks 4-layer matter isolation model
**Architecture Spike Required:**
- How to query cross-matter entity overlap without violating isolation?
- Options: Anonymized entity hashing, admin-only cross-matter view, opt-in sharing

### FR9.8: Bias Testing Framework
**Deferred Reason:** No demographic data, no industry standards
**Prerequisites:**
- Define "fairness" metrics for legal AI
- Collect demographic test data (with consent)
- Establish baselines for each engine

---

*Generated by BMAD Create Tech-Spec Workflow*
