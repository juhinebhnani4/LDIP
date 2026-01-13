'use client';

/**
 * ActDiscoveryModal Component
 *
 * Modal that displays the Act Discovery Report, showing which Acts are
 * referenced in case files and their availability status.
 * Allows users to upload missing Acts or skip them.
 *
 * Story 3-2: Act Discovery Report UI
 *
 * @example
 * ```tsx
 * <ActDiscoveryModal
 *   matterId="matter-123"
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 *   onContinue={() => console.log('Continue with processing')}
 * />
 * ```
 */

import { useCallback, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useActDiscovery } from '@/hooks/useActDiscovery';
import { ActDiscoveryItem } from './ActDiscoveryItem';
import { ActUploadDropzone } from './ActUploadDropzone';

export interface ActDiscoveryModalProps {
  /** Matter ID for fetching Act Discovery Report */
  matterId: string;
  /** Whether the modal is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Callback when user clicks Continue (with or without uploading all Acts) */
  onContinue: () => void;
}

/** View state for the modal */
type ModalView = 'list' | 'upload';

/**
 * Loading skeleton for the Act list
 */
function ActListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4].map((i) => (
        <Skeleton key={i} className="h-16 w-full rounded-lg" />
      ))}
    </div>
  );
}

/**
 * Error state display
 */
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="rounded-full bg-destructive/10 p-3 mb-3">
        <AlertTriangle className="h-6 w-6 text-destructive" />
      </div>
      <p className="text-sm font-medium text-destructive mb-2">Failed to load Act Discovery Report</p>
      <p className="text-xs text-muted-foreground mb-4">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Try Again
      </Button>
    </div>
  );
}

/**
 * Empty state when no Acts are detected
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="rounded-full bg-muted p-3 mb-3">
        <CheckCircle2 className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium mb-1">No Acts Referenced</p>
      <p className="text-xs text-muted-foreground">
        No Act citations were detected in your case files.
      </p>
    </div>
  );
}

/**
 * Info banner explaining graceful degradation
 */
function GracefulDegradationBanner() {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 border border-muted">
      <Info className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
      <p className="text-xs text-muted-foreground">
        Citations to missing Acts will show as &ldquo;Unverified - Act not provided&rdquo;.
        You can upload Acts later from the Documents Tab.
      </p>
    </div>
  );
}

/**
 * ActDiscoveryModal displays the Act Discovery Report and allows users
 * to upload missing Acts or continue with partial verification.
 *
 * UX Flow (from wireframe):
 * 1. Show available Acts (green checkmarks) - found in uploaded files
 * 2. Show missing Acts (amber warnings) - need user to upload
 * 3. User can: Upload Act, Skip Act, or Continue with partial verification
 */
