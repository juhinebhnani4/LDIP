# Story 10A.3: Implement Main Content Area and Q&A Panel Integration

Status: review

## Story

As an **attorney**,
I want **the main content area to work alongside the Q&A panel**,
So that **I can ask questions while viewing analysis results**.

## Acceptance Criteria

1. **Given** I am in the workspace
   **When** content loads
   **Then** the main content area shows the active tab content
   **And** the Q&A panel appears in its configured position (default: right sidebar)

2. **Given** I resize the Q&A panel
   **When** I drag the divider
   **Then** the panel resizes (20-60% width range)
   **And** the main content adjusts accordingly

3. **Given** I change Q&A panel position
   **When** I select a new position (right, bottom, float, hide)
   **Then** the panel moves to the new position
   **And** my preference is saved

## Tasks / Subtasks

- [x] Task 1: Add shadcn/ui Resizable component (AC: #2)
  - [x] 1.1: Run `npx shadcn@latest add resizable` to add resizable primitives
  - [x] 1.2: Verify `ResizablePanelGroup`, `ResizablePanel`, `ResizableHandle` components installed
  - [x] 1.3: Check dependency `react-resizable-panels` is added to package.json

- [x] Task 2: Create Q&A Panel components (AC: #1, #2)
  - [x] 2.1: Create `frontend/src/components/features/chat/QAPanel.tsx` - main Q&A panel component
  - [x] 2.2: Create `frontend/src/components/features/chat/QAPanelHeader.tsx` - panel header with position controls
  - [x] 2.3: Create `frontend/src/components/features/chat/QAPanelPlaceholder.tsx` - placeholder content (full Q&A in Epic 11)
  - [x] 2.4: Create `frontend/src/components/features/chat/index.ts` - barrel export

- [x] Task 3: Create Q&A Panel position store (AC: #3)
  - [x] 3.1: Create `frontend/src/stores/qaPanelStore.ts` for Q&A panel state
  - [x] 3.2: Define `QAPanelPosition` type: 'right' | 'bottom' | 'float' | 'hidden'
  - [x] 3.3: Add `position`, `width`, `height` state with defaults (right, 35%, 40%)
  - [x] 3.4: Add `setPosition`, `setWidth`, `setHeight` actions
  - [x] 3.5: Add `loadPreferences`, `savePreferences` for localStorage persistence
  - [x] 3.6: Follow MANDATORY Zustand selector pattern

- [x] Task 4: Create WorkspaceContentArea component (AC: #1, #2)
  - [x] 4.1: Create `frontend/src/components/features/matter/WorkspaceContentArea.tsx`
  - [x] 4.2: Implement resizable two-panel layout: [Tab Content | Q&A Panel]
  - [x] 4.3: Use `ResizablePanelGroup` with horizontal direction for right sidebar
  - [x] 4.4: Enforce 20-60% width constraint via `minSize`/`maxSize` on Q&A panel
  - [x] 4.5: Add `ResizableHandle` with visible drag affordance
  - [x] 4.6: Connect to `qaPanelStore` for width persistence

- [x] Task 5: Implement panel position switching (AC: #3)
  - [x] 5.1: Add position selector dropdown in `QAPanelHeader` (right, bottom, float, hidden)
  - [x] 5.2: Implement bottom panel layout (horizontal resize, 20-60% height range)
  - [x] 5.3: Implement floating panel with drag-to-move and resize handles
  - [x] 5.4: Implement hidden mode with floating expand button
  - [x] 5.5: Persist position preference to localStorage on change
  - [x] 5.6: Load saved preference on mount

- [x] Task 6: Create floating panel logic (AC: #3)
  - [x] 6.1: Create `frontend/src/components/features/chat/FloatingQAPanel.tsx`
  - [x] 6.2: Implement draggable positioning (constrained to viewport)
  - [x] 6.3: Implement corner resize (min 300x200, max 80% viewport)
  - [x] 6.4: Save position and size to localStorage
  - [x] 6.5: Add z-index management to stay above content but below modals
  - [x] 6.6: Add close button to return to hidden mode

- [x] Task 7: Update matter layout integration (AC: #1)
  - [x] 7.1: Modify `frontend/src/app/(matter)/[matterId]/layout.tsx`
  - [x] 7.2: Replace simple `main` content with `WorkspaceContentArea`
  - [x] 7.3: Pass children (tab content) as content panel child
  - [x] 7.4: Ensure Q&A panel renders based on position setting
  - [x] 7.5: Maintain existing `MatterWorkspaceWrapper` functionality

- [x] Task 8: Create hidden mode expand button (AC: #3)
  - [x] 8.1: Create `frontend/src/components/features/chat/QAPanelExpandButton.tsx`
  - [x] 8.2: Position as fixed button in bottom-right corner
  - [x] 8.3: Use `MessageSquare` icon with tooltip "Open Q&A Panel"
  - [x] 8.4: Show badge with unread count (mock for MVP)
  - [x] 8.5: Click to restore panel to previous non-hidden position

- [x] Task 9: Export new components (AC: All)
  - [x] 9.1: Update `frontend/src/components/features/matter/index.ts` with WorkspaceContentArea
  - [x] 9.2: Create `frontend/src/components/features/chat/index.ts` barrel export
  - [x] 9.3: Update `frontend/src/stores/index.ts` with qaPanelStore export

- [x] Task 10: Write comprehensive tests (AC: All)
  - [x] 10.1: Create `QAPanel.test.tsx` - panel rendering, header, content placeholder
  - [x] 10.2: Create `QAPanelHeader.test.tsx` - position dropdown, button interactions
  - [x] 10.3: Create `WorkspaceContentArea.test.tsx` - resize behavior, panel integration
  - [x] 10.4: Create `qaPanelStore.test.ts` - state changes, localStorage persistence
  - [x] 10.5: Test panel position transitions (right -> bottom -> float -> hidden)
  - [x] 10.6: Test resize constraints (min/max enforcement)
  - [x] 10.7: Test preference persistence across page reloads

## Dev Notes

### Critical Architecture Patterns

**Q&A Panel Position Configuration (from UX-Decisions-Log.md):**
```typescript
// Panel positions available
export type QAPanelPosition = 'right' | 'bottom' | 'float' | 'hidden';

// Position behaviors (from UX section 5.2):
// - Right sidebar (default): Vertical panel, resizable width (20-60%)
// - Bottom panel: Horizontal panel, resizable height (20-60%)
// - Floating: Draggable anywhere, resizable, can overlap content
// - Hidden: Collapsed, small button to expand
```

**Component Structure (from architecture.md):**
```
frontend/src/
├── app/(matter)/[matterId]/
│   └── layout.tsx                    # UPDATE - Use WorkspaceContentArea
├── components/features/
│   ├── matter/
│   │   ├── WorkspaceContentArea.tsx  # NEW - Resizable content + Q&A layout
│   │   ├── WorkspaceContentArea.test.tsx # NEW
│   │   └── index.ts                  # UPDATE - Add exports
│   └── chat/                         # NEW - Q&A panel components
│       ├── QAPanel.tsx               # NEW - Main panel container
│       ├── QAPanel.test.tsx          # NEW
│       ├── QAPanelHeader.tsx         # NEW - Header with position controls
│       ├── QAPanelHeader.test.tsx    # NEW
│       ├── QAPanelPlaceholder.tsx    # NEW - Placeholder for Epic 11
│       ├── FloatingQAPanel.tsx       # NEW - Floating mode implementation
│       ├── QAPanelExpandButton.tsx   # NEW - Hidden mode expand button
│       └── index.ts                  # NEW - Barrel export
└── stores/
    ├── qaPanelStore.ts               # NEW - Q&A panel position/size state
    ├── qaPanelStore.test.ts          # NEW
    └── index.ts                      # UPDATE - Add export
```

**Zustand Store Pattern (MANDATORY from project-context.md):**
```typescript
// CORRECT - Selector pattern
const position = useQAPanelStore((state) => state.position);
const setPosition = useQAPanelStore((state) => state.setPosition);
const width = useQAPanelStore((state) => state.width);

// WRONG - Full store subscription (causes re-renders)
const { position, setPosition, width, height } = useQAPanelStore();
```

**TypeScript Requirements:**
- Strict mode: no `any` types - use `unknown` + type guards
- Use `satisfies` operator for type-safe objects
- Import types separately: `import type { FC } from 'react'`

**Naming Conventions (from project-context.md):**
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `QAPanel`, `WorkspaceContentArea` |
| Component files | PascalCase.tsx | `QAPanel.tsx` |
| Hooks | camelCase with `use` prefix | `useQAPanelPosition` |
| Functions | camelCase | `handlePositionChange`, `savePanelPreferences` |
| Constants | SCREAMING_SNAKE | `DEFAULT_PANEL_WIDTH`, `MIN_PANEL_WIDTH` |
| Types/Interfaces | PascalCase | `QAPanelPosition`, `QAPanelState` |

### UI Component Requirements

**Use existing shadcn/ui components (DO NOT RECREATE):**
- `ResizablePanelGroup`, `ResizablePanel`, `ResizableHandle` - for resizable layout (NEED TO ADD)
- `DropdownMenu` - for position selector
- `Button` - for panel actions
- `Tooltip` - for icon button hints
- `Badge` - for unread message count

**Use lucide-react icons:**
- `PanelRight` - right sidebar position
- `PanelBottom` - bottom panel position
- `Maximize2` or `Move` - floating position
- `X` or `EyeOff` - hidden position
- `MessageSquare` - Q&A expand button
- `GripVertical` / `GripHorizontal` - resize handle indicator
- `Settings2` - panel settings
- `Minimize2` - minimize floating panel

### Q&A Panel Store Pattern

```typescript
// stores/qaPanelStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type QAPanelPosition = 'right' | 'bottom' | 'float' | 'hidden';

interface QAPanelState {
  // Position and sizing
  position: QAPanelPosition;
  rightWidth: number;    // Percentage (20-60)
  bottomHeight: number;  // Percentage (20-60)
  floatX: number;        // Pixels from left
  floatY: number;        // Pixels from top
  floatWidth: number;    // Pixels
  floatHeight: number;   // Pixels
  previousPosition: QAPanelPosition; // For restoring from hidden

  // Mock state for MVP
  unreadCount: number;
}

interface QAPanelActions {
  setPosition: (position: QAPanelPosition) => void;
  setRightWidth: (width: number) => void;
  setBottomHeight: (height: number) => void;
  setFloatPosition: (x: number, y: number) => void;
  setFloatSize: (width: number, height: number) => void;
  restoreFromHidden: () => void;
  setUnreadCount: (count: number) => void;
}

// Defaults from UX spec
const DEFAULT_RIGHT_WIDTH = 35;
const DEFAULT_BOTTOM_HEIGHT = 40;
const DEFAULT_FLOAT_WIDTH = 400;
const DEFAULT_FLOAT_HEIGHT = 500;
const MIN_PANEL_SIZE = 20;  // percentage
const MAX_PANEL_SIZE = 60;  // percentage
```

### WorkspaceContentArea Layout Pattern

```tsx
// WorkspaceContentArea - handles all Q&A panel positions
'use client';

import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import { useQAPanelStore } from '@/stores/qaPanelStore';
import { QAPanel, FloatingQAPanel, QAPanelExpandButton } from '@/components/features/chat';

interface WorkspaceContentAreaProps {
  children: ReactNode; // Tab content
  matterId: string;
}

function WorkspaceContentArea({ children, matterId }: WorkspaceContentAreaProps) {
  const position = useQAPanelStore((state) => state.position);
  const rightWidth = useQAPanelStore((state) => state.rightWidth);
  const bottomHeight = useQAPanelStore((state) => state.bottomHeight);
  const setRightWidth = useQAPanelStore((state) => state.setRightWidth);
  const setBottomHeight = useQAPanelStore((state) => state.setBottomHeight);

  // Right sidebar layout
  if (position === 'right') {
    return (
      <ResizablePanelGroup direction="horizontal" className="flex-1">
        <ResizablePanel defaultSize={100 - rightWidth} minSize={40}>
          <div className="h-full overflow-auto">
            {children}
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel
          defaultSize={rightWidth}
          minSize={20}
          maxSize={60}
          onResize={setRightWidth}
        >
          <QAPanel matterId={matterId} />
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  // Bottom panel layout
  if (position === 'bottom') {
    return (
      <ResizablePanelGroup direction="vertical" className="flex-1">
        <ResizablePanel defaultSize={100 - bottomHeight} minSize={40}>
          <div className="h-full overflow-auto">
            {children}
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel
          defaultSize={bottomHeight}
          minSize={20}
          maxSize={60}
          onResize={setBottomHeight}
        >
          <QAPanel matterId={matterId} />
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  // Floating panel layout
  if (position === 'float') {
    return (
      <div className="relative flex-1">
        <div className="h-full overflow-auto">
          {children}
        </div>
        <FloatingQAPanel matterId={matterId} />
      </div>
    );
  }

  // Hidden - just content with expand button
  return (
    <div className="relative flex-1">
      <div className="h-full overflow-auto">
        {children}
      </div>
      <QAPanelExpandButton />
    </div>
  );
}
```

### Q&A Panel Header Pattern

```tsx
// QAPanelHeader - position controls
interface QAPanelHeaderProps {
  matterId: string;
}

function QAPanelHeader({ matterId }: QAPanelHeaderProps) {
  const position = useQAPanelStore((state) => state.position);
  const setPosition = useQAPanelStore((state) => state.setPosition);

  return (
    <div className="flex items-center justify-between p-3 border-b">
      <h2 className="text-sm font-semibold">Q&A Assistant</h2>
      <div className="flex items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Panel position">
              <Settings2 className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Panel Position</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setPosition('right')}>
              <PanelRight className="mr-2 h-4 w-4" />
              Right Sidebar
              {position === 'right' && <Check className="ml-auto h-4 w-4" />}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setPosition('bottom')}>
              <PanelBottom className="mr-2 h-4 w-4" />
              Bottom Panel
              {position === 'bottom' && <Check className="ml-auto h-4 w-4" />}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setPosition('float')}>
              <Move className="mr-2 h-4 w-4" />
              Floating
              {position === 'float' && <Check className="ml-auto h-4 w-4" />}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setPosition('hidden')}>
              <EyeOff className="mr-2 h-4 w-4" />
              Hide Panel
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
```

### Q&A Panel Placeholder Content

```tsx
// QAPanelPlaceholder - MVP placeholder for Epic 11
function QAPanelPlaceholder() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
      <MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium mb-2">Q&A Assistant</h3>
      <p className="text-sm text-muted-foreground max-w-xs">
        Ask questions about your matter. The AI will analyze documents
        and provide answers with citations.
      </p>
      <p className="text-xs text-muted-foreground mt-4">
        Coming in Epic 11
      </p>
    </div>
  );
}
```

### Floating Panel Implementation

```tsx
// FloatingQAPanel - draggable, resizable floating panel
'use client';

import { useState, useRef, useCallback } from 'react';
import { useQAPanelStore } from '@/stores/qaPanelStore';

const MIN_WIDTH = 300;
const MIN_HEIGHT = 200;

function FloatingQAPanel({ matterId }: { matterId: string }) {
  const floatX = useQAPanelStore((state) => state.floatX);
  const floatY = useQAPanelStore((state) => state.floatY);
  const floatWidth = useQAPanelStore((state) => state.floatWidth);
  const floatHeight = useQAPanelStore((state) => state.floatHeight);
  const setFloatPosition = useQAPanelStore((state) => state.setFloatPosition);
  const setFloatSize = useQAPanelStore((state) => state.setFloatSize);
  const setPosition = useQAPanelStore((state) => state.setPosition);

  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });

  // Drag handlers for header
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    setIsDragging(true);
    dragOffset.current = {
      x: e.clientX - floatX,
      y: e.clientY - floatY,
    };
  }, [floatX, floatY]);

  // ... mouse move/up handlers for drag and resize

  return (
    <div
      className="fixed bg-background border rounded-lg shadow-lg z-40"
      style={{
        left: floatX,
        top: floatY,
        width: floatWidth,
        height: floatHeight,
      }}
    >
      {/* Draggable header */}
      <div
        className="cursor-move"
        onMouseDown={handleDragStart}
      >
        <QAPanelHeader matterId={matterId} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <QAPanelPlaceholder />
      </div>

      {/* Resize handle in corner */}
      <div
        className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
        onMouseDown={(e) => {
          e.stopPropagation();
          setIsResizing(true);
        }}
      >
        <GripHorizontal className="h-4 w-4 text-muted-foreground" />
      </div>
    </div>
  );
}
```

### Existing Code to Reference/Reuse

**WorkspaceHeader & WorkspaceTabBar (from Story 10A.1 & 10A.2):**
- `frontend/src/components/features/matter/WorkspaceHeader.tsx` - Header pattern
- `frontend/src/components/features/matter/WorkspaceTabBar.tsx` - Tab pattern
- Follow same styling conventions (container, backdrop-blur, etc.)

**Matter Layout (integration point):**
- `frontend/src/app/(matter)/[matterId]/layout.tsx` - Where WorkspaceContentArea will be integrated

**Stores:**
- `frontend/src/stores/workspaceStore.ts` - Store pattern with Zustand persist
- `frontend/src/stores/matterStore.ts` - Store pattern reference

**Types:**
- `frontend/src/types/matter.ts` - Matter type definitions

### Project Structure Notes

**File Locations:**
```
frontend/src/
├── app/(matter)/[matterId]/
│   └── layout.tsx                    # UPDATE - Use WorkspaceContentArea
├── components/
│   ├── ui/
│   │   └── resizable.tsx             # NEW - via shadcn (react-resizable-panels)
│   └── features/
│       ├── matter/
│       │   ├── WorkspaceContentArea.tsx      # NEW
│       │   ├── WorkspaceContentArea.test.tsx # NEW
│       │   └── index.ts                      # UPDATE
│       └── chat/
│           ├── QAPanel.tsx                   # NEW
│           ├── QAPanel.test.tsx              # NEW
│           ├── QAPanelHeader.tsx             # NEW
│           ├── QAPanelHeader.test.tsx        # NEW
│           ├── QAPanelPlaceholder.tsx        # NEW
│           ├── FloatingQAPanel.tsx           # NEW
│           ├── QAPanelExpandButton.tsx       # NEW
│           └── index.ts                      # NEW
└── stores/
    ├── qaPanelStore.ts               # NEW
    ├── qaPanelStore.test.ts          # NEW
    └── index.ts                      # UPDATE
```

### Previous Story Intelligence (Stories 10A.1 & 10A.2)

**From Story 10A.1 implementation:**
- WorkspaceHeader uses sticky positioning with backdrop blur at `top-0`
- Header height is `h-14`
- Container class provides proper max-width and centering
- Uses shadcn/ui Dialog, DropdownMenu patterns
- Comprehensive test coverage with co-located tests
- All 52 tests passing

**From Story 10A.2 implementation:**
- WorkspaceTabBar positioned at `top-14` (below header)
- Tab bar height is `h-12`
- workspaceStore uses Zustand persist pattern
- Keyboard navigation implemented
- All 59 tests passing

**Key patterns established:**
- Comprehensive test coverage for all new components
- Co-located test files (ComponentName.test.tsx)
- Use of Zustand selector pattern throughout
- Mock implementations for APIs not yet built
- Barrel exports from index.ts files

### Git Commit Context (Recent Relevant Commits)

```
02d261a fix(review): code review fixes for Story 10A.2
ba592a7 feat(workspace): implement tab bar navigation (Story 10A.2)
79e7f0a fix(review): code review fixes for Story 10A.1
a6a6865 feat(workspace): implement workspace shell header (Story 10A.1)
```

Recent patterns established:
- Stories in Epic 10A follow consistent component patterns
- Test files co-located with components
- Zustand selectors enforced throughout
- Code review identifies and fixes HIGH/MEDIUM issues

### Testing Considerations

**WorkspaceContentArea tests:**
```typescript
describe('WorkspaceContentArea', () => {
  // Position layout tests (AC #1)
  it('renders right sidebar layout when position is right', () => {});
  it('renders bottom panel layout when position is bottom', () => {});
  it('renders floating panel when position is float', () => {});
  it('renders expand button when position is hidden', () => {});
  it('renders children (tab content) in content panel', () => {});

  // Resize tests (AC #2)
  it('allows resizing Q&A panel width in right mode', () => {});
  it('allows resizing Q&A panel height in bottom mode', () => {});
  it('enforces minimum panel size of 20%', () => {});
  it('enforces maximum panel size of 60%', () => {});
  it('persists resize to store', () => {});
});
```

**QAPanelHeader tests:**
```typescript
describe('QAPanelHeader', () => {
  it('renders Q&A Assistant title', () => {});
  it('renders position dropdown menu', () => {});
  it('shows all four position options', () => {});
  it('highlights current position with checkmark', () => {});
  it('calls setPosition when option selected', () => {});
});
```

**qaPanelStore tests:**
```typescript
describe('qaPanelStore', () => {
  // State tests
  it('initializes with right position as default', () => {});
  it('initializes with default widths and heights', () => {});

  // Action tests
  it('setPosition updates position state', () => {});
  it('setRightWidth updates rightWidth state', () => {});
  it('setBottomHeight updates bottomHeight state', () => {});
  it('setFloatPosition updates float x/y', () => {});
  it('setFloatSize updates float width/height', () => {});

  // Restore behavior
  it('restoreFromHidden returns to previous non-hidden position', () => {});
  it('stores previousPosition when hiding', () => {});

  // Persistence tests
  it('persists state to localStorage', () => {});
  it('loads state from localStorage on init', () => {});
});
```

### Accessibility Requirements

From project-context.md and UX best practices:
- Resize handles have `aria-label="Resize panel"`
- Position dropdown is keyboard navigable
- Floating panel can be moved via keyboard (arrow keys when focused on drag handle)
- Close/hide buttons have clear aria-labels
- Panel content area has proper heading structure
- Focus trapped within floating panel when open
- Announce position changes to screen readers

### Error Handling

**Resize errors:**
- Clamp values to min/max range (don't throw)
- If localStorage fails, use defaults and log warning
- Don't break layout on invalid stored values

**Position change errors:**
- Validate position value before setting
- Log invalid positions but don't crash
- Fall back to 'right' if position is invalid

### Constants to Define

```typescript
// Q&A Panel constants
export const QA_PANEL_POSITIONS = ['right', 'bottom', 'float', 'hidden'] as const;
export type QAPanelPosition = typeof QA_PANEL_POSITIONS[number];

export const DEFAULT_PANEL_POSITION: QAPanelPosition = 'right';
export const DEFAULT_RIGHT_WIDTH = 35;      // percentage
export const DEFAULT_BOTTOM_HEIGHT = 40;    // percentage
export const MIN_PANEL_SIZE = 20;           // percentage
export const MAX_PANEL_SIZE = 60;           // percentage

export const DEFAULT_FLOAT_WIDTH = 400;     // pixels
export const DEFAULT_FLOAT_HEIGHT = 500;    // pixels
export const MIN_FLOAT_WIDTH = 300;         // pixels
export const MIN_FLOAT_HEIGHT = 200;        // pixels

export const STORAGE_KEY = 'ldip-qa-panel-preferences';
```

### Integration Notes

**Layout Update Approach:**
The matter layout currently renders:
```tsx
<main className="flex-1">
  <MatterWorkspaceWrapper matterId={matterId}>
    {children}
  </MatterWorkspaceWrapper>
</main>
```

After this story, it will render:
```tsx
<main className="flex-1">
  <MatterWorkspaceWrapper matterId={matterId}>
    <WorkspaceContentArea matterId={matterId}>
      {children}
    </WorkspaceContentArea>
  </MatterWorkspaceWrapper>
</main>
```

**Future Epic 11 Integration:**
- `QAPanelPlaceholder` will be replaced with actual chat components
- `QAPanel` shell structure remains, only content changes
- Store structure supports message history, streaming state (add later)

### References

- [Source: epics.md#story-10a3 - Acceptance criteria]
- [Source: UX-Decisions-Log.md#section-1.3 - Q&A Panel Position decision]
- [Source: UX-Decisions-Log.md#section-5.2 - Q&A Panel Options]
- [Source: architecture.md#frontend-structure - Component organization]
- [Source: project-context.md - Zustand selector pattern, naming conventions]
- [Source: Story 10A.1 - WorkspaceHeader patterns]
- [Source: Story 10A.2 - WorkspaceTabBar and workspaceStore patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No blocking issues encountered

### Completion Notes List

- Implemented Q&A Panel integration with main content area supporting 4 position modes: right sidebar, bottom panel, floating window, and hidden
- Created qaPanelStore with Zustand persist middleware for localStorage persistence of panel preferences
- Implemented resizable panels using shadcn/ui resizable component (react-resizable-panels library)
- Built FloatingQAPanel with drag-to-move and corner resize functionality
- Created QAPanelExpandButton for hidden mode with unread count badge
- Integrated WorkspaceContentArea into matter layout
- All acceptance criteria satisfied:
  - AC #1: Main content shows active tab, Q&A panel appears in configured position
  - AC #2: Panel resizes within 20-60% range, main content adjusts accordingly
  - AC #3: All 4 positions implemented, preferences saved to localStorage
- Comprehensive test coverage: 1158 tests passing (67 test files)
- Lint passes with 0 errors (2 warnings for intentionally unused params that will be used in Epic 11)

### File List

**New Files:**
- frontend/src/components/ui/resizable.tsx (via shadcn)
- frontend/src/components/features/chat/QAPanel.tsx
- frontend/src/components/features/chat/QAPanel.test.tsx
- frontend/src/components/features/chat/QAPanelHeader.tsx
- frontend/src/components/features/chat/QAPanelHeader.test.tsx
- frontend/src/components/features/chat/QAPanelPlaceholder.tsx
- frontend/src/components/features/chat/QAPanelPlaceholder.test.tsx
- frontend/src/components/features/chat/FloatingQAPanel.tsx
- frontend/src/components/features/chat/FloatingQAPanel.test.tsx
- frontend/src/components/features/chat/QAPanelExpandButton.tsx
- frontend/src/components/features/chat/QAPanelExpandButton.test.tsx
- frontend/src/components/features/chat/index.ts
- frontend/src/components/features/matter/WorkspaceContentArea.tsx
- frontend/src/components/features/matter/WorkspaceContentArea.test.tsx
- frontend/src/stores/qaPanelStore.ts
- frontend/src/stores/qaPanelStore.test.ts

**Modified Files:**
- frontend/package.json (added react-resizable-panels dependency)
- frontend/src/app/(matter)/[matterId]/layout.tsx (integrated WorkspaceContentArea)
- frontend/src/components/features/matter/index.ts (added WorkspaceContentArea export)
- frontend/src/stores/index.ts (added qaPanelStore exports)

## Change Log

- 2026-01-15: Story implementation complete - Q&A Panel integration with 4 position modes, resizable panels, localStorage persistence, comprehensive tests (1158 passing)

