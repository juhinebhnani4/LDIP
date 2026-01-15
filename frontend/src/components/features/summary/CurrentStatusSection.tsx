'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Calendar, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { InlineVerificationButtons } from './InlineVerificationButtons';
import { VerificationBadge } from './VerificationBadge';
import { SummaryNotesDialog } from './SummaryNotesDialog';
import type { CurrentStatus, SummaryVerificationDecision } from '@/types/summary';

/**
 * Current Status Section Component
 *
 * Displays the current status of proceedings including last order date and description.
 * Now includes inline verification buttons on hover.
 *
 * Story 10B.1: Summary Tab Content (AC #1)
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 */

interface CurrentStatusSectionProps {
  /** Current status data */
  currentStatus: CurrentStatus;
  /** Optional className for styling */
  className?: string;
  /** Callback when section is verified */
  onVerify?: () => Promise<void>;
  /** Callback when section is flagged */
  onFlag?: () => Promise<void>;
  /** Callback when note is saved */
  onSaveNote?: (note: string) => Promise<void>;
}

/**
 * Format date for display
 */
function formatDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    // Check for Invalid Date
    if (isNaN(date.getTime())) {
      return 'Unknown date';
    }
    return date.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  } catch {
    return 'Unknown date';
  }
}

export function CurrentStatusSection({
  currentStatus,
  className,
  onVerify,
  onFlag,
  onSaveNote,
}: CurrentStatusSectionProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;
  const formattedDate = formatDate(currentStatus.lastOrderDate);
  const [isHovered, setIsHovered] = useState(false);
  const [isNotesDialogOpen, setIsNotesDialogOpen] = useState(false);
  const [verificationDecision, setVerificationDecision] = useState<SummaryVerificationDecision | undefined>(
    currentStatus.isVerified ? 'verified' : undefined
  );

  const handleVerify = async () => {
    if (onVerify) {
      await onVerify();
      setVerificationDecision('verified');
    }
  };

  const handleFlag = async () => {
    if (onFlag) {
      await onFlag();
      setVerificationDecision('flagged');
    }
  };

  const handleSaveNote = async (note: string) => {
    if (onSaveNote) {
      await onSaveNote(note);
    }
  };

  return (
    <section className={className} aria-labelledby="current-status-heading">
      <h2 id="current-status-heading" className="text-lg font-semibold mb-4">
        Current Status
      </h2>
      <Card
        className="relative"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <CardTitle className="text-base">Last Order: {formattedDate}</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <InlineVerificationButtons
                sectionType="current_status"
                sectionId={matterId}
                currentDecision={verificationDecision}
                onVerify={handleVerify}
                onFlag={handleFlag}
                onAddNote={() => setIsNotesDialogOpen(true)}
                isVisible={isHovered}
              />
              <VerificationBadge decision={verificationDecision} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <p className="text-sm leading-relaxed">{currentStatus.description}</p>

          {/* Source reference */}
          <div className="mt-4 pt-4 border-t flex items-center justify-between flex-wrap gap-4">
            <div className="text-sm text-muted-foreground">
              Source: {currentStatus.sourceDocument}, p. {currentStatus.sourcePage}
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link
                href={`/matters/${matterId}/documents?doc=${encodeURIComponent(currentStatus.sourceDocument)}&page=${currentStatus.sourcePage}`}
                aria-label={`View full order: ${currentStatus.sourceDocument}, page ${currentStatus.sourcePage}`}
              >
                <ExternalLink className="h-4 w-4 mr-1.5" aria-hidden="true" />
                View Full Order
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <SummaryNotesDialog
        isOpen={isNotesDialogOpen}
        onClose={() => setIsNotesDialogOpen(false)}
        onSave={handleSaveNote}
        sectionType="current_status"
        sectionId={matterId}
      />
    </section>
  );
}

/**
 * Current Status Section Skeleton
 */
export function CurrentStatusSectionSkeleton({ className }: { className?: string }) {
  return (
    <section className={className}>
      <Skeleton className="h-6 w-32 mb-4" />
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-5" />
              <Skeleton className="h-5 w-48" />
            </div>
            <Skeleton className="h-5 w-24" />
          </div>
        </CardHeader>
        <CardContent className="pt-2 space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="pt-4 border-t mt-4 flex items-center justify-between">
            <Skeleton className="h-4 w-32" />
            <div className="flex gap-2">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-8 w-20" />
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
