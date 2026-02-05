---
stepsCompleted: [1, 2, 3, 4]
workflowComplete: true
inputDocuments:
  - '_bmad-output/prd.md'
  - '_bmad-output/architecture.md'
  - '_bmad-output/project-planning-artifacts/ux-design-jaanch.md'
---

# LDIP User Experience Reliability Fixes - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for LDIP User Experience Reliability Fixes, decomposing the requirements from the PRD, Architecture, and UX Design into implementable stories.

**Scope:** 6 critical user-facing reliability issues
**Project Context:** Brownfield — extending existing production system

## Requirements Inventory

### Functional Requirements

#### Citation Accuracy

- FR1: System can detect the correct source page from bounding box data when displaying timeline events
- FR2: System can fall back to chunk-level page detection when bounding box data is unavailable
- FR3: Users can see which page number will be displayed before clicking a citation link
- FR4: System can process citation page references without producing "p. ?" output
- FR5: System can log when page detection falls back to chunk page for monitoring purposes

#### Response Completeness

- FR6: Users can see an error notification when SSE stream contains malformed JSON
- FR7: System can detect SSE parse failures and display user-visible feedback
- FR8: Users can understand when a chat response was interrupted vs completed normally
- FR9: System can log SSE parse errors with sufficient context for debugging

#### Error Visibility & Feedback

- FR10: Users can distinguish between "no entities found" and "entity extraction failed" states
- FR11: Users can see clear error messages when backend operations fail
- FR12: Users can understand what action to take when an error occurs
- FR13: System can display contextual error messages with actionable next steps

#### Real-time Connection Reliability

- FR14: System can detect when WebSocket connection is lost
- FR15: System can automatically attempt to reconnect WebSocket connections
- FR16: Users can see a "Reconnecting..." indicator when WebSocket is disconnecting
- FR17: System can re-subscribe to relevant topics after WebSocket reconnection
- FR18: Users can continue using the application during WebSocket reconnection attempts

#### Request Timeout Handling

- FR19: System can enforce maximum wait times on all frontend API requests
- FR20: Users can see feedback when a request is taking longer than expected
- FR21: Users can see an error message when a request times out
- FR22: System can cancel and cleanup requests that exceed timeout thresholds

#### Monitoring & Diagnostics

- FR23: Support staff can view citation page accuracy metrics per matter
- FR24: Support staff can view SSE error rates and patterns
- FR25: Support staff can view WebSocket connection health metrics
- FR26: Support staff can view entity extraction success/failure rates
- FR27: System can log all reliability events with sufficient context for debugging

### NonFunctional Requirements

#### Performance

- NFR1: Frontend API requests must timeout after 30 seconds maximum
- NFR2: WebSocket reconnection attempts must begin within 1 second of disconnect detection
- NFR3: Error toast notifications must appear within 500ms of error detection
- NFR4: Citation page detection must not add perceptible latency to timeline/citation display

#### Reliability

- NFR5: WebSocket connections must automatically reconnect with exponential backoff (1s → 2s → 4s → 8s → 30s max)
- NFR6: SSE parse failures must never silently fail — all errors produce user-visible feedback
- NFR7: Citation page accuracy must be ≥95% (down from 52% current failure rate)
- NFR8: Zero frontend requests may hang indefinitely without timeout or error feedback
- NFR9: Entity extraction must clearly distinguish error states from empty results in 100% of cases

#### Observability

- NFR10: All reliability-related errors must be logged with sufficient context for debugging (user ID, matter ID, error type, timestamp)
- NFR11: Citation page fallback events must be countable in monitoring dashboards
- NFR12: SSE parse errors must be trackable per user session
- NFR13: WebSocket reconnection events must be trackable per hour/day
- NFR14: Support staff must be able to access reliability metrics without engineering involvement

### Additional Requirements

#### From Architecture Document

