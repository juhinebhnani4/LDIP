'use client';

/**
 * InlineVerificationButtons Component
 *
 * Hover-reveal action buttons for verifying, flagging, or adding notes to summary sections.
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 */

import { useState } from 'react';
import { Check, Flag, MessageSquare, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { SummarySectionType, SummaryVerificationDecision } from '@/types/summary';

interface InlineVerificationButtonsProps {
  /** Section type being verified */
  sectionType: SummarySectionType;
  /** Section ID */
  sectionId: string;
  /** Current verification status */
  currentDecision?: SummaryVerificationDecision;
  /** Callback for verify action */
  onVerify: () => Promise<void>;
  /** Callback for flag action */
  onFlag: () => Promise<void>;
  /** Callback for add note action */
  onAddNote: () => void;
  /** Whether buttons are visible (controlled by parent hover) */
  isVisible?: boolean;
  /** Additional className */
  className?: string;
}

export function InlineVerificationButtons({
  currentDecision,
  onVerify,
  onFlag,
  onAddNote,
  isVisible = true,
  className,
}: InlineVerificationButtonsProps) {
  const [isVerifying, setIsVerifying] = useState(false);
  const [isFlagging, setIsFlagging] = useState(false);

  const handleVerify = async () => {
    setIsVerifying(true);
    try {
      await onVerify();
    } catch {
      // Error handling is delegated to the parent component
    } finally {
      setIsVerifying(false);
    }
  };

  const handleFlag = async () => {
    setIsFlagging(true);
    try {
      await onFlag();
    } catch {
      // Error handling is delegated to the parent component
    } finally {
      setIsFlagging(false);
    }
  };

  return (
    <div
      className={cn(
        'flex items-center gap-1 transition-opacity',
        isVisible ? 'opacity-100' : 'opacity-0',
        className
      )}
      aria-label="Verification actions"
    >
      <Button
        variant="ghost"
        size="sm"
        className="h-7 px-2 text-green-600 hover:text-green-700 hover:bg-green-50"
        onClick={handleVerify}
        disabled={isVerifying || currentDecision === 'verified'}
        aria-label="Verify this section"
      >
        {isVerifying ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Check className="h-4 w-4" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="h-7 px-2 text-amber-600 hover:text-amber-700 hover:bg-amber-50"
        onClick={handleFlag}
        disabled={isFlagging || currentDecision === 'flagged'}
        aria-label="Flag this section"
      >
        {isFlagging ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Flag className="h-4 w-4" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="h-7 px-2 text-muted-foreground hover:text-foreground"
        onClick={onAddNote}
        aria-label="Add note to this section"
      >
        <MessageSquare className="h-4 w-4" />
      </Button>
    </div>
  );
}
