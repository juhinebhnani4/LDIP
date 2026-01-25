'use client';

import { useCallback, useState, useRef, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { QAPanelHeader } from './QAPanelHeader';
import { ConversationHistory } from './ConversationHistory';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';
import { ChatInput } from './ChatInput';
import { StreamingMessage } from './StreamingMessage';
import { SuggestedQuestions } from './SuggestedQuestions';
import { ErrorAlert } from '@/components/ui/error-alert';
import { useChatStore, selectIsEmpty } from '@/stores/chatStore';
import { useSSE, type CompleteData, type EngineTraceData, type TokenData, type SSEParseErrorContext } from '@/hooks/useSSE';
import { useUser } from '@/hooks/useAuth';
import { canRetryError } from '@/lib/api/client';
import type { SourceReference, ChatMessage, EngineTrace } from '@/types/chat';

interface QAPanelProps {
  /** Matter ID for loading conversation history */
  matterId?: string;
  /** User ID for loading conversation history (optional - will use auth if not provided) */
  userId?: string;
  /** Callback when a source reference is clicked */
  onSourceClick?: (source: SourceReference) => void;
}

/**
 * Q&A Panel Component
 *
 * Main container for the Q&A panel, containing the header with position
 * controls, conversation history, streaming message, and chat input.
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 * Story 11.2: Implement Q&A Conversation History
 * Story 11.3: Streaming Response with Engine Trace
 * Story 11.4: Suggested Questions and Message Input
 */
export function QAPanel({ matterId, userId: userIdProp, onSourceClick }: QAPanelProps) {
  // Get user from auth if not provided as prop
  const { user, loading: authLoading } = useUser();
  const userId = userIdProp ?? user?.id;
  // Zustand selectors for streaming state
  const addMessage = useChatStore((state) => state.addMessage);
  const startStreaming = useChatStore((state) => state.startStreaming);
  const appendToken = useChatStore((state) => state.appendToken);
  const addTrace = useChatStore((state) => state.addTrace);
  const completeStreaming = useChatStore((state) => state.completeStreaming);
  const abortStreaming = useChatStore((state) => state.abortStreaming);
  const setTyping = useChatStore((state) => state.setTyping);
  const setError = useChatStore((state) => state.setError);

  const isTyping = useChatStore((state) => state.isTyping);
  const streamingContent = useChatStore((state) => state.streamingContent);
  const streamingTraces = useChatStore((state) => state.streamingTraces);
  const streamingMessageId = useChatStore((state) => state.streamingMessageId);

  // Story 11.4: Empty state detection for suggested questions
  const isEmpty = useChatStore(selectIsEmpty);

  // Story 13.4: Track last query and error for retry functionality
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<Error | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  // F5: Track last parse error toast time to debounce multiple errors
  const lastParseErrorToastRef = useRef<number>(0);
  const PARSE_ERROR_TOAST_DEBOUNCE_MS = 2000;

  // Convert EngineTraceData from hook to EngineTrace type
  const convertTrace = useCallback((data: EngineTraceData): EngineTrace => ({
    engine: data.engine,
    executionTimeMs: data.executionTimeMs,
    findingsCount: data.findingsCount,
    success: data.success,
    error: data.error,
  }), []);

  // SSE hook callbacks
  const handleTyping = useCallback(() => {
    setTyping(true);
  }, [setTyping]);

  const handleToken = useCallback((data: TokenData) => {
    appendToken(data.token, data.accumulated);
  }, [appendToken]);

  const handleEngineComplete = useCallback((data: EngineTraceData) => {
    addTrace(convertTrace(data));
  }, [addTrace, convertTrace]);

  const handleComplete = useCallback((data: CompleteData) => {
    const traces: EngineTrace[] = data.engineTraces.map((t) => ({
      engine: t.engine,
      executionTimeMs: t.executionTimeMs,
      findingsCount: t.findingsCount,
      success: t.success,
      error: t.error,
    }));
    // Convert sources from hook data to SourceReference type
    const sources: SourceReference[] = data.sources.map((s) => ({
      documentId: s.documentId,
      documentName: s.documentName ?? 'Unknown Document',
      page: s.page,
      chunkId: s.chunkId,
      confidence: s.confidence,
    }));
    // DEBUG: Log sources before storing
    if (process.env.NODE_ENV === 'development') {
      console.log('[QAPanel] handleComplete sources:', sources.map(s => ({
        documentId: s.documentId.slice(0, 8) + '...',
        documentName: s.documentName,
        page: s.page,
      })));
    }
    completeStreaming(
      data.response,
      traces,
      sources,
      data.searchNotice,
      data.searchMode,
      data.embeddingCompletionPct
    );
    // Story 13.4: Clear error state on success
    setStreamError(null);
    setIsRetrying(false);
  }, [completeStreaming]);

  const handleError = useCallback((error: Error) => {
    setError(error.message);
    // Story 13.4: Store error for inline retry display
    setStreamError(error);
    setIsRetrying(false);
    // Reset streaming state on error
    setTyping(false);
    // Only show toast for non-retryable errors
    if (!canRetryError(error)) {
      toast.error(error.message);
    }
  }, [setError, setTyping]);

  /**
   * Story 2.2: Handle SSE JSON parse errors with toast notification.
   * Shows user-friendly error message without retry action in toast
   * (retry is available via the ErrorAlert component below).
   * F3: Includes sessionId for correlation.
   * F5: Debounces multiple rapid errors to avoid toast spam.
   */
  const handleParseError = useCallback((context: SSEParseErrorContext) => {
    // F5: Debounce multiple parse errors within 2 seconds
    const now = Date.now();
    if (now - lastParseErrorToastRef.current < PARSE_ERROR_TOAST_DEBOUNCE_MS) {
      return; // Skip toast, already shown recently
    }
    lastParseErrorToastRef.current = now;

    // Story 2.2: Show toast within 500ms (sonner is immediate)
    // F3: Include sessionId in description for debugging correlation
    toast.error('Response interrupted — please retry', {
      description: `Some data could not be processed. Your response may be incomplete. (Session: ${context.sessionId.slice(-8)})`,
      duration: 10000, // 10 seconds before auto-dismiss
    });

    // Log to console for debugging (context already logged in useSSE)
    if (process.env.NODE_ENV === 'development') {
      console.log('[QAPanel] SSE parse error received:', context.sessionId);
    }
  }, []);

  // Initialize SSE hook
  // Story 2.1/2.2: Added onParseError for SSE JSON parse error handling
  // F4: Now extracting wasInterrupted to wire up abortStreaming
  const { isStreaming, startStream, wasInterrupted } = useSSE({
    onTyping: handleTyping,
    onToken: handleToken,
    onEngineComplete: handleEngineComplete,
    onComplete: handleComplete,
    onError: handleError,
    onParseError: handleParseError,
  });

  // F4: Wire up wasInterrupted to call abortStreaming when stream is interrupted
  useEffect(() => {
    if (wasInterrupted && !isStreaming) {
      abortStreaming();
    }
  }, [wasInterrupted, isStreaming, abortStreaming]);

  // Handle message submission
  const handleSubmit = useCallback(async (query: string) => {
    if (!matterId || !userId) {
      toast.error('No matter selected');
      return;
    }

    // Story 13.4: Store query for potential retry
    setLastQuery(query);
    setStreamError(null);

    // Create user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date().toISOString(),
    };

    // Add user message to store
    addMessage(userMessage);

    // Start streaming for assistant response
    const assistantMessageId = crypto.randomUUID();
    startStreaming(assistantMessageId);

    // Start SSE stream
    await startStream(`/api/chat/${matterId}/stream`, { query });
  }, [matterId, userId, addMessage, startStreaming, startStream]);

  // Story 13.4: Handle retry for failed queries
  const handleRetry = useCallback(async () => {
    if (!lastQuery) return;
    setIsRetrying(true);
    setStreamError(null);
    await handleSubmit(lastQuery);
  }, [lastQuery, handleSubmit]);

  // Story 13.4: Dismiss error without retrying
  const handleDismissError = useCallback(() => {
    setStreamError(null);
    setLastQuery(null);
  }, []);

  // Show loading state while auth is loading, placeholder if no matter/user context
  const isAuthReady = !authLoading;
  const canLoadHistory = Boolean(matterId && userId);

  // Calculate total time from traces for streaming message (use max since engines run in parallel)
  const streamingTotalTimeMs = streamingTraces.length > 0
    ? Math.max(...streamingTraces.map((t) => t.executionTimeMs))
    : 0;

  // Render content based on state
  const renderContent = () => {
    // Show loading spinner while auth is loading
    if (!isAuthReady) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      );
    }

    // Show placeholder if no matter context
    if (!canLoadHistory) {
      return <QAPanelPlaceholder />;
    }

    // Show chat interface
    return (
      <>
        {/* Story 11.4: Empty state with suggested questions */}
        {isEmpty && !streamingMessageId ? (
          <div className="flex flex-1 flex-col items-center justify-center p-6">
            <SuggestedQuestions onQuestionClick={handleSubmit} />
          </div>
        ) : (
          /* Conversation history with streaming message inside scroll area */
          <ConversationHistory
            matterId={matterId!}
            userId={userId!}
            onSourceClick={onSourceClick}
          >
            {/* Streaming message (shown during streaming) - inside scroll area */}
            {streamingMessageId && (
              <StreamingMessage
                content={streamingContent}
                isTyping={isTyping}
                isStreaming={isStreaming}
                traces={streamingTraces}
                totalTimeMs={streamingTotalTimeMs}
              />
            )}
          </ConversationHistory>
        )}

        {/* Story 13.4: Inline error alert for streaming errors */}
        {streamError && canRetryError(streamError) && (
          <div className="shrink-0 px-4 py-2">
            <ErrorAlert
              error={streamError}
              onRetry={handleRetry}
              onDismiss={handleDismissError}
              isRetrying={isRetrying}
            />
          </div>
        )}

        {/* Chat input (always visible at bottom) */}
        <ChatInput
          onSubmit={handleSubmit}
          disabled={isStreaming}
          isLoading={isStreaming}
          className="shrink-0"
        />
      </>
    );
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <QAPanelHeader />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {renderContent()}
      </div>
    </div>
  );
}
