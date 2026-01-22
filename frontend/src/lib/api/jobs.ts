'use client'

/**
 * Jobs API Client
 *
 * API functions for background job tracking and management.
 * Story 2c-3: Background Job Status Tracking and Retry
 */

import { api } from './client'
import type {
  JobCancelResponse,
  JobDetailResponse,
  JobListResponse,
  JobQueueStats,
  JobResetResponse,
  JobRetryRequest,
  JobRetryResponse,
  JobSkipResponse,
  JobStatus,
  JobType,
  StuckJobsResponse,
} from '@/types/job'

// =============================================================================
// Job Query API
// =============================================================================

export interface ListJobsParams {
  matterId: string
  status?: JobStatus
  jobType?: JobType
  limit?: number
  offset?: number
}

/**
 * List processing jobs for a matter.
 */
export async function listJobs(params: ListJobsParams): Promise<JobListResponse> {
  const { matterId, status, jobType, limit = 50, offset = 0 } = params

  const queryParams = new URLSearchParams()
  if (status) queryParams.set('status', status)
  if (jobType) queryParams.set('job_type', jobType)
  queryParams.set('limit', limit.toString())
  queryParams.set('offset', offset.toString())

  const query = queryParams.toString()
  return api.get<JobListResponse>(
    `/api/jobs/matters/${matterId}${query ? `?${query}` : ''}`
  )
}

/**
 * Get job queue statistics for a matter.
 */
export async function getJobStats(matterId: string): Promise<JobQueueStats> {
  return api.get<JobQueueStats>(`/api/jobs/matters/${matterId}/stats`)
}

/**
 * Get stuck jobs for a matter.
 */
export async function getStuckJobs(
  matterId: string,
  thresholdMinutes?: number
): Promise<StuckJobsResponse> {
  const query = thresholdMinutes ? `?threshold_minutes=${thresholdMinutes}` : ''
  return api.get<StuckJobsResponse>(`/api/jobs/matters/${matterId}/stuck${query}`)
}

/**
 * Get details for a specific job.
 */
export async function getJob(jobId: string): Promise<JobDetailResponse> {
  return api.get<JobDetailResponse>(`/api/jobs/${jobId}`)
}

/**
 * Get active job for a document (if any).
 */
export async function getActiveJobForDocument(
  documentId: string
): Promise<JobDetailResponse | null> {
  return api.get<JobDetailResponse | null>(`/api/jobs/documents/${documentId}/active`)
}

// =============================================================================
// Job Action API
// =============================================================================

/**
 * Retry a failed job.
 */
export async function retryJob(
  jobId: string,
  options?: JobRetryRequest
): Promise<JobRetryResponse> {
  return api.post<JobRetryResponse>(`/api/jobs/${jobId}/retry`, options ?? {})
}

/**
 * Skip a failed job.
 */
export async function skipJob(jobId: string): Promise<JobSkipResponse> {
  return api.post<JobSkipResponse>(`/api/jobs/${jobId}/skip`, {})
}

/**
 * Cancel a pending or processing job.
 */
export async function cancelJob(jobId: string): Promise<JobCancelResponse> {
  return api.post<JobCancelResponse>(`/api/jobs/${jobId}/cancel`, {})
}

/**
 * Reset a stuck or failed job back to QUEUED for re-processing.
 */
export async function resetJob(jobId: string): Promise<JobResetResponse> {
  return api.post<JobResetResponse>(`/api/jobs/${jobId}/reset`, {})
}

// =============================================================================
// Convenience Hooks Data (for use with SWR or React Query)
// =============================================================================

/**
 * Get SWR key for jobs list.
 */
export function getJobsKey(params: ListJobsParams): string {
  const { matterId, status, jobType, limit = 50, offset = 0 } = params
  const parts = [`jobs:matter:${matterId}`]
  if (status) parts.push(`status:${status}`)
  if (jobType) parts.push(`type:${jobType}`)
  parts.push(`limit:${limit}`)
  parts.push(`offset:${offset}`)
  return parts.join(':')
}

/**
 * Get SWR key for job stats.
 */
export function getJobStatsKey(matterId: string): string {
  return `job-stats:${matterId}`
}

/**
 * Get SWR key for job detail.
 */
export function getJobKey(jobId: string): string {
  return `job:${jobId}`
}

/**
 * Get SWR key for active document job.
 */
export function getActiveJobKey(documentId: string): string {
  return `active-job:${documentId}`
}

// =============================================================================
// Exported API Object
// =============================================================================

export const jobsApi = {
  // Query
  list: listJobs,
  getStats: getJobStats,
  getStuckJobs: getStuckJobs,
  get: getJob,
  getActiveForDocument: getActiveJobForDocument,

  // Actions
  retry: retryJob,
  skip: skipJob,
  cancel: cancelJob,
  reset: resetJob,

  // Keys
  keys: {
    jobs: getJobsKey,
    stats: getJobStatsKey,
    job: getJobKey,
    activeJob: getActiveJobKey,
  },
}
