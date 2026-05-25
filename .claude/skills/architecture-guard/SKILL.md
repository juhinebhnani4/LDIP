---
name: architecture-guard
description: Use BEFORE designing or implementing any non-trivial change to the document pipeline, Celery workers, job orchestration, queue routing, document state machine, admin retry/recovery, or anything that touches `documents.status`, `processing_jobs`, `job_stage_history`, or pipeline locks. Also use before adding a new task to `backend/app/workers/tasks/`, before adding a new "exit path" to an existing task, and before any deployment topology change (railway.toml, start-worker.sh, queue config). Returns a checklist that must be answered in writing before code is written.
---

# Architecture Guard — LDIP

This skill exists because LDIP has accumulated three foundational architectural debts (ARCH-001, ARCH-002, ARCH-003 in `BUGS.md`) that have produced **every** P0/P1 pipeline incident in the project's history. Every one of those incidents was the same class of mistake: **implicit coordination through convention instead of explicit coordination through structure**.

The job of this skill is to make sure the next change does not add a fourth.

**As of 2026-05-25**, the skill also covers four **frontend** architectural debts — `FE-ARCH-01..04` in `BUGS.md` §0 (matter workspace convergence, responsive layout system, skeleton drift, presentation/format layer). See "The Four Frontend Forbidden Patterns" and "The Mandatory Checklist — Frontend" sections below. **One skill, two halves**: the backend and frontend catalogs are intentionally distinct because the dangerous surfaces differ, but the underlying disease (convention where structure belongs) is the same.

## When this skill MUST be invoked

Invoke before writing any code that:

1. Adds, removes, or reorders a Celery task in the document pipeline
2. Adds a new "exit path" / early return / shortcut to an existing pipeline task
3. Adds a new pipeline branch keyed on document properties (page count, type, size, MIME, source)
4. Touches `documents.status`, `processing_jobs`, `job_stage_history`, or pipeline lock keys
5. Touches `_mark_job_completed`, `create_post_ocr_chain`, `_dispatch_post_entity_tasks`, `_trigger_parallel_processing`, or any `finalize_*` task
6. Modifies `railway.toml`, `start-worker.sh`, queue routing in `celery.py`, worker concurrency, or `numReplicas`
7. Adds a new admin retry / recovery / cleanup endpoint
8. Adds a new background reconciler, sweeper, or maintenance task that mutates job/document state
9. Introduces a new "the X task must remember to call Y" rule

**Frontend triggers (added 2026-05-25, covering FE-ARCH-01..04):**

10. Adds a new feature panel to the matter workspace (a new `*Content.tsx` with its own SWR/fetch hooks under `frontend/src/components/features/`)
11. Touches `frontend/src/stores/matterStore.ts` (especially `fetchMatter` or the placeholder-fabrication path) or `frontend/src/types/matter.ts` (`MatterProcessingStatus`)
12. Adds, removes, or modifies a two-pane / multi-column / `ResizablePanelGroup` layout
13. Authors a new `*Skeleton` component or an inline `animate-pulse` placeholder
14. Calls `toLocaleDateString` / `toLocaleTimeString` / `Intl.DateTimeFormat`, or builds an inline count-string template (`` `${n} documents` ``), in a component outside `frontend/src/lib/format/`
15. Edits `frontend/src/components/ui/api-error-boundary.tsx`, `frontend/src/components/ui/skeleton.tsx`, or `frontend/src/lib/utils.ts`

If the user's request is purely UI copy changes, content-only edits, color/spacing tweaks that don't touch any of the surfaces above, isolated bug fixes outside both the pipeline and the frontend high-risk surfaces, or migrations that only add columns without changing flow — **skip this skill**.

## The Three Forbidden Patterns

Every proposed change must be checked against these. If the change matches any of them, **stop and propose an alternative** before writing code.

### Forbidden #1 — Parallel duplicate paths for the same logical work
**Smell**: "I'll handle small documents one way and large documents another." "I'll add a special case for Act documents." "I'll fork the chain when X."

**Why forbidden**: this is exactly how ARCH-001 happened. Two pipelines that "should" stay in sync. Three post-mortems and counting.

**Allowed alternative**: parameterize a single path. The optimization for the special case lives *inside* a stage, not as a top-level fork in the orchestrator.

### Forbidden #2 — Logical isolation without physical isolation
**Smell**: "I'll add a new queue for X." "I'll add `task_routes` for Y." "I'll set a soft timeout so it can't block others."

**Why forbidden**: this is exactly how ARCH-002 happened. Routing without separate worker processes is decoration. Queues, soft timeouts, and rate limiters do not isolate workloads — only **separate processes consuming separate queues** do.