export function ActDiscoveryModal({
  matterId,
  open,
  onOpenChange,
  onContinue,
}: ActDiscoveryModalProps) {
  const [view, setView] = useState<ModalView>('list');
  const [uploadingActName, setUploadingActName] = useState<string | null>(null);

  const {
    actReport,
    isLoading,
    error,
    refetch,
    markUploaded,
    markSkipped,
    isMutating,
    availableCount,
    missingCount,
  } = useActDiscovery(matterId, open);

  // Group Acts by status for display
  const availableActs = actReport.filter((act) => act.resolutionStatus === 'available');
  const missingActs = actReport.filter((act) => act.resolutionStatus === 'missing');
  const skippedActs = actReport.filter((act) => act.resolutionStatus === 'skipped');

  /**
   * Handle upload button click - switch to upload view
   */
  const handleUploadClick = useCallback((actName: string) => {
    setUploadingActName(actName);
    setView('upload');
  }, []);

  /**
   * Handle skip button click
   */
  const handleSkipClick = useCallback(
    async (actName: string) => {
      await markSkipped(actName);
    },
    [markSkipped]
  );

  /**
   * Handle upload complete - mark Act as uploaded and return to list
   */
  const handleUploadComplete = useCallback(
    async (documentId: string) => {
      if (uploadingActName) {
        await markUploaded(uploadingActName, documentId);
        setUploadingActName(null);
        setView('list');
      }
    },
    [uploadingActName, markUploaded]
  );

  /**
   * Handle cancel upload - return to list view
   */
  const handleCancelUpload = useCallback(() => {
    setUploadingActName(null);
    setView('list');
  }, []);

  /**
   * Handle skip for now - close modal and continue
   */
  const handleSkipForNow = useCallback(() => {
    onOpenChange(false);
    onContinue();
  }, [onOpenChange, onContinue]);

  /**
   * Handle continue button
   */
  const handleContinue = useCallback(() => {
    onOpenChange(false);
    onContinue();
  }, [onOpenChange, onContinue]);

  // Reset view when modal opens
  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (newOpen) {
        setView('list');
        setUploadingActName(null);
      }
      onOpenChange(newOpen);
    },
    [onOpenChange]
  );

  const totalActs = actReport.length;
  const hasMissingActs = missingActs.length > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-[600px] max-h-[80vh] flex flex-col"
        aria-describedby="act-discovery-description"
      >
        <DialogHeader>
          <DialogTitle>Act References Detected</DialogTitle>
          <DialogDescription id="act-discovery-description">
            {view === 'upload' && uploadingActName
              ? `Upload the PDF for ${uploadingActName}`
              : `Your case files reference ${totalActs} ${totalActs === 1 ? 'Act' : 'Acts'}. ${availableCount} available, ${missingCount} missing.`}
          </DialogDescription>
        </DialogHeader>

        {/* Content area */}
        <div className="flex-1 overflow-hidden py-2">
          {view === 'upload' && uploadingActName ? (
            /* Upload view */
            <ActUploadDropzone
              matterId={matterId}
              actName={uploadingActName}
              onUploadComplete={handleUploadComplete}
              onCancel={handleCancelUpload}
            />
          ) : (
            /* List view */
            <>
              {isLoading && <ActListSkeleton />}

              {error && !isLoading && (
                <ErrorState message={error.message} onRetry={refetch} />
              )}

              {!isLoading && !error && actReport.length === 0 && <EmptyState />}

              {!isLoading && !error && actReport.length > 0 && (
                <div className="h-[350px] overflow-y-auto pr-2 -mr-2">
                  <div className="space-y-4">
                    {/* Available Acts Section */}
                    {availableActs.length > 0 && (
                      <div>
                        <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2 flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                          Detected in Your Files ({availableActs.length})
                        </h3>
                        <div className="space-y-2" role="list" aria-label="Available Acts">
                          {availableActs.map((act) => (
                            <ActDiscoveryItem
                              key={act.actNameNormalized}
                              act={act}
                              onUpload={handleUploadClick}
                              onSkip={handleSkipClick}
                              isDisabled={isMutating}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Missing Acts Section */}
                    {missingActs.length > 0 && (
                      <div>
                        <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2 flex items-center gap-2">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                          Missing Acts ({missingActs.length})
                        </h3>
                        <div className="space-y-2" role="list" aria-label="Missing Acts">
                          {missingActs.map((act) => (
                            <ActDiscoveryItem
                              key={act.actNameNormalized}
                              act={act}
                              onUpload={handleUploadClick}
                              onSkip={handleSkipClick}
                              isDisabled={isMutating}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Skipped Acts Section */}
                    {skippedActs.length > 0 && (
                      <div>
                        <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2">
                          Skipped ({skippedActs.length})
                        </h3>
                        <div className="space-y-2" role="list" aria-label="Skipped Acts">
                          {skippedActs.map((act) => (
                            <ActDiscoveryItem
                              key={act.actNameNormalized}
                              act={act}
                              onUpload={handleUploadClick}
                              onSkip={handleSkipClick}
                              isDisabled={isMutating}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Graceful degradation info */}
                    {hasMissingActs && (
                      <div className="mt-4">
                        <GracefulDegradationBanner />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer - only show in list view */}
        {view === 'list' && (
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={handleSkipForNow}
              disabled={isLoading || isMutating}
            >
              Skip for Now
            </Button>
            <Button
              onClick={handleContinue}
              disabled={isLoading || isMutating}
            >
              Continue
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
