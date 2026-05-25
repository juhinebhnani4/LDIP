# ARCH-PATTERNS.md — Convention-Where-Structure-Belongs Patterns

> Created 2026-04-13 from a second-pass architectural review.
>
> This file is the **abstract catalog**. The concrete instances live in `BUGS.md` section 0 (ARCH-001 through ARCH-007). The enforcement checklist for the three most-violated patterns lives in `.claude/skills/architecture-guard/SKILL.md`. The actionable backlog of guardrails to ship lives in `GUARDRAIL-BACKLOG.md`.
>
> The purpose of this file is to make the **shapes** memorable so they can be spotted in code review *before* they become a new ARCH-00X entry.

---

## The frame

Every architectural debt in LDIP's history has had the same root: **implicit coordination through convention instead of explicit coordination through structure**.

A useful test for any proposed change: *is this fix a **wall** or a **sticky note**?*

- **Wall**: a thing the wrong action physically cannot take. A `try/finally` that releases a lock no matter how the function exits. A foreign key constraint that refuses an orphan row. A generated TypeScript type that fails the build if it drifts from the Pydantic source. Walls survive forgetting.
- **Sticky note**: a thing the right action depends on someone reading. A code comment that says "remember to call X." A MEMORY.md rule. A docstring. An entry in CLAUDE.md. Sticky notes only work if every future author reads them every time. They are reminders, not constraints.

Every one of the ten patterns below is **a place where LDIP has a sticky note where a wall belongs**. The fix is always shaped the same way: replace the convention with structure that makes the right thing the only possible thing.

A second test: *if this rule is true, is its existence in our docs a sign that we don't yet have a wall?* If yes, the docs entry is itself debt. **A rule that has survived past its wall is debt** — it tells future authors there's vigilance work to do when in fact the wall already exists, and it crowds out the rules that *do* still need vigilance.

---

## P1 — "Remember to call X from all exit paths of Y"

**The smell**: a rule (in code comments, MEMORY.md, or CLAUDE.md) that says "every exit path of task X must dispatch task Y" or "every failure handler must release the lock" or "all callers must update the status." Counted versions: "lock release has 14 call sites." Authored versions: "the Nth call site of `_release_pipeline_lock_safe`."

**Why it's a sticky note**: humans (and Claudes) forget. Every new exit path is a place where someone has to remember to ring the bell. The Nth time, someone won't.

**The wall version**:
1. **`try/finally` or context manager** — the cleanup runs on every exit because the language guarantees it, not because the author remembered.
2. **Decorator wrapping the task** — the dispatch happens after the wrapped function returns, regardless of how it returned.
3. **Reconciler / watchdog** — instead of every author signaling correctly, a periodic process *observes the database* and derives the correct state from what it sees. This is how Airflow, Temporal, and every mature workflow engine handle pipeline completion.

**Concrete instance**: ARCH-003 (pipeline completion as "remember to signal"). 14 lock-release call sites. The MEMORY.md rule *"`extract_citations` MUST dispatch `detect_contradictions` from ALL exit paths"* is itself an instance of this pattern preserved as documentation.

---

## P2 — "Two implementations of the same logical thing, branched on a property of the input"

**The smell**: `if size > N: do_thing_a() else: do_thing_b()` where `do_thing_a()` and `do_thing_b()` are each substantial code paths (hundreds of lines, their own files, their own dispatch logic). "Special case for Act documents." "Different chain for large uploads." A fork in the orchestration layer keyed on a document property.

**Why it's a sticky note**: every change to the underlying logic has to be made twice and stay in sync. There is nothing structural that enforces the sync. The two paths drift the moment one author edits one of them and forgets the other.

**The wall version**:
1. **Parameterize a single path.** The optimization for the special case lives *inside* a stage, not as a top-level fork in the orchestrator. A small document is a chunked document with one chunk.
2. **Fan-out / fan-in chord that's identical regardless of input size.** The shape of the pipeline is constant; only the per-chunk count varies.

