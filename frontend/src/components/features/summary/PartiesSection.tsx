'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { User, ExternalLink, CheckCircle2, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { PartyInfo, PartyRole } from '@/types/summary';

/**
 * Parties Section Component
 *
 * Displays the key parties (Petitioner, Respondent) in the matter.
 * Each party card shows entity name, source reference, and verification status.
 *
 * Story 10B.1: Summary Tab Content (AC #3)
 */

interface PartiesSectionProps {
  /** Party information array */
  parties: PartyInfo[];
  /** Optional className for styling */
  className?: string;
}

interface PartyCardProps {
  /** Party information */
  party: PartyInfo;
  /** Matter ID for navigation */
  matterId: string;
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
 */
function PartyCard({ party, matterId }: PartyCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Badge variant={getRoleBadgeVariant(party.role)}>
            {getRoleLabel(party.role)}
          </Badge>
          {party.isVerified ? (
            <Badge variant="outline" className="gap-1 text-green-600 border-green-600">
              <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
              Verified
            </Badge>
          ) : (
            <Badge variant="outline" className="gap-1 text-amber-600 border-amber-600">
              <Clock className="h-3 w-3" aria-hidden="true" />
              Pending
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="flex items-start gap-3">
          <div className="flex items-center justify-center size-10 rounded-full bg-muted">
            <User className="size-5 text-muted-foreground" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-base truncate">{party.entityName}</h3>
            <p className="text-sm text-muted-foreground mt-0.5">
              {party.sourceDocument}, p. {party.sourcePage}
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
  );
}

export function PartiesSection({ parties, className }: PartiesSectionProps) {
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

  return (
    <section className={className} aria-labelledby="parties-heading">
      <h2 id="parties-heading" className="text-lg font-semibold mb-4">
        Parties
      </h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {petitioner && <PartyCard party={petitioner} matterId={matterId} />}
        {respondent && <PartyCard party={respondent} matterId={matterId} />}
        {otherParties.map((party) => (
          <PartyCard key={party.entityId} party={party} matterId={matterId} />
        ))}
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
