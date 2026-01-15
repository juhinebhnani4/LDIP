/**
 * Upload Wizard Store
 *
 * Zustand store for managing the upload wizard flow state.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const currentStage = useUploadWizardStore((state) => state.currentStage);
 *   const setStage = useUploadWizardStore((state) => state.setStage);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { currentStage, setStage } = useUploadWizardStore();
 */

import { create } from 'zustand';
import type {
  UploadWizardStore,
  UploadWizardStage,
  DetectedAct,
  ProcessingStage,
  LiveDiscovery,
  UploadProgress,
  LiveDiscoveryType,
} from '@/types/upload';
import {
  PROCESSING_STAGE_LABELS,
  PROCESSING_STAGE_NUMBERS,
} from '@/types/upload';

/** Initial state for the wizard */
const initialState = {
  currentStage: 'FILE_SELECTION' as UploadWizardStage,
  files: [] as File[],
  matterName: '',
  detectedActs: [] as DetectedAct[],
  isLoading: false,
  error: null as string | null,
  // Processing state (Story 9-5)
  uploadProgress: new Map<string, UploadProgress>(),
  processingStage: null as ProcessingStage | null,
  overallProgressPct: 0,
  liveDiscoveries: [] as LiveDiscovery[],
  matterId: null as string | null,
  failedUploads: new Map<string, string>(),
  // Completion state (Story 9-6)
  isProcessingComplete: false,
};

/**
 * Generate matter name from first file
 * Removes extension and replaces underscores/hyphens with spaces
 */
function generateMatterName(file: File): string {
  const nameWithoutExt = file.name.replace(/\.[^.]+$/, '');
  // Replace underscores and hyphens with spaces, then trim
  return nameWithoutExt.replace(/[_-]+/g, ' ').trim();
}

