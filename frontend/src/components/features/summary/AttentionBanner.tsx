'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ChevronRight } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AttentionItem } from '@/types/summary';

/**
 * Attention Banner Component
 *
 * Displays items requiring user attention (contradictions, citation issues, timeline gaps).
 * Each item links to the relevant tab for resolution.
 *
 * Story 10B.1: Summary Tab Content (AC #2)
 */

interface AttentionBannerProps {
  /** Items requiring attention */
  items: AttentionItem[];
  /** Optional className for styling */
  className?: string;
}

interface AttentionItemRowProps {
  /** Attention item data */
  item: AttentionItem;
  /** Matter ID for link building */
  matterId: string;
}

/**
 * Single attention item row
 */
function AttentionItemRow({ item, matterId }: AttentionItemRowProps) {
  return (
    <Link
      href={`/matter/${matterId}/${item.targetTab}`}
      className="flex items-center justify-between w-full py-2 px-3 rounded-md hover:bg-destructive/10 transition-colors text-left group"
      aria-label={`${item.count} ${item.label}. Click to review in ${item.targetTab} tab.`}
    >
      <span className="text-sm">
        <span className="font-semibold">{item.count}</span>{' '}
        <span className="text-muted-foreground">{item.label}</span>
      </span>
      <ChevronRight
        className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors"
        aria-hidden="true"
      />
    </Link>
  );
}

export function AttentionBanner({ items, className }: AttentionBannerProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // Don't render if no items need attention
  if (!items || items.length === 0) {
    return null;
  }

  const totalIssues = items.reduce((sum, item) => sum + item.count, 0);

  return (
    <Alert variant="destructive" className={className}>
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle className="flex items-center justify-between">
        <span>
          {totalIssues} {totalIssues === 1 ? 'item needs' : 'items need'} attention
        </span>
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="h-7 text-xs hover:bg-destructive/20"
        >
          <Link href={`/matter/${matterId}/verification`}>Review All</Link>
        </Button>
      </AlertTitle>
      <AlertDescription className="mt-2">
        <div className="space-y-1">
          {items.map((item) => (
            <AttentionItemRow key={item.type} item={item} matterId={matterId} />
          ))}
        </div>
      </AlertDescription>
    </Alert>
  );
}

/**
 * Attention Banner Skeleton
 */
export function AttentionBannerSkeleton({ className }: { className?: string }) {
  return (
    <div className={className}>
      <div className="h-32 bg-muted/50 rounded-lg animate-pulse" />
    </div>
  );
}
