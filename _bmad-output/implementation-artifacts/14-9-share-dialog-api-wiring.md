# Story 14.9: Share Dialog API Wiring

Status: done

## Story

As a **matter owner**,
I want the **Share Dialog to connect to real backend APIs**,
so that I can **actually invite, view, and remove collaborators persistently**.

## Acceptance Criteria

1. **GET /api/matters/{matterId}/members Integration**
   - When dialog opens, fetch real collaborators from `GET /api/matters/{matterId}/members`
   - Display loading skeleton while fetching (already implemented)
   - Handle API errors gracefully with toast notification
   - Map backend `MatterMember` to frontend `Collaborator` interface

2. **POST /api/matters/{matterId}/members Integration**
   - When user clicks "Invite", call `POST /api/matters/{matterId}/members` with `{ email, role }`
   - Handle success: Add returned member to collaborator list, show success toast
   - Handle `MemberAlreadyExistsError`: Show "This email is already a collaborator" error
   - Handle `UserNotFoundError`: Show "User not found" error (user must have account)
   - Handle other errors: Show generic error toast

3. **DELETE /api/matters/{matterId}/members/{userId} Integration**
   - When owner clicks remove button, call `DELETE /api/matters/{matterId}/members/{userId}`
   - Handle success: Remove member from list, show success toast
   - Handle `CannotRemoveOwnerError`: Show error toast (should not happen due to UI guard)
   - Handle other errors: Show generic error toast

4. **Type Alignment**
   - Use existing `MatterMember` type from `@/types/matter`
   - Map backend `user_id` to frontend usage (backend uses `user_id`, frontend component uses `id`)
   - Ensure role types are compatible (`MatterRole` enum matches)

5. **Tests Updated**
   - Update existing tests in `ShareDialog.test.tsx` to mock API calls instead of simulating mock data
   - Add tests for API error states (member already exists, user not found)
   - Ensure all existing test behaviors still pass

## Tasks / Subtasks

