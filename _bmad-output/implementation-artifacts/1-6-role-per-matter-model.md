# Story 1.6: Implement Role-Per-Matter Model

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **matter owner**,
I want **to assign roles (Owner, Editor, Viewer) to attorneys on my matters**,
So that **I can control who can view, edit, or manage each matter**.

## Acceptance Criteria

1. **Given** I have created a new matter, **When** the matter is created, **Then** I am automatically assigned as the "Owner" role **And** a record is created in the `matter_attorneys` table with matter_id, user_id, role="owner", invited_by, invited_at

2. **Given** I am an Owner of a matter, **When** I invite another attorney by email with role "Editor", **Then** a record is created in `matter_attorneys` with role="editor" **And** the invited user can access the matter with edit permissions

3. **Given** I am an Owner of a matter, **When** I invite another attorney with role "Viewer", **Then** a record is created in `matter_attorneys` with role="viewer" **And** the invited user can only view the matter (read-only access)

4. **Given** I am an Editor on a matter, **When** I try to delete the matter or change sharing settings, **Then** the action is denied with a permission error **And** only Owners can delete or manage sharing

## Tasks / Subtasks

- [x] Task 1: Create matter_attorneys database table and migration (AC: #1)
  - [x] Create Supabase migration `20260105000002_create_matter_attorneys_table.sql`
  - [x] Define schema: `id`, `matter_id`, `user_id`, `role` (enum: owner/editor/viewer), `invited_by`, `invited_at`, `created_at`
  - [x] Add foreign key constraints to `matters(id)` and `auth.users(id)`
  - [x] Add unique constraint on `(matter_id, user_id)` - one role per user per matter
  - [x] Add check constraint on role enum values
  - [x] Create index on `matter_id` for fast lookups
  - [x] Create index on `user_id` for user's matters list

- [x] Task 2: Create RLS policies for matter_attorneys table (AC: #1, #2, #3)
  - [x] Enable RLS on `matter_attorneys` table
  - [x] Policy: Users can SELECT their own memberships
  - [x] Policy: Owners can INSERT new members to their matters
  - [x] Policy: Owners can UPDATE member roles on their matters
  - [x] Policy: Owners can DELETE members from their matters
  - [x] Policy: Users cannot modify their own owner role (prevent self-demotion)

- [x] Task 3: Create matters table if not exists (AC: #1)
  - [x] Created migration `20260105000001_create_matters_table.sql`
  - [x] Defined schema with: `id`, `title`, `description`, `status`, `created_at`, `updated_at`, `deleted_at`
  - [x] Add soft-delete support with `deleted_at` column
  - [x] Enable RLS on matters table

- [x] Task 4: Create RLS policies for matters table (AC: #1, #4)
  - [x] Policy: Users can SELECT matters where they have any role in `matter_attorneys`
  - [x] Policy: Authenticated users can INSERT new matters (creator becomes owner via trigger)
  - [x] Policy: Editors and Owners can UPDATE matter details
  - [x] Policy: Only Owners can soft-DELETE matters

- [x] Task 5: Create database trigger for auto-assigning owner on matter creation (AC: #1)
  - [x] Create function `auto_assign_matter_owner()`
  - [x] Trigger on INSERT to `matters` table
  - [x] Automatically insert owner record into `matter_attorneys`
  - [x] Use `auth.uid()` for the creating user

- [x] Task 6: Create Pydantic models for matter and role (AC: #1, #2, #3)
  - [x] Create `backend/app/models/matter.py` with:
    - [x] `MatterRole` enum (owner, editor, viewer)
    - [x] `MatterMember` model (user_id, role, invited_at, invited_by)
    - [x] `Matter` model (id, title, description, status, members, created_at)
    - [x] `MatterCreate` request model
    - [x] `MatterInvite` request model (email, role)
    - [x] `MatterResponse` response model

- [x] Task 7: Create matter service with role checks (AC: #1, #2, #3, #4)
  - [x] Create `backend/app/services/matter_service.py`
  - [x] `create_matter(user_id, data)` - creates matter, auto-assigns owner
  - [x] `get_user_matters(user_id)` - returns all matters user has access to
  - [x] `get_matter(matter_id, user_id)` - returns matter if user has access
  - [x] `get_user_role(matter_id, user_id)` - returns user's role on matter
  - [x] `invite_member(matter_id, inviter_id, email, role)` - owner-only invite
  - [x] `update_member_role(matter_id, user_id, new_role)` - owner-only
  - [x] `remove_member(matter_id, member_user_id)` - owner-only, can't remove self

- [x] Task 8: Create matter API routes (AC: #1, #2, #3)
  - [x] Create `backend/app/api/routes/matters.py`
  - [x] `POST /api/matters` - create new matter
  - [x] `GET /api/matters` - list user's matters
  - [x] `GET /api/matters/{matter_id}` - get matter details with role
  - [x] `PATCH /api/matters/{matter_id}` - update matter (editor+ only)
  - [x] `DELETE /api/matters/{matter_id}` - soft delete (owner only)
  - [x] `POST /api/matters/{matter_id}/members` - invite member (owner only)
  - [x] `GET /api/matters/{matter_id}/members` - list members
  - [x] `PATCH /api/matters/{matter_id}/members/{user_id}` - update role (owner only)
  - [x] `DELETE /api/matters/{matter_id}/members/{user_id}` - remove member (owner only)

- [x] Task 9: Create require_matter_role dependency (AC: #4)
  - [x] Update `backend/app/api/deps.py`
  - [x] Create `MatterMembership` class for dependency return
  - [x] Create `require_matter_role(*allowed_roles)` factory
  - [x] Return 403 Forbidden if user lacks required role
  - [x] Use in route handlers for role-based access

- [x] Task 10: Create TypeScript types for matters (AC: #1, #2, #3)
  - [x] Create `frontend/src/types/matter.ts`
  - [x] `MatterRole` type (owner | editor | viewer)
  - [x] `MatterMember` interface
  - [x] `Matter` interface with members array
  - [x] `MatterCreateRequest` interface
  - [x] `MatterInviteRequest` interface

- [x] Task 11: Create matter API client functions (AC: #1, #2, #3)
  - [x] Create `frontend/src/lib/api/matters.ts`
  - [x] `createMatter(data)` - POST /api/matters
  - [x] `getMatters()` - GET /api/matters
  - [x] `getMatter(matterId)` - GET /api/matters/{id}
  - [x] `updateMatter(matterId, data)` - PATCH /api/matters/{id}
  - [x] `deleteMatter(matterId)` - DELETE /api/matters/{id}
  - [x] `inviteMember(matterId, email, role)` - POST /api/matters/{id}/members
  - [x] `getMembers(matterId)` - GET /api/matters/{id}/members
  - [x] `updateMemberRole(matterId, userId, role)` - PATCH
  - [x] `removeMember(matterId, userId)` - DELETE

- [x] Task 12: Write backend tests for matter service (AC: #1, #2, #3, #4)
  - [x] Create `backend/tests/services/test_matter_service.py`
  - [x] Test create_matter auto-assigns owner
  - [x] Test get_user_matters returns only accessible matters
  - [x] Test invite_member fails for non-owner
  - [x] Test owner cannot remove self
  - [x] Test viewer cannot update matter
  - [x] Test editor can update matter
  - [x] Mock Supabase client for unit tests

- [x] Task 13: Write backend API tests (AC: #1, #2, #3, #4)
  - [x] Create `backend/tests/api/test_matters.py`
  - [x] Test create matter returns 201 with owner role
  - [x] Test list matters returns only user's matters
  - [x] Test 403 when non-owner tries to invite
  - [x] Test 403 when viewer tries to update
  - [x] Test 403 when editor tries to delete
  - [x] Test 404 for non-existent matter

- [x] Task 14: Write RLS integration tests (AC: #4)
  - [x] Create `backend/tests/security/test_matter_isolation.py`
  - [x] Test user cannot SELECT matters without membership
  - [x] Test user cannot bypass RLS with direct SQL
  - [x] Test role hierarchy is enforced correctly
  - [x] Use separate test users to verify isolation

## Dev Notes

### Critical Architecture Constraints

**FROM ARCHITECTURE DOCUMENT - MUST FOLLOW EXACTLY:**

#### Role-Per-Matter Model (FR29)

| Role | Permissions |
|------|-------------|
| Owner | Full access, can delete matter, manage members |
| Editor | Upload documents, run engines, verify findings |
| Viewer | Read-only access to findings and documents |

**CRITICAL:** This is the foundation for the 4-layer matter isolation:
1. **Layer 1: PostgreSQL RLS** - Every table with `matter_id` MUST have RLS policy checking `matter_attorneys`
2. Layer 2: Vector namespace prefix (Story 1-7)
3. Layer 3: Redis key prefix (Story 1-7)
4. Layer 4: API middleware validates matter access (this story)

#### Database Schema (REQUIRED)

```sql
-- matter_attorneys table
CREATE TABLE matter_attorneys (
  id uuid primary key default gen_random_uuid(),
  matter_id uuid not null references matters(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'editor', 'viewer')),
  invited_by uuid references auth.users(id),
  invited_at timestamptz default now(),
  created_at timestamptz default now(),

  unique(matter_id, user_id)
);

-- Indexes for performance
create index idx_matter_attorneys_matter_id on matter_attorneys(matter_id);
create index idx_matter_attorneys_user_id on matter_attorneys(user_id);
```

#### RLS Policy Pattern (REQUIRED)

```sql
-- Enable RLS
alter table matter_attorneys enable row level security;

-- Users can see their own memberships
create policy "Users can view own memberships"
on matter_attorneys for select
using (user_id = auth.uid());

-- Owners can manage members
create policy "Owners can manage members"
on matter_attorneys for all
using (
  exists (
    select 1 from matter_attorneys ma
    where ma.matter_id = matter_attorneys.matter_id
    and ma.user_id = auth.uid()
    and ma.role = 'owner'
  )
);
```

#### Matters Table RLS (REQUIRED)

```sql
-- Users can only access matters where they have a role
create policy "Users access own matters only"
on matters for select
using (
  id in (
    select matter_id from matter_attorneys
    where user_id = auth.uid()
  )
);

-- Editors and Owners can update
create policy "Editors and Owners can update"
on matters for update
using (
  id in (
    select matter_id from matter_attorneys
    where user_id = auth.uid()
    and role in ('owner', 'editor')
  )
);

-- Only Owners can delete
create policy "Only Owners can delete"
on matters for delete
using (
  id in (
    select matter_id from matter_attorneys
    where user_id = auth.uid()
    and role = 'owner'
  )
);
```

#### Auto-Assign Owner Trigger (REQUIRED)

```sql
create or replace function auto_assign_matter_owner()
returns trigger as $$
begin
  insert into matter_attorneys (matter_id, user_id, role, invited_by)
  values (NEW.id, auth.uid(), 'owner', auth.uid());
  return NEW;
end;
$$ language plpgsql security definer;

create trigger on_matter_created
  after insert on matters
  for each row
  execute function auto_assign_matter_owner();
```

### Naming Conventions (CRITICAL - Must Follow)

| Element | Convention | Example |
|---------|------------|---------|
| Database tables | snake_case, plural | `matter_attorneys`, `matters` |
| Database columns | snake_case | `matter_id`, `invited_at` |
| Python models | PascalCase | `MatterMember`, `MatterRole` |
| Python functions | snake_case | `get_user_role`, `invite_member` |
| TypeScript types | PascalCase | `MatterMember`, `MatterRole` |
| API endpoints | plural nouns | `/api/matters`, `/api/matters/{id}/members` |

### API Response Format (MANDATORY)

```python
# Success - single matter
{
  "data": {
    "id": "uuid",
    "title": "Matter Title",
    "role": "owner",  # Current user's role
    "members": [...]
  }
}

# Success - list
{
  "data": [...],
  "meta": { "total": 10, "page": 1, "per_page": 20 }
}

# Error
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Only matter owners can invite members",
    "details": {}
  }
}
```

### Error Codes for Role Violations

| Error Code | HTTP Status | When |
|------------|-------------|------|
| `MATTER_NOT_FOUND` | 404 | Matter doesn't exist or user has no access |
| `INSUFFICIENT_PERMISSIONS` | 403 | User lacks required role |
| `CANNOT_REMOVE_OWNER` | 400 | Attempt to remove last owner |
| `MEMBER_ALREADY_EXISTS` | 409 | User already has role on matter |

### Previous Story Intelligence

**From Story 1-4 (JWT Token Handling):**
- `get_current_user` dependency in `app/api/deps.py` returns `AuthenticatedUser`
- Use `AuthenticatedUser.id` as `user_id` for matter operations
- JWT validation extracts user claims from Supabase token
- `require_role` factory pattern available - adapt for `require_matter_role`

**From Story 1-3 (Supabase Auth):**
- Supabase client at `backend/app/services/supabase/client.py`
- User profiles stored in `users` table (if created)
- RLS policies use `auth.uid()` for current user

**From Story 1-5 (Password Reset):**
- Form validation patterns established
- Error display in `rounded-md bg-destructive/10 p-3`
- Success messages in `rounded-md bg-green-50 p-3`

**Key Patterns Established:**
- Use Pydantic models for all request/response types
- All API responses wrapped in `{ data }` or `{ error }`
- FastAPI routes use `Depends()` for auth and validation
- TypeScript strict mode - no `any` types

### File Structure for Role-Per-Matter Feature

```
supabase/
├── migrations/
│   ├── 009_create_matters.sql          # If matters table doesn't exist
│   └── 010_create_matter_attorneys.sql # Role assignments

backend/
├── app/
│   ├── models/
│   │   └── matter.py                   # MatterRole, Matter, MatterMember
│   ├── services/
│   │   └── matter_service.py           # Business logic for matters
│   └── api/
│       ├── deps.py                     # Update: require_matter_role
│       └── routes/
│           └── matters.py              # Matter API endpoints
└── tests/
    ├── services/
    │   └── test_matter_service.py      # Service unit tests
    ├── api/
    │   └── test_matters.py             # API integration tests
    └── security/
        └── test_matter_isolation.py    # RLS security tests

frontend/
└── src/
    ├── types/
    │   └── matter.ts                   # TypeScript types
    └── lib/
        └── api/
            └── matters.ts              # API client functions
```

### Security Considerations (MANDATORY)

1. **RLS is the primary security layer** - API middleware is defense-in-depth
2. **Never trust client-provided role** - Always check `matter_attorneys` table
3. **Use `security definer`** for trigger functions - Runs with elevated privileges
4. **Test isolation thoroughly** - Cross-matter access tests are critical
5. **Audit member changes** - Consider adding `audit_log` entries for invite/remove

### Anti-Patterns to AVOID

```python
# WRONG: Trusting client-provided matter_id without role check
@router.get("/matters/{matter_id}")
async def get_matter(matter_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    return await db.get_matter(matter_id)  # No role check!

# CORRECT: Verify user has access via matter_attorneys
@router.get("/matters/{matter_id}")
async def get_matter(
    matter_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
):
    # RLS handles this, but explicit check for clarity
    membership = await matter_service.get_user_role(matter_id, user.id)
    if not membership:
        raise HTTPException(404, detail={"error": {"code": "MATTER_NOT_FOUND", ...}})
    return await matter_service.get_matter(matter_id)
```

```typescript
// WRONG: Assuming role from local state
if (userRole === 'owner') {
  showDeleteButton();  // Could be stale!
}

// CORRECT: Get role from API response
const { data: matter } = await getMatter(matterId);
if (matter.role === 'owner') {
  showDeleteButton();
}
```

### Testing Guidance

**RLS Security Tests (CRITICAL):**
```python
import pytest
from supabase import Client

@pytest.fixture
def user_a_client() -> Client:
    """Supabase client authenticated as User A"""
    # Use test user credentials
    pass

@pytest.fixture
def user_b_client() -> Client:
    """Supabase client authenticated as User B"""
    pass

async def test_user_cannot_access_others_matter(user_a_client, user_b_client):
    # User A creates a matter
    matter = await user_a_client.table('matters').insert({'title': 'Private'}).execute()

    # User B should NOT be able to see it
    result = await user_b_client.table('matters').select('*').eq('id', matter.data[0]['id']).execute()
    assert len(result.data) == 0  # RLS blocks access
```

**Service Tests:**
```python
@pytest.mark.asyncio
async def test_create_matter_assigns_owner(matter_service, mock_user):
    matter = await matter_service.create_matter(mock_user.id, {"title": "Test"})

    role = await matter_service.get_user_role(matter.id, mock_user.id)
    assert role == "owner"

@pytest.mark.asyncio
async def test_non_owner_cannot_invite(matter_service, owner_user, editor_user):
    matter = await matter_service.create_matter(owner_user.id, {"title": "Test"})
    await matter_service.invite_member(matter.id, owner_user.id, "editor@test.com", "editor")

    with pytest.raises(InsufficientPermissionsError):
        await matter_service.invite_member(matter.id, editor_user.id, "new@test.com", "viewer")
```

### Git Intelligence (Recent Patterns)

From recent commits:
- `a9ee66a feat(auth): implement password reset flow (Story 1-5)` - auth patterns
- `c7f23f3 feat(auth): implement JWT token handling` - deps.py patterns
- `5493c65 feat(auth): implement Supabase Auth integration` - RLS patterns

**Commit message format:** `feat(auth): implement role-per-matter model (Story 1-6)`

### Project Structure Notes

- Migrations go in `supabase/migrations/` with sequential numbering
- Backend services in `backend/app/services/`
- API routes in `backend/app/api/routes/`
- Follow existing patterns from `health.py` for route structure

### References

- [Source: _bmad-output/architecture.md#Authorization] - Role definitions
- [Source: _bmad-output/architecture.md#Matter-Isolation] - 4-layer security
- [Source: _bmad-output/architecture.md#Database-Naming] - Naming conventions
- [Source: _bmad-output/project-context.md#Matter-Isolation] - Critical rules
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-1.6] - Acceptance criteria
- [Supabase Docs: RLS](https://supabase.com/docs/guides/auth/row-level-security)
- [Supabase Docs: Database Functions](https://supabase.com/docs/guides/database/functions)

### IMPORTANT: Always Check These Files Before Implementation

- **Previous Story:** `_bmad-output/implementation-artifacts/1-5-password-reset-flow.md`
- **Architecture:** `_bmad-output/architecture.md`
- **Project Context:** `_bmad-output/project-context.md`
- **Existing Auth Deps:** `backend/app/api/deps.py`
- **Existing Security:** `backend/app/core/security.py`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Fixed async/await mismatch: MatterService methods were defined as `async def` but use synchronous Supabase client. Converted all service methods to synchronous (`def`), removed `await` calls from routes and dependencies.
- Fixed deprecation warning: Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` in `delete_matter` method.

### Completion Notes List

- All 64 backend tests pass (38 matter-specific: 14 service + 15 API + 9 security tests; plus 26 other backend tests)
- Database migrations created for matters and matter_attorneys tables with RLS policies
- Backend service layer implements complete CRUD with role-based access control
- API routes follow RESTful conventions with proper error handling
- TypeScript types and API client fully typed (strict mode compatible)
- Security tests verify matter isolation via RLS policies
- Fixed N+1 query issues via batch user info fetching

### File List

**Database Migrations:**
- `supabase/migrations/20260105000001_create_matters_table.sql` - Matters table with RLS
- `supabase/migrations/20260105000002_create_matter_attorneys_table.sql` - Role assignments with RLS and auto-owner trigger

**Backend Models:**
- `backend/app/models/matter.py` - Pydantic models for matters and roles

**Backend Services:**
- `backend/app/services/matter_service.py` - Business logic with role checks

**Backend API:**
- `backend/app/api/deps.py` - Updated with `require_matter_role` dependency
- `backend/app/api/routes/matters.py` - Matter CRUD and member management routes
- `backend/app/main.py` - Updated to include matters router

**Frontend Types:**
- `frontend/src/types/matter.ts` - TypeScript interfaces
- `frontend/src/types/index.ts` - Re-exports matter types

**Frontend API:**
- `frontend/src/lib/api/matters.ts` - API client functions

**Tests:**
- `backend/tests/services/test_matter_service.py` - Service unit tests (15 tests)
- `backend/tests/api/test_matters.py` - API integration tests (15 tests)
- `backend/tests/security/test_matter_isolation.py` - RLS security tests (9 tests)