**Concrete instance**: ARCH-001 (parallel small-doc chain vs chunked path). 6,471 lines in `document_tasks.py`, 1,926 in `chunked_document_tasks.py`, both implementing what is logically the same pipeline.

---

## P3 — "Routing without process isolation"

**The smell**: Celery `task_routes` mapping tasks to queues. Or topic names in a message bus. Or "we'll use a separate queue for the heavy work." Looks like isolation. Smells like isolation. Drawn on the floor like isolation.

**Why it's a sticky note**: queues only buy isolation if separate worker processes consume them exclusively. One process draining four queues turns the routing into decoration. Greenlets serialize the moment work becomes CPU-bound or blocks on a sync HTTP client. Soft timeouts and rate limiters do not isolate workloads — only **separate processes** do.

**The wall version**:
1. **Any new queue ships with the worker that consumes it exclusively.** Cite the `railway.toml` line that adds the service. If you can't ship the worker in the same PR, don't ship the queue.

**Concrete instance**: ARCH-002 (single worker on `-Q default,llm,heavy,low` with `--pool=gevent --concurrency=50`). `task_routes` are configured beautifully and irrelevantly.

---

## P3b — "Shared upstream API quota with no partitioning"

**The smell**: a new task class that calls Gemini (or any rate-limited upstream). "We'll add retry-with-backoff on 429s so it self-heals." "Just bump the quota." Multiple LLM-bound task classes all reaching for the same Google account.

**Why it's a sticky note** *and* worse: even with separate worker processes per queue (P3 fixed), every LLM-bound task ultimately calls the same Gemini account, which enforces *one* per-minute request quota. When any single task class saturates that quota, every other LLM task in the system gets `429 Too Many Requests`. Worker isolation does not help — the workers exist, they're just all stuck on hold with the same phone line. Retry-with-backoff makes it *worse*: the backed-off requests pile up and the next quota window gets immediately re-saturated.

**The wall version** (one of):
1. **In-process token bucket** in front of the LLM client, partitioned by task class. Citations gets X req/min, aliases gets Y, etc., summing to ≤ the global quota. One task class running hot cannot starve the others.
2. **Separate GCP projects** for hot task classes, each with its own native quota at the source.

**Concrete instances**: ARCH-002 deeper failure mode (Gemini 429s recurring across all task classes during any heavy alias-resolution run). E2E verification (2026-04-17) confirmed this extends to **OpenAI as a second unpartitioned upstream**: `detect_contradictions` calls GPT-4o with no rate limiter (60 concurrent calls possible), while Gemini calls in the same engine ARE rate-limited — asymmetric enforcement, same system (E2E-008).

---

## P4 — "Helper in `core/` that *can* be called but isn't required to be"

**The smell**: a utility module sitting at `app/core/` (e.g. `cost_tracking.py`, `llm_rate_limiter.py`, `audit_service.py`) that provides the right thing for code to call, but every call site has to remember to call it. The infrastructure exists; using it is a convention.

**Why it's a sticky note**: the failure mode is *absence* of a call, not presence. Nothing greps positive for "you forgot to track cost." A new code path that calls Gemini directly works fine — it just isn't logged, isn't rate-limited, isn't bucketed against the right quota.

**The wall version**:
1. **The helper becomes the only API to do the underlying operation.** You literally cannot call Gemini except through the gateway. The gateway exposes domain-level methods (`extract_citations(text)`, `classify_event(date_phrase)`) — never raw `generate_content`. Cost logging, rate limiting, model selection, retry behavior all live inside the gateway, not at every call site.
2. **CI lint as a bridge**: a script that fails the build if `from google.genai import types` appears outside the gateway directory. Locks in progress: the count can only go down, never up.

**Concrete instance**: ARCH-004. `gemini_client.py` exists and is imported by ~15 files, but 14 files reach past it with `from google.genai import types` and build their own request payloads. The infrastructure is *aspirational architecture that never landed*.

---

