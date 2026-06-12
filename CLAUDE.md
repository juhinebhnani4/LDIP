# CLAUDE.md - Project Configuration

## MANDATORY: Zoom Out Before Every Change (READ FIRST OF FIRST)

**This rule applies to EVERY request — bug fix, feature, refactor, "small tweak," "quick patch," everything. No exceptions.**

Before writing a single line of code or proposing an implementation, Claude must **zoom out** and answer four questions in writing in the response to the user:

1. **What is the user actually trying to achieve?** Not the literal request — the underlying goal. ("Fix this bug" might really mean "stop documents getting stuck"; "add this button" might really mean "users can't find feature X.")
2. **What is the bigger system this change sits inside?** Name the surrounding module, the data flow, the call chain, the architectural layer. One or two sentences.
3. **Does the obvious local fix make the bigger system better, worse, or unchanged?** If "worse" — name what it makes worse (duplication? coupling? a new "must remember to..." rule? a new special case in the orchestrator? a new shared-state hazard?).
4. **Is there a different change at a different level that would solve the underlying goal without the local damage?** Even if it's bigger work, name it. The user can still choose the local fix — but they choose it knowingly.

**Why this rule exists**: every P0 architectural debt in this project (ARCH-001, ARCH-002, ARCH-003 — see `BUGS.md` section 0) was built one "small reasonable local fix" at a time, across many sessions, by Claude answering the literal question instead of the zoomed-out one. No single PR looked bad. The shape only became visible after months of accumulation. The user explicitly asked for this rule on 2026-04-13 after surfacing those debts.

**What "zoom out" looks like in practice**:
- For a bug fix: don't just patch the symptom — say what category of bug this is, whether other code has the same shape, and whether the patch makes that category easier or harder to keep happening.
- For a new feature: don't just add it where it "fits" — say which existing pattern you're extending, whether that pattern is healthy, and whether you're calcifying a bad decision by extending it.
- For a refactor: don't just move code — say what the refactor enables that wasn't possible before, and what it forecloses.
- For a "small tweak": say it's small, say why it's small, and say what the bigger version would be if the user later regrets the small one.

**The zoom-out is not optional and not a section to skip when the request looks obvious.** Obvious-looking requests are exactly when local-fix bias is strongest. If the answer to question 3 is genuinely "unchanged, this is a one-line copy edit" — say so explicitly. That sentence IS the zoom-out for that change. The point is the deliberate pause, not the length of the answer.

**Skipping the zoom-out is the single biggest way Claude has hurt this project.** Don't.

---

## MANDATORY: Verify UI Changes Visually — Pixels Are the Gate (READ FIRST)

**Applies to EVERY frontend / UI change. No exceptions.**

A UI change is "verified" ONLY after you have **rendered it and looked at the actual pixels** — at the standard widths **375 / 768 / 1024 / 1440** — on every surface it touches, and described what you saw.

The **accessibility tree / DOM snapshot is NOT visual verification.** It proves an element exists; it says nothing about clipping, horizontal overflow, cramped spacing, overlap, ugly scrollbar troughs, or whether the layout looks intentional. Confirming the DOM (or a Playwright accessibility snapshot) and then calling a UI change "verified" / "LIVE-VERIFIED" is a **forbidden substitution**.

This is the UI twin of the backend gate "the live-DB read is the GATE — logs can't close it." For UI: **pixels are the gate — the DOM can't close it.** (See hostile-review Post-Deploy step 5; run the `visual-verify` skill.)

**Why this rule exists** (2026-06-11): Claude marked an FE-ARCH-02 responsive fix "LIVE-VERIFIED" off the Playwright accessibility tree, merged it, and deployed to production — where it rendered badly (full-screen sheet takeover, doubled "Ask jaanch" headers, summary content clipped off the right edge, raw scrollbar troughs). The DOM check could not see any of it. Only mark verified after eyes on pixels.

---

