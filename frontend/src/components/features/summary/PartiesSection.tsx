'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { User, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { InlineVerificationButtons } from './InlineVerificationButtons';
import { VerificationBadge } from './VerificationBadge';
import { SummaryNotesDialog } from './SummaryNotesDialog';
import { CitationLink } from './CitationLink';
import type { PartyInfo, PartyRole, SummaryVerificationDecision } from '@/types/summary';

/**
 * Parties Section Component
 *
 * Displays the key parties (Petitioner, Respondent) in the matter.
 * Each party card shows entity name, source reference, and verification status.
 * Now includes inline verification buttons on hover.
 *
 * Story 10B.1: Summary Tab Content (AC #3)
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 * Story 14.6: Integrated CitationLink (AC #3, #6)
 */

interface PartiesSectionProps {
  /** Party information array */
  parties: PartyInfo[];
  /** Optional className for styling */
  className?: string;
  /** Callback when a party is verified */
  onVerifyParty?: (entityId: string) => Promise<void>;
  /** Callback when a party is flagged */
  onFlagParty?: (entityId: string) => Promise<void>;
  /** Callback when note is saved for a party */
  onSavePartyNote?: (entityId: string, note: string) => Promise<void>;
}

interface PartyCardProps {
  /** Party information */
  party: PartyInfo;
  /** Matter ID for navigation */
  matterId: string;
  /** Callback when verified */
  onVerify?: () => Promise<void>;
  /** Callback when flagged */
  onFlag?: () => Promise<void>;
  /** Callback when note is saved */
  onSaveNote?: (note: string) => Promise<void>;
}

/**
 * Get display label for party role
 */
function getRoleLabel(role: PartyRole): string {
  switch (role) {
    case 'petitioner':
      return 'Petitioner';
    case 'respondent':
      return 'Respondent';
    case 'other':
      return 'Other Party';
  }
}

/**
 * Get role badge variant
 */
function getRoleBadgeVariant(role: PartyRole): 'default' | 'secondary' | 'outline' {
  switch (role) {
    case 'petitioner':
      return 'default';
    case 'respondent':
      return 'secondary';
    case 'other':
      return 'outline';
  }
}

/**
 * Individual party card
 *
 * Story 14.6: Added CitationLink for source reference (AC #6)
 */
function PartyCard({ party, matterId, onVerify, onFlag, onSaveNote }: PartyCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isNotesDialogOpen, setIsNotesDialogOpen] = useState(false);
  const [verificationDecision, setVerificationDecision] = useState<SummaryVerificationDecision | undefined>(
    party.isVerified ? 'verified' : undefined
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
    <>
      <Card
        className="relative"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <Badge variant={getRoleBadgeVariant(party.role)}>
              {getRoleLabel(party.role)}
            </Badge>
            <div className="flex items-center gap-2">
              <InlineVerificationButtons
                sectionType="parties"
                sectionId={party.entityId}
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
          <div className="flex items-start gap-3">
            <div className="flex items-center justify-center size-10 rounded-full bg-muted">
              <User className="size-5 text-muted-foreground" aria-hidden="true" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-base truncate">{party.entityName}</h3>
              {/* Story 14.6: Use CitationLink if citation available */}
              <p className="text-sm text-muted-foreground mt-0.5">
                {party.citation ? (
                  <CitationLink
                    documentName={party.citation.documentName}
                    pageNumber={party.citation.page}
                    excerpt={party.citation.excerpt}
                    displayText={`${party.sourceDocument}, p. ${party.sourcePage}`}
                  />
                ) : (
                  <span>{party.sourceDocument}, p. {party.sourcePage}</span>
                )}
              </p>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <Button asChild variant="outline" size="sm" className="flex-1">
              <Link href={`/matters/${matterId}/entities?entityId=${party.entityId}`}>
                <User className="h-4 w-4 mr-1.5" aria-hidden="true" />
                View Entity
              </Link>
            </Button>
            <Button
              asChild
              variant="ghost"
              size="sm"
              className="flex-1"
            >
              <Link
                href={`/matters/${matterId}/documents?doc=${encodeURIComponent(party.sourceDocument)}&page=${party.sourcePage}`}
                aria-label={`View source: ${party.sourceDocument}, page ${party.sourcePage}`}
              >
                <ExternalLink className="h-4 w-4 mr-1.5" aria-hidden="true" />
                View Source
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <SummaryNotesDialog
        isOpen={isNotesDialogOpen}
        onClose={() => setIsNotesDialogOpen(false)}
        onSave={handleSaveNote}
        sectionType="parties"
        sectionId={party.entityId}
      />
    </>
  );
}

export function PartiesSection({
  parties,
  className,
  onVerifyParty,
  onFlagParty,
  onSavePartyNote,
}: PartiesSectionProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // Separate petitioner and respondent from other parties
  const petitioner = parties.find((p) => p.role === 'petitioner');
  const respondent = parties.find((p) => p.role === 'respondent');
  const otherParties = parties.filter((p) => p.role === 'other');

  if (parties.length === 0) {
    return (
      <section className={className}>
        <h2 className="text-lg font-semibold mb-4">Parties</h2>
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No parties have been identified yet.
          </CardContent>
        </Card>
      </section>
    );
  }

  const renderPartyCard = (party: PartyInfo) => (
    <PartyCard
      key={party.entityId}
      party={party}
      matterId={matterId}
      onVerify={onVerifyParty ? () => onVerifyParty(party.entityId) : undefined}
      onFlag={onFlagParty ? () => onFlagParty(party.entityId) : undefined}
      onSaveNote={onSavePartyNote ? (note) => onSavePartyNote(party.entityId, note) : undefined}
    />
  );

  return (
    <section className={className} aria-labelledby="parties-heading">
      <h2 id="parties-heading" className="text-lg font-semibold mb-4">
        Parties
      </h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {petitioner && renderPartyCard(petitioner)}
        {respondent && renderPartyCard(respondent)}
        {otherParties.map(renderPartyCard)}
      </div>
    </section>
  );
}

/**
 * Parties Section Skeleton
 */
export function PartiesSectionSkeleton({ className }: { className?: string }) {
  return (
    <section className={className}>
      <Skeleton className="h-6 w-20 mb-4" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-5 w-16" />
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="flex items-start gap-3">
              <Skeleton className="size-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-24" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <Skeleton className="h-9 flex-1" />
              <Skeleton className="h-9 flex-1" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-5 w-16" />
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="flex items-start gap-3">
              <Skeleton className="size-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-24" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <Skeleton className="h-9 flex-1" />
              <Skeleton className="h-9 flex-1" />
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
