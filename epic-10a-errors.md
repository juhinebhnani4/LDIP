# Code Review Findings: Epic 10a (Stories 10A.1 - 10A.3)

**Review Status**: 🔴 **FAIL**
**Scope**: Frontend Components & Stores for Workspace Shell (Header, Tabs, Q&A Panel)

## 🚨 Critical Issues

### 1. False Test Coverage Claims (Discrepancy)
- **Severity**: CRITICAL
- **Affected Artifacts**: `10a-3-content-area-qa-panel.md` (and others)
- **Claim**: "1158 tests passing" in completion notes.
- **Actual**: `vitest run` executed only 681 tests (41 test files).
- **Impact**: Approximately 40% of claimed tests are missing, unrunnable, or not detected by the test runner. This indicates either a massive failure in test reporting by the previous agent or missing test files in the repository.

### 2. Broken Optimistic Update Rollback
- **Severity**: HIGH
- **Affected File**: `frontend/src/stores/matterStore.ts` (Lines 177-200)
- **Issue**: The `updateMatterName` action optimistically updates the global store state (`matters` list and `currentMatter`) *before* attempting the API call. Critical flaw: The function lacks any `try/catch` or rollback logic to revert the store state if the API call fails.
- **Outcome**: If the backend fails, the UI (`EditableMatterName`) might revert its local input, but the Global Store remains permanently desynchronized with the invalid name until a hard page reload. This violates data integrity principles.

## 🟡 Medium Issues

### 3. Architecture Violation: Manual Data Fetching vs SWR
- **Severity**: MEDIUM
- **Affected Files**: `frontend/src/stores/matterStore.ts`, `frontend/src/stores/workspaceStore.ts`
- **Issue**: The project includes `swr` as a dependency, which is the standard for server state management in Next.js. However, the implementation manually reinvents data fetching using Zustand stores + `useEffect` + manual `isLoading`/ `error` states.
- **Impact**: This leads to increased codebase complexity and bugs like Issue #4 (Caching). It ignores the robustness of `swr` for revalidation, deduplication, and cache management.

### 4. Aggressive Caching prevents Data Freshness
- **Severity**: MEDIUM
- **Affected File**: `frontend/src/stores/workspaceStore.ts` (Lines 125-133)
- **Issue**: `fetchTabStats` implements a naive cache check that returns early if *any* keys exist in `tabCounts`.
- **Impact**: If a user performs an action that changes counts (e.g., uploads a document), navigating away to another page and back to the workspace will *not* show updated stats because the store considers the stale data valid forever.

### 5. Unsafe "Mock" usage in Production Code
- **Severity**: MEDIUM
- **Affected File**: `frontend/src/stores/matterStore.ts` (Lines 25, 109, 140)
- **Issue**: `getMockMatters` is imported and used directly in the main logic path.
- **Impact**: There is no feature flag or environment variable switching. The mock data logic is interwoven with production logic, increasing the risk of mock data leaking into production if the "TODO" comments are missed during backend integration.

## 🟢 Low Issues

### 6. Hardcoded User-Facing Strings
- **Severity**: LOW
- **Affected Files**: `WorkspaceHeader.tsx`, `EditableMatterName.tsx`
- **Issue**: User-facing strings (e.g., "Settings coming soon", "Matter name cannot be empty") are hardcoded.
- **Impact**: Hinders future localization efforts and makes copy updates difficult.
