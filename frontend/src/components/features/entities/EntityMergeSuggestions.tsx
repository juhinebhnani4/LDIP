'use client';

/**
 * EntityMergeSuggestions Component
 *
 * Displays potential duplicate entities that lawyers may want to merge.
 * Shows as a banner at the top of the Entities tab.
 *
 * Lawyer UX Improvement: Entity Auto-Merge Suggestions
 */

import { useState } from 'react';
import { Users2, ChevronDown, ChevronUp, Merge, X, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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

/**
 * EntityMergeSuggestions - Banner showing potential duplicate entities.
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

  // Filter out dismissed suggestions
  const visibleSuggestions = suggestions.filter((s) => {
    const pairKey = [s.entityAId, s.entityBId].sort().join('-');
    return !dismissedPairs.has(pairKey);
  });

  if (visibleSuggestions.length === 0) {
    return null;
  }

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
    } catch {
      toast.error('Failed to merge entities');
    }
  };

  const handleDismiss = (suggestion: MergeSuggestionItem) => {
    const pairKey = [suggestion.entityAId, suggestion.entityBId].sort().join('-');
    setDismissedPairs((prev) => new Set(prev).add(pairKey));
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
              {visibleSuggestions.map((suggestion) => (
                <div
                  key={`${suggestion.entityAId}-${suggestion.entityBId}`}
                  className="flex items-center justify-between gap-3 p-3 rounded-lg border bg-white dark:bg-gray-900"
                >
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
                      disabled={isLoading}
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
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Merge Confirmation Dialog */}
      <AlertDialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Merge className="h-5 w-5" />
              Merge Entities
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-3">
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
              <div className="flex items-start gap-2 p-2 bg-amber-50 dark:bg-amber-950/30 rounded text-amber-800 dark:text-amber-200 text-sm mt-4">
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <span>
                  The other name will be added as an alias. This action cannot be undone.
                </span>
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
    </>
  );
}
