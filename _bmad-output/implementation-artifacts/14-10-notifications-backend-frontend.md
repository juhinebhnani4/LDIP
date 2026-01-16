# Story 14.10: Notifications Backend & Frontend Wiring

Status: review

## Story

As an **attorney**,
I want **real-time notifications about important events in my matters**,
so that I can **stay informed about processing completions, verification needs, and issues requiring attention without constantly checking each matter**.

## Acceptance Criteria

1. **Notifications Table Created**
   - When the migration runs, a `notifications` table exists in Supabase
   - Table has columns: id (UUID), user_id, matter_id (nullable), type, title, message, priority, is_read, created_at
   - RLS policy ensures users can only see their own notifications
   - Index on (user_id, is_read, created_at DESC) for efficient badge count and listing

2. **GET /api/notifications Endpoint**
   - When authenticated user calls GET /api/notifications, they receive their notifications
   - Response includes list of notifications sorted by created_at DESC
   - Response includes unread count for badge display
   - Supports optional `limit` query param (default 20, max 50)
   - Supports optional `unread_only` query param (default false)
   - Response matches frontend `Notification` interface from `types/notification.ts`

3. **PATCH /api/notifications/{id}/read Endpoint**
   - When user marks a notification as read, is_read updates to true
   - Returns updated notification on success
   - Returns 404 if notification not found or belongs to another user (RLS enforced)

4. **POST /api/notifications/read-all Endpoint**
   - When user clicks "Mark all as read", all unread notifications update to is_read=true
   - Returns count of notifications marked as read

5. **Frontend Store Wired to Real API**
   - notificationStore.ts `fetchNotifications` calls GET /api/notifications
   - notificationStore.ts `markAsRead` calls PATCH /api/notifications/{id}/read
   - notificationStore.ts `markAllAsRead` calls POST /api/notifications/read-all
   - Remove mock data generation from store

6. **Notification Creation Integration**
   - Activity service's `create_activity` also creates a corresponding notification
   - Notifications created for: processing_complete, processing_failed, contradictions_found, verification_needed
   - NOT for: matter_opened (low priority, activity feed only)

7. **Tests Added**
   - Backend: pytest tests for all 3 endpoints with authentication and RLS verification
   - Frontend: Update notificationStore.test.ts to mock API calls instead of mock data

## Tasks / Subtasks

