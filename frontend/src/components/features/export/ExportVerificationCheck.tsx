'use client';

/**
 * ExportVerificationCheck Component
 *
 * Displays export eligibility check results before generating an export.
 * Shows blocking findings (must verify) and warning findings (can dismiss).
 *
 * Story 12.3: AC #1, #2 - Verification check before export
 *
 * @example
 * ```tsx
 * <ExportVerificationCheck
 *   matterId="matter-123"
 *   open={showVerificationCheck}
 *   onOpenChange={setShowVerificationCheck}
 *   onProceed={handleProceedToExport}
 *   onNavigateToQueue={() => router.push(`/matters/${matterId}/verification`)}
 * />
 * ```
 */

import { useEffect, useState, useCallback } from 'react';
import { AlertTriangle, Ban, CheckCircle2, ExternalLink, Loader2, Scale } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { checkExportEligibility } from '@/lib/api/verifications';
import type { ExportEligibility, ExportBlockingFinding, ExportWarningFinding } from '@/types';

export interface ExportVerificationCheckProps {
  /** Matter ID for checking eligibility */
  matterId: string;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when user proceeds with export (after passing or dismissing warnings) */
  onProceed: () => void;
  /** Callback to navigate to verification queue */
  onNavigateToQueue: () => void;
}

/**
 * Format finding type for display
 */
function formatFindingType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Get confidence badge variant based on score
 */
function getConfidenceBadgeVariant(confidence: number): 'destructive' | 'outline' {
  return confidence < 70 ? 'destructive' : 'outline';
}

/**
 * Finding item display component for blocking or warning findings.
 *
 * Story 12.3: Displays individual finding with type badge, confidence indicator,
 * and summary text. Visual styling differs based on whether finding blocks export.
 *
 * @param finding - The finding data to display (blocking or warning).
 * @param isBlocking - Whether this is a blocking finding (affects styling).
 */
