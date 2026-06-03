# Hostile Review — Post-Implementation Pre-Deploy Verification

> **When to invoke**: After code is written, before deploying. This is not
> optional — the deploy hook enforces it.
>
> **Why this exists (2026-05-14, expanded 2026-05-25)**: The blast-radius-research
> skill catches architectural problems BEFORE implementation. But these categories
> of bugs slip through because they can only be found by interrogating ACTUAL CODE:
>
> 1. **Runtime behavior mismatches** — Celery decorator behavior when called
>    inline vs via `.delay()`. Framework magic that changes semantics.
> 2. **Infrastructure limits** — Upstash 100MB record size limit. Redis
>    serialization costs. gRPC timeout defaults. These don't appear in code.
> 3. **Concurrent execution races** — what happens when two instances of the
>    same task run simultaneously? What happens when a sweep fires during
>    processing? These require simulating parallel execution.
> 4. **Attribute/method mismatches** — `service._client` vs `service.client`.
>    Import checks and type checks pass because Python evaluates function
>    bodies at call time. Only caught at runtime. (2026-05-25: Section H)
> 5. **Silent failure from copied patterns** — `try/except` that's correct
>    for one direction (promote) is dangerous for the reverse (demote).
>    The asymmetry is invisible to review. (2026-05-25: Section I)
> 6. **Invisible features** — backend endpoint deployed with no UI path to
>    trigger it. Feature marked PASSED via API but unreachable by users.
>    (2026-05-25: Section J)
>
> Blast-radius asks "what does the system look like?" This skill asks
> "given this specific code, what are all the ways it can fail?"

---

## How to Run

1. **Identify all changed files** — `git diff --name-only` or list from context.
2. **Spawn a research agent** with the checklist below, filling in the
   file-specific sections. The agent must READ every changed file in full.
3. **Review the results** — fix any BUG FOUND items before deploying.
   RISK items are accepted knowingly.

---

## The Checklist

For each changed file, the agent must answer every applicable item.
Skip items only if they're genuinely irrelevant (e.g., "queue routing"
for a frontend-only change).

### A. Function Call Boundaries

For every function call that crosses a boundary (task→task, service→task,
inline call of a decorated function):

- What **decorators** does the called function have? Do they behave
  differently when called inline vs dispatched? (`bind=True`,
  `autoretry_for`, `rate_limit`, `time_limit`)
- What does `self` refer to? What does `self.request` return?
- If the function **raises**, where is the exception caught? Trace the
  full propagation path to the final handler. Does status get updated?

### B. Serialization & Infrastructure Limits

For every value that crosses a process/network boundary:

- What gets serialized into Redis/Celery messages? How large is it?
- What gets serialized into HTTP requests (Supabase, external APIs)?
- Are there **size limits** on any of these channels? (Upstash: 100MB/key.
  Supabase REST: ~2MB payload. Document AI: 15 pages/request.)
- If the payload exceeds the limit, what error appears? Is it caught?

### C. Concurrent Execution

For every task or function that could run twice for the same input:

- What happens if **two instances** run simultaneously with the same ID?
- Is there an **idempotency guard**? What data does it check? Is there a
  window between the check and the action where a race can occur?
- Do both instances **insert** data? Is there a unique constraint? If not,
  are duplicates harmful?
- Do both instances **dispatch** downstream tasks? Does the downstream
  task handle being called twice?

### D. Error Handling Completeness

For every `try/except` block in changed code:

- What exceptions are caught? What's re-raised vs swallowed?
- If status is set to FAILED in the except block, what happens if THAT
  call also fails? Is it swallowed (`except Exception: pass`)?
- Is there a **safety net** (link_error, chain error callback, sweep)?
  Or is the except block the only recovery?

### E. Missing Wiring

For dispatch calls (`.apply_async()`, `.delay()`, `chain()`):

- Is `link_error` wired? For ALL dispatch paths (not just the chain path)?
- Is the correct **queue** specified? Does it match the routing table?
- Are **all required arguments** passed? Check the function signature
  against what's dispatched.
- If a callback/chain step was removed, is its work still done somewhere?

### F. Dead Code & Dangling References

