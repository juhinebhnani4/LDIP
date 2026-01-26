/**
 * Bounding Box API Client
 *
 * Functions for fetching bounding boxes for documents, pages, and chunks.
 * All endpoints enforce matter isolation via RLS and Layer 4 validation.
 */

import { api } from './client'
import type {
  BoundingBox,
  BoundingBoxListResponse,
  BoundingBoxPageResponse,
} from '@/types/document'

/**
 * Transform backend bounding box response to frontend format.
 * Handles both snake_case and camelCase for backward compatibility.
 * Uses safe type coercion to handle unexpected data types.
 */
function transformBoundingBox(bbox: Record<string, unknown>): BoundingBox {
  return {
    id: String(bbox.id ?? ''),
    documentId: String(bbox.documentId ?? bbox.document_id ?? ''),
    pageNumber: Number(bbox.pageNumber ?? bbox.page_number ?? 0),
    x: Number(bbox.x ?? 0),
    y: Number(bbox.y ?? 0),
    width: Number(bbox.width ?? 0),
    height: Number(bbox.height ?? 0),
    text: String(bbox.text ?? ''),
    confidence: (bbox.confidence != null) ? Number(bbox.confidence) : null,
    readingOrderIndex: (bbox.readingOrderIndex ?? bbox.reading_order_index) != null ? Number(bbox.readingOrderIndex ?? bbox.reading_order_index) : null,
  }
}

/**
 * Transform backend list response to frontend format.
 * Handles both snake_case and camelCase for backward compatibility.
 */
function transformListResponse(response: {
  data: Record<string, unknown>[]
  meta?: Record<string, unknown>
}): BoundingBoxListResponse {
  const m = response.meta;
  return {
    data: response.data.map(transformBoundingBox),
    meta: m
      ? {
          total: (m.total ?? 0) as number,
          page: (m.page ?? 1) as number,
          perPage: ((m.perPage ?? m.per_page) ?? 20) as number,
          totalPages: ((m.totalPages ?? m.total_pages) ?? 0) as number,
        }
      : undefined,
  }
}

/**
 * Transform backend page response to frontend format.
 */
function transformPageResponse(response: {
  data: Record<string, unknown>[]
}): BoundingBoxPageResponse {
  return {
    data: response.data.map(transformBoundingBox),
  }
}

/**
 * Fetch all bounding boxes for a document.
 *
 * Returns paginated list of bounding boxes sorted by page number
 * and reading order index.
 *
 * @param documentId - Document UUID
 * @param options - Pagination options
 * @returns Bounding boxes with pagination metadata
 */
export async function fetchBoundingBoxesForDocument(
  documentId: string,
  options?: { page?: number; perPage?: number }
): Promise<BoundingBoxListResponse> {
  const params = new URLSearchParams()
  if (options?.page) params.append('page', String(options.page))
  if (options?.perPage) params.append('per_page', String(options.perPage))

  const queryString = params.toString()
  const endpoint = `/api/documents/${documentId}/bounding-boxes${queryString ? `?${queryString}` : ''}`

  const response = await api.get<{
    data: Record<string, unknown>[]
    meta?: { total: number; page: number; per_page: number; total_pages: number }
  }>(endpoint)

  return transformListResponse(response)
}

/**
 * Fetch bounding boxes for a specific page.
 *
 * Returns all bounding boxes for the page sorted by reading order.
 *
 * @param documentId - Document UUID
 * @param pageNumber - Page number (1-indexed)
 * @returns Bounding boxes for the page
 */
export async function fetchBoundingBoxesForPage(
  documentId: string,
  pageNumber: number
): Promise<BoundingBoxPageResponse> {
  const response = await api.get<{ data: Record<string, unknown>[] }>(
    `/api/documents/${documentId}/pages/${pageNumber}/bounding-boxes`
  )

  return transformPageResponse(response)
}

/**
 * Fetch bounding boxes for a chunk.
 *
 * Returns bounding boxes linked to the chunk via its bbox_ids array.
 * Useful for highlighting search results or citations.
 *
 * @param chunkId - Chunk UUID
 * @returns Bounding boxes linked to the chunk
 */
export async function fetchBoundingBoxesForChunk(
  chunkId: string
): Promise<BoundingBoxPageResponse> {
  const response = await api.get<{ data: Record<string, unknown>[] }>(
    `/api/chunks/${chunkId}/bounding-boxes`
  )

  return transformPageResponse(response)
}

/**
 * Fetch bounding boxes by their IDs directly.
 *
 * This allows fetching bboxes when you already have the IDs
 * (e.g., from Q&A source references with bboxIds).
 *
 * @param bboxIds - Array of bbox UUIDs
 * @param matterId - Matter UUID for access control
 * @returns Bounding boxes matching the IDs
 */
export async function fetchBoundingBoxesByIds(
  bboxIds: string[],
  matterId: string
): Promise<BoundingBoxPageResponse> {
  const response = await api.post<{ data: Record<string, unknown>[] }>(
    '/api/bounding-boxes/by-ids',
    { bbox_ids: bboxIds, matter_id: matterId }
  )

  return transformPageResponse(response)
}