## P5 — "Hand-mirrored types across two repos / two layers / two languages"

**The smell**: a Python type and a TypeScript type that are supposed to match. Or a Pydantic model and a SQLAlchemy model. Or a Postgres column and a Python attribute name. The only thing keeping them in sync is human attention. A field rename in one place produces zero errors in the other place — it just produces silently wrong runtime behavior.

**Why it's a sticky note**: drift is invisible. The MEMORY.md rule *"`documents` table uses `filename` (not `name`), `ocr_error` (not `error_message`)"* is itself an instance of this pattern preserved as documentation. The fact that this rule exists means we don't have a wall.

**The wall version**:
1. **Codegen.** Generate the second representation from the first. FastAPI emits OpenAPI → use `openapi-typescript` to generate frontend types. Postgres has the column list → generate Python models from `psql \d`. Renaming becomes a compile error in seconds, not a UI bug in days.
2. **Once the wall exists, *delete the corresponding rule from MEMORY.md*.** The rule's continued presence after the wall lands is debt.

**Concrete instances**: ARCH-006 (frontend hand-mirrors backend Pydantic — 36 files in `frontend/src/lib/api/`). Also the `documents` column-name rule in MEMORY.md (Python hand-mirrors Postgres). Same pattern, two boundaries.

---

## P6 — "`CREATE OR REPLACE FUNCTION` on a function with cross-repo callers"

**The smell**: a Postgres function whose signature can change without a version bump, and whose callers live in a different repository that has to redeploy in lockstep. `CREATE OR REPLACE FUNCTION search_chunks(...)` mutates the contract in place. There is no rollback target — `git revert` on the migration is meaningless because the function in production has already been overwritten.

**Why it's a sticky note**: a search RPC migration is a coordinated cross-repo deploy pretending to be a single function call. The convention is "remember to update both sides simultaneously." It will fail the day someone forgets.

**The wall version**:
1. **Version the RPCs explicitly.** New signatures land as `search_chunks_v3` alongside the existing `_v2`. The Python client picks the version it expects via a config constant. Migration deploy and API deploy decouple. After the API has cut over for a safe window, `_v2` is dropped in a separate migration.
2. **CI lint as a bridge**: fail any new migration containing `CREATE OR REPLACE FUNCTION search_` (or any cross-repo function name from an allowlist) without a version suffix.

**Concrete instance**: ARCH-005. `search_chunks` / `search_documents` / `hybrid_search` modified across 11 migrations, all `CREATE OR REPLACE`, no version bumps.

---

## P7 — "Signaling failure in a language the framework doesn't speak"

**The smell**: A task returns a status value (`{"status": "chunking_failed"}`) to indicate failure, but the orchestration framework (Celery chains, Promise chains, HTTP middleware pipelines) only recognizes **exceptions/rejections** as failure. The return value is invisible to the framework — it's "success." Every downstream consumer must manually inspect the returned dict and decide to skip.

**Why it's a sticky note**: The framework already has a structural mechanism for failure propagation (exceptions stop Celery chains, rejected Promises skip `.then()`, thrown errors trigger Express error handlers). By returning a value instead, you opt out of the wall and replace it with "every downstream task must remember to check the status field." That's P1 at the framework boundary — and it's invisible because each task appears to work in isolation.

**The wall version**:
1. **Use the framework's native failure mechanism.** In Celery: raise an exception on terminal failure (chain stops structurally). In Promises: reject (`.catch()` fires). In HTTP middleware: throw (error handler runs). The framework becomes the wall — downstream code never runs on bad input because it structurally can't.
2. **Attach framework-level error callbacks** (`link_error` in Celery, `.catch()` in Promises) for centralized cleanup, rather than distributing cleanup across every task's catch block.

**The test**: "If I add a new task to this chain and forget to check `prev_result`, does bad data silently flow through?" If yes, you're speaking a language the framework doesn't understand.

