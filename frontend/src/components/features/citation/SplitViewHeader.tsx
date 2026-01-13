'use client';

/**
 * Split View Header Component
 *
 * Displays citation information, verification status, and navigation controls
 * at the top of the split view panel.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #1, #3)
 */

import type { FC } from 'react';
import {
  X,
  Maximize2,
  Minimize2,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { Citation, VerificationResult, VerificationStatus } from '@/types/citation';

export interface SplitViewHeaderProps {
  /** Citation being viewed */
  citation: Citation;
  /** Verification result if available */
  verification: VerificationResult | null;
  /** Whether in full screen mode */
  isFullScreen: boolean;
  /** Navigation info */
  navigationInfo: {
    currentIndex: number;
    totalCount: number;
    canPrev: boolean;
    canNext: boolean;
  };
  /** Callback when close button is clicked */
  onClose: () => void;
  /** Callback when expand/collapse button is clicked */
  onToggleFullScreen: () => void;
  /** Callback when previous button is clicked */
  onPrev: () => void;
  /** Callback when next button is clicked */
  onNext: () => void;
}

/**
 * Get status badge variant and icon based on verification status.
 */
function getStatusInfo(status: VerificationStatus): {
  variant: 'default' | 'secondary' | 'destructive' | 'outline';
  icon: typeof CheckCircle;
  label: string;
} {
  switch (status) {
    case 'verified':
      return { variant: 'default', icon: CheckCircle, label: 'Verified' };
    case 'mismatch':
      return { variant: 'destructive', icon: XCircle, label: 'Mismatch' };
    case 'section_not_found':
      return { variant: 'secondary', icon: AlertTriangle, label: 'Section Not Found' };
    case 'act_unavailable':
      return { variant: 'outline', icon: HelpCircle, label: 'Act Unavailable' };
    case 'pending':
    default:
      return { variant: 'outline', icon: HelpCircle, label: 'Pending' };
  }
}

/**
 * Split view header with citation info, status, and controls.
 */
export const SplitViewHeader: FC<SplitViewHeaderProps> = ({
  citation,
  verification,
  isFullScreen,
  navigationInfo,
  onClose,
  onToggleFullScreen,
  onPrev,
  onNext,
}) => {
  const statusInfo = getStatusInfo(citation.verificationStatus);
  const StatusIcon = statusInfo.icon;

  return (
    <div className="flex flex-col border-b bg-muted/50">
      {/* Main header row */}
      <div className="flex items-center justify-between px-4 py-3">
        {/* Citation info */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <h3 className="text-sm font-semibold">{citation.actName}</h3>
            <p className="text-xs text-muted-foreground">
              Section {citation.sectionNumber}
              {citation.subsection && ` (${citation.subsection})`}
              {citation.clause && `, Clause ${citation.clause}`}
            </p>
          </div>

          {/* Status badge */}
          <Badge variant={statusInfo.variant} className="flex items-center gap-1">
            <StatusIcon className="h-3 w-3" />
            {statusInfo.label}
          </Badge>

          {/* Similarity score if available */}
          {verification?.similarityScore !== undefined && (
            <span className="text-xs text-muted-foreground">
              {verification.similarityScore.toFixed(1)}% match
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* Navigation */}
          {navigationInfo.totalCount > 1 && (
            <div className="flex items-center gap-1 mr-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={onPrev}
                disabled={!navigationInfo.canPrev}
                title="Previous citation (Left Arrow)"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground min-w-[60px] text-center">
                {navigationInfo.currentIndex + 1} / {navigationInfo.totalCount}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={onNext}
                disabled={!navigationInfo.canNext}
                title="Next citation (Right Arrow)"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Expand/collapse */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleFullScreen}
            title={isFullScreen ? 'Exit full screen (F)' : 'Full screen (F)'}
          >
            {isFullScreen ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </Button>

          {/* Close */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            title="Close (Escape)"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Mismatch explanation row (AC: #3) */}
      {citation.verificationStatus === 'mismatch' && verification?.explanation && (
        <div className="px-4 py-2 bg-destructive/10 border-t border-destructive/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-destructive">Mismatch Detected</p>
              <p className="text-muted-foreground">{verification.explanation}</p>
            </div>
          </div>
        </div>
      )}

      {/* Act unavailable message (AC: #4) */}
      {citation.verificationStatus === 'act_unavailable' && (
        <div className="px-4 py-2 bg-muted border-t">
          <div className="flex items-start gap-2">
            <HelpCircle className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
            <div className="text-sm text-muted-foreground">
              <p>Act document not uploaded. Only the source citation is displayed.</p>
              <p className="text-xs mt-1">
                Upload the Act via Act Discovery to enable verification.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
