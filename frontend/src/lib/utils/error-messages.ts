/**
 * Error code to user-friendly message mapping.
 * Story 13.4: Graceful Degradation and Error States
 */

/** Error message with optional retry information */
export interface ErrorMessage {
  title: string
  description: string
  isRetryable: boolean
}

/**
 * Map error codes to user-friendly messages.
 * Designed to be clear and actionable for attorneys using the platform.
 */
const ERROR_MESSAGES: Record<string, ErrorMessage> = {
  // Authentication & Session
  RATE_LIMIT_EXCEEDED: {
    title: 'Too Many Requests',
    description: "You're making requests too quickly. Please wait a moment and try again.",
    isRetryable: true,
  },
  SESSION_EXPIRED: {
    title: 'Session Expired',
    description: 'Your session has expired. Please log in again to continue.',
    isRetryable: false,
  },
  UNAUTHORIZED: {
    title: 'Not Authorized',
    description: 'You need to log in to access this feature.',
    isRetryable: false,
  },

  // Resource Not Found
  MATTER_NOT_FOUND: {
    title: 'Matter Not Found',
    description: 'This matter could not be found. It may have been deleted or you may not have access.',
    isRetryable: false,
  },
  DOCUMENT_NOT_FOUND: {
    title: 'Document Not Found',
    description: 'This document could not be found. It may have been removed.',
    isRetryable: false,
  },
  ENTITY_NOT_FOUND: {
    title: 'Entity Not Found',
    description: 'This entity could not be found.',
    isRetryable: false,
  },
  EVENT_NOT_FOUND: {
    title: 'Event Not Found',
    description: 'This timeline event could not be found.',
    isRetryable: false,
  },

  // Permission Errors
  INSUFFICIENT_PERMISSIONS: {
    title: 'Permission Denied',
    description: "You don't have permission to perform this action. Contact the matter owner if you need access.",
    isRetryable: false,
  },
  FORBIDDEN: {
    title: 'Access Denied',
    description: "You don't have permission to access this resource.",
    isRetryable: false,
  },

  // Service Availability
  SERVICE_UNAVAILABLE: {
    title: 'Service Temporarily Unavailable',
    description: 'This feature is temporarily unavailable. Please try again in a few moments.',
    isRetryable: true,
  },
  CIRCUIT_OPEN: {
    title: 'Service Experiencing Issues',
    description: 'This service is experiencing issues. Some features may be limited until the service recovers.',
    isRetryable: true,
  },
  TIMEOUT: {
    title: 'Request Timed Out',
    description: 'The request took too long to complete. Please try again.',
    isRetryable: true,
  },
  GATEWAY_TIMEOUT: {
    title: 'Server Timeout',
    description: 'The server took too long to respond. Please try again.',
    isRetryable: true,
  },

  // Processing Errors
  OCR_FAILED: {
    title: 'Document Processing Failed',
    description: 'We could not process this document. You can retry or skip it.',
    isRetryable: true,
  },
  LLM_FAILED: {
    title: 'AI Analysis Failed',
    description: 'AI analysis could not be completed. Results may be incomplete. Please try again.',
    isRetryable: true,
  },
  EXTRACTION_FAILED: {
    title: 'Extraction Failed',
    description: 'We could not extract information from this document. Please try again.',
    isRetryable: true,
  },
  EMBEDDING_FAILED: {
    title: 'Search Indexing Failed',
    description: 'Document search indexing failed. The document may not appear in search results.',
    isRetryable: true,
  },

  // Validation Errors
  VALIDATION_ERROR: {
    title: 'Invalid Input',
    description: 'Please check your input and try again.',
    isRetryable: false,
  },
  INVALID_FILE_TYPE: {
    title: 'Invalid File Type',
    description: 'This file type is not supported. Please upload a PDF, DOC, or image file.',
    isRetryable: false,
  },
  FILE_TOO_LARGE: {
    title: 'File Too Large',
    description: 'This file exceeds the maximum size limit. Please use a smaller file.',
    isRetryable: false,
  },

  // Network Errors
  NETWORK_ERROR: {
    title: 'Connection Error',
    description: 'Unable to connect to the server. Please check your internet connection.',
    isRetryable: true,
  },
  FETCH_FAILED: {
    title: 'Request Failed',
    description: 'The request could not be completed. Please try again.',
    isRetryable: true,
  },

  // Generic
  UNKNOWN_ERROR: {
    title: 'Something Went Wrong',
    description: 'An unexpected error occurred. Please try again or contact support if the problem persists.',
    isRetryable: true,
  },
  INTERNAL_SERVER_ERROR: {
    title: 'Server Error',
    description: 'A server error occurred. Our team has been notified. Please try again.',
    isRetryable: true,
  },
}

/** Default error message for unknown errors */
const DEFAULT_ERROR: ErrorMessage = {
  title: 'Something Went Wrong',
  description: 'An unexpected error occurred. Please try again or contact support if the problem persists.',
  isRetryable: true,
}

/**
 * Get user-friendly error message for an error code.
 * Returns a default message if the code is not recognized.
 */
export function getErrorMessage(code: string): ErrorMessage {
  return ERROR_MESSAGES[code] ?? DEFAULT_ERROR
}

/**
 * Get user-friendly description for an error code.
 * Can include dynamic values like retry countdown.
 */
export function getErrorDescription(code: string, details?: { retryAfter?: number }): string {
  if (code === 'RATE_LIMIT_EXCEEDED' && details?.retryAfter) {
    return `You're making requests too quickly. Please wait ${details.retryAfter} seconds.`
  }
  return getErrorMessage(code).description
}

/**
 * Check if an error is retryable based on its code.
 */
export function isRetryableError(code: string): boolean {
  return getErrorMessage(code).isRetryable
}

/**
 * Map HTTP status codes to error codes when no specific code is provided.
 */
export function getErrorCodeFromStatus(status: number): string {
  switch (status) {
    case 400:
      return 'VALIDATION_ERROR'
    case 401:
      return 'UNAUTHORIZED'
    case 403:
      return 'FORBIDDEN'
    case 404:
      return 'DOCUMENT_NOT_FOUND'
    case 408:
      return 'TIMEOUT'
    case 429:
      return 'RATE_LIMIT_EXCEEDED'
    case 500:
      return 'INTERNAL_SERVER_ERROR'
    case 502:
    case 503:
      return 'SERVICE_UNAVAILABLE'
    case 504:
      return 'GATEWAY_TIMEOUT'
    default:
      return 'UNKNOWN_ERROR'
  }
}

/**
 * Map circuit names to user-friendly feature names.
 * Used by ServiceStatusBanner to show which features are affected.
 */
export const CIRCUIT_TO_FEATURE: Record<string, string> = {
  openai_embeddings: 'Search',
  openai_chat: 'AI Chat',
  gemini_flash: 'Document Analysis',
  cohere_rerank: 'Search Ranking',
  documentai_ocr: 'Document Processing',
}

/**
 * Get affected feature names for a list of open circuits.
 */
export function getAffectedFeatures(openCircuits: string[]): string[] {
  return openCircuits
    .map((circuit) => CIRCUIT_TO_FEATURE[circuit])
    .filter((feature): feature is string => Boolean(feature))
}
