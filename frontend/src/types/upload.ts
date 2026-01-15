/**
 * Upload Wizard Types
 *
 * Types for the multi-stage upload wizard flow.
 * Stages: File Selection → Review & Name → Act Discovery → Uploading → Processing
 */

/** Upload wizard stages */
export type UploadWizardStage =
  | 'FILE_SELECTION'
  | 'REVIEW'
  | 'ACT_DISCOVERY'
  | 'UPLOADING'
  | 'PROCESSING';

// =============================================================================
// Processing Stage Types (Story 9-5)
// =============================================================================

/**
 * Processing stages during matter analysis
 * From UX-Decisions-Log.md Section 4.3
 */
export type ProcessingStage =
  | 'UPLOADING'
  | 'OCR'
  | 'ENTITY_EXTRACTION'
  | 'ANALYSIS'
  | 'INDEXING';

/** Human-readable labels for processing stages */
export const PROCESSING_STAGE_LABELS: Record<ProcessingStage, string> = {
  UPLOADING: 'Uploading files',
  OCR: 'OCR & text extraction',
  ENTITY_EXTRACTION: 'Extracting entities & relationships',
  ANALYSIS: 'Running analysis engines',
  INDEXING: 'Final indexing',
};

/** Stage numbers for display (1-5) */
export const PROCESSING_STAGE_NUMBERS: Record<ProcessingStage, number> = {
  UPLOADING: 1,
  OCR: 2,
  ENTITY_EXTRACTION: 3,
  ANALYSIS: 4,
  INDEXING: 5,
};

/**
 * Live discovery type categories
 */
export type LiveDiscoveryType =
  | 'entity'
  | 'date'
  | 'citation'
  | 'insight';

/**
 * Live discovery during processing
 * Updates shown in real-time as processing progresses
 */
export interface LiveDiscovery {
  /** Unique identifier */
  id: string;
  /** Type of discovery */
  type: LiveDiscoveryType;
  /** Count of items discovered */
  count: number;
  /** Additional details (varies by type) */
  details: DiscoveredEntity[] | DiscoveredDate | DiscoveredCitation[] | EarlyInsight;
  /** When this discovery was made */
  timestamp: Date;
}

/**
 * Individual file upload progress
 */
export interface UploadProgress {
  /** File name */
  fileName: string;
  /** File size in bytes */
  fileSize: number;
  /** Upload progress percentage (0-100) */
  progressPct: number;
  /** Upload status */
  status: 'pending' | 'uploading' | 'complete' | 'error';
  /** Error message if failed */
  errorMessage?: string;
}

/**
 * Overall processing progress
 */
export interface ProcessingProgress {
  /** Current processing stage */
  currentStage: ProcessingStage;
  /** Overall progress percentage (0-100) */
  overallProgressPct: number;
  /** Number of files received */
  filesReceived: number;
  /** Total pages extracted */
  pagesExtracted: number;
  /** OCR progress percentage */
  ocrProgressPct: number;
  /** Documents processed so far */
  documentsProcessed: number;
  /** Total documents to process */
  totalDocuments: number;
}

// =============================================================================
// Discovery Detail Types (Story 9-5)
// =============================================================================

/**
 * Discovered entity during processing
 */
export interface DiscoveredEntity {
  /** Entity name */
  name: string;
  /** Role in the case (e.g., "Petitioner", "Respondent") */
  role: string;
}

/**
 * Discovered date range during processing
 */
export interface DiscoveredDate {
  /** Earliest date found */
  earliest: Date;
  /** Latest date found */
  latest: Date;
  /** Total count of dates extracted */
  count: number;
}

/**
 * Discovered citation during processing
 */
export interface DiscoveredCitation {
  /** Act name */
  actName: string;
  /** Number of citations to this act */
  count: number;
}

/**
 * Early insight discovered during processing
 */
export interface EarlyInsight {
  /** Insight message */
  message: string;
  /** Type of insight */
  type: 'info' | 'warning';
  /** Icon to display (lucide-react icon name) */
  icon: 'lightbulb' | 'alert-triangle';
}

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

  // Processing state (Story 9-5)
  /** Individual file upload progress */
  uploadProgress: Map<string, UploadProgress>;
  /** Current processing stage */
  processingStage: ProcessingStage | null;
  /** Overall progress percentage (0-100) */
  overallProgressPct: number;
  /** Live discoveries found during processing */
  liveDiscoveries: LiveDiscovery[];
  /** Created matter ID (set after matter creation) */
  matterId: string | null;
  /** Failed file uploads */
  failedUploads: Map<string, string>;

  // Completion state (Story 9-6)
  /** Whether processing has completed (Stage 5) */
  isProcessingComplete: boolean;
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

  // Processing actions (Story 9-5)
  /** Update upload progress for a specific file */
  setUploadProgress: (fileName: string, progress: UploadProgress) => void;
  /** Set the current processing stage */
  setProcessingStage: (stage: ProcessingStage | null) => void;
  /** Add a live discovery */
  addLiveDiscovery: (discovery: LiveDiscovery) => void;
  /** Set the created matter ID */
  setMatterId: (matterId: string | null) => void;
  /** Set overall progress percentage */
  setOverallProgress: (progressPct: number) => void;
  /** Mark a file upload as failed */
  setUploadFailed: (fileName: string, errorMessage: string) => void;
  /** Clear all processing state (for reset) */
  clearProcessingState: () => void;

  // Completion actions (Story 9-6)
  /** Set processing complete state */
  setProcessingComplete: (complete: boolean) => void;
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