**Project Context:**
- Brownfield project — no starter template required; extending existing production system
- Existing tech stack must be preserved: FastAPI, Celery, Redis, Supabase (PostgreSQL), Next.js, TypeScript
- No database schema changes required — fixes use existing tables (`bounding_boxes`, `citations`, `events`)

**Implementation Patterns to Follow:**
- Follow existing error handling patterns in the codebase
- Use established logging patterns with structured context (user_id, matter_id, etc.)
- WebSocket and SSE implementations must follow existing real-time architecture
- Maintain consistency with existing API response formats

**Files Already Identified for Changes:**

Backend (Python/FastAPI):
- `date_extractor.py:256` — Timeline page detection logic
- `storage.py:156-161` — Citation storage with page info
- `generator.py:229-266` — "p. ?" citation bug fix
- `extractor.py:309-325` — Entity extraction error states
- `main.py:111-120` — WebSocket health check
- `pubsub_service.py` — Redis reconnect logic

Frontend (TypeScript/Next.js):
- `useSSE.ts:399` — SSE malformed JSON handling
- `apiClient.ts` — 30s timeout implementation
- `useWebSocket.ts` — Reconnection indicator UI
- Entity extraction components — Error vs empty state UI

**Monitoring Requirements:**
- Add structured log patterns: `sse_json_parse_failed`, `websocket_reconnection`, `citation_page_fallback`, `entity_extraction_failed`
- All logs must include: user_id, matter_id, timestamp, error_type, context

**Testing Approach:**
- Run before/after comparison on existing matters for page detection fix
- Test WebSocket reconnection with Redis health monitoring
- Test SSE error handling with malformed JSON payloads

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Bbox page detection for timeline events |
| FR2 | Epic 1 | Chunk-level fallback for page detection |
| FR3 | Epic 1 | Preview page number before clicking |
| FR4 | Epic 1 | Eliminate "p. ?" output |
| FR5 | Epic 1 | Log page detection fallbacks |
| FR6 | Epic 2 | SSE malformed JSON error notification |
| FR7 | Epic 2 | SSE parse failure visibility |
| FR8 | Epic 2 | Interrupted vs complete response clarity |
| FR9 | Epic 2 | SSE error logging with context |
| FR10 | Epic 3 | Entity extraction error vs empty states |
| FR11 | Epic 3 | Clear backend error messages |
| FR12 | Epic 3 | Actionable error guidance |
| FR13 | Epic 3 | Contextual error display |
| FR14 | Epic 4 | WebSocket disconnect detection |
| FR15 | Epic 4 | Automatic reconnection attempts |
| FR16 | Epic 4 | "Reconnecting..." indicator |
| FR17 | Epic 4 | Topic re-subscription on reconnect |
| FR18 | Epic 4 | Application usable during reconnect |
| FR19 | Epic 5 | Enforce max wait times |
| FR20 | Epic 5 | Slow request feedback |
| FR21 | Epic 5 | Timeout error message |
| FR22 | Epic 5 | Request cleanup on timeout |
| FR23 | Epic 6 | Citation accuracy metrics |
| FR24 | Epic 6 | SSE error rate monitoring |
| FR25 | Epic 6 | WebSocket health metrics |
| FR26 | Epic 6 | Entity extraction success rates |
| FR27 | Epic 6 | Comprehensive reliability logging |

## Epic List

### Epic 1: Accurate Citation Page Navigation

Users can click any timeline event or citation link and land directly on the correct source page where the referenced text appears.

**FRs covered:** FR1, FR2, FR3, FR4, FR5
**NFRs:** NFR4, NFR7
**User Journey:** Priya's citation accuracy journey
**Key Fix:** Timeline 48% → <5% wrong pages, "p. ?" elimination

---

### Epic 2: Complete & Reliable Chat Responses

Users receive complete chat responses, and when SSE parsing fails, they see clear error feedback instead of silent truncation.

