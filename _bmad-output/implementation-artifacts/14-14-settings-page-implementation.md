# Story 14.14: Settings Page Implementation

Status: done

## Story

As a **legal attorney using LDIP**,
I want **a Settings page where I can manage my account preferences and notification settings**,
so that **I can customize my LDIP experience and control how I receive updates**.

## Acceptance Criteria

1. **AC1: Settings page accessible from user dropdown**
   - Settings link in user profile dropdown navigates to /settings
   - Page renders with proper layout (header, sections)
   - Back navigation returns to previous page

2. **AC2: Profile section**
   - Display current user email (read-only)
   - Editable full name field
   - Avatar upload/change functionality
   - Save button with success/error feedback

3. **AC3: Notification preferences section**
   - Toggle for email notifications (document processing complete)
   - Toggle for email notifications (verification reminders)
   - Toggle for browser push notifications
   - Save preferences to backend

4. **AC4: Appearance section (optional)**
   - Theme toggle (light/dark/system)
   - Persist preference in localStorage
   - Apply theme immediately on change

5. **AC5: Account section**
   - Change password link/flow
   - Sign out of all devices button
   - Delete account (with confirmation modal)

6. **AC6: Backend API for user preferences**
   - GET /api/users/me/preferences - fetch current preferences
   - PATCH /api/users/me/preferences - update preferences
   - PATCH /api/users/me/profile - update profile (name, avatar)

## Tasks / Subtasks

- [x] **Task 1: Create backend user preferences endpoints** (AC: #6)
  - [x] 1.1 Create `backend/app/api/routes/users.py` if not exists
  - [x] 1.2 Add GET /api/users/me/preferences endpoint
  - [x] 1.3 Add PATCH /api/users/me/preferences endpoint
  - [x] 1.4 Add PATCH /api/users/me/profile endpoint
  - [x] 1.5 Create user_preferences table migration if needed
  - [x] 1.6 Write backend tests

- [x] **Task 2: Create useUserPreferences hook** (AC: #3, #6)
  - [x] 2.1 Create `frontend/src/hooks/useUserPreferences.ts`
  - [x] 2.2 Fetch preferences from API
  - [x] 2.3 Provide updatePreferences mutation
  - [x] 2.4 Handle optimistic updates

- [x] **Task 3: Create useUserProfile hook** (AC: #2, #6)
  - [x] 3.1 Create `frontend/src/hooks/useUserProfile.ts`
  - [x] 3.2 Fetch profile from existing /api/auth/me or create new endpoint
  - [x] 3.3 Provide updateProfile mutation
  - [x] 3.4 Handle avatar upload

- [x] **Task 4: Create SettingsPage component** (AC: #1)
  - [x] 4.1 Create `frontend/src/app/settings/page.tsx`
  - [x] 4.2 Add page layout with header and back button
  - [x] 4.3 Render settings sections
  - [x] 4.4 Add loading skeleton

- [x] **Task 5: Create ProfileSection component** (AC: #2)
  - [x] 5.1 Create `frontend/src/components/features/settings/ProfileSection.tsx`
  - [x] 5.2 Display email (read-only)
  - [x] 5.3 Editable name field with save
  - [x] 5.4 Avatar upload with preview
  - [x] 5.5 Form validation and error handling

- [x] **Task 6: Create NotificationSection component** (AC: #3)
  - [x] 6.1 Create `frontend/src/components/features/settings/NotificationSection.tsx`
  - [x] 6.2 Email notification toggles
  - [x] 6.3 Browser push notification toggle (with permission request)
  - [x] 6.4 Save on toggle change with debounce

- [x] **Task 7: Create AppearanceSection component** (AC: #4)
  - [x] 7.1 Create `frontend/src/components/features/settings/AppearanceSection.tsx`
  - [x] 7.2 Theme selector (light/dark/system)
  - [x] 7.3 Integrate with existing theme provider
  - [x] 7.4 Persist to localStorage

- [x] **Task 8: Create AccountSection component** (AC: #5)
  - [x] 8.1 Create `frontend/src/components/features/settings/AccountSection.tsx`
  - [x] 8.2 Change password button (opens modal or redirects)
  - [x] 8.3 Sign out all devices button with confirmation
  - [x] 8.4 Delete account with confirmation modal

- [x] **Task 9: Enable Settings route in navigation** (AC: #1)
  - [x] 9.1 Update user dropdown to link to /settings (currently disabled)
  - [x] 9.2 Verify route protection (authenticated only)

- [x] **Task 10: Write frontend tests** (AC: all)
  - [x] 10.1 Test SettingsPage renders sections
  - [x] 10.2 Test ProfileSection form submission
  - [x] 10.3 Test NotificationSection toggle saves
  - [x] 10.4 Test theme switching

## Dev Notes

### Current State

The Settings route exists but is disabled in the user dropdown. From the audit:
- Route: `/settings` - exists but no implementation
- User dropdown has Settings link commented out or disabled

### Database Schema

May need a new table for user preferences:

```sql
CREATE TABLE user_preferences (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email_notifications_processing BOOLEAN DEFAULT true,
  email_notifications_verification BOOLEAN DEFAULT true,
  browser_notifications BOOLEAN DEFAULT false,
  theme VARCHAR(10) DEFAULT 'system',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: Users can only access their own preferences
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own preferences"
ON user_preferences FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences"
ON user_preferences FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences"
ON user_preferences FOR INSERT
WITH CHECK (auth.uid() = user_id);
```

### API Response Format

```typescript
// GET /api/users/me/preferences
interface UserPreferences {
  emailNotificationsProcessing: boolean;
  emailNotificationsVerification: boolean;
  browserNotifications: boolean;
  theme: 'light' | 'dark' | 'system';
}

// PATCH /api/users/me/profile
interface UpdateProfileRequest {
  fullName?: string;
  avatarUrl?: string;
}
```

### Existing Patterns

- Use Card component for each section
- Use Switch component from shadcn/ui for toggles
- Use existing Avatar component for profile picture
- Follow form patterns from LoginForm

### File Structure

```
frontend/src/
├── app/settings/
│   └── page.tsx
├── components/features/settings/
│   ├── index.ts
│   ├── ProfileSection.tsx
│   ├── NotificationSection.tsx
│   ├── AppearanceSection.tsx
│   ├── AccountSection.tsx
│   └── __tests__/
└── hooks/
    ├── useUserPreferences.ts
    └── useUserProfile.ts

backend/
├── app/api/routes/
│   └── users.py (CREATE or UPDATE)
├── app/models/
│   └── user_preferences.py
└── supabase/migrations/
    └── 20260117_create_user_preferences.sql
```

### References

- [Source: frontend/src/components/features/dashboard/UserDropdown.tsx] - Settings link location
- [Source: frontend/src/app/settings/] - Check if route exists
- [Source: supabase/migrations/20260104000000_create_users_table.sql] - Existing users table