function FindingItem({
  finding,
  isBlocking,
}: {
  finding: ExportBlockingFinding | ExportWarningFinding;
  isBlocking: boolean;
}) {
  // Issue #7 fix: Null safety for finding properties
  const findingType = finding?.findingType ?? 'unknown';
  const confidence = finding?.confidence ?? 0;
  const summary = finding?.findingSummary ?? 'No summary available';

  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg border ${
        isBlocking ? 'border-destructive/50 bg-destructive/5' : 'border-warning/50 bg-warning/5'
      }`}
    >
      {isBlocking ? (
        <Ban className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
      ) : (
        <AlertTriangle className="h-4 w-4 text-warning mt-0.5 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="secondary" className="text-xs">
            {formatFindingType(findingType)}
          </Badge>
          <Badge variant={getConfidenceBadgeVariant(confidence)} className="text-xs">
            {confidence.toFixed(0)}% confidence
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
          {summary}
        </p>
      </div>
    </div>
  );
}

/**
 * Loading skeleton for eligibility check
 */
function EligibilitySkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-64" />
        </div>
      </div>
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

/**
 * ExportVerificationCheck dialog for displaying export eligibility status.
 *
 * Features:
 * - Fetches export eligibility on open
 * - Shows blocking findings that must be verified
 * - Shows warning findings that can be dismissed
 * - Navigate to verification queue option
 * - Continue with warnings option
 */
export function ExportVerificationCheck({
  matterId,
  open,
  onOpenChange,
  onProceed,
  onNavigateToQueue,
}: ExportVerificationCheckProps) {
  const [eligibility, setEligibility] = useState<ExportEligibility | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEligibility = useCallback(async () => {
    if (!matterId) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await checkExportEligibility(matterId);
      setEligibility(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check export eligibility');
    } finally {
      setIsLoading(false);
    }
  }, [matterId]);

  // Fetch eligibility when dialog opens
  useEffect(() => {
    if (open) {
      fetchEligibility();
    }
  }, [open, fetchEligibility]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setEligibility(null);
      setError(null);
    }
  }, [open]);

  const handleNavigateToQueue = () => {
    onOpenChange(false);
    onNavigateToQueue();
  };

  const handleProceed = () => {
    onOpenChange(false);
    onProceed();
  };

  // Determine dialog state
  const isBlocked = eligibility && !eligibility.eligible;
  const hasWarnings = eligibility && eligibility.warningCount > 0;
  const canProceed = eligibility?.eligible ?? false;
  // Story 3.2: Check if matter is in court-ready mode
  const isCourtReady = eligibility?.verificationMode === 'required';

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            {isLoading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Checking Export Eligibility...
              </>
            ) : error ? (
              <>
                <Ban className="h-5 w-5 text-destructive" />
                Eligibility Check Failed
              </>
            ) : isBlocked ? (
              <>
                <Ban className="h-5 w-5 text-destructive" />
                Export Blocked
                {isCourtReady && (
                  <Badge variant="secondary" className="ml-2 gap-1">
                    <Scale className="h-3 w-3" />
                    Court-Ready
                  </Badge>
                )}
              </>
            ) : hasWarnings ? (
              <>
                <AlertTriangle className="h-5 w-5 text-warning" />
                Export Available with Warnings
              </>
            ) : (
              <>
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                Ready to Export
                {isCourtReady && (
                  <Badge variant="secondary" className="ml-2 gap-1">
                    <Scale className="h-3 w-3" />
                    Court-Ready
                  </Badge>
                )}
              </>
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {isLoading ? (
              'Verifying all findings meet export requirements...'
            ) : error ? (
              error
            ) : isBlocked ? (
              isCourtReady
                ? `Court-ready mode requires 100% verification. ${eligibility.blockingCount} finding(s) still need verification before export.`
                : `${eligibility.blockingCount} finding(s) with low confidence must be verified before export.`
            ) : hasWarnings ? (
              `${eligibility.warningCount} finding(s) are suggested for verification but export is allowed.`
            ) : (
              isCourtReady
                ? 'Court-ready: All findings verified. Export is allowed.'
                : 'All findings meet the verification requirements for export.'
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {/* Content */}
        {isLoading ? (
          <EligibilitySkeleton />
        ) : error ? (
          <div className="py-4 text-center text-muted-foreground">
            <p>Unable to verify export eligibility. Please try again.</p>
          </div>
        ) : eligibility && (eligibility.blockingCount > 0 || eligibility.warningCount > 0) ? (
          <ScrollArea className="max-h-[300px] pr-4">
            <div className="space-y-4">
              {/* Blocking findings */}
              {eligibility.blockingCount > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-destructive flex items-center gap-2">
                    <Ban className="h-4 w-4" />
                    {isCourtReady
                      ? `Pending Verification (${eligibility.blockingCount})`
                      : `Requires Verification (${eligibility.blockingCount})`}
                  </h4>
                  <div className="space-y-2">
                    {eligibility.blockingFindings.map((finding, index) => (
                      <FindingItem
                        // Issue #7 fix: Fallback key if verificationId is missing
                        key={finding?.verificationId ?? `blocking-${index}`}
                        finding={finding}
                        isBlocking={true}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Warning findings */}
              {eligibility.warningCount > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-warning flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Suggested for Verification ({eligibility.warningCount})
                  </h4>
                  <div className="space-y-2">
                    {eligibility.warningFindings.map((finding, index) => (
                      <FindingItem
                        // Issue #7 fix: Fallback key if verificationId is missing
                        key={finding?.verificationId ?? `warning-${index}`}
                        finding={finding}
                        isBlocking={false}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        ) : null}

        <AlertDialogFooter className="flex-col sm:flex-row gap-2">
          {isBlocked ? (
            <>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <Button
                variant="default"
                onClick={handleNavigateToQueue}
                className="gap-2"
              >
                <ExternalLink className="h-4 w-4" />
                Go to Verification Queue
              </Button>
            </>
          ) : hasWarnings ? (
            <>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <Button
                variant="outline"
                onClick={handleNavigateToQueue}
                className="gap-2"
              >
                <ExternalLink className="h-4 w-4" />
                Verify First
              </Button>
              <AlertDialogAction onClick={handleProceed}>
                Continue with Warnings
              </AlertDialogAction>
            </>
          ) : canProceed ? (
            <>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleProceed}>
                Continue to Export
              </AlertDialogAction>
            </>
          ) : (
            <AlertDialogCancel>Close</AlertDialogCancel>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
