# Story 11.1: Implement Q&A Panel Header and Position

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to control the Q&A panel position**,
So that **I can arrange my workspace optimally**.

## Acceptance Criteria

1. **Given** I am in the workspace
   **When** the Q&A panel loads
   **Then** the header shows: "ASK LDIP", minimize button, position selector dropdown

2. **Given** I click the position selector
   **When** options appear
   **Then** I can choose: Right (default), Bottom, Float, Hide

3. **Given** I select "Float"
   **When** the panel updates
   **Then** it becomes a draggable, resizable floating window
   **And** it can overlap workspace content

4. **Given** I select "Hide"
   **When** the panel hides
   **Then** a small chat button appears in the corner
   **And** clicking it expands the panel

## Tasks / Subtasks

- [x] Task 1: Update header title to "ASK LDIP" (AC: #1)
  - [x] 1.1: Change title from "Q&A Assistant" to "ASK LDIP" in `QAPanelHeader.tsx`
  - [x] 1.2: Update title in `QAPanelPlaceholder.tsx` for consistency
  - [x] 1.3: Update any tests that check for "Q&A Assistant" text

- [x] Task 2: Add minimize button to all panel positions (AC: #1)
  - [x] 2.1: Add minimize button to `QAPanelHeader.tsx` as a prop-independent feature
  - [x] 2.2: Ensure minimize button appears in right, bottom, AND float modes
  - [x] 2.3: Minimize button should call `setPosition('hidden')`
  - [x] 2.4: Add tooltip "Minimize" to the button

- [x] Task 3: Verify position selector dropdown (AC: #2)
  - [x] 3.1: Verify dropdown shows all 4 options: Right, Bottom, Float, Hide
  - [x] 3.2: Verify current position is indicated with checkmark
  - [x] 3.3: Verify position changes persist to localStorage

- [x] Task 4: Verify floating panel functionality (AC: #3)
  - [x] 4.1: Verify panel is draggable via header
  - [x] 4.2: Verify panel is resizable via corner handle
  - [x] 4.3: Verify panel can overlap workspace content (z-index)
  - [x] 4.4: Verify position/size persists across page reloads

- [x] Task 5: Verify hidden mode expand button (AC: #4)
  - [x] 5.1: Verify chat button appears in bottom-right corner when hidden
  - [x] 5.2: Verify clicking restores to previous position
  - [x] 5.3: Verify unread badge displays correctly (mock data)

- [x] Task 6: Write/update tests for header changes (AC: All)
  - [x] 6.1: Update `QAPanelHeader.test.tsx` for "ASK LDIP" title
  - [x] 6.2: Add tests for minimize button presence and functionality
  - [x] 6.3: Update `QAPanel.test.tsx` for new title (no changes needed - uses mock)
  - [x] 6.4: Update `QAPanelPlaceholder.test.tsx` for consistency

- [x] Task 7: Run all tests and lint validation (AC: All)
  - [x] 7.1: Run `npm run test` - all chat/Q&A tests passing (101 tests)
  - [x] 7.2: Run `npm run lint` - no errors in chat components
  - [x] 7.3: Run TypeScript compiler - no type errors in chat components

## Dev Notes

### Critical Architecture Pattern: MOST INFRASTRUCTURE EXISTS

**IMPORTANT: Story 10A.3 already implemented most of this story's requirements!**

| Existing Component | Location | What Already Works |
|-------------------|----------|-------------------|
| `QAPanelHeader` | `components/features/chat/QAPanelHeader.tsx` | Position dropdown with all 4 options |
| `QAPanel` | `components/features/chat/QAPanel.tsx` | Main container, header + placeholder |
| `FloatingQAPanel` | `components/features/chat/FloatingQAPanel.tsx` | Full drag/resize, minimize button |
| `QAPanelExpandButton` | `components/features/chat/QAPanelExpandButton.tsx` | Hidden mode expand button with badge |
| `qaPanelStore` | `stores/qaPanelStore.ts` | Position state, persistence, all actions |

### What Actually Needs to Change

**Frontend Changes (MINIMAL):**

1. **QAPanelHeader.tsx** - Change title, add minimize button
2. **QAPanelPlaceholder.tsx** - Update title for consistency
3. **Test files** - Update assertions for new title

### Current Implementation Analysis

**QAPanelHeader.tsx:55** - Current title:
```tsx
<h2 className="text-sm font-semibold">Q&A Assistant</h2>
```

Should become:
```tsx
<h2 className="text-sm font-semibold">ASK LDIP</h2>
```

**QAPanelHeader.tsx:56-57** - Current actions section:
```tsx
<div className="flex items-center gap-1">
  {actions}  // Only used in floating mode for minimize button
  <DropdownMenu>
```

Should include minimize button by default (not just via `actions` prop):
```tsx
<div className="flex items-center gap-1">
  <Tooltip>
    <TooltipTrigger asChild>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setPosition('hidden')}
        aria-label="Minimize panel"
      >
        <Minus className="h-4 w-4" />
      </Button>
    </TooltipTrigger>
    <TooltipContent>
      <p>Minimize</p>
    </TooltipContent>
  </Tooltip>
  {actions}  // Keep for additional floating mode actions
  <DropdownMenu>
```

### Implementation Pattern for Minimize Button

```tsx
// QAPanelHeader.tsx - Updated implementation
import { Minus, Check, EyeOff, Move, PanelBottom, PanelRight, Settings2 } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export function QAPanelHeader({ actions }: QAPanelHeaderProps = {}) {
  const position = useQAPanelStore((state) => state.position);
  const setPosition = useQAPanelStore((state) => state.setPosition);

  const handleMinimize = () => {
    setPosition('hidden');
  };

  return (
    <div className="flex items-center justify-between border-b p-3">
      <h2 className="text-sm font-semibold">ASK LDIP</h2>
      <div className="flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleMinimize}
              aria-label="Minimize panel"
            >
              <Minus className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Minimize</p>
          </TooltipContent>
        </Tooltip>
        {actions}
        <DropdownMenu>
          {/* ... existing dropdown content unchanged ... */}
        </DropdownMenu>
      </div>
    </div>
  );
}
```

### FloatingQAPanel Adjustment

The FloatingQAPanel currently passes its own minimize button via `actions` prop:
```tsx
// FloatingQAPanel.tsx:175-191
const minimizeAction = (
  <Tooltip>
    <TooltipTrigger asChild>
      <Button variant="ghost" size="icon" onClick={handleMinimize}>
        <Minimize2 className="h-4 w-4" />
      </Button>
    </TooltipTrigger>
    ...
  </Tooltip>
);
```

Since minimize will now be in the header by default, FloatingQAPanel can:
- Option A: Remove its minimize action (header handles it)
- Option B: Keep it for a different minimize behavior (collapse vs hide)

**Recommendation:** Remove duplicate minimize from FloatingQAPanel since header now has it.

### Store Already Supports Everything

The `qaPanelStore.ts` already has:
- `setPosition('hidden')` - Working
- `restoreFromHidden()` - Working
- Position persistence to localStorage - Working
- All 4 position options - Working

### Testing Strategy

**Update Existing Tests:**
```typescript
// QAPanelHeader.test.tsx
test('renders ASK LDIP title', () => {
  render(<QAPanelHeader />);
  expect(screen.getByText('ASK LDIP')).toBeInTheDocument();
});

test('renders minimize button', () => {
  render(<QAPanelHeader />);
  expect(screen.getByRole('button', { name: /minimize/i })).toBeInTheDocument();
});

test('minimize button calls setPosition with hidden', async () => {
  render(<QAPanelHeader />);
  await userEvent.click(screen.getByRole('button', { name: /minimize/i }));
  // Verify store was called with 'hidden'
});
```

### Project Structure Notes

```
frontend/src/
├── components/features/chat/
│   ├── QAPanel.tsx              # NO CHANGES NEEDED
│   ├── QAPanelHeader.tsx        # UPDATE - Title + minimize button
│   ├── QAPanelPlaceholder.tsx   # UPDATE - Title for consistency
│   ├── FloatingQAPanel.tsx      # UPDATE - Remove duplicate minimize (optional)
│   ├── QAPanelExpandButton.tsx  # NO CHANGES NEEDED
│   ├── QAPanelHeader.test.tsx   # UPDATE - New title, minimize tests
│   ├── QAPanel.test.tsx         # UPDATE - If checks title
│   ├── QAPanelPlaceholder.test.tsx # UPDATE - If checks title
│   └── FloatingQAPanel.test.tsx # UPDATE - If minimize removed
└── stores/
    └── qaPanelStore.ts          # NO CHANGES NEEDED
```

### Previous Story Intelligence (Story 10A.3)

**Key Learnings:**
1. Q&A panel position system fully functional
2. Zustand store with persistence works correctly
3. Floating mode has full drag/resize functionality
4. Hidden mode expand button with unread badge works
5. All position transitions preserve state correctly

**From 10A.3 Implementation:**
- Position dropdown pattern established
- FloatingQAPanel drag/resize handling robust
- QAPanelExpandButton fixed position pattern works
- Tests comprehensive for store and components

### Git Commit Pattern

```
feat(qa-panel): update header to ASK LDIP with minimize button (Story 11.1)
```

### Testing Checklist

- [ ] Header shows "ASK LDIP" title
- [ ] Minimize button visible in right, bottom, and float modes
- [ ] Minimize button hides panel
- [ ] Position dropdown shows all 4 options
- [ ] Current position shows checkmark
- [ ] Right sidebar position works
- [ ] Bottom panel position works
- [ ] Float mode is draggable
- [ ] Float mode is resizable
- [ ] Hidden mode shows expand button
- [ ] Expand button restores to previous position
- [ ] Position persists after page reload
- [ ] Keyboard navigation works (arrow keys in float mode)
- [ ] Accessibility: all ARIA labels present

### References

- [Source: epics.md#Story-11.1 - Acceptance Criteria]
- [Source: 10a-3-content-area-qa-panel.md - Previous story with Q&A implementation]
- [Source: QAPanelHeader.tsx - Current header implementation]
- [Source: FloatingQAPanel.tsx - Floating panel with minimize]
- [Source: QAPanelExpandButton.tsx - Hidden mode expand button]
- [Source: qaPanelStore.ts - Position state management]
- [Source: project-context.md - Zustand selectors, naming conventions]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None required - implementation was straightforward.

### Completion Notes List

- Changed Q&A panel header title from "Q&A Assistant" to "ASK LDIP" in both QAPanelHeader.tsx and QAPanelPlaceholder.tsx
- Added minimize button with tooltip directly in QAPanelHeader.tsx (now appears in all panel positions: right, bottom, float)
- Removed duplicate minimize button logic from FloatingQAPanel.tsx since header now handles it
- Updated all test files to reflect the new "ASK LDIP" title
- Added new tests for minimize button presence and functionality in QAPanelHeader.test.tsx
- All 101 chat/Q&A related tests pass (55 component tests + 46 store tests)
- Lint passes with no errors for chat components

### Change Log

- 2026-01-15: Implemented Story 11.1 - Q&A Panel header shows "ASK LDIP" with minimize button in all positions
- 2026-01-15: Code review fixes - Removed unused `actions` prop from QAPanelHeader, updated FloatingQAPanel aria-label to "ASK LDIP", cleaned up stale comments and tests

### File List

**Modified:**
- frontend/src/components/features/chat/QAPanelHeader.tsx - Added minimize button, changed title to "ASK LDIP"
- frontend/src/components/features/chat/QAPanelPlaceholder.tsx - Changed title to "ASK LDIP"
- frontend/src/components/features/chat/FloatingQAPanel.tsx - Removed duplicate minimize button (now in header)
- frontend/src/components/features/chat/QAPanelHeader.test.tsx - Updated title tests, added minimize button tests
- frontend/src/components/features/chat/QAPanelPlaceholder.test.tsx - Updated title tests
- frontend/src/components/features/chat/FloatingQAPanel.test.tsx - Updated to reflect header changes
