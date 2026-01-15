/**
 * Backend to UI Stage Mapping
 *
 * Maps backend job current_stage values to frontend ProcessingStage enum.
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 *
 * Backend stages come from ProcessingJob.current_stage field:
 * - upload, receiving → UPLOADING
 * - ocr, validation → OCR
 * - entity_extraction, alias_resolution → ENTITY_EXTRACTION
 * - chunking, embedding, date_extraction, event_classification → ANALYSIS
 * - indexing, completed → INDEXING
 */

import type { ProcessingStage } from '@/types/upload';

/**
 * Map of backend stage strings to UI ProcessingStage values.
 * Keys are lowercase backend stage names, values are UI stage constants.
 */
const BACKEND_TO_UI_STAGE_MAP: Record<string, ProcessingStage> = {
  // UPLOADING stage
  upload: 'UPLOADING',
  receiving: 'UPLOADING',
  queued: 'UPLOADING',

  // OCR stage
  ocr: 'OCR',
  validation: 'OCR',
  text_extraction: 'OCR',

  // ENTITY_EXTRACTION stage
  entity_extraction: 'ENTITY_EXTRACTION',
  alias_resolution: 'ENTITY_EXTRACTION',
  mig_construction: 'ENTITY_EXTRACTION',

  // ANALYSIS stage
  chunking: 'ANALYSIS',
  embedding: 'ANALYSIS',
  date_extraction: 'ANALYSIS',
  event_classification: 'ANALYSIS',
  citation_extraction: 'ANALYSIS',
  contradiction_detection: 'ANALYSIS',

  // INDEXING stage
  indexing: 'INDEXING',
  completed: 'INDEXING',
  finalizing: 'INDEXING',
};

/**
 * Map backend current_stage to UI ProcessingStage.
 *
 * @param backendStage - Backend stage string from job.current_stage
 * @returns Corresponding UI ProcessingStage, defaults to UPLOADING if unknown
 *
 * @example
 * mapBackendStageToUI('ocr') // returns 'OCR'
 * mapBackendStageToUI('entity_extraction') // returns 'ENTITY_EXTRACTION'
 * mapBackendStageToUI('unknown_stage') // returns 'UPLOADING' (default)
 */
export function mapBackendStageToUI(backendStage: string | null | undefined): ProcessingStage {
  if (!backendStage) {
    return 'UPLOADING';
  }

  // Normalize: lowercase and trim
  const normalized = backendStage.toLowerCase().trim();

  return BACKEND_TO_UI_STAGE_MAP[normalized] ?? 'UPLOADING';
}

/**
 * Determine the overall processing stage from a list of job stages.
 *
 * Uses the stage of the first PROCESSING job, or the most advanced
 * stage if all jobs are in the same status.
 *
 * @param jobStages - Array of job current_stage strings
 * @returns Most relevant UI ProcessingStage
 */
export function determineOverallStage(
  jobStages: (string | null | undefined)[]
): ProcessingStage {
  if (jobStages.length === 0) {
    return 'UPLOADING';
  }

  // Filter out null/undefined and map to UI stages
  const uiStages = jobStages
    .filter((s): s is string => s !== null && s !== undefined)
    .map(mapBackendStageToUI);

  if (uiStages.length === 0) {
    return 'UPLOADING';
  }

  // Stage priority order (higher index = more advanced)
  const stagePriority: ProcessingStage[] = [
    'UPLOADING',
    'OCR',
    'ENTITY_EXTRACTION',
    'ANALYSIS',
    'INDEXING',
  ];

  // Find the most advanced stage
  let maxPriority = 0;
  for (const stage of uiStages) {
    const priority = stagePriority.indexOf(stage);
    if (priority > maxPriority) {
      maxPriority = priority;
    }
  }

  return stagePriority[maxPriority] ?? 'UPLOADING';
}

/**
 * Check if a backend status indicates completion.
 *
 * @param status - Backend job status string
 * @returns true if the job is in a terminal state
 */
export function isTerminalStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const normalized = status.toUpperCase();
  return ['COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED'].includes(normalized);
}

/**
 * Check if a backend status indicates active processing.
 *
 * @param status - Backend job status string
 * @returns true if the job is queued or processing
 */
export function isActiveStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const normalized = status.toUpperCase();
  return ['QUEUED', 'PROCESSING'].includes(normalized);
}