**Allowed alternative**: any new queue must come with a deployment plan that includes the worker service (or replica) that will consume it exclusively. If you can't ship the worker, don't ship the queue.

### Forbidden #2b — Shared upstream API quota with no partitioning
**Smell**: "I'll add another LLM call from this task." "I'll route LLM work to the `llm` queue and call it isolated." "I'll add retry-with-backoff on 429s so it self-heals." "We'll just bump the Gemini quota."

**Why forbidden**: this is the deeper failure mode under ARCH-002. Every LLM-bound task in LDIP eventually calls the same Google Gemini account, which enforces ONE per-minute request quota. When any single task class saturates that quota, every *other* LLM task in the system starts getting `429 Too Many Requests`. Worker isolation does not help — the workers exist, they're just all stuck on hold with the same phone line. Retry-with-backoff makes it worse: the backed-off requests pile up and the next quota window gets immediately re-saturated.

**Allowed alternative**: any new task class that calls Gemini (or any other quota-limited upstream) must declare its **share** of the upstream budget. Enforced one of two ways:
1. **In-process token bucket** in front of the LLM client, partitioned by task class — citations gets X req/min, aliases gets Y, etc., summing to ≤ the global quota. One task class running hot cannot starve the others.
2. **Separate GCP projects** for hot task classes, each with its own native quota at the source.

If the change adds Gemini calls without specifying which budget bucket they consume, reject it.

### Forbidden #3 — "Remember to signal" coordination
**Smell**: "All exit paths of task X must dispatch task Y." "Make sure to release the lock in the failure handler." "If condition Z, also call `_mark_job_completed`." "Don't forget to update `documents.status` here." Adding the Nth call site of `_release_pipeline_lock_safe`.

**Why forbidden**: this is exactly how ARCH-003 happened. Lock release already has 14 call sites. Every "must dispatch from ALL exit paths" rule is a future P0.

**Allowed alternative**: state must be **derived from observed reality**, not signaled by convention. Ask "can a reconciler determine this status by querying the database?" If yes, prefer that. If you must signal, the signal site must be **exactly one** place that all paths necessarily flow through (a `finally:` block, a context manager, a decorator, or a wrapping orchestrator) — not "every author must remember."

## The Four Frontend Forbidden Patterns

Frontend changes are checked against a *separate* catalog of four debt shapes — `FE-ARCH-01..04` in `BUGS.md` §0. They are not the same as Forbidden #1/#2/#2b/#3 (those describe backend pipeline patterns). They apply when the touched file is in the frontend high-risk surface (triggers 10–15 above).

### FE-ARCH-01 — Per-panel-handles-its-own (no convergence point)
**Smell**: "I'll add a new feature panel and have it fetch its own data and render its own error state." "I'll catch the 404 and return a default object so the UI doesn't crash." "I'll add an inline `ErrorAlert` for this case." Adding the Nth independent fetch hook to the matter workspace.

**Why forbidden**: this is exactly how FE-ARCH-01 happened. Today the matter workspace has 29 independent fetch hooks across 7 panels with no shared existence/authorization gate, and `matterStore.fetchMatter()` *fabricates* an `'Untitled Matter'` placeholder on 404 (FE-003 = 18 console errors). The matter status type has no `'failed'` state (FE-007 = wrong "Ready" badge on the dashboard). `ApiErrorBoundary` is built but has zero usages.

**Allowed alternative**: one matter-existence/authorization gate at the layout level that resolves *once* before panels render — new panels render only behind it. Use the shared `ApiErrorBoundary` (or wire it if not yet wired) — do not add a per-panel error renderer. Add `'failed'` to `MatterProcessingStatus` if you touch that type; do not preserve the placeholder fabrication.

### FE-ARCH-02 — Responsive-by-component (no layout system)
**Smell**: "I'll add a two-pane / split / `ResizablePanelGroup` layout." "It works on desktop." "I'll add `sm:`/`md:`/`lg:` classes to make it responsive."

**Why forbidden**: this is exactly how FE-ARCH-02 happened. 68 files hand-add raw breakpoint classes; the matter Q&A panel never collapses by viewport because nothing structurally selects its position from width; no `useBreakpoint` / `useMediaQuery` primitive exists in the codebase. FE-001/002/005/006 are the symptoms — matter workspace unusable on mobile.

**Allowed alternative**: build a `useBreakpoint` hook (or equivalent) first if it doesn't exist. New multi-pane layouts must collapse to a single column / drawer / sheet below the tablet breakpoint *structurally* — not by hoping the user remembers to set the Q&A panel position to `'hidden'`. Add `scrollbar-gutter: stable` to globals.css if you're touching layout width.

