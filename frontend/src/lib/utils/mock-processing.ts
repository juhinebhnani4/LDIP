/**
 * Mock Processing Simulation
 *
 * Simulates file upload progress and processing stages with live discoveries.
 * Used for MVP until backend API is ready.
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 *
 * TODO: Replace with real backend integration:
 * - POST /api/matters - Create matter and start upload
 * - GET /api/matters/{id}/processing/status - Get processing status
 * - GET /api/matters/{id}/discoveries - Get live discoveries (SSE stream)
 * - POST /api/matters/{id}/background - Move processing to background
 */

import type {
  ProcessingStage,
  UploadProgress,
  LiveDiscovery,
  DiscoveredEntity,
  DiscoveredDate,
  DiscoveredCitation,
  EarlyInsight,
} from '@/types/upload';

// =============================================================================
// Mock Data Constants
// =============================================================================

/** Mock entities to discover during processing */
export const MOCK_ENTITIES: DiscoveredEntity[] = [
  { name: 'Mehul Parekh', role: 'Petitioner' },
  { name: 'Nirav D. Jobalia', role: 'Respondent' },
  { name: 'Jitendra Kumar', role: 'Custodian' },
  { name: 'SEBI', role: 'Regulatory Authority' },
  { name: 'National Stock Exchange', role: 'Respondent' },
  { name: 'Securities Appellate Tribunal', role: 'Adjudicating Authority' },
  { name: 'Reserve Bank of India', role: 'Regulatory Authority' },
  { name: 'Ministry of Finance', role: 'Stakeholder' },
];

/** Mock date range extracted from documents */
export const MOCK_DATES: DiscoveredDate = {
  earliest: new Date('2016-05-12'),
  latest: new Date('2024-01-15'),
  count: 47,
};

/** Mock citations detected in documents */
export const MOCK_CITATIONS: DiscoveredCitation[] = [
  { actName: 'Securities Act 1992', count: 18 },
  { actName: 'SARFAESI Act 2002', count: 4 },
  { actName: 'Companies Act 2013', count: 1 },
];

/** Mock early insights discovered during processing */
export const MOCK_INSIGHTS: EarlyInsight[] = [
  {
    message: 'This case spans 7+ years with 4 major procedural stages',
    type: 'info',
    icon: 'lightbulb',
  },
  {
    message: 'Found potential date discrepancy in notice timeline',
    type: 'warning',
    icon: 'alert-triangle',
  },
];

// =============================================================================
// Processing Stages Configuration
// =============================================================================

/** Processing stages with their duration ranges (in ms) */
const STAGE_DURATIONS: Record<ProcessingStage, { min: number; max: number }> = {
  UPLOADING: { min: 500, max: 1500 },
  OCR: { min: 2000, max: 4000 },
  ENTITY_EXTRACTION: { min: 1500, max: 3000 },
  ANALYSIS: { min: 2000, max: 4000 },
  INDEXING: { min: 1000, max: 2000 },
};

/** All stages in order */
const STAGES_IN_ORDER: ProcessingStage[] = [
  'UPLOADING',
  'OCR',
  'ENTITY_EXTRACTION',
  'ANALYSIS',
  'INDEXING',
];

// =============================================================================
// Simulation Callbacks Interface
// =============================================================================

export interface SimulationCallbacks {
  /** Called when individual file upload progress changes */
  onUploadProgress: (fileName: string, progress: UploadProgress) => void;
  /** Called when processing stage changes */
  onProcessingStage: (stage: ProcessingStage | null) => void;
  /** Called when overall progress changes */
  onOverallProgress: (progressPct: number) => void;
  /** Called when a new discovery is made */
  onDiscovery: (discovery: LiveDiscovery) => void;
  /** Called when processing is complete */
  onComplete: () => void;
}

// =============================================================================
// Helper Functions
// =============================================================================