- Are there **imports** of removed functions/tasks anywhere in the codebase?
- Are there **task names** registered in beat/config that reference removed tasks?
- Are there **old messages** in Redis queues that reference removed task names?
  What happens when the worker picks them up?

### G. Data Flow Integrity

- For every database write: is it an **insert** or **upsert**? If insert,
  is there a unique constraint that prevents duplicates?
- For every database read used for a decision: can the data change between
  the read and the action? (TOCTOU race)
- For every status update: can two tasks set conflicting statuses? Which wins?

### H. Service Object Attribute Verification

> **Why this exists (2026-05-25)**: `document_service._client` passed import
> checks, type checks, and hostile review — but the attribute is `client`,
> not `_client`. Python only evaluates function bodies at call time. The
> `try/except` swallowed the `AttributeError`, returning HTTP 200 while
> leaving the document invisible in both UIs. Found only in production logs.

For every new `service_object.attribute` or `service_object.method()` access
in changed code, where the service is injected (DI, function arg, singleton):

- **Open the service class file.** Find `__init__`. Verify the attribute
  is assigned there. Do not infer from variable names elsewhere.
- Write: **VERIFIED: `ClassName.__init__` at file:line assigns `self.X`**.
  "Should work" without a line number is not acceptable.

### I. Silent Failure State Analysis

> **Why this exists (2026-05-25)**: A "log-but-don't-fail" `try/except`
> was copied from promotion (where it's correct — type change is the safe
> primary mutation) to demotion (where it's dangerous — the
> `migrated_to_library=False` clear IS the safety-critical mutation). The
> PATCH returned 200 while leaving the document invisible. The asymmetry
> between "the same pattern in two directions" was invisible to review.

For every `try/except` that catches and does NOT re-raise:

- **Enumerate the partial write state** if the block throws at each line.
  Which fields have been written? Which haven't?
- **Is partial state worse than failure?** "Worse" = the user reaches a
  state they cannot recover from through normal UI (invisible document,
  double-charged, locked with no unlock, orphaned with no cleanup path).
- If partial state is worse than failure: the except must either
  (a) **re-raise**, or (b) **be split** — the safety-critical write goes
  outside the swallowed try; the recoverable side-effect stays inside.
- **Watch for copied patterns**: if the same `try/except` shape exists for
  both directions of an operation (promote/demote, create/delete,
  grant/revoke), verify the contract is correct for BOTH directions.
  The safe direction for one is often the dangerous direction for the other.

### J. Backend-Frontend Parity

> **Why this exists (2026-05-25)**: Gap 5 deployed a working PATCH demotion
> endpoint. But `DocumentActionMenu.tsx` has "Set as Act" for non-act docs
> and nothing for act docs. No UI path exists to trigger the demotion. The
> feature was deployed, live-tested via direct API call, and marked PASSED —
> but is unreachable by users. "Backend ready, frontend deferred" is only
> acceptable when explicitly named and tracked.

For every new or changed API endpoint that affects user-visible behavior:

