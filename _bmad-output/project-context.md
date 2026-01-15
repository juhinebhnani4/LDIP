---
project_name: 'LDIP'
user_name: 'Juhi'
date: '2026-01-03'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
existing_patterns_found: 15
status: 'complete'
rule_count: 65
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in LDIP (Legal Document Intelligence Platform). Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

### Frontend
- **Next.js 16** with App Router (NOT Pages Router)
- **TypeScript 5.x** in strict mode - no `any` types allowed
- **React 19** - use new concurrent features where appropriate
- **Tailwind CSS 4.x** with CSS variables
- **shadcn/ui** - use existing components, don't create custom primitives
- **Zustand** for state management - use selectors, not destructuring

### Backend
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **Celery** with Redis broker - use priority queues

### Database & Infrastructure
- **Supabase PostgreSQL** - pgvector enabled, RLS mandatory
- **Upstash Redis** - serverless, pay-per-request
- **Vercel** (frontend), **Railway** (backend)

### AI/ML Services
- **Gemini 3 Flash** - ingestion/extraction tasks ONLY
- **GPT-4** - reasoning/user-facing tasks ONLY
- **GPT-3.5** - query normalization ONLY
- **Google Document AI** - OCR with Indian language support

---

## Critical Implementation Rules

### Language-Specific Rules

#### TypeScript (Frontend)

- **Strict mode is MANDATORY** - `"strict": true` in tsconfig.json
- **No `any` types** - use `unknown` + type guards instead
- **Use `satisfies` operator** for type-safe object literals
- **Prefer `const` over `let`** - use `let` only when reassignment needed
- **Use optional chaining** (`?.`) and nullish coalescing (`??`)
- **Import React types** - `import type { FC } from 'react'` (not namespace import)

```typescript
// CORRECT
const matter = data satisfies Matter;
const title = matter?.title ?? 'Untitled';

// WRONG
const matter: any = data;
const title = matter.title || 'Untitled';  // falsy issue
```

#### Python (Backend)

- **Type hints on ALL functions** - both parameters and return types
- **Use `|` union syntax** instead of `Union[]` (Python 3.10+)
- **Use `match` statements** for multi-branch conditionals
- **Async functions** for I/O-bound operations (DB, API calls)
- **Use `structlog`** not standard logging library
- **Pydantic v2 syntax** - `model_validator` not `validator`

```python
# CORRECT
async def get_matter(matter_id: str) -> Matter | None:
    match status:
        case 'active': ...
        case 'archived': ...

# WRONG
def get_matter(matter_id) -> Union[Matter, None]:
    if status == 'active': ...
```

### Framework-Specific Rules

#### Next.js 16 App Router

- **Server Components by default** - add `'use client'` only when needed
- **Route groups** for layout sharing: `(auth)`, `(dashboard)`, `(matter)`
- **Server Actions** for simple Supabase queries (not FastAPI)
- **Use `loading.tsx`** and `error.tsx` for suspense boundaries
- **Dynamic routes** with `[matterId]` NOT `[id]` (be descriptive)
- **No `getServerSideProps`** - that's Pages Router

```typescript
// CORRECT - App Router
// src/app/(matter)/[matterId]/page.tsx
export default async function MatterPage({ params }: { params: { matterId: string } }) {
  const matter = await getMatter(params.matterId);
}

// WRONG - Pages Router syntax
export async function getServerSideProps(context) { }
```

#### FastAPI

- **Dependency injection via `Depends()`** for all shared logic
- **Use Pydantic models** for request/response - never raw dicts
- **Path parameters** for resources: `/matters/{matter_id}`
- **Query parameters** for filtering: `?page=1&status=active`
- **Use `HTTPException`** from custom exceptions module
- **Background tasks** via Celery, not FastAPI BackgroundTasks (for long operations)

```python
# CORRECT
@router.get("/matters/{matter_id}")
async def get_matter(
    matter_id: str,
    current_user: User = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
) -> MatterResponse:
    ...

# WRONG
@router.get("/matters")
def get_matter(request: Request):  # Don't use raw Request
    matter_id = request.query_params.get("id")  # Use path params
```

#### Zustand State Management

- **ALWAYS use selectors** - subscribe to specific state slices
- **NEVER destructure the entire store** - causes unnecessary re-renders
- **Separate stores by domain** - matterStore, sessionStore, chatStore

```typescript
// CORRECT - Selector pattern
const currentMatter = useMatterStore((state) => state.currentMatter);
const setCurrentMatter = useMatterStore((state) => state.setCurrentMatter);

// WRONG - Full store subscription
const { currentMatter, setCurrentMatter, matters, isLoading } = useMatterStore();
```

### Testing Rules

#### Frontend Testing (Vitest + React Testing Library)

