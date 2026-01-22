'use client';

import { cn } from '@/lib/utils';
import { formatDistanceToNow, isValid } from 'date-fns';
import { User, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { SourceReference } from './SourceReference';
import { EngineTrace } from './EngineTrace';
import type { ChatMessage as ChatMessageType, SourceReference as SourceReferenceType } from '@/types/chat';

interface ChatMessageProps {
  /** The message to display */
  message: ChatMessageType;
  /** Callback when a source reference is clicked */
  onSourceClick?: (source: SourceReferenceType) => void;
}

/**
 * ChatMessage Component
 *
 * Displays a single chat message bubble with proper alignment based on role.
 * User messages appear on the right with primary styling.
 * Assistant messages appear on the left with muted styling and may include source references.
 *
 * Story 11.2: Implement Q&A Conversation History (AC: #1)
 * Story 11.3: Streaming Response with Engine Trace (AC: #2-3)
 */
/**
 * Format timestamp with fallback for invalid dates.
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  if (!isValid(date)) {
    return 'Unknown time';
  }
  return formatDistanceToNow(date, { addSuffix: true });
}

export function ChatMessage({ message, onSourceClick }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const roleLabel = isUser ? 'Your message' : 'LDIP assistant message';

  return (
    <article
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
      data-testid={`chat-message-${message.role}`}
      aria-label={roleLabel}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        )}
        aria-hidden="true"
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message bubble */}
      <div
        className={cn(
          'flex min-w-0 max-w-[80%] flex-col gap-1',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        <div
          className={cn(
            'min-w-0 max-w-full overflow-hidden rounded-lg px-4 py-2 text-sm',
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-foreground'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none break-words prose-p:my-2 prose-ul:my-2 prose-ul:pl-4 prose-li:my-1 prose-strong:text-foreground prose-headings:mt-3 prose-headings:mb-1">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}

          {/* Source references (assistant only) */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1 border-t border-border/50 pt-2">
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
          {formatTimestamp(message.timestamp)}
        </span>

        {/* Engine trace (assistant only) - Story 11.3 */}
        {/* Note: Use max instead of sum since engines run in parallel */}
        {!isUser && message.engineTraces && message.engineTraces.length > 0 && (
          <EngineTrace
            traces={message.engineTraces}
            totalTimeMs={Math.max(
              ...message.engineTraces.map((t) => t.executionTimeMs)
            )}
          />
        )}
      </div>
    </article>
  );
}
