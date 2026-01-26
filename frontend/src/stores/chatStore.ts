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
 * Story 11.3: Streaming Response with Engine Trace
 */

import { create } from 'zustand';
import { persist, createJSONStorage, type StateStorage } from 'zustand/middleware';
import { getConversationHistory, getArchivedMessages } from '@/lib/api/chat';
import type { ChatMessage, EngineTrace, SourceReference } from '@/types/chat';

// ============================================================================
// Constants
// ============================================================================

/** @deprecated Use getStorageKey() for matter-specific keys */
export const STORAGE_KEY = 'ldip-chat-history';
export const STORAGE_KEY_PREFIX = 'ldip-chat-history';
export const MAX_PERSISTED_MESSAGES = 20;
export const SLIDING_WINDOW_SIZE = 20;

/**
 * Generate matter-specific storage key for localStorage.
 * Ensures chat history is isolated per matter.
 */
export const getStorageKey = (matterId: string | null): string =>
  matterId ? `${STORAGE_KEY_PREFIX}:${matterId}` : STORAGE_KEY_PREFIX;

// ============================================================================
// Matter-Aware Storage Adapter
// ============================================================================

/**
 * Custom storage adapter that uses matter-specific localStorage keys.
 * This ensures chat histories are isolated per matter, preventing cross-contamination.
 */
const createMatterAwareStorage = (): StateStorage => {
  // Track current matter for storage operations
  let currentMatterId: string | null = null;

  return {
    getItem: (name: string): string | null => {
      if (typeof window === 'undefined') return null;

      // If we have a current matter, try its specific key first
      if (currentMatterId) {
        const matterKey = getStorageKey(currentMatterId);
        const matterData = localStorage.getItem(matterKey);
        if (matterData) return matterData;
      }

      // Fallback: check for legacy global key (for migration)
      const globalData = localStorage.getItem(STORAGE_KEY_PREFIX);
      if (globalData && currentMatterId) {
        // Migrate to matter-specific key if it matches
        try {
          const parsed = JSON.parse(globalData);
          const storedMatterId = parsed?.state?.currentMatterId;
          if (!storedMatterId || storedMatterId === currentMatterId) {
            // This data belongs to current matter, migrate it
            const matterKey = getStorageKey(currentMatterId);
            localStorage.setItem(matterKey, globalData);
            localStorage.removeItem(STORAGE_KEY_PREFIX);
            return globalData;
          }
        } catch {
          // Ignore parse errors
        }
      }

      return null;
    },

    setItem: (name: string, value: string): void => {
      if (typeof window === 'undefined') return;

      try {
        const parsed = JSON.parse(value);
        const matterId = parsed?.state?.currentMatterId;

        if (matterId) {
          currentMatterId = matterId;
          const matterKey = getStorageKey(matterId);
          localStorage.setItem(matterKey, value);
        }
      } catch {
        // Fallback to global key if parsing fails
        localStorage.setItem(STORAGE_KEY_PREFIX, value);
      }
    },

    removeItem: (name: string): void => {
      if (typeof window === 'undefined') return;

      if (currentMatterId) {
        localStorage.removeItem(getStorageKey(currentMatterId));
      }
      // Also clean up legacy global key if it exists
      localStorage.removeItem(STORAGE_KEY_PREFIX);
    },
  };
};

/**
 * Migrate chat history from global localStorage to matter-specific key.
 * Call this when loading a matter for the first time after upgrade.
 */