- **Co-locate test files** with components: `MatterCard.test.tsx`
- **Test behavior, not implementation** - what user sees/does
- **Use `screen` queries** - prefer `getByRole` over `getByTestId`
- **Mock API calls** - use MSW for network mocking
- **No snapshot tests** for dynamic content

```typescript
// CORRECT
test('shows loading state while fetching', async () => {
  render(<MatterList />);
  expect(screen.getByRole('progressbar')).toBeInTheDocument();
});

// WRONG
expect(component).toMatchSnapshot();
```

#### Backend Testing (pytest)

- **Separate test directory** - `tests/api/`, `tests/engines/`, `tests/services/`
- **Use fixtures in `conftest.py`** for shared test data
- **Async tests** with `pytest-asyncio`
- **Use `httpx.AsyncClient`** for API testing
- **Mock external services** (LLM, OCR) - never call real APIs in tests

```python
# CORRECT
@pytest.mark.asyncio
async def test_get_matter(client: AsyncClient, test_matter: Matter):
    response = await client.get(f"/api/matters/{test_matter.id}")
    assert response.status_code == 200
```

#### Critical Security Tests

- **ALWAYS include `test_cross_matter_isolation.py`** - verify RLS
- **ALWAYS include `test_prompt_injection.py`** - LLM security
- **Run on every PR** - not just before release

### Code Quality & Style Rules

#### Naming Conventions (CRITICAL - Must Follow Exactly)

| Layer | Convention | Example |
|-------|------------|---------|
| Database tables | snake_case, plural | `matters`, `matter_attorneys` |
| Database columns | snake_case | `matter_id`, `created_at` |
| API endpoints | plural nouns | `/api/matters`, `/api/documents` |
| API path params | snake_case in braces | `{matter_id}` |
| TypeScript variables | camelCase | `matterId`, `isLoading` |
| TypeScript functions | camelCase | `getMatter`, `uploadDocument` |
| React components | PascalCase | `MatterCard`, `DocumentViewer` |
| React component files | PascalCase.tsx | `MatterCard.tsx` |
| Python functions | snake_case | `get_matter`, `process_document` |
| Python classes | PascalCase | `MatterService`, `CitationEngine` |
| Constants (all) | SCREAMING_SNAKE | `MAX_FILE_SIZE`, `API_TIMEOUT` |

#### API Response Format (MANDATORY)

```typescript
// Success - single item
{ "data": { "id": "uuid", "title": "Matter" } }

// Success - list with pagination
{
  "data": [...],
  "meta": { "total": 150, "page": 1, "per_page": 20, "total_pages": 8 }
}

// Error - always include code and message
{
  "error": {
    "code": "MATTER_NOT_FOUND",
    "message": "Matter with ID xyz not found",
    "details": {}
  }
}
```

**NEVER return raw objects** - always wrap in `{ data }` or `{ error }`.

#### File Organization

- **Frontend features** in `components/features/{domain}/`
- **Backend engines** in `engines/{engine_name}/`
- **Backend services** in `services/{service_name}/`
- **Shared types** in `types/{domain}.ts` (frontend) or `models/{domain}.py` (backend)

### Development Workflow Rules

#### Story Completion Requirements (MANDATORY)

After completing each story, the dev agent MUST explicitly inform the user of:

1. **Supabase Migrations to Run**
   - List all migration files that need to be applied
   - Note any that require service role execution
   - Example: `supabase migration up` or specific file paths

2. **Environment Variables to Add**
   - List new variables for frontend (`.env.local`)
   - List new variables for backend (`.env`)
   - Include where to find values (e.g., "Supabase Dashboard → Settings → API")

3. **Dashboard Configurations**
   - Supabase: Auth settings, redirect URLs, storage buckets, RLS policies
   - External services: Google Cloud, OAuth providers, etc.
   - Any manual toggles or settings required

4. **Manual Tests to Perform**
   - User-facing flows that should be tested manually
   - Specific scenarios beyond automated test coverage
   - Example: "Test login flow end-to-end with real email"

**Format for Story Completion:**
```
## Manual Steps Required

### Migrations
- [ ] Run: `supabase/migrations/YYYYMMDD_name.sql`

### Environment Variables
- [ ] Add to `frontend/.env.local`: `NEXT_PUBLIC_XXX=value`
- [ ] Add to `backend/.env`: `XXX=value` (from: location)

### Dashboard Configuration
- [ ] Supabase: Configure X in Y section

### Manual Tests
- [ ] Test: Description of manual test
```

#### Git Conventions

- **Branch naming**: `feature/ldip-{number}-short-description`, `fix/ldip-{number}-description`
- **Commit messages**: Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
- **PR title**: Same format as commit message
- **No force pushing** to `main` or `develop`

#### Environment Variables

