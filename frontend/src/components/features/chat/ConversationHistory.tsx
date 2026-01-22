'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, ChevronUp, ArrowDown } from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';
import { useChatStore } from '@/stores/chatStore';
import type { SourceReference } from '@/types/chat';
import { toast } from 'sonner';

interface ConversationHistoryProps {
  /** Matter ID for loading conversation history */
  matterId: string;
  /** User ID for loading conversation history */
  userId: string;
  /** Callback when a source reference is clicked */
  onSourceClick?: (source: SourceReference) => void;
}

/** Distance from bottom (in pixels) to consider "near bottom" for auto-scroll */
const NEAR_BOTTOM_THRESHOLD = 100;

/**
 * ConversationHistory Component
 *
 * Container component that displays the chat message history with:
 * - Virtualized-like scrolling using ScrollArea
 * - Auto-scroll to bottom on new messages (if user is near bottom)
 * - Load more button for archived messages
 * - Loading and empty states
 *
 * Story 11.2: Implement Q&A Conversation History (AC: #1, #3)
 */
export function ConversationHistory({
  matterId,
  userId,
  onSourceClick,
}: ConversationHistoryProps) {
  const messages = useChatStore((state) => state.messages);
  const isLoading = useChatStore((state) => state.isLoading);
  const error = useChatStore((state) => state.error);
  const hasMore = useChatStore((state) => state.hasMore);
  const loadHistory = useChatStore((state) => state.loadHistory);
  const loadArchivedMessages = useChatStore((state) => state.loadArchivedMessages);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const prevMessageCountRef = useRef(messages.length);

  // Load history on mount
  useEffect(() => {
    if (matterId && userId) {
      loadHistory(matterId, userId);
    }
  }, [matterId, userId, loadHistory]);

  // Handle scroll position tracking
  const handleScroll = useCallback(() => {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    const nearBottom = distanceFromBottom < NEAR_BOTTOM_THRESHOLD;
    setIsNearBottom(nearBottom);
    setShowScrollButton(!nearBottom && messages.length > 0);
  }, [messages.length]);

  // Auto-scroll to bottom when new messages arrive (if user was near bottom)
  useEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer) return;

    // Only auto-scroll if we have new messages and user was near bottom
    if (messages.length > prevMessageCountRef.current && isNearBottom) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }

    prevMessageCountRef.current = messages.length;
  }, [messages.length, isNearBottom]);

  // Scroll to bottom helper
  const scrollToBottom = useCallback(() => {
    const scrollContainer = scrollRef.current;
    if (scrollContainer) {
      scrollContainer.scrollTo({
        top: scrollContainer.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, []);

  // Handle load more archived messages
  const handleLoadMore = useCallback(async () => {
    try {
      await loadArchivedMessages(matterId, userId);
    } catch {
      toast.error('Failed to load older messages');
    }
  }, [matterId, userId, loadArchivedMessages]);

  // Handle source click with PDF viewer integration placeholder
  const handleSourceClick = useCallback(
    (source: SourceReference) => {
      if (onSourceClick) {
        onSourceClick(source);
      } else {
        // Placeholder until Story 11.5 (PDF viewer)
        toast.info(`Opening ${source.documentName}${source.page ? ` at page ${source.page}` : ''}`);
      }
    },
    [onSourceClick]
  );

  // Show error toast when error occurs
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  // Empty state
  if (!isLoading && messages.length === 0) {
    return <QAPanelPlaceholder />;
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Load more button */}
      {hasMore && (
        <div className="flex shrink-0 justify-center border-b bg-background/95 p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLoadMore}
            disabled={isLoading}
            className="gap-2"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ChevronUp className="h-4 w-4" />
            )}
            Load older messages
          </Button>
        </div>
      )}

      {/* Messages list */}
      <div
        ref={scrollRef}
        className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto"
        onScroll={handleScroll}
        data-testid="conversation-history"
      >
        {/* Loading indicator at top when loading more */}
        {isLoading && messages.length > 0 && (
          <div className="flex justify-center p-4">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Initial loading state */}
        {isLoading && messages.length === 0 && (
          <div className="flex flex-1 items-center justify-center p-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Messages */}
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            onSourceClick={handleSourceClick}
          />
        ))}

        {/* Spacer for scroll padding at bottom */}
        <div className="h-4" />
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <Button
          variant="secondary"
          size="icon"
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 rounded-full shadow-lg"
          aria-label="Scroll to bottom"
        >
          <ArrowDown className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
