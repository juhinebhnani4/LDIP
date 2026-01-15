'use client';

/**
 * VerificationBadge Component
 *
 * Displays verification status badge with tooltip showing who verified and when.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #2)
 */

import { CheckCircle2, Flag } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { SummaryVerificationDecision } from '@/types/summary';

interface VerificationBadgeProps {
  /** Verification decision */
  decision?: SummaryVerificationDecision;
  /** User who verified */
  verifiedBy?: string;
  /** Verification timestamp (ISO) */
  verifiedAt?: string;
  /** Additional className */
  className?: string;
}

/**
 * Format date for display in tooltip
 */
function formatDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return isoDate;
  }
}

export function VerificationBadge({
  decision,
  verifiedBy,
  verifiedAt,
  className,
}: VerificationBadgeProps) {
  // Render nothing if no decision
  if (!decision) {
    return null;
  }

  const isVerified = decision === 'verified';

  const badge = (
    <Badge
      variant="outline"
      className={cn(
        'gap-1',
        isVerified
          ? 'text-green-600 border-green-600'
          : 'text-amber-600 border-amber-600',
        className
      )}
    >
      {isVerified ? (
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
      ) : (
        <Flag className="h-3 w-3" aria-hidden="true" />
      )}
      {isVerified ? 'Verified' : 'Flagged'}
    </Badge>
  );

  // If we have verification details, wrap in tooltip
  if (verifiedBy || verifiedAt) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{badge}</TooltipTrigger>
          <TooltipContent side="top">
            <div className="text-sm">
              {verifiedBy && (
                <p className="font-medium">{verifiedBy}</p>
              )}
              {verifiedAt && (
                <p className="text-muted-foreground">{formatDate(verifiedAt)}</p>
              )}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return badge;
}
