# Story 1.4: Implement JWT Token Handling and Session Management

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **my authentication session to persist and automatically refresh**,
So that **I don't have to log in repeatedly during my work session**.

## Acceptance Criteria

1. **Given** I am logged in with a valid JWT token, **When** I make API requests to the FastAPI backend, **Then** the JWT token is included in the Authorization header **And** the backend validates and authenticates the request successfully

2. **Given** my JWT token is about to expire (within 5 minutes), **When** I make an API request, **Then** the token is automatically refreshed using the refresh token from Supabase **And** the new token is stored via cookies

3. **Given** my refresh token has expired (after 7 days), **When** I make an API request, **Then** I am redirected to the login page **And** a message indicates my session has expired

4. **Given** I click "Logout", **When** the logout action completes, **Then** my session is invalidated on both frontend and backend **And** my tokens are cleared from cookies **And** I am redirected to the login page

5. **Given** the FastAPI backend receives a request with a JWT token, **When** the token is valid and not expired, **Then** the user information is extracted from the JWT claims **And** the request proceeds with the authenticated user context

6. **Given** the FastAPI backend receives a request with an invalid or expired JWT, **When** the validation fails, **Then** a 401 Unauthorized response is returned **And** the error follows the standard API error format

## Tasks / Subtasks

- [x] Task 1: Install PyJWT for backend JWT validation (AC: #5, #6)
  - [x] Add `PyJWT>=2.8.0` to backend dependencies in pyproject.toml
  - [x] Run `uv sync` to install the dependency
  - [x] Verify PyJWT import works in Python

- [x] Task 2: Add Supabase JWT secret to backend configuration (AC: #5, #6)
  - [x] Add `SUPABASE_JWT_SECRET` to `app/core/config.py` Settings class
  - [x] Add the variable to `.env.example` with clear documentation
  - [x] Document where to find JWT secret (Supabase Dashboard -> Settings -> API -> JWT Settings)

- [x] Task 3: Implement JWT validation in backend security module (AC: #5, #6)
  - [x] Update `app/core/security.py` with full JWT validation using PyJWT
  - [x] Decode JWT with HS256 algorithm and audience="authenticated"
  - [x] Extract user claims: `sub` (user_id), `email`, `role`, `exp`, `iat`
  - [x] Handle PyJWTError exceptions with proper 401 responses
  - [x] Return typed user dictionary with extracted claims
  - [x] Use structlog for logging validation events (success/failure)

- [x] Task 4: Create user type models for JWT claims (AC: #5)
  - [x] Create `app/models/auth.py` with Pydantic models
  - [x] Define `JWTClaims` model matching Supabase JWT structure
  - [x] Define `AuthenticatedUser` model for dependency return type
  - [x] Ensure models use snake_case for Python, match camelCase in JWT

- [x] Task 5: Create frontend API client with auth interceptor (AC: #1, #2)
  - [x] Create `src/lib/api/client.ts` with fetch wrapper
  - [x] Add Authorization header injection using Supabase session
  - [x] Implement token refresh on 401 response (retry with fresh token)
  - [x] Configure base URL from environment variable `NEXT_PUBLIC_API_URL`
  - [x] Add request/response logging in development mode

- [x] Task 6: Create frontend auth hooks (AC: #1, #2, #3)
  - [x] Create `src/hooks/useAuth.ts` for auth state management
  - [x] Implement `useSession` hook to get current session with auto-refresh
  - [x] Implement `useUser` hook to get current user data
  - [x] Handle session expiration and redirect to login
  - [x] Use Supabase's `onAuthStateChange` for real-time session updates

- [x] Task 7: Update logout to work with backend (AC: #4)
  - [x] Update `src/app/auth/logout/route.ts` to clear all session data
  - [x] Ensure cookies are cleared properly on both domains
  - [x] Add optional backend logout endpoint for session audit logging

- [x] Task 8: Add session expiry handling in middleware (AC: #2, #3)
  - [x] Update `src/middleware.ts` to detect near-expiry tokens
  - [x] Trigger token refresh when token expires within 5 minutes
  - [x] Redirect to login with `session_expired=true` query param on failure
  - [x] Display session expired message on login page when redirected

- [x] Task 9: Create FastAPI protected route decorator/dependency (AC: #5, #6)
  - [x] Create `app/api/deps.py` with `get_current_user` dependency (update existing)
  - [x] Create `get_optional_user` for routes that support anonymous access
  - [x] Create `require_role` dependency for role-based access control (future use)
  - [x] Add proper type hints using AuthenticatedUser model

- [x] Task 10: Write backend tests for JWT validation (AC: #5, #6)
  - [x] Create `tests/core/test_security.py`
  - [x] Test valid JWT token decoding extracts correct claims
  - [x] Test expired JWT token returns 401
  - [x] Test invalid signature JWT returns 401
  - [x] Test missing token returns 401
  - [x] Test malformed token returns 401
  - [x] Mock JWT secret for tests

- [x] Task 11: Write frontend tests for auth hooks (AC: #1, #2)
  - [x] Create `src/hooks/useAuth.test.ts`
  - [x] Test useSession returns current session
  - [x] Test useUser returns current user
  - [x] Test session refresh on expiry
  - [x] Mock Supabase client for tests

- [x] Task 12: Create integration test for full auth flow (AC: #1-6)
  - [x] Create `tests/api/test_auth_integration.py`
  - [x] Test authenticated request to protected endpoint
  - [x] Test unauthenticated request returns 401
  - [x] Test token in Authorization header is validated

## Dev Notes

### Critical Architecture Constraints

**FROM ARCHITECTURE DOCUMENT - MUST FOLLOW EXACTLY:**

#### Authentication Session Configuration
| Feature | Implementation |
|---------|----------------|
| Session | JWT with 1-hour access token, 7-day refresh token |
| Storage | Supabase handles token storage via HTTP-only cookies |
| Validation | Backend validates JWT locally using PyJWT (NOT Supabase API call) |
| Algorithm | HS256 with Supabase JWT secret |

#### JWT Token Structure (Supabase)
```json
{
  "aud": "authenticated",
  "exp": 1704067200,
  "iat": 1704063600,
  "iss": "https://<project-ref>.supabase.co/auth/v1",
  "sub": "user-uuid-here",
  "email": "user@example.com",
  "phone": "",
  "app_metadata": { "provider": "google", "providers": ["google"] },
  "user_metadata": { "full_name": "John Doe", "avatar_url": "..." },
  "role": "authenticated",
  "aal": "aal1",
  "amr": [{ "method": "oauth", "timestamp": 1704063600 }],
  "session_id": "session-uuid-here"
}
```

#### Backend JWT Validation Pattern (REQUIRED)
```python
# app/core/security.py
import jwt
from jwt.exceptions import PyJWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing authentication token", "details": {}}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return AuthenticatedUser(
            id=payload["sub"],
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
            session_id=payload.get("session_id"),
        )
    except PyJWTError as e:
        logger.warning("jwt_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token", "details": {}}},
            headers={"WWW-Authenticate": "Bearer"},
        )
```

#### Frontend API Client Pattern (REQUIRED)
```typescript
// src/lib/api/client.ts
import { createClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');

  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 - try refresh and retry once
  if (response.status === 401 && session) {
    const { data: { session: newSession } } = await supabase.auth.refreshSession();
    if (newSession?.access_token) {
      headers.set('Authorization', `Bearer ${newSession.access_token}`);
      const retryResponse = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
      });
      if (!retryResponse.ok) {
        const error = await retryResponse.json();
        throw new ApiError(error.error.code, error.error.message, retryResponse.status);
      }
      return retryResponse.json();
    }
    // Refresh failed - redirect to login
    window.location.href = '/login?session_expired=true';
    throw new Error('Session expired');
  }

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(error.error.code, error.error.message, response.status);
  }

  return response.json();
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
```

#### useAuth Hook Pattern (REQUIRED)
```typescript
// src/hooks/useAuth.ts
'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { User, Session } from '@supabase/supabase-js';

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();

    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  return { session, loading };
}

export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  return { user, loading };
}
```

### Naming Conventions (CRITICAL - Must Follow)

| Element | Convention | Example |
|---------|------------|---------|
| Python models | PascalCase | `AuthenticatedUser`, `JWTClaims` |
| Python functions | snake_case | `get_current_user`, `validate_token` |
| TypeScript hooks | camelCase with `use` | `useSession`, `useAuth` |
| TypeScript functions | camelCase | `apiClient`, `refreshToken` |
| API error codes | SCREAMING_SNAKE | `INVALID_TOKEN`, `UNAUTHORIZED` |

### Technology Stack - JWT Specific

| Technology | Version | Notes |
|------------|---------|-------|
| PyJWT | >=2.8.0 | JWT decoding and validation |
| @supabase/ssr | Already installed | Token refresh via cookies |
| @supabase/supabase-js | Already installed | Auth state management |

### Required Environment Variables

**Backend (.env):**
```
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard
```

**Frontend (.env.local):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Where to find JWT Secret:**
1. Go to Supabase Dashboard
2. Navigate to Settings -> API
3. Find "JWT Settings" section
4. Copy the "JWT Secret" value
5. NEVER expose this in frontend code

### Previous Story Intelligence

**From Story 1-3 (Supabase Auth):**
- Supabase SSR auth implemented with `@supabase/ssr`
- Server client at `src/lib/supabase/server.ts` uses cookie-based sessions
- Browser client at `src/lib/supabase/client.ts` for client components
- Middleware at `src/middleware.ts` validates sessions using `getUser()`
- Users table with RLS policies created
- Logout route at `src/app/auth/logout/route.ts` already exists

**From Story 1-2 (Backend):**
- Security module at `app/core/security.py` has placeholder `get_current_user`
- Settings at `app/core/config.py` uses Pydantic Settings
- Supabase client already installed (`supabase>=2.27.0`)
- structlog configured for logging

**Key Patterns Established:**
- Error responses use `{"error": {"code": "...", "message": "...", "details": {}}}`
- Protected routes use FastAPI `Depends()` pattern
- 23 auth tests exist for frontend (LoginForm, SignupForm, LogoutButton)

### Security Considerations (MANDATORY)

1. **Local JWT validation is preferred** - Avoids 600ms latency of Supabase API call per request
2. **audience="authenticated"** - MUST validate audience claim to prevent token confusion
3. **HS256 algorithm** - Supabase uses symmetric key, not RSA
4. **Token refresh** - Frontend handles automatic refresh; backend just validates
5. **Never log tokens** - Log token metadata only (length, expiry), never the actual token
6. **Secure JWT secret** - Treat like a password, never commit to code

### Anti-Patterns to AVOID

```python
# WRONG: Using Supabase client for validation (600ms per request)
supabase_client.auth.get_user(token)  # DON'T DO THIS

# WRONG: Not validating audience
jwt.decode(token, secret, algorithms=["HS256"])  # Missing audience!

# WRONG: Logging the actual token
logger.info("Received token", token=token)  # SECURITY RISK!

# WRONG: Catching generic Exception
except Exception as e:  # Too broad, use PyJWTError

# WRONG: Returning raw error details
raise HTTPException(detail=str(e))  # Use structured error format
```

```typescript
// WRONG: Storing tokens in localStorage
localStorage.setItem('access_token', session.access_token);  // Use cookies!

// WRONG: Not handling 401 responses
const data = await fetch('/api/endpoint');  // No auth retry logic

// WRONG: Hardcoding API URL
const response = await fetch('http://localhost:8000/api/...');  // Use env var
```

### File Structure for JWT Feature

```
frontend/
├── src/
│   ├── lib/
│   │   └── api/
│   │       ├── client.ts           # API client with auth
│   │       └── types.ts            # API response types
│   ├── hooks/
│   │   ├── useAuth.ts              # Auth hooks (useSession, useUser)
│   │   └── useAuth.test.ts         # Hook tests
│   └── app/
│       └── (auth)/
│           └── login/
│               └── page.tsx        # Update for session_expired message

backend/
├── app/
│   ├── core/
│   │   ├── config.py               # Add SUPABASE_JWT_SECRET
│   │   └── security.py             # Update with real JWT validation
│   ├── models/
│   │   └── auth.py                 # JWTClaims, AuthenticatedUser models
│   └── api/
│       └── deps.py                 # Update get_current_user
└── tests/
    ├── core/
    │   └── test_security.py        # JWT validation tests
    └── api/
        └── test_auth_integration.py # Full auth flow tests
```

### Testing Guidance

**Backend JWT Tests (pytest):**
```python
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from app.core.security import get_current_user

@pytest.fixture
def valid_token(settings):
    payload = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")

@pytest.fixture
def expired_token(settings):
    payload = {
        "sub": "test-user-id",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")

async def test_valid_token_returns_user(valid_token, settings):
    # Test implementation
    pass

async def test_expired_token_raises_401(expired_token, settings):
    # Test implementation
    pass
```

**Frontend Hook Tests (vitest):**
```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useSession, useUser } from './useAuth';
import { vi } from 'vitest';

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-token', user: { id: 'test-id' } } }
      }),
      getUser: vi.fn().mockResolvedValue({
        data: { user: { id: 'test-id', email: 'test@example.com' } }
      }),
      onAuthStateChange: vi.fn().mockReturnValue({
        data: { subscription: { unsubscribe: vi.fn() } }
      }),
    },
  }),
}));

test('useSession returns session', async () => {
  const { result } = renderHook(() => useSession());
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.session).toBeDefined();
});
```

### References

- [Source: _bmad-output/architecture.md#Authentication-Authorization]
- [Source: _bmad-output/architecture.md#API-Communication-Patterns]
- [Source: _bmad-output/project-context.md#Language-Specific-Rules]
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-1.4]
- [Supabase Docs: JWTs](https://supabase.com/docs/guides/auth/jwts)
- [FastAPI Docs: OAuth2 JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [DEV: Validating Supabase JWT with FastAPI](https://dev.to/zwx00/validating-a-supabase-jwt-locally-with-python-and-fastapi-59jf)

### IMPORTANT: Always Check These Files

- **PRD/Requirements:** `_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md`
- **UX Decisions:** `_bmad-output/project-planning-artifacts/UX-Decisions-Log.md`
- **Architecture:** `_bmad-output/architecture.md`
- **Project Context:** `_bmad-output/project-context.md`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 26 backend tests passing (11 security tests + 11 integration tests + 4 health tests)
- All 35 frontend tests passing (12 auth hook tests + 23 existing auth tests)

### Completion Notes List

- Implemented full JWT validation using PyJWT with HS256 algorithm and audience validation
- Created AuthenticatedUser and JWTClaims Pydantic models for type-safe JWT handling
- Frontend API client with automatic token injection and 401 retry with refresh
- Auth hooks (useSession, useUser, useAuth, useAuthActions) with real-time state updates
- Middleware handles proactive token refresh when expires within 5 minutes
- Session expired message displayed on login page via query parameter
- Added protected `/api/health/me` endpoint for auth testing
- Created require_role dependency factory for future role-based access control

### Change Log

| Date | Change |
|------|--------|
| 2026-01-05 | Implemented all 12 tasks for JWT token handling and session management |

### File List

**Backend (modified):**
- backend/pyproject.toml - Added PyJWT>=2.8.0 dependency
- backend/app/core/config.py - Added supabase_jwt_secret configuration
- backend/app/core/security.py - Full JWT validation implementation
- backend/app/api/deps.py - Added require_role dependency
- backend/app/api/routes/health.py - Added protected /me endpoint
- backend/.env.example - Added SUPABASE_JWT_SECRET documentation

**Backend (new):**
- backend/app/models/auth.py - JWTClaims and AuthenticatedUser models
- backend/tests/core/__init__.py - Test package init
- backend/tests/core/test_security.py - 11 JWT validation tests
- backend/tests/api/test_auth_integration.py - 11 integration tests

**Frontend (new):**
- frontend/src/lib/api/client.ts - API client with auth
- frontend/src/lib/api/types.ts - API response types
- frontend/src/hooks/useAuth.ts - Auth hooks
- frontend/src/hooks/useAuth.test.ts - 12 hook tests

**Frontend (modified):**
- frontend/src/hooks/index.ts - Export auth hooks
- frontend/src/middleware.ts - Token expiry handling
- frontend/src/app/auth/logout/route.ts - GET support + cookie clearing
- frontend/src/app/(auth)/login/page.tsx - Session expired message
- frontend/src/tests/mocks/supabase.ts - Added refreshSession and onAuthStateChange mocks

