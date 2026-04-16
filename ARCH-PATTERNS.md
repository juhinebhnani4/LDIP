# ARCH-PATTERNS.md — The Six Convention-Where-Structure-Belongs Patterns

> Created 2026-04-13 from a second-pass architectural review.
>
> This file is the **abstract catalog**. The concrete instances live in `BUGS.md` section 0 (ARCH-001 through ARCH-006). The enforcement checklist for the three most-violated patterns lives in `.claude/skills/architecture-guard/SKILL.md`. The actionable backlog of guardrails to ship lives in `GUARDRAIL-BACKLOG.md`.
>
> The purpose of this file is to make the **shapes** memorable so they can be spotted in code review *before* they become a new ARCH-00X entry.

---

## The frame

Every architectural debt in LDIP's history has had the same root: **implicit coordination through convention instead of explicit coordination through structure**.

A useful test for any proposed change: *is this fix a **wall** or a **sticky note**?*

- **Wall**: a thing the wrong action physically cannot take. A `try/finally` that releases a lock no matter how the function exits. A foreign key constraint that refuses an orphan row. A generated TypeScript type that fails the build if it drifts from the Pydantic source. Walls survive forgetting.
- **Sticky note**: a thing the right action depends on someone reading. A code comment that says "remember to call X." A MEMORY.md rule. A docstring. An entry in CLAUDE.md. Sticky notes only work if every future author reads them every time. They are reminders, not constraints.

Every one of the six patterns below is **a place where LDIP has a sticky note where a wall belongs**. The fix is always shaped the same way: replace the convention with structure that makes the right thing the only possible thing.

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

**Concrete instance**: ARCH-002 deeper failure mode (Gemini 429s recurring across all task classes during any heavy alias-resolution run).

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

## How to use this catalog

When reviewing any proposed change — yours, a teammate's, or one Claude is about to write — ask in this order:

1. **Does the fix match one of these six patterns?** If yes, name which one. Don't ship the local version of the fix; propose the wall version. (The architecture-guard skill formalizes this for the three most dangerous patterns; this file extends it to all six.)
2. **If you must ship the sticky-note version anyway** (deadline, scope, etc.), mark it explicitly as a debt — log it in `BUGS.md` section 0 as a new entry, and note in the commit message that an architectural waiver was taken. Don't let it slip in unmarked.
3. **If the fix is to add a new MEMORY.md rule**, ask whether the rule itself is an instance of one of these patterns. *"Remember to call X from all exit paths"* is P1. *"Remember to use the right column name"* is P5. If the rule is itself a sticky note disguised as a fix, you have two debts now: the original bug, and the rule that papers over it.

A rule in MEMORY.md or CLAUDE.md is a sticky note. Sometimes that's the right answer. Often it isn't. The wall-vs-sticky-note question is the discipline that separates those cases.

---

## Cross-references

- `BUGS.md` section 0 — concrete ARCH-001 through ARCH-006 entries
- `.claude/skills/architecture-guard/SKILL.md` — enforcement checklist for the most dangerous patterns
- `GUARDRAIL-BACKLOG.md` — actionable list of walls and smart sticky notes to build, with promotion paths
- `CLAUDE.md` — top-level zoom-out rule and architecture-guard reference
