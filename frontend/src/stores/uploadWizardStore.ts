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
} from '@/types/upload';

/** Initial state for the wizard */
const initialState = {
  currentStage: 'FILE_SELECTION' as UploadWizardStage,
  files: [] as File[],
  matterName: '',
  detectedActs: [] as DetectedAct[],
  isLoading: false,
  error: null,
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
    set(initialState);
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
