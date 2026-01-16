/**
 * Export API Client for Document Generation
 *
 * Provides typed API functions for export operations.
 *
 * Story 12-3: Export Verification Check and Format Generation
 * Epic 12: Export Builder
 */

import { api } from './client';

// =============================================================================
// Story 12-3: Export Types (Task 6.1)
// =============================================================================

export type ExportFormat = 'pdf' | 'word' | 'powerpoint';

export type ExportStatus = 'generating' | 'completed' | 'failed';

export interface ExportSectionEdit {
  textContent?: string;
  removedItemIds: string[];
  addedNotes: string[];
}

export interface ExportRequest {
  format: ExportFormat;
  sections: string[];
  sectionEdits?: Record<string, ExportSectionEdit>;
  includeVerificationStatus?: boolean;
}

export interface ExportGenerationResponse {
  exportId: string;
  status: ExportStatus;
  downloadUrl: string | null;
  fileName: string;
  message: string;
}

export interface ExportRecord {
  id: string;
  matterId: string;
  format: ExportFormat;
  status: ExportStatus;
  filePath: string | null;
  downloadUrl: string | null;
  fileName: string;
  sectionsIncluded: string[];
  verificationSummary: Record<string, unknown>;
  createdBy: string;
  createdAt: string;
  completedAt: string | null;
  errorMessage: string | null;
}

export interface ExportResponse {
  data: ExportRecord;
}

export interface ExportListItem {
  id: string;
  format: ExportFormat;
  status: ExportStatus;
  fileName: string;
  createdAt: string;
  completedAt: string | null;
}

export interface ExportListResponse {
  data: ExportListItem[];
}

// =============================================================================
// Story 12-3: Export API Functions (Task 6.2)
// =============================================================================

/**
 * Generate an export document.
 *
 * @param matterId - Matter UUID.
 * @param request - Export request with format and sections.
 * @returns Export generation response with download URL.
 *
 * @example
 * ```ts
 * const result = await generateExport('matter-123', {
 *   format: 'pdf',
 *   sections: ['executive-summary', 'timeline'],
 * });
 * window.open(result.downloadUrl, '_blank');
 * ```
 */
export async function generateExport(
  matterId: string,
  request: ExportRequest
): Promise<ExportGenerationResponse> {
  // Convert camelCase to snake_case for API
  const apiRequest = {
    format: request.format,
    sections: request.sections,
    section_edits: request.sectionEdits
      ? Object.fromEntries(
          Object.entries(request.sectionEdits).map(([key, edit]) => [
            key,
            {
              text_content: edit.textContent ?? null,
              removed_item_ids: edit.removedItemIds,
              added_notes: edit.addedNotes,
            },
          ])
        )
      : {},
    include_verification_status: request.includeVerificationStatus ?? true,
  };

  const response = await api.post<{
    export_id: string;
    status: ExportStatus;
    download_url: string | null;
    file_name: string;
    message: string;
  }>(`/api/matters/${matterId}/exports`, apiRequest);

  return {
    exportId: response.export_id,
    status: response.status,
    downloadUrl: response.download_url,
    fileName: response.file_name,
    message: response.message,
  };
}

/**
 * Get an export record by ID.
 *
 * @param matterId - Matter UUID.
 * @param exportId - Export UUID.
 * @returns Export record with download URL.
 *
 * @example
 * ```ts
 * const export = await getExport('matter-123', 'export-456');
 * if (export.status === 'completed') {
 *   window.open(export.downloadUrl, '_blank');
 * }
 * ```
 */
export async function getExport(
  matterId: string,
  exportId: string
): Promise<ExportRecord> {
  const response = await api.get<{
    data: {
      id: string;
      matter_id: string;
      format: ExportFormat;
      status: ExportStatus;
      file_path: string | null;
      download_url: string | null;
      file_name: string;
      sections_included: string[];
      verification_summary: Record<string, unknown>;
      created_by: string;
      created_at: string;
      completed_at: string | null;
      error_message: string | null;
    };
  }>(`/api/matters/${matterId}/exports/${exportId}`);

  const data = response.data;
  return {
    id: data.id,
    matterId: data.matter_id,
    format: data.format,
    status: data.status,
    filePath: data.file_path,
    downloadUrl: data.download_url,
    fileName: data.file_name,
    sectionsIncluded: data.sections_included,
    verificationSummary: data.verification_summary,
    createdBy: data.created_by,
    createdAt: data.created_at,
    completedAt: data.completed_at,
    errorMessage: data.error_message,
  };
}

/**
 * List export history for a matter.
 *
 * @param matterId - Matter UUID.
 * @param limit - Max exports to return (default 10).
 * @returns List of recent exports.
 *
 * @example
 * ```ts
 * const exports = await listExports('matter-123');
 * console.log(`${exports.length} exports found`);
 * ```
 */
export async function listExports(
  matterId: string,
  limit: number = 10
): Promise<ExportListItem[]> {
  const response = await api.get<{
    data: Array<{
      id: string;
      format: ExportFormat;
      status: ExportStatus;
      file_name: string;
      created_at: string;
      completed_at: string | null;
    }>;
  }>(`/api/matters/${matterId}/exports?limit=${limit}`);

  return response.data.map((item) => ({
    id: item.id,
    format: item.format,
    status: item.status,
    fileName: item.file_name,
    createdAt: item.created_at,
    completedAt: item.completed_at,
  }));
}

// =============================================================================
// Story 12-3: Consolidated API Object
// =============================================================================

/**
 * Export API methods consolidated for convenience.
 */
export const exportsApi = {
  generate: generateExport,
  get: getExport,
  list: listExports,
};
