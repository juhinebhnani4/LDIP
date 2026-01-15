'use client';

import {
  differenceInDays,
  differenceInMonths,
  differenceInYears,
  isValid,
  parseISO,
} from 'date-fns';
import { cn } from '@/lib/utils';

/**
 * Timeline Connector Component
 *
 * Displays a vertical line between events with duration text.
 * Emphasizes large time gaps (> 90 days) with warning styling.
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #3)
 */

interface TimelineConnectorProps {
  /** Previous event date (ISO) */
  fromDate: string;
  /** Next event date (ISO) */
  toDate: string;
  /** Additional className */
  className?: string;
}

/** Gap threshold in days for significant gap styling (3 months) */
const SIGNIFICANT_GAP_DAYS = 90;

/** Gap threshold for "very large" gap warning (6 months) */
const LARGE_GAP_DAYS = 180;

/**
 * Format duration between two dates in human-readable format
 */
export function formatDuration(fromDate: string, toDate: string): string {
  try {
    const from = parseISO(fromDate);
    const to = parseISO(toDate);

    if (!isValid(from) || !isValid(to)) {
      return 'Unknown';
    }

    const days = differenceInDays(to, from);
    const months = differenceInMonths(to, from);
    const years = differenceInYears(to, from);

    if (days < 0) {
      return 'Invalid range';
    }

    if (days === 0) {
      return 'Same day';
    }

    if (days === 1) {
      return '1 day';
    }

    if (years >= 1) {
      const remainingMonths = months % 12;
      if (remainingMonths > 0) {
        return `${years} year${years > 1 ? 's' : ''}, ${remainingMonths} month${remainingMonths > 1 ? 's' : ''}`;
      }
      return `${years} year${years > 1 ? 's' : ''}`;
    }

    if (months >= 1) {
      return `${months} month${months > 1 ? 's' : ''}`;
    }

    return `${days} day${days > 1 ? 's' : ''}`;
  } catch {
    return 'Unknown';
  }
}

/**
 * Calculate if the gap is significant (> 90 days)
 */
export function isSignificantGap(fromDate: string, toDate: string): boolean {
  try {
    const from = parseISO(fromDate);
    const to = parseISO(toDate);
    if (!isValid(from) || !isValid(to)) {
      return false;
    }
    return differenceInDays(to, from) > SIGNIFICANT_GAP_DAYS;
  } catch {
    return false;
  }
}

/**
 * Calculate if the gap is very large (> 180 days)
 */
export function isLargeGap(fromDate: string, toDate: string): boolean {
  try {
    const from = parseISO(fromDate);
    const to = parseISO(toDate);
    if (!isValid(from) || !isValid(to)) {
      return false;
    }
    return differenceInDays(to, from) > LARGE_GAP_DAYS;
  } catch {
    return false;
  }
}

export function TimelineConnector({
  fromDate,
  toDate,
  className,
}: TimelineConnectorProps) {
  const duration = formatDuration(fromDate, toDate);
  const significant = isSignificantGap(fromDate, toDate);
  const large = isLargeGap(fromDate, toDate);

  return (
    <div
      className={cn('flex items-center py-2 pl-6', className)}
      role="separator"
      aria-label={`Time gap: ${duration}${significant ? ' (significant delay)' : ''}`}
    >
      {/* Vertical connector line */}
      <div
        className={cn(
          'w-0.5 h-8 mr-4',
          significant
            ? 'bg-amber-400 dark:bg-amber-500'
            : 'bg-border'
        )}
        aria-hidden="true"
      />

      {/* Duration text */}
      <span
        className={cn(
          'text-xs',
          significant
            ? 'text-amber-600 dark:text-amber-400 font-medium'
            : 'text-muted-foreground'
        )}
      >
        ← {duration}
        {large && (
          <span className="ml-1 font-semibold">(SIGNIFICANT DELAY)</span>
        )}
      </span>
    </div>
  );
}
