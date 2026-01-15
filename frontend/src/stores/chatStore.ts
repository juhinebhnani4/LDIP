/**
 * Chat Store
 *
 * Zustand store for Q&A conversation state management.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const messages = useChatStore((state) => state.messages);
 *   const addMessage = useChatStore((state) => state.addMessage);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { messages, addMessage } = useChatStore();
 *
 * Story 11.2: Implement Q&A Conversation History
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { getConversationHistory, getArchivedMessages } from '@/lib/api/chat';
import type { ChatMessage } from '@/types/chat';

// ============================================================================
// Constants
// ============================================================================

export const STORAGE_KEY = 'ldip-chat-history';
export const MAX_PERSISTED_MESSAGES = 20;
export const SLIDING_WINDOW_SIZE = 20;

// ============================================================================
// Types
// ============================================================================

interface ChatState {
  /** Chat messages in the current session */
  messages: ChatMessage[];
  /** Whether a chat operation is in progress */
  isLoading: boolean;
  /** Error message if something went wrong */
  error: string | null;
  /** Whether there are more archived messages to load */
  hasMore: boolean;
  /** Current session ID from backend */
  currentSessionId: string | null;
  /** Matter ID for the current session */
  currentMatterId: string | null;
  /** User ID for the current session */
  currentUserId: string | null;
}

interface ChatActions {
  /** Add a new message to the conversation */
  addMessage: (message: ChatMessage) => void;
  /** Set all messages (used when loading from backend) */
  setMessages: (messages: ChatMessage[]) => void;
  /** Load conversation history from backend */
  loadHistory: (matterId: string, userId: string) => Promise<void>;
  /** Load archived messages from Matter Memory */
  loadArchivedMessages: (matterId: string, userId: string) => Promise<void>;
  /** Clear all messages */
  clearMessages: () => void;
  /** Set loading state */
  setLoading: (loading: boolean) => void;
  /** Set error state */
  setError: (error: string | null) => void;
  /** Reset store to initial state */
  reset: () => void;
}

type ChatStore = ChatState & ChatActions;

// ============================================================================
// Initial State
// ============================================================================

const initialState: ChatState = {
  messages: [],
  isLoading: false,
  error: null,
  hasMore: false,
  currentSessionId: null,
  currentMatterId: null,
  currentUserId: null,
};

// ============================================================================
// Store
// ============================================================================

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      addMessage: (message) => {
        set((state) => ({
          messages: [...state.messages, message],
          error: null,
        }));
      },

      setMessages: (messages) => {
        set({ messages, error: null });
      },

      loadHistory: async (matterId, userId) => {
        const { currentMatterId, currentUserId, messages } = get();

        // If already loaded for this matter/user, don't reload
        if (
          currentMatterId === matterId &&
          currentUserId === userId &&
          messages.length > 0
        ) {
          return;
        }

        set({
          isLoading: true,
          error: null,
          currentMatterId: matterId,
          currentUserId: userId,
        });

        try {
          const response = await getConversationHistory(matterId, userId);
          set({
            messages: response.messages,
            hasMore: response.hasArchived,
            currentSessionId: response.sessionId,
            isLoading: false,
          });
        } catch (error) {
          const errorMessage =
            error instanceof Error ? error.message : 'Failed to load conversation history';
          set({
            error: errorMessage,
            isLoading: false,
          });
        }
      },

      loadArchivedMessages: async (matterId, userId) => {
        const { isLoading, hasMore, messages } = get();

        // Don't load if already loading or no more to load
        if (isLoading || !hasMore) {
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const response = await getArchivedMessages(matterId, userId);
          // Prepend archived messages to existing messages
          set({
            messages: [...response.messages, ...messages],
            hasMore: response.hasMore,
            isLoading: false,
          });
        } catch (error) {
          const errorMessage =
            error instanceof Error ? error.message : 'Failed to load archived messages';
          set({
            error: errorMessage,
            isLoading: false,
          });
        }
      },

      clearMessages: () => {
        set({
          messages: [],
          hasMore: false,
          currentSessionId: null,
        });
      },

      setLoading: (loading) => {
        set({ isLoading: loading });
      },

      setError: (error) => {
        set({ error });
      },

      reset: () => {
        set(initialState);
      },
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        // Only persist essential data for conversation continuity
        messages: state.messages.slice(-MAX_PERSISTED_MESSAGES),
        currentSessionId: state.currentSessionId,
        currentMatterId: state.currentMatterId,
        currentUserId: state.currentUserId,
        // Don't persist loading/error states or hasMore
      }),
    }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for getting the most recent message
 */
export const selectLatestMessage = (state: ChatStore): ChatMessage | undefined => {
  return state.messages[state.messages.length - 1];
};

/**
 * Selector for getting message count
 */
export const selectMessageCount = (state: ChatStore): number => {
  return state.messages.length;
};

/**
 * Selector for checking if conversation is empty
 */
export const selectIsEmpty = (state: ChatStore): boolean => {
  return state.messages.length === 0;
};

/**
 * Selector for checking if we have user messages
 */
export const selectHasUserMessages = (state: ChatStore): boolean => {
  return state.messages.some((m) => m.role === 'user');
};
