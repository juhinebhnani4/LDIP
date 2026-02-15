/** Error context for support requests */
export interface ErrorContext {
  errorCode: string
  errorMessage: string
  timestamp: string
  userId?: string
  matterId?: string
  matterTitle?: string
  browserInfo: string
  currentUrl: string
  correlationId?: string
}