**Concrete instance**: DPP-002. All 5 chained document tasks return failure dicts. Celery sees every failure as success. 3 downstream tasks have manual "skip if prev failed" blocks that are structurally unnecessary if exceptions were used.

---

## P8 — "Sibling tasks with inconsistent contracts"

**The smell**: Tasks at the same pipeline level (same chain, same role, same lifecycle) have **different cleanup behavior** on failure. Some call `_mark_job_failed`, others don't. Some release the pipeline lock, others don't. No structural definition of "what every task at this level must do on failure" exists — each author independently decided, and the decisions diverged.

**Why it's a sticky note**: When you add a new task to the chain, nothing tells you what cleanup is required. You copy from the nearest sibling, which may itself be incomplete. The inconsistency is invisible — there's no contract to violate, just a convention that was never fully followed. The missing cleanup doesn't cause a visible error; it causes a silent state leak (orphan locks, jobs stuck in PROCESSING) that only surfaces hours later.

**The wall version**:
1. **A single error callback** on the chain/pipeline that handles all cleanup centrally. Individual tasks don't need to remember — the framework does it.
2. **A base class or decorator** that enforces the cleanup contract structurally — every task wrapped by it gets the required cleanup on failure automatically.
3. **An integration test** that asserts: "for every task in the chain, failure triggers X, Y, Z cleanup." The test IS the contract.

**The test**: "If I look at any two sibling tasks' failure handlers, are they doing the same set of cleanup operations?" If not, one of them has a bug — but nothing in the code tells you which one.

**Concrete instance**: DPP-002 investigation. Of 5 chained tasks: `validate_ocr` and `chunk_document` call both `_mark_job_failed` and `_release_pipeline_lock_safe`. `calculate_confidence` calls `_mark_job_failed` but NOT `_release_pipeline_lock_safe`. `embed_chunks` and `extract_entities` call `_release_pipeline_lock_safe` but NOT `_mark_job_failed`. Three different cleanup behaviors for five siblings in the same chain.

---

## P9 — "Surface audits hide orchestration debt"

**The smell**: A bug at an orchestration boundary (how tasks coordinate, how state is handed off, how pipelines complete) is described by its surface symptom — "wastes ~5 seconds," "status sometimes wrong," "retry doesn't work." The audit accepts the symptom description and sizes the fix accordingly. The actual blast radius is 5-10x larger because orchestration bugs are never local.

**Why it's a sticky note**: Sizing bugs by symptom description is a convention. The assumption "this is about as big as it looks" works for leaf-node bugs (wrong format string, missing null check) but systematically fails for coordination bugs. The same root cause (return-dict-as-failure) produced: 5 tasks with wrong error signaling, 3 tasks with manual skip blocks, 3 tasks with incomplete cleanup, 1 library pipeline with identical issues, 0 error callbacks where there should be 2. A "medium-severity 5-second waste" was actually a 16-task, 28-call-site architectural mismatch.

**The wall version**:
1. **Mandatory blast-radius trace for coordination bugs.** Any bug that involves task coordination, state handoff, pipeline sequencing, or completion signaling must get a full call-chain trace BEFORE sizing — not after. The trace is the wall; it physically prevents underestimation.
2. **The trace checklist**: (a) How many tasks/functions participate in this coordination? (b) How many are affected by the root cause? (c) Is the same pattern replicated in other pipelines? (d) What cleanup/state-management is inconsistent across siblings (→ P8)?
3. **The heuristic**: If a bug touches anything in the "forbidden surface" (pipeline chains, worker queues, status/lock management, task dispatch), assume the blast radius is the entire pipeline until proven otherwise.

**The test**: "Did we trace the full call chain before writing the fix, or did we accept the symptom description as the scope?" If the latter, the fix is probably incomplete.

**Concrete instance**: DPP-002. Listed as "Medium severity, Low complexity — config change." Actual scope: 8 files, 16 tasks, 28 cleanup call sites, 3 missing cleanup bugs, 0 error callbacks. The deep analysis that revealed this took one investigation session; the surface audit that missed it was instantaneous.