- [x] Task 1: Wire GET /api/matters/{matterId}/members (AC: #1)
  - [x] 1.1: Import `getMembers` from `@/lib/api/matters`
  - [x] 1.2: Replace mock fetch in `fetchCollaborators` with `getMembers(matterId)`
  - [x] 1.3: Map `MatterMember[]` to `Collaborator[]` (handle field name differences)
  - [x] 1.4: Handle API errors with toast.error

- [x] Task 2: Wire POST /api/matters/{matterId}/members (AC: #2)
  - [x] 2.1: Import `inviteMember` from `@/lib/api/matters`
  - [x] 2.2: Replace mock invite in `handleInvite` with `inviteMember(matterId, email, role)`
  - [x] 2.3: Map returned `MatterMember` to `Collaborator` and add to list
  - [x] 2.4: Handle specific error codes for better UX

- [x] Task 3: Wire DELETE /api/matters/{matterId}/members/{userId} (AC: #3)
  - [x] 3.1: Import `removeMember` from `@/lib/api/matters`
  - [x] 3.2: Replace mock removal in `handleRemoveCollaborator` with `removeMember(matterId, collaboratorId)`
  - [x] 3.3: Handle error cases gracefully

- [x] Task 4: Update Tests (AC: #5)
  - [x] 4.1: Mock API functions in test setup
  - [x] 4.2: Update tests to expect API calls instead of mock delays
  - [x] 4.3: Add error state tests (member exists, user not found)
  - [x] 4.4: All 25 tests pass (7 new tests added)

- [x] Task 5: Determine Current User Ownership (AC: #1, #3)
  - [x] 5.1: Get current user via `useUser` hook
  - [x] 5.2: Compare user ID with collaborators to determine ownership
  - [x] 5.3: Only show remove buttons if current user is owner

## Dev Notes

### Critical Implementation Details

#### Field Mapping (Backend → Frontend)
The backend `MatterMember` model has snake_case fields that need mapping:

```typescript
// Backend MatterMember (snake_case)
{
  id: string,           // membership record ID
  user_id: string,      // user's UUID
  email: string | null,
  full_name: string | null,
  role: MatterRole,
  invited_by: string | null,
  invited_at: string | null
}

// Frontend Collaborator interface (camelCase)
interface Collaborator {
  id: string;        // USE user_id here for DELETE operations
  email: string;
  name: string;      // Map from full_name
  role: MatterRole;
  avatarUrl?: string;
}
```

**CRITICAL**: The `id` in the frontend `Collaborator` must be the `user_id` from backend, NOT the membership `id`, because the DELETE endpoint uses `/members/{user_id}`.

#### Mapping Function
```typescript
function mapMemberToCollaborator(member: MatterMember): Collaborator {
  return {
    id: member.userId,  // CRITICAL: Use userId, not membership id
    email: member.email ?? 'Unknown',
    name: member.fullName ?? member.email?.split('@')[0] ?? 'Unknown',
    role: member.role,
  };
}
```

#### API Client Already Exists
All API functions are already implemented in `frontend/src/lib/api/matters.ts`:
- `getMembers(matterId: string): Promise<MatterMember[]>`
- `inviteMember(matterId: string, email: string, role: MatterRole): Promise<MatterMember>`
- `removeMember(matterId: string, userId: string): Promise<void>`

#### Error Handling
Backend returns errors in this format:
```json
{
  "error": {
    "code": "MEMBER_ALREADY_EXISTS",
    "message": "User is already a member of this matter",
    "details": {}
  }
}
```

Common error codes:
- `MEMBER_ALREADY_EXISTS` - User already has access
- `USER_NOT_FOUND` - Email doesn't match any registered user
- `CANNOT_REMOVE_OWNER` - Attempted to remove owner
- `MATTER_NOT_FOUND` - Matter doesn't exist or user lacks access

### Project Structure Notes

Files to modify:
- `frontend/src/components/features/matter/ShareDialog.tsx` (main component)
- `frontend/src/components/features/matter/ShareDialog.test.tsx` (tests)

Files to reference (NO changes needed):
- `frontend/src/lib/api/matters.ts` - API client (already complete)
- `frontend/src/types/matter.ts` - Types (already aligned)
- `backend/app/api/routes/matters.py` - Backend routes (already complete)

### Testing Strategy

Mock the API functions, not the network:

```typescript
vi.mock('@/lib/api/matters', () => ({
  getMembers: vi.fn(),
  inviteMember: vi.fn(),
  removeMember: vi.fn(),
}));
```

Test cases to add:
1. API error on fetch collaborators → shows toast.error
2. Member already exists error → shows specific validation message
3. User not found error → shows "User not found" message
4. Network error on remove → shows error toast, doesn't remove from list

### References

- [Source: ShareDialog.tsx lines 127-128, 176-177, 219-220] - TODO comments marking API integration points
- [Source: matters.ts API client] - Existing API functions to use
- [Source: Story 10A.1] - Original implementation story for ShareDialog
- [Source: sprint-status.yaml line 235] - Story tracking entry
- [Source: backend/app/api/routes/matters.py lines 198-329] - Backend member endpoints

### Edge Cases to Handle

1. **Empty email/full_name from backend**: Some members may have null email/full_name if user profile is incomplete. Use fallbacks.

2. **Dialog re-open**: Currently fetches on first open. If user closes and reopens, should re-fetch to get latest state.

3. **Optimistic updates**: Current mock implementation uses optimistic updates. Real API should:
   - For invite: Add to list after API success (not optimistically)
   - For remove: Remove from list after API success (not optimistically)
   - This prevents UI inconsistency if API fails

4. **Current user ownership**: The `currentUserIsOwner` is hardcoded to `true`. Should be derived from the matter's role or passed as prop.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Fixed dialog mock in `vitest.config.ts` alias `src/__mocks__/components/ui/dialog.tsx` to support controlled dialog state with context

### Completion Notes List

1. All API integration complete - GET, POST, DELETE for matter members
2. Error handling implemented with specific error codes (MEMBER_ALREADY_EXISTS, USER_NOT_FOUND)
3. Tests updated: 25 tests pass (7 new API-focused tests added)
4. Current user ownership detection via `useUser` hook
5. Dialog mock fixed to properly support asChild pattern and controlled state

### File List

- `frontend/src/components/features/matter/ShareDialog.tsx` - Main component with real API integration
- `frontend/src/components/features/matter/ShareDialog.test.tsx` - Updated tests with API mocking
- `frontend/src/__mocks__/components/ui/dialog.tsx` - Fixed dialog mock for proper trigger support