export function migrateGlobalChatHistory(matterId: string): boolean {
  if (typeof window === 'undefined') return false;

  const globalKey = STORAGE_KEY_PREFIX;
  const matterKey = getStorageKey(matterId);

  // Skip if matter already has its own data
  if (localStorage.getItem(matterKey)) {
    return false;
  }

  const globalData = localStorage.getItem(globalKey);
  if (!globalData) return false;

  try {
    const parsed = JSON.parse(globalData);
    const storedMatterId = parsed?.state?.currentMatterId;

    // Only migrate if the stored data belongs to this matter or has no matter
    if (!storedMatterId || storedMatterId === matterId) {
      localStorage.setItem(matterKey, globalData);
      localStorage.removeItem(globalKey);
      return true;
    }
  } catch {
    // Ignore parse errors
  }

  return false;
}

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
  /** Story 11.3: Streaming state */
  /** ID of message currently being streamed */
  streamingMessageId: string | null;
  /** Accumulated content during streaming */
  streamingContent: string;
  /** Engine traces accumulated during streaming */
  streamingTraces: EngineTrace[];
  /** Whether typing indicator should show */
  isTyping: boolean;
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
  /** Story 11.3: Start streaming a new response */
  startStreaming: (messageId: string) => void;
  /** Story 11.3: Append token to streaming content */
  appendToken: (token: string, accumulated: string) => void;
  /** Story 11.3: Add engine trace during streaming */
  addTrace: (trace: EngineTrace) => void;
  /** Story 11.3: Complete streaming and finalize message */
  completeStreaming: (
    finalContent: string,
    traces: EngineTrace[],
    sources?: SourceReference[],
    searchNotice?: string,
    searchMode?: 'hybrid' | 'bm25_only' | 'bm25_fallback',
    embeddingCompletionPct?: number,
    queryWasRewritten?: boolean,
    originalQuery?: string
  ) => void;
  /**
   * Story 2.3: Abort streaming and save incomplete message.
   * Called when stream is interrupted (error, timeout, or user abort).
   */
  abortStreaming: () => void;
  /** Story 11.3: Set typing indicator */
  setTyping: (isTyping: boolean) => void;
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
  // Story 11.3: Streaming state
  streamingMessageId: null,
  streamingContent: '',
  streamingTraces: [],
  isTyping: false,
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

        // CRITICAL: Clear state when switching matters to prevent cross-contamination
        const isSwitchingMatters = currentMatterId !== null && currentMatterId !== matterId;
        if (isSwitchingMatters) {
          set({
            messages: [],
            hasMore: false,
            currentSessionId: null,
            streamingMessageId: null,
            streamingContent: '',
            streamingTraces: [],
            isTyping: false,
          });
        }

        set({
          isLoading: true,
          error: null,
          currentMatterId: matterId,
          currentUserId: userId,
        });

        // Attempt migration from global localStorage key (one-time)
        migrateGlobalChatHistory(matterId);

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

      // Story 11.3: Streaming actions
      startStreaming: (messageId) => {
        set({
          streamingMessageId: messageId,
          streamingContent: '',
          streamingTraces: [],
          isTyping: true,
          error: null,
        });
      },

      appendToken: (_token, accumulated) => {
        set({
          streamingContent: accumulated,
          isTyping: false,
        });
      },

      addTrace: (trace) => {
        set((state) => ({
          streamingTraces: [...state.streamingTraces, trace],
        }));
      },

      completeStreaming: (finalContent, traces, sources, searchNotice, searchMode, embeddingCompletionPct, queryWasRewritten, originalQuery) => {
        const { streamingMessageId, messages } = get();
        if (!streamingMessageId) return;

        // Create the completed assistant message
        // Story 2.3: Mark as complete since we received proper 'complete' event
        const completedMessage: ChatMessage = {
          id: streamingMessageId,
          role: 'assistant',
          content: finalContent,
          timestamp: new Date().toISOString(),
          engineTraces: traces,
          sources: sources,
          // Optimistic RAG metadata
          searchNotice,
          searchMode,
          embeddingCompletionPct,
          // Story 2.3: Mark as successfully completed
          isComplete: true,
          // Query safety rewrite metadata
          queryWasRewritten,
          originalQuery,
        };

        set({
          messages: [...messages, completedMessage],
          streamingMessageId: null,
          streamingContent: '',
          streamingTraces: [],
          isTyping: false,
        });
      },

      // Story 2.3: Abort streaming and save incomplete message
      abortStreaming: () => {
        const { streamingMessageId, streamingContent, streamingTraces, messages } = get();
        if (!streamingMessageId) return;

        // Only save message if there's some content
        if (streamingContent.trim()) {
          const incompleteMessage: ChatMessage = {
            id: streamingMessageId,
            role: 'assistant',
            content: streamingContent,
            timestamp: new Date().toISOString(),
            engineTraces: streamingTraces,
            // Story 2.3: Mark as incomplete
            isComplete: false,
          };

          set({
            messages: [...messages, incompleteMessage],
            streamingMessageId: null,
            streamingContent: '',
            streamingTraces: [],
            isTyping: false,
          });
        } else {
          // No content, just clear streaming state
          set({
            streamingMessageId: null,
            streamingContent: '',
            streamingTraces: [],
            isTyping: false,
          });
        }
      },

      setTyping: (isTyping) => {
        set({ isTyping });
      },
    }),
    {
      name: STORAGE_KEY_PREFIX, // Base name (actual key is matter-specific)
      storage: createJSONStorage(() => createMatterAwareStorage()),
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

/**
 * Story 11.3: Selector for checking if streaming is active
 */
export const selectIsStreaming = (state: ChatStore): boolean => {
  return state.streamingMessageId !== null;
};

/**
 * Story 11.3: Selector for streaming content
 */
export const selectStreamingContent = (state: ChatStore): string => {
  return state.streamingContent;
};

/**
 * Story 11.3: Selector for streaming traces
 */
export const selectStreamingTraces = (state: ChatStore): EngineTrace[] => {
  return state.streamingTraces;
};
