# Story 13.1: Implement Axiom Logging Integration

Status: done

## Story

As a **developer**,
I want **structured logging sent to Axiom**,
So that **I can monitor and debug production issues**.

## Acceptance Criteria

1. **Given** the application is running
   **When** log events occur
   **Then** structured JSON logs are sent to Axiom
   **And** logs include: timestamp, level, message, correlation_id, user_id, matter_id

2. **Given** an API request is processed
   **When** logging occurs
   **Then** a correlation_id is assigned
   **And** all related logs share this ID for tracing

3. **Given** logs are in Axiom
   **When** I query them
   **Then** hot storage provides 30 days of data
   **And** cold storage retains 1 year

## Tasks / Subtasks

- [x] Task 1: Install and configure axiom-py SDK (AC: #1, #2)
  - [x] 1.1 Add `axiom-py` to backend/pyproject.toml dependencies
  - [x] 1.2 Add AXIOM_TOKEN and AXIOM_DATASET to Settings class in config.py
  - [x] 1.3 Add environment variables to .env.example

- [x] Task 2: Create AxiomProcessor integration for structlog (AC: #1)
  - [x] 2.1 Update logging.py to conditionally add AxiomProcessor in production
  - [x] 2.2 Ensure JSON output is preserved for local development
  - [x] 2.3 Add graceful fallback if Axiom not configured

- [x] Task 3: Implement correlation_id middleware (AC: #2)
  - [x] 3.1 Create middleware to generate/extract correlation_id per request
  - [x] 3.2 Use structlog.contextvars to bind correlation_id to all logs in request
  - [x] 3.3 Propagate correlation_id to response headers (X-Correlation-ID)

- [x] Task 4: Enhance log context with user and matter data (AC: #1)
  - [x] 4.1 Add user_id binding after authentication in security.py
  - [x] 4.2 Add matter_id binding when matter access is validated
  - [x] 4.3 Ensure sensitive data is not logged (tokens, passwords)

- [x] Task 5: Write tests for logging infrastructure (AC: #1, #2)
  - [x] 5.1 Test correlation_id propagation across async calls
  - [x] 5.2 Test log context includes required fields
  - [x] 5.3 Test graceful degradation when Axiom unavailable
  - [x] 5.4 Test no sensitive data leakage in logs

## Dev Notes

### Existing Infrastructure

The project already has structured logging configured with structlog. Key files:

- **[logging.py](backend/app/core/logging.py)**: Configures structlog with JSON output in production, console in dev
- **[config.py](backend/app/core/config.py)**: Pydantic Settings for environment variables
- **[main.py](backend/app/main.py)**: Application entry, calls `configure_logging()` on startup
- **[deps.py](backend/app/api/deps.py)**: Contains `get_current_user` and `validate_matter_access` for binding context

### Current structlog Configuration (logging.py:27-57)

```python
shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,  # <-- Already uses contextvars!
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]
```

The `merge_contextvars` processor is already in place - this is critical for propagating correlation_id across async calls.

### Axiom Integration Pattern

Install axiom-py and use its AxiomProcessor:

```python
# In logging.py
from axiom_py import Client
from axiom_py.structlog import AxiomProcessor

# Add to production processors BEFORE JSONRenderer
if settings.axiom_token:
    axiom_client = Client(settings.axiom_token)
    processors.insert(-1, AxiomProcessor(axiom_client, settings.axiom_dataset))
```

### Correlation ID Middleware Pattern

Create middleware that binds correlation_id early in the request lifecycle:

```python
# In new file: backend/app/core/correlation.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Extract from header or generate new
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Bind to structlog contextvars
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)

        # Include in response for client-side correlation
        response.headers["X-Correlation-ID"] = correlation_id

        # Clear context after request
        structlog.contextvars.unbind_contextvars("correlation_id")

        return response
```

### User/Matter Context Binding

Extend existing deps.py patterns to bind context:

```python
# In deps.py after authentication
async def get_current_user_with_logging(...) -> AuthenticatedUser:
    user = await get_current_user(...)
    structlog.contextvars.bind_contextvars(user_id=user.id, user_email=user.email)
    return user

# In validate_matter_access after access granted
structlog.contextvars.bind_contextvars(matter_id=matter_id)
```

### Sensitive Data Protection

The project-context.md explicitly prohibits logging sensitive data. Ensure:

- Never log `authorization` header values
- Never log full JWT tokens
- Redact email addresses in high-volume logs (keep first 3 chars + domain)
- Never log password fields

### Project Structure Notes

Following project conventions from project-context.md:

| New File | Location | Purpose |
|----------|----------|---------|
| correlation.py | backend/app/core/ | Correlation ID middleware |
| test_logging.py | backend/tests/core/ | Logging infrastructure tests |

No new directories needed - all files fit existing structure.

### Configuration Variables (config.py)

```python
# Add to Settings class
axiom_token: str = ""  # AXIOM_TOKEN env var
axiom_dataset: str = "ldip-logs"  # AXIOM_DATASET env var
```

### Async Logging Considerations

Per Axiom documentation, their SDK uses blocking urllib. For production resilience:

1. Configure AxiomProcessor with reasonable buffer sizes
2. Consider adding a QueueHandler for high-throughput scenarios (future optimization)
3. Ensure graceful degradation if Axiom is unreachable

### Test Strategy

1. **Unit tests**: Mock axiom-py client, verify log payloads contain required fields
2. **Integration tests**: Verify correlation_id propagates through async chains
3. **Security tests**: Verify sensitive data is not logged (scan for patterns like "password", "token", "secret")

### References

- [Source: architecture.md#Observability] Axiom with 30 days hot, 1 year cold retention
- [Source: project-context.md#Python] Use `structlog` not standard logging library
- [Source: epics.md#Epic-13] Story 13.1 requirements for structured JSON logs
- [Axiom Python SDK Documentation](https://axiom.co/docs/guides/python)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed without major issues.

### Completion Notes List

1. **Task 1**: Added `axiom-py>=1.1.0` to pyproject.toml, added `axiom_token` and `axiom_dataset` settings to config.py, updated .env.example with Axiom configuration variables.

2. **Task 2**: Updated logging.py with `_get_axiom_processor()` function that lazily initializes the Axiom client and returns an AxiomProcessor. Added graceful fallback when Axiom token is not configured or client initialization fails. In production mode, AxiomProcessor is added before JSONRenderer.

3. **Task 3**: Created new correlation.py module with CorrelationMiddleware that:
   - Generates UUID if X-Correlation-ID header not present
   - Binds correlation_id to structlog contextvars for all logs in request
   - Returns correlation_id in response headers
   - Clears context after request to prevent leakage
   - Added middleware to main.py after CORS, exposed X-Correlation-ID header in CORS config

4. **Task 4**: Added user_id binding in security.py after successful JWT validation. Added matter_id binding in deps.py in all three matter access validation functions (require_matter_role, require_matter_role_from_form, validate_matter_access).

5. **Task 5**: Created comprehensive test suite with 19 tests covering:
   - CorrelationMiddleware (generates ID, uses existing ID, propagates across async, clears after request)
   - get_correlation_id helper function
   - Logging configuration (dev mode, prod mode without Axiom)
   - Axiom processor graceful degradation (not configured, import fails, client fails)
   - Log context (correlation_id, user_id, matter_id included)
   - Sensitive data protection (no auth headers, passwords, or JWT tokens logged)
   - get_logger helper function

### File List

**New Files:**
- backend/app/core/correlation.py (Correlation ID middleware)
- backend/tests/core/test_logging.py (19 logging infrastructure tests)

**Modified Files:**
- backend/pyproject.toml (added axiom-py dependency)
- backend/app/core/config.py (added axiom_token, axiom_dataset settings)
- backend/app/core/logging.py (added Axiom processor integration with graceful fallback)
- backend/app/core/security.py (added user_id binding to log context)
- backend/app/api/deps.py (added matter_id binding to log context in 3 functions)
- backend/app/main.py (added CorrelationMiddleware, exposed X-Correlation-ID in CORS)
- backend/.env.example (added AXIOM_TOKEN, AXIOM_DATASET variables)

## Manual Steps Required

### Environment Variables
- [ ] Add to `backend/.env`: `AXIOM_TOKEN=xaat-your-api-token` (from: [Axiom Dashboard](https://axiom.co) → Settings → API Tokens)
- [ ] Add to `backend/.env`: `AXIOM_DATASET=ldip-logs` (or your preferred dataset name)

### Dashboard Configuration
- [ ] Axiom: Create dataset `ldip-logs` in Axiom dashboard if it doesn't exist
- [ ] Axiom: Configure retention policy - 30 days hot storage, 1 year cold storage (per AC#3)

### Manual Tests
- [ ] Test: Start backend with `DEBUG=false` and `AXIOM_TOKEN` set, verify logs appear in Axiom dashboard
- [ ] Test: Make API request without X-Correlation-ID header, verify response includes generated UUID in X-Correlation-ID
- [ ] Test: Make API request with X-Correlation-ID header, verify same ID appears in response and logs
- [ ] Test: Make authenticated request, verify user_id appears in log context in Axiom
- [ ] Test: Access a matter endpoint, verify matter_id appears in log context in Axiom

## Change Log

- 2026-01-16: Code review fixes - Fixed 4 ruff linting errors (B904 exception chaining), removed debug print statements, added Manual Steps Required section.
- 2026-01-16: Story completed - Implemented Axiom logging integration with correlation ID middleware, user/matter context binding, and graceful degradation. 19 tests added and passing.
