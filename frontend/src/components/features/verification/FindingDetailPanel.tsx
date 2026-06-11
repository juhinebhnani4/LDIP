'use client';

/**
 * FindingDetailPanel Component
 *
 * Slide-over panel showing full details of a verification finding.
 * Supports contradiction, citation, and timeline anomaly findings.
 *
 * BUG-012: Add detail expansion for contradictions in verification queue.
 */

import { useCallback } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  XCircle,
  FileText,
  Flag,
  X,
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
import type { VerificationQueueItem } from '@/types';
import { formatFindingType } from '@/stores/verificationStore';

interface FindingDetailPanelProps {
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback to close the panel */
  onClose: () => void;
  /** The finding to display */
  finding: VerificationQueueItem | null;
  /** Callback when approve is clicked */
  onApprove?: (id: string) => void;
  /** Callback when reject is clicked */
  onReject?: (id: string) => void;
  /** Callback when flag is clicked */
  onFlag?: (id: string) => void;
  /** Whether an action is loading */
  isLoading?: boolean;
}

/**
 * Confidence color based on value
 */
function getConfidenceBadgeClass(confidence: number): string {
  if (confidence >= 90) return 'text-red-600 border-red-300 bg-red-50 dark:bg-red-900/20';
  if (confidence >= 70) return 'text-orange-600 border-orange-300 bg-orange-50 dark:bg-orange-900/20';
  return 'text-yellow-600 border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20';
}

/**
 * Engine type badge color
 */
function getEngineBadgeClass(engine: string): string {
  switch (engine) {
    case 'contradiction':
      return 'text-red-700 border-red-300 bg-red-50 dark:bg-red-900/20';
    case 'citation':
      return 'text-blue-700 border-blue-300 bg-blue-50 dark:bg-blue-900/20';
    case 'timeline':
      return 'text-purple-700 border-purple-300 bg-purple-50 dark:bg-purple-900/20';
    default:
      return 'text-gray-700 border-gray-300';
  }
}

export function FindingDetailPanel({
  isOpen,
  onClose,
  finding,
  onApprove,
  onReject,
  onFlag,
  isLoading = false,
}: FindingDetailPanelProps) {
  const handleApprove = useCallback(() => {
    if (finding && onApprove) {
      onApprove(finding.id);
      onClose();
    }
  }, [finding, onApprove, onClose]);

  const handleReject = useCallback(() => {
    if (finding && onReject) {
      onReject(finding.id);
    }
  }, [finding, onReject]);

  const handleFlag = useCallback(() => {
    if (finding && onFlag) {
      onFlag(finding.id);
    }
  }, [finding, onFlag]);

  if (!finding) {
    return null;
  }

  const isResolved = finding.decision === 'approved' || finding.decision === 'rejected';
  const IconComponent = finding.engine === 'contradiction' ? AlertTriangle
    : finding.engine === 'citation' ? FileText
    : AlertCircle;

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={cn(
                'p-2 rounded-lg',
                finding.engine === 'contradiction' ? 'bg-red-100 dark:bg-red-900/30' :
                finding.engine === 'citation' ? 'bg-blue-100 dark:bg-blue-900/30' :
                'bg-purple-100 dark:bg-purple-900/30'
              )}>
                <IconComponent className={cn(
                  'h-5 w-5',
                  finding.engine === 'contradiction' ? 'text-red-600 dark:text-red-400' :
                  finding.engine === 'citation' ? 'text-blue-600 dark:text-blue-400' :
                  'text-purple-600 dark:text-purple-400'
                )} />
              </div>
              <div>
                <SheetTitle className="text-left">
                  {formatFindingType(finding.findingType)}
                </SheetTitle>
                <SheetDescription className="text-left capitalize">
                  {finding.engine} Engine Finding
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
            <Badge variant="outline" className={getEngineBadgeClass(finding.engine)}>
              {finding.engine}
            </Badge>
            <Badge variant="outline" className={getConfidenceBadgeClass(finding.confidence)}>
              {Math.round(finding.confidence)}% confidence
            </Badge>
            <Badge variant="outline" className="capitalize">
              {finding.requirement}
            </Badge>
            {finding.decision === 'approved' && (
              <Badge variant="outline" className="text-green-600 border-green-500">
                <CheckCircle className="h-3 w-3 mr-1" />
                Approved
              </Badge>
            )}
            {finding.decision === 'rejected' && (
              <Badge variant="outline" className="text-red-600 border-red-500">
                <XCircle className="h-3 w-3 mr-1" />
                Rejected
              </Badge>
            )}
            {finding.decision === 'flagged' && (
              <Badge variant="outline" className="text-orange-600 border-orange-500">
                <Flag className="h-3 w-3 mr-1" />
                Flagged
              </Badge>
            )}
          </div>
        </SheetHeader>

        <Separator className="my-4" />

        {/* Finding Details */}
        <div className="space-y-4">
          {/* Summary / Explanation */}
          <div>
            <h4 className="text-sm font-medium mb-2">Details</h4>
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
              {finding.findingSummary}
            </p>
          </div>

          {/* Source Document */}
          {finding.sourceDocument && (
            <div>
              <h4 className="text-sm font-medium mb-2">Source Document</h4>
              <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg">
                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm">{finding.sourceDocument}</span>
              </div>
            </div>
          )}

          {/* Notes (if any) */}
          {finding.notes && (
            <div>
              <h4 className="text-sm font-medium mb-2">Attorney Notes</h4>
              <div className="p-3 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground italic">
                  &ldquo;{finding.notes}&rdquo;
                </p>
              </div>
            </div>
          )}

          {/* Verification info */}
          {finding.verifiedBy && (
            <div className="text-xs text-muted-foreground">
              Verified by: {finding.verifiedBy}
              {finding.verifiedAt && (
                <> on {new Date(finding.verifiedAt).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}</>
              )}
            </div>
          )}

          {/* Created date */}
          <div className="text-xs text-muted-foreground">
            Detected:{' '}
            {new Date(finding.createdAt).toLocaleDateString('en-US', {
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
          <div className="grid grid-cols-3 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReject}
              disabled={isLoading}
            >
              <XCircle className="h-4 w-4 mr-1" />
              Reject
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleFlag}
              disabled={isLoading}
            >
              <Flag className="h-4 w-4 mr-1" />
              Flag
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleApprove}
              disabled={isLoading}
            >
              <CheckCircle className="h-4 w-4 mr-1" />
              Approve
            </Button>
          </div>
        )}

        {isResolved && (
          <div className="text-center text-sm text-muted-foreground p-4 bg-muted/50 rounded-lg">
            This finding has been {finding.decision === 'approved' ? 'approved' : 'rejected'}.
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

FindingDetailPanel.displayName = 'FindingDetailPanel';
