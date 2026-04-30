# Deep Research Protocol — Two-Phase Investigation

> **When to invoke**: Before implementing ANY proposed change, or before recommending solutions to any operational/architectural problem. This protocol replaces ad-hoc research prompts.
>
> **Why this exists**: Multiple failure modes observed across sessions (2026-04-21/22):
> - **Contradiction metadata**: Three passes needed because each asked a different question shape. Missed that skip-1-mention already existed, missed two tracker types with similar names, missed a was_escalated bug on the failure path.
> - **Railway cost**: Generic cloud cost advice ("enable auto-sleep, reduce concurrency, combine services") proposed without reading BUGS.md, railway.toml, or understanding how Celery workers connect to Redis. Three of four suggestions would have made ARCH-002 worse.
> - **Common root**: Research looked at the surface (symptom, file list, generic patterns) without understanding the actual system (runtime behavior, prior analysis, interaction boundaries).

---

## Phase 1: Open Exploration (Inductive — What Don't I Know?)

**Purpose**: Understand the actual system before proposing anything. This phase prevents recommending solutions that conflict with existing architecture or ignore prior analysis.

**This phase is mandatory. Skipping it is how every bad recommendation in this project's history was born.**

### 1.1 — What does the project already know?

Before analyzing any problem, check whether it's already been analyzed.

- Search `BUGS.md` for the problem domain keywords (worker, cost, concurrency, queue, sleep, memory, etc.)
- Search `ARCH-PATTERNS.md` for the pattern shape (P1-P9)
- Search `.claude/projects/*/memory/` for prior session findings
- Search `CLAUDE.md` for relevant rules or constraints

**If prior analysis exists, START FROM WHERE IT LEFT OFF.** Do not restart from scratch. State what the prior analysis found and what's new.

**Prompt fragment:**
```
FIRST: Search BUGS.md, ARCH-PATTERNS.md, and memory files for prior 
analysis of this problem. Search for: [DOMAIN KEYWORDS]. If prior analysis 
exists, summarize what it found and identify what's NEW or CHANGED since 
then. Do not re-derive known conclusions.
```

### 1.2 — What does the system actually do? (Not what should it do)

Read the actual runtime configuration, not just the application code.

- **Deployment configs**: `railway.toml`, `start-worker.sh`, `Procfile`, `docker-compose.yml`, `vercel.json`
- **Startup behavior**: What processes launch? What do they import? What memory do they consume?
- **Connection patterns**: How does the worker connect to Redis? How does the API connect to Supabase? Pull-based or push-based? Persistent or transient?
- **Runtime data**: If the question is about cost, query `llm_costs`. If it's about failures, query `processing_jobs`. If it's about timing, check logs. Code tells you what SHOULD happen; data tells you what DOES happen.

**CRITICAL — Trace the current failure path, not just the happy path:**

Before reporting "this behavior doesn't exist," trace what the system does TODAY when the user hits the problem scenario. Walk through the exact code path step by step, including every branch and edge case. The current behavior IS the baseline — you can't evaluate a proposed change without understanding what it replaces.

Specifically:
- What code path runs today when the problem scenario occurs?
- What conditions trigger each branch? What happens when those conditions are `0`, `None`, or empty?
- What does the user **actually see on screen** at the end of this path? Name the exact component that renders and the exact text/state shown. If you can't name the component and the text, you haven't finished Phase 1.

> **Why this was added (2026-04-29):** Q&A processing guard research reported "no handling exists" when in fact partial handling existed in `hybrid_search.py` (BM25 fallback + `searchNotice` rendering). The agents described what the fallback code does in the happy case but never traced what happens when `total_chunks == 0` (the fallback condition is false, user sees generic "no results"). Three gaps were only discovered by manual line-by-line code reading.

**Prompt fragment:**
```
Read the actual deployment/runtime configuration, not just the application 
code. For this problem, read: [SPECIFIC CONFIG FILES]. Then answer: What 
processes actually run? How do they connect to external services? What is 
their actual resource consumption? If live data exists that could answer 
the question directly, say what query would answer it.

THEN: Trace what happens TODAY when the user hits the problem scenario.
Walk through the exact code path step by step. At every branch condition,
check what happens when the value is 0, None, or empty. Follow the path
all the way to what the user sees on screen — name the component and the
text. If you can't, you haven't finished.
```

### 1.3 — What systems interact that aren't in the codebase?

Map the boundaries between this system and external systems that won't appear in any grep.

