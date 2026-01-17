'use client';

/**
 * AnomalyDetailPanel Component
 *
 * Slide-over panel showing full details of a timeline anomaly.
 * Includes anomaly type, severity, explanation, affected events,
 * and actions to dismiss or verify.
 *
 * Story 14.16: Anomalies UI Integration (AC #3)
 */

import { useCallback } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  X,
  CheckCircle,
  XCircle,
  Clock,
  FileText,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import type { AnomalyListItem, Anomaly, AnomalySeverity } from '@/hooks/useAnomalies';
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
 * Background color map for icon container
 */
const SEVERITY_BG_MAP: Record<AnomalySeverity, string> = {
  critical: 'bg-red-100 dark:bg-red-900/30',
  high: 'bg-red-100 dark:bg-red-900/30',
  medium: 'bg-orange-100 dark:bg-orange-900/30',
  low: 'bg-yellow-100 dark:bg-yellow-900/30',
};

/**
 * Icon color map
 */
const SEVERITY_ICON_COLOR_MAP: Record<AnomalySeverity, string> = {
  critical: 'text-red-600 dark:text-red-400',
  high: 'text-red-600 dark:text-red-400',
  medium: 'text-orange-600 dark:text-orange-400',
  low: 'text-yellow-600 dark:text-yellow-400',
};

interface AnomalyDetailPanelProps {
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback to close the panel */
  onClose: () => void;
  /** The anomaly to display (can be list item or full detail) */
  anomaly: AnomalyListItem | Anomaly | null;
  /** Callback when dismiss is clicked */
  onDismiss?: (anomalyId: string) => void;
  /** Callback when verify is clicked */
  onVerify?: (anomalyId: string) => void;
  /** Callback when an event link is clicked */
  onEventClick?: (eventId: string) => void;
  /** Whether mutations are loading */
  isLoading?: boolean;
}

export function AnomalyDetailPanel({
  isOpen,
  onClose,
  anomaly,
  onDismiss,
  onVerify,
  onEventClick,
  isLoading = false,
}: AnomalyDetailPanelProps) {
  const handleDismiss = useCallback(() => {
    if (anomaly && onDismiss) {
      onDismiss(anomaly.id);
    }
  }, [anomaly, onDismiss]);

  const handleVerify = useCallback(() => {
    if (anomaly && onVerify) {
      onVerify(anomaly.id);
    }
  }, [anomaly, onVerify]);

  const handleEventClick = useCallback(
    (eventId: string) => {
      if (onEventClick) {
        onEventClick(eventId);
      }
    },
    [onEventClick]
  );

  if (!anomaly) {
    return null;
  }

  // Access static maps directly to avoid component creation during render
  const IconComponent = SEVERITY_ICON_MAP[anomaly.severity];
  const iconBgColor = SEVERITY_BG_MAP[anomaly.severity];
  const iconColor = SEVERITY_ICON_COLOR_MAP[anomaly.severity];
  const isResolved = anomaly.verified || anomaly.dismissed;

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={cn('p-2 rounded-lg', iconBgColor)}>
                <IconComponent className={cn('h-5 w-5', iconColor)} />
              </div>
              <div>
                <SheetTitle className="text-left">{anomaly.title}</SheetTitle>
                <SheetDescription className="text-left">
                  {getAnomalyTypeLabel(anomaly.anomalyType)}
                </SheetDescription>
              </div>
            </div>
            <SheetClose asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <X className="h-4 w-4" />
                <span className="sr-only">Close</span>
              </Button>
            </SheetClose>
          </div>

          {/* Status badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="outline"
              className={cn(getAnomalySeverityColor(anomaly.severity))}
            >
              {getAnomalySeverityLabel(anomaly.severity)} Severity
            </Badge>
            {anomaly.verified && (
              <Badge variant="outline" className="text-green-600 border-green-500">
                <CheckCircle className="h-3 w-3 mr-1" />
                Verified Issue
              </Badge>
            )}
            {anomaly.dismissed && (
              <Badge variant="outline" className="text-gray-600 border-gray-400">
                <XCircle className="h-3 w-3 mr-1" />
                Dismissed
              </Badge>
            )}
            <Badge variant="secondary" className="text-xs">
              {Math.round(anomaly.confidence * 100)}% confidence
            </Badge>
          </div>
        </SheetHeader>

        <Separator className="my-4" />

        {/* Explanation */}
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-medium mb-2">Explanation</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {anomaly.explanation}
            </p>
          </div>

          {/* Gap days (for gap anomalies) */}
          {anomaly.gapDays !== null && (
            <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                <strong>{anomaly.gapDays} days</strong> between events
              </span>
            </div>
          )}

          {/* Sequence info (for sequence violations) */}
          {'expectedOrder' in anomaly &&
            anomaly.expectedOrder &&
            anomaly.actualOrder && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Sequence Analysis</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-muted/50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Expected</p>
                    <div className="flex flex-wrap gap-1">
                      {anomaly.expectedOrder.map((type, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {type}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Actual</p>
                    <div className="flex flex-wrap gap-1">
                      {anomaly.actualOrder.map((type, i) => (
                        <Badge
                          key={i}
                          variant="outline"
                          className="text-xs border-red-300"
                        >
                          {type}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

          {/* Affected events */}
          <div>
            <h4 className="text-sm font-medium mb-2">
              Affected Events ({anomaly.eventIds.length})
            </h4>
            <div className="space-y-2">
              {anomaly.eventIds.map((eventId) => (
                <button
                  key={eventId}
                  onClick={() => handleEventClick(eventId)}
                  className={cn(
                    'w-full flex items-center gap-2 p-2 rounded-md text-left',
                    'hover:bg-accent transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-ring'
                  )}
                >
                  <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <span className="text-sm truncate flex-1">{eventId}</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </button>
              ))}
            </div>
          </div>

          {/* Created date */}
          <div className="text-xs text-muted-foreground">
            Detected:{' '}
            {new Date(anomaly.createdAt).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        </div>

        <Separator className="my-4" />

        {/* Action buttons */}
        {!isResolved && (
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="flex-1"
              onClick={handleDismiss}
              disabled={isLoading}
            >
              <XCircle className="h-4 w-4 mr-2" />
              Dismiss
            </Button>
            <Button
              variant="default"
              className="flex-1"
              onClick={handleVerify}
              disabled={isLoading}
            >
              <CheckCircle className="h-4 w-4 mr-2" />
              Verify as Issue
            </Button>
          </div>
        )}

        {isResolved && (
          <div className="text-center text-sm text-muted-foreground p-4 bg-muted/50 rounded-lg">
            This anomaly has been {anomaly.verified ? 'verified' : 'dismissed'}.
            {'verifiedBy' in anomaly && anomaly.verifiedBy && (
              <span className="block mt-1">by {anomaly.verifiedBy}</span>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

AnomalyDetailPanel.displayName = 'AnomalyDetailPanel';
