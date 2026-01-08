'use client';

import type { OCRQualityStatus } from '@/types/document';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface OCRQualityBadgeProps {
  status: OCRQualityStatus | null;
  confidence?: number | null;
  showPercentage?: boolean;
  className?: string;
}

const STATUS_CONFIG: Record<
  OCRQualityStatus,
  { label: string; className: string; icon: string }
> = {
  good: {
    label: 'Good',
    className: 'bg-green-100 text-green-800 border-green-200 hover:bg-green-200',
    icon: '',
  },
  fair: {
    label: 'Fair',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-200 hover:bg-yellow-200',
    icon: '',
  },
  poor: {
    label: 'Poor',
    className: 'bg-red-100 text-red-800 border-red-200 hover:bg-red-200',
    icon: '',
  },
};

/**
 * Color-coded badge for OCR quality status
 *
 * Colors:
 * - good (>85%): green
 * - fair (70-85%): yellow
 * - poor (<70%): red
 *
 * Optionally shows the confidence percentage.
 */
export function OCRQualityBadge({
  status,
  confidence,
  showPercentage = false,
  className,
}: OCRQualityBadgeProps) {
  // Handle null status (OCR not complete)
  if (!status) {
    return (
      <Badge
        variant="outline"
        className={cn('bg-gray-100 text-gray-600 border-gray-200', className)}
      >
        Pending
      </Badge>
    );
  }

  const config = STATUS_CONFIG[status];
  const percentageText = showPercentage && confidence != null
    ? ` (${Math.round(confidence * 100)}%)`
    : '';

  const badge = (
    <Badge
      variant="outline"
      className={cn(config.className, className)}
    >
      {config.label}{percentageText}
    </Badge>
  );

  // Show tooltip for poor quality explaining manual review may be needed
  if (status === 'poor') {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            {badge}
          </TooltipTrigger>
          <TooltipContent>
            <p>OCR quality is low. Manual review may be needed for accuracy.</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return badge;
}
