'use client';

/**
 * useExportGeneration Hook
 *
 * Manages export generation workflow including verification checks,
 * format selection, and document download.
 *
 * Story 12-3: AC #1, #2, #3 - Export verification and generation
 *
 * @example
 * ```tsx
 * const {
 *   generateExport,
 *   isGenerating,
 *   downloadUrl,
 *   error,
 * } = useExportGeneration('matter-123');
 *
 * const handleExport = async () => {
 *   await generateExport({
 *     format: 'pdf',
 *     sections: selectedSections,
 *   });
 * };
 * ```
 */

import { useState, useCallback } from 'react';
import { generateExport as generateExportApi, type ExportFormat, type ExportSectionEdit } from '@/lib/api/exports';
import { checkExportEligibility } from '@/lib/api/verifications';
import type { ExportEligibility } from '@/types';

export interface ExportGenerationOptions {
  format: ExportFormat;
  sections: string[];
  sectionEdits?: Record<string, ExportSectionEdit>;
  includeVerificationStatus?: boolean;
  skipVerificationCheck?: boolean;
}

export interface ExportGenerationResult {
  exportId: string;
  downloadUrl: string | null;
  fileName: string;
}

export interface UseExportGenerationReturn {
  /** Generate an export document */
  generateExport: (options: ExportGenerationOptions) => Promise<ExportGenerationResult | null>;
  /** Check export eligibility without generating */
  checkEligibility: () => Promise<ExportEligibility | null>;
  /** Current eligibility status */
  eligibility: ExportEligibility | null;
  /** Whether export is currently being generated */
  isGenerating: boolean;
  /** Whether eligibility is being checked */
  isChecking: boolean;
  /** Most recent download URL */
  downloadUrl: string | null;
  /** Most recent filename */
  fileName: string | null;
  /** Error message if generation failed */
  error: string | null;
  /** Clear error state */
  clearError: () => void;
  /** Reset all state */
  reset: () => void;
}

/**
 * Hook for managing export generation workflow.
 *
 * Features:
 * - Pre-export verification eligibility check
 * - Format selection (PDF, Word, PowerPoint)
 * - Section content with edits
 * - Download URL management
 * - Error handling
 *
 * @param matterId - Matter UUID for the export.
 * @returns Export generation state and methods.
 */
export function useExportGeneration(matterId: string): UseExportGenerationReturn {
  const [eligibility, setEligibility] = useState<ExportEligibility | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  /**
   * Check export eligibility without generating.
   */
  const checkEligibility = useCallback(async (): Promise<ExportEligibility | null> => {
    if (!matterId) {
      setError('Matter ID is required');
      return null;
    }

    setIsChecking(true);
    setError(null);

    try {
      const result = await checkExportEligibility(matterId);
      setEligibility(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to check export eligibility';
      setError(message);
      return null;
    } finally {
      setIsChecking(false);
    }
  }, [matterId]);

  /**
   * Generate an export document.
   */
  const generateExport = useCallback(
    async (options: ExportGenerationOptions): Promise<ExportGenerationResult | null> => {
      if (!matterId) {
        setError('Matter ID is required');
        return null;
      }

      if (!options.sections.length) {
        setError('At least one section must be selected');
        return null;
      }

      setIsGenerating(true);
      setError(null);
      setDownloadUrl(null);
      setFileName(null);

      try {
        // Check eligibility first (unless skipped)
        if (!options.skipVerificationCheck) {
          const eligibilityResult = await checkExportEligibility(matterId);
          setEligibility(eligibilityResult);

          if (!eligibilityResult.eligible) {
            setError(
              `Export blocked: ${eligibilityResult.blockingCount} finding(s) require verification`
            );
            return null;
          }
        }

        // Generate the export
        const result = await generateExportApi(matterId, {
          format: options.format,
          sections: options.sections,
          sectionEdits: options.sectionEdits,
          includeVerificationStatus: options.includeVerificationStatus ?? true,
        });

        if (result.status === 'completed' && result.downloadUrl) {
          setDownloadUrl(result.downloadUrl);
          setFileName(result.fileName);

          return {
            exportId: result.exportId,
            downloadUrl: result.downloadUrl,
            fileName: result.fileName,
          };
        } else if (result.status === 'failed') {
          setError(result.message || 'Export generation failed');
          return null;
        } else if (result.status === 'completed' && !result.downloadUrl) {
          // Issue #3 fix: Handle completed status but no download URL
          setError('Export completed but download URL not available. Please try again.');
          return null;
        }

        // Generating status - shouldn't happen for sync exports but handle gracefully
        setError('Export is still processing. Please wait and try again.');
        return null;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to generate export';
        setError(message);
        return null;
      } finally {
        setIsGenerating(false);
      }
    },
    [matterId]
  );

  /**
   * Clear error state.
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Reset all state.
   */
  const reset = useCallback(() => {
    setEligibility(null);
    setIsGenerating(false);
    setIsChecking(false);
    setDownloadUrl(null);
    setFileName(null);
    setError(null);
  }, []);

  return {
    generateExport,
    checkEligibility,
    eligibility,
    isGenerating,
    isChecking,
    downloadUrl,
    fileName,
    error,
    clearError,
    reset,
  };
}
