# Story 1.1: Initialize Next.js 15 Frontend Project

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a properly configured Next.js 15 frontend project with TypeScript, shadcn/ui, Tailwind CSS, and Zustand**,
So that **I have a production-ready foundation for building the LDIP user interface**.

## Acceptance Criteria

1. **Given** the LDIP repository is empty, **When** I run the project initialization commands, **Then** a Next.js 15 project is created with App Router enabled
2. **And** TypeScript is configured with strict mode (`"strict": true` in tsconfig.json)
3. **And** Tailwind CSS 4.x is installed and configured with CSS variables and dark mode support
4. **And** shadcn/ui is initialized with default components (button, card, dialog, dropdown-menu, input, label, tabs, toast, table)
5. **And** Zustand is installed for state management
6. **And** ESLint and Prettier are configured with consistent rules
7. **And** the project runs successfully with `npm run dev`
8. **And** the project structure follows the architecture specification exactly

## Tasks / Subtasks

- [x] Task 1: Initialize Next.js 15 project (AC: #1)
  - [x] Run `npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir`
  - [x] Verify App Router is enabled (no pages directory)
  - [x] Verify src directory structure created

- [x] Task 2: Configure TypeScript strict mode (AC: #2)
  - [x] Verify `"strict": true` in tsconfig.json
  - [x] Add path aliases (@/ for src/)
  - [x] Enable strict null checks

- [x] Task 3: Configure Tailwind CSS 4.x (AC: #3)
  - [x] Verify Tailwind CSS installation
  - [x] Configure CSS variables for theming
  - [x] Add dark mode support via next-themes (optional - can be added later)

- [x] Task 4: Initialize shadcn/ui (AC: #4)
  - [x] Run `npx shadcn@latest init -y`
  - [x] Add required components: `npx shadcn@latest add button card dialog dropdown-menu input label tabs sonner table` (sonner replaces deprecated toast)
  - [x] Verify components are in src/components/ui/

- [x] Task 5: Install Zustand for state management (AC: #5)
  - [x] Run `npm install zustand`
  - [x] Create initial store structure in src/stores/

- [x] Task 6: Install additional dependencies (AC: #6, #7)
  - [x] Run `npm install @supabase/supabase-js` for Supabase client
  - [x] Configure Prettier with `.prettierrc`
  - [x] Verify ESLint configuration (uses new flat config format)

- [x] Task 7: Create project directory structure (AC: #8)
  - [x] Create src/components/features/ (empty, for future feature components)
  - [x] Create src/lib/ with placeholder files (supabase.ts, utils.ts)
  - [x] Create src/stores/ with placeholder store
  - [x] Create src/types/ with placeholder type files
  - [x] Create src/hooks/ (empty, for custom hooks)

- [x] Task 8: Create initial app structure (AC: #1, #8)
  - [x] Create (auth)/ route group with layout.tsx
  - [x] Create (dashboard)/ route group with layout.tsx
  - [x] Create (matter)/[matterId]/ route group with layout.tsx
  - [x] Create loading.tsx and error.tsx for suspense boundaries

- [x] Task 9: Create environment configuration
  - [x] Create .env.local.example with required variables
  - [x] Add NEXT_PUBLIC_SUPABASE_URL placeholder
  - [x] Add NEXT_PUBLIC_SUPABASE_ANON_KEY placeholder
  - [x] Add NEXT_PUBLIC_API_URL placeholder (FastAPI backend)

- [x] Task 10: Verify project runs (AC: #7)
  - [x] Run `npm run dev`
  - [x] Verify no TypeScript errors
  - [x] Verify no ESLint errors
  - [x] Verify hot reload works

## Dev Notes

### Critical Architecture Constraints

**FROM ARCHITECTURE DOCUMENT - MUST FOLLOW EXACTLY:**

#### Project Structure (Required)
```
frontend/
├── src/
│   ├── app/                      # App Router pages
│   │   ├── (auth)/               # Auth route group
│   │   │   ├── login/page.tsx
│   │   │   └── layout.tsx
│   │   ├── (dashboard)/          # Dashboard route group
│   │   │   ├── page.tsx
│   │   │   └── layout.tsx
│   │   └── (matter)/             # Matter workspace route group
│   │       └── [matterId]/
│   │           ├── page.tsx
│   │           └── layout.tsx
│   ├── components/
│   │   ├── ui/                   # shadcn components (auto-generated)
│   │   └── features/             # Feature-specific components
│   ├── lib/
│   │   ├── supabase.ts           # Supabase client
│   │   └── utils.ts              # Utilities
│   ├── stores/                   # Zustand stores
│   ├── types/                    # TypeScript types
│   └── hooks/                    # Custom hooks
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── .env.local.example
```

#### Naming Conventions (CRITICAL - Must Follow)
| Element | Convention | Example |
|---------|------------|---------|
| Components | PascalCase | `MatterCard`, `DocumentViewer` |
| Component files | PascalCase.tsx | `MatterCard.tsx` |
| Hooks | camelCase with `use` prefix | `useMatter`, `useDocuments` |
| Functions | camelCase | `getMatter`, `uploadDocument` |
| Variables | camelCase | `matterId`, `isLoading` |
| Constants | SCREAMING_SNAKE | `MAX_FILE_SIZE`, `API_BASE_URL` |
| Types/Interfaces | PascalCase | `Matter`, `DocumentUpload` |

#### TypeScript Rules (MANDATORY)
- **Strict mode is MANDATORY** - `"strict": true` in tsconfig.json
- **No `any` types** - use `unknown` + type guards instead
- **Use `satisfies` operator** for type-safe object literals
- **Prefer `const` over `let`** - use `let` only when reassignment needed
- **Import React types** - `import type { FC } from 'react'`

#### Next.js 15 App Router Rules
- **Server Components by default** - add `'use client'` only when needed
- **Route groups** for layout sharing: `(auth)`, `(dashboard)`, `(matter)`
- **Use `loading.tsx`** and `error.tsx` for suspense boundaries
- **Dynamic routes** with `[matterId]` NOT `[id]` (be descriptive)
- **No `getServerSideProps`** - that's Pages Router (WRONG)

#### Zustand State Management Pattern
```typescript
// CORRECT - Selector pattern
const currentMatter = useMatterStore((state) => state.currentMatter);
const setCurrentMatter = useMatterStore((state) => state.setCurrentMatter);

// WRONG - Full store subscription (causes unnecessary re-renders)
const { currentMatter, setCurrentMatter } = useMatterStore();
```

### Technology Stack Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Next.js | 15.x | App Router, NOT Pages Router |
| React | 19.x | Use new concurrent features |
| TypeScript | 5.x | Strict mode |
| Tailwind CSS | 4.x | With CSS variables |
| shadcn/ui | Latest | Radix UI primitives |
| Zustand | Latest | State management |

### Initialization Commands

```bash
# Step 1: Initialize Next.js
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir

# Step 2: Navigate and initialize shadcn
cd frontend
npx shadcn@latest init -y

# Step 3: Add shadcn components
npx shadcn@latest add button card dialog dropdown-menu input label tabs toast table

# Step 4: Install additional dependencies
npm install zustand @supabase/supabase-js
```

### Project Structure Notes

- All paths MUST match the architecture document exactly
- Route groups `(auth)`, `(dashboard)`, `(matter)` are for layout organization
- `[matterId]` is the dynamic route param name (not `[id]`)
- Feature components go in `components/features/{domain}/`
- UI components (shadcn) auto-generated in `components/ui/`

### Anti-Patterns to AVOID

```typescript
// WRONG: Using any type
const matter: any = data;

// WRONG: Pages Router syntax
export async function getServerSideProps(context) { }

// WRONG: Destructuring entire Zustand store
const { currentMatter, matters, isLoading } = useMatterStore();

// WRONG: Using localStorage for auth tokens
localStorage.setItem('authToken', token);

// WRONG: Non-descriptive dynamic routes
app/(matter)/[id]/page.tsx  // Should be [matterId]
```

### References

- [Source: _bmad-output/architecture.md#Starter-Template-Evaluation]
- [Source: _bmad-output/architecture.md#Project-Structure]
- [Source: _bmad-output/architecture.md#Frontend-Structure]
- [Source: _bmad-output/architecture.md#Naming-Patterns]
- [Source: _bmad-output/project-context.md#TypeScript-Rules]
- [Source: _bmad-output/project-context.md#Next.js-15-App-Router]
- [Source: _bmad-output/project-context.md#Zustand-State-Management]
- [Source: _bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md#Infrastructure]
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-1.1]

### IMPORTANT: Always Check These Files
- **PRD/Requirements:** `_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md`
- **UX Decisions:** `_bmad-output/project-planning-artifacts/UX-Decisions-Log.md`
- **Architecture:** `_bmad-output/architecture.md`
- **Project Context:** `_bmad-output/project-context.md`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- None required - all tasks completed successfully

### Completion Notes List

- **Task 1**: Initialized Next.js 16.1.1 project with App Router, TypeScript, Tailwind CSS, ESLint using `create-next-app@latest`
- **Task 2**: TypeScript strict mode verified (`"strict": true`), added `strictNullChecks` and `noUncheckedIndexedAccess` for additional type safety
- **Task 3**: Tailwind CSS 4.x pre-configured by create-next-app with CSS variables and dark mode support via `prefers-color-scheme`
- **Task 4**: shadcn/ui initialized with 9 components: button, card, dialog, dropdown-menu, input, label, tabs, sonner (replaces deprecated toast), table
- **Task 5**: Zustand installed (v5.x), created stores directory with index.ts documenting selector pattern
- **Task 6**: Installed @supabase/supabase-js, configured Prettier with tailwind plugin, ESLint uses new flat config format (ESLint 9+)
- **Task 7**: Created complete directory structure matching architecture: components/features/, lib/, stores/, types/, hooks/
- **Task 8**: Created all route groups: (auth)/login, (dashboard), (matter)/[matterId] with layouts, plus loading.tsx and error.tsx
- **Task 9**: Created .env.local.example and .env.local with Supabase and API URL placeholders
- **Task 10**: Verified project runs with `npm run dev` - no TypeScript or ESLint errors, dev server starts on localhost:3000

### Change Log

- 2026-01-03: Story 1-1 completed - Frontend project initialized with full architecture-compliant structure

### File List

**New Files Created:**
- frontend/ (entire directory created)
- frontend/src/app/(auth)/layout.tsx
- frontend/src/app/(auth)/login/page.tsx
- frontend/src/app/(dashboard)/layout.tsx
- frontend/src/app/(dashboard)/page.tsx
- frontend/src/app/(matter)/[matterId]/layout.tsx
- frontend/src/app/(matter)/[matterId]/page.tsx
- frontend/src/app/loading.tsx
- frontend/src/app/error.tsx
- frontend/src/components/ui/button.tsx
- frontend/src/components/ui/card.tsx
- frontend/src/components/ui/dialog.tsx
- frontend/src/components/ui/dropdown-menu.tsx
- frontend/src/components/ui/input.tsx
- frontend/src/components/ui/label.tsx
- frontend/src/components/ui/tabs.tsx
- frontend/src/components/ui/sonner.tsx
- frontend/src/components/ui/table.tsx
- frontend/src/components/features/.gitkeep
- frontend/src/lib/supabase.ts
- frontend/src/lib/utils.ts
- frontend/src/stores/index.ts
- frontend/src/types/index.ts
- frontend/src/hooks/index.ts
- frontend/.env.local.example
- frontend/.env.local
- frontend/.prettierrc
- frontend/.prettierignore
- frontend/tsconfig.json (modified from default)
- frontend/package.json
- frontend/next.config.ts
- frontend/eslint.config.mjs
- frontend/components.json

