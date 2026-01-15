'use client';

import { useCallback } from 'react';
import { toast } from 'sonner';
import { QAPanelHeader } from './QAPanelHeader';
import { ConversationHistory } from './ConversationHistory';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';
import { ChatInput } from './ChatInput';
import { StreamingMessage } from './StreamingMessage';
import { SuggestedQuestions } from './SuggestedQuestions';
import { useChatStore, selectIsEmpty } from '@/stores/chatStore';
import { useSSE, type CompleteData, type EngineTraceData, type TokenData } from '@/hooks/useSSE';
import type { SourceReference, ChatMessage, EngineTrace } from '@/types/chat';

interface QAPanelProps {
  /** Matter ID for loading conversation history */
  matterId?: string;
  /** User ID for loading conversation history */
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
export function QAPanel({ matterId, userId, onSourceClick }: QAPanelProps) {
  // Zustand selectors for streaming state
  const addMessage = useChatStore((state) => state.addMessage);
  const startStreaming = useChatStore((state) => state.startStreaming);
  const appendToken = useChatStore((state) => state.appendToken);
  const addTrace = useChatStore((state) => state.addTrace);
  const completeStreaming = useChatStore((state) => state.completeStreaming);
  const setTyping = useChatStore((state) => state.setTyping);
  const setError = useChatStore((state) => state.setError);

  const isTyping = useChatStore((state) => state.isTyping);
  const streamingContent = useChatStore((state) => state.streamingContent);
  const streamingTraces = useChatStore((state) => state.streamingTraces);
  const streamingMessageId = useChatStore((state) => state.streamingMessageId);

  // Story 11.4: Empty state detection for suggested questions
  const isEmpty = useChatStore(selectIsEmpty);

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
    completeStreaming(data.response, traces, sources);
  }, [completeStreaming]);

  const handleError = useCallback((error: Error) => {
    setError(error.message);
    toast.error(error.message);
    // Reset streaming state on error
    setTyping(false);
  }, [setError, setTyping]);

  // Initialize SSE hook
  // Note: abortStream available but not exposed in UI yet (future story for cancel button)
  const { isStreaming, startStream } = useSSE({
    onTyping: handleTyping,
    onToken: handleToken,
    onEngineComplete: handleEngineComplete,
    onComplete: handleComplete,
    onError: handleError,
  });

  // Handle message submission
  const handleSubmit = useCallback(async (query: string) => {
    if (!matterId || !userId) {
      toast.error('No matter selected');
      return;
    }

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

  // Show placeholder if we don't have matter/user context
  const canLoadHistory = Boolean(matterId && userId);

  // Calculate total time from traces for streaming message (use max since engines run in parallel)
  const streamingTotalTimeMs = streamingTraces.length > 0
    ? Math.max(...streamingTraces.map((t) => t.executionTimeMs))
    : 0;

  return (
    <div className="flex h-full flex-col bg-background">
      <QAPanelHeader />

      <div className="flex flex-1 flex-col overflow-hidden">
        {canLoadHistory ? (
          <>
            {/* Story 11.4: Empty state with suggested questions */}
            {isEmpty && !streamingMessageId ? (
              <div className="flex flex-1 flex-col items-center justify-center p-6">
                <SuggestedQuestions onQuestionClick={handleSubmit} />
              </div>
            ) : (
              <>
                {/* Conversation history */}
                <ConversationHistory
                  matterId={matterId!}
                  userId={userId!}
                  onSourceClick={onSourceClick}
                />

                {/* Streaming message (shown during streaming) */}
                {streamingMessageId && (
                  <StreamingMessage
                    content={streamingContent}
                    isTyping={isTyping}
                    isStreaming={isStreaming}
                    traces={streamingTraces}
                    totalTimeMs={streamingTotalTimeMs}
                  />
                )}
              </>
            )}

            {/* Chat input (always visible) */}
            <ChatInput
              onSubmit={handleSubmit}
              disabled={isStreaming}
              isLoading={isStreaming}
            />
          </>
        ) : (
          <QAPanelPlaceholder />
        )}
      </div>
    </div>
  );
}