- **Name every user action** the endpoint enables. ("Change document type
  back from Act to Case File")
- **Does a UI path exist** that a user can find and execute without knowing
  API internals? Name the component and the interaction.
- If no UI path exists: **BUG FOUND** — unless a tracked gap exists in
  BUGS.md with severity P2+ and the backend state cannot produce a
  user-visible broken state without the UI path.
- If the backend state CAN produce a broken/confusing state without the
  UI path (e.g., document invisible in both panels): this is a **BUG**,
  not a deferral. The UI path must ship with the backend, or the backend
  must refuse the operation until the UI is ready.
- For every UI action identified above: **trace the VISIBILITY CHAIN from
  the page root to the interactive element.** The component rendering is
  necessary but not sufficient — every ancestor must also be visible.
  Specifically:
  - What **query** populates the list/table/panel that contains this element?
  - Does that query have WHERE/filter clauses that **exclude** the target
    entity? (e.g., `migrated_to_library=False` filters out promoted acts)
  - Does any parent component have conditional rendering
    (`{condition && <Child/>}`) that hides the subtree?
  - Can the user **navigate to a state** where the element is simultaneously
    rendered AND its parent is visible? Name the exact click sequence.
  - If no click sequence exists: **BUG FOUND** — dead UX. The component
    code is correct but unreachable.

> **Why the visibility chain was added (2026-05-25)**: PROD-003 added
> "Set as Case File" to `DocumentActionMenu.tsx`. Section J confirmed the
> component renders when `canEdit && isAct`. But promoted acts have
> `migrated_to_library=True`, which the document list query filters out.
> The row never appears → the menu never mounts → dead UX shipped to
> production. The component was code-correct but parent-invisible.

### K. Production Baseline Check

> **Why this exists (2026-05-25)**: PROD-001 (`identity_nodes.document_id`
> doesn't exist) and PROD-002 (`act_resolutions` FK orphan) were pre-existing
> errors in the same subsystem as the deployed changes. They caused confusion
> during live testing — unclear whether errors were regressions or pre-existing.
> API-001/002/003 (phantom column queries returning 400 on every request) lived
> in production for weeks before anyone checked logs. GAP-18 (library recovery
> dead code) was invisible because the early return produced no error log.

Before deploying changes to any subsystem:

- **Check production logs** (last 24h) for errors in the subsystem being
  changed. Use: `railway logs -s <service>` and grep for ERROR, 400, 500,
  "does not exist", "constraint", "not found" in the relevant code area.
- **Check for known-broken queries**: If the change touches a DB table,
  grep production logs for that table name + error codes.
- **List all pre-existing errors found.** For each: is it related to the
  change being deployed? Could it interfere with testing the new change?
- If pre-existing errors exist in the same code path: **fix them in the
  same deploy** or **document them as known noise** so they don't mask
  regressions during post-deploy verification.

### L. Code Path Exercisability

> **Why this exists (2026-05-25)**: GAP-11 added `library_document_id` to
> cost tracking. But: (a) pypdf extraction is free — no cost row generated
> for digital PDFs, (b) test PDFs produced 0 chunks — embedding never ran.
> The code path that writes `library_document_id` to `llm_costs` can ONLY
> fire for scanned PDFs large enough to chunk. The fix was "verified" by
> uploading a digital PDF, which exercises zero of the changed code.
> Same pattern: GAP-17 requires Supabase outage; GAP-19 required child chunks.

For every changed code path:

- **What input triggers this code path?** Be specific: file type, size,
  content characteristics, document state, external service behavior.
- **Can you provide that input during testing?** If the path requires:
  - A scanned PDF (Document AI) but you only have digital PDFs (pypdf): NO
  - A document >30 pages but test docs are <10 pages: NO
  - An external service failure (Supabase down, Gemini 429): NO
  - A specific document type that gets filtered differently: MAYBE
- If NO: **mark the fix as "DEPLOYED BUT UNEXERCISED"** in the deploy
  report and BUGS.md. Do NOT mark it as FIXED/VERIFIED.
- If the path has a `try/except` that swallows errors: the path is
  ESPECIALLY dangerous when unexercised — silent failure means you won't
  know it's broken until someone checks logs or data.

---

## Post-Deploy Verification Protocol

> Run within 15 minutes of every deploy. This is not optional — pre-deploy
> skills prevent shipping bugs, post-deploy checks prevent bugs that persist
> undetected. Added 2026-05-25 after PROD-001/002 were found only because
> we happened to look at logs during live testing.

1. **Log scan**: Check production logs for deployed service(s) for the last
   15 minutes. Filter for ERROR, WARN, 400, 500, "does not exist",
   "constraint", "not found".
2. **Regression check**: For each endpoint/task touched by the deploy,
   trigger one execution. Check response code AND response body (200 with
   empty data is often a silent failure).
3. **Data verification**: For each DB write in the deployed code, query
   the table and verify at least one row was written with expected values.
   If the write path hasn't fired yet, note as "UNEXERCISED" and schedule
   a follow-up.
4. **Pre-existing error triage**: Any errors found that are NOT in the
   deployed code: check if they're in BUGS.md. If not, file them.

---

## Output Format

For EACH item, answer one of:
- **VERIFIED** — with file:line proving it works
- **BUG FOUND** — with file:line and exact failure scenario
- **RISK** — works but has a failure mode under specific conditions
- **N/A** — genuinely not applicable (state why in one sentence)

Do not say "should work" without line numbers.
Do not skip any applicable item.
