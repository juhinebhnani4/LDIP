'use client';

/**
 * AnomaliesBanner Component
 *
 * Alert banner displayed at top of Timeline tab when anomalies are detected.
 * Shows count and severity breakdown with action buttons.
 *
 * Story 14.16: Anomalies UI Integration (AC #2)
 */

import { useState, useCallback } from 'react';
import { AlertTriangle, X, Eye, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { cn } from '@/lib/utils';
import type { AnomalySummary } from '@/hooks/useAnomalies';

interface AnomaliesBannerProps {
  /** Anomaly summary data */
  summary: AnomalySummary | null;
  /** Callback to show anomalies filter */
  onShowAnomalies?: () => void;
  /** Callback to open anomaly review panel */
  onReviewAnomalies?: () => void;
  /** Whether the banner can be dismissed */
  dismissible?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export function AnomaliesBanner({
  summary,
  onShowAnomalies,
  onReviewAnomalies,
  dismissible = true,
  className,
}: AnomaliesBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);

  const handleDismiss = useCallback(() => {
    setIsDismissed(true);
  }, []);

  // Don't show if no anomalies, dismissed, or no unreviewed
  if (!summary || summary.unreviewed === 0 || isDismissed) {
    return null;
  }

  const totalActive = summary.total - summary.dismissed;
  const criticalCount = summary.bySeverity.critical ?? 0;
  const highCount = summary.bySeverity.high ?? 0;
  const mediumCount = summary.bySeverity.medium ?? 0;
  const hasCriticalOrHigh = criticalCount > 0 || highCount > 0;

  return (
    <Alert
      variant={hasCriticalOrHigh ? 'destructive' : 'default'}
      className={cn(
        'relative',
        !hasCriticalOrHigh && 'border-orange-200 bg-orange-50 text-orange-900 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-100',
        className
      )}
    >
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle className="flex items-center gap-2">
        Timeline Anomalies Detected
        <Badge
          variant="secondary"
          className={cn(
            'ml-2',
            hasCriticalOrHigh
              ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
              : 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
          )}
        >
          {summary.unreviewed} to review
        </Badge>
      </AlertTitle>
      <AlertDescription className="mt-2">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex flex-wrap gap-2 text-sm">
            <span>{totalActive} total anomalies found:</span>
            {criticalCount > 0 && (
              <Badge variant="outline" className="text-red-700 border-red-300 dark:text-red-300 dark:border-red-700">
                {criticalCount} critical
              </Badge>
            )}
            {highCount > 0 && (
              <Badge variant="outline" className="text-red-600 border-red-300 dark:text-red-300 dark:border-red-700">
                {highCount} high
              </Badge>
            )}
            {mediumCount > 0 && (
              <Badge variant="outline" className="text-orange-600 border-orange-300 dark:text-orange-300 dark:border-orange-700">
                {mediumCount} medium
              </Badge>
            )}
          </div>

          <div className="flex gap-2 sm:ml-auto">
            {onShowAnomalies && (
              <Button
                variant="outline"
                size="sm"
                onClick={onShowAnomalies}
                className={cn(
                  'gap-1',
                  hasCriticalOrHigh
                    ? 'border-red-300 hover:bg-red-100 dark:border-red-700 dark:hover:bg-red-900'
                    : 'border-orange-300 hover:bg-orange-100 dark:border-orange-700 dark:hover:bg-orange-900'
                )}
              >
                <Filter className="h-3.5 w-3.5" />
                Show in Timeline
              </Button>
            )}
            {onReviewAnomalies && (
              <Button
                variant={hasCriticalOrHigh ? 'destructive' : 'default'}
                size="sm"
                onClick={onReviewAnomalies}
                className="gap-1"
              >
                <Eye className="h-3.5 w-3.5" />
                Review
              </Button>
            )}
          </div>
        </div>
      </AlertDescription>

      {dismissible && (
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'absolute top-2 right-2 h-6 w-6',
            hasCriticalOrHigh
              ? 'hover:bg-red-100 dark:hover:bg-red-900'
              : 'hover:bg-orange-100 dark:hover:bg-orange-900'
          )}
          onClick={handleDismiss}
          aria-label="Dismiss banner"
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </Alert>
  );
}

/**
 * Compact version for use in header areas
 */
export function AnomaliesIndicatorBadge({
  count,
  hasCritical,
  onClick,
  className,
}: {
  count: number;
  hasCritical?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  if (count === 0) {
    return null;
  }

  return (
    <Badge
      variant={hasCritical ? 'destructive' : 'secondary'}
      className={cn(
        'cursor-pointer gap-1',
        !hasCritical && 'bg-orange-100 text-orange-800 hover:bg-orange-200 dark:bg-orange-900 dark:text-orange-200',
        className
      )}
      onClick={onClick}
    >
      <AlertTriangle className="h-3 w-3" />
      {count}
    </Badge>
  );
}

AnomaliesBanner.displayName = 'AnomaliesBanner';
AnomaliesIndicatorBadge.displayName = 'AnomaliesIndicatorBadge';
