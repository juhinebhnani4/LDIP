/**
 * Timeline Components
 *
 * Components for the Timeline tab displaying chronological events.
 *
 * Story 10B.3: Timeline Tab Vertical List View
 * Story 10B.4: Timeline Tab Alternative Views
 */

// Main content component
export { TimelineContent, TimelineContentSkeleton } from './TimelineContent';

// Header component
export { TimelineHeader, TimelineHeaderSkeleton } from './TimelineHeader';

// Event card component (for list view)
export { TimelineEventCard, TimelineEventCardSkeleton } from './TimelineEventCard';

// Connector component (for list view)
export {
  TimelineConnector,
  formatDuration,
  isSignificantGap,
  isLargeGap,
} from './TimelineConnector';

// List view component
export { TimelineList, TimelineListSkeleton } from './TimelineList';

// Horizontal view component (Story 10B.4)
export { TimelineHorizontal } from './TimelineHorizontal';

// Multi-track view component (Story 10B.4)
export { TimelineMultiTrack } from './TimelineMultiTrack';

// Event detail component (for horizontal/multitrack views - Story 10B.4)
export { TimelineEventDetail } from './TimelineEventDetail';

// Zoom slider component (Story 10B.4)
export { TimelineZoomSlider } from './TimelineZoomSlider';

// Timeline utilities (Story 10B.4)
export {
  calculateTimelineScale,
  calculateDatePosition,
  clusterEvents,
  groupEventsByActor,
  calculateGaps,
  formatTimeAxisLabel,
  getNextZoomLevel,
  getPreviousZoomLevel,
  formatGapDuration,
  SIGNIFICANT_GAP_DAYS,
  CLUSTER_THRESHOLDS,
  SCALE_MULTIPLIERS,
  BASE_WIDTH_PER_YEAR,
} from './timelineUtils';

// Event type utilities
export {
  EVENT_TYPE_ICONS,
  EVENT_TYPE_LABELS,
  EVENT_TYPE_COLORS,
  getEventTypeIcon,
  getEventTypeLabel,
  getEventTypeColor,
} from './eventTypeIcons';
