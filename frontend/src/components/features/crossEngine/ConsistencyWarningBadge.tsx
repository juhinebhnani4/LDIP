'use client';

/**
 * ConsistencyWarningBadge Component
 *
 * Story 5.4: Cross-Engine Consistency Checking
 *
 * Displays a warning badge with count of open consistency issues.
 * Shows in workspace header or matter card to alert users of data inconsistencies.
 */

import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { useConsistencyIssueSummary } from '@/hooks/useCrossEngine';

// =============================================================================
// Types
// =============================================================================

export interface ConsistencyWarningBadgeProps {
  /** Matter ID to fetch issues for */
  matterId: string | null;
  /** Size variant */
  size?: 'sm' | 'default';
  /** Whether to show as button with popover */
  interactive?: boolean;
  /** Callback when clicked */
  onClick?: () => void;
  /** Custom className */
  className?: string;
}

// =============================================================================
// ConsistencyWarningBadge Component
// =============================================================================

/**
 * Badge showing consistency issue count with severity-based styling.
 */
export function ConsistencyWarningBadge({
  matterId,
  size = 'default',
  interactive = false,
  onClick,
  className,
}: ConsistencyWarningBadgeProps) {
  const { summary, openCount, warningCount, errorCount, isLoading } =
    useConsistencyIssueSummary(matterId);

  // Don't render if no open issues
  if (!summary || openCount === 0) {
    return null;
  }

  const isSmall = size === 'sm';
  const hasErrors = errorCount > 0;
  const hasWarnings = warningCount > 0;

  // Determine variant based on severity
  const variant = hasErrors ? 'destructive' : hasWarnings ? 'default' : 'secondary';
  const Icon = hasErrors ? AlertCircle : hasWarnings ? AlertTriangle : Info;

  const badgeContent = (
    <Badge
      variant={variant}
      className={cn(
        'gap-1 cursor-pointer transition-colors',
        isSmall ? 'text-[10px] px-1.5 py-0' : 'text-xs px-2 py-0.5',
        hasErrors && 'bg-red-100 text-red-800 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400',
        hasWarnings && !hasErrors && 'bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400',
        className
      )}
      onClick={onClick}
    >
      <Icon className={cn(isSmall ? 'h-2.5 w-2.5' : 'h-3 w-3')} aria-hidden="true" />
      <span>
        {openCount} {openCount === 1 ? 'issue' : 'issues'}
      </span>
    </Badge>
  );

  if (interactive) {
    return (
      <Popover>
        <PopoverTrigger asChild>
          <button type="button" className="focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary rounded">
            {badgeContent}
          </button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-64">
          <div className="space-y-2">
            <h4 className="font-medium text-sm">Consistency Issues</h4>
            <p className="text-xs text-muted-foreground">
              Found {openCount} data inconsistencies between analysis engines.
            </p>
            <div className="space-y-1 text-xs">
              {errorCount > 0 && (
                <div className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
                  <AlertCircle className="h-3 w-3" />
                  <span>{errorCount} critical</span>
                </div>
              )}
              {warningCount > 0 && (
                <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-3 w-3" />
                  <span>{warningCount} warnings</span>
                </div>
              )}
              {openCount - errorCount - warningCount > 0 && (
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Info className="h-3 w-3" />
                  <span>{openCount - errorCount - warningCount} info</span>
                </div>
              )}
            </div>
            <Button
              size="sm"
              variant="outline"
              className="w-full mt-2"
              onClick={onClick}
            >
              Review Issues
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{badgeContent}</TooltipTrigger>
      <TooltipContent>
        <p className="font-medium">Consistency Issues</p>
        <p className="text-xs">
          {errorCount > 0 && `${errorCount} critical, `}
          {warningCount > 0 && `${warningCount} warnings`}
          {errorCount === 0 && warningCount === 0 && `${openCount} info`}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

// =============================================================================
// ConsistencyStatusIndicator Component
// =============================================================================

export interface ConsistencyStatusIndicatorProps {
  /** Matter ID to fetch issues for */
  matterId: string | null;
  /** Custom className */
  className?: string;
}

/**
 * Inline status indicator showing consistency health.
 */
export function ConsistencyStatusIndicator({
  matterId,
  className,
}: ConsistencyStatusIndicatorProps) {
  const { openCount, errorCount, warningCount, isLoading } =
    useConsistencyIssueSummary(matterId);

  if (isLoading) {
    return null;
  }

  if (openCount === 0) {
    return (
      <span className={cn('text-xs text-green-600 dark:text-green-400', className)}>
        No issues detected
      </span>
    );
  }

  const hasErrors = errorCount > 0;

  return (
    <span
      className={cn(
        'text-xs',
        hasErrors ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400',
        className
      )}
    >
      {openCount} {hasErrors ? 'critical' : 'warning'} issue{openCount !== 1 ? 's' : ''}
    </span>
  );
}

export default ConsistencyWarningBadge;
