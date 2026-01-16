'use client';

import { useCallback, useEffect, useState } from 'react';
import type { OCRConfidenceResult, PageConfidence, OCRQualityStatus } from '@/types/document';
import { fetchOCRQuality } from '@/lib/api/documents';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  OCR_QUALITY_GOOD_THRESHOLD,
  OCR_QUALITY_FAIR_THRESHOLD,
} from '@/lib/constants/ocr';
import { ManualReviewDialog } from './ManualReviewDialog';

interface OCRQualityDetailProps {
  documentId: string;
  className?: string;
  onPageClick?: (pageNumber: number) => void;
}

/** Status configuration - jaanch.ai brand palette */
const STATUS_CONFIG: Record<OCRQualityStatus, { label: string; color: string }> = {
  good: { label: 'Good Quality', color: 'text-[#2d5a3d] dark:text-[#4a8a5d]' }, // Forest Green
  fair: { label: 'Fair Quality', color: 'text-[#b8973b] dark:text-[#c4a85a]' }, // Muted Gold
  poor: { label: 'Poor Quality', color: 'text-[#8b2635] dark:text-[#c44d5e]' }, // Burgundy
};

/** Progress bar colors - jaanch.ai brand palette */
function getProgressColor(confidence: number): string {
  if (confidence >= OCR_QUALITY_GOOD_THRESHOLD) return 'bg-[#2d5a3d]'; // Forest Green
  if (confidence >= OCR_QUALITY_FAIR_THRESHOLD) return 'bg-[#b8973b]'; // Muted Gold
  return 'bg-[#8b2635]'; // Burgundy
}

function OCRQualityDetailSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-6 w-16" />
        </div>
        <Skeleton className="h-2 w-full" />
        <div className="grid grid-cols-5 gap-2 mt-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function OCRQualityDetail({
  documentId,
  className,
  onPageClick,
}: OCRQualityDetailProps) {
  const [quality, setQuality] = useState<OCRConfidenceResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showReviewDialog, setShowReviewDialog] = useState(false);

  const loadQuality = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await fetchOCRQuality(documentId);
      setQuality(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load OCR quality';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    loadQuality();
  }, [loadQuality]);

  if (isLoading) {
    return <OCRQualityDetailSkeleton />;
  }

  if (error) {
    return (
      <Card className={cn('border-destructive', className)}>
        <CardContent className="pt-6">
          <p className="text-destructive text-center">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!quality) {
    return null;
  }

  const statusConfig = quality.qualityStatus ? STATUS_CONFIG[quality.qualityStatus] : null;
  const overallPercentage = quality.overallConfidence != null
    ? Math.round(quality.overallConfidence * 100)
    : null;

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>OCR Quality</span>
          {statusConfig && (
            <span className={cn('text-sm font-normal', statusConfig.color)}>
              {statusConfig.label}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Overall confidence */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Overall Confidence</span>
            <span className="font-medium">
              {overallPercentage != null ? `${overallPercentage}%` : 'N/A'}
            </span>
          </div>
          {quality.overallConfidence != null && (
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className={cn('h-full transition-all', getProgressColor(quality.overallConfidence))}
                style={{ width: `${quality.overallConfidence * 100}%` }}
              />
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {quality.totalWords.toLocaleString()} words analyzed across{' '}
            {quality.pageConfidences.length} pages
          </p>
        </div>

        {/* Per-page confidence grid */}
        {quality.pageConfidences.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Per-Page Quality</h4>
            <div className="grid grid-cols-5 gap-2">
              {quality.pageConfidences.map((page) => (
                <PageConfidenceButton
                  key={page.pageNumber}
                  page={page}
                  onClick={() => onPageClick?.(page.pageNumber)}
                />
              ))}
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground mt-2">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded bg-[#2d5a3d]" /> Good (85%+)
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded bg-[#b8973b]" /> Fair (70-85%)
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded bg-[#8b2635]" /> Poor (&lt;70%)
              </span>
            </div>
          </div>
        )}

        {/* Request Manual Review button - shown when quality is poor or fair */}
        {quality.qualityStatus && quality.qualityStatus !== 'good' && (
          <Button
            variant="outline"
            className="w-full mt-4"
            onClick={() => setShowReviewDialog(true)}
          >
            Request Manual Review
          </Button>
        )}
      </CardContent>

      {/* Manual Review Dialog */}
      {quality.pageConfidences.length > 0 && (
        <ManualReviewDialog
          documentId={documentId}
          pageConfidences={quality.pageConfidences}
          open={showReviewDialog}
          onOpenChange={setShowReviewDialog}
          onSuccess={loadQuality}
        />
      )}
    </Card>
  );
}

interface PageConfidenceButtonProps {
  page: PageConfidence;
  onClick?: () => void;
}

/** Page confidence button - jaanch.ai brand palette */
function PageConfidenceButton({ page, onClick }: PageConfidenceButtonProps) {
  const percentage = Math.round(page.confidence * 100);
  const bgColor = page.confidence >= OCR_QUALITY_GOOD_THRESHOLD
    ? 'bg-[#e5f0e8] hover:bg-[#d5e8da] border-[#2d5a3d]/20' // Forest Green tint
    : page.confidence >= OCR_QUALITY_FAIR_THRESHOLD
      ? 'bg-[#f5f0e0] hover:bg-[#efe8d0] border-[#b8973b]/20' // Muted Gold tint
      : 'bg-[#f2d4d7] hover:bg-[#eac4c8] border-[#8b2635]/20'; // Burgundy tint

  return (
    <button
      type="button"
      className={cn(
        'flex flex-col items-center justify-center p-2 rounded border text-xs transition-colors',
        bgColor,
        onClick && 'cursor-pointer'
      )}
      onClick={onClick}
      title={`Page ${page.pageNumber}: ${percentage}% confidence (${page.wordCount} words)`}
    >
      <span className="font-medium">P{page.pageNumber}</span>
      <span className="text-muted-foreground">{percentage}%</span>
    </button>
  );
}
