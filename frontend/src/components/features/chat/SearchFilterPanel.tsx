'use client';

/**
 * Search Filter Panel
 *
 * Gap 4: Collapsible panel for metadata filtering during chat.
 * Allows users to scope search to specific documents, types, or page ranges.
 */

import { useState, useCallback, useMemo } from 'react';
import { Filter, X, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { useDocuments } from '@/hooks/useDocuments';
import type { SearchFilters } from '@/types/search';
import { DOCUMENT_TYPE_OPTIONS } from '@/types/search';

interface SearchFilterPanelProps {
  matterId: string;
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

/** Count active filters for badge */
function countActiveFilters(filters: SearchFilters): number {
  let count = 0;
  if (filters.documentIds?.length) count++;
  if (filters.documentTypes?.length) count++;
  if (filters.pageMin != null || filters.pageMax != null) count++;
  return count;
}

export function SearchFilterPanel({ matterId, filters, onChange }: SearchFilterPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { documents } = useDocuments(matterId, { perPage: 100 });
  const activeCount = countActiveFilters(filters);

  const handleClearAll = useCallback(() => {
    onChange({});
  }, [onChange]);

  const toggleDocType = useCallback((type: string) => {
    const current = filters.documentTypes ?? [];
    const next = current.includes(type as 'case_file')
      ? current.filter((t) => t !== type)
      : [...current, type as 'case_file' | 'act' | 'annexure' | 'other'];
    onChange({ ...filters, documentTypes: next.length > 0 ? next : undefined });
  }, [filters, onChange]);

  const toggleDocId = useCallback((docId: string) => {
    const current = filters.documentIds ?? [];
    const next = current.includes(docId)
      ? current.filter((id) => id !== docId)
      : [...current, docId];
    onChange({ ...filters, documentIds: next.length > 0 ? next : undefined });
  }, [filters, onChange]);

  const handlePageMin = useCallback((value: string) => {
    const num = value ? parseInt(value, 10) : undefined;
    onChange({ ...filters, pageMin: num && num > 0 ? num : undefined });
  }, [filters, onChange]);

  const handlePageMax = useCallback((value: string) => {
    const num = value ? parseInt(value, 10) : undefined;
    onChange({ ...filters, pageMax: num && num > 0 ? num : undefined });
  }, [filters, onChange]);

  // Group completed documents by type for display
  const completedDocs = useMemo(
    () => documents.filter((d) => d.status === 'completed'),
    [documents]
  );

  return (
    <div className="border-b border-border bg-muted/30">
      {/* Toggle bar */}
      <button
        type="button"
        className="flex w-full items-center gap-2 px-4 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <Filter className="h-3 w-3" />
        <span>Search Filters</span>
        {activeCount > 0 && (
          <Badge variant="secondary" className="h-4 min-w-[16px] px-1 text-[10px]">
            {activeCount}
          </Badge>
        )}
        <span className="flex-1" />
        {activeCount > 0 && (
          <button
            type="button"
            className="flex items-center gap-1 text-[10px] hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              handleClearAll();
            }}
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}
        {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {/* Expanded filter panel */}
      {isExpanded && (
        <div className="space-y-3 px-4 pb-3">
          {/* Document type filter */}
          <div>
            <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">Document Type</p>
            <div className="flex flex-wrap gap-2">
              {DOCUMENT_TYPE_OPTIONS.map(({ value, label }) => (
                <label
                  key={value}
                  className="flex cursor-pointer items-center gap-1.5 text-xs"
                >
                  <Checkbox
                    checked={filters.documentTypes?.includes(value) ?? false}
                    onCheckedChange={() => toggleDocType(value)}
                    className="h-3.5 w-3.5"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>

          {/* Page range filter */}
          <div>
            <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">Page Range</p>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                placeholder="From"
                value={filters.pageMin ?? ''}
                onChange={(e) => handlePageMin(e.target.value)}
                className="h-7 w-20 text-xs"
              />
              <span className="text-xs text-muted-foreground">to</span>
              <Input
                type="number"
                min={1}
                placeholder="To"
                value={filters.pageMax ?? ''}
                onChange={(e) => handlePageMax(e.target.value)}
                className="h-7 w-20 text-xs"
              />
            </div>
          </div>

          {/* Document selector (only show if there are documents) */}
          {completedDocs.length > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">
                Documents ({filters.documentIds?.length ?? 0}/{completedDocs.length} selected)
              </p>
              <div className="max-h-28 space-y-1 overflow-y-auto">
                {completedDocs.map((doc) => (
                  <label
                    key={doc.id}
                    className="flex cursor-pointer items-center gap-1.5 text-xs truncate"
                  >
                    <Checkbox
                      checked={filters.documentIds?.includes(doc.id) ?? false}
                      onCheckedChange={() => toggleDocId(doc.id)}
                      className="h-3.5 w-3.5 shrink-0"
                    />
                    <span className="truncate">{doc.filename}</span>
                    <span className="shrink-0 text-muted-foreground">
                      ({doc.pageCount ?? 0}p)
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