**FRs covered:** FR6, FR7, FR8, FR9
**NFRs:** NFR6
**User Journey:** Amit's incomplete response journey
**Key Fix:** SSE malformed JSON handling with visible errors

---

### Epic 3: Clear Error States & Feedback

Users can clearly distinguish between "no results found" and "operation failed" states, with actionable next steps when errors occur.

**FRs covered:** FR10, FR11, FR12, FR13
**NFRs:** NFR9
**User Journey:** All users encountering errors
**Key Fix:** Entity extraction error vs empty state differentiation

---

### Epic 4: Resilient Real-time Updates

Users see reliable pipeline progress with automatic WebSocket reconnection and clear "Reconnecting..." indicators during brief disconnections.

**FRs covered:** FR14, FR15, FR16, FR17, FR18
**NFRs:** NFR2, NFR5
**User Journey:** Meera's frozen screen journey
**Key Fix:** WebSocket auto-reconnect with exponential backoff

---

### Epic 5: Bounded Request Handling

Users never experience frozen UI states — all requests have bounded wait times with clear timeout feedback.

**FRs covered:** FR19, FR20, FR21, FR22
**NFRs:** NFR1, NFR3, NFR8
**User Journey:** Meera's frozen screen journey
**Key Fix:** 30s frontend timeout with error feedback

---

### Epic 6: Reliability Monitoring & Diagnostics

Support staff can view dashboards showing citation accuracy, SSE errors, WebSocket health, and entity extraction rates without engineering involvement.

**FRs covered:** FR23, FR24, FR25, FR26, FR27
**NFRs:** NFR10, NFR11, NFR12, NFR13, NFR14
**User Journey:** Support staff diagnostic journey
**Key Fix:** Structured logging + monitoring dashboards

---

## Epic 1: Accurate Citation Page Navigation

Users can click any timeline event or citation link and land directly on the correct source page where the referenced text appears.

### Story 1.1: Fix Bounding Box Page Detection for Timeline Events

As a **legal professional**,
I want **timeline events to use the bounding box page number instead of chunk page number**,
So that **when I click a citation, I land on the exact page containing the referenced text**.

**Acceptance Criteria:**

