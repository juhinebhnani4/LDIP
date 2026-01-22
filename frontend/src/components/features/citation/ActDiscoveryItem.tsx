'use client';

/**
 * ActDiscoveryItem Component
 *
 * Displays a single Act in the Act Discovery Report with status and actions.
 * Shows act name, citation count, status badge, and upload/skip actions.
 *
 * Story 3-2: Act Discovery Report UI
 *
 * @example
 * ```tsx
 * <ActDiscoveryItem
 *   act={{
 *     actName: 'Negotiable Instruments Act, 1881',
 *     actNameNormalized: 'negotiable_instruments_act_1881',
 *     citationCount: 12,
 *     resolutionStatus: 'missing',
 *     userAction: 'pending',
 *     actDocumentId: null,
 *   }}
 *   onUpload={(actName) => console.log('Upload', actName)}
 *   onSkip={(actName) => console.log('Skip', actName)}
 * />
 * ```
 */

import { CheckCircle2, AlertCircle, Upload, SkipForward, Loader2, CloudDownload, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ActDiscoverySummary } from '@/types/citation';

export interface ActDiscoveryItemProps {
  /** Act summary data */
  act: ActDiscoverySummary;
  /** Callback when user clicks Upload */
  onUpload: (actName: string) => void;
  /** Callback when user clicks Skip */
  onSkip: (actName: string) => void;
  /** Whether an upload is in progress for this Act */
  isUploading?: boolean;
  /** Whether any mutation is in progress (disables actions) */
  isDisabled?: boolean;
}

/**
 * Get the status badge for an Act based on its resolution status.
 */
function getStatusBadge(status: ActDiscoverySummary['resolutionStatus'], citationCount: number) {
  switch (status) {
    case 'available':
      return (
        <Badge
          variant="default"
          className="bg-green-500/10 text-green-700 border-green-200 dark:bg-green-500/20 dark:text-green-400 dark:border-green-800"
          aria-label="Act available for verification"
        >
          <CheckCircle2 className="mr-1 h-3 w-3" aria-hidden="true" />
          Available
        </Badge>
      );
    case 'auto_fetched':
      return (
        <Badge
          variant="default"
          className="bg-blue-500/10 text-blue-700 border-blue-200 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-800"
          aria-label="Act auto-fetched from India Code"
        >
          <CloudDownload className="mr-1 h-3 w-3" aria-hidden="true" />
          Auto-fetched
        </Badge>
      );
    case 'missing':
      return (
        <Badge
          variant="outline"
          className="bg-amber-500/10 text-amber-700 border-amber-200 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-800"
          aria-label={`Act missing, cited ${citationCount} times`}
        >
          <AlertCircle className="mr-1 h-3 w-3" aria-hidden="true" />
          Missing ({citationCount} {citationCount === 1 ? 'citation' : 'citations'})
        </Badge>
      );
    case 'not_on_indiacode':
      return (
        <Badge
          variant="outline"
          className="bg-orange-500/10 text-orange-700 border-orange-200 dark:bg-orange-500/20 dark:text-orange-400 dark:border-orange-800"
          aria-label={`Act not available on India Code, upload manually`}
        >
          <ExternalLink className="mr-1 h-3 w-3" aria-hidden="true" />
          Upload manually
        </Badge>
      );
    case 'skipped':
      return (
        <Badge
          variant="secondary"
          className="text-muted-foreground"
          aria-label="Act skipped by user"
        >
          Skipped
        </Badge>
      );
    case 'invalid':
      // Invalid acts should be filtered out by the backend, but handle just in case
      return null;
    default:
      return null;
  }
}

/**
 * ActDiscoveryItem displays a single Act with its status and available actions.
 *
 * Visual Design:
 * - Available Acts: Green checkmark badge
 * - Auto-fetched Acts: Blue cloud download badge (from India Code)
 * - Missing Acts: Amber warning badge with citation count + Upload/Skip buttons
 * - Not on India Code: Orange external link badge + Upload/Skip buttons
 * - Skipped Acts: Muted secondary badge
 * - Invalid Acts: Hidden (garbage extractions filtered by backend)
 */
export function ActDiscoveryItem({
  act,
  onUpload,
  onSkip,
  isUploading = false,
  isDisabled = false,
}: ActDiscoveryItemProps) {
  // Acts that need user action (missing or not on India Code)
  const needsUpload = act.resolutionStatus === 'missing' || act.resolutionStatus === 'not_on_indiacode';
  const showActions = needsUpload && act.userAction === 'pending';

  // Don't render invalid acts (garbage extractions)
  if (act.resolutionStatus === 'invalid') {
    return null;
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-4 p-3 rounded-lg border',
        act.resolutionStatus === 'available' && 'bg-green-50/50 border-green-200 dark:bg-green-950/20 dark:border-green-900',
        act.resolutionStatus === 'auto_fetched' && 'bg-blue-50/50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-900',
        act.resolutionStatus === 'missing' && 'bg-amber-50/50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900',
        act.resolutionStatus === 'not_on_indiacode' && 'bg-orange-50/50 border-orange-200 dark:bg-orange-950/20 dark:border-orange-900',
        act.resolutionStatus === 'skipped' && 'bg-muted/50 border-muted'
      )}
      role="listitem"
      aria-label={`${act.actName}, ${act.resolutionStatus}, ${act.citationCount} citations`}
    >
      {/* Act info */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate" title={act.actName}>
          {act.actName}
        </p>
        {!needsUpload && (
          <p className="text-xs text-muted-foreground">
            {act.citationCount} {act.citationCount === 1 ? 'citation' : 'citations'}
          </p>
        )}
      </div>

      {/* Status and actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {getStatusBadge(act.resolutionStatus, act.citationCount)}

        {showActions && (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onUpload(act.actName)}
              disabled={isDisabled || isUploading}
              aria-label={`Upload ${act.actName}`}
            >
              {isUploading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Upload className="h-4 w-4" aria-hidden="true" />
              )}
              <span className="ml-1.5 hidden sm:inline">Upload</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSkip(act.actName)}
              disabled={isDisabled || isUploading}
              aria-label={`Skip ${act.actName}`}
            >
              <SkipForward className="h-4 w-4" aria-hidden="true" />
              <span className="ml-1.5 hidden sm:inline">Skip</span>
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