- **Infrastructure model**: How does Railway detect idle? How does it scale? What triggers a restart?
- **Broker model**: How does Celery discover tasks? Pull from Redis? Push? What happens if the process sleeps?
- **API quotas**: Gemini RPM, OpenAI rate limits, Supabase connection pool limits, Document AI per-page pricing
- **Timing dependencies**: What assumes something else is running? (Beat assumes worker is alive. Recovery sweeps assume beat is running. Pipeline completion assumes detect_contradictions will eventually fire.)

**Prompt fragment:**
```
What external systems interact with this component? For each: How does 
the interaction work (pull/push, persistent/transient, HTTP/broker)? 
What happens if one side goes down or sleeps? What assumptions does each 
system make about the other's availability?
```

### 1.4 — What constraints exist that aren't obvious from the symptom?

The surface problem ("RAM is too high") hides constraints that eliminate most generic solutions.

- Read the ARCH entries referenced by the problem area
- Check if proposed solutions have been explicitly REJECTED before (BUGS.md tracks these with reasons)
- Check if the problem interacts with known architectural debt

**Prompt fragment:**
```
Before proposing any solution: check BUGS.md for approaches that have 
already been REJECTED for this problem (search for "REJECTED", "DEFERRED", 
"UNSAFE"). Check if the problem area intersects with any ARCH-001 through 
ARCH-007 entries. List any constraints that would disqualify generic 
solutions.
```

### 1.5 — System-level synthesis (the zoom-out step)

**Purpose**: After tracing individual code paths (1.2) and mapping interactions (1.3), step back and evaluate the **subsystem as a whole**. Individual paths can each look reasonable while the system they form has structural gaps.

**This step catches three failure modes that 1.1–1.4 miss:**

**A. Multiple entry paths, no shared gate**: For any subsystem you're investigating, enumerate ALL entry paths and ALL exit paths. If there are multiple ways to reach the same state (e.g., a document becoming a library_document, a job reaching COMPLETED status), map all of them. Gaps between entry paths reveal classification/routing flaws — one path may have validation that another lacks.

**B. No recovery from wrong decisions**: For any decision point (classification, routing, status transition): what happens if the decision is WRONG? Is there a recovery path? If the user realizes the mistake 10 minutes later, what can they do? If the answer is "nothing" or "delete and start over," that's a structural finding — not a feature request.

**C. Design intent vs. actual architecture**: Looking at all the paths, tables, and decision points you've mapped — does this subsystem have a coherent design, or are there structural gaps (missing paths, orphaned states, parallel implementations that should be unified, dead ends)? Does the architecture match what the system is *supposed* to do?

