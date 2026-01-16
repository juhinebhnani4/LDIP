'use client';

import { Button } from '@/components/ui/button';
import { JaanchIcon } from '@/components/ui/jaanch-logo';
import { cn } from '@/lib/utils';

/**
 * Default suggested questions for empty conversation state
 * From FR26 in epics.md - help attorneys quickly explore their matter
 */
const DEFAULT_SUGGESTIONS = [
  'What is this case about?',
  'Who are the main parties involved?',
  'What is the timeline of key events?',
  'Are there any citation issues?',
  'What contradictions exist in the documents?',
  'Summarize the key findings',
] as const;

interface SuggestedQuestionsProps {
  /** Callback when a suggested question is clicked */
  onQuestionClick: (question: string) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * SuggestedQuestions Component
 *
 * Displays suggested questions in the empty state of the Q&A panel.
 * When clicked, questions are submitted to the chat as if the user typed them.
 *
 * Story 11.4: Implement Suggested Questions and Message Input
 */
export function SuggestedQuestions({
  onQuestionClick,
  className,
}: SuggestedQuestionsProps) {
  return (
    <div
      className={cn('flex flex-col items-center text-center', className)}
      role="region"
      aria-label="Suggested questions"
    >
      <JaanchIcon size="lg" className="mb-4 opacity-50" />
      <h3 className="mb-2 text-lg font-medium">Ask jaanch</h3>
      <p className="mb-6 max-w-xs text-sm text-muted-foreground">
        Ask questions about your matter. The AI will analyze documents and
        provide answers with citations.
      </p>

      <div className="w-full max-w-sm space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Try asking
        </p>
        <div className="flex flex-col gap-2" role="list" aria-label="Suggested questions list">
          {DEFAULT_SUGGESTIONS.map((question) => (
            <Button
              key={question}
              variant="outline"
              size="sm"
              className="h-auto justify-start px-3 py-2 text-left text-sm font-normal"
              onClick={() => onQuestionClick(question)}
              role="listitem"
              aria-label={`Ask: ${question}`}
            >
              {question}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}

export { DEFAULT_SUGGESTIONS };
