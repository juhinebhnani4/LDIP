'use client';

/**
 * Verification Grouped View Component
 *
 * Displays verification queue items grouped by finding type in collapsible sections.
 *
 * Story 10D.2: Verification Statistics and Filtering (Task 4)
 * Enhancement: "By Type" grouped view
 */

import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { VerificationQueue } from './VerificationQueue';
import type { VerificationQueueItem } from '@/types';
import { formatFindingType, getFindingTypeIcon } from '@/stores/verificationStore';

interface VerificationGroupedViewProps {
  /** Queue items to display */
  data: VerificationQueueItem[];
  /** Loading state */
  isLoading?: boolean;
  /** Callback when approve is clicked */
  onApprove: (id: string) => void;
  /** Callback when reject is clicked */
  onReject: (id: string) => void;
  /** Callback when flag is clicked */
  onFlag: (id: string) => void;
  /** Currently selected IDs */
  selectedIds: string[];
  /** Callback when selection is toggled */
  onToggleSelect: (id: string) => void;
  /** Callback when all rows are selected */
  onSelectAll: (ids: string[]) => void;
  /** IDs currently being processed */
  processingIds?: string[];
}

/**
 * Group header component for each finding type section
 */
function GroupHeader({
  type,
  count,
  isOpen,
}: {
  type: string;
  count: number;
  isOpen: boolean;
}) {
  return (
    <div className="flex items-center gap-3 w-full">
      <span className="text-muted-foreground">
        {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </span>
      <span className="text-lg">{getFindingTypeIcon(type)}</span>
      <span className="font-medium">{formatFindingType(type)}</span>
      <Badge variant="secondary" className="ml-auto">
        {count} {count === 1 ? 'item' : 'items'}
      </Badge>
    </div>
  );
}

/**
 * Verification queue grouped by finding type.
 *
 * Features:
 * - Groups items by findingType
 * - Collapsible sections with count badges
 * - Preserves sorting within each group
 * - All sections open by default
 *
 * @example
 * ```tsx
 * <VerificationGroupedView
 *   data={filteredQueue}
 *   onApprove={handleApprove}
 *   onReject={handleReject}
 *   onFlag={handleFlag}
 *   selectedIds={selectedIds}
 *   onToggleSelect={handleToggle}
 *   onSelectAll={handleSelectAll}
 * />
 * ```
 */
export function VerificationGroupedView({
  data,
  isLoading = false,
  onApprove,
  onReject,
  onFlag,
  selectedIds,
  onToggleSelect,
  onSelectAll,
  processingIds = [],
}: VerificationGroupedViewProps) {
  // Group items by findingType
  const groupedData = useMemo(() => {
    const groups = new Map<string, VerificationQueueItem[]>();

    data.forEach((item) => {
      const existing = groups.get(item.findingType) ?? [];
      groups.set(item.findingType, [...existing, item]);
    });

    // Sort groups alphabetically by type name
    const sortedEntries = Array.from(groups.entries()).sort(([a], [b]) =>
      a.localeCompare(b)
    );

    return sortedEntries;
  }, [data]);

  // Track which sections are open (all open by default)
  // Use a Set that starts empty - we'll compute "all open" dynamically
  const [closedSections, setClosedSections] = useState<Set<string>>(new Set());

  // Toggle section open state (tracks closed sections - all open by default)
  const toggleSection = (type: string) => {
    setClosedSections((prev: Set<string>) => {
      const next = new Set(prev);
      if (next.has(type)) {
        // Currently closed, open it
        next.delete(type);
      } else {
        // Currently open, close it
        next.add(type);
      }
      return next;
    });
  };

  // Check if a section is open (open = NOT in closedSections)
  const isSectionOpen = (type: string) => !closedSections.has(type);

  // Handle "select all" for grouped view - only select visible items in open sections
  const handleGroupSelectAll = (ids: string[]) => {
    onSelectAll(ids);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-muted rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // Empty state
  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No verifications pending.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {groupedData.map(([type, items]) => {
        const isOpen = isSectionOpen(type);
        const groupSelectedIds = selectedIds.filter((id) =>
          items.some((item) => item.id === id)
        );

        return (
          <Collapsible
            key={type}
            open={isOpen}
            onOpenChange={() => toggleSection(type)}
          >
            <div className="rounded-lg border bg-card">
              <CollapsibleTrigger asChild>
                <Button
                  variant="ghost"
                  className="w-full justify-start px-4 py-3 h-auto hover:bg-muted/50"
                >
                  <GroupHeader type={type} count={items.length} isOpen={isOpen} />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="px-2 pb-2">
                  <VerificationQueue
                    data={items}
                    isLoading={false}
                    onApprove={onApprove}
                    onReject={onReject}
                    onFlag={onFlag}
                    selectedIds={groupSelectedIds}
                    onToggleSelect={onToggleSelect}
                    onSelectAll={(ids) => handleGroupSelectAll(ids)}
                    processingIds={processingIds}
                  />
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}
