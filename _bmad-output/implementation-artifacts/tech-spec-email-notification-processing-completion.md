# Tech-Spec: Email Notification on Processing Completion

**Created:** 2026-01-27
**Status:** Ready for Development
**Story:** gap-5-1-email-notification-processing-completion
**FR:** FR4.1 | **Gap:** #19

---

## Overview

### Problem Statement

Paralegals upload documents and must repeatedly check the dashboard to know when processing completes. This creates friction and wasted time - Gap #19 identified this as a key operational pain point.

### Solution

Integrate **Resend** email service to send notifications when document processing completes for an upload batch. Users receive a single email per upload session with status summary and deep link to their workspace.

### Scope

**In Scope:**
- Resend API integration with async Celery task
- Email on upload batch completion (success or partial failure)
- User opt-out preference (`email_notifications_enabled` column)
- Single email template for processing completion
- Deep link to matter workspace

**Out of Scope (Deferred):**
- Individual document completion emails
- Export ready notifications
- Verification reminder emails
- Email template customization per firm
- Digest/summary emails

---

## Context for Development

### Codebase Patterns

**Notification Pattern:**
```python
# Existing pattern in notification_service.py
await notification_service.create_notification_for_matter_members(
    matter_id=matter_id,
    type=NotificationTypeEnum.SUCCESS,
    title="Processing Complete",
    message="47 documents processed successfully",
    priority=NotificationPriorityEnum.MEDIUM,
)
```

**Celery Task Pattern:**
```python
# Existing pattern in document_tasks.py
@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: str, matter_id: str):
    # ... processing logic
    # Trigger point: after final document in batch completes
```

**Config Pattern:**
```python
# Existing pattern in config.py
class Settings(BaseSettings):
    resend_api_key: str = ""  # NEW
    email_notifications_enabled: bool = True  # NEW (global default)
```

### Files to Reference

| File | Purpose |
|------|---------|
| `backend/app/services/notification_service.py` | Pattern for async service + matter member lookup |
| `backend/app/workers/tasks/document_tasks.py` | Hook point for batch completion detection |
| `backend/app/workers/tasks/chunked_document_tasks.py` | Alternative hook for large document batches |
| `backend/app/core/config.py` | Add Resend config vars |
| `backend/app/models/auth.py` | User model for email preference |
| `backend/app/services/job_tracking_service.py` | Job status tracking for batch completion |

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Email Provider | Resend | Modern API, simple Python SDK, Railway-friendly, no SMTP complexity |
| Trigger Point | Batch completion | Avoids spam on multi-doc uploads; single notification per upload session |
| Async Pattern | Separate Celery task | Isolates email failures from document pipeline; retry logic |
| Opt-out Storage | `users.email_notifications_enabled` | Minimal schema change; boolean default true |
| Template Approach | Python string template | Simple MVP; can migrate to React Email later |

---

## Implementation Plan

### Tasks

- [ ] **Task 1: Add Resend Configuration**
  - Add `RESEND_API_KEY` to `backend/app/core/config.py`
  - Add `EMAIL_FROM_ADDRESS` config (default: `noreply@ldip.app`)
  - Add `EMAIL_NOTIFICATIONS_ENABLED` global feature flag
  - Update `.env.example` with new variables

- [ ] **Task 2: Create Email Service**
  - Create `backend/app/services/email_service.py`
  - Implement `EmailService` class with Resend SDK
  - Method: `send_processing_complete_email(user_email, matter_name, doc_count, success_count, failed_count, workspace_url)`
  - Include circuit breaker pattern (tenacity) for resilience
  - Add structured logging for email send attempts

- [ ] **Task 3: Add User Email Preference**
  - Create Supabase migration: `ALTER TABLE auth.users ADD COLUMN email_notifications_enabled BOOLEAN DEFAULT true`
  - Note: May need to use `profiles` table if `auth.users` is managed by Supabase Auth
  - Update user settings API to expose this preference

- [ ] **Task 4: Create Email Celery Task**
  - Create `backend/app/workers/tasks/email_tasks.py`
  - Implement `send_processing_complete_notification` task
  - Max retries: 3 with exponential backoff
  - Input: `matter_id`, `upload_batch_id`, `user_id`
  - Lookup: matter name, document stats, user email + preference
  - Skip if `email_notifications_enabled = false`

- [ ] **Task 5: Hook Batch Completion Trigger**
  - Modify `backend/app/workers/tasks/document_tasks.py`
  - Detect when all documents in upload batch are `completed` or `failed`
  - Trigger `send_processing_complete_notification.delay()`
  - Pass: `matter_id`, `batch_id` (or `job_id`), `uploading_user_id`

