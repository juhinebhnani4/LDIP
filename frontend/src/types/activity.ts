/**
 * Activity Types
 *
 * Types for activity feed and dashboard statistics.
 * Matches future backend API models for dashboard activities.
 */

/**
 * Activity type enum for activity feed items.
 * Determines icon and color coding.
 */
export type ActivityType =
  | 'processing_complete'
  | 'verification_needed'
  | 'processing_started'
  | 'matter_opened'
  | 'contradictions_found'
  | 'processing_failed';

/**
 * Activity item for activity feed.
 * Represents a single activity entry.
 */
export interface Activity {
  /** Unique identifier for the activity */
  id: string;
  /** ID of the related matter (null if not matter-specific) */
  matterId: string | null;
  /** Display name of the related matter */
  matterName: string | null;
  /** Type of activity - determines icon and color */
  type: ActivityType;
  /** Human-readable description of the activity */
  description: string;
  /** ISO timestamp of when the activity occurred */
  timestamp: string;
  /** Whether the activity has been viewed/acknowledged */
  isRead: boolean;
}

/**
 * Dashboard statistics for quick stats panel.
 */
export interface DashboardStats {
  /** Count of active (non-archived) matters */
  activeMatters: number;
  /** Count of verified findings across all matters */
  verifiedFindings: number;
  /** Count of findings pending review */
  pendingReviews: number;
}

/**
 * Icon configuration for activity types.
 * Maps activity type to icon name and color class.
 */
export interface ActivityIconConfig {
  /** Icon component name from lucide-react */
  icon: 'CheckCircle2' | 'Info' | 'Clock' | 'AlertTriangle' | 'XCircle';
  /** Tailwind CSS color class for the icon */
  colorClass: string;
  /** Label for accessibility */
  label: string;
}

/**
 * Activity icon configuration map.
 * Used to render correct icon and color for each activity type.
 */
export const ACTIVITY_ICONS: Record<ActivityType, ActivityIconConfig> = {
  processing_complete: {
    icon: 'CheckCircle2',
    colorClass: 'text-green-500',
    label: 'Success',
  },
  verification_needed: {
    icon: 'AlertTriangle',
    colorClass: 'text-orange-500',
    label: 'Attention needed',
  },
  processing_started: {
    icon: 'Clock',
    colorClass: 'text-yellow-500',
    label: 'In progress',
  },
  matter_opened: {
    icon: 'Info',
    colorClass: 'text-blue-500',
    label: 'Information',
  },
  contradictions_found: {
    icon: 'AlertTriangle',
    colorClass: 'text-orange-500',
    label: 'Attention needed',
  },
  processing_failed: {
    icon: 'XCircle',
    colorClass: 'text-red-500',
    label: 'Error',
  },
} as const;

/**
 * Get activity icon configuration for a given activity type.
 */
export function getActivityIconConfig(type: ActivityType): ActivityIconConfig {
  return ACTIVITY_ICONS[type];
}
