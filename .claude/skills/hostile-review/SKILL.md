# Hostile Review — Post-Implementation Pre-Deploy Verification

> **When to invoke**: After code is written, before deploying. This is not
> optional — the deploy hook enforces it.
>
> **Why this exists (2026-05-14)**: The blast-radius-research skill catches
> architectural problems BEFORE implementation. But three categories of bugs
> slip through because they can only be found by interrogating ACTUAL CODE:
>
> 1. **Runtime behavior mismatches** — Celery decorator behavior when called
>    inline vs via `.delay()`. Framework magic that changes semantics.
> 2. **Infrastructure limits** — Upstash 100MB record size limit. Redis
>    serialization costs. gRPC timeout defaults. These don't appear in code.
> 3. **Concurrent execution races** — what happens when two instances of the
>    same task run simultaneously? What happens when a sweep fires during
>    processing? These require simulating parallel execution.
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

---

## Output Format

For EACH item, answer one of:
- **VERIFIED** — with file:line proving it works
- **BUG FOUND** — with file:line and exact failure scenario
- **RISK** — works but has a failure mode under specific conditions
- **N/A** — genuinely not applicable (state why in one sentence)

Do not say "should work" without line numbers.
Do not skip any applicable item.
