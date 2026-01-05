/**
 * Standard API response wrapper for single items.
 */
export interface ApiResponse<T> {
  data: T
}

/**
 * Standard API response wrapper for paginated lists.
 */
export interface PaginatedResponse<T> {
  data: T[]
  meta: {
    total: number
    page: number
    per_page: number
    total_pages: number
  }
}

/**
 * Standard API error response structure.
 */
export interface ApiErrorResponse {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}


