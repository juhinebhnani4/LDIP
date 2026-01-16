# Story 13.4: Implement Graceful Degradation and Error States

Status: dev-complete

## Story

As an **attorney**,
I want **clear error messages when things go wrong**,
So that **I understand what happened and what to do**.

## Acceptance Criteria

1. **Given** an API call fails
   **When** the error is handled
   **Then** the UI shows a clear error message
   **And** suggests a retry or alternative action

2. **Given** a long operation is running
   **When** loading states are shown
   **Then** clear progress indicators appear
   **And** users understand the wait

3. **Given** an external service is down (circuit breaker open)
   **When** degraded mode activates
   **Then** affected features show a warning
   **And** unaffected features continue to work

4. **Given** processing fails for a document
   **When** the error occurs
   **Then** the document shows an error state
   **And** users can retry or skip the document

## Tasks / Subtasks

- [x] Task 1: Create reusable error state components (AC: #1, #4)
  - [x] 1.1 Create `ErrorAlert` component in `components/ui/` with retry/dismiss actions
  - [x] 1.2 Create `ApiErrorBoundary` component for catching API errors in sections
  - [x] 1.3 Create `InlineError` component for inline error messages with icons

- [x] Task 2: Create loading state components (AC: #2)
  - [x] 2.1 Create `LoadingSpinner` with optional message prop
  - [x] 2.2 Create `ProgressBar` component with percentage and message
  - [x] 2.3 Create `OperationProgress` component for multi-step operations

- [x] Task 3: Implement service degradation banner (AC: #3)
  - [x] 3.1 Create `ServiceStatusBanner` component showing degraded services
  - [x] 3.2 Create `useServiceHealth` hook to poll `/health/circuits` endpoint
  - [x] 3.3 Add global status banner to workspace layout when circuits are open
  - [x] 3.4 Show service-specific warnings in affected features (mapped via CIRCUIT_TO_FEATURE)

- [x] Task 4: Enhance API client with error categorization (AC: #1)
  - [x] 4.1 Extend `ApiError` class with `isRetryable` and `userMessage` properties
  - [x] 4.2 Create `getErrorUserMessage()` helper mapping error codes to user-friendly messages
  - [x] 4.3 Add rate limit (429) specific handling with countdown display
  - [x] 4.4 Add circuit breaker error handling (show service degradation message)

- [x] Task 5: Implement document processing error states (AC: #4)
  - [x] 5.1 Add error state to document card in upload flow (enhanced UploadProgressView)
  - [x] 5.2 Add "Retry" and "Skip" buttons for failed document processing
  - [x] 5.3 Show processing failure reason with actionable guidance (tooltip)
  - [x] 5.4 Track failed documents in upload wizard store (already existed via setUploadFailed)

- [x] Task 6: Apply error handling to existing components (AC: #1, #2, #3)
  - [x] 6.1 Update `QAPanel` with streaming error states and retry option
  - [x] 6.2 Update `TimelineContent`/`TimelineList` with fetch error states and retry

- [x] Task 7: Write comprehensive tests (AC: #1-#4)
  - [x] 7.1 Test ErrorAlert rendering with different error types
  - [x] 7.2 Test ServiceStatusBanner with mock circuit breaker responses
  - [x] 7.3 Test useServiceHealth hook polling behavior
  - [x] 7.4 Test InlineError, LoadingSpinner, OperationProgress
  - [x] 7.5 Test error message mapping for all error codes

## Dev Notes

### Existing Infrastructure (DO NOT RECREATE)

**Backend Circuit Breaker (Story 13.2):**
- [backend/app/core/circuit_breaker.py](backend/app/core/circuit_breaker.py) - Full circuit breaker implementation
- [backend/app/api/routes/health.py](backend/app/api/routes/health.py) - `GET /health/circuits` endpoint returns all circuit states
- Circuit states: `closed` (healthy), `open` (failing fast), `half_open` (testing recovery)
- Protected services: `openai_embeddings`, `openai_chat`, `gemini_flash`, `cohere_rerank`, `documentai_ocr`

**Backend Rate Limiting (Story 13.3):**
- [backend/app/core/rate_limit.py](backend/app/core/rate_limit.py) - Rate limit implementation
- Returns 429 with `Retry-After` header and structured error response
- Error format: `{ error: { code: "RATE_LIMIT_EXCEEDED", message, details: { retry_after, limit, remaining } } }`

**Frontend API Client:**
```typescript
// File: frontend/src/lib/api/client.ts
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number
  ) { ... }
}
```

**Existing Toast System:**
```typescript
import { toast } from 'sonner';
toast.error(message);  // Already used throughout app
toast.success(message);
```

### Error Code to User Message Mapping

Create this mapping in `frontend/src/lib/utils/error-messages.ts`:

| Error Code | User Message |
|------------|--------------|
| `RATE_LIMIT_EXCEEDED` | "You're making requests too quickly. Please wait {retry_after} seconds." |
| `SESSION_EXPIRED` | "Your session has expired. Please log in again." |
| `MATTER_NOT_FOUND` | "This matter could not be found. It may have been deleted." |
| `DOCUMENT_NOT_FOUND` | "This document could not be found." |
| `INSUFFICIENT_PERMISSIONS` | "You don't have permission to perform this action." |
| `SERVICE_UNAVAILABLE` | "This feature is temporarily unavailable. Please try again shortly." |
| `CIRCUIT_OPEN` | "This service is experiencing issues. Some features may be limited." |
| `TIMEOUT` | "The request took too long. Please try again." |
| `OCR_FAILED` | "Document processing failed. You can retry or skip this document." |
| `LLM_FAILED` | "AI analysis failed. Results may be incomplete. Please try again." |
| `UNKNOWN_ERROR` | "Something went wrong. Please try again or contact support." |

### ServiceStatusBanner Component Spec

```typescript
// File: frontend/src/components/features/status/ServiceStatusBanner.tsx
interface ServiceStatusBannerProps {
  className?: string;
}

// Polls /health/circuits every 30 seconds
// Shows banner only when at least one circuit is 'open'
// Maps circuit names to user-friendly descriptions:
// - openai_embeddings/openai_chat: "AI Chat"
// - gemini_flash: "Document Analysis"
// - cohere_rerank: "Search"
// - documentai_ocr: "Document Processing"
```

### useServiceHealth Hook Spec

```typescript
// File: frontend/src/hooks/useServiceHealth.ts
interface CircuitStatus {
  name: string;
  state: 'closed' | 'open' | 'half_open';
  cooldownRemaining: number;
}

interface ServiceHealthState {
  circuits: CircuitStatus[];
  hasOpenCircuits: boolean;
  isLoading: boolean;
  error: Error | null;
  affectedFeatures: string[];  // e.g., ['AI Chat', 'Search']
}

export function useServiceHealth(pollIntervalMs?: number): ServiceHealthState;
// Default poll interval: 30000ms (30 seconds)
// Only polls when document is visible (use document.visibilityState)
```

### Error Alert Component Spec

```typescript
// File: frontend/src/components/ui/error-alert.tsx
interface ErrorAlertProps {
  error: ApiError | Error | string;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

// Uses Alert component from shadcn/ui
// Shows appropriate icon based on error type
// Retry button only shown if onRetry provided
// Dismiss button only shown if onDismiss provided
```

### Document Error State Flow

In upload wizard, document failures should:
1. Show red error indicator on document card
2. Display truncated error message (expand on hover)
3. Provide "Retry Processing" button
4. Provide "Skip Document" button (removes from processing queue)
5. Track in store: `failedDocuments: Array<{ documentId, errorCode, errorMessage }>`

### Integration Points

**Workspace Layout** (add ServiceStatusBanner):
```typescript
// File: frontend/src/app/(matter)/[matterId]/layout.tsx
// Add <ServiceStatusBanner /> above main content when circuits are degraded
```

**QAPanel Error Handling** (already uses toast, enhance):
```typescript
// File: frontend/src/components/features/chat/QAPanel.tsx:94-99
// Current: toast.error(error.message)
// Enhance: Show inline retry button for retryable errors
```

### Testing Strategy

Use Vitest + React Testing Library:

```typescript
// Test service health hook
describe('useServiceHealth', () => {
  it('returns hasOpenCircuits: true when any circuit is open', async () => {
    server.use(
      http.get('/api/health/circuits', () => {
        return HttpResponse.json({
          data: {
            circuits: [
              { circuit_name: 'openai_chat', state: 'open', cooldown_remaining: 45 }
            ]
          }
        });
      })
    );

    const { result } = renderHook(() => useServiceHealth());
    await waitFor(() => expect(result.current.hasOpenCircuits).toBe(true));
    expect(result.current.affectedFeatures).toContain('AI Chat');
  });
});
```

### Project Structure Notes

**New Files to Create:**
```
frontend/src/
├── components/
│   ├── ui/
│   │   └── error-alert.tsx           # Reusable error alert
│   └── features/
│       └── status/
│           ├── ServiceStatusBanner.tsx    # Global degradation banner
│           ├── ServiceStatusBanner.test.tsx
│           └── index.ts
├── hooks/
│   ├── useServiceHealth.ts           # Circuit status polling
│   └── useServiceHealth.test.ts
└── lib/
    └── utils/
        └── error-messages.ts         # Error code mapping
```

**Files to Modify:**
| File | Changes |
|------|---------|
| frontend/src/lib/api/client.ts | Add isRetryable, userMessage to ApiError |
| frontend/src/app/(matter)/[matterId]/layout.tsx | Add ServiceStatusBanner |
| frontend/src/components/features/chat/QAPanel.tsx | Add inline retry for errors |
| frontend/src/components/features/timeline/TimelineContent.tsx | Add error state |
| frontend/src/components/features/upload/DocumentCard.tsx | Add error/retry/skip |
| frontend/src/stores/uploadWizardStore.ts | Add failedDocuments tracking |

### Previous Story Learnings (13-3)

From Story 13.3 (Rate Limiting):
1. **Structured error responses** - Follow the `{ error: { code, message, details } }` format
2. **429 handling** - Include `Retry-After` header in responses, show countdown in UI
3. **User ID context** - Rate limit key uses user:{uuid} format
4. **Test patterns** - Use MSW for mocking API responses in frontend tests

From Story 13.2 (Circuit Breakers):
1. **Circuit states** - `closed`, `open`, `half_open` - map to user-friendly descriptions
2. **Cooldown remaining** - Show users when service might recover
3. **Service-specific messaging** - Different circuits affect different features
4. **Health endpoint** - `GET /health/circuits` returns all circuit statuses

### Architecture Requirements

From [architecture.md#Error-Handling]:
- Use React Error Boundaries for component crashes
- Use try-catch + toast for API errors
- Structured error responses with error codes
- Graceful degradation on timeout: "Analysis taking longer than usual..."

From [project-context.md#Anti-Patterns]:
```typescript
// WRONG - Catching errors silently
try { await upload() } catch (e) { /* silent */ }

// CORRECT - Handle and display errors
try { await upload() } catch (e) {
  if (e instanceof ApiError) {
    toast.error(getUserMessage(e.code));
  }
  throw e;
}
```

### Anti-Patterns to Avoid

1. **DO NOT** swallow errors silently - always inform the user
2. **DO NOT** show technical error messages to users - map to friendly messages
3. **DO NOT** block entire app on single feature failure - isolate failures
4. **DO NOT** poll health endpoint too frequently - 30 second minimum
5. **DO NOT** show raw status codes to users - use error code mapping
6. **DO NOT** forget to clean up polling on component unmount
7. **DO NOT** use console.log for errors - use structlog patterns and toast

### Security Considerations

1. Never expose internal error details to users (stack traces, SQL errors)
2. Sanitize error messages before display (prevent XSS)
3. Rate limit health endpoint access (already done in 13.3)
4. Don't reveal circuit breaker internal state details beyond what's needed

### References

- [Source: epics.md#Story-13.4] Acceptance criteria for graceful degradation
- [Source: architecture.md#Error-Handling-Patterns] Error handling standards
- [Source: project-context.md#Anti-Patterns] Error handling anti-patterns
- [Source: 13-2-circuit-breakers-tenacity.md] Circuit breaker implementation
- [Source: 13-3-rate-limiting-slowapi.md] Rate limit error format
- [shadcn/ui Alert](https://ui.shadcn.com/docs/components/alert) - Base alert component
- [sonner toast](https://sonner.emilkowal.ski/) - Toast notifications (already integrated)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No major issues encountered during implementation.

### Completion Notes List

1. Created comprehensive error state components (ErrorAlert, InlineError, ApiErrorBoundary)
2. Created loading state components (LoadingSpinner, ProgressBar, OperationProgress)
3. Created ServiceStatusBanner with useServiceHealth hook for circuit breaker status monitoring
4. Enhanced ApiError class with isRetryable, userMessage, and rateLimitDetails properties
5. Created error-messages.ts utility with error code to user-friendly message mapping
6. Enhanced UploadProgressView with Retry/Skip buttons for failed documents
7. Added inline error retry to QAPanel for streaming errors
8. Added retry callback to TimelineList error state
9. All tests written for new components and utilities
10. TypeScript compilation verified (no errors in implementation files)

### File List

**New Files Created:**
- frontend/src/lib/utils/error-messages.ts - Error code to user message mapping
- frontend/src/components/ui/error-alert.tsx - Reusable error alert component
- frontend/src/components/ui/inline-error.tsx - Inline error component
- frontend/src/components/ui/api-error-boundary.tsx - Error boundary for API errors
- frontend/src/components/ui/loading-spinner.tsx - Loading spinner component
- frontend/src/components/ui/progress-bar.tsx - Progress bar component
- frontend/src/components/ui/operation-progress.tsx - Multi-step operation progress
- frontend/src/hooks/useServiceHealth.ts - Circuit breaker status polling hook
- frontend/src/components/features/status/ServiceStatusBanner.tsx - Service degradation banner
- frontend/src/components/features/status/index.ts - Status feature exports
- frontend/src/lib/utils/error-messages.test.ts - Error messages utility tests
- frontend/src/components/ui/error-alert.test.tsx - ErrorAlert tests
- frontend/src/components/ui/inline-error.test.tsx - InlineError tests
- frontend/src/components/ui/loading-spinner.test.tsx - LoadingSpinner tests
- frontend/src/components/ui/operation-progress.test.tsx - OperationProgress tests
- frontend/src/hooks/useServiceHealth.test.ts - useServiceHealth hook tests
- frontend/src/components/features/status/ServiceStatusBanner.test.tsx - Banner tests

**Files Modified:**
- frontend/src/lib/api/client.ts - Enhanced ApiError class with isRetryable, userMessage, rateLimitDetails; added getErrorUserMessage() and canRetryError() helpers
- frontend/src/app/(matter)/[matterId]/layout.tsx - Added ServiceStatusBanner to workspace layout
- frontend/src/components/features/chat/QAPanel.tsx - Added inline error retry for streaming errors
- frontend/src/components/features/upload/UploadProgressView.tsx - Added Retry/Skip buttons for failed files
- frontend/src/components/features/timeline/TimelineList.tsx - Added onRetry prop to ErrorState
- frontend/src/components/features/timeline/TimelineContent.tsx - Passed refreshTimeline to TimelineList

