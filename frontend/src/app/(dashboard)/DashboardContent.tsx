'use client';

import { MatterCardsGrid, ViewToggle, MatterFilters } from '@/components/features/dashboard';

/**
 * Dashboard Content Component (Client)
 *
 * Handles the interactive parts of the dashboard:
 * - View toggle (grid/list)
 * - Filters (sort/filter dropdowns)
 * - Matter cards grid
 *
 * This is a client component because it uses Zustand store
 * and handles user interactions.
 */

export function DashboardContent() {
  return (
    <div className="space-y-4">
      {/* Controls row - filters and view toggle */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <MatterFilters />
        <ViewToggle />
      </div>

      {/* Matter cards grid */}
      <MatterCardsGrid />
    </div>
  );
}