---

## P10 — "Fire-and-forget classification with no recovery path"

**The smell**: A decision about an object's type/category/route is made once at creation time, with no intelligence and no ability to correct it later. "The user chose the right document type." "The system will figure it out." The decision is permanent — the object enters a pipeline that produces irreversible side effects based on the classification, and there's no undo.

**Why it's a sticky note**: The classification depends on the user or caller remembering to choose correctly. But: (a) there may be no UI to choose at all, (b) the user may not know the right answer, (c) auto-detection may not exist or may be incomplete, (d) even if the wrong choice is noticed later, there's no reclassification action that undoes the downstream work.

**The wall version**:
1. **Auto-detection at the gate.** Before the object enters any pipeline, run a classifier (heuristic, rule-based, or LLM). The classifier pre-selects the type; the user confirms or overrides. The gate exists for ALL entry paths — not just the one the most common users see.
2. **Recovery path.** If classification is wrong, a "reclassify" action exists that: (a) stops or undoes wrong-pipeline work, (b) moves the object to the correct pipeline, (c) cleans up garbage side effects. Without this, every misclassification is permanent damage.
3. **Post-processing reconciler.** After the first pipeline stage produces data (e.g., OCR text), re-evaluate the classification. Text full of "Section 1", "Be it enacted", "WHEREAS" is a statute, not a case file. Flag for reclassification if the data disagrees with the initial label.

**The test**: "If the user uploads an object with the wrong type, what happens? Can they fix it? Does the system notice? Or does it silently produce garbage and waste compute?" If the answer is "garbage and waste" — you need a gate, a recovery path, or both.

**Concrete instance**: ARCH-007. User uploaded "TORTS Act 1992.pdf" — a statute. System classified it as Case File (the default — no UI to choose otherwise). Full expensive pipeline ran (OCR → entities → citations → contradictions — all nonsensical for a statute). Document AI timed out on 22 pages. The library system has 4 entry paths for Acts but none have auto-detection, and misclassified documents have no recovery path. The backend plumbing for `document_type=act` exists and works — but the frontend never sends it.

---

## How to use this catalog

When reviewing any proposed change — yours, a teammate's, or one Claude is about to write — ask in this order:

1. **Does the fix match one of these nine patterns?** If yes, name which one. Don't ship the local version of the fix; propose the wall version. (The architecture-guard skill formalizes this for the three most dangerous patterns; this file extends it to all nine.)
2. **If you must ship the sticky-note version anyway** (deadline, scope, etc.), mark it explicitly as a debt — log it in `BUGS.md` section 0 as a new entry, and note in the commit message that an architectural waiver was taken. Don't let it slip in unmarked.
3. **If the fix is to add a new MEMORY.md rule**, ask whether the rule itself is an instance of one of these patterns. *"Remember to call X from all exit paths"* is P1. *"Remember to use the right column name"* is P5. If the rule is itself a sticky note disguised as a fix, you have two debts now: the original bug, and the rule that papers over it.

A rule in MEMORY.md or CLAUDE.md is a sticky note. Sometimes that's the right answer. Often it isn't. The wall-vs-sticky-note question is the discipline that separates those cases.

---

## Cross-references

- `BUGS.md` section 0 — concrete ARCH-001..007 (backend) + FE-ARCH-01..04 (frontend) entries; DPP-002 for P7/P8/P9; ARCH-007 for P10
- `BUGS.md` §10 — frontend audit findings FE-001..022 (2026-05-20)
- `FRONTEND-AUDIT-2026-05-20.md` — evidence snapshot (screenshots, repro, console captures) for FE-### items
- `.claude/skills/architecture-guard/SKILL.md` — enforcement checklist for the most dangerous patterns
- `GUARDRAIL-BACKLOG.md` — actionable list of walls and smart sticky notes to build, with promotion paths
- `CLAUDE.md` — top-level zoom-out rule and architecture-guard reference