export const useUploadWizardStore = create<UploadWizardStore>()((set, get) => ({
  // Initial state
  ...initialState,

  // Actions
  setStage: (stage: UploadWizardStage) => {
    set({ currentStage: stage });
  },

  addFiles: (newFiles: File[]) => {
    const currentFiles = get().files;
    const currentMatterName = get().matterName;
    const allFiles = [...currentFiles, ...newFiles];

    // Auto-generate matter name from first file if not set
    const firstFile = allFiles[0];
    const matterName =
      currentMatterName || (firstFile ? generateMatterName(firstFile) : '');

    set({
      files: allFiles,
      matterName,
      // Transition to review stage when files are added
      currentStage: allFiles.length > 0 ? 'REVIEW' : 'FILE_SELECTION',
    });
  },

  removeFile: (index: number) => {
    const files = get().files;
    const newFiles = files.filter((_, i) => i !== index);
    const currentMatterName = get().matterName;

    // If removing first file and matter name matches generated name, update it
    let matterName = currentMatterName;
    const firstFile = files[0];
    const newFirstFile = newFiles[0];
    if (
      index === 0 &&
      firstFile &&
      currentMatterName === generateMatterName(firstFile)
    ) {
      // Generate new name from next file, or clear if no files left
      matterName = newFirstFile ? generateMatterName(newFirstFile) : '';
    }

    // Go back to file selection if no files remain
    const currentStage = newFiles.length === 0 ? 'FILE_SELECTION' : 'REVIEW';

    set({ files: newFiles, matterName, currentStage });
  },

  setMatterName: (name: string) => {
    set({ matterName: name });
  },

  setDetectedActs: (acts: DetectedAct[]) => {
    set({ detectedActs: acts });
  },

  startUpload: () => {
    set({ currentStage: 'UPLOADING', isLoading: true });
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  reset: () => {
    set({
      ...initialState,
      // Create new Map instances to avoid reference issues
      uploadProgress: new Map<string, UploadProgress>(),
      failedUploads: new Map<string, string>(),
    });
  },

  // Processing actions (Story 9-5)
  setUploadProgress: (fileName: string, progress: UploadProgress) => {
    const currentProgress = get().uploadProgress;
    const newProgress = new Map(currentProgress);
    newProgress.set(fileName, progress);
    set({ uploadProgress: newProgress });
  },

  setProcessingStage: (stage: ProcessingStage | null) => {
    set({ processingStage: stage });
  },

  addLiveDiscovery: (discovery: LiveDiscovery) => {
    const currentDiscoveries = get().liveDiscoveries;
    set({ liveDiscoveries: [...currentDiscoveries, discovery] });
  },

  setMatterId: (matterId: string | null) => {
    set({ matterId });
  },

  setOverallProgress: (progressPct: number) => {
    set({ overallProgressPct: progressPct });
  },

  setUploadFailed: (fileName: string, errorMessage: string) => {
    const currentFailed = get().failedUploads;
    const newFailed = new Map(currentFailed);
    newFailed.set(fileName, errorMessage);

    // Also update the upload progress to show error
    const currentProgress = get().uploadProgress;
    const newProgress = new Map(currentProgress);
    const existing = newProgress.get(fileName);
    if (existing) {
      newProgress.set(fileName, {
        ...existing,
        status: 'error',
        errorMessage,
      });
    }

    set({ failedUploads: newFailed, uploadProgress: newProgress });
  },

  clearProcessingState: () => {
    set({
      uploadProgress: new Map<string, UploadProgress>(),
      processingStage: null,
      overallProgressPct: 0,
      liveDiscoveries: [],
      matterId: null,
      failedUploads: new Map<string, string>(),
      isProcessingComplete: false,
    });
  },

  // Completion actions (Story 9-6)
  setProcessingComplete: (complete: boolean) => {
    set({ isProcessingComplete: complete });
  },
}));

/**
 * Selector for total file size
 */
export function selectTotalFileSize(state: UploadWizardStore): number {
  return state.files.reduce((total, file) => total + file.size, 0);
}

/**
 * Selector for file count
 */
export function selectFileCount(state: UploadWizardStore): number {
  return state.files.length;
}

/**
 * Selector for acts by status
 */
export function selectActsByStatus(
  state: UploadWizardStore,
  status: 'found' | 'missing'
): DetectedAct[] {
  return state.detectedActs.filter((act) => act.status === status);
}

/**
 * Check if matter name is valid
 */
export function selectIsMatterNameValid(state: UploadWizardStore): boolean {
  const name = state.matterName.trim();
  return name.length > 0 && name.length <= 100;
}

/**
 * Check if wizard can proceed to upload
 */
export function selectCanStartUpload(state: UploadWizardStore): boolean {
  return (
    state.files.length > 0 &&
    selectIsMatterNameValid(state) &&
    !state.isLoading
  );
}

// =============================================================================
// Processing Selectors (Story 9-5)
// =============================================================================

/**
 * Check if all files have been uploaded
 */
export function selectUploadComplete(state: UploadWizardStore): boolean {
  if (state.files.length === 0) return false;

  for (const file of state.files) {
    const progress = state.uploadProgress.get(file.name);
    if (!progress || progress.status !== 'complete') {
      return false;
    }
  }
  return true;
}

/**
 * Get discoveries filtered by type
 */
export function selectDiscoveriesByType(
  state: UploadWizardStore,
  type: LiveDiscoveryType
): LiveDiscovery[] {
  return state.liveDiscoveries.filter((d) => d.type === type);
}

/**
 * Get human-readable current stage name
 */
export function selectCurrentStageName(state: UploadWizardStore): string {
  if (!state.processingStage) return '';
  return PROCESSING_STAGE_LABELS[state.processingStage] ?? '';
}

/**
 * Get current stage number (1-5)
 */
export function selectCurrentStageNumber(state: UploadWizardStore): number {
  if (!state.processingStage) return 0;
  return PROCESSING_STAGE_NUMBERS[state.processingStage] ?? 0;
}

/**
 * Get count of completed file uploads
 */
export function selectCompletedUploadsCount(state: UploadWizardStore): number {
  let count = 0;
  state.uploadProgress.forEach((progress) => {
    if (progress.status === 'complete') count++;
  });
  return count;
}

/**
 * Get count of failed file uploads
 */
export function selectFailedUploadsCount(state: UploadWizardStore): number {
  return state.failedUploads.size;
}

/**
 * Check if any uploads have failed
 */
export function selectHasFailedUploads(state: UploadWizardStore): boolean {
  return state.failedUploads.size > 0;
}

/**
 * Get upload progress as array (for rendering file list)
 */
export function selectUploadProgressArray(
  state: UploadWizardStore
): UploadProgress[] {
  return Array.from(state.uploadProgress.values());
}

// =============================================================================
// Completion Selectors (Story 9-6)
// =============================================================================

/**
 * Check if processing is complete (INDEXING stage at 100%)
 * Used to trigger Stage 5 completion screen
 */
export function selectIsProcessingComplete(state: UploadWizardStore): boolean {
  return state.processingStage === 'INDEXING' && state.overallProgressPct >= 100;
}
