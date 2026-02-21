'use client';

import { AlertTriangle, Loader2 } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
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
 * Handles loading, error, generating, and content states.
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
 * Map backend stage strings to human-readable labels
 */
const STAGE_LABELS: Record<string, string> = {
  queued: 'Waiting in queue...',
  db_queries: 'Gathering data from documents...',
  generating: 'Analyzing documents with AI...',
  validation_and_cache: 'Validating results...',
  retrying: 'Retrying...',
  completed: 'Finishing up...',
};

/**
 * Generating state — shown while the background worker is producing the summary
 */
function SummaryGenerating({
  progress,
  stage,
}: {
  progress?: number;
  stage?: string;
}) {
  const stageLabel = stage ? STAGE_LABELS[stage] ?? stage : 'Preparing...';
  const displayProgress = progress ?? 0;

  return (
    <div className="space-y-8">
      {/* Generating indicator card */}
      <div className="rounded-lg border bg-card p-8 text-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <div>
            <h3 className="text-lg font-semibold">Generating Summary</h3>
            <p className="mt-1 text-sm text-muted-foreground">{stageLabel}</p>
          </div>
          <div className="w-full max-w-md">
            <Progress value={displayProgress} className="h-2" />
            <p className="mt-2 text-xs text-muted-foreground">
              {displayProgress}% complete
            </p>
          </div>
        </div>
      </div>

      {/* Partial skeletons for layout stability */}
      <PartiesSectionSkeleton />
      <SubjectMatterSectionSkeleton />
      <CurrentStatusSectionSkeleton />
    </div>
  );
}

/**
 * Error state display
 */
function SummaryError({ message }: { message?: string }) {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {message || 'Failed to load summary data. Please try refreshing the page.'}
      </AlertDescription>
    </Alert>
  );
}

export function SummaryContent({ matterId }: SummaryContentProps) {
  const {
    summary,
    isLoading,
    isError,
    isGenerating,
    progress,
    stage,
    generationError,
  } = useMatterSummary(matterId);

  if (isLoading) {
    return <SummarySkeleton />;
  }

  if (isGenerating) {
    return <SummaryGenerating progress={progress} stage={stage} />;
  }

  if (isError || !summary) {
    return <SummaryError message={generationError} />;
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
