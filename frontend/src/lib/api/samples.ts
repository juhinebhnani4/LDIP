/**
 * Samples API Client
 *
 * Story 6.3: Sample Case Import
 * API client for importing sample documents for new users.
 */

import { api } from './client';

export interface SampleImportResponse {
  matterId: string;
  matterTitle: string;
  documentCount: number;
  message: string;
}

export interface SampleCheckResponse {
  hasSampleCase: boolean;
  sampleMatterId: string | null;
}

/**
 * Import sample case with pre-loaded documents.
 *
 * Creates a new matter with sample documents for exploring LDIP features.
 *
 * @throws Error if user already has a sample case
 */
export async function importSampleCase(): Promise<SampleImportResponse> {
  return api.post<SampleImportResponse>('/api/samples/import', {});
}

/**
 * Check if user already has a sample case.
 */
export async function checkSampleExists(): Promise<SampleCheckResponse> {
  return api.get<SampleCheckResponse>('/api/samples/check');
}