- [ ] **Task 6: Create Email Template**
  - Create `backend/app/services/email/templates/processing_complete.py`
  - HTML template with:
    - Subject: `Your documents for {matter_name} are ready`
    - Body: Document count, success/failure summary
    - CTA button: "View in LDIP" with deep link
    - Footer: Unsubscribe link to user settings
  - Plain text fallback version

- [ ] **Task 7: Add User Settings UI (Frontend)**
  - Add toggle to user profile/settings page
  - Label: "Email me when document processing completes"
  - Wire to PATCH `/api/users/me` endpoint

- [ ] **Task 8: Write Tests**
  - Unit tests for `EmailService` (mock Resend API)
  - Unit tests for `send_processing_complete_notification` task
  - Integration test: batch completion triggers email task
  - Test opt-out: user with preference=false receives no email
  - Test partial failure: email shows correct success/failed counts

### Acceptance Criteria

- [ ] **AC 1: Email Sent on Completion**
  - Given a user uploads 10 documents to a matter
  - When all documents finish processing (success or failure)
  - Then the uploading user receives ONE email with:
    - Matter name in subject
    - Document count and status summary
    - Link to workspace

- [ ] **AC 2: Opt-Out Respected**
  - Given a user has `email_notifications_enabled = false`
  - When their upload batch completes
  - Then NO email is sent
  - And in-app notification still created

- [ ] **AC 3: Partial Failure Handling**
  - Given an upload batch where 8/10 documents succeed and 2 fail
  - When processing completes
  - Then email shows "8 documents processed successfully, 2 need attention"
  - And link goes to workspace (not specific failed docs)

- [ ] **AC 4: Email Resilience**
  - Given Resend API is temporarily unavailable
  - When email send fails
  - Then task retries up to 3 times with exponential backoff
  - And failure is logged with correlation ID
  - And document processing is NOT affected

- [ ] **AC 5: User Preference Toggle**
  - Given user navigates to profile settings
  - When they toggle "Email notifications" off
  - Then preference is saved to database
  - And future uploads do not trigger emails

---

## Additional Context

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `resend` | `^2.0.0` | Python SDK for Resend email API |
| `tenacity` | (existing) | Retry logic with circuit breaker |

### Environment Variables

```bash
# Backend .env
RESEND_API_KEY=re_xxxxxxxxxxxx          # From Resend dashboard
EMAIL_FROM_ADDRESS=noreply@ldip.app     # Verified sender domain
EMAIL_NOTIFICATIONS_ENABLED=true        # Global feature flag
```

### Testing Strategy

1. **Unit Tests:**
   - Mock Resend API responses (success, rate limit, server error)
   - Test email template rendering with various inputs
   - Test opt-out logic in Celery task

2. **Integration Tests:**
   - Upload batch → completion → email task triggered
   - Verify task arguments (matter_id, user_id, etc.)

3. **Manual Tests:**
   - End-to-end: Upload docs, wait for completion, check inbox
   - Verify email renders correctly in Gmail, Outlook
   - Test unsubscribe link works

### Database Migration

```sql
-- Migration: add_email_notification_preference.sql
-- Note: If using Supabase Auth, may need profiles table instead

-- Option A: If profiles table exists
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN DEFAULT true;

-- Option B: Create user_preferences table
CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email_notifications_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS Policy
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own preferences"
ON public.user_preferences FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences"
ON public.user_preferences FOR UPDATE
USING (auth.uid() = user_id);
```

### Notes

- **Rate Limits:** Resend free tier = 100 emails/day, 3000/month. Production will need paid plan.
- **Domain Verification:** Must verify sending domain in Resend dashboard before production.
- **Deep Links:** Workspace URL format: `https://app.ldip.com/matters/{matter_id}/documents`
- **Future Enhancement:** Consider React Email templates for richer formatting and component reuse with frontend.

---

## File Structure (New Files)

```
backend/
├── app/
│   ├── services/
│   │   └── email_service.py          # NEW: Resend integration
│   │   └── email/
│   │       └── templates/
│   │           └── processing_complete.py  # NEW: Email template
│   └── workers/
│       └── tasks/
│           └── email_tasks.py        # NEW: Email Celery task
└── tests/
    └── services/
        └── test_email_service.py     # NEW: Unit tests
    └── workers/
        └── test_email_tasks.py       # NEW: Task tests

supabase/
└── migrations/
    └── 20260127_add_email_notification_preference.sql  # NEW
```

---

_Generated by create-tech-spec workflow_
