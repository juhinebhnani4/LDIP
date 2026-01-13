# Story 3.4: Implement Split-View Citation Highlighting

Status: completed

## Story

As an **attorney**,
I want **to see the case document and Act side-by-side with citations highlighted**,
So that **I can visually verify the citation accuracy**.

## Acceptance Criteria

1. **Given** I click on a citation in the Citations tab **When** the split view opens **Then** the left panel shows the case document at the citation location **And** the right panel shows the Act document at the referenced section **And** both locations are highlighted with bounding boxes

2. **Given** the split view is open **When** I view the citation **Then** the case document highlights the citation text in yellow **And** the Act document highlights the referenced section in blue

3. **Given** a citation has a mismatch **When** I view it in split view **Then** the differing text is highlighted in red **And** the explanation appears above the panels

4. **Given** an Act is not available **When** I click the citation **Then** only the case document panel is shown **And** a message indicates "Act not uploaded"

5. **Given** the split view is open **When** I navigate within either panel **Then** I can scroll/zoom independently **And** use prev/next page controls

6. **Given** I want to expand the view **When** I click the expand button **Then** the split view expands to full modal mode **And** I can close it to return to split view

## Tasks / Subtasks

- [x] Task 1: Create Split-View Container Component (AC: #1, #4, #5)
  - [x] Create `frontend/src/components/features/citation/SplitViewCitationPanel.tsx`
    - Implement resizable split panel layout (left: source, right: target)
    - Use react-resizable-panels for adjustable divider
    - Handle single-panel mode when Act unavailable
    - Include close button and expand button in header
    - Show citation summary bar at top (Act name, Section, Status)
  - [x] Create `frontend/src/components/features/citation/SplitViewHeader.tsx`
    - Display: citation text, act name, section number, verification status
    - Show explanation for mismatches in collapsible alert
    - Include action buttons: expand, close, navigate prev/next citation
  - [x] Create `frontend/src/hooks/useSplitView.ts`
    - Manage split view open/close state
    - Track current citation being viewed
    - Handle keyboard shortcuts (Escape to close, arrows for prev/next)

- [x] Task 2: Create PDF Viewer Wrapper Component (AC: #1, #2, #5)
  - [x] Create `frontend/src/components/features/pdf/PdfViewerPanel.tsx`
    - Wrap PDF.js viewer for split-view context
    - Props: documentId, pageNumber, bboxIds, highlightColor
    - Handle scroll position sync with page changes
    - Include page navigation controls (prev/next, page input)
    - Include zoom controls (+/-, fit-width, fit-page)
    - Support loading states and error handling
  - [x] Create `frontend/src/components/features/pdf/BboxOverlay.tsx`
    - Render bounding box highlights on PDF canvas
    - Support multiple highlight colors: yellow (source), blue (target), red (mismatch)
    - Calculate overlay positions based on normalized bbox coordinates
    - Handle page scale changes for accurate positioning
    - Use canvas overlay (NOT DOM elements) for performance per project-context.md

- [x] Task 3: Create Highlight Rendering System (AC: #2, #3)
  - [x] Create `frontend/src/lib/pdf/highlightUtils.ts`
    - Function: `calculateBboxPosition(bbox: BoundingBox, pageWidth: number, pageHeight: number, scale: number) -> CanvasRect`
    - Function: `renderBboxHighlight(ctx: CanvasRenderingContext2D, rect: CanvasRect, color: string, opacity: number)`
    - Function: `getBboxColor(status: VerificationStatus, isSource: boolean) -> string`
      - Source citation: yellow (#FDE047)
      - Target verified: blue (#3B82F6)
      - Target mismatch: red (#EF4444)
      - Target section_not_found: orange (#F97316)
  - [x] Create `frontend/src/types/pdf.ts`
    - Interface: `BoundingBox { id: string; x: number; y: number; width: number; height: number }`
    - Interface: `CanvasRect { x: number; y: number; width: number; height: number }`
    - Interface: `PdfViewerState { currentPage: number; scale: number; scrollPosition: { x: number; y: number } }`

- [x] Task 4: Create Split-View API Integration (AC: #1, #4)
  - [x] Update `frontend/src/lib/api/citations.ts`
    - Function: `getCitationSplitViewData(matterId: string, citationId: string): Promise<SplitViewData>`
      - Returns: source document URL, source page, source bboxIds
      - Returns: target document URL, target page, target bboxIds (if available)
      - Returns: verification result with explanation
  - [x] Update `frontend/src/types/citation.ts`
    - Interface: `SplitViewData`:
      - `citation: Citation`
      - `sourceDocument: { url: string; page: number; bboxIds: string[] }`
      - `targetDocument: { url: string; page: number; bboxIds: string[] } | null`
      - `verification: VerificationResult | null`
  - Note: Bounding box API not needed as coordinates returned in split-view response

- [x] Task 5: Create Backend Split-View Endpoint (AC: #1, #4)
  - [x] Added to `backend/app/api/routes/citations.py`
    - `GET /api/matters/{matter_id}/citations/{citation_id}/split-view`
      - Returns all data needed for split view rendering
      - Include source document URL, page, bbox coordinates
      - Include target document URL, page, bbox coordinates (if Act uploaded)
      - Include verification result and explanation
      - Validate matter access via require_matter_role dependency
  - [x] Uses existing services:
    - `storage_service.get_storage_service()` for signed URLs
    - `bounding_box_service.get_bounding_box_service()` for bbox coordinates
  - [x] Response schema `SplitViewResponseModel` defined inline with:
    - `source_document: DocumentViewDataModel`
    - `target_document: DocumentViewDataModel | None`
    - `verification: VerificationResultModel | None`
    - `citation: CitationModel`

- [x] Task 6: Integrate with Citations Tab (AC: #1)
  - [x] Create `frontend/src/components/features/citation/CitationsList.tsx`
    - Add "View" button/icon on each citation row
    - On click, open SplitViewCitationPanel with citation data
    - Handle loading state while fetching split view data
  - [x] Create `frontend/src/components/features/citation/CitationsTab.tsx`
    - Add split view panel container (rendered conditionally)
    - Manage split view state via useSplitView hook

- [x] Task 7: Implement Mismatch Highlighting (AC: #3)
  - [x] Create `frontend/src/components/features/citation/MismatchExplanation.tsx`
    - Display diff details from VerificationResult
    - Show citation text vs Act text side-by-side
    - Highlight specific differences inline
    - Collapsible panel above split view when mismatch detected
  - Note: Diff highlight utilities integrated into highlightUtils.ts and BboxOverlay

- [x] Task 8: Implement Full Modal Mode (AC: #6)
  - [x] Create `frontend/src/components/features/citation/SplitViewModal.tsx`
    - Full-screen modal wrapper for split view
    - Reuse SplitViewCitationPanel at larger size
    - Keyboard shortcuts: Escape to close
  - [x] Update `frontend/src/hooks/useSplitView.ts`
    - Add `isFullScreen` state
    - Add `toggleFullScreen()` action
    - Persist scroll positions when toggling modes

- [x] Task 9: Create Zustand Store for Split View State (AC: #5, #6)
  - [x] Create `frontend/src/stores/splitViewStore.ts`
    - State: `isOpen: boolean`
    - State: `isFullScreen: boolean`
    - State: `currentCitationId: string | null`
    - State: `sourceViewState: PdfViewerState`
    - State: `targetViewState: PdfViewerState`
    - Actions: `openSplitView(citationId)`, `closeSplitView()`, `toggleFullScreen()`
    - Actions: `setSourcePage(page)`, `setTargetPage(page)`, `setZoom(scale)`
    - Use selectors pattern per project-context.md

- [x] Task 10: Write Frontend Unit Tests
  - [x] Create `frontend/src/components/features/citation/SplitViewHeader.test.tsx`
    - Test rendering citation info
    - Test status badges
    - Test mismatch explanation
    - Test navigation buttons
  - [x] Create `frontend/src/lib/pdf/highlightUtils.test.ts`
    - Test position calculations (18 tests across 4 describe blocks)
    - Test color utilities
    - Test bbox rendering
  - [x] Create `frontend/src/stores/splitViewStore.test.ts`
    - Test store actions and state

- [x] Task 11: Write Backend Unit Tests
  - [x] Create `backend/tests/api/test_citations_split_view.py`
    - Test GET split-view endpoint returns correct structure
    - Test 404 when citation not found
    - Test handling when Act not uploaded (targetDocument null)
    - Test authentication required

- [x] Task 12: Write Integration Tests
  - [x] Backend API tests cover integration scenarios:
    - Test split-view returns source and target data
    - Test single panel when Act unavailable
    - Test authentication requirements

## Dev Notes

### CRITICAL: Architecture Requirements

**From [architecture.md](../_bmad-output/architecture.md):**

Split-View Citation Highlighting is the final stage of the Citation Engine flow:

```
CITATION EXTRACTION (Story 3-1) ✅
  |
  v
ACT DISCOVERY REPORT (Story 3-2) ✅
  |
  v
CITATION VERIFICATION (Story 3-3) ✅
  |
  v
SPLIT-VIEW HIGHLIGHTING (THIS STORY)
  | Display side-by-side:
  |   * Left: Case document with citation highlighted
  |   * Right: Act document with section highlighted
  |   * Color-coded status: verified (blue), mismatch (red)
  v
ATTORNEY VERIFICATION
```

### Previous Story Intelligence

#### Story 3-3: Citation Verification
**Key patterns from [3-3-citation-verification.md](3-3-citation-verification.md):**

1. **Verification Result Structure (Already exists):**
   ```python
   class VerificationResult:
       status: VerificationStatus
       section_found: bool
       section_text: str | None
       target_page: int | None        # <-- Use for right panel
       target_bbox_ids: list[str]     # <-- Use for right panel highlighting
       similarity_score: float
       explanation: str
       diff_details: DiffDetail | None  # <-- Use for mismatch highlighting
   ```

2. **Citation Model Fields (Already exists):**
   ```python
   class Citation:
       source_page: int              # <-- Use for left panel
       source_bbox_ids: list[str]    # <-- Use for left panel highlighting
       target_act_document_id: str | None
       target_page: int | None
       target_bbox_ids: list[str]
       verification_status: VerificationStatus
   ```

3. **Frontend Types (Already exists in `types/citation.ts`):**
   ```typescript
   interface Citation {
     sourcePage: number;
     sourceBboxIds: string[];
     targetActDocumentId: string | null;
     targetPage: number | null;
     targetBboxIds: string[];
     verificationStatus: VerificationStatus;
   }

   interface VerificationResult {
     status: VerificationStatus;
     targetPage: number | null;
     targetBboxIds: string[];
     diffDetails: DiffDetail | null;
   }

   interface DiffDetail {
     citationText: string;
     actText: string;
     matchType: 'exact' | 'paraphrase' | 'mismatch';
     differences: string[];
   }
   ```

### Git Intelligence

Recent commits:
```
01c0313 feat(citation): implement citation verification against Act text (Story 3-3)
eb10100 feat(citation): implement Act Discovery Report UI (Story 3-2)
d543898 feat(citation): implement Act citation extraction from case files (Story 3-1)
```

**Recommended commit message:** `feat(citation): implement split-view citation highlighting (Story 3-4)`

### Performance Requirements (CRITICAL)

**From [project-context.md](../_bmad-output/project-context.md):**

```
### Performance Gotchas

- **Virtualize PDF rendering** - Only visible pages + 1 buffer
- **Bbox overlay as canvas** - Not 500 DOM elements
- **Lazy load tabs** - Active tab only on mount
- **Client-side cache** - Tab data in Zustand store
```

**Implementation requirements:**
1. Use `<canvas>` for bbox overlays, NOT individual DOM elements
2. Only render visible page + 1 page buffer
3. Cache split view data in Zustand store
4. Lazy load PDF.js library

### PDF Viewer Implementation

**Library: PDF.js (pdfjs-dist)**

```typescript
// PDF.js setup
import * as pdfjs from 'pdfjs-dist';
import 'pdfjs-dist/build/pdf.worker.entry';

// Configure worker
pdfjs.GlobalWorkerOptions.workerSrc =
  `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;
```

**Bounding Box Coordinate System:**
- Coordinates are normalized (0-1 range) from Google Document AI
- Must scale to actual page dimensions
- Account for PDF.js viewport scaling

```typescript
// Coordinate transformation
function transformBbox(
  bbox: BoundingBox,
  viewport: pdfjs.PageViewport
): CanvasRect {
  const { x, y, width, height } = bbox;
  return {
    x: x * viewport.width,
    y: y * viewport.height,
    width: width * viewport.width,
    height: height * viewport.height
  };
}
```

### Color Scheme for Highlights

| Status | Location | Color | Hex |
|--------|----------|-------|-----|
| Source citation | Left panel | Yellow | #FDE047 (bg) / #CA8A04 (border) |
| Verified section | Right panel | Blue | #BFDBFE (bg) / #3B82F6 (border) |
| Mismatch | Right panel | Red | #FECACA (bg) / #EF4444 (border) |
| Section not found | Right panel | Orange | #FED7AA (bg) / #F97316 (border) |
| Act unavailable | N/A | Gray message | N/A |

### API Response Format (MANDATORY)

```python
# GET /api/matters/{matter_id}/citations/{citation_id}/split-view
{
  "data": {
    "citation": {
      "id": "uuid",
      "act_name": "Negotiable Instruments Act, 1881",
      "section_number": "138",
      "raw_citation_text": "Section 138 of NI Act...",
      "verification_status": "verified"
    },
    "source_document": {
      "document_id": "uuid",
      "document_url": "https://storage.supabase.co/...",
      "page_number": 45,
      "bounding_boxes": [
        {"bbox_id": "uuid", "x": 0.1, "y": 0.3, "width": 0.4, "height": 0.05, "text": "Section 138..."}
      ]
    },
    "target_document": {
      "document_id": "uuid",
      "document_url": "https://storage.supabase.co/...",
      "page_number": 89,
      "bounding_boxes": [
        {"bbox_id": "uuid", "x": 0.1, "y": 0.2, "width": 0.8, "height": 0.15, "text": "138. Dishonour of cheque..."}
      ]
    },
    "verification": {
      "status": "verified",
      "section_found": true,
      "similarity_score": 98.5,
      "explanation": "Section 138 verified. Quoted text matches Act text.",
      "diff_details": null
    }
  }
}

# When Act not uploaded
{
  "data": {
    "citation": {...},
    "source_document": {...},
    "target_document": null,  # <-- Null when Act unavailable
    "verification": null
  }
}
```

### Component Architecture

```
SplitViewCitationPanel
├── SplitViewHeader
│   ├── Citation summary (Act, Section, Status)
│   ├── MismatchExplanation (if applicable)
│   └── Action buttons (expand, close, prev/next)
├── SplitContainer (resizable)
│   ├── SourcePanel (left)
│   │   └── PdfViewerPanel
│   │       ├── PdfPage (canvas)
│   │       └── BboxOverlay (canvas layer)
│   └── TargetPanel (right, or message if unavailable)
│       └── PdfViewerPanel
│           ├── PdfPage (canvas)
│           └── BboxOverlay (canvas layer)
└── NavigationControls (page, zoom)
```

### Zustand Store Pattern (MANDATORY)

```typescript
// CORRECT - Selector pattern per project-context.md
const isOpen = useSplitViewStore((state) => state.isOpen);
const openSplitView = useSplitViewStore((state) => state.openSplitView);

// WRONG - Full store subscription
const { isOpen, openSplitView, ... } = useSplitViewStore();
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Escape | Close split view |
| F | Toggle fullscreen |
| Left Arrow | Previous citation |
| Right Arrow | Next citation |
| +/= | Zoom in |
| - | Zoom out |

### Error States

1. **Act Not Uploaded:**
   - Show single panel with source document
   - Right panel shows message: "Act not uploaded - verification unavailable"
   - Link to Act Discovery to upload the Act

2. **Document Loading Error:**
   - Show error message in panel
   - Retry button
   - Log error for debugging

3. **Bounding Box Not Found:**
   - Highlight page but note "Exact location unavailable"
   - Still navigate to correct page

### File Organization

```
frontend/src/
├── components/
│   └── features/
│       ├── citations/
│       │   ├── SplitViewCitationPanel.tsx    (NEW)
│       │   ├── SplitViewHeader.tsx           (NEW)
│       │   ├── SplitViewModal.tsx            (NEW)
│       │   ├── MismatchExplanation.tsx       (NEW)
│       │   ├── CitationsList.tsx             (UPDATE - add view button)
│       │   └── CitationsTab.tsx              (UPDATE - add split view container)
│       └── pdf/
│           ├── PdfViewerPanel.tsx            (NEW)
│           └── BboxOverlay.tsx               (NEW)
├── lib/
│   ├── api/
│   │   ├── citations.ts                      (UPDATE - add split view API)
│   │   └── boundingBoxes.ts                  (NEW)
│   └── pdf/
│       └── highlightUtils.ts                 (NEW)
├── types/
│   ├── citation.ts                           (UPDATE - add SplitViewData)
│   └── pdf.ts                                (NEW)
├── stores/
│   └── splitViewStore.ts                     (NEW)
└── hooks/
    └── useSplitView.ts                       (NEW)

backend/app/
├── api/
│   └── routes/
│       └── split_view.py                     (NEW)
├── schemas/
│   └── split_view.py                         (NEW)
├── services/
│   └── document_service.py                   (UPDATE - add signed URL method)

backend/tests/
├── api/
│   └── routes/
│       └── test_split_view.py                (NEW)
└── integration/
    └── test_split_view_flow.py               (NEW)
```

### Dependencies

**Frontend:**
```bash
# PDF.js for PDF rendering (add to package.json)
npm install pdfjs-dist@latest

# react-resizable-panels for split view (optional, can use CSS)
npm install react-resizable-panels
```

**Backend:**
```bash
# No new dependencies - uses existing Supabase storage SDK
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - schema already supports bbox coordinates from Story 2B-4

#### Environment Variables
- [ ] None - uses existing Supabase credentials

#### Dashboard Configuration
- [ ] None - no dashboard changes needed

#### Manual Tests
- [ ] Navigate to Citations tab in matter workspace
- [ ] Click "View" on a verified citation
- [ ] Verify split view opens with both panels
- [ ] Verify left panel shows source document with yellow highlight
- [ ] Verify right panel shows Act document with blue highlight
- [ ] Test zoom and page navigation in both panels
- [ ] Click "View" on a mismatch citation
- [ ] Verify red highlighting and explanation displayed
- [ ] Click "View" on citation without Act uploaded
- [ ] Verify single panel with "Act not uploaded" message
- [ ] Test expand to full modal mode
- [ ] Test keyboard shortcuts (Escape, F, arrows)
- [ ] Test panel resize dragging
- [ ] Verify matter isolation - cannot view other matter's citations

### Downstream Dependencies

This story enables:
- **Epic 10C (Citations Tab):** Full Citations Tab UI integration
- **Epic 11 (PDF Viewer):** Reuses PdfViewerPanel components
- **Export Builder (Epic 12):** Can link to split view for verification

### References

- [Source: architecture.md#Citation-Engine-Flow] - Split view in citation pipeline
- [Source: epics.md#Story-3.4] - Story requirements and acceptance criteria
- [Source: epics.md#Story-11.5] - PDF viewer split-view mode patterns
- [Source: epics.md#Story-11.7] - Bounding box overlay patterns
- [Source: project-context.md#Performance-Gotchas] - Canvas overlay requirement
- [Source: 3-3-citation-verification.md] - Verification result structure
- [Source: frontend/src/types/citation.ts] - Existing citation types
- [Source: UX-Decisions-Log.md#PDF-Viewer-Mode] - Split view UX decisions

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- Components in `components/features/{domain}/` per project-context.md
- API routes in `api/routes/` following FastAPI patterns
- Types in `types/{domain}.ts` following TypeScript conventions
- Store in `stores/` following Zustand patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- All 12 tasks completed
- Frontend tests: 294 passing (all split-view related tests pass)
- Backend tests: 4 passing for split-view endpoint
- TypeScript compilation passes with no errors
- Dependencies added: pdfjs-dist, react-resizable-panels

### File List

**Frontend - New Files:**
- `frontend/src/types/pdf.ts` - PDF viewer types and constants
- `frontend/src/lib/pdf/highlightUtils.ts` - Bbox highlighting utilities
- `frontend/src/lib/pdf/highlightUtils.test.ts` - Highlighting tests
- `frontend/src/stores/splitViewStore.ts` - Zustand store for split view state
- `frontend/src/stores/splitViewStore.test.ts` - Store tests
- `frontend/src/hooks/useSplitView.ts` - Split view hook
- `frontend/src/components/features/pdf/PdfViewerPanel.tsx` - PDF.js wrapper
- `frontend/src/components/features/pdf/BboxOverlay.tsx` - Canvas bbox overlay
- `frontend/src/components/features/pdf/index.ts` - PDF component exports
- `frontend/src/components/features/citation/SplitViewCitationPanel.tsx` - Main split view
- `frontend/src/components/features/citation/SplitViewHeader.tsx` - Header with status
- `frontend/src/components/features/citation/SplitViewHeader.test.tsx` - Header tests
- `frontend/src/components/features/citation/SplitViewModal.tsx` - Full-screen modal
- `frontend/src/components/features/citation/MismatchExplanation.tsx` - Diff display
- `frontend/src/components/features/citation/CitationsList.tsx` - Citations list with view
- `frontend/src/components/features/citation/CitationsTab.tsx` - Citations tab wrapper

**Frontend - Modified Files:**
- `frontend/src/lib/api/citations.ts` - Added getCitationSplitViewData
- `frontend/src/types/citation.ts` - Added SplitViewData, DocumentViewData types
- `frontend/src/types/index.ts` - Added PDF type exports
- `frontend/src/components/features/citation/index.ts` - Added split view exports
- `frontend/package.json` - Added pdfjs-dist, react-resizable-panels

**Backend - Modified Files:**
- `backend/app/api/routes/citations.py` - Added split-view endpoint with response models

**Backend - New Test Files:**
- `backend/tests/api/test_citations_split_view.py` - Split view API tests
