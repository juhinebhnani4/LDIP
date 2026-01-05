# Story 1.5: Implement Password Reset Flow

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **attorney**,
I want **to reset my password if I forget it**,
So that **I can regain access to my LDIP account without contacting support**.

## Acceptance Criteria

1. **Given** I am on the login page, **When** I click "Forgot Password", **Then** I am shown a form to enter my email address

2. **Given** I enter my registered email and click "Send Reset Link", **When** the request is processed, **Then** I receive an email with a password reset link (valid for 1 hour) **And** the UI shows "Check your email for reset instructions"

3. **Given** I click the password reset link in my email, **When** the link is valid and not expired, **Then** I am shown a form to enter a new password

4. **Given** I enter a valid new password (meets complexity requirements), **When** I click "Reset Password", **Then** my password is updated **And** I am redirected to the login page with a success message **And** I can log in with my new password

5. **Given** I click an expired or already-used reset link, **When** the page loads, **Then** I see an error message "This reset link has expired or already been used" **And** I am prompted to request a new reset link

## Tasks / Subtasks

- [x] Task 1: Create ForgotPasswordForm component (AC: #1, #2)
  - [x] Create `src/components/features/auth/ForgotPasswordForm.tsx`
  - [x] Add email input with validation (reuse `validateEmail` pattern from LoginForm)
  - [x] Implement `handleSubmit` calling `supabase.auth.resetPasswordForEmail()`
  - [x] Show success message after email sent
  - [x] Add "Back to login" link
  - [x] Export from `src/components/features/auth/index.ts`

- [x] Task 2: Create forgot-password page (AC: #1)
  - [x] Create `src/app/(auth)/forgot-password/page.tsx`
  - [x] Use ForgotPasswordForm component
  - [x] Follow existing auth page structure (login/signup pattern)
  - [x] Add page title "Reset Your Password"

- [x] Task 3: Add "Forgot Password" link to LoginForm (AC: #1)
  - [x] Update `src/components/features/auth/LoginForm.tsx`
  - [x] Add link below password field in password tab
  - [x] Link to `/forgot-password`
  - [x] Style consistently with existing links

- [x] Task 4: Create ResetPasswordForm component (AC: #3, #4)
  - [x] Create `src/components/features/auth/ResetPasswordForm.tsx`
  - [x] Add new password input with visibility toggle
  - [x] Add confirm password input
  - [x] Implement password strength validation (min 8 chars, 1 uppercase, 1 lowercase, 1 number)
  - [x] Implement `handleSubmit` calling `supabase.auth.updateUser({ password })`
  - [x] Show success message and redirect to login
  - [x] Export from `src/components/features/auth/index.ts`

- [x] Task 5: Create reset-password page (AC: #3, #4, #5)
  - [x] Create `src/app/(auth)/reset-password/page.tsx`
  - [x] Use ResetPasswordForm component
  - [x] Handle `code` query parameter from Supabase email link
  - [x] Detect and handle expired/invalid tokens
  - [x] Show appropriate error messages for invalid links

- [x] Task 6: Create auth callback route for password recovery (AC: #3, #5)
  - [x] Update `src/app/auth/callback/route.ts` to handle `type=recovery`
  - [x] Exchange code for session using `exchangeCodeForSession`
  - [x] Redirect to `/reset-password` on success
  - [x] Redirect to `/forgot-password?error=invalid_link` on failure

- [x] Task 7: Write tests for ForgotPasswordForm (AC: #1, #2)
  - [x] Create `src/components/features/auth/ForgotPasswordForm.test.tsx`
  - [x] Test email validation (empty, invalid format, valid)
  - [x] Test form submission calls `resetPasswordForEmail`
  - [x] Test success message display
  - [x] Test loading state during submission
  - [x] Mock Supabase client following existing patterns

- [x] Task 8: Write tests for ResetPasswordForm (AC: #3, #4)
  - [x] Create `src/components/features/auth/ResetPasswordForm.test.tsx`
  - [x] Test password validation (too short, missing requirements, valid)
  - [x] Test password confirmation match
  - [x] Test form submission calls `updateUser`
  - [x] Test success redirect behavior
  - [x] Mock Supabase client following existing patterns

- [x] Task 9: Write tests for reset-password page (AC: #5)
  - [x] Create `src/app/(auth)/reset-password/page.test.tsx`
  - [x] Test invalid link error display
  - [x] Test expired link handling
  - [x] Test successful password reset flow

## Dev Notes

### Critical Architecture Constraints

**FROM ARCHITECTURE DOCUMENT - MUST FOLLOW EXACTLY:**

#### Supabase Password Reset Flow
Supabase Auth handles password reset via magic link emails. The flow is:

1. User requests reset: `supabase.auth.resetPasswordForEmail(email, { redirectTo })`
2. Supabase sends email with secure link containing recovery code
3. User clicks link → redirects to `redirectTo` with `code` query param
4. App exchanges code for session: `supabase.auth.exchangeCodeForSession(code)`
5. User sets new password: `supabase.auth.updateUser({ password: newPassword })`

**CRITICAL:** The `redirectTo` URL MUST be added to Supabase Dashboard > Authentication > URL Configuration > Redirect URLs.

#### Password Reset API Pattern (REQUIRED)
```typescript
// Request password reset email
const { error } = await supabase.auth.resetPasswordForEmail(email, {
  redirectTo: `${window.location.origin}/auth/callback?type=recovery`,
});

// In auth/callback/route.ts - handle recovery type
if (code) {
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return NextResponse.redirect(`${origin}/forgot-password?error=invalid_link`);
  }
  // For recovery flows, redirect to reset-password page
  if (searchParams.get('type') === 'recovery') {
    return NextResponse.redirect(`${origin}/reset-password`);
  }
}

// Update password (user already authenticated via recovery flow)
const { error } = await supabase.auth.updateUser({
  password: newPassword,
});
```

### Password Validation Requirements

```typescript
const validatePassword = (password: string): { valid: boolean; error?: string } => {
  if (password.length < 8) {
    return { valid: false, error: 'Password must be at least 8 characters' };
  }
  if (!/[A-Z]/.test(password)) {
    return { valid: false, error: 'Password must contain at least one uppercase letter' };
  }
  if (!/[a-z]/.test(password)) {
    return { valid: false, error: 'Password must contain at least one lowercase letter' };
  }
  if (!/[0-9]/.test(password)) {
    return { valid: false, error: 'Password must contain at least one number' };
  }
  return { valid: true };
};
```

### Naming Conventions (CRITICAL - Must Follow)

| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `ForgotPasswordForm`, `ResetPasswordForm` |
| Component files | PascalCase.tsx | `ForgotPasswordForm.tsx` |
| Pages | lowercase with hyphens | `forgot-password/page.tsx` |
| Functions | camelCase | `handleSubmit`, `validatePassword` |
| Test files | Component.test.tsx | `ForgotPasswordForm.test.tsx` |

### File Structure for Password Reset Feature

```
frontend/
├── src/
│   ├── app/
│   │   └── (auth)/
│   │       ├── forgot-password/
│   │       │   └── page.tsx           # Request reset email
│   │       ├── reset-password/
│   │       │   └── page.tsx           # Set new password
│   │       └── login/
│   │           └── page.tsx           # Add forgot password link
│   └── components/
│       └── features/
│           └── auth/
│               ├── ForgotPasswordForm.tsx
│               ├── ForgotPasswordForm.test.tsx
│               ├── ResetPasswordForm.tsx
│               ├── ResetPasswordForm.test.tsx
│               ├── LoginForm.tsx       # Update with forgot link
│               └── index.ts            # Update exports
```

### Previous Story Intelligence

**From Story 1-4 (JWT Token Handling):**
- Auth hooks exist at `src/hooks/useAuth.ts` - reuse for session detection
- Supabase client at `src/lib/supabase/client.ts` (browser) and `server.ts` (server)
- Auth callback at `src/app/auth/callback/route.ts` - UPDATE this file for recovery type
- Login page at `src/app/(auth)/login/page.tsx` - session_expired pattern for banners
- Test mocks at `src/tests/mocks/supabase.ts` - reuse for new tests

**From Story 1-3 (Supabase Auth):**
- LoginForm pattern: tabs for different auth methods, error display, loading states
- SignupForm pattern: form validation, success messages
- Auth layout at `src/app/(auth)/layout.tsx` - centered card layout

**Key Patterns Established:**
- Use `createClient()` from `@/lib/supabase/client` for browser auth operations
- Error display in `rounded-md bg-destructive/10 p-3` div
- Success notice in `rounded-md bg-green-50 p-3` div
- Form validation before submission with `errors` state object
- Loading state with `isLoading` boolean
- Input components from shadcn/ui: Button, Input, Label, Card

### Error Messages (User-Friendly)

| Scenario | Error Message |
|----------|---------------|
| Invalid email format | "Please enter a valid email address" |
| Email not found | "If an account exists, you will receive an email" (security - don't reveal if account exists) |
| Invalid/expired reset link | "This reset link has expired or already been used. Please request a new one." |
| Password too weak | "[Specific requirement not met]" |
| Passwords don't match | "Passwords do not match" |
| Network error | "An unexpected error occurred. Please try again." |

### Anti-Patterns to AVOID

```typescript
// WRONG: Revealing if email exists in database
if (error.message.includes('User not found')) {
  setErrors({ general: 'No account with this email' }); // Security risk!
}

// CORRECT: Always show neutral message
setNotice("If an account exists, you will receive an email.");

// WRONG: Not handling expired tokens
// User clicks old link, gets cryptic error

// CORRECT: Explicit expired token handling
if (error.message.includes('expired') || error.message.includes('invalid')) {
  setErrors({ general: 'This reset link has expired or already been used. Please request a new one.' });
}

// WRONG: Redirecting to reset-password without valid session
// User can't update password without authentication

// CORRECT: Exchange code for session BEFORE showing reset form
const { error } = await supabase.auth.exchangeCodeForSession(code);
if (error) {
  return NextResponse.redirect(`${origin}/forgot-password?error=invalid_link`);
}
```

### Testing Guidance

**ForgotPasswordForm Tests (vitest):**
```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { ForgotPasswordForm } from './ForgotPasswordForm';

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      resetPasswordForEmail: vi.fn().mockResolvedValue({ error: null }),
    },
  }),
}));

test('shows success message after valid email submission', async () => {
  render(<ForgotPasswordForm />);

  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'test@example.com' },
  });
  fireEvent.click(screen.getByRole('button', { name: /send reset/i }));

  await waitFor(() => {
    expect(screen.getByText(/check your email/i)).toBeInTheDocument();
  });
});
```

**ResetPasswordForm Tests:**
```typescript
test('validates password requirements', async () => {
  render(<ResetPasswordForm />);

  fireEvent.change(screen.getByLabelText(/new password/i), {
    target: { value: 'weak' },
  });
  fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

  await waitFor(() => {
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
  });
});

test('validates password confirmation', async () => {
  render(<ResetPasswordForm />);

  fireEvent.change(screen.getByLabelText(/new password/i), {
    target: { value: 'ValidPass123' },
  });
  fireEvent.change(screen.getByLabelText(/confirm password/i), {
    target: { value: 'DifferentPass123' },
  });
  fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

  await waitFor(() => {
    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
  });
});
```

### Supabase Dashboard Configuration Required

**CRITICAL: Add redirect URL to Supabase Dashboard:**
1. Go to Supabase Dashboard > Authentication > URL Configuration
2. Add to "Redirect URLs": `http://localhost:3000/auth/callback`
3. For production, add: `https://your-domain.com/auth/callback`

Without this configuration, password reset emails will fail to redirect properly.

### References

- [Source: _bmad-output/architecture.md#Authentication-Authorization]
- [Source: _bmad-output/project-context.md#Framework-Specific-Rules]
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-1.5]
- [Source: _bmad-output/implementation-artifacts/1-4-jwt-token-handling.md#Dev-Notes]
- [Supabase Docs: Reset Password](https://supabase.com/docs/guides/auth/passwords?queryGroups=language&language=js#resetting-passwords)
- [Supabase Docs: updateUser](https://supabase.com/docs/reference/javascript/auth-updateuser)

### IMPORTANT: Always Check These Files Before Implementation

- **Previous Story:** `_bmad-output/implementation-artifacts/1-4-jwt-token-handling.md`
- **Architecture:** `_bmad-output/architecture.md`
- **Project Context:** `_bmad-output/project-context.md`
- **Existing Auth Components:** `frontend/src/components/features/auth/`
- **Auth Callback:** `frontend/src/app/auth/callback/route.ts`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 9 tasks completed successfully
- 65 tests pass (10 for ForgotPasswordForm, 13 for ResetPasswordForm, 7 for reset-password page)
- Build passes with all pages generating correctly
- Security: Shows neutral message for reset requests regardless of email existence
- Password validation: min 8 chars, uppercase, lowercase, number required
- Auth callback updated to handle `type=recovery` query parameter
- Fixed pre-existing tailwind.config.ts type error (changed darkMode from array to string)

### Change Log

| Date | Change |
|------|--------|
| 2026-01-05 | Initial implementation of all 9 tasks |
| 2026-01-05 | All tests passing (65 total) |
| 2026-01-05 | Build verified |

### File List

**New Files Created:**
- `frontend/src/components/features/auth/ForgotPasswordForm.tsx`
- `frontend/src/components/features/auth/ForgotPasswordForm.test.tsx`
- `frontend/src/components/features/auth/ResetPasswordForm.tsx`
- `frontend/src/components/features/auth/ResetPasswordForm.test.tsx`
- `frontend/src/components/features/auth/index.ts`
- `frontend/src/app/(auth)/forgot-password/page.tsx`
- `frontend/src/app/(auth)/reset-password/page.tsx`
- `frontend/src/app/(auth)/reset-password/page.test.tsx`

**Files Modified:**
- `frontend/src/components/features/auth/LoginForm.tsx` - Added "Forgot password?" link
- `frontend/src/app/auth/callback/route.ts` - Added recovery type handling
- `frontend/src/tests/mocks/supabase.ts` - Added resetPasswordForEmail, updateUser, verifyOtp mocks
- `frontend/tailwind.config.ts` - Fixed darkMode type (pre-existing issue)

