'use client';

/**
 * Celery Status Indicator Component
 *
 * Shows the health status of Celery workers in the UI.
 * Green = healthy (workers running)
 * Red = unhealthy (no workers responding)
 *
 * Can be used in headers or dashboards to give users visibility
 * into backend processing health.
 */

import { useState, useEffect } from 'react';
import { Activity, AlertCircle, CheckCircle2 } from 'lucide-react';
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
}

/**
 * Celery Status Indicator
 *
 * Displays a small status indicator showing if background workers are running.
 * Useful for debugging processing issues.
 */
export function CeleryStatusIndicator({
  refreshInterval = 30000,
  showLabel = false,
}: CeleryStatusIndicatorProps) {
  const [status, setStatus] = useState<CeleryStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const result = await checkCeleryHealth();
        setStatus(result);
      } catch {
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
    };

    // Initial fetch
    fetchStatus();

    // Set up interval
    const interval = setInterval(fetchStatus, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Activity className="h-4 w-4 animate-pulse" />
        {showLabel && <span className="text-xs">Checking...</span>}
      </div>
    );
  }

  const isHealthy = status?.status === 'healthy';
  const workerCount = status?.workerCount ?? 0;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={`flex items-center gap-1.5 ${
              isHealthy ? 'text-green-600' : 'text-destructive'
            }`}
          >
            {isHealthy ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {showLabel && (
              <span className="text-xs">
                {isHealthy ? `${workerCount} worker${workerCount !== 1 ? 's' : ''}` : 'Offline'}
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="center">
          <div className="space-y-1">
            <div className="font-medium">
              Background Processing: {isHealthy ? 'Online' : 'Offline'}
            </div>
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