### FE-ARCH-03 — Skeleton-as-parallel-copy
**Smell**: "I'll add a `SomethingSkeleton` component with `h-5 w-48` sized to roughly match the real component." Authoring a new `*Skeleton` as a separate file with hardcoded dimensions.

**Why forbidden**: this is exactly how FE-ARCH-03 happened. ~47 skeleton definitions hand-author dimensions that must stay in sync with the real component by vigilance alone. When the real component changes, the skeleton silently drifts → content jumps when real data arrives (contributes to FE-022's CLS 0.1138).

**Allowed alternative**: the skeleton IS the real component rendered in a "skeleton" mode (same DOM, same dimensions, shimmer instead of content). One source of truth — no parallel hand-tuning. If the project doesn't yet have a skeleton-mode primitive, build it *before* authoring more skeletons.

### FE-ARCH-04 — Format-at-call-site (no presentation layer)
**Smell**: "I'll call `date.toLocaleDateString({...})` right here in the component." "I'll write `` `${n} documents` `` inline." "I'll define my own `formatDate` function in this file."

**Why forbidden**: this is exactly how FE-ARCH-04 happened. 8 separate `formatDate` impls, 55 ad-hoc `Intl` call sites, 16 `date-fns` calls, 87 count strings, **4 actually-shipping plural bugs** ("1 documents", "1 pages"). `frontend/src/lib/utils.ts` has only `cn()`; no shared formatter.

**Allowed alternative**: `frontend/src/lib/format/` is the single source. Build it (`formatDate`, `formatDateTime`, `formatRelative`, `pluralize`, `formatCount` on one date library) if it doesn't exist yet — that's part of the FE-ARCH-04 wall (B4.3 in `GUARDRAIL-BACKLOG.md`). New formatting in components must import from there. The ESLint rule (when B4.3 ships) will eventually enforce this at PR time.

## The Mandatory Checklist

Before any code is written for a qualifying change, answer all of these in writing in your response to the user. Do not skip any. "N/A" is an acceptable answer if you justify why.

```
ARCHITECTURE GUARD CHECKLIST — <date>
Change summary: <one sentence>

1. PARALLEL PATHS (ARCH-001)
   - Does this introduce a branch in the orchestration layer keyed on document properties? [Y/N]
   - If Y: why can't this be parameterized inside a single stage? Justify.
   - Does any logic added here also need to be added to a sibling task file? List them.
   - If yes to the above: what enforces sync between the two? (Tests? Shared helper? If "vigilance," reject.)

2. PHYSICAL ISOLATION (ARCH-002)
   - Does this add or rely on a queue? [Y/N]
   - If Y: which worker process will consume it exclusively? Cite railway.toml line.
   - If "the existing worker," does this work block the existing worker? Estimate p99 duration.
   - If p99 > 30s OR LLM/CPU-bound: reject unless a dedicated worker is also shipped.

2b. SHARED UPSTREAM QUOTA (ARCH-002 deeper failure mode)
   - Does this change add or modify calls to Gemini, OpenAI, Voyage, or any other rate-limited upstream API? [Y/N]
   - If Y: which task class's budget bucket do these calls consume? Name it.
   - Is that bucket enforced by an in-process token bucket OR a dedicated GCP project? Cite the file/line.
   - If neither exists yet: reject the change OR ship the partitioner in the same PR.
   - Estimate the per-document call count for this task. Multiply by expected concurrent documents. Does it fit in the bucket?

3. STATE COORDINATION (ARCH-003)
   - Does this change `documents.status`, `processing_jobs.*`, or pipeline lock state? [Y/N]
   - If Y: how many call sites will mutate this state after the change? List them.
   - If > 1: can a reconciler derive this state from observed DB rows instead? If yes, prefer that.
   - If signaling is unavoidable: where is the SINGLE convergence point all paths flow through?
   - Does this add a new "must remember to call X" rule to MEMORY.md or comments? If yes, reject.

4. EXIT PATHS
   - List every early return / exception path in the touched task(s).
   - For each: does the downstream signal still fire? Demonstrate, don't assume.

5. FAILURE MODES
   - What happens if this task crashes mid-execution? Will the document be stuck or auto-recoverable?
   - What happens on retry? Is the operation idempotent? Cite the idempotency key.
   - What happens if the next task never starts (worker dies between dispatch and ack)?

6. VERIFICATION (per CLAUDE.md trust hierarchy)
   - Live DB schema queried for every touched table? [Y/N — paste column list]
   - Every callsite of every modified function found via Grep? [Y/N]
   - Every modified file Read in full (not just the changed function)? [Y/N]

7. DEPLOYMENT
   - Which Railway services need redeploying? (API, worker, both?)
   - Are there migration files? If yes, are they applied to live Supabase?

8. TEST PLAN
   - How will this be verified end-to-end against a real document?
   - What's the rollback plan if it breaks production?
```

## The Mandatory Checklist — Frontend (added 2026-05-25)

If the change touches the frontend high-risk surface (triggers 10–15), answer the relevant subset of this checklist in writing, *alongside* sections 6–8 from the backend Mandatory Checklist above (Verification, Deployment, Test Plan — those apply to all code regardless of half).

```
FRONTEND ARCHITECTURE GUARD CHECKLIST — <date>
Change summary: <one sentence>

F1. CONVERGENCE (FE-ARCH-01) — answer if you touched the matter workspace
   - Does this add a new feature panel, fetch hook, or matter-workspace child? [Y/N]
   - If Y: which existence/authorization gate does it sit behind? Cite file:line.
   - If "the matter layout renders me unconditionally and I fetch my own data" — reject.
     That's the pattern that produced FE-003.
   - Does it use ApiErrorBoundary or render its own error UI? If its own: justify
     why the shared boundary isn't appropriate. ("I forgot it exists" is not a
     justification.)
   - If touching matterStore.fetchMatter on the catch path: are you preserving the
     placeholder fabrication? If yes, reject — that IS the bug.
   - If touching MatterProcessingStatus: have you added a 'failed' state, or are you
     preserving the 3-value type with one dead value?

F2. RESPONSIVE / LAYOUT (FE-ARCH-02) — answer if you touched layout
   - Does this add a multi-column / two-pane / ResizablePanelGroup / sidebar layout? [Y/N]
   - If Y: how does it collapse below the tablet breakpoint? Cite the breakpoint and
     the collapsed shape (drawer? stacked? tabs?).
   - Does the project have a useBreakpoint / useMediaQuery primitive yet? If no,
     building it is part of the fix — propose that first.
   - Are you adding LAYOUT STRUCTURE (not just spacing) via per-component sm:/md:/lg:
     classes? If yes, propose the structural alternative.

F3. SKELETONS (FE-ARCH-03) — answer if you authored a Skeleton or animate-pulse placeholder
   - Why is the skeleton not the real component in skeleton-mode? Justify.
   - List the hardcoded h-/w- dimensions you are introducing. Explain why they
     cannot drift from the real component as the real component evolves.
   - If the project has no skeleton-mode primitive yet, building it is part of the
     fix — propose that before adding another hand-tuned skeleton.

F4. FORMATTING (FE-ARCH-04) — answer if you formatted a date or count
   - Does this call toLocaleDateString / toLocaleTimeString / Intl.DateTimeFormat
     in a component? [Y/N]
   - If Y: is it inside frontend/src/lib/format/? If no, reject — move to the
     format layer (build the layer if it doesn't exist).
   - Does this add a count-string template? Are you pluralizing with an inline
     ternary? If yes, use pluralize() (build it in lib/format/ if it doesn't exist)
     — don't add the 84th ternary.
   - Does this define a new formatDate function? Reject — there are already 8.

F5+. EXIT PATHS / FAILURE MODES / VERIFICATION / DEPLOYMENT / TEST PLAN
   - Use sections 4–8 from the backend Mandatory Checklist above. They apply to
     all code, not just pipeline code.
```

## How to use this skill in a conversation

When invoked:

1. Decide which half (or both) the change touches — backend pipeline surface, frontend high-risk surface, or both. Print the relevant checklist(s) filled in for the user's specific request. Be honest — if you can't answer a question, say so and ask the user.
2. If any backend forbidden pattern (#1 / #2 / #2b / #3) OR any frontend forbidden pattern (FE-ARCH-01..04) is matched, **stop and propose the allowed alternative**. Do not write the forbidden version even if the user asks for "just a quick fix."
3. Once the checklist is complete and all answers are clean, proceed to implementation.
4. After implementation, re-print items 4, 5, 6 from the backend checklist (or F1–F4 from the frontend checklist, whichever applied) to confirm the actual diff matches what was promised.

## Escape hatch

If the user explicitly says *"I know this violates ARCH-00X and I accept the debt — proceed anyway"* — you may proceed, but you must:

1. Add a new entry to the relevant `ARCH-00X` section in `BUGS.md` describing the new violation
2. Update MEMORY.md with the new "must remember to..." rule that was just added
3. Note in the PR/commit message that an architectural waiver was taken

This escape hatch exists because sometimes shipping matters more than purity. But it must be a deliberate, recorded choice — never a silent one.
