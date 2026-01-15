'use client';

import { AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useMatterSummary } from '@/hooks/useMatterSummary';
import {
  AttentionBanner,
  AttentionBannerSkeleton,
  PartiesSection,
  PartiesSectionSkeleton,
  SubjectMatterSection,
  SubjectMatterSectionSkeleton,
  CurrentStatusSection,
  CurrentStatusSectionSkeleton,
  KeyIssuesSection,
  KeyIssuesSectionSkeleton,
  MatterStatistics,
  MatterStatisticsSkeleton,
} from './index';

/**
 * Summary Content Component
 *
 * Client component that fetches and displays the complete matter summary.
 * Handles loading, error, and content states.
 *
 * Story 10B.1: Summary Tab Content
 */

interface SummaryContentProps {
  /** Matter ID */
  matterId: string;
}

/**
 * Loading skeleton for the entire summary page
 */
function SummarySkeleton() {
  return (
    <div className="space-y-8">
      <AttentionBannerSkeleton />
      <PartiesSectionSkeleton />
      <SubjectMatterSectionSkeleton />
      <CurrentStatusSectionSkeleton />
      <KeyIssuesSectionSkeleton />
      <MatterStatisticsSkeleton />
    </div>
  );
}

/**
 * Error state display
 */
function SummaryError() {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        Failed to load summary data. Please try refreshing the page.
      </AlertDescription>
    </Alert>
  );
}

export function SummaryContent({ matterId }: SummaryContentProps) {
  const { summary, isLoading, isError } = useMatterSummary(matterId);

  if (isLoading) {
    return <SummarySkeleton />;
  }

  if (isError || !summary) {
    return <SummaryError />;
  }

  return (
    <div className="space-y-8">
      {/* Attention Banner - Only show if there are items needing attention */}
      {summary.attentionItems.length > 0 && (
        <AttentionBanner items={summary.attentionItems} />
      )}

      {/* Parties Section */}
      <PartiesSection parties={summary.parties} />

      {/* Subject Matter */}
      <SubjectMatterSection subjectMatter={summary.subjectMatter} />

      {/* Current Status */}
      <CurrentStatusSection currentStatus={summary.currentStatus} />

      {/* Key Issues */}
      <KeyIssuesSection keyIssues={summary.keyIssues} />

      {/* Matter Statistics */}
      <MatterStatistics stats={summary.stats} />
    </div>
  );
}
