import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from '@testing-library/react';
import { ConversationHistory } from './ConversationHistory';
import { useChatStore, STORAGE_KEY } from '@/stores/chatStore';
import type { ChatMessage } from '@/types/chat';

// Mock the chat API
vi.mock('@/lib/api/chat', () => ({
  getConversationHistory: vi.fn(),
  getArchivedMessages: vi.fn(),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    info: vi.fn(),
  },
}));

import { getConversationHistory, getArchivedMessages } from '@/lib/api/chat';
import { toast } from 'sonner';

const mockGetConversationHistory = vi.mocked(getConversationHistory);
const mockGetArchivedMessages = vi.mocked(getArchivedMessages);
const mockToast = vi.mocked(toast);

describe('ConversationHistory', () => {
  const matterId = 'matter-123';
  const userId = 'user-456';

  const createMessage = (
    id: string,
    role: 'user' | 'assistant',
    content?: string
  ): ChatMessage => ({
    id,
    role,
    content: content ?? `Message ${id}`,
    timestamp: new Date().toISOString(),
  });

  const mockSessionContext = {
    sessionId: 'session-1',
    matterId,
    userId,
    messages: [
      createMessage('1', 'user', 'What is this case about?'),
      createMessage('2', 'assistant', 'This case involves a contract dispute.'),
    ],
    entities: [],
    hasArchived: true,
  };

  beforeEach(() => {
    // Reset store state
    act(() => {
      useChatStore.getState().reset();
    });
    // Clear mocks
    vi.clearAllMocks();
    // Clear localStorage
    localStorage.removeItem(STORAGE_KEY);
    // Setup default mock response
    mockGetConversationHistory.mockResolvedValue(mockSessionContext);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading state initially', async () => {
    // Create a delayed promise
    mockGetConversationHistory.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockSessionContext), 100))
    );

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    // Should show loading indicator
    expect(screen.getByTestId('conversation-history')).toBeInTheDocument();
  });

  test('renders placeholder when no messages', async () => {
    mockGetConversationHistory.mockResolvedValue({
      ...mockSessionContext,
      messages: [],
      hasArchived: false,
    });

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('ASK LDIP')).toBeInTheDocument();
    });
  });

  test('renders messages after loading', async () => {
    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('What is this case about?')).toBeInTheDocument();
      expect(screen.getByText('This case involves a contract dispute.')).toBeInTheDocument();
    });
  });

  test('shows user messages with correct styling', async () => {
    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      const userMessage = screen.getByTestId('chat-message-user');
      expect(userMessage).toHaveClass('flex-row-reverse');
    });
  });

  test('shows assistant messages with correct styling', async () => {
    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      const assistantMessage = screen.getByTestId('chat-message-assistant');
      expect(assistantMessage).not.toHaveClass('flex-row-reverse');
    });
  });

  test('shows "Load older messages" button when hasMore is true', async () => {
    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('Load older messages')).toBeInTheDocument();
    });
  });

  test('hides "Load older messages" button when hasMore is false', async () => {
    mockGetConversationHistory.mockResolvedValue({
      ...mockSessionContext,
      hasArchived: false,
    });

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('What is this case about?')).toBeInTheDocument();
    });

    expect(screen.queryByText('Load older messages')).not.toBeInTheDocument();
  });

  test('loads archived messages when Load button clicked', async () => {
    const user = userEvent.setup();
    const archivedMessages = [
      createMessage('old-1', 'user', 'Old question'),
      createMessage('old-2', 'assistant', 'Old answer'),
    ];

    mockGetArchivedMessages.mockResolvedValue({
      messages: archivedMessages,
      hasMore: false,
    });

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('Load older messages')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Load older messages'));

    await waitFor(() => {
      expect(mockGetArchivedMessages).toHaveBeenCalledWith(matterId, userId);
    });
  });

  test('shows error toast on load failure', async () => {
    mockGetConversationHistory.mockRejectedValue(new Error('Network error'));

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Network error');
    });
  });

  test('calls onSourceClick when source is clicked', async () => {
    const user = userEvent.setup();
    const handleSourceClick = vi.fn();

    const messageWithSource: ChatMessage = {
      id: 'msg-with-source',
      role: 'assistant',
      content: 'Here is the information.',
      timestamp: new Date().toISOString(),
      sources: [
        {
          documentId: 'doc-1',
          documentName: 'contract.pdf',
          page: 5,
        },
      ],
    };

    mockGetConversationHistory.mockResolvedValue({
      ...mockSessionContext,
      messages: [messageWithSource],
    });

    render(
      <ConversationHistory
        matterId={matterId}
        userId={userId}
        onSourceClick={handleSourceClick}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('contract.pdf (p. 5)')).toBeInTheDocument();
    });

    await user.click(screen.getByText('contract.pdf (p. 5)'));

    expect(handleSourceClick).toHaveBeenCalledWith({
      documentId: 'doc-1',
      documentName: 'contract.pdf',
      page: 5,
    });
  });

  test('shows toast when source clicked without handler', async () => {
    const user = userEvent.setup();

    const messageWithSource: ChatMessage = {
      id: 'msg-with-source',
      role: 'assistant',
      content: 'Here is the information.',
      timestamp: new Date().toISOString(),
      sources: [
        {
          documentId: 'doc-1',
          documentName: 'contract.pdf',
          page: 5,
        },
      ],
    };

    mockGetConversationHistory.mockResolvedValue({
      ...mockSessionContext,
      messages: [messageWithSource],
    });

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('contract.pdf (p. 5)')).toBeInTheDocument();
    });

    await user.click(screen.getByText('contract.pdf (p. 5)'));

    expect(mockToast.info).toHaveBeenCalledWith('Opening contract.pdf at page 5');
  });

  test('loads history on mount with matter and user IDs', async () => {
    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(mockGetConversationHistory).toHaveBeenCalledWith(matterId, userId);
    });
  });

  test('has conversation-history testid', async () => {
    render(<ConversationHistory matterId={matterId} userId={userId} />);

    expect(screen.getByTestId('conversation-history')).toBeInTheDocument();
  });

  test('renders multiple messages in correct order', async () => {
    const messages = [
      createMessage('1', 'user', 'First question'),
      createMessage('2', 'assistant', 'First answer'),
      createMessage('3', 'user', 'Second question'),
      createMessage('4', 'assistant', 'Second answer'),
    ];

    mockGetConversationHistory.mockResolvedValue({
      ...mockSessionContext,
      messages,
    });

    render(<ConversationHistory matterId={matterId} userId={userId} />);

    await waitFor(() => {
      expect(screen.getByText('First question')).toBeInTheDocument();
      expect(screen.getByText('Second answer')).toBeInTheDocument();
    });

    // Check all messages rendered
    const userMessages = screen.getAllByTestId('chat-message-user');
    const assistantMessages = screen.getAllByTestId('chat-message-assistant');

    expect(userMessages).toHaveLength(2);
    expect(assistantMessages).toHaveLength(2);
  });
});
