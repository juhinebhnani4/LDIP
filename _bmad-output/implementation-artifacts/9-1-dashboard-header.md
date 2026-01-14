# Story 9.1: Implement Dashboard Header

Status: code-review

## Story

As an **attorney**,
I want **a consistent header with navigation and user controls**,
So that **I can access key features from anywhere in the app**.

## Acceptance Criteria

1. **Given** I am logged in
   **When** the dashboard loads
   **Then** the header shows: LDIP logo, global search bar, notifications badge (with count), help button, user profile dropdown

2. **Given** I click the notifications badge
   **When** the dropdown opens
   **Then** I see recent notifications (processing complete, verification needed, etc.)
   **And** I can mark notifications as read

3. **Given** I click the user profile dropdown
   **When** it opens
   **Then** I see my name and avatar
   **And** options: Settings, Help, Logout

4. **Given** I use the global search
   **When** I enter a query
   **Then** I can search across all my matters
   **And** results show matter names and matched content

## Tasks / Subtasks

- [ ] Task 1: Create DashboardHeader component (AC: #1)
  - [ ] 1.1: Create `frontend/src/components/features/dashboard/DashboardHeader.tsx` with proper structure
  - [ ] 1.2: Add LDIP logo (left side) - use existing logo or text-based
  - [ ] 1.3: Add global search bar in center using shadcn Input component
  - [ ] 1.4: Add notifications badge (right side) with count indicator using Badge component
  - [ ] 1.5: Add help button (right side)
  - [ ] 1.6: Add user profile dropdown (right side) using DropdownMenu component
  - [ ] 1.7: Style with Tailwind CSS following wireframe: `[Logo] [----Search----] [🔔] [❓] [User▼]`

- [ ] Task 2: Create NotificationsDropdown component (AC: #2)
  - [ ] 2.1: Create `frontend/src/components/features/dashboard/NotificationsDropdown.tsx`
  - [ ] 2.2: Implement dropdown panel using DropdownMenu
  - [ ] 2.3: Display notification list with types (processing complete, verification needed, etc.)
  - [ ] 2.4: Add "Mark as read" functionality for individual items
  - [ ] 2.5: Add "Mark all as read" action
  - [ ] 2.6: Style notifications based on type (success green, warning yellow, etc.)

- [ ] Task 3: Create UserProfileDropdown component (AC: #3)
  - [ ] 3.1: Create `frontend/src/components/features/dashboard/UserProfileDropdown.tsx`
  - [ ] 3.2: Display user name/email and avatar initials
  - [ ] 3.3: Add menu items: Settings, Help, Logout (use existing LogoutButton action)
  - [ ] 3.4: Implement navigation to settings page (placeholder route for now)
  - [ ] 3.5: Connect to Supabase auth context for user info

- [ ] Task 4: Create GlobalSearch component (AC: #4)
  - [ ] 4.1: Create `frontend/src/components/features/dashboard/GlobalSearch.tsx`
  - [ ] 4.2: Implement search input with search icon using Input component
  - [ ] 4.3: Add placeholder text "Search all matters..."
  - [ ] 4.4: Create search results dropdown/popover
  - [ ] 4.5: Connect to backend search API (or mock if not available)
  - [ ] 4.6: Display results grouped by matter with matched content preview

- [ ] Task 5: Create notifications store and types (AC: #2)
  - [ ] 5.1: Create `frontend/src/types/notification.ts` with Notification types
  - [ ] 5.2: Create `frontend/src/stores/notificationStore.ts` using Zustand selector pattern
  - [ ] 5.3: Implement actions: fetchNotifications, markAsRead, markAllAsRead
  - [ ] 5.4: Add unread count selector

- [ ] Task 6: Update dashboard layout to use header (AC: #1)
  - [ ] 6.1: Update `frontend/src/app/(dashboard)/layout.tsx` to include DashboardHeader
  - [ ] 6.2: Update `frontend/src/app/(dashboard)/page.tsx` to remove inline header
  - [ ] 6.3: Create feature index file `frontend/src/components/features/dashboard/index.ts`

- [ ] Task 7: Write tests (All ACs)
  - [ ] 7.1: Create `DashboardHeader.test.tsx` - renders all components
  - [ ] 7.2: Create `NotificationsDropdown.test.tsx` - dropdown opens, mark as read works
  - [ ] 7.3: Create `UserProfileDropdown.test.tsx` - user info displayed, logout works
  - [ ] 7.4: Create `GlobalSearch.test.tsx` - search input, results display
  - [ ] 7.5: Create `notificationStore.test.ts` - store actions work correctly

## Dev Notes

### Critical Architecture Patterns

**UI Component Requirements:**
- Use existing shadcn/ui components: `DropdownMenu`, `Input`, `Badge`, `Button`
- Follow component structure in `frontend/src/components/features/{domain}/`
- Co-locate tests with components: `ComponentName.test.tsx`

**Zustand Store Pattern (MANDATORY):**
```typescript
// CORRECT - Selector pattern
const unreadCount = useNotificationStore((state) => state.unreadCount);
const markAsRead = useNotificationStore((state) => state.markAsRead);

// WRONG - Full store subscription (causes re-renders)
const { unreadCount, markAsRead } = useNotificationStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions:**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `DashboardHeader`, `NotificationsDropdown` |
| Component files | PascalCase.tsx | `DashboardHeader.tsx` |
| Variables | camelCase | `unreadCount`, `isLoading` |
| Functions | camelCase | `markAsRead`, `fetchNotifications` |
| Constants | SCREAMING_SNAKE | `MAX_NOTIFICATIONS`, `NOTIFICATION_TYPES` |

### UX Design Reference

From UX-Decisions-Log.md wireframe:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  HEADER                                                                         │
│  ┌──────┐                                      ┌────┐ ┌────┐ ┌───────────┐      │
│  │ LDIP │   [🔍 Search all matters...]         │ 🔔 │ │ ❓ │ │ JJ ▼     │      │
│  │      │                                      │ 3  │ │    │ │ Juhi     │      │
│  └──────┘                                      └────┘ └────┘ └───────────┘      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Notification Types (from UX Design):**
| Icon | Type | Example |
|------|------|---------|
| 🟢 | Success | Processing complete, verification done |
| 🔵 | Info | Login, opened matter |
| 🟡 | In progress | Upload started, processing |
| ⚠️ | Attention needed | Contradictions found, low confidence |
| 🔴 | Error | Processing failed, upload error |

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── components/features/dashboard/    # NEW - This story
│   ├── DashboardHeader.tsx
│   ├── DashboardHeader.test.tsx
│   ├── NotificationsDropdown.tsx
│   ├── NotificationsDropdown.test.tsx
│   ├── UserProfileDropdown.tsx
│   ├── UserProfileDropdown.test.tsx
│   ├── GlobalSearch.tsx
│   ├── GlobalSearch.test.tsx
│   └── index.ts
├── stores/
│   ├── notificationStore.ts          # NEW
│   └── notificationStore.test.ts     # NEW
└── types/
    └── notification.ts               # NEW
```

**Existing Components to Use:**
- `frontend/src/components/ui/dropdown-menu.tsx` - DropdownMenu primitives
- `frontend/src/components/ui/input.tsx` - Input component
- `frontend/src/components/ui/badge.tsx` - Badge for notification count
- `frontend/src/components/ui/button.tsx` - Button component
- `frontend/src/components/features/auth/LogoutButton.tsx` - Logout action

**Existing Patterns to Follow:**
- `frontend/src/stores/uploadStore.ts` - Zustand store structure
- `frontend/src/types/matter.ts` - TypeScript types structure
- `frontend/src/components/features/verification/VerificationQueue.tsx` - Component structure

### Backend Dependencies

**Search API:** Backend search endpoint may not exist yet. Implement frontend with:
1. Interface defined for search API
2. Mock data for development
3. Easy swap to real API when available

**Notifications API:** Backend notification endpoints may not exist yet. Implement with:
1. Interface defined for notifications
2. Local state management initially
3. Ready to connect to backend when available

### Accessibility Requirements

From UX-Decisions-Log.md:
- Focus order: Header navigation → Tab bar → Main content
- Skip links: "Skip to main content" (visible on Tab focus)
- Keyboard: Escape closes dropdowns
- ARIA labels on icon buttons (help, notifications)

### Performance Considerations

- Header renders on every dashboard page - keep lightweight
- Lazy load dropdown content (notifications list fetched on open)
- Cache notification count in store with reasonable TTL
- Search should debounce input (300ms delay)

### References

- UX Wireframe: [UX-Decisions-Log.md#3-dashboard--home](../_bmad-output/project-planning-artifacts/UX-Decisions-Log.md)
- Architecture Naming: [architecture.md#naming-patterns](../_bmad-output/architecture.md)
- Component Patterns: [project-context.md#framework-specific-rules](../_bmad-output/project-context.md)
- Zustand Pattern: [project-context.md#zustand-state-management](../_bmad-output/project-context.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No significant debugging required

### Completion Notes List

1. **DashboardHeader component** - Implemented with LDIP logo, global search, notifications, help button, and user profile dropdown
2. **NotificationsDropdown component** - Shows notifications with type-based styling, mark as read/mark all as read functionality, unread count badge (shows 99+ for >99)
3. **UserProfileDropdown component** - Shows user avatar initials, name, email, with Settings, Help, and Sign Out options
4. **GlobalSearch component** - Search input with debounced search (300ms), results popover showing matters and documents with matched content
5. **Notification store** - Zustand store following selector pattern with mock data (backend API not yet available)
6. **Dashboard layout updated** - Server-side user data passed to header, removed inline header from page
7. **Tests** - 48 tests written covering all components and store functionality

### Implementation Notes

- **Mock Data**: Both notifications and search use mock data since backend APIs are not yet available. Interfaces are defined and ready for real API integration.
- **Selector Pattern**: All Zustand store usage follows the mandatory selector pattern to prevent unnecessary re-renders.
- **Accessibility**: All icon buttons have aria-labels, dropdowns are keyboard accessible.
- **Performance**: Notifications fetched on mount for badge count, lazy-loaded on dropdown open. Search debounces input by 300ms.

### File List

**New Files Created:**
- `frontend/src/types/notification.ts` - Notification types and helper functions
- `frontend/src/stores/notificationStore.ts` - Zustand store for notifications
- `frontend/src/stores/notificationStore.test.ts` - Store tests (22 tests)
- `frontend/src/components/features/dashboard/DashboardHeader.tsx` - Main header component
- `frontend/src/components/features/dashboard/DashboardHeader.test.tsx` - Header tests (6 tests)
- `frontend/src/components/features/dashboard/NotificationsDropdown.tsx` - Notifications dropdown
- `frontend/src/components/features/dashboard/NotificationsDropdown.test.tsx` - Notifications tests (7 tests)
- `frontend/src/components/features/dashboard/UserProfileDropdown.tsx` - User profile dropdown
- `frontend/src/components/features/dashboard/UserProfileDropdown.test.tsx` - User profile tests (8 tests)
- `frontend/src/components/features/dashboard/GlobalSearch.tsx` - Global search component
- `frontend/src/components/features/dashboard/GlobalSearch.test.tsx` - Search tests (8 tests)
- `frontend/src/components/features/dashboard/index.ts` - Feature exports

**Modified Files:**
- `frontend/src/app/(dashboard)/layout.tsx` - Added DashboardHeader, server-side user data
- `frontend/src/app/(dashboard)/page.tsx` - Removed inline header
