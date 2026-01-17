# Story 14.18: In-App Help System

Status: done

## Story

As a **legal attorney using LDIP**,
I want **contextual help available within the application**,
so that **I can learn how to use features without leaving the app or searching external documentation**.

## Acceptance Criteria

1. **AC1: Help button in navigation**
   - Help icon/button visible in header or user menu
   - Opens help panel or modal
   - Keyboard shortcut (? or F1)

2. **AC2: Contextual help tooltips**
   - Help icons (?) next to complex features
   - Hover/click shows explanation tooltip
   - Links to detailed help if available

3. **AC3: Feature tour for new users**
   - First-time user guided tour
   - Highlights key features step-by-step
   - Skip option and "Don't show again" preference

4. **AC4: Help panel with search**
   - Searchable help content
   - Organized by feature/topic
   - Quick answers for common questions

5. **AC5: Feedback link**
   - "Report an issue" link
   - Opens GitHub issues or feedback form
   - Pre-fills context (current page, user ID)

## Tasks / Subtasks

- [x] **Task 1: Create HelpButton component** (AC: #1)
  - [x] 1.1 Create `frontend/src/components/features/help/HelpButton.tsx`
  - [x] 1.2 Add to header navigation
  - [x] 1.3 Implement keyboard shortcut (?)
  - [x] 1.4 Opens HelpPanel on click

- [x] **Task 2: Create HelpPanel component** (AC: #1, #4)
  - [x] 2.1 Create `frontend/src/components/features/help/HelpPanel.tsx`
  - [x] 2.2 Slide-over panel design (from right)
  - [x] 2.3 Search input at top
  - [x] 2.4 Topic list with expandable sections
  - [x] 2.5 Close button and escape key

- [x] **Task 3: Create help content** (AC: #4)
  - [x] 3.1 Create `frontend/src/data/help-content.ts`
  - [x] 3.2 Write help entries for each feature
  - [x] 3.3 Include: title, content, related topics
  - [x] 3.4 Organize by category (Documents, Timeline, Chat, etc.)

- [x] **Task 4: Create HelpTooltip component** (AC: #2)
  - [x] 4.1 Create `frontend/src/components/features/help/HelpTooltip.tsx`
  - [x] 4.2 Small (?) icon that shows tooltip on hover
  - [x] 4.3 Optional "Learn more" link
  - [x] 4.4 Accessible (screen reader friendly)

- [x] **Task 5: Add tooltips to complex features** (AC: #2)
  - [x] 5.1 Add HelpTooltip to Hybrid Search explanation
  - [x] 5.2 Add HelpTooltip to Contradiction confidence
  - [x] 5.3 Added data-tour attributes for feature tour

- [x] **Task 6: Create FeatureTour component** (AC: #3)
  - [x] 6.1 Create `frontend/src/components/features/help/FeatureTour.tsx`
  - [x] 6.2 Custom implementation (no external dependency)
  - [x] 6.3 Define tour steps for key features
  - [x] 6.4 Store "tour completed" in localStorage
  - [x] 6.5 Trigger on first login (with 1s delay)

- [x] **Task 7: Create FeedbackButton component** (AC: #5)
  - [x] 7.1 Create `frontend/src/components/features/help/FeedbackButton.tsx`
  - [x] 7.2 Add to help panel footer
  - [x] 7.3 Link to GitHub issues with pre-filled template
  - [x] 7.4 Include context: page URL, browser info

- [x] **Task 8: Add help content for all features** (AC: #4)
  - [x] 8.1 Dashboard/Getting started help content
  - [x] 8.2 Document upload help content
  - [x] 8.3 Timeline help content
  - [x] 8.4 Citations help content
  - [x] 8.5 Contradictions help content
  - [x] 8.6 Chat/Q&A help content
  - [x] 8.7 Export help content
  - [x] 8.8 Entities help content
  - [x] 8.9 Troubleshooting help content

- [x] **Task 9: Write tests** (AC: all)
  - [x] 9.1 Test HelpPanel opens/closes
  - [x] 9.2 Test search filters content
  - [x] 9.3 Test keyboard shortcut
  - [x] 9.4 Test tour completes and saves preference
  - [x] 9.5 Test FeedbackButton
  - [x] 9.6 Test HelpTooltip

## Dev Notes

### Current State

From the audit:
- Help link currently goes to external URL
- No in-app help or tooltips
- No onboarding tour

### Help Content Structure

```typescript
// frontend/src/data/help-content.ts
interface HelpEntry {
  id: string;
  title: string;
  category: 'getting-started' | 'documents' | 'timeline' | 'chat' | 'export' | 'troubleshooting';
  content: string; // Markdown supported
  keywords: string[]; // For search
  relatedTopics?: string[]; // IDs of related entries
}

export const helpContent: HelpEntry[] = [
  {
    id: 'upload-documents',
    title: 'Uploading Documents',
    category: 'documents',
    content: `
## How to Upload Documents

1. Navigate to the Documents tab in your matter workspace
2. Click the "Upload" button or drag files into the drop zone
3. Supported formats: PDF, DOCX, images (JPG, PNG)
4. Wait for OCR processing to complete

### Tips
- Large PDFs (100+ pages) may take several minutes
- You'll see a progress indicator during processing
    `,
    keywords: ['upload', 'document', 'pdf', 'file', 'ocr'],
    relatedTopics: ['document-processing', 'supported-formats'],
  },
  // ... more entries
];
```

### Feature Tour Steps

```typescript
const tourSteps = [
  {
    target: '.matter-cards',
    content: 'Your matters appear here. Click a card to open the workspace.',
    placement: 'bottom',
  },
  {
    target: '.upload-button',
    content: 'Upload case documents here. We support PDF, Word, and images.',
    placement: 'left',
  },
  {
    target: '.chat-panel',
    content: 'Ask questions about your documents using natural language.',
    placement: 'left',
  },
  {
    target: '.timeline-tab',
    content: 'View extracted events on an interactive timeline.',
    placement: 'bottom',
  },
];
```

### Libraries

- **react-joyride** - Feature tour library
- **@radix-ui/react-tooltip** - Already in shadcn/ui
- **fuse.js** - Client-side fuzzy search for help content

### Keyboard Shortcuts

```typescript
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // ? key (shift + /) opens help
    if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      setHelpOpen(true);
    }
    // Escape closes help
    if (e.key === 'Escape' && helpOpen) {
      setHelpOpen(false);
    }
  };

  document.addEventListener('keydown', handleKeyDown);
  return () => document.removeEventListener('keydown', handleKeyDown);
}, [helpOpen]);
```

### File Structure

```
frontend/src/
├── components/features/help/
│   ├── index.ts
│   ├── HelpButton.tsx
│   ├── HelpPanel.tsx
│   ├── HelpTooltip.tsx
│   ├── FeatureTour.tsx
│   ├── FeedbackButton.tsx
│   └── __tests__/
├── data/
│   └── help-content.ts
└── hooks/
    └── useHelpSearch.ts
```

### Feedback URL Template

```
https://github.com/your-org/ldip/issues/new?
  template=bug_report.md&
  title=[Bug]%20&
  body=%0A%0A---%0APage:%20${encodeURIComponent(window.location.pathname)}%0A
  Browser:%20${encodeURIComponent(navigator.userAgent)}
```

### References

- [Source: frontend/src/components/layout/Header.tsx] - Where help button goes
- [Source: react-joyride documentation] - Tour library
