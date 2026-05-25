# GUARDRAIL-BACKLOG.md — Walls and Smart Sticky Notes to Build

> Created 2026-04-13 from an audit of existing rules in `CLAUDE.md`, `MEMORY.md`, the architecture-guard skill, and `verification-failures.md`.
>
> This file is **not a bug tracker** (that's `BUGS.md`). It's a backlog of **enforcement work**: rules currently held together by Claude remembering to read them, with a concrete promotion path to either a real wall (CI lint, codegen, structural fix) or a smart sticky note (auto-firing hook injection at the right moment).
>
> The frame and the six abstract patterns this backlog enforces against live in `ARCH-PATTERNS.md`.

---

## Quick legend

- **Wall** — structural enforcement. Build fails, function won't compile, type system rejects. Survives forgetting. Highest value, often highest cost to build.
- **Smart sticky note** — auto-firing hook that injects a focused reminder at the exact moment the danger sign appears (file edit, user prompt phrase, symbol insertion). Better than a passive sticky note because it can't be ignored at the moment of decision. Still depends on Claude reading it.
- **Passive sticky note** — a paragraph in `CLAUDE.md` or `MEMORY.md` that depends on Claude remembering to read and apply it. The default state of every rule we've ever written. Almost never reliably enforced.
- **The audit principle**: a rule that has survived past the existence of its wall is **debt**. When a wall lands, the corresponding passive sticky note should be **deleted from `MEMORY.md` / `CLAUDE.md` in the same PR**. Deletion is part of the fix.

---

## Bucket 1 — Promotable rules (cheap, high-value, ship soon)

These are rules currently held together by vigilance. Each one has a clear promotion path. They are listed in **value-per-minute order** — the cheapest, highest-leverage items first.

---

### B1.1 — User-prompt sniffer for "is not working" / "is broken" language

**Currently lives**: `MEMORY.md` line 92 ("For 'X is not working' bugs — query the live system FIRST"); full post-mortem in `verification-failures.md`.

**The known failure** it was written to prevent: 2026-03-18 LLM-005 incident. Five wrong theories built from code-reading, defended through five revisions, finally killed by one SQL query. Five hours of debug time wasted because Claude reached for code instead of data.

**Current form**: passive sticky note in MEMORY.md. Will not fire unless Claude happens to re-read MEMORY.md at exactly the right moment.

**Promotion → smart sticky note**: extend `.claude/hooks/zoom_out_guard.py` to sniff `UserPromptSubmit` payloads for the danger-phrase set:

  - `"not working"`, `"is broken"`, `"doesn't work"`, `"stopped working"`, `"failing"`, `"is failing"`, `"isn't working"`, `"broke"`, `"broken"`

When matched, inject a **second** context block (in addition to the universal zoom-out) that says:

> The request you just made describes something as broken or not working. Past sessions on this project built five wrong theories from code-reading before finally running one SQL query that settled the question (see `verification-failures.md`). **Before reading any code, run one query/curl against the live system.** Data beats theory. Always.

**Promotion → real wall**: not possible. You cannot grep Claude's reasoning. The smart sticky note is the strongest available form for this rule.

**Effort**: ~30 lines added to existing hook. ~20 minutes.

**Value**: would have prevented the LLM-005 incident outright. Single highest-ROI item in this entire backlog.

**Action on landing**: keep the MEMORY.md rule (it's still useful as durable narrative context), but add a one-line note that the smart sticky note now fires automatically.

---

### B1.2 — CI lint: `result.get()` inside Celery tasks

**Currently lives**: `MEMORY.md` line 44 ("Never call `result.get()` inside a Celery task — causes deadlock with prefork/gevent").

**The known failure**: this rule exists because someone hit it once. The deadlock is well-understood, has no false-positive cases inside the worker tasks directory, and is silently violatable today.

**Current form**: passive sticky note in MEMORY.md.

**Promotion → real wall**: a 5-line CI lint script. Sloppy version:

```bash
#!/usr/bin/env bash
if grep -rn 'result\.get(' backend/app/workers/tasks/; then
  echo "ERROR: result.get() inside a Celery task — causes deadlock with prefork/gevent"
  exit 1
fi
```

A more precise version uses Python's `ast` module to check that the `.get()` call is on a Celery `AsyncResult` (the result of a `.delay()` or `.apply_async()` call), but the sloppy grep version is good enough — false positives in `backend/app/workers/tasks/` would be rare, and the failure mode is severe enough that one false positive a year is fine.

**Effort**: 15 minutes (write script + add to CI).

**Value**: deletes a category of bug entirely. Real wall, no Claude judgment required.

**Action on landing**: **delete the MEMORY.md rule**. The wall now enforces it; the rule is debt.

---

### B1.3 — Bash hook for one-sided Railway deploys

**Currently lives**: `CLAUDE.md` Deployment section ("always deploy ALL services that have changes... always deploy both API and worker together").

**The known failure**: a half-deployed system. Worker out of sync with API. This rule lives in CLAUDE.md because it has been violated before, and the consequence is a class of production bug that's hard to diagnose because the symptoms vary by which side was redeployed.

**Current form**: passive sticky note in CLAUDE.md. Worse than usual, because deploy commands are run by the user (not Claude) — even if Claude reads the rule perfectly, the user is the one who has to remember.

**Promotion → smart sticky note**: a Bash-tool PreToolUse hook that fires when the command starts with `railway up -s LDIP` (API only) or `railway up -s ldip-worker` (worker only) and injects:

> You are deploying only one Railway service. The API and worker share a codebase and must stay in sync. Did you also need to deploy the other service? If yes: `railway up -s <other-service>`. If you intentionally want to deploy only one (rare), proceed.

**Promotion → real wall**: a `scripts/deploy.sh` (or Make target, or npm script) that *always* deploys both services. The wall is that there's no command surface that deploys only one — if you genuinely need to, you have to type the underlying `railway up -s X` directly, which is the friction that makes the hazard visible.

**Effort**: hook is ~10 lines added to `zoom_out_guard.py`. Deploy script is ~5 lines, plus the discipline of using it.

**Value**: prevents recurrence of a class of production bug.

**Action on landing**: keep the CLAUDE.md note for narrative context, but tighten it to "the deploy script handles this; if you bypass the script, the bash hook will remind you."

---

### B1.4 — Hook detection of new call sites for ARCH-003 symbols

**Currently lives**: `MEMORY.md` line 34 (*"`extract_citations` MUST dispatch `detect_contradictions` from ALL exit paths"*) and `BUGS.md` ARCH-003 (broader pattern).

**Why this rule is the most damning entry in MEMORY.md**: it is *literally* the sentence that defines pattern P1 from `ARCH-PATTERNS.md`. We documented it as a *fix*. It is not a fix. It is a sticky note describing the very problem ARCH-003 says we are not allowed to use as a fix. Its presence in MEMORY.md is the smell.

**Current form**: passive sticky note in MEMORY.md, plus partial coverage by the architecture-guard hook (which fires when files in `HIGH_RISK_PATH_FRAGMENTS` are edited but doesn't specifically watch for new call sites of these symbols).

**Promotion → smart sticky note**: extend `zoom_out_guard.py:edit_mentions_high_risk_symbol()` to detect *insertion* of these symbols (present in `new_string`, absent from `old_string`) — distinct from editing an existing call site. The reminder text becomes specific:

> You are adding a new call site of `_mark_job_completed` / `_release_pipeline_lock_safe` / `_dispatch_post_entity_tasks`. This function already has N call sites (lock release: 14). This is the exact pattern that built ARCH-003. **Before adding the (N+1)th call site, ask: can the convergence point be moved into a `try/finally`, decorator, or reconciler instead?**

**Promotion → real wall (one task at a time)**: an AST-based unit test that imports `extract_citations`, walks its function body, finds every `return` and exception-exit path, and asserts each one is followed by a dispatch of `detect_contradictions`. ~50 lines. Test fails the build if any exit path skips the dispatch. This retires the *specific* MEMORY.md rule even before the broader ARCH-003 refactor lands.

**Promotion → real wall (the actual ARCH-003 fix)**: a `try/finally` decorator or context manager around `extract_citations` (and eventually all tasks with this shape) that dispatches `detect_contradictions` on exit regardless of how the function returns. Once the decorator exists, the rule **deletes itself from MEMORY.md** because it's enforced by structure.

**Effort**: smart sticky note ~20 lines. AST test one afternoon. Decorator refactor scoped per-task, ~half a day each.

**Value**: smart sticky note is immediate; AST test retires one specific MEMORY.md rule; decorator refactor is the cheapest piece of ARCH-003 to actually pay down.

**Action on landing**: when the AST test ships, change the MEMORY.md rule from *"MUST dispatch from ALL exit paths"* to *"the AST test enforces this; do not weaken or skip the test."* When the decorator refactor ships, **delete the MEMORY.md rule entirely**.

---

### B1.5 — Migration-file hook for unversioned `CREATE OR REPLACE FUNCTION search_*`

**Currently lives**: nowhere explicit. ARCH-005 in `BUGS.md` documents the broader pattern; no rule prevents the next instance.

**The known failure**: 11 migrations have already mutated `search_chunks` / `search_documents` / `hybrid_search` in place. Each one was a coordinated cross-repo deploy with no rollback story.

**Current form**: not even a passive sticky note. Pure convention.

**Promotion → smart sticky note**: extend `zoom_out_guard.py` with a third matcher for Edit/Write on files matching `supabase/migrations/*.sql`. Sniff the proposed content for `CREATE OR REPLACE FUNCTION` followed by any name in a small allowlist (initial set: `search_chunks`, `search_documents`, `hybrid_search`; expand as more cross-repo functions are identified by `Grep .rpc(` in `backend/`). On match, inject:

> This migration mutates a Postgres function that has callers in `backend/` (Python `.rpc(...)` calls). Without a version suffix, this is a coordinated cross-repo deploy with no rollback target — `git revert` on this file is meaningless because the function in production has already been overwritten. **Propose `<function_name>_v3` alongside the existing `_v2` instead.** Only drop `_v2` in a separate migration after the API has cut over.

**Promotion → real wall**: CI lint that fails any new file in `supabase/migrations/` containing `CREATE OR REPLACE FUNCTION search_` (or any allowlist name) without a `_v[0-9]+` suffix in the function name. Same shape as B1.2.

**Effort**: hook ~15 lines. Lint ~10 lines.

**Value**: prevents recurrence of ARCH-005's failure mode in new migrations. Existing 11 migrations are unaffected (this is a forward fence, not a retrofit).

**Action on landing**: add a one-line note in `BUGS.md` ARCH-005 that the hook fences new instances.

---

### B1.6 — Codegen for backend↔frontend types (ARCH-006 wall)

**Currently lives**: `BUGS.md` ARCH-006 documents the pattern; no enforcement exists.

**The known failure**: 36 hand-written `frontend/src/lib/api/*.ts` files mirroring FastAPI Pydantic models. Field renames silently break the frontend.

**Current form**: pattern documented, no rule, no enforcement.

**Promotion → real wall**: add `openapi-typescript` as a frontend dev dependency. Add an npm script `gen:api-types` that fetches `https://jaanch-ai.up.railway.app/openapi.json` (or local backend) and writes `frontend/src/lib/api/types.generated.ts`. Wire into the frontend build so the file is regenerated on every CI run. Hand-written API client function bodies in `lib/api/*.ts` keep their request logic but **import their types from the generated file**. Type drift becomes a TypeScript compile error.

**CI lint as a complementary fence**: count the number of hand-written `interface` declarations in `frontend/src/lib/api/`. Commit a baseline. The number can only go down. New API client files must import types from `types.generated.ts`.

**Effort**: half a day for codegen setup + initial migration of the most-used types. Full migration of all 36 files is a longer refactor, but the codegen + lint can land before the migration is complete — they just gate *new* work without forcing the existing files to convert immediately.

**Value**: highest of any single item in this backlog. Deletes an entire category of bug (silent type drift across the API boundary), and a non-trivial fraction of the open UX bugs in `BUGS.md` sections 4–9 likely have type drift somewhere upstream of them.

**Action on landing**: this is the first piece of ARCH-006 to actually pay down.

---

### B1.7 — Codegen for Python↔Postgres column names

**Currently lives**: `MEMORY.md` line 109 (*"`documents` table uses `filename` (not `name`), `ocr_error` (not `error_message`/`error_code`)"*).

**Why this rule is the most embarrassing entry in MEMORY.md**: it shouldn't need to exist at all. The fact that we have a memory entry telling Claude what columns a Postgres table has is *exactly* pattern P5 from `ARCH-PATTERNS.md` (hand-mirrored types between layers), at the Python↔Postgres boundary. The CLAUDE.md "Trust Hierarchy" rule already says "live database wins" — codegen is just that rule made structural.

**Current form**: passive sticky note in MEMORY.md, plus the more general "query the live database before any Supabase query" rule in CLAUDE.md.

**Promotion → real wall**: auto-generated SQLAlchemy / SQLModel / Pydantic models from the live Postgres schema, regenerated on CI, committed to the repo. Once they exist, `Document.flename` is a Python `AttributeError` *at import time*, not a silent SQL error at runtime. There are several existing Python tools for this (`sqlacodegen`, `datamodel-code-generator`, etc.); pick whichever fits the rest of the backend stack.

**CI lint as a complementary fence**: same shape as B1.6 — count hand-written column references and ratchet down.

**Effort**: half a day for the codegen setup, ongoing zero. Migration of existing model files is incremental.

**Value**: very high. Deletes the same category of bug as B1.6 but at the Python↔Postgres boundary. Together with B1.6, replaces ~half of MEMORY.md with structure.

**Action on landing**: **delete the MEMORY.md column-name rule**. **Delete the "Schema Check Discipline — NEVER SKIP STEP 2" rule** at MEMORY.md line 75 — that rule exists *only* because we read migration files instead of querying the live DB, and codegen makes the live DB the source of truth.

---

### B1.8 — Hook fix: skip symbol check on documentation files

**STATUS (2026-05-25)**: ✅ **LANDED** in working tree (`zoom_out_guard.py`). Added `DOC_FILE_SUFFIXES = (".md", ".markdown", ".mdx", ".rst", ".txt")` and an early `return False` in `edit_mentions_high_risk_symbol()` for documentation files. The path-based check (`is_high_risk_path`) is unchanged, so code-file protection is intact. **PR-bundling note**: this entry's own "Action on landing" said to bundle with the next hook change rather than ship standalone. It is currently sitting in the working tree alongside the BUGS.md / GUARDRAIL-BACKLOG.md merge; bundle with **B4.2** (frontend hook extension) when that lands. Do not commit B1.8 alone as a standalone PR.

**Currently lives**: `.claude/hooks/zoom_out_guard.py:edit_mentions_high_risk_symbol()`.

**The known failure**: discovered while writing this very file. The hook fires the architecture-guard reminder when a `.md` documentation file mentions any symbol in `HIGH_RISK_SYMBOLS`. A doc file that *describes* `_release_pipeline_lock_safe` looks identical to a Python file that *adds a new call site* of it. False positives are guaranteed for any file in this backlog or in `ARCH-PATTERNS.md`.

**Current form**: a real bug in the hook itself. Itself an instance of pattern P4 — the helper exists, but its detection rule is too coarse to distinguish "calling this thing" from "talking about this thing."

**Promotion → real wall**: one-line fix. In `edit_mentions_high_risk_symbol()`, return `False` if `file_path` ends in `.md` / `.txt` / `.rst` / `.mdx`. The path-based check (`is_high_risk_path`) still fires correctly on actual code files, so the protection is intact.

**Effort**: 5 minutes.

**Value**: stops the hook from crying wolf on every documentation edit, which is the single fastest way for a hook to lose its credibility and start being ignored. Especially important now that we have multiple .md files (`ARCH-PATTERNS.md`, this file, future ones) that legitimately need to reference the symbols.

**Action on landing**: ship in the same PR as any other hook edit (B1.1, B1.4, B1.5, B1.6 all touch this file). Do not ship as a standalone PR — bundle with the next hook change.

---

## Bucket 2 — Rules that are appropriately sticky notes (do not promote)

These are rules in CLAUDE.md and verification-failures.md that I considered for promotion and concluded **should stay as passive sticky notes**. Mechanically enforcing them would be theater.

- **CLAUDE.md "Engineering Philosophy"** (no band-aid fixes / research before implementing / future-ready design / understand before changing / fix root causes). These are values, not rules. There is no regex that detects "you took a band-aid approach." Walls do not apply. Keep as framing.
- **CLAUDE.md "Trust Hierarchy"** (live database > code > migrations > CLAUDE.md > NEVER trust comments). A meta-rule about which evidence beats which. Cannot be enforced from outside Claude's reasoning. Stays a sticky note.
- **`verification-failures.md` Rules 3 and 4** ("when building a theory, look for disconfirming evidence" / "don't defend a wrong answer — restart from data"). Meta-rules about reasoning under challenge. Cannot be enforced by hook or lint. Stay as narrative post-mortem.
- **The four zoom-out questions themselves**. Already a smart sticky note via `zoom_out_guard.py:UserPromptSubmit`. Working as intended. No further promotion needed.

The honest move on these is to **stop pretending they're enforceable** and acknowledge they depend on Claude (and the user) reading them. Proposing to promote them would be the same kind of theater as MEMORY.md accumulating "remember to..." rules in lieu of actual fixes.

---

## Bucket 3 — The meta-finding: MEMORY.md is itself rotting in the ARCH-003 shape

This is the most important observation from the whole audit, and it doesn't fit cleanly into "promote rule X to wall Y." It's a property of the MEMORY.md file as a whole.

**The pattern**: every promotable rule in Bucket 1 above was added to MEMORY.md *as the response to a past bug*. Each addition was individually defensible: "we hit this bug, let's document so it doesn't happen again." Each addition increased the count of sticky notes Claude has to read and remember.

**The shape**: this is the same failure mode as the lock-release call sites going from 1 to 14. We have responded to past bugs by writing more rules instead of building more structure. **MEMORY.md has become the equivalent of the `_release_pipeline_lock_safe` 14 call sites**: a place where we paste obligations every time something breaks, in lieu of fixing the structural reason it broke.

**The discipline this implies**: every entry in MEMORY.md (and in CLAUDE.md, and in `verification-failures.md`, and in any future memory file) should be tagged with one of three states:

1. **Wall exists** — the rule is enforced by structure. The MEMORY.md entry should be **deleted** or shrunk to a one-line pointer at the wall.
2. **Smart sticky note exists** — the rule is auto-injected at the right moment by a hook. The MEMORY.md entry can stay as durable narrative context but should note that the smart sticky note carries the load.
3. **Passive sticky note only** — the rule depends on Claude remembering to read MEMORY.md. **This is debt.** It belongs in this backlog with a promotion path.

**Concrete proposal**: when any item in Bucket 1 lands, the corresponding MEMORY.md rule gets deleted *in the same PR*. The deletion is the load-bearing part of the fix. A rule that survives past its wall is debt — it tells future Claudes there is still vigilance work to do when in fact there isn't, and it crowds out the rules that *do* still need vigilance.

**Periodic audit**: every 2-3 months, do this audit again. Find the rules that have accumulated since the last pass. Promote the promotable ones. Delete the ones whose walls have landed. Acknowledge the ones that are appropriately sticky notes. The audit *itself* is the wall against MEMORY.md rotting — without it, the file slides back into the same shape.

---

## Bucket 4 — Frontend architecture guard extension (added 2026-05-25)

**Why this bucket exists**: the frontend was never under the `architecture-guard` lens, so it accumulated four parallel architectural debts unobserved — **FE-ARCH-01..04** in `BUGS.md` §0. They share the disease of Bucket 1 (sticky notes where walls belong) but at frontend boundaries: matter workspace shell, layout/responsive system, loading skeletons, and the presentation/format layer.

**Design principle — do NOT skip**: this is an **extension of the existing `architecture-guard` skill**, not a parallel `frontend-arch-guard` skill. A separate skill would be exactly the P2 / parallel-duplicate-paths failure mode this project keeps warning against — two skills doing the same job, drifting over time, with a new "remember which one to invoke" sticky note in MEMORY.md. The wall is **one skill, two halves** + auto-firing hook extension + targeted CI lints. The same shape as the merge that consolidated FE-ARCH-01..04 into `BUGS.md` §0 today.

---

### B4.1 — Extend `architecture-guard/SKILL.md` to cover frontend FE-ARCH-01..04

**STATUS (2026-05-25)**: ✅ **LANDED** in working tree alongside B1.8 and B4.2 (same PR bundle). Added: (a) intro paragraph naming the frontend half, (b) frontend trigger items 10–15 in "When MUST be invoked" + updated "skip this skill" exception, (c) full "## The Four Frontend Forbidden Patterns" section covering FE-ARCH-01..04 in the same Smell / Why forbidden / Allowed alternative shape as the existing backend forbidden patterns, (d) "## The Mandatory Checklist — Frontend" with F1–F4 question blocks (verification/deployment/test plan reuses backend §§6–8 to avoid duplication), (e) updated "How to use" to reference both halves. The skill body now matches what the B4.2 hook reminder text directs readers to.

**Currently lives**: nowhere. `architecture-guard/SKILL.md` already includes `frontend/` path fragments but carries no frontend-specific checklist content.

**Current form**: not even a sticky note for the frontend half.

**Promotion → smart sticky note**: append four checklist sections to `architecture-guard/SKILL.md`, one per FE-ARCH-NN, that the skill must answer in writing before code is written:
- **FE-ARCH-01 (matter convergence)**: "Are you adding a new feature panel to the matter workspace? Then you are adding a new independent fetch site. Has this been routed through the existence/auth gate? Does it use `ApiErrorBoundary` or implement its own error UI?"
- **FE-ARCH-02 (responsive)**: "Are you adding a fixed two-pane / resizable / multi-column layout? Where is its viewport-collapse breakpoint? Is there a shared `useBreakpoint` primitive (currently there isn't — adding one is part of the fix)?"
- **FE-ARCH-03 (skeletons)**: "Are you authoring a new skeleton? Why isn't it the real component in skeleton-mode? List the dimensions you're hand-coding and explain why they cannot drift."
- **FE-ARCH-04 (format layer)**: "Are you formatting a date/count inline? `lib/format/` is the only allowed source. If it doesn't have what you need, add it there — do not roll your own at the call site."

**Effort**: ~30 min.

**Value**: makes the FE-ARCH frame discoverable the moment a frontend high-risk file is edited. Same shape as the existing backend checklist sections of `architecture-guard/SKILL.md` — one skill, two halves.

**Action on landing**: add a one-line cross-link in each of BUGS.md FE-ARCH-NN's "Target architecture" sections pointing to the new checklist section.

---

### B4.2 — Extend `zoom_out_guard.py` hook with frontend high-risk paths and symbols

**STATUS (2026-05-25)**: ✅ **LANDED** in working tree alongside B1.8. Renamed `HIGH_RISK_PATH_FRAGMENTS` / `HIGH_RISK_SYMBOLS` / `ARCHITECTURE_GUARD_REMINDER` to `BACKEND_*`, added symmetric `FRONTEND_HIGH_RISK_PATH_FRAGMENTS`, `FRONTEND_HIGH_RISK_SYMBOLS`, `FRONTEND_ARCHITECTURE_GUARD_REMINDER` (the FE-ARCH-01..04 checklist). Factored out shared helpers (`_content_blobs`, `_is_doc_file`) so the B1.8 doc-file exclusion applies to both halves. `main()` emits both reminders when both halves match. Verified via 7 subprocess test cases — backend-only, frontend-only, dual-fire, doc-file suppression, and no-match all behave correctly. **One PR bundles B1.8 + B4.2** (zoom_out_guard.py changes), satisfying B1.8's "do not ship standalone" rule.

**Currently lives**: `.claude/hooks/zoom_out_guard.py`. Today: detects backend high-risk paths (Celery tasks, pipeline files) and symbols (`_release_pipeline_lock_safe` etc.) on Edit/Write and injects backend architecture-guard reminders.

**Current form**: backend-only — zero frontend detection.

**Promotion → smart sticky note**: add frontend `HIGH_RISK_PATH_FRAGMENTS` and `HIGH_RISK_SYMBOLS` (mirroring the existing backend pattern):
- **Paths**: `frontend/src/stores/matterStore.ts`, `frontend/src/app/matter/[matterId]/layout.tsx`, `frontend/src/components/features/matter/WorkspaceContentArea.tsx`, `frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx`, `frontend/src/lib/utils.ts`, `frontend/src/app/globals.css`, and anything matching `frontend/src/components/features/*/*Content.tsx` or `*Skeleton*.tsx`.
- **Symbols**: `MatterProcessingStatus`, `fetchMatter`, `ApiErrorBoundary`, `Untitled Matter`, `toLocaleDateString`, `formatDate`, `ResizablePanelGroup`, `useMatterSummary`.

On match, inject the relevant FE-ARCH-NN guard text (one paragraph per debt, mirroring the existing backend reminder text in this hook).

**Promotion → real wall**: not possible at the hook layer — same as the backend equivalent. The wall versions are B4.3 (ESLint) and B4.4 (markdown lint).

**Effort**: ~30 min (mostly mirroring existing backend stanzas in this file).

**Value**: **highest leverage in Bucket 4** — auto-fires the FE-ARCH checklist at edit time, the moment someone touches a frontend high-risk file. Equivalent of B1.4 for the frontend half.

**Action on landing**: requires the `.md`-file-exclusion fix from **B1.8** to already be in place, otherwise every edit to `BUGS.md` / `FRONTEND-AUDIT-2026-05-20.md` mentioning these symbols will false-positive.

---

### B4.3 — ESLint rule + `lib/format/` layer (the real wall for FE-ARCH-04)

**Currently lives**: nowhere. FE-ARCH-04 in `BUGS.md` §0 documents the pattern; nothing enforces it.

**The known failure**: 8 reimplementations of `formatDate`, 55 ad-hoc `toLocaleDateString` calls, 4 hardcoded plural bugs ("1 documents", "1 pages") rendered to actual users.

**Current form**: pure convention.

**Promotion → real wall**:
1. Build `frontend/src/lib/format/` (the structural fix from FE-ARCH-04's "Target architecture"): `formatDate`, `formatDateTime`, `formatRelative`, `pluralize`, `formatCount`. One date library. `utils/formatRelativeTime.ts` migrates into it.
2. Add a custom ESLint rule that fails the build if any `.tsx` outside `lib/format/` calls `toLocaleDateString` / `toLocaleString` / `toLocaleTimeString` / `new Intl.DateTimeFormat`, or builds a count-string template `` `${...} <word>s` `` without going through `pluralize`.
3. Ratchet — commit a baseline of current violations; the count can only go down.

**Effort**: ~half day for `lib/format/` setup + initial ESLint rule + baseline ratchet. Full migration of the 71 date sites + 87 count strings is incremental and parallelizable.

**Value**: deletes the FE-ARCH-04 category of bug at the build boundary. Equivalent of B1.6 (frontend codegen for ARCH-006) at a different boundary inside the same repo.

**Action on landing**: when the rule + lib land and the four acute plural bugs in FE-015 (`MatterCard.tsx:169`, `:217`, `OCRQualityDetail.tsx:141`, `citationGrouping.ts:158`) are fixed, mark FE-015 FIXED in BUGS.md. Mark FE-ARCH-04 FIXED only after the baseline ratchet reaches zero violations and the rule blocks regressions.

---

### B4.4 — Markdown lint: every `### (FE-)ARCH-NN` entry in `BUGS.md` must carry a `**Detector:**` field

**Currently lives**: nowhere. The detector-driven census discipline lives in the four FE-ARCH-01..04 entries by convention; ARCH-001..007 don't have it.

**The known failure**: without this lint, the next FE-ARCH-05 (or ARCH-008) will be authored without a regenerable detector, and the census will rot back into a hand-list — exactly the shape `FRONTEND-ARCH-DEBT.md` was deleted to escape (today, 2026-05-25). The detector mechanism is the only thing keeping the instance counts in FE-ARCH-NN entries honest.

**Current form**: pure convention. The four FE-ARCH entries authored today carry detectors; nothing makes that mandatory for the next entry.

**Promotion → real wall**: a ~10-line markdown lint that scans `BUGS.md` for `^### (ARCH|FE-ARCH)-\w+:` headers and asserts each one's body contains a `**Detector:**` field. CI fails on missing.

**Effort**: ~30 min for the lint.

**Value**: locks in the regenerable-detector discipline. New ARCH-style entries cannot ship without one. Modest effort for a wall that prevents the rot pattern from recurring.

**Action on landing**: retrofit detectors onto ARCH-001..007 in the same PR. Most have natural detectors (ARCH-001: line counts of the two pipeline files; ARCH-002: `numReplicas` in `railway.toml` + `task_routes` grep; ARCH-004: `rg "from google.genai import types" backend/app/engines backend/app/services | wc -l`; ARCH-005: count of `CREATE OR REPLACE FUNCTION search_` migrations; ARCH-006: count of hand-written `interface` in `frontend/src/lib/api/`). ARCH-003 / ARCH-007 are pattern-matches and need careful detector wording.

---

### Items NOT in this bucket (named explicitly)

- **A separate `frontend-arch-guard` skill.** Rejected on principle — would be a parallel duplicate path (P2) of the existing `architecture-guard`. The four B4 items above are the principled alternative: extend the one skill, extend the one hook, add targeted lints.
- **The four FE-ARCH-NN refactors themselves** (the matter convergence gate, the `useBreakpoint` primitive, skeleton-as-mode, `lib/format/`). Those are not enforcement work — they are the actual architectural fixes. They live in BUGS.md §0 as the "Target architecture" sections of each FE-ARCH entry and get prioritized via clusters, not this backlog.

---

## Recommended ship order

If you actually want to start retiring sticky notes, the cheapest-first / highest-value-first order is:

1. **B1.8** — hook fix for `.md` files (5 min, prevents hook credibility loss)
2. **B1.1** — user-prompt sniffer for "is broken" (~20 min, would have prevented LLM-005)
3. **B1.2** — `result.get()` CI lint (~15 min, real wall, deletes MEMORY.md entry)
4. **B1.3** — Bash hook for one-sided Railway deploys (~10 min, smart sticky note)
5. **B1.4** — hook detection of new ARCH-003 call sites (~20 min, smart sticky note); follow with the AST test (~one afternoon, real wall for one task)
6. **B1.5** — migration-file hook for unversioned `CREATE OR REPLACE FUNCTION` (~15 min, smart sticky note)
7. **B1.6** — frontend codegen for ARCH-006 (~half day, real wall, highest single-item value)
8. **B1.7** — Python↔Postgres codegen for the column-name rule (~half day, real wall, deletes 2 MEMORY.md entries)

**Frontend additions (Bucket 4, added 2026-05-25):**

9. **B4.2** — `zoom_out_guard.py` hook extension for frontend high-risk paths/symbols (~30 min, smart sticky note, highest leverage in Bucket 4). Requires **B1.8** landed first or it false-positives on every doc edit.
10. **B4.1** — extend `architecture-guard/SKILL.md` with FE-ARCH-01..04 checklists (~30 min, smart sticky note)
11. **B4.4** — markdown lint enforcing `**Detector:**` on every `### (FE-)ARCH-NN` entry in BUGS.md (~30 min, real wall — locks in the detector discipline; retrofit ARCH-001..007 in same PR)
12. **B4.3** — build `frontend/src/lib/format/` + ESLint rule banning raw `toLocaleDateString` (~half day, real wall, kills FE-ARCH-04 category + the 4 acute plural bugs in FE-015)

Items 1–5 are roughly **two hours total**. Items 9–11 add **another ~90 min** of smart-sticky-note + markdown-lint work. Items 6, 7, 12 are each **half a day** and each delete a category of bug.

After items 1–5 land, MEMORY.md should shrink by ~3 entries (B1.2, B1.4 partial, plus deletions noted in the "Action on landing" notes above). After items 6–7 land, MEMORY.md should shrink by ~2 more entries. After B4.3 lands, FE-015 in BUGS.md §10 should be marked FIXED and the 4 hardcoded-plural bug rows can be retired. The shrink is the metric. **A growing MEMORY.md (or growing BUGS.md OPEN count) is the symptom; a shrinking one is the fix.**

---

## Cross-references

- `ARCH-PATTERNS.md` — the ten abstract patterns this backlog enforces against
- `BUGS.md` section 0 — concrete ARCH-001..007 (backend) + FE-ARCH-01..04 (frontend) entries
- `BUGS.md` §10 — Frontend audit findings FE-001..022 (2026-05-20)
- `FRONTEND-AUDIT-2026-05-20.md` — evidence snapshot for the FE-### items
- `.claude/skills/architecture-guard/SKILL.md` — current enforcement skill (covers backend; Bucket 4 extends it to frontend)
- `.claude/hooks/zoom_out_guard.py` — current smart-sticky-note layer (universal zoom-out + architecture-guard injection)
- `MEMORY.md` — the file being audited; the deletion-on-landing actions in Bucket 1 specify what to remove from it
- `CLAUDE.md` — top-level rules; Deployment section is the source of B1.3
- `C:/Users/Jyotsna/.claude/projects/E--Career-coaching-100x-LDIP/memory/verification-failures.md` — full post-mortem that produced the MEMORY.md rule promoted by B1.1