## MANDATORY: Explain in Plain English — Define Every Term (READ FIRST)

**This rule applies to EVERY response that contains information — analyses, recommendations, bug explanations, plans, code walkthroughs, status updates. No exceptions.**

The user is not a deep-technical reader. Whenever a response uses a technical term, jargon word, acronym, internal ID, library name, or code symbol, **explain it in simple English the first time it appears in that response.** Assume the reader does not already know what it means.

**What this looks like in practice:**
- **Acronyms / internal IDs** (FE-ARCH-01, ARCH-003, OCR, FK, RPC, CLS): spell out what it stands for AND what it means in one short clause. "FE-ARCH-01 (an ID for one frontend structure problem)".
- **Jargon** (idempotent, reconciler, convergence point, blast radius, race condition): give a one-line plain meaning, ideally with a tiny everyday analogy.
- **Code symbols** (`fetchMatter`, `error.tsx`, `documents.status`): say what the thing *does* in human terms, not just its name.
- **Library / framework names** (Celery, Next.js, Supabase, Docling): one clause on what it is and its role here.
- Prefer a short "jargon decoded" list up front for dense/technical answers, then the plain explanation. Keep the precise term too (don't dumb it down to the point of being wrong) — pair the precise term WITH its plain meaning, never replace one with the other.

**Why this rule exists**: the user explicitly asked on 2026-06-11 that information be given with terms explained simply, so they can actually understand and act on it. An accurate answer the user can't parse is a failed answer.

---

## MANDATORY: Architecture Guard (READ FIRST)

LDIP carries three foundational architectural debts (**ARCH-001, ARCH-002, ARCH-003** — top of `BUGS.md`) that have caused every P0/P1 pipeline incident in this project's history. They all share one root cause: **implicit coordination through convention instead of explicit coordination through structure**.

The three forbidden patterns:

1. **Parallel duplicate paths for the same logical work** (e.g. small-doc chain vs chunked path). Same logical pipeline, two implementations, branched at the orchestrator on a document property. Always parameterize a single path instead.
2. **Logical isolation without physical isolation** (e.g. queue routing without separate worker processes). Routing, soft timeouts, and rate limiters do not isolate workloads — only separate processes consuming separate queues do. New queues must ship with the worker that consumes them.
3. **"Remember to signal" coordination** (e.g. "all exit paths must dispatch X", lock release at 14 call sites, status updates scattered everywhere). State must be **derived from observed reality** by a reconciler whenever possible. If signaling is unavoidable, there must be exactly **one** convergence point all paths flow through — never "every author must remember."

**BEFORE writing code that touches**: the Celery document pipeline, worker queues, `documents.status` / `processing_jobs` / `job_stage_history`, pipeline locks, `_mark_job_completed` / `create_post_ocr_chain` / `_dispatch_post_entity_tasks` / any `finalize_*` task, `railway.toml` / `start-worker.sh` / worker concurrency, or admin retry/recovery endpoints — **invoke the `architecture-guard` skill** and answer its checklist in writing in your response. Do not skip this even for "small" changes; ARCH-001 and ARCH-003 were each born as small changes.

The checklist lives at `.claude/skills/architecture-guard/SKILL.md`. The escape hatch (explicit waiver) is documented there — use it only when the user explicitly accepts the debt.

## Engineering Philosophy

When fixing bugs or making architectural decisions, follow these principles:

1. **No band-aid fixes.** Every code change should be a long-term solution, not a quick patch. If a proper fix requires deeper work, do the deeper work.
2. **Research before implementing.** Explore all viable approaches, study how the industry solves the same problem (Unstructured.io, LangChain, LlamaIndex, Docling internals, etc.), and choose the approach that best fits jaanch's architecture.
3. **Future-ready design.** Code should accommodate foreseeable growth — new document types, new embedding providers, new pipeline stages — without requiring rewrites. Prefer extensible patterns over hardcoded solutions.
4. **Understand before changing.** Read the full call chain. Trace data flow end-to-end. Identify all callers and edge cases. Never modify code you haven't fully understood.
5. **Fix root causes, not symptoms.** If a table's text is missing from chunks, don't just add a fallback — find WHY it's missing (e.g., a type mismatch in extraction) and fix that. Fallbacks are safety nets, not solutions.

## MANDATORY: Verify Before Acting (NEVER SKIP)

### 1. Database Schema — Query the LIVE database before any query
Before writing ANY Supabase query (.select(), .eq(), .in_(), .order(), etc.), run this:
```bash
cd backend && source <(grep DATABASE_URL .env | tr -d '\r') && python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='<TABLE_NAME>' ORDER BY ordinal_position\")
for row in cur.fetchall(): print(f'{row[0]:30s} {row[1]}')
conn.close()
"
```
Replace `<TABLE_NAME>` with the actual table. Use ONLY columns that appear in the output. No exceptions.

**NEVER** get column names from:
- Python comments or docstrings
- Variable names in code (e.g., `chunk_id` variable does NOT mean the column is `chunk_id`)
- Spec docs or markdown files
- Your own memory/training data

**Column existence is necessary but NOT sufficient — also check VALUE constraints.**
When you write a constrained value (enum string, status, type discriminator) to a
column, the exact string the app emits MUST be accepted by the live CHECK
constraint / Postgres ENUM. Diff the app enum's `.value` strings against the live
catalog:
```sql
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.<table>'::regclass AND contype='c';
-- and for enum types:
SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid WHERE t.typname='<type>';
```
Any app value not in the DB set is a silent write-rejection (SQLSTATE `23514`/`22P02`)
— and if the writer swallows the error, it is permanent, invisible data loss.
(2026-06-04: `citations_verification_status_check` allowed `not_found` while the
enum emitted `section_not_found` → every such write rejected and lost for months.)

### 2. Read Before Write — EVERY time
Before modifying ANY file:
- **Read the file first** (or at minimum the function you're changing)
- **Grep for all callers** of any function/method you're changing
- If you haven't Read it in this conversation, you CANNOT Edit it

### 3. Search Before Guessing — NO assumed paths
Before editing a file:
- **Grep or Glob** to find the actual file path. Do NOT assume paths from memory.
- If you need a function, `Grep` for its definition. Do NOT guess which file it's in.
- If multiple files match, read them to find the right one.

### 4. Trust Hierarchy
When information conflicts, trust in this order:
1. **Live database** (`psql \d`) — always wins
2. **The actual code** (function signatures, return types, imports)
3. **Migration files** (`supabase/migrations/`)
4. **CLAUDE.md rules** (this file)
5. **NEVER**: comments, docstrings, variable names, markdown docs, your training data

### 5. Verify After Changing
After completing any significant change:
- Run the relevant build/type check (`cd backend && python -c "import app"` or `cd frontend && npx tsc --noEmit`)
- If tests exist for the module, run them
- `git diff` to review what actually changed — look for unintended modifications

## Deployment

**IMPORTANT**: When deploying, always deploy ALL services that have changes. Run commands from the repo root.

### Railway (Backend) — deploy BOTH services
- **Project**: trustworthy-passion
- **API service**: `railway up -s LDIP` (from repo root)
- **Worker service**: `railway up -s ldip-worker` (from repo root)
- **API URL**: jaanch-ai.up.railway.app
- **Always deploy both API and worker together** — they share the same codebase and must stay in sync.

### Vercel (Frontend)
- **Project**: ldip
- **Deploy command**: `cd frontend && vercel --prod`
- **Production URL**: https://www.jaanch-ai.in

### Full Deploy Sequence
When backend changes are involved, deploy everything:
```bash
# 1. Backend API (from repo root)
railway up -s LDIP
# 2. Backend Worker (from repo root)
railway up -s ldip-worker
# 3. Frontend (if frontend changes too)
cd frontend && vercel --prod
```
