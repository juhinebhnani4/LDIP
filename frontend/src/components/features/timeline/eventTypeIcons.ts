/**
 * Event Type Icon Mapping
 *
 * Maps timeline event types to icons, labels, and colors.
 * Based on UX-Decisions-Log.md Section 7.3.
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */

import {
  FileText,
  Gavel,
  Mail,
  Calendar,
  CreditCard,
  File,
  Clock,
  HelpCircle,
  type LucideIcon,
} from 'lucide-react';
import type { TimelineEventType } from '@/types/timeline';

/**
 * Icon mapping for each event type
 */
export const EVENT_TYPE_ICONS: Record<TimelineEventType, LucideIcon> = {
  filing: FileText,
  order: Gavel,
  notice: Mail,
  hearing: Calendar,
  transaction: CreditCard,
  document: File,
  deadline: Clock,
  unclassified: HelpCircle,
  raw_date: HelpCircle,
};

/**
 * Human-readable labels for event types
 */
export const EVENT_TYPE_LABELS: Record<TimelineEventType, string> = {
  filing: 'Filing',
  order: 'Order',
  notice: 'Notice',
  hearing: 'Hearing',
  transaction: 'Transaction',
  document: 'Document',
  deadline: 'Deadline',
  unclassified: 'Unclassified',
  raw_date: 'Date',
};

/**
 * Tailwind color classes for event type badges
 */
export const EVENT_TYPE_COLORS: Record<TimelineEventType, string> = {
  filing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  order: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  notice: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  hearing: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  transaction: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300',
  document: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300',
  deadline: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  unclassified: 'bg-slate-100 text-slate-600 dark:bg-slate-900/30 dark:text-slate-400',
  raw_date: 'bg-slate-100 text-slate-600 dark:bg-slate-900/30 dark:text-slate-400',
};

/**
 * Get icon component for event type
 */
export function getEventTypeIcon(eventType: TimelineEventType): LucideIcon {
  return EVENT_TYPE_ICONS[eventType] ?? EVENT_TYPE_ICONS.unclassified;
}

/**
 * Get label for event type
 */
export function getEventTypeLabel(eventType: TimelineEventType): string {
  return EVENT_TYPE_LABELS[eventType] ?? EVENT_TYPE_LABELS.unclassified;
}

/**
 * Get color class for event type
 */
export function getEventTypeColor(eventType: TimelineEventType): string {
  return EVENT_TYPE_COLORS[eventType] ?? EVENT_TYPE_COLORS.unclassified;
}
