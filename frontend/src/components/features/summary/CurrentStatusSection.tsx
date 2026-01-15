'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Calendar, ExternalLink, CheckCircle2, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { CurrentStatus } from '@/types/summary';

/**
 * Current Status Section Component
 *
 * Displays the current status of proceedings including last order date and description.
 *
 * Story 10B.1: Summary Tab Content (AC #1)
 */

interface CurrentStatusSectionProps {
  /** Current status data */
  currentStatus: CurrentStatus;
  /** Optional className for styling */
  className?: string;
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
}: CurrentStatusSectionProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;
  const formattedDate = formatDate(currentStatus.lastOrderDate);

  return (
    <section className={className} aria-labelledby="current-status-heading">
      <h2 id="current-status-heading" className="text-lg font-semibold mb-4">
        Current Status
      </h2>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <CardTitle className="text-base">Last Order: {formattedDate}</CardTitle>
            </div>
            {currentStatus.isVerified ? (
              <Badge variant="outline" className="gap-1 text-green-600 border-green-600">
                <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                Verified
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1 text-amber-600 border-amber-600">
                <Clock className="h-3 w-3" aria-hidden="true" />
                Pending Verification
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <p className="text-sm leading-relaxed">{currentStatus.description}</p>

          {/* Source reference */}
          <div className="mt-4 pt-4 border-t flex items-center justify-between flex-wrap gap-4">
            <div className="text-sm text-muted-foreground">
              Source: {currentStatus.sourceDocument}, p. {currentStatus.sourcePage}
            </div>
            <div className="flex gap-2">
              <Button asChild variant="ghost" size="sm">
                <Link
                  href={`/matters/${matterId}/documents?doc=${encodeURIComponent(currentStatus.sourceDocument)}&page=${currentStatus.sourcePage}`}
                  aria-label={`View full order: ${currentStatus.sourceDocument}, page ${currentStatus.sourcePage}`}
                >
                  <ExternalLink className="h-4 w-4 mr-1.5" aria-hidden="true" />
                  View Full Order
                </Link>
              </Button>
              {!currentStatus.isVerified && (
                <Button variant="outline" size="sm">
                  <CheckCircle2 className="h-4 w-4 mr-1.5" aria-hidden="true" />
                  Verify
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
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
