/**
 * Custom Hooks
 *
 * Naming conventions (from project-context.md):
 * - Hooks: camelCase with `use` prefix (e.g., useMatter, useDocuments)
 */

// Auth hooks
export { useSession, useUser, useAuthActions, useAuth } from './useAuth';

// Split view hooks (Story 3-4)
export { useSplitView } from './useSplitView';

// Act discovery hooks (Story 3-2)
export { useActDiscovery } from './useActDiscovery';

// Verification hooks (Story 8-5)
export { useVerificationQueue } from './useVerificationQueue';
export { useVerificationStats } from './useVerificationStats';
export { useVerificationActions } from './useVerificationActions';

// Summary hooks (Story 10B.1, Story 10B.2, Story 14.6)
export { useMatterSummary } from './useMatterSummary';
export { useSummaryVerification } from './useSummaryVerification';
export { useSummaryEdit } from './useSummaryEdit';

// Timeline hooks (Story 10B.3)
export { useTimeline } from './useTimeline';
export { useTimelineStats } from './useTimelineStats';

// Citation hooks (Story 10C.3)
export {
  useCitationsList,
  useCitationStats,
  useCitationSummaryByAct,
  useActDiscoveryReport,
  useActMutations,
  getActNamesFromSummary,
} from './useCitations';

// Bounding box hooks (Story 11.7)
export { useBoundingBoxes } from './useBoundingBoxes';
