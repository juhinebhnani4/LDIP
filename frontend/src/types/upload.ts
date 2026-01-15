/**
 * Upload Wizard Types
 *
 * Types for the multi-stage upload wizard flow.
 * Stages: File Selection → Review & Name → Act Discovery → (hand off to uploading)
 */

/** Upload wizard stages */
export type UploadWizardStage =
  | 'FILE_SELECTION'
  | 'REVIEW'
  | 'ACT_DISCOVERY'
  | 'UPLOADING';

/** Status of a detected Act reference */
export type ActStatus = 'found' | 'missing';

/**
 * Detected Act from citation extraction
 * For MVP: Uses mock data until backend citation extraction is available
 */
export interface DetectedAct {
  /** Unique identifier for the act */
  id: string;
  /** Display name (e.g., "SARFAESI Act, 2002") */
  actName: string;
  /** Number of times this Act is cited in the uploaded documents */
  citationCount: number;
  /** Whether the Act was found in uploaded files or is missing */
  status: ActStatus;
  /** If found, which uploaded file contains this Act */
  sourceFile?: string;
}

/**
 * Upload wizard state interface
 * Used by uploadWizardStore
 */
export interface UploadWizardState {
  /** Current stage of the wizard */
  currentStage: UploadWizardStage;
  /** Files selected/validated for upload */
  files: File[];
  /** Auto-generated or user-edited matter name */
  matterName: string;
  /** Acts detected during citation scan (mock for MVP) */
  detectedActs: DetectedAct[];
  /** Whether an operation is in progress */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
}

/**
 * Upload wizard actions interface
 * Used by uploadWizardStore
 */
export interface UploadWizardActions {
  /** Set the current wizard stage */
  setStage: (stage: UploadWizardStage) => void;
  /** Add validated files to the wizard */
  addFiles: (files: File[]) => void;
  /** Remove a file by index */
  removeFile: (index: number) => void;
  /** Update the matter name */
  setMatterName: (name: string) => void;
  /** Set detected Acts (from scan or mock) */
  setDetectedActs: (acts: DetectedAct[]) => void;
  /** Start the upload process (transitions to Stage 3/UPLOADING) */
  startUpload: () => void;
  /** Set loading state */
  setLoading: (loading: boolean) => void;
  /** Set error message */
  setError: (error: string | null) => void;
  /** Reset wizard to initial state */
  reset: () => void;
}

/** Combined store type */
export type UploadWizardStore = UploadWizardState & UploadWizardActions;

/**
 * Matter creation request (for future backend integration)
 */
export interface CreateMatterRequest {
  /** User-defined matter name */
  name: string;
  /** Files to upload to the matter */
  files: File[];
}

/**
 * Matter creation response (for future backend integration)
 */
export interface CreateMatterResponse {
  data: {
    /** Created matter ID */
    matterId: string;
    /** Final matter name */
    name: string;
    /** Number of files queued for upload */
    fileCount: number;
  };
}
