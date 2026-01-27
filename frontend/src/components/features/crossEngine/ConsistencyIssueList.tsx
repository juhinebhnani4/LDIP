'use client';

/**
 * ConsistencyIssueList Component
 *
 * Story 5.4: Cross-Engine Consistency Checking
 *
 * Displays a list of consistency issues with filtering, pagination,
 * and actions to review/resolve issues.
 */

import { useState } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Check,
  X,
  RefreshCw,
  ChevronDown,
  FileText,
  Clock,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  useConsistencyIssues,
  useConsistencyIssueSummary,
  useConsistencyIssueMutations,
} from '@/hooks/useCrossEngine';
import {
  ISSUE_TYPE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
  type ConsistencyIssue,
  type ConsistencyIssueStatus,
  type ConsistencyIssueSeverity,
} from '@/types/crossEngine';

// =============================================================================
// Types
// =============================================================================

export interface ConsistencyIssueListProps {
  /** Matter ID to show issues for */
  matterId: string;
  /** Custom className */
  className?: string;
}

// =============================================================================
// Helper Components
// =============================================================================

function SeverityIcon({
  severity,
  className,
}: {
  severity: ConsistencyIssueSeverity;
  className?: string;
}) {
  switch (severity) {
    case 'error':
      return <AlertCircle className={cn('text-red-500', className)} />;
    case 'warning':
      return <AlertTriangle className={cn('text-amber-500', className)} />;
    default:
      return <Info className={cn('text-blue-500', className)} />;
  }
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// =============================================================================
// Issue Card Component
// =============================================================================

interface IssueCardProps {
  issue: ConsistencyIssue;
  onUpdateStatus: (
    issueId: string,
    status: ConsistencyIssueStatus
  ) => Promise<boolean>;
  isUpdating: boolean;
}

function IssueCard({ issue, onUpdateStatus, isUpdating }: IssueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleStatusUpdate = async (status: ConsistencyIssueStatus) => {
    await onUpdateStatus(issue.id, status);
  };

  return (
    <Card className={cn('transition-shadow hover:shadow-md')}>
      <CardHeader className="py-3 px-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5 min-w-0 flex-1">
            <SeverityIcon severity={issue.severity} className="h-4 w-4 mt-0.5 shrink-0" />
            <div className="min-w-0 flex-1">
              <CardTitle className="text-sm font-medium leading-tight">
                {ISSUE_TYPE_LABELS[issue.issueType]}
              </CardTitle>
              <CardDescription className="text-xs mt-0.5 line-clamp-2">
                {issue.description}
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] px-1.5',
                issue.status === 'open' && 'border-amber-300 text-amber-700 dark:text-amber-400',
                issue.status === 'reviewed' && 'border-blue-300 text-blue-700 dark:text-blue-400',
                issue.status === 'resolved' && 'border-green-300 text-green-700 dark:text-green-400',
                issue.status === 'dismissed' && 'border-gray-300 text-gray-500'
              )}
            >
              {STATUS_LABELS[issue.status]}
            </Badge>
            {issue.status === 'open' && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2"
                    disabled={isUpdating}
                  >
                    <ChevronDown className="h-3.5 w-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => handleStatusUpdate('reviewed')}>
                    <Check className="h-3.5 w-3.5 mr-2" />
                    Mark as Reviewed
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleStatusUpdate('resolved')}>
                    <Check className="h-3.5 w-3.5 mr-2 text-green-600" />
                    Mark as Resolved
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleStatusUpdate('dismissed')}>
                    <X className="h-3.5 w-3.5 mr-2 text-gray-500" />
                    Dismiss
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent className="pt-0 pb-3 px-4">
          <div className="space-y-2 text-xs border-t pt-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-muted-foreground">Source:</span>{' '}
                <span className="font-medium capitalize">{issue.sourceEngine}</span>
                {issue.sourceValue && (
                  <span className="text-muted-foreground ml-1">({issue.sourceValue})</span>
                )}
              </div>
              <div>
                <span className="text-muted-foreground">Conflicts with:</span>{' '}
                <span className="font-medium capitalize">{issue.conflictingEngine}</span>
                {issue.conflictingValue && (
                  <span className="text-muted-foreground ml-1">({issue.conflictingValue})</span>
                )}
              </div>
            </div>
            {issue.documentName && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <FileText className="h-3 w-3" />
                <span>{issue.documentName}</span>
              </div>
            )}
            <div className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span>Detected {formatRelativeTime(issue.detectedAt)}</span>
            </div>
          </div>
        </CardContent>
      )}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full py-1.5 text-[10px] text-muted-foreground hover:text-foreground border-t transition-colors"
      >
        {isExpanded ? 'Show less' : 'Show details'}
      </button>
    </Card>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function ConsistencyIssueList({
  matterId,
  className,
}: ConsistencyIssueListProps) {
  const [statusFilter, setStatusFilter] = useState<ConsistencyIssueStatus | 'all'>('open');
  const [severityFilter, setSeverityFilter] = useState<ConsistencyIssueSeverity | 'all'>('all');

  const { summary, openCount, mutate: mutateSummary } = useConsistencyIssueSummary(matterId);
  const {
    issues,
    meta,
    isLoading,
    mutate: mutateIssues,
  } = useConsistencyIssues(matterId, {
    status: statusFilter === 'all' ? undefined : statusFilter,
    severity: severityFilter === 'all' ? undefined : severityFilter,
    limit: 20,
  });

  const {
    updateIssueStatus,
    runConsistencyCheck,
    isUpdating,
    isChecking,
    checkResult,
  } = useConsistencyIssueMutations(matterId);

  const handleRefresh = async () => {
    await runConsistencyCheck();
    mutateIssues();
    mutateSummary();
  };

  const handleUpdateStatus = async (
    issueId: string,
    status: ConsistencyIssueStatus
  ) => {
    const success = await updateIssueStatus(issueId, status);
    if (success) {
      mutateIssues();
      mutateSummary();
    }
    return success;
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header with stats and actions */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-medium">Consistency Issues</h3>
          <p className="text-xs text-muted-foreground">
            {openCount > 0
              ? `${openCount} open issue${openCount !== 1 ? 's' : ''} detected`
              : 'No open issues'}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isChecking}
          className="gap-1.5"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isChecking && 'animate-spin')} />
          {isChecking ? 'Checking...' : 'Run Check'}
        </Button>
      </div>

      {/* Check result toast */}
      {checkResult && (
        <div className="bg-muted/50 rounded-md p-3 text-xs">
          <span className="font-medium">Check complete:</span>{' '}
          Found {checkResult.issuesFound} issues ({checkResult.issuesCreated} new).
          Checked: {checkResult.enginesChecked.join(', ')}.
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter(value as ConsistencyIssueStatus | 'all')}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="reviewed">Reviewed</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
            <SelectItem value="dismissed">Dismissed</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={severityFilter}
          onValueChange={(value) => setSeverityFilter(value as ConsistencyIssueSeverity | 'all')}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Severity</SelectItem>
            <SelectItem value="error">Errors</SelectItem>
            <SelectItem value="warning">Warnings</SelectItem>
            <SelectItem value="info">Info</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Issue list */}
      <div className="space-y-2">
        {isLoading ? (
          <>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </>
        ) : issues.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            {statusFilter === 'open'
              ? 'No open consistency issues found.'
              : 'No issues match the selected filters.'}
          </div>
        ) : (
          issues.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              onUpdateStatus={handleUpdateStatus}
              isUpdating={isUpdating}
            />
          ))
        )}
      </div>

      {/* Pagination info */}
      {meta.count > 0 && (
        <p className="text-xs text-muted-foreground text-center">
          Showing {meta.count} of {summary?.totalCount ?? meta.count} issues
        </p>
      )}
    </div>
  );
}

export default ConsistencyIssueList;
