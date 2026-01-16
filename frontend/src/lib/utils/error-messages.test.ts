import {
  getErrorMessage,
  getErrorDescription,
  isRetryableError,
  getErrorCodeFromStatus,
  getAffectedFeatures,
  CIRCUIT_TO_FEATURE,
} from './error-messages'

describe('error-messages', () => {
  describe('getErrorMessage', () => {
    it('returns correct message for known error code', () => {
      const message = getErrorMessage('RATE_LIMIT_EXCEEDED')

      expect(message.title).toBe('Too Many Requests')
      expect(message.description).toContain('too quickly')
      expect(message.isRetryable).toBe(true)
    })

    it('returns default message for unknown error code', () => {
      const message = getErrorMessage('UNKNOWN_CODE_12345')

      expect(message.title).toBe('Something Went Wrong')
      expect(message.isRetryable).toBe(true)
    })

    it('returns non-retryable for permission errors', () => {
      const message = getErrorMessage('UNAUTHORIZED')

      expect(message.isRetryable).toBe(false)
    })

    it('returns retryable for network errors', () => {
      const message = getErrorMessage('NETWORK_ERROR')

      expect(message.isRetryable).toBe(true)
    })
  })

  describe('getErrorDescription', () => {
    it('returns base description for regular errors', () => {
      const desc = getErrorDescription('NETWORK_ERROR')

      expect(desc).toBe('Unable to connect to the server. Please check your internet connection.')
    })

    it('includes retry countdown for rate limit errors', () => {
      const desc = getErrorDescription('RATE_LIMIT_EXCEEDED', { retryAfter: 30 })

      expect(desc).toBe("You're making requests too quickly. Please wait 30 seconds.")
    })

    it('uses default description when no retryAfter provided', () => {
      const desc = getErrorDescription('RATE_LIMIT_EXCEEDED')

      expect(desc).toContain('wait a moment')
    })
  })

  describe('isRetryableError', () => {
    it('returns true for retryable errors', () => {
      expect(isRetryableError('NETWORK_ERROR')).toBe(true)
      expect(isRetryableError('TIMEOUT')).toBe(true)
      expect(isRetryableError('SERVICE_UNAVAILABLE')).toBe(true)
      expect(isRetryableError('RATE_LIMIT_EXCEEDED')).toBe(true)
    })

    it('returns false for non-retryable errors', () => {
      expect(isRetryableError('UNAUTHORIZED')).toBe(false)
      expect(isRetryableError('FORBIDDEN')).toBe(false)
      expect(isRetryableError('VALIDATION_ERROR')).toBe(false)
    })
  })

  describe('getErrorCodeFromStatus', () => {
    it('maps status codes to error codes', () => {
      expect(getErrorCodeFromStatus(400)).toBe('VALIDATION_ERROR')
      expect(getErrorCodeFromStatus(401)).toBe('UNAUTHORIZED')
      expect(getErrorCodeFromStatus(403)).toBe('FORBIDDEN')
      expect(getErrorCodeFromStatus(404)).toBe('DOCUMENT_NOT_FOUND')
      expect(getErrorCodeFromStatus(429)).toBe('RATE_LIMIT_EXCEEDED')
      expect(getErrorCodeFromStatus(500)).toBe('INTERNAL_SERVER_ERROR')
      expect(getErrorCodeFromStatus(503)).toBe('SERVICE_UNAVAILABLE')
    })

    it('returns UNKNOWN_ERROR for unmapped status codes', () => {
      expect(getErrorCodeFromStatus(418)).toBe('UNKNOWN_ERROR')
      expect(getErrorCodeFromStatus(999)).toBe('UNKNOWN_ERROR')
    })
  })

  describe('getAffectedFeatures', () => {
    it('maps circuit names to feature names', () => {
      const features = getAffectedFeatures(['openai_chat', 'documentai_ocr'])

      expect(features).toContain('AI Chat')
      expect(features).toContain('Document Processing')
    })

    it('filters out unknown circuits', () => {
      const features = getAffectedFeatures(['openai_chat', 'unknown_circuit'])

      expect(features).toHaveLength(1)
      expect(features).toContain('AI Chat')
    })

    it('returns empty array for no circuits', () => {
      const features = getAffectedFeatures([])

      expect(features).toEqual([])
    })
  })

  describe('CIRCUIT_TO_FEATURE mapping', () => {
    it('contains all expected circuits', () => {
      expect(CIRCUIT_TO_FEATURE).toHaveProperty('openai_embeddings')
      expect(CIRCUIT_TO_FEATURE).toHaveProperty('openai_chat')
      expect(CIRCUIT_TO_FEATURE).toHaveProperty('gemini_flash')
      expect(CIRCUIT_TO_FEATURE).toHaveProperty('cohere_rerank')
      expect(CIRCUIT_TO_FEATURE).toHaveProperty('documentai_ocr')
    })
  })
})
