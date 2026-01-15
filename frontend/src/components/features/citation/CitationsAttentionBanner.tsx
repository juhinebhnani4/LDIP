'use client';

/**
 * CitationsAttentionBanner Component
 *
 * Alert banner showing citation issues that need attention.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Scale,
  Upload,
  Eye,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

export interface CitationsAttentionBannerProps {
  /** Total number of citations with issues */
  issueCount: number;
  /** Number of missing Acts */
  missingActsCount: number;
  /** Called when "Review Issues" is clicked */
  onReviewIssues?: () => void;
  /** Called when "Upload Missing Acts" is clicked */
  onUploadMissingActs?: () => void;
  className?: string;
}

/**
 * Banner component that alerts users to citation issues needing attention.
 *
 * Shows collapsible content with actionable buttons to address issues.
 *
 * @example
 * ```tsx
 * <CitationsAttentionBanner
 *   issueCount={3}
 *   missingActsCount={2}
 *   onReviewIssues={() => setFilters({ showOnlyIssues: true })}
 *   onUploadMissingActs={() => setShowMissingActsCard(true)}
 * />
 * ```
 */
export function CitationsAttentionBanner({
  issueCount,
  missingActsCount,
  onReviewIssues,
  onUploadMissingActs,
  className,
}: CitationsAttentionBannerProps) {
  const [isOpen, setIsOpen] = useState(true);

  // Don't render if there are no issues
  if (issueCount === 0 && missingActsCount === 0) {
    return null;
  }

  const totalAttentionItems = issueCount + missingActsCount;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          'rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30',
          className
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-amber-100/50 dark:hover:bg-amber-900/20 rounded-lg transition-colors"
            aria-label={isOpen ? 'Collapse attention banner' : 'Expand attention banner'}
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              <span className="font-semibold text-amber-800 dark:text-amber-200">
                {totalAttentionItems} {totalAttentionItems === 1 ? 'CITATION NEEDS' : 'CITATIONS NEED'} ATTENTION
              </span>
            </div>
            {isOpen ? (
              <ChevronUp className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            )}
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-4 pb-4 pt-0">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {/* Issue details */}
              <div className="flex flex-col gap-1 text-sm text-amber-700 dark:text-amber-300">
                {issueCount > 0 && (
                  <span>
                    {issueCount} citation{issueCount !== 1 ? 's have' : ' has'} incorrect section references or verification issues
                  </span>
                )}
                {missingActsCount > 0 && (
                  <div className="flex items-center gap-1.5">
                    <Scale className="h-4 w-4" />
                    <span>
                      {missingActsCount} Act{missingActsCount !== 1 ? 's are' : ' is'} missing - upload to enable verification
                    </span>
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2">
                {issueCount > 0 && onReviewIssues && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onReviewIssues}
                    className="gap-1.5 border-amber-300 bg-white hover:bg-amber-100 dark:border-amber-700 dark:bg-transparent dark:hover:bg-amber-900/30"
                  >
                    <Eye className="h-4 w-4" />
                    Review Issues
                  </Button>
                )}
                {missingActsCount > 0 && onUploadMissingActs && (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={onUploadMissingActs}
                    className="gap-1.5 bg-amber-600 hover:bg-amber-700 text-white"
                  >
                    <Upload className="h-4 w-4" />
                    Upload Missing Acts
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

CitationsAttentionBanner.displayName = 'CitationsAttentionBanner';