- [x] Task 1: Create notifications table migration (AC: #1)
  - [x] 1.1: Create Supabase migration file `supabase/migrations/20260117000001_create_notifications_table.sql`
  - [x] 1.2: Define table schema matching frontend Notification interface
  - [x] 1.3: Create index on (user_id, is_read, created_at DESC)
  - [x] 1.4: Add RLS policy for user isolation

- [x] Task 2: Create Notification Pydantic models (AC: #2)
  - [x] 2.1: Create `backend/app/models/notification.py`
  - [x] 2.2: Define NotificationTypeEnum matching frontend NotificationType
  - [x] 2.3: Define NotificationPriorityEnum matching frontend NotificationPriority
  - [x] 2.4: Define NotificationRecord with camelCase aliases for API response
  - [x] 2.5: Define NotificationListResponse with data and unreadCount

- [x] Task 3: Create Notification service (AC: #2, #3, #4)
  - [x] 3.1: Create `backend/app/services/notification_service.py`
  - [x] 3.2: Implement `get_notifications(user_id, limit, unread_only)` with Supabase query
  - [x] 3.3: Implement `get_unread_count(user_id)` for badge
  - [x] 3.4: Implement `mark_as_read(notification_id, user_id)` with ownership check
  - [x] 3.5: Implement `mark_all_as_read(user_id)` returning count
  - [x] 3.6: Implement `create_notification(user_id, matter_id, type, title, message, priority)`

- [x] Task 4: Create Notification API routes (AC: #2, #3, #4)
  - [x] 4.1: Create `backend/app/api/routes/notifications.py`
  - [x] 4.2: Implement `GET /api/notifications` with query params
  - [x] 4.3: Implement `PATCH /api/notifications/{id}/read`
  - [x] 4.4: Implement `POST /api/notifications/read-all`
  - [x] 4.5: Register router in `backend/app/main.py`

- [x] Task 5: Integrate notification creation with activity service (AC: #6)
  - [x] 5.1: Modify `ActivityService.create_activity` to also create notification
  - [x] 5.2: Map activity types to notification types (filter out matter_opened)
  - [x] 5.3: Generate user-friendly title/message from activity context

- [x] Task 6: Wire frontend to real API (AC: #5)
  - [x] 6.1: Create `frontend/src/lib/api/notifications.ts` with API functions
  - [x] 6.2: Update `notificationStore.ts` to use real API calls
  - [x] 6.3: Remove mock data generation code
  - [x] 6.4: Handle API errors gracefully with toast notifications

- [x] Task 7: Write tests (AC: #7)
  - [x] 7.1: Create `backend/tests/api/test_notifications.py`
  - [x] 7.2: Test GET returns user's notifications only (RLS)
  - [x] 7.3: Test PATCH mark as read with ownership check
  - [x] 7.4: Test POST mark all as read
  - [x] 7.5: Create `frontend/src/lib/api/notifications.test.ts` for API client tests

## Dev Notes

### Critical Implementation Details

#### Database Schema

```sql
-- supabase/migrations/YYYYMMDD_create_notifications.sql

CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  matter_id UUID REFERENCES matters(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('success', 'info', 'warning', 'error', 'in_progress')),
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for efficient queries (badge count, listing)
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read, created_at DESC);

-- RLS policy - users can only see/modify their own notifications
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own notifications"
  ON notifications FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can update own notifications"
  ON notifications FOR UPDATE
  USING (user_id = auth.uid());

-- Service role can insert (for background job notifications)
CREATE POLICY "Service can insert notifications"
  ON notifications FOR INSERT
  WITH CHECK (true);
```

#### Type Mapping (Backend → Frontend)

Backend Pydantic models MUST match frontend TypeScript types exactly:

**Frontend types/notification.ts:**
```typescript
export type NotificationType = 'success' | 'info' | 'warning' | 'error' | 'in_progress';
export type NotificationPriority = 'high' | 'medium' | 'low';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  matterId: string | null;
  matterTitle: string | null;
  isRead: boolean;
  createdAt: string;
  priority: NotificationPriority;
}
```

**Backend models/notification.py:**
```python
class NotificationTypeEnum(str, Enum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    IN_PROGRESS = "in_progress"

class NotificationPriorityEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class NotificationRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: NotificationTypeEnum
    title: str
    message: str
    matter_id: str | None = Field(None, alias="matterId")
    matter_title: str | None = Field(None, alias="matterTitle")
    is_read: bool = Field(..., alias="isRead")
    created_at: datetime = Field(..., alias="createdAt")
    priority: NotificationPriorityEnum
```

#### Activity → Notification Type Mapping

```python
ACTIVITY_TO_NOTIFICATION = {
    ActivityTypeEnum.PROCESSING_COMPLETE: (NotificationTypeEnum.SUCCESS, "Processing Complete"),
    ActivityTypeEnum.PROCESSING_STARTED: (NotificationTypeEnum.IN_PROGRESS, "Processing Started"),
    ActivityTypeEnum.PROCESSING_FAILED: (NotificationTypeEnum.ERROR, "Processing Failed"),
    ActivityTypeEnum.CONTRADICTIONS_FOUND: (NotificationTypeEnum.WARNING, "Contradictions Found"),
    ActivityTypeEnum.VERIFICATION_NEEDED: (NotificationTypeEnum.WARNING, "Verification Needed"),
    # matter_opened NOT mapped - too noisy for notifications
}

ACTIVITY_TO_PRIORITY = {
    ActivityTypeEnum.PROCESSING_FAILED: NotificationPriorityEnum.HIGH,
    ActivityTypeEnum.CONTRADICTIONS_FOUND: NotificationPriorityEnum.HIGH,
    ActivityTypeEnum.VERIFICATION_NEEDED: NotificationPriorityEnum.MEDIUM,
    ActivityTypeEnum.PROCESSING_COMPLETE: NotificationPriorityEnum.MEDIUM,
    ActivityTypeEnum.PROCESSING_STARTED: NotificationPriorityEnum.LOW,
}
```

#### API Response Format

Following project-context.md API patterns:

```typescript
// GET /api/notifications
{
  "data": [
    {
      "id": "uuid",
      "type": "success",
      "title": "Processing Complete",
      "message": "Document 'Contract.pdf' has been processed.",
      "matterId": "uuid",
      "matterTitle": "Smith vs. Jones",
      "isRead": false,
      "createdAt": "2026-01-16T10:00:00Z",
      "priority": "medium"
    }
  ],
  "unreadCount": 5
}

// Error response
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Notification not found",
    "details": {}
  }
}
```

### Frontend API Client

Create `frontend/src/lib/api/notifications.ts`:

```typescript
import { apiClient } from './client';
import type { Notification } from '@/types/notification';

interface NotificationListResponse {
  data: Notification[];
  unreadCount: number;
}

export async function getNotifications(
  limit = 20,
  unreadOnly = false
): Promise<NotificationListResponse> {
  const params = new URLSearchParams();
  params.set('limit', limit.toString());
  if (unreadOnly) params.set('unread_only', 'true');

  return apiClient.get<NotificationListResponse>(
    `/api/notifications?${params.toString()}`
  );
}

export async function markNotificationRead(
  notificationId: string
): Promise<{ data: Notification }> {
  return apiClient.patch<{ data: Notification }>(
    `/api/notifications/${notificationId}/read`
  );
}

export async function markAllNotificationsRead(): Promise<{ count: number }> {
  return apiClient.post<{ count: number }>('/api/notifications/read-all');
}
```

### Store Update Pattern

In `notificationStore.ts`, update fetchNotifications:

```typescript
fetchNotifications: async () => {
  set({ isLoading: true, error: null });
  try {
    const response = await getNotifications();
    set({
      notifications: response.data,
      unreadCount: response.unreadCount,
      isLoading: false,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to fetch notifications';
    set({ error: message, isLoading: false });
  }
},
```

### Project Structure Notes

**Files to Create:**
- `supabase/migrations/YYYYMMDD_create_notifications.sql` - Database migration
- `backend/app/models/notification.py` - Pydantic models
- `backend/app/services/notification_service.py` - Business logic
- `backend/app/api/routes/notifications.py` - API routes
- `backend/tests/api/test_notifications.py` - Backend tests
- `frontend/src/lib/api/notifications.ts` - API client

**Files to Modify:**
- `backend/app/api/routes/__init__.py` - Register notifications router
- `backend/app/services/activity_service.py` - Add notification creation
- `frontend/src/stores/notificationStore.ts` - Wire to real API
- `frontend/src/stores/notificationStore.test.ts` - Update tests

**Files to Reference (NO changes):**
- `frontend/src/types/notification.ts` - Type definitions (already correct)
- `frontend/src/components/features/dashboard/NotificationsDropdown.tsx` - UI (already works)
- `backend/app/models/activity.py` - Activity patterns to follow
- `backend/app/services/activity_service.py` - Service patterns to follow

### Testing Strategy

**Backend Tests (pytest):**
```python
@pytest.mark.asyncio
async def test_get_notifications_returns_only_user_notifications(
    client: AsyncClient, test_user: User, other_user: User
):
    """Verify RLS - users only see own notifications."""
    # Create notifications for both users
    # Query as test_user
    # Assert only test_user's notifications returned

@pytest.mark.asyncio
async def test_mark_as_read_requires_ownership(
    client: AsyncClient, test_user: User, other_user: User
):
    """Verify can't mark another user's notification as read."""
    # Create notification for other_user
    # Try to mark as read as test_user
    # Assert 404 (RLS prevents access)
```

**Frontend Tests (vitest):**
```typescript
vi.mock('@/lib/api/notifications', () => ({
  getNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

test('fetchNotifications calls API and updates store', async () => {
  const mockResponse = {
    data: [{ id: 'notif-1', type: 'success', ... }],
    unreadCount: 1,
  };
  vi.mocked(getNotifications).mockResolvedValue(mockResponse);

  await useNotificationStore.getState().fetchNotifications();

  expect(getNotifications).toHaveBeenCalled();
  expect(useNotificationStore.getState().notifications).toEqual(mockResponse.data);
  expect(useNotificationStore.getState().unreadCount).toBe(1);
});
```

### References

- [Source: types/notification.ts](frontend/src/types/notification.ts) - Frontend type definitions
- [Source: notificationStore.ts](frontend/src/stores/notificationStore.ts) - Frontend store to update
- [Source: activity_service.py](backend/app/services/activity_service.py) - Service pattern to follow
- [Source: models/activity.py](backend/app/models/activity.py) - Model pattern to follow
- [Source: routes/activity.py](backend/app/api/routes/activity.py) - Route pattern to follow
- [Source: project-context.md#api-response-format](docs/project-context.md) - API response standards
- [Source: Story 9.1](implementation-artifacts/9-1-dashboard-header.md) - Original notification UI implementation
- [Source: Story 14.5](implementation-artifacts/14-5-dashboard-real-apis.md) - Activity service patterns
- [Source: sprint-status.yaml line 236](implementation-artifacts/sprint-status.yaml) - Story tracking

### Edge Cases to Handle

1. **No notifications**: Return empty array with unreadCount: 0
2. **Matter deleted**: Notifications with deleted matter_id should show matterTitle as null
3. **Concurrent updates**: mark_all_as_read should handle concurrent markAsRead gracefully
4. **High volume**: Consider pagination for users with many notifications (future story)

### Performance Considerations

- Index on (user_id, is_read, created_at DESC) enables fast badge count query
- Limit default to 20 prevents over-fetching
- Consider Redis caching for badge count if it becomes a bottleneck (future optimization)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed successfully

### Completion Notes List

1. **Task 1**: Created notifications table migration with all columns, indexes, and RLS policies
2. **Task 2**: Created Pydantic models with camelCase aliases matching frontend types exactly
3. **Task 3**: Implemented notification service with all CRUD operations and batch operations
4. **Task 4**: Created FastAPI routes with proper authentication and error handling
5. **Task 5**: Integrated notification creation into activity service - maps activity types to notification types
6. **Task 6**: Updated frontend store to use real API with optimistic updates and error handling
7. **Task 7**: Added 11 backend tests and 12 frontend tests, all passing

### File List

**Files Created:**
- `supabase/migrations/20260117000001_create_notifications_table.sql` - Database migration
- `backend/app/models/notification.py` - Pydantic models (NotificationRecord, NotificationListResponse, etc.)
- `backend/app/services/notification_service.py` - Business logic service
- `backend/app/api/routes/notifications.py` - FastAPI routes
- `backend/tests/api/test_notifications.py` - Backend tests (11 tests)
- `frontend/src/lib/api/notifications.ts` - API client functions
- `frontend/src/lib/api/notifications.test.ts` - Frontend tests (12 tests)

**Files Modified:**
- `backend/app/main.py` - Registered notifications router
- `backend/app/services/activity_service.py` - Added notification creation integration
- `frontend/src/stores/notificationStore.ts` - Wired to real API

### Test Summary

- **Backend**: 11 tests passing
  - GET /api/notifications (5 tests)
  - PATCH /api/notifications/{id}/read (2 tests)
  - POST /api/notifications/read-all (2 tests)
  - Response format (2 tests)

- **Frontend**: 12 tests passing
  - getNotifications (6 tests)
  - markNotificationRead (3 tests)
  - markAllNotificationsRead (3 tests)
