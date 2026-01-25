'use client';

/**
 * MissingActsCard Component
 *
 * Displays missing Acts that need user action with upload/skip options.
 * Integrates with ActUploadDropzone for uploading Act documents.
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { useState, useCallback } from 'react';
import {
  Scale,
  AlertCircle,
  Upload,
  SkipForward,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ActUploadDropzone } from './ActUploadDropzone';
import type { ActDiscoverySummary } from '@/types/citation';

export interface MissingActsCardProps {
  /** Matter ID for document uploads */
  matterId: string;
  /** List of Acts from discovery report */
  acts: ActDiscoverySummary[];
  /** Whether data is loading */
  isLoading?: boolean;
  /** Callback when Act is marked as uploaded (triggers verification) */
  onActUploadedAndVerify: (actName: string, documentId: string) => Promise<void>;
  /** Callback when Act is skipped */
  onActSkipped: (actName: string) => Promise<void>;
  /** Callback to refresh discovery data */
  onRefresh?: () => void;
  className?: string;
}

/**
 * MissingActsCard - Card component showing missing Acts needing attention.
 *
 * @example
 * ```tsx
 * <MissingActsCard
 *   matterId="matter-123"
 *   acts={acts}
 *   onActUploadedAndVerify={handleUploadAndVerify}
 *   onActSkipped={handleSkip}
 * />
 * ```
 */
export function MissingActsCard({
  matterId,
  acts,
  isLoading = false,
  onActUploadedAndVerify,
  onActSkipped,
  onRefresh,
  className,
}: MissingActsCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [uploadingAct, setUploadingAct] = useState<string | null>(null);
  const [skippingAct, setSkippingAct] = useState<string | null>(null);

  // Filter to only missing acts that need action
  const missingActs = acts.filter(
    (act) => act.resolutionStatus === 'missing' && act.userAction === 'pending'
  );

  // Handle upload completion
  const handleUploadComplete = useCallback(
    async (actName: string, documentId: string) => {
      try {
        await onActUploadedAndVerify(actName, documentId);
        toast.success(`${actName} uploaded - verification started`);
        setUploadingAct(null);
        onRefresh?.();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to verify';
        toast.error(message);
      }
    },
    [onActUploadedAndVerify, onRefresh]
  );

  // Handle skip action
  const handleSkip = useCallback(
    async (actName: string) => {
      setSkippingAct(actName);
      try {
        await onActSkipped(actName);
        toast.success(`${actName} marked as skipped`);
        onRefresh?.();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to skip';
        toast.error(message);
      } finally {
        setSkippingAct(null);
      }
    },
    [onActSkipped, onRefresh]
  );

  // Don't render if no missing acts
  if (missingActs.length === 0 && !isLoading) {
    return null;
  }

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
      <Card className={cn('', className)}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Scale className="h-5 w-5 text-amber-600" />
                <CardTitle className="text-base">Missing Acts</CardTitle>
                <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300">
                  {missingActs.length}
                </Badge>
              </div>
              {isExpanded ? (
                <ChevronUp className="h-5 w-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-5 w-5 text-muted-foreground" />
              )}
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              {missingActs.length === 1
                ? `Upload "${missingActs[0].actName}" to verify ${missingActs[0].citationCount} citation${missingActs[0].citationCount !== 1 ? 's' : ''}`
                : missingActs.length <= 3
                  ? `Upload "${missingActs.map(a => a.actName).join('", "')}" to enable citation verification`
                  : `Upload "${missingActs.slice(0, 2).map(a => a.actName).join('", "')}" and ${missingActs.length - 2} more to enable citation verification`}
            </p>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="space-y-3 pt-0">
            {isLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              missingActs.map((act) => (
                <div key={act.actNameNormalized}>
                  {uploadingAct === act.actName ? (
                    // Show upload dropzone
                    <div className="border rounded-lg p-4 bg-muted/30">
                      <ActUploadDropzone
                        matterId={matterId}
                        actName={act.actName}
                        onUploadComplete={(docId) => handleUploadComplete(act.actName, docId)}
                        onCancel={() => setUploadingAct(null)}
                      />
                    </div>
                  ) : (
                    // Show act info with actions
                    <div
                      className="flex items-center justify-between gap-4 p-3 rounded-lg border bg-amber-50/50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900"
                    >
                      {/* Act info */}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate" title={act.actName}>
                          {act.actName}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          <AlertCircle className="inline h-3 w-3 mr-1 text-amber-600" />
                          {act.citationCount} citation{act.citationCount !== 1 ? 's' : ''} cannot be verified
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setUploadingAct(act.actName)}
                          disabled={skippingAct === act.actName}
                          className="gap-1"
                        >
                          <Upload className="h-4 w-4" />
                          <span className="hidden sm:inline">Upload</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSkip(act.actName)}
                          disabled={skippingAct === act.actName}
                          className="gap-1"
                        >
                          {skippingAct === act.actName ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <SkipForward className="h-4 w-4" />
                          )}
                          <span className="hidden sm:inline">Skip</span>
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}

            {/* Summary for skipped acts */}
            {acts.filter((a) => a.resolutionStatus === 'skipped').length > 0 && (
              <p className="text-xs text-muted-foreground pt-2 border-t">
                {acts.filter((a) => a.resolutionStatus === 'skipped').length} Act{acts.filter((a) => a.resolutionStatus === 'skipped').length !== 1 ? 's' : ''} skipped
              </p>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

MissingActsCard.displayName = 'MissingActsCard';
