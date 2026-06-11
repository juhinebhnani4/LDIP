'use client';

import * as React from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useIsBelowBreakpoint } from '@/hooks';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';

/**
 * ResponsiveTable — the single source of truth for "show a data table on desktop,
 * a stacked card list on phone/tablet" (FE-ARCH-02).
 *
 * Why this exists: three matter tabs (verification, citations, documents) each had
 * a wide table that only scrolled sideways on small screens. The first fix
 * reinvented the table->cards conversion three different ways, with the
 * status/badge logic copied between the table cell and the card field — exactly
 * the duplicate-logic shape the project forbids. This primitive removes it:
 *
 *  - Each column's `cell(row)` is defined ONCE and rendered by BOTH the table and
 *    the card. No table-vs-card duplication is possible.
 *  - It renders ONE DOM tree (conditional on `useIsBelowBreakpoint('lg')`), so there
 *    is no duplicate content in the DOM (which broke getByText-based tests) and no
 *    flash-of-wrong-layout for data that arrives after mount.
 *
 * Feature-specific behaviour (sorting controls, selection, grouping, expansion,
 * keyboard nav) stays with the caller — the caller supplies `columns`, `rows`,
 * `sort`, `selection`, `onRowClick`, and per-row classes. This is a responsive
 * shell, deliberately NOT a full datagrid.
 */

export type SortDirection = 'asc' | 'desc';

export interface ResponsiveColumn<T> {
  id: string;
  header: React.ReactNode;
  /** Single source of truth for the cell — rendered by BOTH the table cell and the card field. */
  cell: (row: T) => React.ReactNode;
  /** Label shown beside the value in card (narrow) mode. Defaults to `header`; pass null/'' to hide. */
  cardLabel?: React.ReactNode;
  /** Render as the card's title row (full width, no label) instead of a labelled field. */
  isPrimary?: boolean;
  /** Omit this column from the card entirely (e.g. a redundant icon column). */
  hideOnCard?: boolean;
  /** In the card, render full-width with the value BELOW the label (good for long text / action rows). */
  cardBlock?: boolean;
  align?: 'left' | 'right' | 'center';
  headerClassName?: string;
  cellClassName?: string;
  /** When true (and `sort` is provided) the table header becomes a sort toggle. */
  sortable?: boolean;
}

export interface ResponsiveTableSelection<T> {
  isSelected: (row: T) => boolean;
  onToggle: (row: T) => void;
  ariaLabel?: (row: T) => string;
  /** Per-row disabled (e.g. a row that's mid-processing) — applies in BOTH table and card mode. */
  isDisabled?: (row: T) => boolean;
  /** Optional "select all" — renders a header checkbox (table header AND a mobile-card header) when set. */
  allSelected?: boolean;
  someSelected?: boolean;
  onToggleAll?: (checked: boolean) => void;
}

export interface ResponsiveTableSort {
  columnId: string;
  direction: SortDirection;
  onSortChange: (columnId: string) => void;
}

export interface ResponsiveTableProps<T> {
  columns: ResponsiveColumn<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  /** Optional stable per-row test/e2e hook (applied to the <tr> and the card <li>). */
  getRowTestId?: (row: T) => string;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string | undefined;
  selection?: ResponsiveTableSelection<T>;
  sort?: ResponsiveTableSort;
  /** Rendered (in either mode) when `rows` is empty. */
  emptyState?: React.ReactNode;
  /** Force card layout regardless of viewport (tests / nested narrow contexts). */
  forceCards?: boolean;
  className?: string;
  'data-testid'?: string;
}

const alignClass: Record<NonNullable<ResponsiveColumn<unknown>['align']>, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
};

