/**
 * StreamingMessage Component
 *
 * Displays the streaming assistant message with typing indicator,
 * accumulated content, and real-time engine traces.
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 11: Wire up QAPanel with streaming (AC: #1-3)
 */

'use client';

import { cn } from '@/lib/utils';
import { Bot } from 'lucide-react';
import { StreamingResponse } from './StreamingResponse';
import { EngineTrace } from './EngineTrace';
import type { EngineTrace as EngineTraceType } from '@/types/chat';

interface StreamingMessageProps {
  /** Accumulated response content */
  content: string;
  /** Whether typing indicator should show */
  isTyping: boolean;
  /** Whether streaming is currently active */
  isStreaming: boolean;
  /** Engine traces received so far */
  traces: EngineTraceType[];
  /** Total processing time so far */
  totalTimeMs: number;
  /** Optional CSS classes */
  className?: string;
}

/**
 * StreamingMessage Component
 *
 * Story 11.3: Combined streaming message display.
 *
 * Shows the AI response as it streams in with:
 * - Bot avatar (aligned left like assistant messages)
 * - Typing indicator when waiting for content
 * - Accumulated text with cursor animation
 * - Real-time engine trace updates
 *
 * @example
 * <StreamingMessage
 *   content={streamingContent}
 *   isTyping={isTyping}
 *   isStreaming={isStreaming}
 *   traces={streamingTraces}
 *   totalTimeMs={totalTimeMs}
 * />
 */
export function StreamingMessage({
  content,
  isTyping,
  isStreaming,
  traces,
  totalTimeMs,
  className,
}: StreamingMessageProps) {
  return (
    <article
      className={cn('flex gap-3 px-4 py-3', className)}
      data-testid="streaming-message"
      aria-label="LDIP assistant is responding"
      aria-live="polite"
    >
      {/* Avatar */}
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted"
        aria-hidden="true"
      >
        <Bot className="h-4 w-4" />
      </div>

      {/* Message content */}
      <div className="flex max-w-[80%] flex-col gap-1">
        <div className="rounded-lg bg-muted px-4 py-2 text-foreground">
          <StreamingResponse
            content={content}
            isTyping={isTyping}
            isStreaming={isStreaming}
          />
        </div>

        {/* Engine trace (shown as traces complete) */}
        {traces.length > 0 && (
          <EngineTrace traces={traces} totalTimeMs={totalTimeMs} />
        )}
      </div>
    </article>
  );
}
