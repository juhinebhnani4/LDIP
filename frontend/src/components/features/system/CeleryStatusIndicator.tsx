'use client';

/**
 * Celery Status Indicator Component
 *
 * Shows the health status of Celery workers in the UI.
 * Green = healthy (workers running)
 * Yellow = restarting (workers coming back online)
 * Red = unhealthy (no workers responding)
 *
 * Can be used in headers or dashboards to give users visibility
 * into backend processing health.
 */

import { useState, useEffect, useCallback } from 'react';
import { Activity, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { checkCeleryHealth, type CeleryStatus } from '@/lib/api/documents';

interface CeleryStatusIndicatorProps {
  /** How often to refresh status (in ms). Default: 30000 (30 seconds) */
  refreshInterval?: number;
  /** Whether to show text label. Default: false (icon only) */
  showLabel?: boolean;
  /** Faster polling interval when offline (in ms). Default: 10000 (10 seconds) */
  offlineRefreshInterval?: number;
}

/**
 * Celery Status Indicator
 *
 * Displays a small status indicator showing if background workers are running.
 * Useful for debugging processing issues.
 *
 * When workers are offline, polls more frequently and shows "Restarting..." message
 * to reassure users that the system is auto-recovering.
 */
export function CeleryStatusIndicator({
  refreshInterval = 30000,
  showLabel = false,
  offlineRefreshInterval = 10000,
}: CeleryStatusIndicatorProps) {
  const [status, setStatus] = useState<CeleryStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);

  const fetchStatus = useCallback(async () => {
    try {
      const result = await checkCeleryHealth();
      setStatus(result);
      // Reset failure count on success
      if (result.status === 'healthy') {
        setConsecutiveFailures(0);
      } else {
        setConsecutiveFailures((prev) => prev + 1);
      }
    } catch {
      setConsecutiveFailures((prev) => prev + 1);
      setStatus({
        status: 'error',
        workers: {},
        workerCount: 0,
        queues: [],
        message: 'Failed to check status',
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  const isHealthy = status?.status === 'healthy';

  useEffect(() => {
    // Initial fetch
    fetchStatus();

    // Poll faster when offline to detect recovery quickly
    const currentInterval = isHealthy ? refreshInterval : offlineRefreshInterval;
    const interval = setInterval(fetchStatus, currentInterval);

    return () => clearInterval(interval);
  }, [fetchStatus, refreshInterval, offlineRefreshInterval, isHealthy]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Activity className="h-4 w-4 animate-pulse" />
        {showLabel && <span className="text-xs">Checking...</span>}
      </div>
    );
  }

  const workerCount = status?.workerCount ?? 0;
  // Show "restarting" state after first failure detection
  const isRestarting = !isHealthy && consecutiveFailures >= 1;

  // Determine display state
  const getDisplayState = () => {
    if (isHealthy) {
      return {
        icon: <CheckCircle2 className="h-4 w-4" />,
        color: 'text-green-600',
        label: `${workerCount} worker${workerCount !== 1 ? 's' : ''}`,
        title: 'Background Processing: Online',
      };
    }
    if (isRestarting) {
      return {
        icon: <RefreshCw className="h-4 w-4 animate-spin" />,
        color: 'text-yellow-600',
        label: 'Restarting...',
        title: 'Background Processing: Restarting',
      };
    }
    return {
      icon: <AlertCircle className="h-4 w-4" />,
      color: 'text-destructive',
      label: 'Offline',
      title: 'Background Processing: Offline',
    };
  };

  const displayState = getDisplayState();

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`flex items-center gap-1.5 ${displayState.color}`}>
            {displayState.icon}
            {showLabel && <span className="text-xs">{displayState.label}</span>}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="center">
          <div className="space-y-1">
            <div className="font-medium">{displayState.title}</div>
            {isHealthy ? (
              <>
                <div className="text-xs text-muted-foreground">
                  {workerCount} worker{workerCount !== 1 ? 's' : ''} running
                </div>
                {status?.queues && status.queues.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    Queues: {status.queues.join(', ')}
                  </div>
                )}
              </>
            ) : isRestarting ? (
              <div className="space-y-1">
                <div className="text-xs text-yellow-600">
                  Workers are restarting automatically
                </div>
                <div className="text-xs text-muted-foreground">
                  This usually takes 30-60 seconds. Your uploads will resume once workers are back online.
                </div>
              </div>
            ) : (
              <div className="text-xs text-destructive">
                {status?.message || 'No workers are responding'}
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
