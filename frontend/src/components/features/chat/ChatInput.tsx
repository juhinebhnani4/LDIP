/**
 * ChatInput Component
 *
 * Text input with submit button for sending chat queries.
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 10: Create chat input with submit (AC: #1)
 *
 * Features:
 * - Multiline textarea that auto-grows
 * - Submit button with loading state
 * - Enter to submit (Shift+Enter for newline)
 * - Disabled during streaming
 */

'use client';

import { useState, useCallback, useRef, useEffect, KeyboardEvent } from 'react';
import { SendHorizontal, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  /** Callback when user submits a message */
  onSubmit: (query: string) => void;
  /** Whether input should be disabled (e.g., during streaming) */
  disabled?: boolean;
  /** Whether a request is currently in progress */
  isLoading?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Optional CSS classes */
  className?: string;
}

/** Max rows for the textarea */
const MAX_ROWS = 6;
/** Min rows for the textarea */
const MIN_ROWS = 1;
/** Line height for calculation (in pixels) */
const LINE_HEIGHT = 24;

/**
 * ChatInput Component
 *
 * Story 11.3: Task 10.1-10.5 - Chat input implementation.
 *
 * Provides a textarea for entering queries with:
 * - Auto-growing height based on content
 * - Submit on Enter (Shift+Enter for newlines)
 * - Visual feedback during loading
 * - Accessible labels and keyboard support
 *
 * @example
 * <ChatInput
 *   onSubmit={(query) => handleSendMessage(query)}
 *   disabled={isStreaming}
 *   isLoading={isLoading}
 * />
 */
export function ChatInput({
  onSubmit,
  disabled = false,
  isLoading = false,
  placeholder = 'Ask jaanch a question...',
  className,
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /**
   * Calculate and update textarea height based on content.
   */
  const updateHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to auto to get accurate scrollHeight
    textarea.style.height = 'auto';

    // Calculate new height
    const scrollHeight = textarea.scrollHeight;
    const minHeight = LINE_HEIGHT * MIN_ROWS;
    const maxHeight = LINE_HEIGHT * MAX_ROWS;

    const newHeight = Math.max(minHeight, Math.min(scrollHeight, maxHeight));
    textarea.style.height = `${newHeight}px`;
  }, []);

  // Update height when value changes
  useEffect(() => {
    updateHeight();
  }, [value, updateHeight]);

  /**
   * Handle form submission.
   */
  const handleSubmit = useCallback(() => {
    const trimmedValue = value.trim();
    if (!trimmedValue || disabled || isLoading) return;

    onSubmit(trimmedValue);
    setValue('');
  }, [value, disabled, isLoading, onSubmit]);

  /**
   * Handle keyboard events for Enter to submit.
   */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter without Shift submits
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  /**
   * Handle input change.
   */
  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
  }, []);

  const canSubmit = value.trim().length > 0 && !disabled && !isLoading;

  return (
    <div
      className={cn(
        'flex items-end gap-2 border-t bg-background p-4',
        className
      )}
      data-testid="chat-input"
    >
      {/* Textarea */}
      <div className="relative flex-1">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          rows={MIN_ROWS}
          className={cn(
            'w-full resize-none rounded-lg border bg-background px-4 py-3 pr-12 text-sm',
            'placeholder:text-muted-foreground',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'scrollbar-thin scrollbar-thumb-muted-foreground/20'
          )}
          style={{ lineHeight: `${LINE_HEIGHT}px` }}
          aria-label="Message input"
          data-testid="chat-input-textarea"
        />
      </div>

      {/* Submit button */}
      <Button
        type="button"
        size="icon"
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="h-10 w-10 shrink-0"
        aria-label={isLoading ? 'Sending message...' : 'Send message'}
        data-testid="chat-submit-button"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <SendHorizontal className="h-4 w-4" aria-hidden="true" />
        )}
      </Button>
    </div>
  );
}