/** Get random number between min and max */
function randomBetween(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/** Generate unique ID */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/** Sleep for specified milliseconds */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// =============================================================================
// Simulation Functions
// =============================================================================

/**
 * Simulate file upload progress for a single file
 * Calls onProgress at regular intervals until complete
 */
async function simulateFileUpload(
  file: File,
  onProgress: (progress: UploadProgress) => void,
  signal: AbortSignal
): Promise<boolean> {
  const fileName = file.name;
  const fileSize = file.size;
  const duration = randomBetween(500, 2000);
  const steps = 10;
  const stepDuration = duration / steps;

  // Initial pending state
  onProgress({
    fileName,
    fileSize,
    progressPct: 0,
    status: 'pending',
  });

  // Start uploading
  onProgress({
    fileName,
    fileSize,
    progressPct: 0,
    status: 'uploading',
  });

  // Progress through upload
  for (let i = 1; i <= steps; i++) {
    if (signal.aborted) return false;
    await sleep(stepDuration);

    const progressPct = (i / steps) * 100;
    onProgress({
      fileName,
      fileSize,
      progressPct,
      status: i === steps ? 'complete' : 'uploading',
    });
  }

  return true;
}

/**
 * Simulate processing through all stages with live discoveries
 */
async function simulateProcessing(
  callbacks: SimulationCallbacks,
  signal: AbortSignal
): Promise<void> {
  const { onProcessingStage, onOverallProgress, onDiscovery, onComplete } =
    callbacks;

  // Each stage contributes to overall progress
  const progressPerStage = 100 / STAGES_IN_ORDER.length;
  let overallProgress = 0;

  for (let i = 0; i < STAGES_IN_ORDER.length; i++) {
    if (signal.aborted) return;

    const stage = STAGES_IN_ORDER[i]!;
    const stageDuration = STAGE_DURATIONS[stage];
    const duration = randomBetween(stageDuration.min, stageDuration.max);

    onProcessingStage(stage);

    // Progress through stage
    const stageSteps = 5;
    const stepDuration = duration / stageSteps;

    for (let step = 1; step <= stageSteps; step++) {
      if (signal.aborted) return;
      await sleep(stepDuration);

      const stageProgress = (step / stageSteps) * progressPerStage;
      overallProgress = i * progressPerStage + stageProgress;
      onOverallProgress(Math.min(overallProgress, 100));

      // Generate discoveries at specific points
      await generateDiscoveries(stage, step, onDiscovery, signal);
    }
  }

  // Complete
  onOverallProgress(100);
  onComplete();
}

/**
 * Generate mock discoveries based on current stage and step
 */
async function generateDiscoveries(
  stage: ProcessingStage,
  step: number,
  onDiscovery: (discovery: LiveDiscovery) => void,
  signal: AbortSignal
): Promise<void> {
  if (signal.aborted) return;

  // Entities discovered during entity extraction stage
  if (stage === 'ENTITY_EXTRACTION' && step === 3) {
    onDiscovery({
      id: generateId(),
      type: 'entity',
      count: MOCK_ENTITIES.length,
      details: MOCK_ENTITIES,
      timestamp: new Date(),
    });
  }

  // Dates discovered during OCR stage
  if (stage === 'OCR' && step === 4) {
    onDiscovery({
      id: generateId(),
      type: 'date',
      count: MOCK_DATES.count,
      details: MOCK_DATES,
      timestamp: new Date(),
    });
  }

  // Citations discovered during analysis stage
  if (stage === 'ANALYSIS' && step === 2) {
    const totalCitations = MOCK_CITATIONS.reduce((sum, c) => sum + c.count, 0);
    onDiscovery({
      id: generateId(),
      type: 'citation',
      count: totalCitations,
      details: MOCK_CITATIONS,
      timestamp: new Date(),
    });
  }

  // Insights discovered during analysis stage
  if (stage === 'ANALYSIS' && step === 4) {
    for (const insight of MOCK_INSIGHTS) {
      if (signal.aborted) return;
      onDiscovery({
        id: generateId(),
        type: 'insight',
        count: 1,
        details: insight,
        timestamp: new Date(),
      });
      await sleep(300); // Small delay between insights
    }
  }
}

// =============================================================================
// Main Simulation Function
// =============================================================================

/**
 * Simulate the complete upload and processing flow
 *
 * @param files - Files to "upload"
 * @param callbacks - Callbacks for progress updates
 * @returns Cleanup function to abort simulation
 */
export function simulateUploadAndProcessing(
  files: File[],
  callbacks: SimulationCallbacks
): () => void {
  const abortController = new AbortController();
  const { signal } = abortController;

  // Start simulation
  void (async () => {
    try {
      // Phase 1: Upload all files
      callbacks.onProcessingStage('UPLOADING');
      callbacks.onOverallProgress(0);

      const uploadPromises = files.map((file) =>
        simulateFileUpload(
          file,
          (progress) => callbacks.onUploadProgress(file.name, progress),
          signal
        )
      );

      await Promise.all(uploadPromises);

      if (signal.aborted) return;

      // Phase 2: Processing stages
      await simulateProcessing(callbacks, signal);
    } catch {
      // Simulation cancelled or error
    }
  })();

  // Return cleanup function
  return () => {
    abortController.abort();
  };
}

/**
 * Simulate just the upload progress (without processing)
 * Useful for testing upload UI in isolation
 */
export function simulateUploadProgress(
  files: File[],
  onProgress: (fileName: string, progress: UploadProgress) => void
): () => void {
  const abortController = new AbortController();
  const { signal } = abortController;

  void (async () => {
    for (const file of files) {
      if (signal.aborted) break;
      await simulateFileUpload(
        file,
        (progress) => onProgress(file.name, progress),
        signal
      );
    }
  })();

  return () => {
    abortController.abort();
  };
}

/**
 * Simulate just the processing progress (without upload)
 * Useful for testing processing UI in isolation
 */
export function simulateProcessingProgress(
  callbacks: Omit<SimulationCallbacks, 'onUploadProgress'>
): () => void {
  const abortController = new AbortController();
  const { signal } = abortController;

  void simulateProcessing(
    { ...callbacks, onUploadProgress: () => {} },
    signal
  );

  return () => {
    abortController.abort();
  };
}
