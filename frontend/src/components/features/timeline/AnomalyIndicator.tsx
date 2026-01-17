'use client';

/**
 * AnomalyIndicator Component
 *
 * Displays a warning indicator for timeline events that have anomalies.
 * Shows severity-based coloring and tooltip with anomaly details.
 *
 * Story 14.16: Anomalies UI Integration (AC #1)
 */

import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { AnomalyListItem, AnomalySeverity } from '@/hooks/useAnomalies';
import {
  getAnomalySeverityColor,
  getAnomalyTypeLabel,
  getAnomalySeverityLabel,
} from '@/hooks/useAnomalies';

/**
 * Static icon map - defined outside component to avoid render-time creation
 */
const SEVERITY_ICON_MAP = {
  critical: AlertCircle,
  high: AlertCircle,
  medium: AlertTriangle,
  low: Info,
} as const;

/**
 * Icon color map - defined outside component
 */
const ICON_COLOR_MAP: Record<AnomalySeverity, string> = {
  critical: 'text-red-600 dark:text-red-400',
  high: 'text-red-600 dark:text-red-400',
  medium: 'text-orange-600 dark:text-orange-400',
  low: 'text-yellow-600 dark:text-yellow-400',
};

interface AnomalyIndicatorProps {
  /** List of anomalies affecting this event */
  anomalies: AnomalyListItem[];
  /** Click handler to open detail panel */
  onClick?: (anomaly: AnomalyListItem) => void;
  /** Size variant */
  size?: 'sm' | 'md';
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get the highest severity from a list of anomalies
 */
function getHighestSeverity(anomalies: AnomalyListItem[]): AnomalySeverity {
  const severityOrder: AnomalySeverity[] = ['low', 'medium', 'high', 'critical'];
  let highestIndex = 0;

  anomalies.forEach((anomaly) => {
    const index = severityOrder.indexOf(anomaly.severity);
    if (index > highestIndex) {
      highestIndex = index;
    }
  });

  return severityOrder[highestIndex] ?? 'low';
}

export function AnomalyIndicator({
  anomalies,
  onClick,
  size = 'md',
  className,
}: AnomalyIndicatorProps) {
  if (anomalies.length === 0) {
    return null;
  }

  const highestSeverity = getHighestSeverity(anomalies);
  // Access static map directly to avoid component creation during render
  const IconComponent = SEVERITY_ICON_MAP[highestSeverity];
  const iconColor = ICON_COLOR_MAP[highestSeverity];
  const iconSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';

  // If there's only one anomaly, show its details directly
  const primaryAnomaly = anomalies[0]!;
  const hasMultiple = anomalies.length > 1;

  const handleClick = () => {
    if (onClick) {
      onClick(primaryAnomaly);
    }
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={handleClick}
          className={cn(
            'inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5',
            'hover:bg-accent/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1',
            'transition-colors cursor-pointer',
            className
          )}
          aria-label={`${anomalies.length} anomal${anomalies.length === 1 ? 'y' : 'ies'} detected - click for details`}
        >
          <IconComponent className={cn(iconSize, iconColor)} aria-hidden="true" />
          {hasMultiple && (
            <span className={cn('text-xs font-medium', iconColor)}>
              {anomalies.length}
            </span>
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn('text-xs', getAnomalySeverityColor(highestSeverity))}
            >
              {getAnomalySeverityLabel(highestSeverity)}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {hasMultiple
                ? `${anomalies.length} anomalies`
                : getAnomalyTypeLabel(primaryAnomaly.anomalyType)}
            </span>
          </div>
          <p className="text-sm">{primaryAnomaly.title}</p>
          {hasMultiple && (
            <p className="text-xs text-muted-foreground">
              Click to view all anomalies
            </p>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Compact badge variant for use in tables or tight spaces
 */
export function AnomalyBadge({
  anomalies,
  onClick,
  className,
}: Omit<AnomalyIndicatorProps, 'size'>) {
  if (anomalies.length === 0) {
    return null;
  }

  const highestSeverity = getHighestSeverity(anomalies);
  // Access static map directly to avoid component creation during render
  const IconComponent = SEVERITY_ICON_MAP[highestSeverity];

  const handleClick = () => {
    if (onClick && anomalies[0]) {
      onClick(anomalies[0]);
    }
  };

  return (
    <Badge
      variant="outline"
      className={cn(
        'cursor-pointer gap-1',
        getAnomalySeverityColor(highestSeverity),
        className
      )}
      onClick={handleClick}
    >
      <IconComponent className="h-3 w-3" aria-hidden="true" />
      {anomalies.length > 1 ? `${anomalies.length} Issues` : 'Issue'}
    </Badge>
  );
}

AnomalyIndicator.displayName = 'AnomalyIndicator';
AnomalyBadge.displayName = 'AnomalyBadge';