**Given** a timeline event with associated bounding box data
**When** the system determines the source page for display
**Then** the page number from the bounding box is used (not the chunk's start page)
**And** the source_page field is correctly populated in the database

**Given** a document with bounding boxes spanning multiple pages
**When** events are extracted from different pages
**Then** each event's source_page matches its bounding box page

**Files:** `date_extractor.py:256`, `storage.py:156-161`
**Addresses:** FR1

---

### Story 1.2: Implement Chunk-Level Page Fallback with Logging

As a **legal professional**,
I want **the system to fall back to chunk page detection when bounding box data is unavailable**,
So that **I still get a reasonable page reference even when precise location isn't available**.

**Acceptance Criteria:**

**Given** a timeline event without bounding box data
**When** the system determines the source page
**Then** the chunk's page number is used as fallback
**And** a `citation_page_fallback` log event is recorded with matter_id and event details

**Given** the system uses fallback page detection
**When** logging the event
**Then** the log includes: user_id, matter_id, document_id, event_id, timestamp

**Files:** `date_extractor.py`, logging infrastructure
**Addresses:** FR2, FR5, NFR10, NFR11

---

### Story 1.3: Eliminate "p. ?" Citation Output

As a **legal professional**,
I want **citations to never display "p. ?" as a page reference**,
So that **all citations show actual, usable page numbers**.

**Acceptance Criteria:**

**Given** a citation being generated by the RAG system
**When** the page number cannot be determined
**Then** the citation omits the page reference entirely (not "p. ?")
**And** a fallback indicator is logged for monitoring

**Given** any response containing citations
**When** the response is post-processed
**Then** no "p. ?" text appears in the final output
**And** regex validation confirms zero occurrences

**Files:** `generator.py:229-266`
**Addresses:** FR4

---

### Story 1.4: Display Source Page in Citation UI

As a **legal professional**,
I want **to see the page number in citation links before clicking**,
So that **I can verify I'm going to the right location**.

**Acceptance Criteria:**

**Given** a citation displayed in the chat or timeline UI
**When** the citation has a valid source page
**Then** the page number is visible in the citation text (e.g., "Document X, p. 23")

**Given** a citation without a valid source page
**When** displayed in the UI
**Then** the citation shows only the document name without a misleading page number

**Files:** Frontend citation components
**Addresses:** FR3

---

## Epic 2: Complete & Reliable Chat Responses

Users receive complete chat responses, and when SSE parsing fails, they see clear error feedback instead of silent truncation.

### Story 2.1: Add SSE JSON Parse Error Handling

As a **legal professional**,
I want **the system to catch and handle malformed JSON in SSE streams**,
So that **I know when something went wrong instead of seeing a silently truncated response**.

**Acceptance Criteria:**

**Given** an SSE stream delivering chat response chunks
**When** a chunk contains malformed JSON
**Then** a try/catch wraps the JSON.parse call
**And** the error is captured instead of crashing silently

**Given** a JSON parse error occurs
**When** the error is caught
**Then** the malformed chunk content is logged to console for debugging
**And** processing continues with remaining valid chunks if possible

**Files:** `useSSE.ts:399`
**Addresses:** FR7, FR9

---

### Story 2.2: Display SSE Error Toast Notification

As a **legal professional**,
I want **to see a clear error notification when SSE parsing fails**,
So that **I understand my response may be incomplete and can retry**.

**Acceptance Criteria:**

**Given** an SSE JSON parse error is caught
**When** the error handler executes
**Then** an error toast appears within 500ms (NFR3)
**And** the toast message reads "Response interrupted — please retry"

**Given** the error toast is displayed
**When** the user views it
**Then** the toast includes a retry action button
**And** the toast auto-dismisses after 10 seconds if not acted upon

**Files:** `useSSE.ts`, toast notification system
**Addresses:** FR6, NFR3, NFR6

---

### Story 2.3: Add Response Completion Indicator

As a **legal professional**,
I want **to clearly see when a chat response has completed normally vs was interrupted**,
So that **I can trust that I'm seeing the full answer**.

**Acceptance Criteria:**

**Given** a chat response streaming via SSE
**When** the stream completes with a proper end signal
**Then** a subtle completion indicator appears (e.g., checkmark or "Complete")

**Given** a chat response is interrupted (error or timeout)
**When** the stream stops unexpectedly
**Then** an "Incomplete" indicator appears with the response
**And** a "Retry" option is prominently displayed

**Files:** Chat UI components, `useSSE.ts`
**Addresses:** FR8

---

### Story 2.4: Implement SSE Error Logging with Context

As a **support staff member**,
I want **SSE parse errors to be logged with full context**,
So that **I can diagnose patterns and identify problematic responses**.

**Acceptance Criteria:**

**Given** an SSE parse error occurs
**When** the error is logged
**Then** the log includes: user_id, matter_id, session_id, timestamp, error_type
**And** the log includes the raw malformed chunk (truncated if >1KB)

**Given** multiple SSE errors occur in a session
**When** viewing logs
**Then** errors are trackable per user session (NFR12)

**Files:** `useSSE.ts`, logging infrastructure
**Addresses:** FR9, NFR10, NFR12

---

## Epic 3: Clear Error States & Feedback

Users can clearly distinguish between "no results found" and "operation failed" states, with actionable next steps when errors occur.

### Story 3.1: Distinguish Entity Extraction Error vs Empty States

As a **legal professional**,
I want **to clearly see whether entity extraction found nothing vs failed entirely**,
So that **I know whether to retry or accept that there are no entities**.

**Acceptance Criteria:**

**Given** entity extraction completes successfully with no entities found
**When** the UI displays results
**Then** the message reads "No entities found in this document"
**And** no error styling is applied

**Given** entity extraction fails due to an error
**When** the UI displays the state
**Then** the message reads "Entity extraction failed — please retry"
**And** error styling (red/warning) is applied
**And** a retry button is displayed

**Files:** `extractor.py:309-325`, Entity extraction UI components
**Addresses:** FR10, NFR9

---

### Story 3.2: Update Backend to Return Distinct Error States

As a **frontend developer**,
I want **the backend to return distinct response types for empty results vs errors**,
So that **the UI can display appropriate feedback**.

**Acceptance Criteria:**

**Given** entity extraction completes with no entities
**When** the API responds
**Then** the response includes `status: "success"` and `entities: []`

**Given** entity extraction fails
**When** the API responds
**Then** the response includes `status: "error"` and `error_message: "<reason>"`
**And** the HTTP status code is appropriate (200 for empty, 500/502 for error)

**Files:** `extractor.py:309-325`, API response models
**Addresses:** FR10, FR11

---

### Story 3.3: Display Actionable Error Messages

As a **legal professional**,
I want **error messages to tell me what to do next**,
So that **I'm not stuck wondering how to proceed**.

**Acceptance Criteria:**

**Given** any backend operation fails
**When** the error is displayed to the user
**Then** the message includes: what failed, why (if known), and what to do next

**Given** a retryable error (e.g., timeout, temporary failure)
**When** displayed
**Then** the message includes "Try again" as the suggested action
**And** a retry button is provided

**Given** a non-retryable error (e.g., document not found)
**When** displayed
**Then** the message explains why retry won't help
**And** suggests an alternative action (e.g., "Contact support")

**Files:** Error message components, error handling utilities
**Addresses:** FR12, FR13

---

### Story 3.4: Implement Contextual Error Display Component

As a **frontend developer**,
I want **a reusable error display component with consistent styling**,
So that **all errors across the app look and behave consistently**.

**Acceptance Criteria:**

**Given** an error needs to be displayed anywhere in the app
**When** using the ErrorDisplay component
**Then** it accepts: error_type, message, suggested_action, retry_callback (optional)
**And** it renders with consistent error styling

**Given** the ErrorDisplay component is used
**When** a retry_callback is provided
**Then** a "Retry" button is displayed
**And** clicking it invokes the callback

**Files:** New ErrorDisplay component, integration across app
**Addresses:** FR13

---

## Epic 4: Resilient Real-time Updates

Users see reliable pipeline progress with automatic WebSocket reconnection and clear "Reconnecting..." indicators during brief disconnections.

### Story 4.1: Detect WebSocket Connection Loss

As a **paralegal**,
I want **the system to detect when my WebSocket connection is lost**,
So that **reconnection can be attempted automatically**.

**Acceptance Criteria:**

**Given** an active WebSocket connection
**When** the connection is lost (network issue, server restart)
**Then** the disconnect is detected within 1 second (NFR2)
**And** the connection state is updated to "disconnected"

**Given** no messages received for 30 seconds
**When** the heartbeat timeout fires
**Then** the connection is considered lost
**And** reconnection logic is triggered

**Files:** `useWebSocket.ts`, `main.py:111-120`
**Addresses:** FR14, NFR2

---

### Story 4.2: Implement Automatic WebSocket Reconnection

As a **paralegal**,
I want **the WebSocket to automatically reconnect when disconnected**,
So that **I don't have to manually refresh the page**.

**Acceptance Criteria:**

**Given** a WebSocket disconnect is detected
**When** reconnection begins
**Then** the first attempt occurs within 1 second
**And** subsequent attempts use exponential backoff: 1s → 2s → 4s → 8s → max 30s (NFR5)

**Given** reconnection succeeds
**When** the connection is restored
**Then** the connection state updates to "connected"
**And** normal operation resumes

**Given** reconnection fails after max attempts
**When** all retries are exhausted
**Then** the user sees "Connection lost — please refresh" message

**Files:** `useWebSocket.ts`
**Addresses:** FR15, NFR5

---

### Story 4.3: Display "Reconnecting..." Indicator

As a **paralegal**,
I want **to see a "Reconnecting..." indicator when WebSocket is disconnected**,
So that **I know the system is trying to restore the connection**.

**Acceptance Criteria:**

**Given** a WebSocket disconnect is detected
**When** reconnection attempts begin
**Then** a "Reconnecting..." indicator appears in the UI
**And** the indicator shows attempt count (e.g., "Reconnecting... (attempt 2/5)")

**Given** reconnection succeeds
**When** the connection is restored
**Then** the indicator disappears
**And** a brief "Connected" confirmation appears

**Files:** `useWebSocket.ts`, connection status UI component
**Addresses:** FR16

---

### Story 4.4: Re-subscribe to Topics After Reconnection

As a **paralegal**,
I want **the system to re-subscribe to my matter's topics after reconnection**,
So that **I continue receiving real-time updates**.

**Acceptance Criteria:**

**Given** a WebSocket reconnection succeeds
**When** the connection is restored
**Then** the system automatically re-subscribes to previously subscribed topics
**And** the current matter's topic is included

**Given** re-subscription completes
**When** new events occur for the matter
**Then** the user receives them normally

**Files:** `useWebSocket.ts`, `pubsub_service.py`
**Addresses:** FR17

---

### Story 4.5: Maintain Application Usability During Reconnection

As a **paralegal**,
I want **to continue using the application while WebSocket reconnects**,
So that **I'm not blocked from working**.

**Acceptance Criteria:**

**Given** a WebSocket is in reconnecting state
**When** the user interacts with the application
**Then** all non-realtime features remain functional
**And** the user can navigate, view documents, and use chat (with polling fallback if needed)

**Given** real-time features are unavailable during reconnection
**When** the user triggers a real-time action
**Then** a message indicates "Real-time updates temporarily unavailable"
**And** the action is queued or retried after reconnection

**Files:** `useWebSocket.ts`, application state management
**Addresses:** FR18

---

## Epic 5: Bounded Request Handling

Users never experience frozen UI states — all requests have bounded wait times with clear timeout feedback.

### Story 5.1: Add Global Fetch Timeout

As a **legal professional**,
I want **all API requests to have a maximum wait time**,
So that **the UI never hangs indefinitely**.

**Acceptance Criteria:**

**Given** any frontend API request
**When** the request is made
**Then** a 30-second timeout is enforced (NFR1)
**And** the timeout applies to all fetch calls via the API client

**Given** a request takes longer than 30 seconds
**When** the timeout fires
**Then** the request is aborted
**And** an AbortController is used to properly cancel the request

**Files:** `apiClient.ts`
**Addresses:** FR19, NFR1, NFR8

---

### Story 5.2: Display Slow Request Feedback

As a **legal professional**,
I want **to see feedback when a request is taking longer than expected**,
So that **I know the system is still working**.

**Acceptance Criteria:**

**Given** a request has been pending for more than 5 seconds
**When** the slow threshold is reached
**Then** a subtle "Still loading..." indicator appears
**And** a progress spinner or animation is shown

**Given** the request completes after showing slow feedback
**When** the response arrives
**Then** the slow indicator disappears
**And** the normal result is displayed

**Files:** `apiClient.ts`, loading indicator components
**Addresses:** FR20

---

### Story 5.3: Display Timeout Error Message

As a **legal professional**,
I want **to see a clear error when a request times out**,
So that **I understand what happened and can retry**.

**Acceptance Criteria:**

**Given** a request is aborted due to timeout
**When** the timeout error is handled
**Then** an error toast appears within 500ms (NFR3)
**And** the message reads "Request timed out — please try again"

**Given** a timeout error toast is displayed
**When** the user views it
**Then** a "Retry" button is available
**And** clicking retry re-initiates the original request

**Files:** `apiClient.ts`, error toast system
**Addresses:** FR21, NFR3

---

### Story 5.4: Implement Request Cleanup on Timeout

As a **frontend developer**,
I want **timed-out requests to be properly cleaned up**,
So that **there are no memory leaks or orphaned promises**.

**Acceptance Criteria:**

**Given** a request times out
**When** the AbortController aborts the request
**Then** the fetch promise is properly rejected
**And** any pending state is cleaned up

**Given** multiple requests are in flight
**When** one times out
**Then** other requests are unaffected
**And** each request has its own AbortController

**Files:** `apiClient.ts`
**Addresses:** FR22

---

## Epic 6: Reliability Monitoring & Diagnostics

Support staff can view dashboards showing citation accuracy, SSE errors, WebSocket health, and entity extraction rates without engineering involvement.

### Story 6.1: Add Citation Page Accuracy Logging

As a **support staff member**,
I want **citation page detection events to be logged with metrics**,
So that **I can track citation accuracy per matter**.

**Acceptance Criteria:**

**Given** a citation page is determined (bbox or fallback)
**When** the event is logged
**Then** the log includes: matter_id, document_id, detection_method (bbox/chunk), page_number

**Given** citation events are logged
**When** querying logs
**Then** citation accuracy can be calculated: `COUNT(bbox) / COUNT(*)` per matter

**Files:** Backend logging infrastructure
**Addresses:** FR23, NFR10, NFR11

---

### Story 6.2: Add SSE Error Rate Logging

As a **support staff member**,
I want **SSE parse errors to be logged with session tracking**,
So that **I can identify problematic sessions and error patterns**.

**Acceptance Criteria:**

**Given** an SSE parse error occurs
**When** the error is logged
**Then** the log includes: session_id, user_id, matter_id, error_type, timestamp

**Given** SSE errors are logged
**When** querying logs
**Then** error rate can be calculated per session and per hour

**Files:** Frontend logging, backend log aggregation
**Addresses:** FR24, NFR12

---

### Story 6.3: Add WebSocket Health Metrics Logging

As a **support staff member**,
I want **WebSocket reconnection events to be logged**,
So that **I can monitor connection health and identify infrastructure issues**.

**Acceptance Criteria:**

**Given** a WebSocket reconnection occurs
**When** the event is logged
**Then** the log includes: user_id, session_id, reconnect_reason, attempt_count, success/failure

**Given** WebSocket events are logged
**When** querying logs
**Then** reconnection rate can be calculated per hour/day (NFR13)

**Files:** `useWebSocket.ts`, logging infrastructure
**Addresses:** FR25, NFR13

---

### Story 6.4: Add Entity Extraction Success Rate Logging

As a **support staff member**,
I want **entity extraction outcomes to be logged**,
So that **I can track success vs failure rates**.

**Acceptance Criteria:**

**Given** entity extraction completes (success or failure)
**When** the outcome is logged
**Then** the log includes: matter_id, document_id, status (success/error/empty), entity_count, error_message (if applicable)

**Given** extraction events are logged
**When** querying logs
**Then** success rate can be calculated: `COUNT(success) / COUNT(*)` per time period

**Files:** `extractor.py`, logging infrastructure
**Addresses:** FR26

---

### Story 6.5: Implement Comprehensive Reliability Event Logging

As a **support staff member**,
I want **all reliability events to follow a consistent logging format**,
So that **I can query and analyze them together**.

**Acceptance Criteria:**

**Given** any reliability event occurs (citation, SSE, WebSocket, entity, timeout)
**When** the event is logged
**Then** the log follows a consistent schema: event_type, user_id, matter_id, timestamp, details (JSON)

**Given** logs are written
**When** support staff queries them
**Then** they can filter by event_type, user_id, matter_id, time range
**And** no engineering involvement is required (NFR14)

**Files:** Logging infrastructure, log query documentation
**Addresses:** FR27, NFR10, NFR14
