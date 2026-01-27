'use client';

/**
 * EntityMergeSuggestions Component
 *
 * Displays potential duplicate entities that lawyers may want to merge.
 * Shows as a banner at the top of the Entities tab.
 * Supports bulk selection and batch merge operations.
 *
 * Lawyer UX Improvement: Entity Auto-Merge Suggestions
 */

import { useState, useMemo } from 'react';
import { Users2, ChevronDown, ChevronUp, Merge, X, AlertCircle, CheckSquare, Square, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import type { MergeSuggestionItem } from '@/types/entity';

export interface EntityMergeSuggestionsProps {
  /** List of merge suggestions */
  suggestions: MergeSuggestionItem[];
  /** Callback when user wants to merge entities */
  onMerge: (sourceId: string, targetId: string) => Promise<void>;
  /** Callback to dismiss a suggestion */
  onDismiss?: (entityAId: string, entityBId: string) => void;
  /** Whether merge is in progress */
  isLoading?: boolean;
  /** Optional CSS class */
  className?: string;
}

/** Get pair key for a suggestion */
function getPairKey(suggestion: MergeSuggestionItem): string {
  return [suggestion.entityAId, suggestion.entityBId].sort().join('-');
}

/**
 * EntityMergeSuggestions - Banner showing potential duplicate entities.
 * Supports bulk selection and batch merge operations.
 *
 * @example
 * ```tsx
 * <EntityMergeSuggestions
 *   suggestions={suggestions}
 *   onMerge={handleMerge}
 *   onDismiss={handleDismiss}
 * />
 * ```
 */
export function EntityMergeSuggestions({
  suggestions,
  onMerge,
  onDismiss,
  isLoading = false,
  className,
}: EntityMergeSuggestionsProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState<MergeSuggestionItem | null>(null);
  const [mergeDirection, setMergeDirection] = useState<'a_to_b' | 'b_to_a'>('a_to_b');
  const [dismissedPairs, setDismissedPairs] = useState<Set<string>>(new Set());

  // Bulk selection state
  const [selectedPairs, setSelectedPairs] = useState<Set<string>>(new Set());
  const [isBulkMerging, setIsBulkMerging] = useState(false);
  const [bulkMergeProgress, setBulkMergeProgress] = useState({ current: 0, total: 0 });
  const [bulkMergeDialogOpen, setBulkMergeDialogOpen] = useState(false);

  // Filter out dismissed suggestions
  const visibleSuggestions = useMemo(() => {
    return suggestions.filter((s) => {
      const pairKey = getPairKey(s);
      return !dismissedPairs.has(pairKey);
    });
  }, [suggestions, dismissedPairs]);

  // Get selected suggestions
  const selectedSuggestions = useMemo(() => {
    return visibleSuggestions.filter((s) => selectedPairs.has(getPairKey(s)));
  }, [visibleSuggestions, selectedPairs]);

  const allSelected = visibleSuggestions.length > 0 && selectedPairs.size === visibleSuggestions.length;
  const someSelected = selectedPairs.size > 0 && selectedPairs.size < visibleSuggestions.length;

  if (visibleSuggestions.length === 0) {
    return null;
  }

  const handleToggleSelect = (suggestion: MergeSuggestionItem) => {
    const pairKey = getPairKey(suggestion);
    setSelectedPairs((prev) => {
      const next = new Set(prev);
      if (next.has(pairKey)) {
        next.delete(pairKey);
      } else {
        next.add(pairKey);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedPairs(new Set());
    } else {
      setSelectedPairs(new Set(visibleSuggestions.map(getPairKey)));
    }
  };

  const handleMergeClick = (suggestion: MergeSuggestionItem) => {
    setSelectedSuggestion(suggestion);
    setMergeDirection('a_to_b');
    setMergeDialogOpen(true);
  };

  const handleConfirmMerge = async () => {
    if (!selectedSuggestion) return;

    try {
      const sourceId = mergeDirection === 'a_to_b'
        ? selectedSuggestion.entityAId
        : selectedSuggestion.entityBId;
      const targetId = mergeDirection === 'a_to_b'
        ? selectedSuggestion.entityBId
        : selectedSuggestion.entityAId;

      await onMerge(sourceId, targetId);
      toast.success('Entities merged successfully');
      setMergeDialogOpen(false);
      // Remove from selection if it was selected
      const pairKey = getPairKey(selectedSuggestion);
      setSelectedPairs((prev) => {
        const next = new Set(prev);
        next.delete(pairKey);
        return next;
      });
    } catch {
      toast.error('Failed to merge entities');
    }
  };

  const handleBulkMergeClick = () => {
    if (selectedSuggestions.length === 0) return;
    setBulkMergeDialogOpen(true);
  };

  const handleConfirmBulkMerge = async () => {
    if (selectedSuggestions.length === 0) return;

    setIsBulkMerging(true);
    setBulkMergeProgress({ current: 0, total: selectedSuggestions.length });
    setBulkMergeDialogOpen(false);

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < selectedSuggestions.length; i++) {
      const suggestion = selectedSuggestions[i];
      if (!suggestion) continue;
      setBulkMergeProgress({ current: i + 1, total: selectedSuggestions.length });

      try {
        // For bulk merge, keep entity B (higher similarity typically means B is canonical)
        await onMerge(suggestion.entityAId, suggestion.entityBId);
        successCount++;
      } catch {
        failCount++;
      }
    }

    setIsBulkMerging(false);
    setSelectedPairs(new Set());

    if (failCount === 0) {
      toast.success(`Successfully merged ${successCount} entity pairs`);
    } else {
      toast.warning(`Merged ${successCount} pairs, ${failCount} failed`);
    }
  };

  const handleDismiss = (suggestion: MergeSuggestionItem) => {
    const pairKey = getPairKey(suggestion);
    setDismissedPairs((prev) => new Set(prev).add(pairKey));
    setSelectedPairs((prev) => {
      const next = new Set(prev);
      next.delete(pairKey);
      return next;
    });
    onDismiss?.(suggestion.entityAId, suggestion.entityBId);
  };

  return (
    <>
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <Card className={`border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20 ${className}`}>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-blue-100/50 dark:hover:bg-blue-900/20 transition-colors py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users2 className="h-5 w-5 text-blue-600" />
                  <CardTitle className="text-base">Potential Duplicates Found</CardTitle>
                  <Badge variant="outline" className="bg-blue-100 text-blue-800 border-blue-300">
                    {visibleSuggestions.length}
                  </Badge>
                </div>
                {isExpanded ? (
                  <ChevronUp className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Review these entities that may refer to the same person or organization
              </p>
            </CardHeader>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <CardContent className="space-y-2 pt-0">
              {/* Bulk actions bar */}
              <div className="flex items-center justify-between gap-2 pb-2 border-b">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleSelectAll}
                    className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    disabled={isBulkMerging}
                  >
                    {allSelected ? (
                      <CheckSquare className="h-4 w-4 text-blue-600" />
                    ) : someSelected ? (
                      <div className="h-4 w-4 border-2 border-blue-600 rounded-sm bg-blue-600/20" />
                    ) : (
                      <Square className="h-4 w-4" />
                    )}
                    {allSelected ? 'Deselect all' : 'Select all'}
                  </button>
                  {selectedPairs.size > 0 && (
                    <span className="text-sm text-muted-foreground">
                      ({selectedPairs.size} selected)
                    </span>
                  )}
                </div>

                {selectedPairs.size > 0 && (
                  <Button
                    size="sm"
                    onClick={handleBulkMergeClick}
                    disabled={isLoading || isBulkMerging}
                    className="gap-1"
                  >
                    {isBulkMerging ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Merging {bulkMergeProgress.current}/{bulkMergeProgress.total}
                      </>
                    ) : (
                      <>
                        <Merge className="h-4 w-4" />
                        Merge Selected ({selectedPairs.size})
                      </>
                    )}
                  </Button>
                )}
              </div>

              {/* Progress bar during bulk merge */}
              {isBulkMerging && (
                <div className="py-2">
                  <Progress
                    value={(bulkMergeProgress.current / bulkMergeProgress.total) * 100}
                    className="h-2"
                  />
                  <p className="text-xs text-muted-foreground text-center mt-1">
                    Merging entity pairs... {bulkMergeProgress.current} of {bulkMergeProgress.total}
                  </p>
                </div>
              )}

              {visibleSuggestions.map((suggestion) => {
                const pairKey = getPairKey(suggestion);
                const isSelected = selectedPairs.has(pairKey);

                return (
                  <div
                    key={pairKey}
                    className={`flex items-center justify-between gap-3 p-3 rounded-lg border bg-white dark:bg-gray-900 transition-colors ${
                      isSelected ? 'border-blue-400 bg-blue-50/50 dark:bg-blue-950/20' : ''
                    }`}
                  >
                    {/* Checkbox */}
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => handleToggleSelect(suggestion)}
                      disabled={isBulkMerging}
                      className="flex-shrink-0"
                    />

                    {/* Names */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm truncate" title={suggestion.entityAName}>
                          &quot;{suggestion.entityAName}&quot;
                        </span>
                        <span className="text-muted-foreground text-sm">&amp;</span>
                        <span className="font-medium text-sm truncate" title={suggestion.entityBName}>
                          &quot;{suggestion.entityBName}&quot;
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {suggestion.reason}
                      </p>
                    </div>

                    {/* Similarity Badge */}
                    <Badge
                      variant="outline"
                      className={
                        suggestion.similarityScore >= 0.85
                          ? 'bg-green-100 text-green-800 border-green-300'
                          : suggestion.similarityScore >= 0.7
                            ? 'bg-yellow-100 text-yellow-800 border-yellow-300'
                            : 'bg-gray-100 text-gray-800 border-gray-300'
                      }
                    >
                      {Math.round(suggestion.similarityScore * 100)}% match
                    </Badge>

                    {/* Actions */}
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1"
                        onClick={() => handleMergeClick(suggestion)}
                        disabled={isLoading || isBulkMerging}
                      >
                        <Merge className="h-4 w-4" />
                        Merge
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => handleDismiss(suggestion)}
                        title="Dismiss suggestion"
                        disabled={isBulkMerging}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Single Merge Confirmation Dialog */}
      <AlertDialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Merge className="h-5 w-5" />
              Merge Entities
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="text-sm text-muted-foreground space-y-3">
                <p>
                  Which name should be kept as the primary name?
                </p>
                {selectedSuggestion && (
                  <div className="space-y-2 mt-4">
                    <label className="flex items-center gap-2 p-2 rounded border cursor-pointer hover:bg-muted">
                      <input
                        type="radio"
                        name="mergeDirection"
                        checked={mergeDirection === 'b_to_a'}
                        onChange={() => setMergeDirection('b_to_a')}
                      />
                      <span>
                        Keep <strong>&quot;{selectedSuggestion.entityAName}&quot;</strong>
                      </span>
                    </label>
                    <label className="flex items-center gap-2 p-2 rounded border cursor-pointer hover:bg-muted">
                      <input
                        type="radio"
                        name="mergeDirection"
                        checked={mergeDirection === 'a_to_b'}
                        onChange={() => setMergeDirection('a_to_b')}
                      />
                      <span>
                        Keep <strong>&quot;{selectedSuggestion.entityBName}&quot;</strong>
                      </span>
                    </label>
                  </div>
                )}
                <div className="flex items-start gap-2 p-2 bg-blue-50 dark:bg-blue-950/30 rounded text-blue-800 dark:text-blue-200 text-sm mt-4">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>
                    The other name will be added as an alias. This can be undone later via entity settings.
                  </span>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmMerge} disabled={isLoading}>
              Merge Entities
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Merge Confirmation Dialog */}
      <AlertDialog open={bulkMergeDialogOpen} onOpenChange={setBulkMergeDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Merge className="h-5 w-5" />
              Merge {selectedSuggestions.length} Entity Pairs
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="text-sm text-muted-foreground space-y-3">
                <p>
                  You are about to merge {selectedSuggestions.length} pairs of entities.
                  For each pair, the second entity name will be kept as the primary name.
                </p>
                <div className="max-h-40 overflow-y-auto space-y-1 p-2 bg-muted rounded">
                  {selectedSuggestions.map((s) => (
                    <div key={getPairKey(s)} className="text-xs">
                      &quot;{s.entityAName}&quot; → &quot;{s.entityBName}&quot;
                    </div>
                  ))}
                </div>
                <div className="flex items-start gap-2 p-2 bg-amber-50 dark:bg-amber-950/30 rounded text-amber-800 dark:text-amber-200 text-sm">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>
                    This will merge all selected pairs. Each merge can be undone individually later.
                  </span>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmBulkMerge}>
              Merge All ({selectedSuggestions.length})
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
