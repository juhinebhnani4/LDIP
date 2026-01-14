/**
 * Zustand Store Exports
 *
 * Store usage pattern (from project-context.md):
 *
 * CORRECT - Selector pattern:
 * const currentMatter = useMatterStore((state) => state.currentMatter);
 * const setCurrentMatter = useMatterStore((state) => state.setCurrentMatter);
 *
 * WRONG - Full store subscription (causes unnecessary re-renders):
 * const { currentMatter, setCurrentMatter } = useMatterStore();
 */

// Upload store for document upload management
export { useUploadStore } from './uploadStore';

// Processing store for background job tracking (Story 2c-3)
export {
  useProcessingStore,
  selectJobsArray,
  selectActiveJobCount,
  selectFailedJobCount,
  selectIsProcessing,
} from './processingStore';

// Split view store for citation highlighting (Story 3-4)
export {
  useSplitViewStore,
  selectIsOpen,
  selectIsFullScreen,
  selectCurrentCitationId,
  selectSplitViewData,
  selectIsLoading,
  selectError,
  selectSourceViewState,
  selectTargetViewState,
  selectCanNavigatePrev,
  selectCanNavigateNext,
  selectNavigationInfo,
} from './splitViewStore';

// Verification store for finding verification queue (Story 8-5)
export {
  useVerificationStore,
  selectQueue,
  selectStats,
  selectFilters,
  selectSelectedIds,
  selectIsLoading as selectVerificationIsLoading,
  selectIsLoadingStats,
  selectError as selectVerificationError,
  selectMatterId as selectVerificationMatterId,
  selectSelectedCount,
  selectHasSelection,
  selectAllSelected,
  selectFilteredQueue,
  selectCompletionPercent,
  selectFindingTypes,
  getConfidenceTier,
  getConfidenceColorClass,
  getConfidenceLabel,
  formatFindingType,
  getFindingTypeIcon,
} from './verificationStore';

// Future stores (to be added in later stories):
// export { useMatterStore } from './matterStore';
// export { useSessionStore } from './sessionStore';
// export { useChatStore } from './chatStore';
