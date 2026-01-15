# Story 11.2: Implement Q&A Conversation History

Status: complete

## Story

As an **attorney**,
I want **to see my conversation history with LDIP**,
So that **I can reference previous questions and answers**.

## Acceptance Criteria

1. **Given** I have asked questions
   **When** the panel shows history
   **Then** user messages appear as bubbles on the right
   **And** assistant messages appear as bubbles on the left

2. **Given** an assistant message contains sources
   **When** it is displayed
   **Then** source references appear as clickable links
   **And** clicking a link opens the PDF viewer to that location

3. **Given** I scroll up in history
   **When** I reach older messages
   **Then** the sliding window of 20 messages is shown
   **And** older messages can be loaded from Matter Memory if archived

## Tasks / Subtasks

- [x] Task 1: Create ChatMessage component for message bubbles (AC: #1)
  - [x] 1.1: Create `ChatMessage.tsx` in `components/features/chat/`
  - [x] 1.2: Implement user message styling (right-aligned, bg-primary, text-primary-foreground)
  - [x] 1.3: Implement assistant message styling (left-aligned, bg-muted)
  - [x] 1.4: Include timestamp display (relative time like "2 min ago")
  - [x] 1.5: Write tests for ChatMessage component (15 tests)

- [x] Task 2: Create ConversationHistory container component (AC: #1, #3)
  - [x] 2.1: Create `ConversationHistory.tsx` for the message list
  - [x] 2.2: Use ScrollArea (virtualization not needed for 20 messages)
  - [x] 2.3: Implement scroll-to-bottom on new messages
  - [x] 2.4: Add auto-scroll detection (only auto-scroll if user is near bottom)
  - [x] 2.5: Write tests for ConversationHistory (14 tests)

- [x] Task 3: Implement source references in messages (AC: #2)
  - [x] 3.1: Create `SourceReference.tsx` component for citation links
  - [x] 3.2: Source references come from backend as structured data (not parsing)
  - [x] 3.3: Render clickable source links with document icon
  - [x] 3.4: Wire click handler placeholder (PDF viewer in Story 11.5)
  - [x] 3.5: Write tests for SourceReference (11 tests)

- [x] Task 4: Create chatStore for conversation state (AC: #1, #3)
  - [x] 4.1: Create `chatStore.ts` in `stores/` using Zustand
  - [x] 4.2: Define state: messages[], isLoading, error, hasMore, currentSession
  - [x] 4.3: Implement actions: addMessage, loadHistory, loadArchivedMessages, clearMessages
  - [x] 4.4: Use localStorage persistence for conversation continuity
  - [x] 4.5: Implement selector pattern per project-context.md requirements
  - [x] 4.6: Write tests for chatStore (27 tests)

- [x] Task 5: Integrate with backend session memory API (AC: #3)
  - [x] 5.1: Create `lib/api/chat.ts` with getConversationHistory()
  - [x] 5.2: Add getArchivedMessages() for Matter Memory retrieval
  - [x] 5.3: Handle sliding window (max 20) from backend SessionMemoryService
  - [x] 5.4: Implement error handling with toast notifications
  - [x] 5.5: Write tests for chat API functions (15 tests)

- [x] Task 6: Update QAPanel to use ConversationHistory (AC: All)
  - [x] 6.1: Updated QAPanel to conditionally show ConversationHistory
  - [x] 6.2: Conditionally show placeholder when no matterId/userId
  - [x] 6.3: Wire up message loading via props (matterId, userId)
  - [x] 6.4: Handle loading and error states in ConversationHistory
  - [x] 6.5: Update QAPanel tests (8 tests) and FloatingQAPanel tests (21 tests)

- [x] Task 7: Run all tests and lint validation (AC: All)
  - [x] 7.1: Run `npm run test` - 209 chat-related tests passing
  - [x] 7.2: Run `npm run lint` - no new errors (only pre-existing issues)
  - [x] 7.3: Run TypeScript compiler - no type errors in new files

## Dev Notes

### Critical Architecture Pattern: Backend Session Memory Already Exists

**IMPORTANT: Story 7-1 and 7-2 already implemented the backend session memory system!**

| Existing Backend | Location | What Already Works |
|-----------------|----------|-------------------|
| `SessionMemoryService` | `backend/app/services/memory/session.py` | Full session CRUD, sliding window, archival |
| `SessionContext` model | `backend/app/models/memory.py:91` | Messages list, entities, TTL tracking |
| `SessionMessage` model | `backend/app/models/memory.py:51` | role, content, timestamp, entity_refs |
| `ArchivedSession` model | `backend/app/models/memory.py:153` | Last 10 messages for restoration |
| Redis key pattern | `session:{matter_id}:{user_id}:context` | 7-day TTL, auto-extend |

### Frontend Components to Create

**New Files:**
```
frontend/src/
├── components/features/chat/
│   ├── ChatMessage.tsx           # NEW - Individual message bubble
│   ├── ChatMessage.test.tsx      # NEW - Tests
│   ├── ConversationHistory.tsx   # NEW - Message list container
│   ├── ConversationHistory.test.tsx # NEW - Tests
│   ├── SourceReference.tsx       # NEW - Clickable source link
│   └── SourceReference.test.tsx  # NEW - Tests
├── stores/
│   └── chatStore.ts              # NEW - Conversation state
├── lib/api/
│   └── chat.ts                   # NEW - Chat API client
└── types/
    └── chat.ts                   # NEW - Chat types
```

### Message Interface (Frontend)

```typescript
// types/chat.ts
export interface ChatMessage {
  id: string;                    // Generated client-side
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;             // ISO8601
  sources?: SourceReference[];   // Parsed from content
}

export interface SourceReference {
  documentId: string;
  documentName: string;
  page?: number;
  bboxIds?: string[];
}
```

### Zustand Store Pattern (MANDATORY)

```typescript
// stores/chatStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;               // For loading archived messages
  currentSessionId: string | null;
}

interface ChatActions {
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  loadHistory: (matterId: string, userId: string) => Promise<void>;
  loadArchivedMessages: (matterId: string, userId: string) => Promise<void>;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState & ChatActions>()(
  persist(
    (set, get) => ({
      // State
      messages: [],
      isLoading: false,
      error: null,
      hasMore: true,
      currentSessionId: null,

      // Actions
      addMessage: (message) => set((state) => ({
        messages: [...state.messages, message],
      })),
      // ... other actions
    }),
    {
      name: 'ldip-chat-history',
      partialize: (state) => ({
        messages: state.messages.slice(-20), // Only persist last 20
        currentSessionId: state.currentSessionId,
      }),
    }
  )
);

// CORRECT usage in components (selector pattern):
const messages = useChatStore((state) => state.messages);
const addMessage = useChatStore((state) => state.addMessage);

// WRONG (causes unnecessary re-renders):
const { messages, addMessage } = useChatStore();
```

### ChatMessage Component Pattern

```tsx
// components/features/chat/ChatMessage.tsx
'use client';

import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { User, Bot } from 'lucide-react';
import { SourceReference } from './SourceReference';
import type { ChatMessage as ChatMessageType } from '@/types/chat';

interface ChatMessageProps {
  message: ChatMessageType;
  onSourceClick?: (source: SourceReference) => void;
}

export function ChatMessage({ message, onSourceClick }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message bubble */}
      <div
        className={cn(
          'flex max-w-[80%] flex-col gap-1',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        <div
          className={cn(
            'rounded-lg px-4 py-2 text-sm',
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-foreground'
          )}
        >
          {message.content}

          {/* Source references (assistant only) */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {message.sources.map((source, index) => (
                <SourceReference
                  key={`${source.documentId}-${index}`}
                  source={source}
                  onClick={() => onSourceClick?.(source)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
        </span>
      </div>
    </div>
  );
}
```

### ConversationHistory Virtualization

For performance with sliding window messages, use react-window:

```tsx
// ConversationHistory.tsx
import { FixedSizeList as List } from 'react-window';
import { useRef, useEffect } from 'react';
import { useChatStore } from '@/stores/chatStore';

export function ConversationHistory() {
  const messages = useChatStore((state) => state.messages);
  const listRef = useRef<List>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (listRef.current && messages.length > 0) {
      listRef.current.scrollToItem(messages.length - 1, 'end');
    }
  }, [messages.length]);

  return (
    <List
      ref={listRef}
      height={400}  // Will be dynamic based on container
      itemCount={messages.length}
      itemSize={100}  // Estimated, can vary
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          <ChatMessage message={messages[index]} />
        </div>
      )}
    </List>
  );
}
```

### Source Reference Click Handler

Integrate with existing PDF viewer pattern from Story 11.5 (placeholder for now):

```typescript
// Pattern to implement when PDF viewer exists
const handleSourceClick = (source: SourceReference) => {
  // This will be fully implemented in Story 11.5
  // For now, just console.log and show toast
  console.log('Opening source:', source);
  toast.info(`Opening ${source.documentName} at page ${source.page}`);

  // Future integration:
  // setPdfViewerDocument(source.documentId);
  // setPdfViewerPage(source.page);
  // setPdfViewerHighlight(source.bboxIds);
};
```

### Backend API Integration

The backend already has session memory. Create frontend API client:

```typescript
// lib/api/chat.ts
import { apiClient } from './client';
import type { SessionContext, SessionMessage } from '@/types/chat';

export async function getConversationHistory(
  matterId: string,
  userId: string
): Promise<SessionMessage[]> {
  const response = await apiClient.get<{ data: SessionContext }>(
    `/api/session/${matterId}/${userId}`
  );
  return response.data.data.messages;
}

export async function loadArchivedMessages(
  matterId: string,
  userId: string
): Promise<SessionMessage[]> {
  const response = await apiClient.get<{ data: SessionContext }>(
    `/api/session/${matterId}/${userId}/restore`
  );
  return response.data.data.messages;
}
```

### Testing Strategy

**Component Tests:**
```typescript
// ChatMessage.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatMessage } from './ChatMessage';

describe('ChatMessage', () => {
  const userMessage = {
    id: '1',
    role: 'user' as const,
    content: 'What is this case about?',
    timestamp: new Date().toISOString(),
  };

  const assistantMessage = {
    id: '2',
    role: 'assistant' as const,
    content: 'This case involves a dispute...',
    timestamp: new Date().toISOString(),
    sources: [{
      documentId: 'doc-1',
      documentName: 'petition.pdf',
      page: 5,
    }],
  };

  test('renders user message on the right', () => {
    render(<ChatMessage message={userMessage} />);
    expect(screen.getByText(userMessage.content)).toBeInTheDocument();
    // Check right alignment via class
  });

  test('renders assistant message on the left', () => {
    render(<ChatMessage message={assistantMessage} />);
    expect(screen.getByText(assistantMessage.content)).toBeInTheDocument();
  });

  test('renders source references for assistant messages', () => {
    render(<ChatMessage message={assistantMessage} />);
    expect(screen.getByText(/petition.pdf/)).toBeInTheDocument();
  });

  test('calls onSourceClick when source is clicked', async () => {
    const handleClick = vi.fn();
    render(<ChatMessage message={assistantMessage} onSourceClick={handleClick} />);

    await userEvent.click(screen.getByText(/petition.pdf/));
    expect(handleClick).toHaveBeenCalledWith(assistantMessage.sources[0]);
  });
});
```

### Project Structure Notes

```
frontend/src/
├── components/features/chat/
│   ├── QAPanel.tsx              # UPDATE - Replace placeholder with ConversationHistory
│   ├── QAPanelHeader.tsx        # NO CHANGES - From Story 11.1
│   ├── QAPanelPlaceholder.tsx   # UPDATE - Show only when no messages
│   ├── FloatingQAPanel.tsx      # NO CHANGES
│   ├── QAPanelExpandButton.tsx  # NO CHANGES
│   ├── ChatMessage.tsx          # NEW
│   ├── ChatMessage.test.tsx     # NEW
│   ├── ConversationHistory.tsx  # NEW
│   ├── ConversationHistory.test.tsx # NEW
│   ├── SourceReference.tsx      # NEW
│   └── SourceReference.test.tsx # NEW
├── stores/
│   ├── qaPanelStore.ts          # NO CHANGES
│   └── chatStore.ts             # NEW
├── lib/api/
│   └── chat.ts                  # NEW
└── types/
    └── chat.ts                  # NEW
```

### Previous Story Intelligence (Story 11.1)

**Key Learnings:**
1. Q&A panel header with "ASK LDIP" title and minimize button works
2. Panel positions (right/bottom/float/hidden) all functional
3. qaPanelStore persistence pattern established
4. Test patterns for chat components established

**From 11.1 Implementation:**
- Header uses Zustand selector pattern correctly
- Tooltip pattern for icon buttons established
- Test file co-location pattern used
- 101 chat/Q&A tests passing baseline

### Dependencies

**NPM packages to add (if not already present):**
```bash
npm install react-window @types/react-window date-fns
```

**Existing dependencies to use:**
- Zustand (already installed)
- lucide-react icons (already installed)
- shadcn/ui components (already installed)
- Tailwind CSS (already configured)

### Git Commit Pattern

```
feat(qa-panel): implement conversation history with message bubbles (Story 11.2)
```

### Testing Checklist

- [ ] User messages appear as bubbles on the right (bg-primary)
- [ ] Assistant messages appear as bubbles on the left (bg-muted)
- [ ] Timestamps show relative time ("2 min ago")
- [ ] Source references render as clickable links
- [ ] Clicking source opens console.log for now (PDF viewer in 11.5)
- [ ] Messages load from backend session on mount
- [ ] Sliding window shows max 20 messages
- [ ] "Load more" loads archived messages from Matter Memory
- [ ] Store persists messages to localStorage (last 20 only)
- [ ] Empty state shows QAPanelPlaceholder
- [ ] Loading state shows spinner
- [ ] Error state shows toast notification
- [ ] All tests pass
- [ ] Lint passes with no errors

### References

- [Source: epics.md#Story-11.2 - Acceptance Criteria]
- [Source: 11-1-qa-panel-header-position.md - Previous story with Q&A panel implementation]
- [Source: backend/app/services/memory/session.py - Session memory service with sliding window]
- [Source: backend/app/models/memory.py - SessionMessage, SessionContext models]
- [Source: frontend/src/stores/qaPanelStore.ts - Zustand store pattern reference]
- [Source: project-context.md - Zustand selectors, naming conventions, testing rules]
- [Source: architecture.md - Three-layer memory system (Session Memory = Layer 1)]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Successful implementation without significant issues

### Completion Notes List

1. **Implementation Approach**: Used existing ScrollArea instead of react-window for virtualization since the sliding window is only 20 messages - virtualization would be overkill
2. **Source Reference Pattern**: Sources come from backend as structured data, no parsing required on frontend
3. **PDF Viewer Integration**: Click handler shows toast placeholder - full integration in Story 11.5
4. **Props Threading**: matterId and userId passed from WorkspaceContentArea through QAPanel/FloatingQAPanel to ConversationHistory
5. **User ID Resolution**: Uses existing useUser() hook from auth module
6. **Test Count**: 209 tests total for chat-related components and stores

### File List

**New Files Created:**
- `frontend/src/types/chat.ts` - Chat type definitions
- `frontend/src/components/features/chat/ChatMessage.tsx` - Message bubble component
- `frontend/src/components/features/chat/ChatMessage.test.tsx` - 15 tests
- `frontend/src/components/features/chat/SourceReference.tsx` - Clickable source link
- `frontend/src/components/features/chat/SourceReference.test.tsx` - 11 tests
- `frontend/src/components/features/chat/ConversationHistory.tsx` - Message list container
- `frontend/src/components/features/chat/ConversationHistory.test.tsx` - 14 tests
- `frontend/src/stores/chatStore.ts` - Zustand store for conversation state
- `frontend/src/stores/chatStore.test.ts` - 27 tests
- `frontend/src/lib/api/chat.ts` - Chat API client
- `frontend/src/lib/api/chat.test.ts` - 15 tests

**Modified Files:**
- `frontend/src/components/features/chat/QAPanel.tsx` - Added ConversationHistory integration
- `frontend/src/components/features/chat/QAPanel.test.tsx` - Updated tests (8 tests)
- `frontend/src/components/features/chat/FloatingQAPanel.tsx` - Added matterId/userId props
- `frontend/src/components/features/chat/FloatingQAPanel.test.tsx` - Updated tests (21 tests)
- `frontend/src/components/features/matter/WorkspaceContentArea.tsx` - Wire matterId/userId to panels
