# Story 11.5: Implement PDF Viewer Split-View Mode

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to view documents alongside my workspace when I click a citation or source link**,
So that **I can reference sources while working without losing context**.

## Acceptance Criteria

1. **Given** I click a citation or source link (from Q&A panel, Citations tab, or other locations)
   **When** the split view opens
   **Then** the PDF viewer appears alongside the workspace content
   **And** the workspace is still visible and interactive

2. **Given** the split view is open
   **When** I view the document
   **Then** I see the document header with: filename, page number, total pages, expand button, close button

3. **Given** I navigate in the split view
   **When** I use prev/next or go to page
   **Then** the document navigates accordingly
   **And** the cited location remains visible initially

4. **Given** I click a source reference in a Q&A response
   **When** the PDF viewer opens
   **Then** the document automatically navigates to the cited page
   **And** the source text location is highlighted (if bounding boxes available)

5. **Given** I close the split view
   **When** I click the close button or press Escape
   **Then** the PDF viewer panel closes
   **And** the workspace returns to full width

## Tasks / Subtasks

- [x] Task 1: Create PDFSplitView container component (AC: #1, #2)
  - [x] 1.1: Create `PDFSplitView.tsx` in `frontend/src/components/features/pdf/`
  - [x] 1.2: Use existing `ResizablePanelGroup` from `ui/resizable.tsx` for horizontal layout
  - [x] 1.3: Left panel: Workspace content (children pass-through)
  - [x] 1.4: Right panel: PDF viewer with header controls
  - [x] 1.5: Implement 50/50 default split with min 30% per panel
  - [x] 1.6: Add panel resize handle with visual grip

- [x] Task 2: Create PDFSplitViewHeader component (AC: #2, #3)
  - [x] 2.1: Create `PDFSplitViewHeader.tsx` for PDF panel header
  - [x] 2.2: Display document filename (truncated if needed)
  - [x] 2.3: Display page number / total pages (via PdfViewerPanel)
  - [x] 2.4: Add expand button (opens Story 11.6 full modal - placeholder implemented)
  - [x] 2.5: Add close button with clear visual affordance

- [x] Task 3: Create usePdfSplitView store/hook (AC: #1, #4, #5)
  - [x] 3.1: Create `pdfSplitViewStore.ts` in `frontend/src/stores/`
  - [x] 3.2: Store state: isOpen, documentUrl, documentName, initialPage, boundingBoxes
  - [x] 3.3: Add openPdfSplitView(source: SourceReference) action
  - [x] 3.4: Add closePdfSplitView() action
  - [x] 3.5: Add selectors for optimized re-renders (per project-context.md)
  - [x] 3.6: Support matter_id for Supabase storage URL resolution

- [x] Task 4: Integrate PdfViewerPanel for document display (AC: #1, #3, #4)
  - [x] 4.1: Import existing `PdfViewerPanel` from `features/pdf/`
  - [x] 4.2: Pass initialPage from source reference
  - [x] 4.3: Configure controlled page/scale state
  - [x] 4.4: Handle page navigation callbacks
  - [x] 4.5: Pass bounding boxes when available for highlighting

- [x] Task 5: Update WorkspaceContentArea for split-view support (AC: #1)
  - [x] 5.1: Import PDFSplitView and pdfSplitViewStore
  - [x] 5.2: Conditionally render PDFSplitView when pdfSplitView.isOpen
  - [x] 5.3: Pass workspace content as children to split view
  - [x] 5.4: Ensure Q&A panel position modes work with split view
  - [x] 5.5: Handle edge case: both citation split-view and PDF split-view

- [x] Task 6: Wire onSourceClick from Q&A panel (AC: #4)
  - [x] 6.1: Update `WorkspaceContentArea` to provide onSourceClick handler
  - [x] 6.2: Handler should call `openPdfSplitView` with source data
  - [x] 6.3: Pass handler to QAPanel and FloatingQAPanel components
  - [x] 6.4: Handle document URL resolution from documentId + matterId
  - [x] 6.5: Implement getDocumentUrl API call via GET /api/documents/{documentId}

- [x] Task 7: Implement keyboard shortcuts (AC: #5)
  - [x] 7.1: Add Escape key handler to close split view
  - [x] 7.2: Arrow keys delegated to existing PdfViewerPanel
  - [x] 7.3: Keyboard focus management on open/close

- [x] Task 8: Write comprehensive tests (AC: All)
  - [x] 8.1: Test PDFSplitView renders with workspace content and PDF panel
  - [x] 8.2: Test header displays filename, expand/close buttons
  - [x] 8.3: Test clicking source reference opens split view with correct document
  - [x] 8.4: Test page navigation controls work correctly
  - [x] 8.5: Test close button and Escape key close the split view
  - [x] 8.6: Test resize handle allows panel resizing
  - [x] 8.7: Test split view works with Q&A panel in different positions
  - [x] 8.8: Test accessibility (ARIA labels, keyboard navigation)

## Dev Notes

### Existing Infrastructure to Leverage

This story builds heavily on existing PDF viewer infrastructure from Story 3-4:

| Component | Location | What It Provides |
|-----------|----------|------------------|
| `PdfViewerPanel` | `features/pdf/PdfViewerPanel.tsx` | Complete PDF rendering with PDF.js, page navigation, zoom controls, canvas-based rendering |
| `BboxOverlay` | `features/pdf/BboxOverlay.tsx` | Canvas overlay for bounding box highlights |
| `PdfErrorBoundary` | `features/pdf/PdfErrorBoundary.tsx` | Error boundary for graceful PDF error handling |
| `SplitViewCitationPanel` | `features/citation/SplitViewCitationPanel.tsx` | Reference implementation for resizable two-panel PDF layout |
| `splitViewStore` | `stores/splitViewStore.ts` | Reference for PDF viewer state management patterns |
| `ResizablePanelGroup` | `ui/resizable.tsx` | Pre-built resizable panel components (react-resizable-panels wrapper) |

### Key Differences from Citation Split-View

The **Citation Split-View** (Story 3-4) shows two PDFs side-by-side for verification. This **PDF Split-View** (Story 11.5) shows workspace + single PDF:

| Citation Split-View | PDF Split-View |
|---------------------|----------------|
| Two PDFs (source + Act) | Workspace + Single PDF |
| 50/50 horizontal split | Workspace left, PDF right |
| Both panels are PDF viewers | Left panel passes children |
| Triggered from Citations tab | Triggered from any source link |
| Uses citation context data | Uses source reference data |

### Source Reference Data Structure

From the chat types, source references have this structure:

```typescript
// frontend/src/types/chat.ts
interface SourceReference {
  documentId: string;      // UUID of the document
  documentName: string;    // Display name
  page: number;            // Page to navigate to
  chunkId: string;         // Chunk ID for potential bbox lookup
  confidence: number;      // Confidence score 0-100
}
```

### Document URL Resolution

To display the PDF, we need to convert `documentId` to a Supabase Storage URL:

```typescript
// Pattern from existing code
const getDocumentUrl = async (matterId: string, documentId: string): Promise<string> => {
  // Option 1: API endpoint (preferred for signed URLs)
  const response = await fetch(`/api/matters/${matterId}/documents/${documentId}/url`);
  const { data } = await response.json();
  return data.url;

  // Option 2: Direct Supabase Storage (if public bucket)
  // return `${SUPABASE_URL}/storage/v1/object/public/documents/${matterId}/${documentId}`;
};
```

**Check existing document service** for URL resolution patterns before implementing.

### Store Pattern

Create a dedicated store following the selector pattern from project-context.md:

```typescript
// frontend/src/stores/pdfSplitViewStore.ts

import { create } from 'zustand';
import type { SourceReference } from '@/types/chat';

interface PdfSplitViewState {
  isOpen: boolean;
  documentUrl: string | null;
  documentName: string | null;
  matterId: string | null;
  documentId: string | null;
  initialPage: number;
  boundingBoxes: Array<{ x: number; y: number; width: number; height: number }>;
  currentPage: number;
  scale: number;
}

interface PdfSplitViewActions {
  openPdfSplitView: (source: SourceReference, matterId: string, documentUrl: string) => void;
  closePdfSplitView: () => void;
  setCurrentPage: (page: number) => void;
  setScale: (scale: number) => void;
}

type PdfSplitViewStore = PdfSplitViewState & PdfSplitViewActions;

export const usePdfSplitViewStore = create<PdfSplitViewStore>()((set) => ({
  // Initial state
  isOpen: false,
  documentUrl: null,
  documentName: null,
  matterId: null,
  documentId: null,
  initialPage: 1,
  boundingBoxes: [],
  currentPage: 1,
  scale: 1.0,

  // Actions
  openPdfSplitView: (source, matterId, documentUrl) => {
    set({
      isOpen: true,
      documentUrl,
      documentName: source.documentName,
      matterId,
      documentId: source.documentId,
      initialPage: source.page,
      currentPage: source.page,
      boundingBoxes: [], // TODO: fetch from chunkId if available
      scale: 1.0,
    });
  },

  closePdfSplitView: () => {
    set({
      isOpen: false,
      documentUrl: null,
      documentName: null,
      matterId: null,
      documentId: null,
      initialPage: 1,
      boundingBoxes: [],
      currentPage: 1,
      scale: 1.0,
    });
  },

  setCurrentPage: (page) => set({ currentPage: page }),
  setScale: (scale) => set({ scale }),
}));

// Selectors for optimized re-renders
export const selectIsOpen = (state: PdfSplitViewStore) => state.isOpen;
export const selectDocumentUrl = (state: PdfSplitViewStore) => state.documentUrl;
export const selectDocumentName = (state: PdfSplitViewStore) => state.documentName;
export const selectCurrentPage = (state: PdfSplitViewStore) => state.currentPage;
export const selectScale = (state: PdfSplitViewStore) => state.scale;
export const selectInitialPage = (state: PdfSplitViewStore) => state.initialPage;
```

### PDFSplitView Component Pattern

```tsx
// frontend/src/components/features/pdf/PDFSplitView.tsx
'use client';

import { useEffect } from 'react';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { PdfViewerPanel } from './PdfViewerPanel';
import { PDFSplitViewHeader } from './PDFSplitViewHeader';
import { PdfErrorBoundary } from './PdfErrorBoundary';
import {
  usePdfSplitViewStore,
  selectIsOpen,
  selectDocumentUrl,
  selectDocumentName,
  selectCurrentPage,
  selectScale,
} from '@/stores/pdfSplitViewStore';

interface PDFSplitViewProps {
  /** Workspace content to display on the left */
  children: React.ReactNode;
}

export function PDFSplitView({ children }: PDFSplitViewProps) {
  const isOpen = usePdfSplitViewStore(selectIsOpen);
  const documentUrl = usePdfSplitViewStore(selectDocumentUrl);
  const documentName = usePdfSplitViewStore(selectDocumentName);
  const currentPage = usePdfSplitViewStore(selectCurrentPage);
  const scale = usePdfSplitViewStore(selectScale);
  const setCurrentPage = usePdfSplitViewStore((s) => s.setCurrentPage);
  const setScale = usePdfSplitViewStore((s) => s.setScale);
  const closePdfSplitView = usePdfSplitViewStore((s) => s.closePdfSplitView);

  // Keyboard handler for Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        closePdfSplitView();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, closePdfSplitView]);

  // If not open, just render children
  if (!isOpen || !documentUrl) {
    return <>{children}</>;
  }

  return (
    <ResizablePanelGroup direction="horizontal" className="h-full">
      {/* Workspace content */}
      <ResizablePanel defaultSize={50} minSize={30}>
        <div className="h-full overflow-auto">{children}</div>
      </ResizablePanel>

      <ResizableHandle withHandle aria-label="Resize PDF panel" />

      {/* PDF viewer panel */}
      <ResizablePanel defaultSize={50} minSize={30}>
        <div className="flex h-full flex-col border-l">
          <PDFSplitViewHeader
            documentName={documentName ?? 'Document'}
            onClose={closePdfSplitView}
            onExpand={() => {
              // Story 11.6: Open full modal
              // For now, could show toast or do nothing
            }}
          />
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
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
```

### PDFSplitViewHeader Component Pattern

```tsx
// frontend/src/components/features/pdf/PDFSplitViewHeader.tsx
'use client';

import { X, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface PDFSplitViewHeaderProps {
  documentName: string;
  onClose: () => void;
  onExpand: () => void;
}

export function PDFSplitViewHeader({
  documentName,
  onClose,
  onExpand,
}: PDFSplitViewHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-2">
      <span
        className="truncate text-sm font-medium"
        title={documentName}
      >
        {documentName}
      </span>

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onExpand}
          title="Full screen (F)"
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onClose}
          title="Close (Esc)"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
```

### WorkspaceContentArea Integration

The WorkspaceContentArea needs to:
1. Import and check `pdfSplitViewStore.isOpen`
2. Wrap content in PDFSplitView when source click handler is needed
3. Provide `onSourceClick` to QAPanel

```tsx
// In WorkspaceContentArea.tsx, add:
import { PDFSplitView } from '@/components/features/pdf/PDFSplitView';
import { usePdfSplitViewStore } from '@/stores/pdfSplitViewStore';
import type { SourceReference } from '@/types/chat';

// Handler for source clicks
const handleSourceClick = useCallback(async (source: SourceReference) => {
  if (!matterId) return;

  // Resolve document URL (implementation depends on your API)
  // Option 1: Direct Supabase URL
  // Option 2: API call to get signed URL
  const documentUrl = await getDocumentUrl(matterId, source.documentId);

  const openPdfSplitView = usePdfSplitViewStore.getState().openPdfSplitView;
  openPdfSplitView(source, matterId, documentUrl);
}, [matterId]);

// Wrap render in PDFSplitView
<PDFSplitView>
  {/* existing workspace content */}
</PDFSplitView>

// Pass handler to QAPanel
<QAPanel
  matterId={matterId}
  userId={userId}
  onSourceClick={handleSourceClick}
/>
```

### Project Structure Notes

**New Files:**
```
frontend/src/components/features/pdf/
├── PDFSplitView.tsx              # NEW - Split view container
├── PDFSplitViewHeader.tsx        # NEW - Header with controls
├── __tests__/
│   ├── PDFSplitView.test.tsx     # NEW - Component tests
│   └── PDFSplitViewHeader.test.tsx # NEW - Header tests

frontend/src/stores/
├── pdfSplitViewStore.ts          # NEW - Split view state management
├── __tests__/
│   └── pdfSplitViewStore.test.ts # NEW - Store tests
```

**Modified Files:**
```
frontend/src/components/features/pdf/
├── index.ts                      # UPDATE - Export new components

frontend/src/components/features/matter/
├── WorkspaceContentArea.tsx      # UPDATE - Add PDFSplitView wrapper

frontend/src/stores/
├── index.ts                      # UPDATE - Export pdfSplitViewStore
```

### Previous Story Intelligence (Story 11.4)

**Key Learnings:**
1. QAPanel accepts optional `onSourceClick` callback (already wired)
2. ConversationHistory has placeholder toast when `onSourceClick` not provided
3. Source references include `documentId`, `documentName`, `page`, `chunkId`
4. Chat component tests baseline: 160 passing

**From 11.4 Completion Notes:**
- Empty state SuggestedQuestions hides when streaming starts
- handleSubmit callback pattern already established
- All Zustand stores use selector pattern (MANDATORY)

### Git Commit Pattern

```
feat(pdf): implement PDF split-view for source references (Story 11.5)
```

### Testing Strategy

**Unit Tests (Store):**
```typescript
// pdfSplitViewStore.test.ts
describe('pdfSplitViewStore', () => {
  test('initial state has isOpen false', () => {
    const store = usePdfSplitViewStore.getState();
    expect(store.isOpen).toBe(false);
  });

  test('openPdfSplitView sets state correctly', () => {
    const source = {
      documentId: 'doc-1',
      documentName: 'Test.pdf',
      page: 5,
      chunkId: 'chunk-1',
      confidence: 85,
    };

    usePdfSplitViewStore.getState().openPdfSplitView(
      source,
      'matter-1',
      'https://example.com/doc.pdf'
    );

    const state = usePdfSplitViewStore.getState();
    expect(state.isOpen).toBe(true);
    expect(state.documentUrl).toBe('https://example.com/doc.pdf');
    expect(state.initialPage).toBe(5);
  });

  test('closePdfSplitView resets state', () => {
    // Open first, then close
    usePdfSplitViewStore.getState().openPdfSplitView(...);
    usePdfSplitViewStore.getState().closePdfSplitView();

    const state = usePdfSplitViewStore.getState();
    expect(state.isOpen).toBe(false);
    expect(state.documentUrl).toBeNull();
  });
});
```

**Component Tests:**
```typescript
// PDFSplitView.test.tsx
describe('PDFSplitView', () => {
  test('renders children when split view closed', () => {
    // Mock store with isOpen: false
    render(
      <PDFSplitView>
        <div>Workspace content</div>
      </PDFSplitView>
    );

    expect(screen.getByText('Workspace content')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /pdf/i })).not.toBeInTheDocument();
  });

  test('renders split view when open', () => {
    // Mock store with isOpen: true, documentUrl set
    render(
      <PDFSplitView>
        <div>Workspace content</div>
      </PDFSplitView>
    );

    expect(screen.getByText('Workspace content')).toBeInTheDocument();
    // PDF viewer should be visible
  });

  test('close button calls closePdfSplitView', async () => {
    // Mock store
    render(<PDFSplitView>...</PDFSplitView>);

    await userEvent.click(screen.getByRole('button', { name: /close/i }));

    expect(closePdfSplitView).toHaveBeenCalled();
  });

  test('Escape key closes split view', async () => {
    render(<PDFSplitView>...</PDFSplitView>);

    await userEvent.keyboard('{Escape}');

    expect(closePdfSplitView).toHaveBeenCalled();
  });
});
```

**Integration Tests:**
```typescript
// WorkspaceContentArea.test.tsx (add tests)
describe('WorkspaceContentArea PDF split view', () => {
  test('clicking source reference opens PDF split view', async () => {
    render(<WorkspaceContentArea matterId="test" userId="test">...</WorkspaceContentArea>);

    // Simulate source click from Q&A panel
    // Verify PDF split view opens with correct document
  });
});
```

### Testing Checklist

- [ ] PDF split view renders when store.isOpen is true
- [ ] Split view shows workspace content on left, PDF on right
- [ ] Header displays document name
- [ ] Close button closes split view
- [ ] Escape key closes split view
- [ ] Expand button exists (placeholder for Story 11.6)
- [ ] Resize handle allows panel resizing
- [ ] Page navigation works within PDF panel
- [ ] Clicking source in Q&A opens correct document at correct page
- [ ] Split view works with Q&A panel in right position
- [ ] Split view works with Q&A panel in bottom position
- [ ] Split view works with floating Q&A panel
- [ ] All frontend tests pass
- [ ] Lint passes with no errors

### Architecture Compliance Notes

From architecture.md and project-context.md:
- **Performance**: PDF.js renders only visible page + 1 buffer (already in PdfViewerPanel)
- **Bbox overlay**: Canvas-based, not DOM elements (already in BboxOverlay)
- **Zustand**: MUST use selector pattern, NEVER destructure entire store
- **TypeScript**: No `any` types, use `unknown` + type guards
- **React**: Server components by default, `'use client'` only when needed

### API/Backend Considerations

**Document URL Resolution:**
Check if endpoint exists: `GET /api/matters/{matterId}/documents/{documentId}/url`

If not, may need to:
1. Add endpoint to return signed Supabase Storage URL
2. Or use direct Supabase client in frontend (less secure)

**Bounding Box Lookup:**
Source references include `chunkId`. To show highlight:
1. Endpoint may exist: `GET /api/documents/{documentId}/chunks/{chunkId}/bboxes`
2. Or embed bbox in chunk data returned with search results

For MVP, bbox highlighting is optional - focus on PDF display + navigation.

### References

- [Source: epics.md#Story-11.5 - Acceptance Criteria]
- [Source: epics.md#FR27 - PDF Viewer requirements]
- [Source: project-context.md - Zustand selectors, testing rules, performance constraints]
- [Source: architecture.md#Performance - Virtualized PDF rendering, bbox as canvas]
- [Source: frontend/src/components/features/pdf/PdfViewerPanel.tsx - Existing PDF viewer]
- [Source: frontend/src/components/features/citation/SplitViewCitationPanel.tsx - Reference implementation]
- [Source: frontend/src/stores/splitViewStore.ts - Reference state management]
- [Source: frontend/src/components/features/chat/ConversationHistory.tsx:107 - onSourceClick handler]
- [Source: 11-4-suggested-questions-input.md - Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Store Implementation**: Created `pdfSplitViewStore.ts` following the mandatory selector pattern from project-context.md. Store manages isOpen, documentUrl, documentName, matterId, documentId, initialPage, currentPage, scale, boundingBoxes, and chunkId.

2. **Component Architecture**:
   - `PDFSplitView.tsx` - Container component that conditionally renders split view using ResizablePanelGroup
   - `PDFSplitViewHeader.tsx` - Header with document name, expand button (placeholder for Story 11.6), and close button

3. **WorkspaceContentArea Integration**: Updated to wrap all position modes (right, bottom, float, hidden) with PDFSplitView component. Added handleSourceClick callback that fetches document signed URL via `GET /api/documents/{documentId}` and opens the split view.

4. **Document URL Resolution**: Uses existing backend endpoint `GET /api/documents/{documentId}` which returns `storage_path` as a signed Supabase URL (1-hour expiry).

5. **Keyboard Support**: Escape key closes split view via document-level keydown listener with proper cleanup.

6. **Test Coverage**: 56 tests covering store state management, selectors, component rendering, user interactions, and accessibility.

7. **Expand Button**: Placeholder implemented showing toast "Full screen view coming soon" - will be implemented in Story 11.6.

### File List

**New Files:**
- `frontend/src/stores/pdfSplitViewStore.ts` - Zustand store for PDF split view state
- `frontend/src/stores/pdfSplitViewStore.test.ts` - Store tests (32 tests)
- `frontend/src/components/features/pdf/PDFSplitView.tsx` - Split view container component
- `frontend/src/components/features/pdf/PDFSplitView.test.tsx` - Component tests (16 tests)
- `frontend/src/components/features/pdf/PDFSplitViewHeader.tsx` - Header component
- `frontend/src/components/features/pdf/PDFSplitViewHeader.test.tsx` - Header tests (8 tests)

**Modified Files:**
- `frontend/src/components/features/pdf/index.ts` - Added exports for new components
- `frontend/src/components/features/matter/WorkspaceContentArea.tsx` - Added PDFSplitView wrapper and onSourceClick handler
- `frontend/src/stores/index.ts` - Added pdfSplitViewStore exports

