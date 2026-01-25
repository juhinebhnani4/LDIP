import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from '@testing-library/react';
import { useChatStore, STORAGE_KEY, MAX_PERSISTED_MESSAGES } from './chatStore';
import type { ChatMessage } from '@/types/chat';

// Mock the chat API
vi.mock('@/lib/api/chat', () => ({
  getConversationHistory: vi.fn(),
  getArchivedMessages: vi.fn(),
}));

import { getConversationHistory, getArchivedMessages } from '@/lib/api/chat';

const mockGetConversationHistory = vi.mocked(getConversationHistory);
const mockGetArchivedMessages = vi.mocked(getArchivedMessages);

describe('chatStore', () => {
  beforeEach(() => {
    // Reset store state
    act(() => {
      useChatStore.getState().reset();
    });
    // Clear mocks
    vi.clearAllMocks();
    // Clear localStorage
    localStorage.removeItem(STORAGE_KEY);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const createMessage = (id: string, role: 'user' | 'assistant'): ChatMessage => ({
    id,
    role,
    content: `Test message ${id}`,
    timestamp: new Date().toISOString(),
  });

  describe('initial state', () => {
    test('starts with empty messages', () => {
      expect(useChatStore.getState().messages).toEqual([]);
    });

    test('starts with isLoading false', () => {
      expect(useChatStore.getState().isLoading).toBe(false);
    });

    test('starts with error null', () => {
      expect(useChatStore.getState().error).toBeNull();
    });

    test('starts with hasMore false', () => {
      expect(useChatStore.getState().hasMore).toBe(false);
    });
  });

  describe('addMessage', () => {
    test('adds a message to the list', () => {
      const message = createMessage('1', 'user');
      act(() => {
        useChatStore.getState().addMessage(message);
      });
      expect(useChatStore.getState().messages).toHaveLength(1);
      expect(useChatStore.getState().messages[0]).toEqual(message);
    });

    test('appends new messages to the end', () => {
      const message1 = createMessage('1', 'user');
      const message2 = createMessage('2', 'assistant');
      act(() => {
        useChatStore.getState().addMessage(message1);
        useChatStore.getState().addMessage(message2);
      });
      expect(useChatStore.getState().messages).toHaveLength(2);
      expect(useChatStore.getState().messages[0]!.id).toBe('1');
      expect(useChatStore.getState().messages[1]!.id).toBe('2');
    });

    test('clears error when adding message', () => {
      act(() => {
        useChatStore.getState().setError('Some error');
      });
      expect(useChatStore.getState().error).toBe('Some error');

      act(() => {
        useChatStore.getState().addMessage(createMessage('1', 'user'));
      });
      expect(useChatStore.getState().error).toBeNull();
    });
  });

  describe('setMessages', () => {
    test('replaces all messages', () => {
      act(() => {
        useChatStore.getState().addMessage(createMessage('old', 'user'));
      });
      expect(useChatStore.getState().messages).toHaveLength(1);

      const newMessages = [createMessage('1', 'user'), createMessage('2', 'assistant')];
      act(() => {
        useChatStore.getState().setMessages(newMessages);
      });
      expect(useChatStore.getState().messages).toHaveLength(2);
      expect(useChatStore.getState().messages[0]!.id).toBe('1');
    });

    test('clears error when setting messages', () => {
      act(() => {
        useChatStore.getState().setError('Some error');
        useChatStore.getState().setMessages([]);
      });
      expect(useChatStore.getState().error).toBeNull();
    });
  });

  describe('loadHistory', () => {
    const mockSessionContext = {
      sessionId: 'session-1',
      matterId: 'matter-1',
      userId: 'user-1',
      messages: [createMessage('1', 'user'), createMessage('2', 'assistant')],
      entities: [],
      hasArchived: true,
    };

    test('sets loading state during fetch', async () => {
      mockGetConversationHistory.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockSessionContext), 100))
      );

      const promise = act(async () => {
        useChatStore.getState().loadHistory('matter-1', 'user-1');
      });

      // Check loading state immediately
      expect(useChatStore.getState().isLoading).toBe(true);

      await promise;
      await vi.waitFor(() => {
        expect(useChatStore.getState().isLoading).toBe(false);
      });
    });

    test('loads messages from API', async () => {
      mockGetConversationHistory.mockResolvedValue(mockSessionContext);

      await act(async () => {
        await useChatStore.getState().loadHistory('matter-1', 'user-1');
      });

      expect(useChatStore.getState().messages).toHaveLength(2);
      expect(useChatStore.getState().hasMore).toBe(true);
      expect(useChatStore.getState().currentSessionId).toBe('session-1');
    });

    test('sets error on failure', async () => {
      mockGetConversationHistory.mockRejectedValue(new Error('Network error'));

      await act(async () => {
        await useChatStore.getState().loadHistory('matter-1', 'user-1');
      });

      expect(useChatStore.getState().error).toBe('Network error');
      expect(useChatStore.getState().isLoading).toBe(false);
    });

    test('does not reload if already loaded for same matter/user', async () => {
      mockGetConversationHistory.mockResolvedValue(mockSessionContext);

      await act(async () => {
        await useChatStore.getState().loadHistory('matter-1', 'user-1');
      });

      expect(mockGetConversationHistory).toHaveBeenCalledTimes(1);

      await act(async () => {
        await useChatStore.getState().loadHistory('matter-1', 'user-1');
      });

      // Should not call API again
      expect(mockGetConversationHistory).toHaveBeenCalledTimes(1);
    });

    test('reloads for different matter', async () => {
      mockGetConversationHistory.mockResolvedValue(mockSessionContext);

      await act(async () => {
        await useChatStore.getState().loadHistory('matter-1', 'user-1');
      });

      expect(mockGetConversationHistory).toHaveBeenCalledTimes(1);

      await act(async () => {
        await useChatStore.getState().loadHistory('matter-2', 'user-1');
      });

      expect(mockGetConversationHistory).toHaveBeenCalledTimes(2);
    });
  });

  describe('loadArchivedMessages', () => {
    const mockArchivedResponse = {
      messages: [createMessage('old-1', 'user'), createMessage('old-2', 'assistant')],
      hasMore: false,
    };

    beforeEach(async () => {
      // Set up initial state with hasMore = true
      act(() => {
        useChatStore.setState({
          messages: [createMessage('new-1', 'user')],
          hasMore: true,
          currentMatterId: 'matter-1',
          currentUserId: 'user-1',
        });
      });
    });

    test('prepends archived messages to existing', async () => {
      mockGetArchivedMessages.mockResolvedValue(mockArchivedResponse);

      await act(async () => {
        await useChatStore.getState().loadArchivedMessages('matter-1', 'user-1');
      });

      expect(useChatStore.getState().messages).toHaveLength(3);
      expect(useChatStore.getState().messages[0]!.id).toBe('old-1');
      expect(useChatStore.getState().messages[2]!.id).toBe('new-1');
    });

    test('updates hasMore flag', async () => {
      mockGetArchivedMessages.mockResolvedValue(mockArchivedResponse);

      await act(async () => {
        await useChatStore.getState().loadArchivedMessages('matter-1', 'user-1');
      });

      expect(useChatStore.getState().hasMore).toBe(false);
    });

    test('does not load if hasMore is false', async () => {
      act(() => {
        useChatStore.setState({ hasMore: false });
      });

      await act(async () => {
        await useChatStore.getState().loadArchivedMessages('matter-1', 'user-1');
      });

      expect(mockGetArchivedMessages).not.toHaveBeenCalled();
    });

    test('does not load if already loading', async () => {
      act(() => {
        useChatStore.setState({ isLoading: true });
      });

      await act(async () => {
        await useChatStore.getState().loadArchivedMessages('matter-1', 'user-1');
      });

      expect(mockGetArchivedMessages).not.toHaveBeenCalled();
    });

    test('sets error on failure', async () => {
      mockGetArchivedMessages.mockRejectedValue(new Error('Archive error'));

      await act(async () => {
        await useChatStore.getState().loadArchivedMessages('matter-1', 'user-1');
      });

      expect(useChatStore.getState().error).toBe('Archive error');
    });
  });

  describe('clearMessages', () => {
    test('clears all messages', () => {
      act(() => {
        useChatStore.getState().addMessage(createMessage('1', 'user'));
        useChatStore.getState().clearMessages();
      });
      expect(useChatStore.getState().messages).toEqual([]);
    });

    test('resets hasMore and sessionId', () => {
      act(() => {
        useChatStore.setState({
          hasMore: true,
          currentSessionId: 'session-1',
        });
        useChatStore.getState().clearMessages();
      });
      expect(useChatStore.getState().hasMore).toBe(false);
      expect(useChatStore.getState().currentSessionId).toBeNull();
    });
  });

  describe('setLoading', () => {
    test('sets loading state', () => {
      act(() => {
        useChatStore.getState().setLoading(true);
      });
      expect(useChatStore.getState().isLoading).toBe(true);

      act(() => {
        useChatStore.getState().setLoading(false);
      });
      expect(useChatStore.getState().isLoading).toBe(false);
    });
  });

  describe('setError', () => {
    test('sets error message', () => {
      act(() => {
        useChatStore.getState().setError('Test error');
      });
      expect(useChatStore.getState().error).toBe('Test error');
    });

    test('clears error when set to null', () => {
      act(() => {
        useChatStore.getState().setError('Test error');
        useChatStore.getState().setError(null);
      });
      expect(useChatStore.getState().error).toBeNull();
    });
  });

  describe('reset', () => {
    test('resets all state to initial values', () => {
      act(() => {
        useChatStore.setState({
          messages: [createMessage('1', 'user')],
          isLoading: true,
          error: 'Some error',
          hasMore: true,
          currentSessionId: 'session-1',
          currentMatterId: 'matter-1',
          currentUserId: 'user-1',
        });
        useChatStore.getState().reset();
      });

      const state = useChatStore.getState();
      expect(state.messages).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.hasMore).toBe(false);
      expect(state.currentSessionId).toBeNull();
      expect(state.currentMatterId).toBeNull();
      expect(state.currentUserId).toBeNull();
    });
  });

  describe('streaming actions', () => {
    describe('startStreaming', () => {
      test('sets streaming state', () => {
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
        });
        expect(useChatStore.getState().streamingMessageId).toBe('msg-1');
        expect(useChatStore.getState().streamingContent).toBe('');
        expect(useChatStore.getState().streamingTraces).toEqual([]);
        expect(useChatStore.getState().isTyping).toBe(true);
        expect(useChatStore.getState().error).toBeNull();
      });
    });

    describe('appendToken', () => {
      test('updates streaming content and disables typing', () => {
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().appendToken('Hello', 'Hello');
        });
        expect(useChatStore.getState().streamingContent).toBe('Hello');
        expect(useChatStore.getState().isTyping).toBe(false);
      });
    });

    describe('addTrace', () => {
      test('appends trace to streaming traces', () => {
        const trace = {
          engine: 'rag',
          executionTimeMs: 100,
          findingsCount: 5,
          success: true,
        };
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().addTrace(trace);
        });
        expect(useChatStore.getState().streamingTraces).toHaveLength(1);
        expect(useChatStore.getState().streamingTraces[0]).toEqual(trace);
      });
    });

    describe('completeStreaming', () => {
      test('creates completed message with isComplete=true', () => {
        const trace = {
          engine: 'rag',
          executionTimeMs: 100,
          findingsCount: 5,
          success: true,
        };
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().appendToken('Test', 'Test response');
          useChatStore.getState().completeStreaming('Final response', [trace], undefined);
        });

        const messages = useChatStore.getState().messages;
        expect(messages).toHaveLength(1);
        expect(messages[0]!.id).toBe('msg-1');
        expect(messages[0]!.content).toBe('Final response');
        expect(messages[0]!.isComplete).toBe(true);
        expect(useChatStore.getState().streamingMessageId).toBeNull();
      });

      test('includes optimistic RAG metadata', () => {
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().completeStreaming(
            'Response',
            [],
            undefined,
            'Search notice',
            'bm25_fallback',
            75
          );
        });

        const msg = useChatStore.getState().messages[0];
        expect(msg!.searchNotice).toBe('Search notice');
        expect(msg!.searchMode).toBe('bm25_fallback');
        expect(msg!.embeddingCompletionPct).toBe(75);
      });
    });

    describe('abortStreaming', () => {
      test('saves incomplete message with isComplete=false when content exists', () => {
        const trace = {
          engine: 'rag',
          executionTimeMs: 50,
          findingsCount: 2,
          success: true,
        };
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().appendToken('Partial', 'Partial response');
          useChatStore.getState().addTrace(trace);
          useChatStore.getState().abortStreaming();
        });

        const messages = useChatStore.getState().messages;
        expect(messages).toHaveLength(1);
        expect(messages[0]!.id).toBe('msg-1');
        expect(messages[0]!.content).toBe('Partial response');
        expect(messages[0]!.isComplete).toBe(false);
        expect(messages[0]!.engineTraces).toHaveLength(1);
        expect(useChatStore.getState().streamingMessageId).toBeNull();
      });

      test('does not save message when content is empty', () => {
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().abortStreaming();
        });

        expect(useChatStore.getState().messages).toHaveLength(0);
        expect(useChatStore.getState().streamingMessageId).toBeNull();
      });

      test('does not save message when content is whitespace only', () => {
        act(() => {
          useChatStore.getState().startStreaming('msg-1');
          useChatStore.getState().appendToken('   ', '   ');
          useChatStore.getState().abortStreaming();
        });

        expect(useChatStore.getState().messages).toHaveLength(0);
      });

      test('does nothing when not streaming', () => {
        act(() => {
          useChatStore.getState().abortStreaming();
        });
        // Should not throw, just do nothing
        expect(useChatStore.getState().messages).toHaveLength(0);
      });
    });

    describe('setTyping', () => {
      test('sets typing indicator', () => {
        act(() => {
          useChatStore.getState().setTyping(true);
        });
        expect(useChatStore.getState().isTyping).toBe(true);

        act(() => {
          useChatStore.getState().setTyping(false);
        });
        expect(useChatStore.getState().isTyping).toBe(false);
      });
    });
  });

  describe('persistence', () => {
    test('persists only last N messages', () => {
      // Create more than MAX_PERSISTED_MESSAGES
      const messages: ChatMessage[] = [];
      for (let i = 0; i < MAX_PERSISTED_MESSAGES + 5; i++) {
        messages.push(createMessage(`msg-${i}`, i % 2 === 0 ? 'user' : 'assistant'));
      }

      act(() => {
        useChatStore.getState().setMessages(messages);
      });

      // Get persisted state
      const persistedData = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      expect(persistedData.state.messages.length).toBe(MAX_PERSISTED_MESSAGES);
    });

    test('persists session metadata', () => {
      act(() => {
        useChatStore.setState({
          currentSessionId: 'session-123',
          currentMatterId: 'matter-456',
          currentUserId: 'user-789',
        });
      });

      const persistedData = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      expect(persistedData.state.currentSessionId).toBe('session-123');
      expect(persistedData.state.currentMatterId).toBe('matter-456');
      expect(persistedData.state.currentUserId).toBe('user-789');
    });
  });
});
