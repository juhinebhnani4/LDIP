# Story 10A.1: Implement Workspace Shell Header

Status: completed

## Story

As an **attorney**,
I want **a consistent workspace layout with header controls**,
So that **I can navigate and manage my matter efficiently**.

## Acceptance Criteria

1. **Given** I enter a matter workspace
   **When** the shell loads
   **Then** the header shows: back to Dashboard link, editable matter name, Export dropdown, Share button, Settings gear

2. **Given** I click the matter name
   **When** edit mode activates
   **Then** I can rename the matter
   **And** the name updates across the system

3. **Given** I click Export
   **When** the dropdown opens
   **Then** I see format options (PDF, Word, PowerPoint)
   **And** clicking an option opens the Export Builder (placeholder for Epic 12)

4. **Given** I click Share
   **When** the dialog opens
   **Then** I can invite attorneys by email with role selection (Editor, Viewer)
   **And** see current collaborators

## Tasks / Subtasks

- [x] Task 1: Create WorkspaceHeader component (AC: #1)
  - [x] 1.1: Create `frontend/src/components/features/matter/WorkspaceHeader.tsx`
  - [x] 1.2: Add back navigation: left arrow icon + "Dashboard" link using Next.js Link to `/`
  - [x] 1.3: Display matter name in center (use `matterStore` to get current matter)
  - [x] 1.4: Add right side controls container for Export, Share, Settings
  - [x] 1.5: Use shadcn/ui `Button` with `variant="ghost"` for icon buttons
  - [x] 1.6: Follow DashboardHeader layout pattern from Story 9-1

- [x] Task 2: Implement editable matter name (AC: #2)
  - [x] 2.1: Create `frontend/src/components/features/matter/EditableMatterName.tsx`
  - [x] 2.2: Default display: matter name as text with subtle edit icon on hover
  - [x] 2.3: Click to activate edit mode: inline input field
  - [x] 2.4: Enter or blur to save, Escape to cancel
  - [x] 2.5: Call `PATCH /api/matters/{matter_id}` to update name (mock for MVP)
  - [x] 2.6: Update `matterStore` with new name on success
  - [x] 2.7: Show loading state during save, error toast on failure
  - [x] 2.8: Add optimistic update for immediate UI feedback

- [x] Task 3: Implement Export dropdown (AC: #3)
  - [x] 3.1: Create `frontend/src/components/features/matter/ExportDropdown.tsx`
  - [x] 3.2: Use shadcn/ui `DropdownMenu` component
  - [x] 3.3: Add menu items: "Export as PDF", "Export as Word", "Export as PowerPoint"
  - [x] 3.4: Add icons for each format (lucide-react: `FileText`, `FileType`, `Presentation`)
  - [x] 3.5: On click: show toast "Export Builder coming in Epic 12" (placeholder)
  - [x] 3.6: Future: navigate to `/matters/[matterId]/export?format={format}`

- [x] Task 4: Implement Share dialog (AC: #4)
  - [x] 4.1: Create `frontend/src/components/features/matter/ShareDialog.tsx`
  - [x] 4.2: Use shadcn/ui `Dialog` component
  - [x] 4.3: Add email input field with role selector (Editor/Viewer dropdown)
  - [x] 4.4: Add "Invite" button to send invitation
  - [x] 4.5: Display current collaborators list with their roles
  - [x] 4.6: Show owner badge for matter owner
  - [x] 4.7: Add remove collaborator action (for owners only)
  - [x] 4.8: Mock API call for MVP: `POST /api/matters/{matter_id}/members`
  - [x] 4.9: Integrate with mock data for current collaborators

- [x] Task 5: Implement Settings button (AC: #1)
  - [x] 5.1: Add Settings gear icon button in header
  - [x] 5.2: On click: show toast "Settings coming soon" (placeholder for future)
  - [x] 5.3: Future: navigate to matter settings page or open settings modal

- [x] Task 6: Update matter layout to use WorkspaceHeader (AC: #1)
  - [x] 6.1: Modify `frontend/src/app/(matter)/[matterId]/layout.tsx`
  - [x] 6.2: Import and render `WorkspaceHeader` component
  - [x] 6.3: Ensure header is sticky at top (like DashboardHeader)
  - [x] 6.4: Pass matterId prop from route params
  - [x] 6.5: Ensure MatterWorkspaceWrapper continues to function (processing status banner)

- [x] Task 7: Create/update matterStore for workspace context (AC: #2)
  - [x] 7.1: Verify `frontend/src/stores/matterStore.ts` has `currentMatter` state
  - [x] 7.2: Add `updateMatterName(matterId: string, name: string)` action if not exists
  - [x] 7.3: Add `fetchMatter(matterId: string)` action if not exists
  - [x] 7.4: Ensure proper selector exports for workspace header usage
  - [x] 7.5: Follow MANDATORY Zustand selector pattern

- [x] Task 8: Export new components (AC: All)
  - [x] 8.1: Update `frontend/src/components/features/matter/index.ts` to export all new components
  - [x] 8.2: Verify imports work correctly from barrel export

- [x] Task 9: Write comprehensive tests (AC: All)
  - [x] 9.1: Create `WorkspaceHeader.test.tsx` - header rendering, navigation, controls (9 tests)
  - [x] 9.2: Create `EditableMatterName.test.tsx` - edit mode, save, cancel, validation (17 tests)
  - [x] 9.3: Create `ExportDropdown.test.tsx` - dropdown interaction, menu items (8 tests)
  - [x] 9.4: Create `ShareDialog.test.tsx` - dialog open/close, invite flow, collaborator list (18 tests)

## Dev Notes

### Critical Architecture Patterns

**Component Structure (from architecture.md):**
```
frontend/src/components/features/matter/
├── WorkspaceHeader.tsx           # NEW - Main header component
├── WorkspaceHeader.test.tsx      # NEW - Header tests
├── EditableMatterName.tsx        # NEW - Inline editable name
├── EditableMatterName.test.tsx   # NEW
├── ExportDropdown.tsx            # NEW - Export format selection
├── ExportDropdown.test.tsx       # NEW
├── ShareDialog.tsx               # NEW - Sharing/collaboration dialog
├── ShareDialog.test.tsx          # NEW
├── MatterWorkspaceWrapper.tsx    # EXISTING - Keep as-is
└── index.ts                      # UPDATE - Add exports
```

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const currentMatter = useMatterStore((state) => state.currentMatter);
const updateMatterName = useMatterStore((state) => state.updateMatterName);

// WRONG - Full store subscription (causes re-renders)
const { currentMatter, updateMatterName, matters } = useMatterStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions (from project-context.md):**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `WorkspaceHeader`, `EditableMatterName` |
| Component files | PascalCase.tsx | `WorkspaceHeader.tsx` |
| Functions | camelCase | `handleNameChange`, `openShareDialog` |
| Constants | SCREAMING_SNAKE | `MAX_NAME_LENGTH`, `DEBOUNCE_DELAY_MS` |
| Types/Interfaces | PascalCase | `WorkspaceHeaderProps`, `Collaborator` |

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `Button` - for all clickable actions
- `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem` - for Export dropdown
- `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription` - for Share dialog
- `Input` - for editable name and email input
- `Select`, `SelectTrigger`, `SelectContent`, `SelectItem` - for role selection
- `Badge` - for owner/role badges
- `Tooltip` - for icon button hints

**Use lucide-react icons:**
- `ArrowLeft` - back to dashboard
- `Pencil` or `Edit2` - edit name indicator
- `Download` or `FileDown` - export button
- `Share2` or `Users` - share button
- `Settings` or `Cog` - settings button
- `FileText` - PDF export
- `FileType` - Word export
- `Presentation` - PowerPoint export
- `X` - close/remove
- `Check` - confirm/save
- `Loader2` - loading state

### Header Layout Reference (from DashboardHeader - Story 9-1)

```tsx
// DashboardHeader layout pattern to follow:
<header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
  <div className="container flex h-14 items-center justify-between">
    {/* Left: Back navigation */}
    <div className="flex items-center gap-2">
      <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        <span>Dashboard</span>
      </Link>
    </div>

    {/* Center: Editable matter name */}
    <div className="flex-1 flex justify-center">
      <EditableMatterName matterId={matterId} />
    </div>

    {/* Right: Actions */}
    <div className="flex items-center gap-2">
      <ExportDropdown matterId={matterId} />
      <ShareDialog matterId={matterId} />
      <Button variant="ghost" size="icon">
        <Settings className="h-4 w-4" />
      </Button>
    </div>
  </div>
</header>
```

### EditableMatterName Component Pattern

```tsx
// State machine for edit mode
type EditState = 'viewing' | 'editing' | 'saving';

interface EditableMatterNameProps {
  matterId: string;
}

// Key behaviors:
// 1. Hover shows subtle pencil icon
// 2. Click activates inline input
// 3. Enter or blur outside saves
// 4. Escape cancels and reverts
// 5. Show loading spinner while saving
// 6. Show error toast on failure
// 7. Optimistic update for responsiveness
```

### ShareDialog Component Pattern

```tsx
interface Collaborator {
  id: string;
  email: string;
  name: string;
  role: 'owner' | 'editor' | 'viewer';
  avatarUrl?: string;
}

interface ShareDialogProps {
  matterId: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

// Key behaviors:
// 1. Email validation before invite
// 2. Role selection dropdown (Editor/Viewer)
// 3. Show existing collaborators with roles
// 4. Owner badge for matter owner
// 5. Remove button (owner only)
// 6. Success/error toasts for actions
```

### API Integration (Mock for MVP)

**Update matter name:**
```typescript
// Mock implementation - will connect to real API later
async function updateMatterName(matterId: string, name: string): Promise<void> {
  // TODO: Replace with actual API call
  // PATCH /api/matters/{matter_id}
  // Body: { name: string }

  // For MVP, just update the store
  await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network
  // matterStore.updateMatter(matterId, { name });
}
```

**Invite collaborator:**
```typescript
// Mock implementation
async function inviteCollaborator(
  matterId: string,
  email: string,
  role: 'editor' | 'viewer'
): Promise<void> {
  // TODO: Replace with actual API call
  // POST /api/matters/{matter_id}/members
  // Body: { email: string, role: string }

  await new Promise(resolve => setTimeout(resolve, 500));
  // Show success toast
}
```

### Existing Code to Reference/Reuse

**DashboardHeader (pattern reference):**
- `frontend/src/components/features/dashboard/DashboardHeader.tsx` - Header layout pattern
- `frontend/src/components/features/dashboard/NotificationsDropdown.tsx` - Dropdown pattern
- `frontend/src/components/features/dashboard/UserProfileDropdown.tsx` - User menu pattern

**MatterWorkspaceWrapper (existing integration):**
- `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx` - Processing status tracking
- Keep this component functioning - WorkspaceHeader is additive

**Stores:**
- `frontend/src/stores/matterStore.ts` - Matter state management
- `frontend/src/stores/notificationStore.ts` - Toast notifications pattern

**Types:**
- `frontend/src/types/matter.ts` - Matter type definitions

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── app/(matter)/[matterId]/
│   ├── layout.tsx                    # UPDATE - Add WorkspaceHeader
│   └── page.tsx                      # Will be updated in Story 10A.3
├── components/features/matter/
│   ├── WorkspaceHeader.tsx           # NEW
│   ├── WorkspaceHeader.test.tsx      # NEW
│   ├── EditableMatterName.tsx        # NEW
│   ├── EditableMatterName.test.tsx   # NEW
│   ├── ExportDropdown.tsx            # NEW
│   ├── ExportDropdown.test.tsx       # NEW
│   ├── ShareDialog.tsx               # NEW
│   ├── ShareDialog.test.tsx          # NEW
│   ├── MatterWorkspaceWrapper.tsx    # EXISTING - Do not modify
│   └── index.ts                      # UPDATE - Add exports
└── stores/
    └── matterStore.ts                # UPDATE if needed - Add workspace actions
```

### Previous Story Intelligence (Story 9-6)

**From Story 9-6 implementation:**
- CompletionScreen redirects to `/` (dashboard) with TODO to change to `/matters/[matterId]`
- This story provides the destination for that redirect
- Browser notifications also point to matter workspace (will work after this story)
- Background processing completion will navigate here

**Key learnings from Epic 9:**
- Header components use sticky positioning with backdrop blur
- Use `h-14` height for consistent header sizing
- Use `container` class for proper max-width and centering
- Use `gap-2` for consistent spacing between items
- Loading states use `Loader2` icon with `animate-spin`

### Git Commit Context (Recent Relevant Commits)

```
b8529da fix(review): code review fixes for Story 9-6
689dc40 feat(upload): implement upload flow stage 5 completion (Story 9-6)
f64fd1c fix(review): code review fixes for Story 9-5
9da080d feat(upload): implement upload flow stages 3-4 (Story 9-5)
```

Recent patterns established:
- Comprehensive test coverage for all new components
- Co-located test files (ComponentName.test.tsx)
- Use of Zustand selector pattern throughout
- Mock implementations for APIs not yet built

### Testing Considerations

**WorkspaceHeader tests:**
```typescript
describe('WorkspaceHeader', () => {
  it('renders back to dashboard link', () => {});
  it('displays matter name', () => {});
  it('renders export dropdown', () => {});
  it('renders share button', () => {});
  it('renders settings button', () => {});
  it('back link navigates to dashboard', () => {});
});
```

**EditableMatterName tests:**
```typescript
describe('EditableMatterName', () => {
  it('displays matter name in view mode', () => {});
  it('shows edit icon on hover', () => {});
  it('switches to edit mode on click', () => {});
  it('saves on Enter key', () => {});
  it('saves on blur', () => {});
  it('cancels on Escape key', () => {});
  it('shows loading state while saving', () => {});
  it('handles save error gracefully', () => {});
  it('validates name is not empty', () => {});
});
```

**ShareDialog tests:**
```typescript
describe('ShareDialog', () => {
  it('opens dialog when triggered', () => {});
  it('displays email input and role selector', () => {});
  it('validates email format', () => {});
  it('sends invite on button click', () => {});
  it('displays current collaborators', () => {});
  it('shows owner badge for owner', () => {});
  it('allows owner to remove collaborators', () => {});
  it('closes dialog on success', () => {});
});
```

### Accessibility Requirements

From project-context.md and UX best practices:
- All buttons have accessible labels (aria-label for icon-only buttons)
- Dropdown menus are keyboard navigable
- Dialog has proper focus management (focus trap)
- Edit mode input is properly labeled
- Loading states announced to screen readers
- Color contrast meets WCAG AA standards
- Tooltips provide context for icon buttons

### Error Handling

**Name update errors:**
- Show toast: "Failed to update matter name. Please try again."
- Revert to previous name on error
- Log error to console with structured format

**Share invite errors:**
- Show toast: "Failed to send invite. Please check the email and try again."
- Keep dialog open for retry
- Highlight invalid email if format error

### Constants to Define

```typescript
// In WorkspaceHeader or constants file
export const MAX_MATTER_NAME_LENGTH = 100;
export const SAVE_DEBOUNCE_MS = 500;
export const COLLABORATOR_ROLES = ['editor', 'viewer'] as const;
export type CollaboratorRole = typeof COLLABORATOR_ROLES[number];
```

### References

- [Source: epics.md#story-10a1 - Acceptance criteria]
- [Source: architecture.md#frontend-structure - Component organization]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: DashboardHeader.tsx - Header layout pattern reference]
- [Source: Story 9-6 - Previous story patterns and redirect destination]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No debugging issues encountered

### Completion Notes List

1. **All 52 tests passing** - WorkspaceHeader (9), EditableMatterName (17), ExportDropdown (8), ShareDialog (18)
2. **Lint clean** - All files pass ESLint with no errors
3. **Added shadcn/ui components** - Avatar and Separator components were added to support ShareDialog
4. **Store enhancements** - matterStore extended with `currentMatter`, `fetchMatter`, `setCurrentMatter`, and `updateMatterName` actions
5. **Matter layout updated** - WorkspaceHeader integrated in `(matter)/[matterId]/layout.tsx`
6. **API mock implementations** - All API calls are mocked with TODO comments for future backend integration
7. **Accessibility** - All buttons have aria-labels, keyboard navigation works, tooltips provided for icon buttons

### File List

**New Files Created:**
- `frontend/src/components/features/matter/WorkspaceHeader.tsx`
- `frontend/src/components/features/matter/WorkspaceHeader.test.tsx`
- `frontend/src/components/features/matter/EditableMatterName.tsx`
- `frontend/src/components/features/matter/EditableMatterName.test.tsx`
- `frontend/src/components/features/matter/ExportDropdown.tsx`
- `frontend/src/components/features/matter/ExportDropdown.test.tsx`
- `frontend/src/components/features/matter/ShareDialog.tsx`
- `frontend/src/components/features/matter/ShareDialog.test.tsx`
- `frontend/src/components/ui/avatar.tsx` (via shadcn)
- `frontend/src/components/ui/separator.tsx` (via shadcn)

**Modified Files:**
- `frontend/src/app/(matter)/[matterId]/layout.tsx` - Added WorkspaceHeader
- `frontend/src/components/features/matter/index.ts` - Added exports
- `frontend/src/stores/matterStore.ts` - Added workspace context actions

