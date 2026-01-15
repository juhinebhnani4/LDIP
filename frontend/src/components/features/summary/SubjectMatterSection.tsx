'use client';

import { FileText, ExternalLink, CheckCircle2, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { SubjectMatter } from '@/types/summary';

/**
 * Subject Matter Section Component
 *
 * Displays the AI-generated subject matter description with source citations.
 *
 * Story 10B.1: Summary Tab Content (AC #1)
 */

interface SubjectMatterSectionProps {
  /** Subject matter data */
  subjectMatter: SubjectMatter;
  /** Optional className for styling */
  className?: string;
}

export function SubjectMatterSection({
  subjectMatter,
  className,
}: SubjectMatterSectionProps) {
  return (
    <section className={className} aria-labelledby="subject-matter-heading">
      <h2 id="subject-matter-heading" className="text-lg font-semibold mb-4">
        Subject Matter
      </h2>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <CardTitle className="text-base">Case Overview</CardTitle>
            </div>
            {subjectMatter.isVerified ? (
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
          <p className="text-sm leading-relaxed">{subjectMatter.description}</p>

          {/* Source citations */}
          {subjectMatter.sources.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-xs text-muted-foreground mb-2">Sources:</p>
              <div className="flex flex-wrap gap-2">
                {subjectMatter.sources.map((source, index) => (
                  <Button
                    key={`${source.documentName}-${index}`}
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                  >
                    <ExternalLink className="h-3 w-3 mr-1" aria-hidden="true" />
                    {source.documentName} (pp. {source.pageRange})
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Verification button */}
          {!subjectMatter.isVerified && (
            <div className="mt-4 pt-4 border-t">
              <Button variant="outline" size="sm">
                <CheckCircle2 className="h-4 w-4 mr-1.5" aria-hidden="true" />
                Verify
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

/**
 * Subject Matter Section Skeleton
 */
export function SubjectMatterSectionSkeleton({ className }: { className?: string }) {
  return (
    <section className={className}>
      <Skeleton className="h-6 w-32 mb-4" />
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-5" />
              <Skeleton className="h-5 w-28" />
            </div>
            <Skeleton className="h-5 w-24" />
          </div>
        </CardHeader>
        <CardContent className="pt-2 space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <div className="pt-4 border-t mt-4">
            <Skeleton className="h-3 w-16 mb-2" />
            <div className="flex gap-2">
              <Skeleton className="h-7 w-36" />
              <Skeleton className="h-7 w-32" />
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
