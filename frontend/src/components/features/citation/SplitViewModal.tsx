'use client';

/**
 * Split View Modal Component
 *
 * Full-screen modal wrapper for the split view panel.
 * Provides enhanced viewing experience with larger panels.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #6)
 */

import { type FC, useEffect } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { SplitViewCitationPanel } from './SplitViewCitationPanel';
import type { SplitViewData } from '@/types/citation';

export interface SplitViewModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Split view data */
  data: SplitViewData | null;
  /** Navigation info */
  navigationInfo: {
    currentIndex: number;
    totalCount: number;
    canPrev: boolean;
    canNext: boolean;
  };
  /** Loading state */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
  /** Close handler */
  onClose: () => void;
  /** Exit full screen handler */
  onExitFullScreen: () => void;
  /** Previous citation handler */
  onPrev: () => void;
  /** Next citation handler */
  onNext: () => void;
}

/**
 * Full-screen modal for split view citation display.
 *
 * @example
 * ```tsx
 * <SplitViewModal
 *   isOpen={isFullScreen && isOpen}
 *   data={splitViewData}
 *   navigationInfo={navigationInfo}
 *   onClose={closeSplitView}
 *   onExitFullScreen={toggleFullScreen}
 *   onPrev={navigateToPrev}
 *   onNext={navigateToNext}
 * />
 * ```
 */
export const SplitViewModal: FC<SplitViewModalProps> = ({
  isOpen,
  data,
  navigationInfo,
  isLoading = false,
  error = null,
  onClose,
  onExitFullScreen,
  onPrev,
  onNext,
}) => {
  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!data && !isLoading && !error) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="max-w-none w-screen h-screen p-0 border-0 rounded-none"
        onEscapeKeyDown={(e) => {
          e.preventDefault();
          onExitFullScreen();
        }}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <VisuallyHidden>
          <DialogTitle>
            Citation Split View - {data?.citation.actName} Section{' '}
            {data?.citation.sectionNumber}
          </DialogTitle>
        </VisuallyHidden>

        {data && (
          <SplitViewCitationPanel
            data={data}
            isFullScreen={true}
            navigationInfo={navigationInfo}
            isLoading={isLoading}
            error={error}
            onClose={onClose}
            onToggleFullScreen={onExitFullScreen}
            onPrev={onPrev}
            onNext={onNext}
          />
        )}

        {!data && isLoading && (
          <div className="flex items-center justify-center h-full">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        )}

        {!data && error && (
          <div className="flex items-center justify-center h-full">
            <p className="text-destructive">{error}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
