# Story 11.6: Implement PDF Viewer Full Modal Mode

Status: complete

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to expand the PDF viewer to full screen**,
So that **I can examine documents in detail**.

## Acceptance Criteria

1. **Given** the split view is open
   **When** I click the expand button
   **Then** the PDF viewer opens as a full modal
   **And** the workspace is hidden behind it

2. **Given** the full modal is open
   **When** I view the document
   **Then** I have full navigation controls: prev/next, go to page input
   **And** zoom controls: zoom in, zoom out, fit to width, fit to page

3. **Given** I click close or press Escape
   **When** the modal closes
   **Then** I return to the workspace
   **And** the previous state is preserved

## Tasks / Subtasks

- [x] Task 1: Create PDFFullScreenModal component (AC: #1, #2)
  - [x] 1.1: Create `PDFFullScreenModal.tsx` in `frontend/src/components/features/pdf/`
  - [x] 1.2: Use Dialog/Sheet from shadcn for modal overlay (full viewport coverage)
  - [x] 1.3: Add header bar with document name, page info, close button
  - [x] 1.4: Reuse `PdfViewerPanel` for PDF rendering with full navigation/zoom controls
  - [x] 1.5: Apply dark overlay behind modal (workspace hidden)

- [x] Task 2: Extend pdfSplitViewStore for modal state (AC: #1, #3)
  - [x] 2.1: Add `isFullScreenOpen: boolean` state to store
  - [x] 2.2: Add `openFullScreenModal()` action
  - [x] 2.3: Add `closeFullScreenModal()` action
  - [x] 2.4: Ensure closing modal preserves split-view state (returns to split view)
  - [x] 2.5: Add selectors for modal state

- [x] Task 3: Wire expand button in PDFSplitViewHeader (AC: #1)
  - [x] 3.1: Update `PDFSplitView.handleExpand` to call `openFullScreenModal()`
  - [x] 3.2: Remove placeholder toast message
  - [x] 3.3: Render `PDFFullScreenModal` when `isFullScreenOpen` is true

- [x] Task 4: Implement keyboard shortcuts (AC: #3)
  - [x] 4.1: Escape key closes modal (with priority over split-view Escape)
  - [x] 4.2: Arrow left/right for page navigation
  - [x] 4.3: +/- for zoom in/out
  - [x] 4.4: F key to toggle full screen from split view

- [x] Task 5: Add Fit to Page zoom preset (AC: #2)
  - [x] 5.1: Calculate scale to fit page in viewport
  - [x] 5.2: Add "Fit to Page" button alongside existing zoom controls
  - [x] 5.3: Update PdfViewerPanel to support fit-to-page calculation via callback

- [x] Task 6: Write comprehensive tests (AC: All)
  - [x] 6.1: Test clicking expand button opens full screen modal
  - [x] 6.2: Test modal displays document with navigation controls
  - [x] 6.3: Test zoom controls (zoom in, zoom out, fit to width, fit to page)
  - [x] 6.4: Test close button closes modal and returns to split view
  - [x] 6.5: Test Escape key closes modal
  - [x] 6.6: Test keyboard shortcuts for navigation and zoom
  - [x] 6.7: Test page state preserved when closing modal
  - [x] 6.8: Test accessibility (ARIA labels, keyboard focus management)

## Dev Notes

### Existing Infrastructure to Leverage

This story extends the PDF split-view infrastructure created in Story 11.5:

| Component | Location | What It Provides |
|-----------|----------|------------------|
| `PdfViewerPanel` | `features/pdf/PdfViewerPanel.tsx` | Complete PDF rendering with PDF.js, page navigation, zoom controls |
| `PDFSplitView` | `features/pdf/PDFSplitView.tsx` | Split-view container with expand button |
| `PDFSplitViewHeader` | `features/pdf/PDFSplitViewHeader.tsx` | Header with expand/close buttons (expand triggers this story) |
| `pdfSplitViewStore` | `stores/pdfSplitViewStore.ts` | State management for document URL, page, scale |
| `PdfErrorBoundary` | `features/pdf/PdfErrorBoundary.tsx` | Error boundary for graceful PDF error handling |
| `Dialog` | `ui/dialog.tsx` | shadcn modal component |

### Key Implementation Pattern

The full modal should reuse the same PDF viewer state from split view:

```
Split View (Story 11.5)
  │
  │ Click Expand Button
  ▼
Full Modal (Story 11.6)
  │
  │ - Same documentUrl, currentPage, scale
  │ - Larger viewport for detailed viewing
  │ - Close returns to split view (not to workspace)
  │
  │ Close Modal
  ▼
Split View (preserved state)
```

### Store Pattern Extension

Extend `pdfSplitViewStore.ts` to track modal state:

```typescript
// Add to existing store state
interface PdfSplitViewState {
  // Existing...
  isOpen: boolean;
  documentUrl: string | null;
  currentPage: number;
  // ...

  // NEW for Story 11.6
  isFullScreenOpen: boolean;
}

// Add to existing actions
interface PdfSplitViewActions {
  // Existing...
  openPdfSplitView: (...) => void;
  closePdfSplitView: () => void;

  // NEW for Story 11.6
  openFullScreenModal: () => void;
  closeFullScreenModal: () => void;
}
```

### PDFFullScreenModal Component Pattern

```tsx
// frontend/src/components/features/pdf/PDFFullScreenModal.tsx
'use client';

import { useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
} from '@/components/ui/dialog';
import { PdfViewerPanel } from './PdfViewerPanel';
import { PdfErrorBoundary } from './PdfErrorBoundary';
import {
  usePdfSplitViewStore,
  selectIsFullScreenOpen,
  selectPdfDocumentUrl,
  selectPdfDocumentName,
  selectPdfCurrentPage,
  selectPdfTotalPages,
  selectPdfScale,
} from '@/stores/pdfSplitViewStore';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

export function PDFFullScreenModal() {
  const isOpen = usePdfSplitViewStore(selectIsFullScreenOpen);
  const documentUrl = usePdfSplitViewStore(selectPdfDocumentUrl);
  const documentName = usePdfSplitViewStore(selectPdfDocumentName);
  const currentPage = usePdfSplitViewStore(selectPdfCurrentPage);
  const totalPages = usePdfSplitViewStore(selectPdfTotalPages);
  const scale = usePdfSplitViewStore(selectPdfScale);

  const setCurrentPage = usePdfSplitViewStore((s) => s.setCurrentPage);
  const setScale = usePdfSplitViewStore((s) => s.setScale);
  const closeFullScreenModal = usePdfSplitViewStore((s) => s.closeFullScreenModal);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeFullScreenModal();
        return;
      }

      // Page navigation
      if (e.key === 'ArrowLeft' && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else if (e.key === 'ArrowRight' && currentPage < totalPages) {
        setCurrentPage(currentPage + 1);
      }

      // Zoom shortcuts
      if (e.key === '+' || e.key === '=') {
        setScale(Math.min(scale + 0.25, 3.0));
      } else if (e.key === '-') {
        setScale(Math.max(scale - 0.25, 0.5));
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentPage, totalPages, scale, setCurrentPage, setScale, closeFullScreenModal]);

  if (!isOpen || !documentUrl) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && closeFullScreenModal()}>
      <DialogContent className="max-w-[95vw] h-[95vh] p-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b">
          <span className="font-medium">{documentName}</span>
          <span className="text-sm text-muted-foreground">
            {currentPage} / {totalPages}
          </span>
          <Button variant="ghost" size="icon" onClick={closeFullScreenModal}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* PDF Viewer */}
        <div className="flex-1 overflow-hidden">
          <PdfErrorBoundary>
            <PdfViewerPanel
              documentUrl={documentUrl}
              currentPage={currentPage}
              scale={scale}
              onPageChange={setCurrentPage}
              onScaleChange={setScale}
              panelTitle={documentName ?? 'Document'}
            />
          </PdfErrorBoundary>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

### Integration with PDFSplitView

Update `PDFSplitView.tsx` to render the full screen modal:

```tsx
// In PDFSplitView.tsx

import { PDFFullScreenModal } from './PDFFullScreenModal';

// Update handleExpand
const handleExpand = useCallback(() => {
  const openFullScreenModal = usePdfSplitViewStore.getState().openFullScreenModal;
  openFullScreenModal();
}, []);

// Add modal render at the end
return (
  <>
    <ResizablePanelGroup ...>
      {/* existing split view content */}
    </ResizablePanelGroup>

    {/* Full screen modal - renders via portal above everything */}
    <PDFFullScreenModal />
  </>
);
```

### Project Structure Notes

**New Files:**
```
frontend/src/components/features/pdf/
├── PDFFullScreenModal.tsx           # NEW - Full screen modal component
├── PDFFullScreenModal.test.tsx      # NEW - Modal tests
```

**Modified Files:**
```
frontend/src/stores/
├── pdfSplitViewStore.ts             # UPDATE - Add isFullScreenOpen, openFullScreenModal, closeFullScreenModal
├── pdfSplitViewStore.test.ts        # UPDATE - Add tests for new state/actions

frontend/src/components/features/pdf/
├── PDFSplitView.tsx                 # UPDATE - Wire expand to openFullScreenModal, render modal
├── PDFSplitView.test.tsx            # UPDATE - Add tests for modal integration
├── index.ts                         # UPDATE - Export PDFFullScreenModal
```

### Previous Story Intelligence (Story 11.5)

**Key Patterns Established:**
1. Zustand store uses mandatory selector pattern - NEVER destructure entire store
2. `PdfViewerPanel` accepts controlled page/scale via props with callbacks
3. Keyboard shortcuts handled via `useEffect` with proper cleanup
4. Toast notifications from sonner library
5. Current split-view state is fully preserved in store

**From 11.5 Completion Notes:**
- `handleExpand` currently shows toast "Full screen mode will be available in Story 11.6"
- Store already has all necessary document state (URL, name, page, scale, totalPages)
- `PdfViewerPanel.onTotalPagesChange` callback populates totalPages in store
- All tests use Zustand store mocking pattern

### Architecture Compliance Notes

From architecture.md and project-context.md:
- **TypeScript**: No `any` types, use `unknown` + type guards
- **Zustand**: MUST use selector pattern, NEVER destructure entire store
- **React**: Server components by default, `'use client'` only when needed (needed here)
- **Testing**: Co-locate test files with components
- **Accessibility**: Include ARIA labels for screen readers, keyboard navigation

### Dialog Component Usage

The shadcn Dialog component wraps Radix UI Dialog:

```tsx
// From ui/dialog.tsx
import * as DialogPrimitive from "@radix-ui/react-dialog"

// Key components:
// - Dialog: Root wrapper with controlled open state
// - DialogContent: Portal-rendered modal content
// - DialogHeader: Optional header section
// - DialogTitle: Modal title (required for accessibility)
// - DialogDescription: Optional description

// For full-screen modal, customize DialogContent:
<DialogContent className="max-w-[95vw] h-[95vh] p-0 overflow-hidden">
```

### Testing Strategy

**Unit Tests (Store):**
```typescript
// pdfSplitViewStore.test.ts additions
describe('full screen modal state', () => {
  test('initial state has isFullScreenOpen false', () => {
    const store = usePdfSplitViewStore.getState();
    expect(store.isFullScreenOpen).toBe(false);
  });

  test('openFullScreenModal sets isFullScreenOpen true', () => {
    // Must be in split view first
    usePdfSplitViewStore.getState().openPdfSplitView(mockSource, 'matter-1', 'url');
    usePdfSplitViewStore.getState().openFullScreenModal();

    expect(usePdfSplitViewStore.getState().isFullScreenOpen).toBe(true);
  });

  test('closeFullScreenModal preserves split view state', () => {
    // Open split view
    usePdfSplitViewStore.getState().openPdfSplitView(mockSource, 'matter-1', 'url');
    // Open full screen
    usePdfSplitViewStore.getState().openFullScreenModal();
    // Close full screen
    usePdfSplitViewStore.getState().closeFullScreenModal();

    const state = usePdfSplitViewStore.getState();
    expect(state.isFullScreenOpen).toBe(false);
    expect(state.isOpen).toBe(true); // Split view still open
    expect(state.documentUrl).toBe('url');
  });
});
```

**Component Tests:**
```typescript
// PDFFullScreenModal.test.tsx
describe('PDFFullScreenModal', () => {
  test('renders modal when isFullScreenOpen is true', () => {
    // Mock store with isFullScreenOpen: true
    render(<PDFFullScreenModal />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('does not render when isFullScreenOpen is false', () => {
    // Mock store with isFullScreenOpen: false
    render(<PDFFullScreenModal />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('close button calls closeFullScreenModal', async () => {
    render(<PDFFullScreenModal />);
    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(mockCloseFullScreenModal).toHaveBeenCalled();
  });

  test('Escape key closes modal', async () => {
    render(<PDFFullScreenModal />);
    await userEvent.keyboard('{Escape}');
    expect(mockCloseFullScreenModal).toHaveBeenCalled();
  });

  test('Arrow keys navigate pages', async () => {
    // Setup: currentPage=2, totalPages=10
    render(<PDFFullScreenModal />);
    await userEvent.keyboard('{ArrowRight}');
    expect(mockSetCurrentPage).toHaveBeenCalledWith(3);
  });

  test('+/- keys change zoom', async () => {
    // Setup: scale=1.0
    render(<PDFFullScreenModal />);
    await userEvent.keyboard('+');
    expect(mockSetScale).toHaveBeenCalledWith(1.25);
  });
});
```

### Testing Checklist

- [ ] Store initializes with isFullScreenOpen: false
- [ ] openFullScreenModal sets isFullScreenOpen: true
- [ ] closeFullScreenModal sets isFullScreenOpen: false
- [ ] Closing modal preserves split view isOpen: true
- [ ] Closing modal preserves documentUrl, currentPage, scale
- [ ] Modal renders full viewport dialog (95vw x 95vh)
- [ ] Modal displays document name in header
- [ ] Modal displays page X / Y in header
- [ ] Close button closes modal
- [ ] Escape key closes modal
- [ ] Arrow left/right navigates pages
- [ ] +/- keys adjust zoom
- [ ] PDF content renders correctly in modal
- [ ] Zoom controls work (zoom in, out, fit to width, fit to page)
- [ ] Page navigation works (prev, next, go to page)
- [ ] After closing modal, split view shows same page/zoom
- [ ] All frontend tests pass
- [ ] Lint passes with no errors

### References

- [Source: epics.md#Story-11.6 - Acceptance Criteria]
- [Source: epics.md#FR27 - PDF Viewer requirements]
- [Source: project-context.md - Zustand selectors, testing rules]
- [Source: architecture.md#Performance - Virtualized PDF rendering]
- [Source: frontend/src/components/features/pdf/PdfViewerPanel.tsx - Existing PDF viewer]
- [Source: frontend/src/stores/pdfSplitViewStore.ts - Existing store to extend]
- [Source: frontend/src/components/features/pdf/PDFSplitView.tsx - Integration point]
- [Source: frontend/src/components/ui/dialog.tsx - shadcn Dialog component]
- [Source: 11-5-pdf-viewer-split-view.md - Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation completed without issues.

### Completion Notes List

- All 6 tasks completed successfully
- 90 tests passing (44 store tests, 21 split view tests, 25 full screen modal tests)
- Build succeeds with no errors in new files
- All acceptance criteria met:
  - AC #1: Clicking expand button opens PDF viewer as full modal (95vh x 95vw)
  - AC #2: Full navigation controls (prev/next, page input) and zoom controls (zoom in/out, fit to width, fit to page)
  - AC #3: Close button and Escape key close modal and return to split view with preserved state
- Keyboard shortcuts implemented: Escape (close), Arrow left/right (page navigation), +/- (zoom), F (open full screen from split view)
- Fit to Page zoom preset added that calculates scale to fit entire page in viewport

### File List

**New Files:**
- `frontend/src/components/features/pdf/PDFFullScreenModal.tsx` - Full screen modal component
- `frontend/src/components/features/pdf/PDFFullScreenModal.test.tsx` - 25 modal tests

**Modified Files:**
- `frontend/src/stores/pdfSplitViewStore.ts` - Added isFullScreenOpen state, openFullScreenModal/closeFullScreenModal actions, selectIsFullScreenOpen selector
- `frontend/src/stores/pdfSplitViewStore.test.ts` - Added 15 new tests for full screen modal state
- `frontend/src/components/features/pdf/PDFSplitView.tsx` - Wired expand button to openFullScreenModal, render PDFFullScreenModal
- `frontend/src/components/features/pdf/PDFSplitView.test.tsx` - Updated tests for full screen modal integration, added F key shortcut tests
- `frontend/src/components/features/pdf/PdfViewerPanel.tsx` - Added Fit to Page zoom button and handleFitToPage calculation
- `frontend/src/components/features/pdf/index.ts` - Export PDFFullScreenModal

---

## Senior Developer Review (AI)

**Reviewed by:** Claude Opus 4.5 (claude-opus-4-5-20251101)
**Date:** 2026-01-16
**Outcome:** Changes Requested → Fixed

### Issues Found and Fixed

| Severity | Issue | Fix Applied |
|----------|-------|-------------|
| HIGH | Test count breakdown in Completion Notes was incorrect (claimed 45/30/15, actual 44/21/25) | Updated to correct counts |
| MEDIUM | "Fit to Width" button just reset scale to 100% instead of fitting page width | Implemented `handleFitToWidth` function that calculates scale to fit page width in viewport |
| MEDIUM | Missing DialogDescription for screen reader accessibility | Added sr-only DialogDescription with keyboard shortcut instructions |
| LOW | Page input had no hint about pressing Enter to navigate | Added `title="Enter page number and press Enter"` |
| LOW | F key shortcut not discoverable | Already had `title="Open full screen (F)"` on expand button ✓ |

### Verification
- All 90 tests pass (44 store + 21 split view + 25 modal)
- Lint passes with no errors on modified files
- All ACs verified as implemented

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-16 | Code review fixes: Fit to Width now calculates proper scale, added DialogDescription, added page input hint, corrected test counts | Claude Opus 4.5 |

