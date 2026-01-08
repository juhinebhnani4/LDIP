'use client'

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
 * Maps snake_case from backend to camelCase for frontend.
 */
function transformBoundingBox(bbox: Record<string, unknown>): BoundingBox {
  return {
    id: bbox.id as string,
    documentId: bbox.document_id as string,
    pageNumber: bbox.page_number as number,
    x: bbox.x as number,
    y: bbox.y as number,
    width: bbox.width as number,
    height: bbox.height as number,
    text: bbox.text as string,
    confidence: bbox.confidence as number | null,
    readingOrderIndex: bbox.reading_order_index as number | null,
  }
}

/**
 * Transform backend list response to frontend format.
 */
function transformListResponse(response: {
  data: Record<string, unknown>[]
  meta?: { total: number; page: number; per_page: number }
}): BoundingBoxListResponse {
  return {
    data: response.data.map(transformBoundingBox),
    meta: response.meta
      ? {
          total: response.meta.total,
          page: response.meta.page,
          perPage: response.meta.per_page,
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
    meta?: { total: number; page: number; per_page: number }
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
