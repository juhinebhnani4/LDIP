/**
 * Entity Constants
 *
 * Shared configuration and constants for entity-related components.
 *
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { User, Building2, Landmark, Package } from 'lucide-react';
import type { EntityType } from '@/types/entity';

/**
 * Configuration for entity type display (icons, colors, labels)
 */
export const entityTypeConfig: Record<
  EntityType,
  { icon: typeof User; color: string; bgColor: string; label: string }
> = {
  PERSON: {
    icon: User,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950',
    label: 'Person',
  },
  ORG: {
    icon: Building2,
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950',
    label: 'Organization',
  },
  INSTITUTION: {
    icon: Landmark,
    color: 'text-purple-600 dark:text-purple-400',
    bgColor: 'bg-purple-50 dark:bg-purple-950',
    label: 'Institution',
  },
  ASSET: {
    icon: Package,
    color: 'text-amber-600 dark:text-amber-400',
    bgColor: 'bg-amber-50 dark:bg-amber-950',
    label: 'Asset',
  },
};

/**
 * Standard height for entity view containers (graph, list, grid)
 */
export const ENTITY_VIEW_HEIGHT = 'h-[600px]';

/**
 * Standard height value in pixels for entity view containers
 */
export const ENTITY_VIEW_HEIGHT_PX = 600;
