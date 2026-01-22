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

// Upload wizard store for multi-stage upload flow (Story 9-4, 9-5, 9-6)
export {
  useUploadWizardStore,
  selectTotalFileSize,
  selectFileCount,
  selectActsByStatus,
  selectIsMatterNameValid,
  selectCanStartUpload,
  selectUploadComplete,
  selectDiscoveriesByType,
  selectCurrentStageName,
  selectCurrentStageNumber,
  selectCompletedUploadsCount,
  selectFailedUploadsCount,
  selectHasFailedUploads,
  selectUploadProgressArray,
  selectIsProcessingComplete,
} from './uploadWizardStore';

// Background processing store for async matter processing (Story 9-6)
export {
  useBackgroundProcessingStore,
  selectProcessingMatters,
  selectCompletedMatters,
  selectBackgroundMatterCount,
  selectIsMatterInBackground,
  type BackgroundMatter,
} from './backgroundProcessingStore';

// Notification store for in-app notifications (Story 9-1)
export {
  useNotificationStore,
  selectUnreadNotifications,
  selectNotificationsByMatter,
  selectHighPriorityUnread,
} from './notificationStore';

// Workspace store for tab navigation state (Story 10A.2)
export {
  useWorkspaceStore,
  selectTotalIssueCount,
  selectIsAnyTabProcessing,
  selectTabsWithIssuesCount,
  type TabId,
  type TabStats,
  type TabProcessingStatus,
} from './workspaceStore';

// Q&A Panel store for panel position and sizing (Story 10A.3)
export {
  useQAPanelStore,
  selectIsPanelVisible,
  selectCurrentDimensions,
  QA_PANEL_POSITIONS,
  DEFAULT_PANEL_POSITION,
  DEFAULT_RIGHT_WIDTH,
  DEFAULT_BOTTOM_HEIGHT,
  MIN_PANEL_SIZE,
  MAX_PANEL_SIZE,
  DEFAULT_FLOAT_WIDTH,
  DEFAULT_FLOAT_HEIGHT,
  MIN_FLOAT_WIDTH,
  MIN_FLOAT_HEIGHT,
  type QAPanelPosition,
} from './qaPanelStore';

// PDF Split View store for source reference viewer (Story 11.5)
export {
  usePdfSplitViewStore,
  selectPdfSplitViewIsOpen,
  selectPdfDocumentUrl,
  selectPdfDocumentName,
  selectPdfCurrentPage,
  selectPdfTotalPages,
  selectPdfInitialPage,
  selectPdfScale,
  selectPdfBoundingBoxes,
  selectPdfMatterId,
  selectPdfDocumentId,
  selectPdfChunkId,
} from './pdfSplitViewStore';

// Inspector store for debug/inspector mode (RAG Production Gaps - Feature 3)
export {
  useInspectorStore,
  selectIsDebugActive,
} from './inspectorStore';

// Future stores (to be added in later stories):
// export { useMatterStore } from './matterStore';
// export { useSessionStore } from './sessionStore';
// export { useChatStore } from './chatStore';