export function ResponsiveTable<T,>({
  columns,
  rows,
  getRowId,
  getRowTestId,
  onRowClick,
  rowClassName,
  selection,
  sort,
  emptyState,
  forceCards,
  className,
  ...rest
}: ResponsiveTableProps<T>) {
  const isBelowLg = useIsBelowBreakpoint('lg');
  const asCards = forceCards ?? isBelowLg;
  const testId = rest['data-testid'];

  if (rows.length === 0 && emptyState !== undefined) {
    return <div data-testid={testId}>{emptyState}</div>;
  }

  // ---- Narrow (phone / tablet portrait): stacked cards ----
  if (asCards) {
    const cardCols = columns.filter((c) => !c.hideOnCard);
    const primaryCols = cardCols.filter((c) => c.isPrimary);
    const fieldCols = cardCols.filter((c) => !c.isPrimary);
    return (
      <div className={className} data-testid={testId}>
        {selection?.onToggleAll && (
          <label className="mb-2 flex items-center gap-2 px-1 text-sm text-muted-foreground">
            <Checkbox
              checked={
                selection.allSelected
                  ? true
                  : selection.someSelected
                    ? 'indeterminate'
                    : false
              }
              onCheckedChange={(c) => selection.onToggleAll!(c === true)}
              aria-label="Select all"
            />
            Select all
          </label>
        )}
        <ul className="space-y-3">
        {rows.map((row) => {
          const clickable = Boolean(onRowClick);
          return (
            <li key={getRowId(row)} data-testid={getRowTestId?.(row)}>
              <Card
                className={cn(
                  'space-y-2 p-3',
                  clickable && 'cursor-pointer hover:bg-accent/40',
                  rowClassName?.(row)
                )}
                onClick={clickable ? () => onRowClick!(row) : undefined}
              >
                <div className="flex items-start gap-2">
                  {selection && (
                    <span className="pt-0.5" onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selection.isSelected(row)}
                        onCheckedChange={() => selection.onToggle(row)}
                        aria-label={selection.ariaLabel?.(row) ?? 'Select row'}
                        disabled={selection.isDisabled?.(row)}
                      />
                    </span>
                  )}
                  {primaryCols.length > 0 && (
                    <div className="min-w-0 flex-1 space-y-1">
                      {primaryCols.map((c) => (
                        <div key={c.id} className="min-w-0 break-words font-medium">
                          {c.cell(row)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {fieldCols.map((c) => {
                  const label = c.cardLabel !== undefined ? c.cardLabel : c.header;
                  const hasLabel = label != null && label !== '';
                  if (c.cardBlock) {
                    return (
                      <div key={c.id} className="min-w-0 space-y-1">
                        {hasLabel && <span className="text-xs text-muted-foreground">{label}</span>}
                        <div className="min-w-0 break-words text-sm">{c.cell(row)}</div>
                      </div>
                    );
                  }
                  return (
                    <div key={c.id} className="flex items-start justify-between gap-3 text-sm">
                      {hasLabel && <span className="shrink-0 text-muted-foreground">{label}</span>}
                      <span className="min-w-0 break-words text-right">{c.cell(row)}</span>
                    </div>
                  );
                })}
              </Card>
            </li>
          );
        })}
        </ul>
      </div>
    );
  }

  // ---- Desktop: real table (same column.cell, no duplicated logic) ----
  // Wrapped in `no-scrollbar` so a table wider than its container scrolls
  // WITHOUT the ugly trough that ui/table.tsx's own overflow wrapper shows
  // (the utility cascades to descendants — see globals.css).
  return (
    <div className={cn('no-scrollbar', className)} data-testid={testId}>
      <Table>
      <TableHeader>
        <TableRow>
          {selection && (
            <TableHead className="w-12">
              {selection.onToggleAll && (
                <Checkbox
                  checked={
                    selection.allSelected
                      ? true
                      : selection.someSelected
                        ? 'indeterminate'
                        : false
                  }
                  onCheckedChange={(c) => selection.onToggleAll!(c === true)}
                  aria-label="Select all"
                />
              )}
            </TableHead>
          )}
          {columns.map((c) => {
            const isSorted = c.sortable && sort && sort.columnId === c.id;
            const ariaSort = c.sortable && sort
              ? isSorted
                ? sort.direction === 'asc'
                  ? 'ascending'
                  : 'descending'
                : 'none'
              : undefined;
            return (
              <TableHead
                key={c.id}
                aria-sort={ariaSort}
                className={cn(c.align && alignClass[c.align], c.headerClassName)}
              >
                {c.sortable && sort ? (
                  <button
                    type="button"
                    onClick={() => sort.onSortChange(c.id)}
                    className="inline-flex items-center gap-1 hover:text-foreground"
                  >
                    {c.header}
                    {isSorted ? (
                      sort.direction === 'asc' ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )
                    ) : (
                      <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
                    )}
                  </button>
                ) : (
                  c.header
                )}
              </TableHead>
            );
          })}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const clickable = Boolean(onRowClick);
          return (
            <TableRow
              key={getRowId(row)}
              data-testid={getRowTestId?.(row)}
              className={cn(clickable && 'cursor-pointer', rowClassName?.(row))}
              onClick={clickable ? () => onRowClick!(row) : undefined}
            >
              {selection && (
                <TableCell className="w-12" onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selection.isSelected(row)}
                    onCheckedChange={() => selection.onToggle(row)}
                    aria-label={selection.ariaLabel?.(row) ?? 'Select row'}
                    disabled={selection.isDisabled?.(row)}
                  />
                </TableCell>
              )}
              {columns.map((c) => (
                <TableCell key={c.id} className={cn(c.align && alignClass[c.align], c.cellClassName)}>
                  {c.cell(row)}
                </TableCell>
              ))}
            </TableRow>
          );
        })}
      </TableBody>
      </Table>
    </div>
  );
}