> **Why this was added (2026-04-29):** Library document classification research traced the upload path correctly but stopped there. The library system actually has 4 entry paths, only 1 of which was exposed in the UI (and that one had no selector). The auto-fetch pipeline was sophisticated but backwards-only (detected Acts in case files, couldn't detect that an uploaded file IS an Act). Misclassified documents had no recovery path. Two parallel chunk tables existed for the same logical work. None of these flaws were visible from tracing a single code path — they only emerged when asking "does this subsystem make sense as a whole?" The user had to prompt this zoom-out twice before the structural analysis happened.

**Prompt fragment:**
```
SYNTHESIS (after completing 1.1–1.4): Step back from individual code paths.

A. How many ENTRY PATHS lead into this subsystem? Map all of them. Do they 
   all pass through the same validation/classification gate, or do some 
   bypass it? If bypassed — what breaks?

B. For the key DECISION POINTS in this subsystem: what happens when the 
   decision is WRONG? Can the user or system recover, or is it permanent? 
   If permanent — that's a structural finding.

C. Looking at the full map: does the subsystem's architecture match its 
   design intent? Are there parallel implementations that should be unified, 
   missing paths that should exist, or orphaned states with no transitions 
   out? Name any ARCH-pattern matches (P1–P6 from ARCH-PATTERNS.md).

D. Query the LIVE DATABASE for the subsystem's tables. Check: status 
   distribution (does it match what the code predicts?), data completeness 
   (do terminal-status records actually have their data?), stuck/orphaned 
   records. If data contradicts code, the data wins.

E. For any PARALLEL TABLES serving the same logical purpose: compare 
   schemas column by column. Every column in table A missing from table B 
   is a gap where future improvements to A are silently not applied to B.

D. QUERY THE LIVE DATA. Code tells you what SHOULD happen; the database 
   tells you what DID happen. For the subsystem you've mapped, run:
   - Status distribution: SELECT status, COUNT(*) GROUP BY status
   - Data completeness: Do records in terminal status actually have 
     the data they should? (e.g., completed docs should have chunks; 
     chunks should have embeddings)
   - Orphans and stuck records: Any rows stuck in non-terminal state 
     for >1 hour? Any link table rows pointing to deleted parents?
   If the data contradicts the code's claims, the data wins.

E. For PARALLEL TABLES that serve the same logical purpose (e.g., 
   chunks vs library_chunks, two embedding columns): compare schemas 
   COLUMN BY COLUMN. List every column in table A that's missing from 
   table B. For each missing column, ask: does table B's pipeline 
   populate an equivalent? If not — that's a gap where every future 
   improvement to A must be manually remembered for B.

If you can't confidently answer these five questions, you haven't 
explored enough — go back to 1.2.
```

> **Why D and E were added (2026-04-30):** Full library subsystem audit found 3 P0 gaps that were invisible from code reading alone. (D) Querying `library_chunks` revealed 77% had NULL embeddings and 1 "completed" doc had 0 chunks — the code's completion logic was vacuously true on empty sets. (E) Comparing `chunks` vs `library_chunks` column-by-column revealed `fts`, `embedding_model_version`, `text_start_offset/end_offset` all missing — meaning every search improvement to `chunks` was silently not applied to library search. Both gaps existed for months because prior research read code paths without verifying data reality.

---

## Phase 2: Directed Verification (Deductive — Validate What I Think I Know)

**Purpose**: Once you have a proposed change, verify it won't break anything and find the simplest implementation. This phase prevents implementing the wrong thing correctly.

**Only enter Phase 2 after Phase 1 has produced a specific, informed proposal.**

### 2.1 — Does this already exist?

Before building anything, check whether the behavior is already implemented.

- Grep for the **behavior**, not just the function name
- Example: "skip 1-mention entities" → grep for `< 2`, `<= 1`, `total_statements`, `len(all_statements)`

**"Does this exist?" has THREE answers, not two:**
- **YES** → report what exists and STOP
- **NO** → proceed to 2.2
- **PARTIALLY** → describe what exists, what's missing, and what's broken about the partial implementation. This is the most dangerous answer because it means the proposed change must **integrate with** existing code, not replace it. List the specific gaps.

> **Why this was added (2026-04-29):** Q&A processing guard research answered "NO, zero handling exists" when the real answer was "PARTIALLY — BM25 fallback exists but has 3 gaps (only fires on zero results, fails when total_chunks=0, no upfront check)." The binary YES/NO framing caused the agents to miss existing infrastructure that the implementation needed to integrate with.

**Prompt fragment:**
```
BEFORE tracing any blast radius: search for whether this behavior already 
exists in the codebase. Grep for the BEHAVIOR (not just the function name). 
[SPECIFIC GREP SUGGESTIONS]. 

Answer with one of: YES (stop), NO (proceed), or PARTIALLY. If PARTIALLY:
describe what exists, what's missing, and what's broken. Partial 
implementations are the most dangerous — the new code must integrate with 
what's already there, not ignore it.
```

### 2.2 — What types cross function boundaries?

At every function call in the chain, name the exact type going in and coming out.

- If two functions use different types with similar names, that's a critical finding
- Trace: where does the value ORIGINATE, and does that object survive to the PERSISTENCE layer?

**For cross-stack changes (backend → frontend or vice versa):**

Don't stop at the API boundary. Trace what happens INSIDE the receiving side when the data arrives. Specifically:
- What properties survive serialization → deserialization → object construction?
- If the backend sends a typed response (e.g., `ErrorData` with `code`), does the frontend preserve that type, or does it construct a simpler object (e.g., plain `Error`) that drops fields?
- If the frontend has conditional rendering (e.g., "show retry button if retryable"), what conditions does the received data need to satisfy? Will the new data satisfy them, or will it fall through to a wrong path?

> **Why this was added (2026-04-29):** Backend sent `{code: "DOCUMENTS_PROCESSING", retry_suggested: true}` via SSE. Frontend `useSSE.ts` created `new Error(errorData.error)` — discarding the `code` field. Then `canRetryError()` checked `instanceof ApiError` (not plain Error) → returned false → showed auto-dismissing toast instead of persistent retry alert. The data was correct at the API boundary but lost in transit through frontend internals.

**Prompt fragment:**
```
At every function call boundary, name the EXACT TYPE going in and coming 
out. If two types have similar names (CostTracker vs LLMCostTracker), flag 
this prominently. Trace: where does the value originate, and does that 
object instance survive to where it's consumed/persisted?

For cross-stack changes: trace PAST the API boundary into the receiving 
side. What properties survive? What type does the receiver construct? 
Does it drop any fields the sender included? If the receiver has 
conditional rendering or branching, will the new data satisfy the 
conditions or fall through to the wrong branch?
```

### 2.3 — What happens on every branch?

For any function that returns Optional or can raise, trace the None/exception path. For any boolean flag, trace who sets it in EVERY branch.

- Happy path alone is insufficient
- If a flag stays at its default on a path where it semantically shouldn't, that's a bug

**Apply this to EXISTING code too, not just proposed code.** When the problem involves a UX bug, trace every branch of the existing handling — including the "no handling" path — all the way to what the user sees on screen. Name the component, the text, and why it's wrong.

**Trace the full lifecycle, not just the processing phase.** For any component with setup → processing → cleanup/teardown phases (SSE streams, WebSocket connections, async operations with `finally` blocks, React `useEffect` cleanups), trace ALL three phases. Cleanup/teardown code often has its own branching logic that can overwrite state set during processing.

**Verify enumerations are complete.** When writing a list of values that should cover "all X" (all statuses, all event types, all error codes), verify the list against the source of truth (the enum definition, the database column values, the API spec). Don't write from memory — read and cross-reference.

> **Why this was added (2026-04-29):**
> - **Lifecycle miss:** `useSSE.ts` stream-end cleanup (line 620-647) had its own error-creation logic that overwrote the `DOCUMENTS_PROCESSING` error set during event processing. Research traced event processing but not stream teardown.
> - **Enumeration miss:** `_PROCESSING_STATUSES` was written with 4 of 6 pre-terminal statuses. `ocr_complete` was missed because the list was written from memory instead of cross-referencing the `DocumentStatus` enum.

**Prompt fragment:**
```
For every function that returns Optional or can raise: trace the 
None/exception path. For every boolean flag: trace who sets it in EVERY 
branch. Report any flag that stays at its default where it shouldn't.

Apply this to EXISTING code in the problem area too, not just proposed 
code. For UX bugs: trace the current code path to the screen. Name the 
component that renders and the exact text the user sees. If you can't 
name them, you haven't finished.

For components with lifecycle phases (setup → process → cleanup): trace 
ALL phases, especially cleanup/teardown. Does cleanup overwrite state 
set during processing? Does a finally block create new errors?

When writing a list of values that covers "all X": verify against the 
source enum/table/spec. Don't write from memory.
```

### 2.4 — What's the simplest plumbing?

Before modifying shared infrastructure, check if the layer above or below already has the capability.

- Adding a field to a dataclass with 46 consumers is the WRONG default
- Always prefer the smallest blast radius that achieves the goal

**Prompt fragment:**
```
Before modifying shared infrastructure: check if the layer above or below 
already has the capability. What's the smallest change (fewest files, 
fewest callers affected) that achieves the goal?
```

---

## Composite Prompt Templates

### Template A: Investigating a Problem (before recommending solutions)

```
I need to understand [PROBLEM] before recommending any solutions.

## PHASE 1.1 — What does the project already know?
Search BUGS.md, ARCH-PATTERNS.md, and memory files for prior analysis.
Search for: [DOMAIN KEYWORDS]. If prior analysis exists, summarize what 
it found and what's new/changed.

## PHASE 1.2 — What does the system actually do?
Read the actual runtime/deployment configs: [SPECIFIC FILES]. What 
processes run? How do they connect to external services? What is their 
actual resource consumption? If live data could answer this, say what 
query to run.

THEN: Trace what happens TODAY when the user hits the problem scenario.
Walk the exact code path step by step, including every branch. At each
branch, check what happens when the value is 0, None, or empty. Follow
the path to what the user sees on screen — name the component and the
text. If you can't name them, you haven't finished.

## PHASE 1.3 — What external systems interact here?
What systems outside the codebase interact with this component? How does 
each interaction work (pull/push, persistent/transient)? What happens if 
one side goes down?

## PHASE 1.4 — What constraints eliminate generic solutions?
Check BUGS.md for REJECTED/DEFERRED/UNSAFE approaches. Check if this 
intersects ARCH-001 through ARCH-007. List constraints that would 
disqualify standard advice.

## PHASE 1.5 — System-level synthesis (the zoom-out)
How many ENTRY PATHS lead into this subsystem? Map all of them. Do they 
all pass through the same validation/classification gate? For key 
DECISION POINTS: what happens when the decision is WRONG — can the user 
recover? Looking at the full map: does the architecture match the design 
intent, or are there structural gaps?

Query the LIVE DATABASE for the subsystem's tables. Check: status 
distribution (does it match what the code predicts?), data completeness 
(do terminal-status records actually have their expected data?), 
stuck/orphaned records. If data contradicts code, the data wins.

For any PARALLEL TABLES serving the same logical purpose: compare schemas 
column by column. Every column in table A missing from table B is a gap 
where future improvements to A won't be applied to B.

Report: what the system actually does, what's already been analyzed, 
what constraints exist, and what questions remain unanswered.
DO NOT propose solutions — just report findings.
```

### Template B: Verifying a Proposed Change (before implementing)

```
I'm verifying the blast radius of [PROPOSED CHANGE] in [FILE/MODULE].
Phase 1 exploration is complete — this is directed verification.

## PHASE 2.1 — Does this already exist?
Search for whether this behavior already exists. Grep for the BEHAVIOR: 
[SPECIFIC GREP SUGGESTIONS]. Answer: YES (stop), NO (proceed), or 
PARTIALLY (describe what exists, what's missing, what's broken — this 
is the most dangerous answer because the new code must integrate with 
what's already there).

## PHASE 2.2 — What types cross function boundaries?
Trace the full call chain from [ENTRY POINT] to [EXIT POINT]. At every 
boundary, name the EXACT TYPE in and out. Flag similar-named types.

## PHASE 2.3 — What happens on every branch?
For every Optional-returning or raising function: trace the failure path.
For every boolean flag: trace all setters.

## PHASE 2.4 — What's the simplest plumbing?
Check if the layer above/below already has the capability. What's the 
smallest change that achieves the goal?

Report: every file and function with line numbers. Be specific.
```

---

## Failure Modes This Protocol Prevents

| Failure Mode | Example | Which Phase Catches It |
|---|---|---|
| Rediscovering known problems | Railway analysis ignoring ARCH-002 | Phase 1.1 |
| Not understanding the runtime | "Enable auto-sleep" for a Redis-pull worker | Phase 1.2 |
| Describing happy path, missing failure path | BM25 fallback "works" but `total_chunks==0` falls through silently | Phase 1.2 (trace current failure path) |
| Not tracing to user-visible outcome | "Fallback exists" without naming what user sees on screen | Phase 1.2 (trace to screen) |
| Missing system interactions | Beat dying when worker sleeps | Phase 1.3 |
| Proposing rejected solutions | "Combine API + worker" against ARCH-002 | Phase 1.4 |
| Tracing ONE path when MULTIPLE exist | Library has 4 entry paths; research traced only upload path | Phase 1.5A (enumerate all entry paths) |
| No recovery from wrong decisions | Misclassified Act has no reclassification path — permanent garbage | Phase 1.5B (recovery from wrong decisions) |
| Individual paths look fine but system is incoherent | 4 library entry paths with no shared classification gate | Phase 1.5C (design intent vs architecture) |
| Reporting "doesn't exist" when partial exists | Q&A guard "NO" when BM25 fallback + searchNotice already built | Phase 2.1 (PARTIALLY answer) |
| Building something that exists | Skip-1-mention already implemented | Phase 2.1 |
| Missing type mismatches | CostTracker vs LLMCostTracker | Phase 2.2 |
| Cross-stack data loss at API boundary | SSE error `code` field dropped by `new Error()` | Phase 2.2 (cross-stack trace) |
| Missing failure path bugs | was_escalated wrong on screening failure | Phase 2.3 |
| Tracing only proposed code, not existing | Existing `_check_embedding_status` zero-branch never traced | Phase 2.3 (apply to existing code) |
| Missing cleanup/teardown logic | SSE stream-end overwrites error set during processing | Phase 2.3 (trace full lifecycle) |
| Incomplete enumeration from memory | `_PROCESSING_STATUSES` missing `ocr_complete` — 4 of 6 values | Phase 2.3 (verify enumerations) |
| Over-engineering the change | Modifying dataclass vs fixing plumbing | Phase 2.4 |

---

## When to Use Which Template

- **"Why is X happening?" / "How do I fix X?" / "What are my options?"** → Template A (explore first, don't jump to solutions)
- **"Implement X" / "Change Y to Z" / "Add feature W"** → Template A first (understand the system), then Template B (verify the specific change)
- **"This is a one-line config change"** → Still do Phase 1.1 (check prior analysis) and Phase 1.4 (check constraints). Skip the rest if genuinely trivial.

## Honest Limitation

This is a smart sticky note, not a wall. I have to remember to use it. The zoom-out guard hook fires automatically; this skill does not. The closest to a wall: if the zoom-out guard detects research agents being spawned, it should enforce that Phase 1 was completed before Phase 2 begins.
