'use client';

/**
 * EntityContradictionGroup Component
 *
 * Displays a collapsible group of contradictions for a single entity,
 * with entity name header and contradiction count.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 3: Create EntityContradictionGroup component
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ContradictionCard } from './ContradictionCard';
import type { EntityContradictions } from '@/hooks/useContradictions';

interface EntityContradictionGroupProps {
  /** Entity group data */
  group: EntityContradictions;
  /** Whether the group should be initially expanded */
  defaultExpanded?: boolean;
  /** Optional callback when document link is clicked */
  onDocumentClick?: (documentId: string, page: number | null) => void;
  /** Optional callback when evidence link is clicked */
  onEvidenceClick?: (documentId: string, page: number | null, bboxIds: string[]) => void;
}

/**
 * EntityContradictionGroup displays contradictions grouped by entity.
 *
 * @example
 * ```tsx
 * <EntityContradictionGroup
 *   group={entityGroup}
 *   defaultExpanded={index < 3}
 *   onDocumentClick={(docId, page) => openPdfViewer(docId, page)}
 * />
 * ```
 */
export function EntityContradictionGroup({
  group,
  defaultExpanded = false,
  onDocumentClick,
  onEvidenceClick,
}: EntityContradictionGroupProps) {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg bg-card">
        {/* Header */}
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full justify-between px-4 py-3 h-auto hover:bg-muted/50"
          >
            <div className="flex items-center gap-3">
              <User className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">{group.entityName}</span>
              <span className="text-sm text-muted-foreground">
                ({group.count} contradiction{group.count !== 1 ? 's' : ''})
              </span>
            </div>
            {isOpen ? (
              <ChevronDown className="h-5 w-5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            )}
          </Button>
        </CollapsibleTrigger>

        {/* Content */}
        <CollapsibleContent>
          <div className="px-4 pb-4 space-y-3">
            {group.contradictions.map((contradiction) => (
              <ContradictionCard
                key={contradiction.id}
                contradiction={contradiction}
                onDocumentClick={onDocumentClick}
                onEvidenceClick={onEvidenceClick}
              />
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
