'use client';

/**
 * StatementSection Component
 *
 * Displays a single statement within a contradiction card, including
 * document name, page number, text excerpt, and date if available.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 5: Create StatementSection component
 */

import { FileText } from 'lucide-react';
import type { StatementInfo } from '@/hooks/useContradictions';

interface StatementSectionProps {
  /** Statement data */
  statement: StatementInfo;
  /** Label for the statement (e.g., "Statement A", "Statement B") */
  label: string;
  /** Optional callback when document link is clicked */
  onDocumentClick?: (documentId: string, page: number | null) => void;
}

/**
 * Truncate text to a maximum length with ellipsis, respecting word boundaries.
 */
function truncateText(text: string, maxLength: number = 200): string {
  if (text.length <= maxLength) return text;

  // Find the last space before maxLength to avoid cutting mid-word
  const truncated = text.slice(0, maxLength);
  const lastSpaceIndex = truncated.lastIndexOf(' ');

  // If there's a space, truncate at the word boundary; otherwise use maxLength
  const cutPoint = lastSpaceIndex > maxLength * 0.5 ? lastSpaceIndex : maxLength;
  return text.slice(0, cutPoint).trim() + '...';
}

/**
 * Format date for display.
 */
function formatDate(dateString: string | null): string | null {
  if (!dateString) return null;
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}

/**
 * StatementSection displays a single statement with document reference.
 *
 * @example
 * ```tsx
 * <StatementSection
 *   statement={contradiction.statementA}
 *   label="Statement A"
 *   onDocumentClick={(docId, page) => openPdfViewer(docId, page)}
 * />
 * ```
 */
export function StatementSection({
  statement,
  label,
  onDocumentClick,
}: StatementSectionProps) {
  const handleDocumentClick = () => {
    if (onDocumentClick) {
      onDocumentClick(statement.documentId, statement.page);
    }
  };

  const formattedDate = formatDate(statement.date);

  return (
    <div className="space-y-2">
      {/* Label */}
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </div>

      {/* Document reference */}
      <div className="flex items-center gap-2 text-sm">
        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
        {onDocumentClick ? (
          <button
            type="button"
            onClick={handleDocumentClick}
            className="text-primary hover:underline font-medium truncate max-w-[200px]"
            title={statement.documentName}
          >
            {statement.documentName}
          </button>
        ) : (
          <span
            className="font-medium truncate max-w-[200px]"
            title={statement.documentName}
          >
            {statement.documentName}
          </span>
        )}
        {statement.page !== null && (
          <span className="text-muted-foreground shrink-0">
            (p. {statement.page})
          </span>
        )}
      </div>

      {/* Excerpt */}
      <blockquote className="border-l-2 border-muted pl-3 text-sm text-muted-foreground italic">
        &ldquo;{truncateText(statement.excerpt)}&rdquo;
      </blockquote>

      {/* Date if available */}
      {formattedDate && (
        <div className="text-xs text-muted-foreground">
          Date mentioned: {formattedDate}
        </div>
      )}
    </div>
  );
}