- **Frontend**: Use `NEXT_PUBLIC_` prefix for client-accessible vars
- **Backend**: Use Pydantic Settings with `.env` file
- **NEVER commit `.env`** - only `.env.example`
- **Secrets**: Use platform secrets (Vercel, Railway), not env files in production

---

## Critical Don't-Miss Rules

### Matter Isolation (HIGHEST PRIORITY)

**Every table with `matter_id` MUST have RLS policy:**

```sql
CREATE POLICY "Users access own matters only"
ON {table_name} FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_attorneys
    WHERE user_id = auth.uid()
  )
);
```

**Four-layer enforcement - ALL required:**
1. **RLS policies** on every table with matter_id
2. **Vector namespace prefix** - `matter_{id}_` on all embeddings
3. **Redis key prefix** - `matter:{id}:` on all cache keys
4. **API middleware** - validate matter access on every request

### LLM Routing (Cost & Quality)

| Task Type | Model | Reason |
|-----------|-------|--------|
| OCR post-processing | Gemini 3 Flash | Bulk, low-stakes |
| Entity extraction | Gemini 3 Flash | Verifiable downstream |
| Citation extraction | Gemini 3 Flash | Regex-augmented |
| Contradiction detection | GPT-4 | High-stakes reasoning |
| Q&A synthesis | GPT-4 | User-facing, accuracy critical |
| Query normalization | GPT-3.5 | Simple, cost-sensitive |

**NEVER use GPT-4 for ingestion tasks** - it's 30x more expensive.
**NEVER use Gemini for user-facing answers** - higher hallucination rate.

### Two-Phase Response Pattern

All AI chat responses MUST use this pattern:

```
Phase 1 (0-2s): Return cached/pre-computed results immediately
  SSE: data: {"phase": 1, "cached": [...]}

Phase 2 (2-10s): Stream enhanced analysis
  SSE: data: {"phase": 2, "chunk": "...", "confidence": 85}
  SSE: data: {"complete": true, "final_confidence": 89}
```

### Confidence Thresholds

| Confidence | In-App Display | Export Allowed | Verification |
|------------|----------------|----------------|--------------|
| >90% | Show normally | Yes | Optional |
| 70-90% | Show with badge | Warning shown | Suggested |
| <70% | Show with warning | Blocked | Required |

### Safety Layer (MANDATORY)

1. **Query guardrails** - Block dangerous legal questions before processing
2. **Language policing** - Sanitize ALL engine outputs before user display
3. **No legal conclusions** - Findings are "observations", not "advice"
4. **Attorney verification** - Required for ANY export to court documents

### Anti-Patterns to Avoid

```typescript
// WRONG: Exposing service role key to frontend
const supabase = createClient(url, process.env.SUPABASE_SERVICE_KEY);

// WRONG: Skipping matter validation
async function getMatter(id: string) {
  return await db.matters.findUnique({ where: { id } }); // No user check!
}

// WRONG: Using localStorage for sensitive data
localStorage.setItem('authToken', token);

// WRONG: Catching errors silently
try { await upload() } catch (e) { /* silent */ }

// WRONG: Mixing snake_case in TypeScript
const matter_id = params.matterId; // Use matterId

// WRONG: Direct console.log in production code
console.log('Debug:', data); // Use structured logging
```

### Performance Gotchas

- **Virtualize PDF rendering** - Only visible pages + 1 buffer
- **Bbox overlay as canvas** - Not 500 DOM elements
- **Lazy load tabs** - Active tab only on mount
- **Client-side cache** - Tab data in Zustand store
- **Pre-warm HNSW index** after ingestion (prevents cold-query latency)
- **Batch UI updates** - Send deltas every 2 seconds during processing

---

## Quick Reference Checklist

Before submitting any code, verify:

- [ ] RLS policy exists for any new table with `matter_id`
- [ ] API responses wrapped in `{ data }` or `{ error }`
- [ ] Zustand uses selectors, not destructuring
- [ ] TypeScript has no `any` types
- [ ] Python functions have full type hints
- [ ] LLM routing follows the task-to-model mapping
- [ ] Tests include matter isolation verification
- [ ] No hardcoded secrets or API keys
- [ ] Error handling uses typed exceptions
- [ ] Naming conventions match the layer (snake_case/camelCase/PascalCase)
- [ ] **MANDATORY: Lint passes with zero warnings** - run `npm run lint` (frontend) or `ruff check` (backend) before marking story complete
- [ ] **MANDATORY: No unused imports or variables** - remove speculative imports that aren't used
- [ ] **MANDATORY: All destructured hook values are actually consumed** in the component

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in LDIP
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Check the Quick Reference Checklist before submitting code

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

---

_Last updated: 2026-01-03_
_Generated from: architecture.md_
