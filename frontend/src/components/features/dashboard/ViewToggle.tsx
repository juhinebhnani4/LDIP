'use client';

import { LayoutGrid, List } from 'lucide-react';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { useMatterStore } from '@/stores/matterStore';
import type { MatterViewMode } from '@/types/matter';

/**
 * View Toggle Component
 *
 * Toggles between grid and list view for matter cards.
 * Persists preference to localStorage via matterStore.
 *
 * Uses ToggleGroup from shadcn/ui for accessible toggle buttons.
 */

interface ViewToggleProps {
  /** Optional className for styling */
  className?: string;
}

export function ViewToggle({ className }: ViewToggleProps) {
  const viewMode = useMatterStore((state) => state.viewMode);
  const setViewMode = useMatterStore((state) => state.setViewMode);

  const handleValueChange = (value: string) => {
    // ToggleGroup returns empty string when deselecting, ignore that
    if (value) {
      setViewMode(value as MatterViewMode);
    }
  };

  return (
    <ToggleGroup
      type="single"
      value={viewMode}
      onValueChange={handleValueChange}
      className={className}
      aria-label="View mode"
    >
      <ToggleGroupItem
        value="grid"
        aria-label="Grid view"
        title="Grid view"
      >
        <LayoutGrid className="size-4" />
      </ToggleGroupItem>
      <ToggleGroupItem
        value="list"
        aria-label="List view"
        title="List view"
      >
        <List className="size-4" />
      </ToggleGroupItem>
    </ToggleGroup>
  );
}
