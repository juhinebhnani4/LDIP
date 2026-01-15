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

// Summary hooks (Story 10B.1)
export { useMatterSummary } from './useMatterSummary';
