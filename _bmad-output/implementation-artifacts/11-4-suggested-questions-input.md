# Story 11.4: Implement Suggested Questions and Message Input

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to see suggested questions when the conversation is empty**,
So that **I know what kinds of questions I can ask and can quickly start exploring my matter**.

## Acceptance Criteria

1. **Given** the conversation history is empty
   **When** I open the Q&A panel
   **Then** I see a set of suggested questions displayed as clickable buttons/chips
   **And** example suggestions include: "What is this case about?", "Who are the main parties?", "What is the timeline of events?", "Are there any citation issues?"

2. **Given** I see suggested questions
   **When** I click one of the suggestions
   **Then** the question is submitted to the chat as if I typed it
   **And** the suggested questions disappear
   **And** the conversation begins with my selected question

3. **Given** I have started a conversation (messages exist)
   **When** I return to the Q&A panel
   **Then** the suggested questions are NOT shown (only shown for empty state)

4. **Given** I am in the empty state with suggested questions
   **When** I type in the input field and submit
   **Then** the suggested questions disappear
   **And** my typed message is sent instead

## Tasks / Subtasks

- [x] Task 1: Create SuggestedQuestions component (AC: #1)
  - [x] 1.1: Create `SuggestedQuestions.tsx` in `frontend/src/components/features/chat/`
  - [x] 1.2: Define array of default suggested questions
  - [x] 1.3: Render questions as clickable Button components with `variant="outline"`
  - [x] 1.4: Use grid/flex layout for question chips (responsive for panel width)
  - [x] 1.5: Add descriptive heading "Try asking:" or similar
  - [x] 1.6: Style with muted colors and appropriate spacing

- [x] Task 2: Implement question click handler (AC: #2)
  - [x] 2.1: Add `onQuestionClick` prop to SuggestedQuestions component
  - [x] 2.2: Call parent callback with selected question text
  - [x] 2.3: Ensure click triggers same flow as manual message submission
  - [x] 2.4: Add hover states and focus styles for accessibility

- [x] Task 3: Update QAPanel for empty state (AC: #1, #3, #4)
  - [x] 3.1: Detect empty state using `selectIsEmpty` selector from chatStore
  - [x] 3.2: Conditionally render SuggestedQuestions when conversation is empty
  - [x] 3.3: Pass handleSubmit to SuggestedQuestions for question clicks
  - [x] 3.4: Ensure suggestions hide once first message is sent

- [x] Task 4: Update ConversationHistory for empty state UI (AC: #1)
  - [x] 4.1: Add empty state prop or internal detection (handled via QAPanel conditional rendering)
  - [x] 4.2: Show SuggestedQuestions component inside conversation area when empty (in QAPanel)
  - [x] 4.3: Center suggestions vertically in conversation area
  - [x] 4.4: Include LDIP branding/icon in empty state (MessageSquare icon + ASK LDIP heading)

- [ ] Task 5: Add matter-specific suggested questions (optional enhancement)
  - [ ] 5.1: Define question templates that could include matter context
  - [ ] 5.2: Consider dynamic questions based on matter type (if available)
  - [x] 5.3: Keep static defaults as fallback

- [x] Task 6: Write comprehensive tests (AC: All)
  - [x] 6.1: Test SuggestedQuestions renders all default questions
  - [x] 6.2: Test clicking a question calls onQuestionClick with correct text
  - [x] 6.3: Test suggestions shown when messages array is empty
  - [x] 6.4: Test suggestions hidden when messages exist
  - [x] 6.5: Test suggestion click triggers message submission flow
  - [x] 6.6: Test manual input submission hides suggestions
  - [x] 6.7: Test accessibility (keyboard navigation, ARIA labels)

## Dev Notes

### Empty State Detection

The chatStore already has a selector for detecting empty state:

```typescript
// frontend/src/stores/chatStore.ts (existing)
export const selectIsEmpty = (state: ChatStore): boolean => {
  return state.messages.length === 0;
};
```

Use this selector in QAPanel to conditionally render SuggestedQuestions:

```typescript
const isEmpty = useChatStore(selectIsEmpty);
```

### Default Suggested Questions

From FR26 in epics.md, the suggested questions should help attorneys quickly explore their matter:

```typescript
const DEFAULT_SUGGESTIONS = [
  "What is this case about?",
  "Who are the main parties involved?",
  "What is the timeline of key events?",
  "Are there any citation issues?",
  "What contradictions exist in the documents?",
  "Summarize the key findings",
];
```

### Component Structure

The SuggestedQuestions component should be placed INSIDE the conversation area (above input) when empty, not replacing the entire panel:

```
┌─────────────────────────────────┐
│  QAPanelHeader                  │
├─────────────────────────────────┤
│                                 │
│     [LDIP Icon]                 │
│     "ASK LDIP"                  │
│                                 │
│     Try asking:                 │
│  ┌─────────────────────────┐   │
│  │ What is this case about?│   │
│  └─────────────────────────┘   │
│  ┌─────────────────────────┐   │
│  │ Who are the main parties│   │
│  └─────────────────────────┘   │
│  ┌─────────────────────────┐   │
│  │ What is the timeline... │   │
│  └─────────────────────────┘   │
│  (more suggestions...)          │
│                                 │
├─────────────────────────────────┤
│  ChatInput                      │
└─────────────────────────────────┘
```

### QAPanel Integration Pattern

```tsx
// frontend/src/components/features/chat/QAPanel.tsx
// Add to existing component

import { SuggestedQuestions } from './SuggestedQuestions';
import { selectIsEmpty } from '@/stores/chatStore';

export function QAPanel({ matterId, userId, onSourceClick }: QAPanelProps) {
  // Existing selectors...
  const isEmpty = useChatStore(selectIsEmpty);

  // ... existing code ...

  return (
    <div className="flex h-full flex-col bg-background">
      <QAPanelHeader />

      <div className="flex flex-1 flex-col overflow-hidden">
        {canLoadHistory ? (
          <>
            {isEmpty && !streamingMessageId ? (
              // Empty state with suggested questions
              <div className="flex flex-1 flex-col items-center justify-center p-6">
                <SuggestedQuestions onQuestionClick={handleSubmit} />
              </div>
            ) : (
              <>
                {/* Conversation history */}
                <ConversationHistory ... />

                {/* Streaming message */}
                {streamingMessageId && <StreamingMessage ... />}
              </>
            )}

            {/* Chat input (always visible) */}
            <ChatInput ... />
          </>
        ) : (
          <QAPanelPlaceholder />
        )}
      </div>
    </div>
  );
}
```

### SuggestedQuestions Component Pattern

```tsx
// frontend/src/components/features/chat/SuggestedQuestions.tsx
'use client';

import { MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface SuggestedQuestionsProps {
  /** Callback when a suggested question is clicked */
  onQuestionClick: (question: string) => void;
  /** Additional CSS classes */
  className?: string;
}

const DEFAULT_SUGGESTIONS = [
  "What is this case about?",
  "Who are the main parties involved?",
  "What is the timeline of key events?",
  "Are there any citation issues?",
  "What contradictions exist in the documents?",
  "Summarize the key findings",
];

export function SuggestedQuestions({
  onQuestionClick,
  className
}: SuggestedQuestionsProps) {
  return (
    <div className={cn("flex flex-col items-center text-center", className)}>
      <MessageSquare className="mb-4 h-12 w-12 text-muted-foreground" />
      <h3 className="mb-2 text-lg font-medium">ASK LDIP</h3>
      <p className="mb-6 max-w-xs text-sm text-muted-foreground">
        Ask questions about your matter. The AI will analyze documents and
        provide answers with citations.
      </p>

      <div className="space-y-2 w-full max-w-sm">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Try asking
        </p>
        <div className="flex flex-col gap-2">
          {DEFAULT_SUGGESTIONS.map((question) => (
            <Button
              key={question}
              variant="outline"
              size="sm"
              className="justify-start text-left h-auto py-2 px-3 text-sm font-normal"
              onClick={() => onQuestionClick(question)}
            >
              {question}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### Project Structure Notes

**New Files:**
```
frontend/src/components/features/chat/
├── SuggestedQuestions.tsx              # NEW - Suggested questions component
└── __tests__/
    └── SuggestedQuestions.test.tsx     # NEW - Component tests
```

**Modified Files:**
```
frontend/src/components/features/chat/
├── QAPanel.tsx                         # UPDATE - Add empty state detection and SuggestedQuestions
├── index.ts                            # UPDATE - Export SuggestedQuestions
```

### Existing Infrastructure to Use

| Component | Location | What It Provides |
|-----------|----------|------------------|
| `selectIsEmpty` | `stores/chatStore.ts:302` | Selector for empty conversation |
| `selectHasUserMessages` | `stores/chatStore.ts:309` | Alternative empty check |
| `Button` | `components/ui/button.tsx` | shadcn button component |
| `ChatInput` | `components/features/chat/ChatInput.tsx` | Message submission handler |
| `QAPanelPlaceholder` | `components/features/chat/QAPanelPlaceholder.tsx` | Reference for empty state styling |

### Previous Story Intelligence (Story 11.3)

**Key Learnings:**
1. QAPanel uses Zustand selectors for all state access (not destructuring)
2. handleSubmit callback handles message creation and streaming start
3. ChatInput already supports disabled state during streaming
4. StreamingMessage renders separately from ConversationHistory
5. SSE integration via useSSE hook with typed event handlers

**From 11.3 Implementation:**
- `handleSubmit` in QAPanel creates user message and triggers streaming
- Same callback can be passed to SuggestedQuestions for consistent behavior
- 27 tests added in 11.3, baseline for chat component testing

### Git Commit Pattern

```
feat(chat): implement suggested questions for empty state (Story 11.4)
```

### Testing Strategy

**Component Tests:**
```typescript
// SuggestedQuestions.test.tsx
describe('SuggestedQuestions', () => {
  test('renders all default suggested questions', () => {
    render(<SuggestedQuestions onQuestionClick={vi.fn()} />);

    expect(screen.getByText('What is this case about?')).toBeInTheDocument();
    expect(screen.getByText('Who are the main parties involved?')).toBeInTheDocument();
    // ... verify all suggestions
  });

  test('calls onQuestionClick with question text when clicked', async () => {
    const handleClick = vi.fn();
    render(<SuggestedQuestions onQuestionClick={handleClick} />);

    await userEvent.click(screen.getByText('What is this case about?'));

    expect(handleClick).toHaveBeenCalledWith('What is this case about?');
  });

  test('questions are keyboard accessible', async () => {
    const handleClick = vi.fn();
    render(<SuggestedQuestions onQuestionClick={handleClick} />);

    const firstQuestion = screen.getByText('What is this case about?');
    firstQuestion.focus();
    await userEvent.keyboard('{Enter}');

    expect(handleClick).toHaveBeenCalled();
  });
});
```

**Integration Tests (QAPanel):**
```typescript
// QAPanel.test.tsx (add to existing)
describe('QAPanel empty state', () => {
  test('shows suggested questions when conversation is empty', () => {
    // Mock empty chat store
    render(<QAPanel matterId="test" userId="test" />);

    expect(screen.getByText('Try asking')).toBeInTheDocument();
    expect(screen.getByText('What is this case about?')).toBeInTheDocument();
  });

  test('hides suggested questions when messages exist', () => {
    // Mock chat store with messages
    render(<QAPanel matterId="test" userId="test" />);

    expect(screen.queryByText('Try asking')).not.toBeInTheDocument();
  });

  test('clicking suggestion submits message', async () => {
    render(<QAPanel matterId="test" userId="test" />);

    await userEvent.click(screen.getByText('What is this case about?'));

    // Verify message was added to store and streaming started
  });
});
```

### Testing Checklist

- [ ] Suggested questions render in empty state
- [ ] All 6 default questions are displayed
- [ ] Clicking a question triggers handleSubmit with question text
- [ ] Suggestions disappear after first message is sent
- [ ] Suggestions hidden when conversation has existing messages
- [ ] Manual input submission hides suggestions
- [ ] Keyboard navigation works (Tab, Enter)
- [ ] ARIA labels present for accessibility
- [ ] Responsive layout works in narrow panel widths
- [ ] All frontend tests pass
- [ ] Lint passes with no errors

### References

- [Source: epics.md#FR26 - "Display suggested questions for empty state"]
- [Source: epics.md#Story-11.4 - Acceptance Criteria]
- [Source: 11-3-streaming-response-engine-trace.md - QAPanel integration patterns]
- [Source: frontend/src/stores/chatStore.ts:302 - selectIsEmpty selector]
- [Source: frontend/src/components/features/chat/QAPanelPlaceholder.tsx - Empty state styling]
- [Source: frontend/src/components/features/chat/QAPanel.tsx - Current panel structure]
- [Source: project-context.md - Zustand selectors, testing rules, component patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5

### Debug Log References

N/A - No debugging issues encountered.

### Completion Notes List

- Created SuggestedQuestions component with 6 default questions from FR26
- Implemented empty state detection using existing `selectIsEmpty` selector from chatStore
- Updated QAPanel to conditionally render SuggestedQuestions when conversation is empty
- Clicking a suggested question calls handleSubmit, which creates user message and starts streaming
- Suggestions automatically hide when:
  - User sends any message (isEmpty becomes false)
  - Streaming is active (streamingMessageId is set)
- Component includes:
  - MessageSquare icon with LDIP branding
  - "Try asking" label
  - 6 clickable suggestion buttons with outline variant
  - Full ARIA accessibility (region, list, listitem roles with labels)
  - Keyboard navigation support (Tab, Enter)
- 17 SuggestedQuestions tests + 9 QAPanel empty state tests = 26 new tests
- Total chat component tests: 160 passing

### File List

**New Files:**
- frontend/src/components/features/chat/SuggestedQuestions.tsx
- frontend/src/components/features/chat/SuggestedQuestions.test.tsx

**Modified Files:**
- frontend/src/components/features/chat/QAPanel.tsx (added empty state + SuggestedQuestions)
- frontend/src/components/features/chat/QAPanel.test.tsx (added 9 Story 11.4 tests)
- frontend/src/components/features/chat/index.ts (export SuggestedQuestions)

## Change Log

- 2026-01-16: Story 11.4 implementation complete - Suggested questions for empty Q&A panel state
- 2026-01-16: Code review fixes applied:
  - Removed unused `abortStream` from QAPanel.tsx (lint warning fix)
  - Updated test to verify behavior not implementation details (data-variant removed)
  - Corrected misleading comment about SuggestedQuestions mocking in QAPanel.test.tsx

