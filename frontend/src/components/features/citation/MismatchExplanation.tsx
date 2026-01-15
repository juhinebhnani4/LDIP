'use client';

/**
 * Mismatch Explanation Component
 *
 * Displays diff details when a citation has a mismatch with the Act text.
 * Shows citation text vs Act text side-by-side with differences highlighted.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #3)
 */

import { useState, type FC } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import type { VerificationResult } from '@/types/citation';

export interface MismatchExplanationProps {
  /** Verification result containing diff details */
  verification: VerificationResult;
  /** Optional className */
  className?: string;
}

/**
 * Highlight differences in text.
 *
 * @param text - Text to display
 * @param differences - List of difference strings to highlight
 * @returns Array of text segments with highlight flags
 */
function highlightDifferences(
  text: string,
  differences: string[]
): Array<{ text: string; isHighlighted: boolean }> {
  if (differences.length === 0 || !text) {
    return [{ text, isHighlighted: false }];
  }

  const segments: Array<{ text: string; isHighlighted: boolean }> = [];
  let remainingText = text;

  // Simple highlighting - find and mark each difference
  // This is a simplified approach; a real diff algorithm would be more sophisticated
  for (const diff of differences) {
    const lowerDiff = diff.toLowerCase();
    const lowerRemaining = remainingText.toLowerCase();
    const index = lowerRemaining.indexOf(lowerDiff);

    if (index !== -1) {
      // Add text before the difference
      if (index > 0) {
        segments.push({
          text: remainingText.substring(0, index),
          isHighlighted: false,
        });
      }

      // Add the difference
      segments.push({
        text: remainingText.substring(index, index + diff.length),
        isHighlighted: true,
      });

      // Continue with remaining text
      remainingText = remainingText.substring(index + diff.length);
    }
  }

  // Add any remaining text
  if (remainingText) {
    segments.push({ text: remainingText, isHighlighted: false });
  }

  return segments.length > 0 ? segments : [{ text, isHighlighted: false }];
}

/**
 * Mismatch explanation panel showing citation vs Act text comparison.
 */
export const MismatchExplanation: FC<MismatchExplanationProps> = ({
  verification,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  // Only render if there's a mismatch with diff details
  if (
    verification.status !== 'mismatch' ||
    !verification.diffDetails
  ) {
    return null;
  }

  const { diffDetails } = verification;
  const citationSegments = highlightDifferences(
    diffDetails.citationText,
    diffDetails.differences
  );
  const actSegments = highlightDifferences(
    diffDetails.actText,
    diffDetails.differences
  );

  return (
    <div className={`border-b bg-destructive/5 ${className ?? ''}`}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-destructive/10 transition-colors"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          <span className="text-sm font-medium text-destructive">
            Text Mismatch Detected
          </span>
          <span className="text-xs text-muted-foreground">
            {diffDetails.differences.length} difference
            {diffDetails.differences.length !== 1 ? 's' : ''} found
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4">
          {/* Explanation */}
          {verification.explanation && (
            <p className="text-sm text-muted-foreground mb-4">
              {verification.explanation}
            </p>
          )}

          {/* Side-by-side comparison */}
          <div className="grid grid-cols-2 gap-4">
            {/* Citation text */}
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Citation Text
              </h4>
              <div className="p-3 rounded-md bg-background border text-sm">
                {citationSegments.map((segment, index) => (
                  <span
                    key={index}
                    className={
                      segment.isHighlighted
                        ? 'bg-yellow-200 dark:bg-yellow-900/50 px-0.5 rounded'
                        : ''
                    }
                  >
                    {segment.text}
                  </span>
                ))}
              </div>
            </div>

            {/* Act text */}
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Actual Act Text
              </h4>
              <div className="p-3 rounded-md bg-background border text-sm">
                {actSegments.map((segment, index) => (
                  <span
                    key={index}
                    className={
                      segment.isHighlighted
                        ? 'bg-red-200 dark:bg-red-900/50 px-0.5 rounded'
                        : ''
                    }
                  >
                    {segment.text}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Differences list */}
          {diffDetails.differences.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Specific Differences
              </h4>
              <ul className="space-y-1">
                {diffDetails.differences.map((diff, index) => (
                  <li
                    key={index}
                    className="text-sm flex items-center gap-2"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-destructive" />
                    <span className="text-muted-foreground">{diff}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Match type */}
          <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
            <span>
              Match type:{' '}
              <span className="font-medium capitalize">
                {diffDetails.matchType}
              </span>
            </span>
            {verification.similarityScore !== undefined && (
              <span>
                Similarity:{' '}
                <span className="font-medium">
                  {verification.similarityScore.toFixed(1)}%
                </span>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
