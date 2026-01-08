'use client'

import { api } from './client'
import type {
  ChunkContextResponse,
  ChunkListResponse,
  ChunkResponse,
  ChunkType,
} from '@/types/document'

/**
 * Chunk API client for RAG retrieval operations.
 *
 * Provides methods for fetching document chunks and their context
 * for search results and citation display.
 */
export const chunksApi = {
  /**
   * Get all chunks for a document.
   *
   * @param documentId - Document UUID
   * @param chunkType - Optional filter by chunk type ('parent' or 'child')
   * @returns Promise resolving to chunk list with statistics
   */
  getDocumentChunks: async (
    documentId: string,
    chunkType?: ChunkType
  ): Promise<ChunkListResponse> => {
    const params = new URLSearchParams()
    if (chunkType) {
      params.set('chunk_type', chunkType)
    }
    const query = params.toString()
    const url = `/api/documents/${documentId}/chunks${query ? `?${query}` : ''}`
    return api.get<ChunkListResponse>(url)
  },

  /**
   * Get a single chunk by ID.
   *
   * @param chunkId - Chunk UUID
   * @returns Promise resolving to the chunk
   */
  getChunk: async (chunkId: string): Promise<ChunkResponse> => {
    return api.get<ChunkResponse>(`/api/chunks/${chunkId}`)
  },

  /**
   * Get a chunk with surrounding context.
   *
   * For child chunks, returns parent and siblings.
   * For parent chunks, returns all children.
   *
   * @param chunkId - Chunk UUID
   * @returns Promise resolving to chunk with context
   */
  getChunkContext: async (chunkId: string): Promise<ChunkContextResponse> => {
    return api.get<ChunkContextResponse>(`/api/chunks/${chunkId}/context`)
  },

  /**
   * Get the parent chunk of a child chunk.
   *
   * @param chunkId - Child chunk UUID
   * @returns Promise resolving to the parent chunk
   * @throws ApiError with code NO_PARENT_CHUNK if chunk has no parent
   */
  getChunkParent: async (chunkId: string): Promise<ChunkResponse> => {
    return api.get<ChunkResponse>(`/api/chunks/${chunkId}/parent`)
  },

  /**
   * Get all child chunks of a parent chunk.
   *
   * @param chunkId - Parent chunk UUID
   * @returns Promise resolving to list of child chunks
   */
  getChunkChildren: async (chunkId: string): Promise<ChunkListResponse> => {
    return api.get<ChunkListResponse>(`/api/chunks/${chunkId}/children`)
  },
}
