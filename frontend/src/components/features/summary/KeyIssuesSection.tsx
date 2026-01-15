'use client';

import { useState } from 'react';
import { CheckCircle2, Clock, Flag } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { InlineVerificationButtons } from './InlineVerificationButtons';
import { SummaryNotesDialog } from './SummaryNotesDialog';
import type { KeyIssue, KeyIssueVerificationStatus, SummaryVerificationDecision } from '@/types/summary';

/**
 * Key Issues Section Component
 *
 * Displays the numbered list of key issues with verification status badges.
 * Now includes inline verification buttons on hover.
 *
 * Story 10B.1: Summary Tab Content (AC #1)
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 */

interface KeyIssuesSectionProps {
  /** Key issues array */
  keyIssues: KeyIssue[];
  /** Optional className for styling */
  className?: string;
  /** Callback when an issue is verified */
  onVerifyIssue?: (issueId: string) => Promise<void>;
  /** Callback when an issue is flagged */
  onFlagIssue?: (issueId: string) => Promise<void>;
  /** Callback when note is saved for an issue */
  onSaveIssueNote?: (issueId: string, note: string) => Promise<void>;
}

interface IssueVerificationBadgeProps {
  /** Verification status */
  status: KeyIssueVerificationStatus;
}

/**
 * Verification status badge for key issues
 */
function IssueVerificationBadge({ status }: IssueVerificationBadgeProps) {
  switch (status) {
    case 'verified':
      return (
        <Badge variant="outline" className="gap-1 text-green-600 border-green-600">
          <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
          Verified
        </Badge>
      );
    case 'pending':
      return (
        <Badge variant="outline" className="gap-1 text-amber-600 border-amber-600">
          <Clock className="h-3 w-3" aria-hidden="true" />
          Pending
        </Badge>
      );
    case 'flagged':
      return (
        <Badge variant="outline" className="gap-1 text-red-600 border-red-600">
          <Flag className="h-3 w-3" aria-hidden="true" />
          Flagged
        </Badge>
      );
    default:
      return null;
  }
}

interface KeyIssueItemProps {
  /** Key issue data */
  issue: KeyIssue;
  /** Callback when verified */
  onVerify?: () => Promise<void>;
  /** Callback when flagged */
  onFlag?: () => Promise<void>;
  /** Callback when note is saved */
  onSaveNote?: (note: string) => Promise<void>;
}

/**
 * Individual key issue item with inline verification
 */
function KeyIssueItem({ issue, onVerify, onFlag, onSaveNote }: KeyIssueItemProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isNotesDialogOpen, setIsNotesDialogOpen] = useState(false);
  const [verificationDecision, setVerificationDecision] = useState<SummaryVerificationDecision | undefined>(
    issue.verificationStatus === 'verified' ? 'verified' :
    issue.verificationStatus === 'flagged' ? 'flagged' : undefined
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

  // Determine current status for badge display
  const currentStatus: KeyIssueVerificationStatus =
    verificationDecision === 'verified' ? 'verified' :
    verificationDecision === 'flagged' ? 'flagged' :
    issue.verificationStatus;

  return (
    <>
      <li
        className="flex items-start gap-3 py-3 relative"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <span
          className="flex items-center justify-center size-7 rounded-full bg-primary text-primary-foreground text-sm font-medium shrink-0"
          aria-hidden="true"
        >
          {issue.number}
        </span>
        <div className="flex-1 min-w-0 pt-0.5">
          <p className="text-sm leading-relaxed">{issue.title}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <InlineVerificationButtons
            sectionType="key_issue"
            sectionId={issue.id}
            currentDecision={verificationDecision}
            onVerify={handleVerify}
            onFlag={handleFlag}
            onAddNote={() => setIsNotesDialogOpen(true)}
            isVisible={isHovered}
          />
          <IssueVerificationBadge status={currentStatus} />
        </div>
      </li>

      <SummaryNotesDialog
        isOpen={isNotesDialogOpen}
        onClose={() => setIsNotesDialogOpen(false)}
        onSave={handleSaveNote}
        sectionType="key_issue"
        sectionId={issue.id}
      />
    </>
  );
}

export function KeyIssuesSection({
  keyIssues,
  className,
  onVerifyIssue,
  onFlagIssue,
  onSaveIssueNote,
}: KeyIssuesSectionProps) {
  if (keyIssues.length === 0) {
    return (
      <section className={className} aria-labelledby="key-issues-heading">
        <h2 id="key-issues-heading" className="text-lg font-semibold mb-4">
          Key Issues
        </h2>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No key issues have been identified yet.
          </CardContent>
        </Card>
      </section>
    );
  }

  // Count by status
  const verifiedCount = keyIssues.filter((i) => i.verificationStatus === 'verified').length;
  const pendingCount = keyIssues.filter((i) => i.verificationStatus === 'pending').length;
  const flaggedCount = keyIssues.filter((i) => i.verificationStatus === 'flagged').length;

  return (
    <section className={className} aria-labelledby="key-issues-heading">
      <h2 id="key-issues-heading" className="text-lg font-semibold mb-4">
        Key Issues
      </h2>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{keyIssues.length} Issues Identified</CardTitle>
            <div className="flex items-center gap-2 text-xs">
              {verifiedCount > 0 && (
                <span className="text-green-600">{verifiedCount} verified</span>
              )}
              {pendingCount > 0 && (
                <span className="text-amber-600">{pendingCount} pending</span>
              )}
              {flaggedCount > 0 && (
                <span className="text-red-600">{flaggedCount} flagged</span>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <ol className="divide-y" aria-label="Key issues list">
            {keyIssues.map((issue) => (
              <KeyIssueItem
                key={issue.id}
                issue={issue}
                onVerify={onVerifyIssue ? () => onVerifyIssue(issue.id) : undefined}
                onFlag={onFlagIssue ? () => onFlagIssue(issue.id) : undefined}
                onSaveNote={onSaveIssueNote ? (note) => onSaveIssueNote(issue.id, note) : undefined}
              />
            ))}
          </ol>
        </CardContent>
      </Card>
    </section>
  );
}

/**
 * Key Issues Section Skeleton
 */
export function KeyIssuesSectionSkeleton({ className }: { className?: string }) {
  return (
    <section className={className}>
      <Skeleton className="h-6 w-24 mb-4" />
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-36" />
            <Skeleton className="h-4 w-32" />
          </div>
        </CardHeader>
        <CardContent className="pt-0 divide-y">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-start gap-3 py-3">
              <Skeleton className="size-7 rounded-full shrink-0" />
              <div className="flex-1 space-y-1 pt-0.5">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-1/2" />
              </div>
              <Skeleton className="h-5 w-16 shrink-0" />
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}
