/**
 * StreamingResponse Component
 *
 * Displays streaming response content with typing indicator and cursor animation.
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 6: Create StreamingResponse component (AC: #1)
 *
 * Features:
 * - Typing indicator when processing starts
 * - Accumulated tokens display
 * - Cursor animation during streaming
 * - Error display with toast
 */

'use client';

import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface StreamingResponseProps {
  /** Accumulated response content */
  content: string;
  /** Whether typing indicator should show */
  isTyping: boolean;
  /** Whether streaming is currently active */
  isStreaming: boolean;
  /** Optional CSS classes */
  className?: string;
}

/**
 * StreamingResponse Component
 *
 * Story 11.3: Task 6.1-6.6 - Token streaming display.
 *
 * Shows the AI response as it streams in, with:
 * - "jaanch is thinking..." indicator before content
 * - Accumulated text as tokens arrive
 * - Blinking cursor during active streaming
 *
 * @example
 * <StreamingResponse
 *   content={accumulatedText}
 *   isTyping={isTyping}
 *   isStreaming={isStreaming}
 * />
 */
export function StreamingResponse({
  content,
  isTyping,
  isStreaming,
  className,
}: StreamingResponseProps) {
  return (
    <div className={cn('space-y-2', className)} data-testid="streaming-response">
      {/* Task 6.2: Typing indicator when processing starts */}
      {isTyping && !content && (
        <div
          className="flex items-center gap-2 text-muted-foreground"
          role="status"
          aria-live="polite"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          <span className="text-sm">jaanch padtaal jaari...</span>
        </div>
      )}

      {/* Task 6.3-6.5: Accumulated tokens with cursor */}
      {content && (
        <div className="text-sm prose prose-sm dark:prose-invert max-w-none break-words prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-ul:pl-5 prose-ol:pl-5 prose-li:my-0.5 prose-li:marker:text-muted-foreground prose-strong:text-foreground prose-strong:font-semibold prose-headings:mt-4 prose-headings:mb-2 prose-headings:text-foreground prose-h2:text-base prose-h3:text-sm prose-h2:border-b prose-h2:border-border/50 prose-h2:pb-1" data-testid="streaming-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          {/* Task 6.5: Cursor animation during streaming */}
          {isStreaming && (
            <span
              className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-current"
              aria-hidden="true"
            />
          )}
        </div>
      )}
    </div>
  );
}
