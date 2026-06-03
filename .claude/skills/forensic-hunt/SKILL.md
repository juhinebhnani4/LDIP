---
name: forensic-hunt
description: Use when the same class of bug keeps reappearing in LDIP and the goal is to find the underlying SHAPE that generates them — not patch the next symptom. Invoke with a cluster name (e.g. "stuck documents", "auth 500s", "library ingestion failures", "OCR retries that never complete", "frontend SSE silent drops"). Runs a phase-gated forensic protocol: each phase produces a written deliverable that gates the next. Phase N+1 refuses to start without Phase N's artifact. Composes with `blast-radius-research` (sub-invoked for system mapping) and `architecture-guard` (suspect catalog reuse). Returns a single named root cause and a prosecution plan, not a list of symptom patches.
---

# Forensic Hunt — LDIP

This skill exists because LDIP keeps producing bugs with **the same shape** across different surfaces. Three foundational debts (ARCH-001/002/003) have generated every P0/P1 pipeline incident in the project's history. The ten patterns in `ARCH-PATTERNS.md` (P1–P10) are the broader catalog. Every recurring incident in `BUGS.md` is a body left by one of those shapes.

The job of this skill is to **catch the shape, not the symptom**. Patching a symptom leaves the shape free to kill again on the next surface.

## Detective's oath (forbidden shortcuts — read first every time)

This skill fails the moment any of these is skipped. They are not advisory.

1. **No theory without evidence.** A root cause hypothesis is worthless until verified against the live database, live logs, or live traces. Code reading produces hypotheses; data produces verdicts. See `verification-failures.md` (2026-03-18): five revisions of a wrong theory because nobody ran one SQL query.
2. **No boil-the-ocean.** Refuse to start until the user names the cluster. "Why does the app keep breaking" is not a cluster. "Documents stuck at OCR_COMPLETE" is. If the user can't name one, help them narrow — don't proceed broad.
3. **No code-only investigations.** For every claim about behavior, name the runtime artifact that proves it: a row in `processing_jobs`, a line in worker logs, a Celery task ID, a Supabase audit entry, an HTTP response captured in DevTools. If you can't, your claim is a hypothesis.
4. **No skipping Phase 1 of `blast-radius-research`.** This skill calls it as a sub-routine in Phase 3. Generic findings from skipped Phase 1 work are exactly how Railway cost analysis (2026-04-22) got three of four recommendations wrong.
5. **No symptom-patch recommendations.** If the prosecution plan in Phase 7 doesn't name a structural change (delete a path, collapse two implementations into one, replace signaling with reconciliation, ship a worker for an existing queue) — the suspect was never identified. Go back to Phase 5.
6. **No "this is fine" without checking BUGS.md `REJECTED` and `DEFERRED`.** A solution that's already been rejected for this cluster cannot be your prosecution plan. Cite the entry that approved or freed your approach.
7. **No closing the case without a regression sentinel.** Phase 7 must name how a future occurrence would be detected automatically — a query, a metric, a test, a reconciler. Otherwise the shape just goes dormant.

## When this skill MUST be invoked

- The same bug (or a bug with the same shape) has appeared 3+ times in `BUGS.md`.
- A "fix" landed N times for the same cluster and the cluster came back.
- A P0/P1 incident is being post-mortemed and the user wants to know if it's a one-off or a shape.
- Before opening a new bug epic that touches an area with prior failures.
- The user says any of: "why does this keep happening", "we keep fixing this", "another one of these", "I'm tired of patching this".

If the request is one-off and the cluster has no prior history in `BUGS.md` — skip this skill and use `blast-radius-research` directly.

## Inputs

Required at invocation:
- **Cluster name** (one phrase, ≤ 6 words)
- **Three example incidents** (commit SHAs, BUGS.md entry IDs, error messages, or document/job IDs)

If the user gave fewer than three examples, ask before starting. Two-point pattern matching produces false convictions.

---

## Phase 0 — Name the suspect's neighborhood

**Purpose**: refuse to start until the cluster is narrow enough to investigate. This phase exists because past sessions have spent hours producing generic findings against vague problem statements.

**Deliverable** (written in response to user before any tool call):

```
CLUSTER: <cluster name>
EXAMPLES: <ID 1>, <ID 2>, <ID 3>  [at least 3]
SURFACE: <which subsystem the symptoms appear in — pipeline / API / frontend / worker / library / auth / billing>
WHAT'S COMMON: <one sentence — what do these incidents have in common at the symptom level>
WHAT'S NOT YET KNOWN: <one sentence — what we don't yet know about why they keep recurring>
```

**Gate**: do not proceed to Phase 1 until this artifact is written. If the user disputes the cluster framing, revise and reprint before continuing.

---

## Phase 1 — Crime scene mapping

**Purpose**: map the static topology of the subsystem the cluster lives in. Names, files, tables, queues, deploy units. Not behavior yet — just what's *there*.

**Actions:**
- List every code file directly involved (use Grep / Glob, not memory).
- List every database table involved. **Query the live DB** for each — column list with types. Migration files are append-only and lie about current state.
- List every queue, worker process, and Railway service involved. Cite the `railway.toml` / `start-worker.sh` / `celery.py` lines that define them.
- List every external service in the chain (Supabase, Google Document AI, Gemini, OpenAI, Voyage, Redis, Upstash, Vercel, etc.). For each, name the auth + quota model.
- List every cron / beat / reconciler / sweeper that touches state in this area.

**Deliverable**:

```
SCENE MAP — <cluster name>
- Files: <list with absolute paths>
- Tables: <name + live column list, not migration-derived>
- Queues: <name + which worker service consumes them + railway.toml citation>
- External services: <name + auth + quota model>
- Background jobs: <name + schedule + what state they mutate>
```

**Gate**: if the scene map can't be written because the system is too tangled to map, that IS the finding. Stop and report it — the cluster's shape is "no map exists." Do not proceed.

---

## Phase 2 — Victim catalog

**Purpose**: every previous body. The shape becomes visible by comparing victims, not by reading any single one.

**Actions:**
- Grep `BUGS.md` for cluster keywords. List every entry that matches, including those marked RESOLVED, REJECTED, DEFERRED, NOT REPRODUCIBLE, RECURRING.
- Grep memory files (`C:\Users\Jyotsna\.claude\projects\E--Career-coaching-100x-LDIP\memory\`) for prior session findings.
- Grep commit history (`git log --all --grep`) for fix attempts. Note every commit SHA that purported to fix something in this cluster.
- For each victim, capture: what broke, what the "fix" was, whether the cluster came back after the fix, what the user said when it came back.

**Deliverable**:

```
VICTIM CATALOG — <cluster name>
| # | When | Symptom | Claimed root cause | Fix shipped | Came back? | BUGS.md entry / commit |
|---|------|---------|--------------------|--------------|-------------|------------------------|
| 1 | ...  | ...     | ...                | ...          | Y/N         | ...                    |
| 2 | ...  | ...     | ...                | ...          | Y/N         | ...                    |
```

Add a one-paragraph note: **what's the same across victims, what's different.** This is the suspect profile.

**Gate**: if fewer than 2 victims are found, the cluster isn't a cluster — it's an incident. Stop the forensic hunt; recommend `blast-radius-research` directly for the single incident.

---

## Phase 3 — Path mapping (entry, exit, recovery)

**Purpose**: the killer always lives at a path the investigators didn't walk. This phase exists to make sure every path is walked.

**This phase invokes `blast-radius-research` Phase 1 as a sub-routine.** Specifically Phase 1.2 (trace current failure path), 1.3 (external interactions), and 1.5 (system-level synthesis — all entry paths, all exit paths, recovery from wrong decisions). Do not duplicate that protocol here; invoke it.

**Then add the forensic-specific extensions:**

- **Every entry path that reaches the symptom state.** Not just the obvious one. For a stuck-document cluster: API upload, library auto-fetch, admin retry, recovery sweep, batch import, manual SQL update.
- **Every exit path from the suspect zone.** Including silent successes, silent failures, exceptions caught and swallowed, early returns, dispatched-but-never-acked tasks, lock-released-without-status-update branches.
- **Every state transition into and out of the symptom state.** Query `job_stage_history` / equivalent for the example incidents. What state was the victim in before? What was the last task that touched it?
- **Every recovery / repair surface.** Admin endpoints, recover scripts (`recover_stuck_document.py`), reconcilers, the human-clicking-retry-in-prod path.

**Deliverable**:

```
PATH MAP — <cluster name>
ENTRY PATHS: <numbered list — code citation for each>
EXIT PATHS FROM SUSPECT ZONE: <numbered list — code citation, including silent ones>
STATE TRANSITIONS OBSERVED IN VICTIMS:
  Victim 1: <state_history dump from DB>
  Victim 2: <state_history dump from DB>
  Victim 3: <state_history dump from DB>
RECOVERY SURFACES: <numbered list — who can repair a stuck case and how>
PATHS NOT YET TRACED: <honest list of paths suspected but not walked>
```

**Gate**: if "paths not yet traced" is non-empty, either walk them or escalate. Do not proceed to pattern matching while paths are dark — that's where the killer is hiding.

---

## Phase 4 — Pattern match against the suspect catalog

**Purpose**: every shape that has hurt LDIP before is already catalogued in `ARCH-PATTERNS.md` (P1–P10) and the three forbidden patterns in `architecture-guard`. Match before inventing.

**Actions:**
- For each entry/exit path mapped in Phase 3, ask: **does this path match P1, P2, … P10?** Be specific — quote the pattern definition, name the path, name the match.
- Match against the three forbidden patterns in `architecture-guard`: parallel duplicate paths, logical-without-physical isolation, "remember to signal" coordination.
- Pattern matches across victims are stronger than a single-victim match. If Victims 1, 2, and 3 all match P3 ("convention-coordinated state"), that's the suspect profile.
- A new shape NOT in the catalog is allowed, but rare and must be justified — describe why it doesn't fit any existing pattern.

**Deliverable**:

```
PATTERN MATCHES — <cluster name>
| Pattern | Victims matched | Specific path | Quote from catalog |
|---------|-----------------|---------------|--------------------|
| P3 (convention-coordinated state) | 1, 2, 3 | extract_citations exit on 0 chunks | "must dispatch from ALL exit paths..." |
| P7 (...) | 2 | ... | ... |

DOMINANT PATTERN: <the one matched by the most victims — this is the suspect>
NEW PATTERN (if any): <describe why no catalog entry fits>
```

**Gate**: if no pattern matches any victim, you have either (a) missed paths in Phase 3 — go back, or (b) discovered a new pattern worth adding to `ARCH-PATTERNS.md`. Don't proceed with "no match" as the answer.

---

## Phase 5 — Suspect identification (the named hypothesis)

**Purpose**: produce **exactly one** named root cause. Not a list. A list means the suspect wasn't identified — it means several were rounded up.

**Format the hypothesis as a falsifiable claim**:

```
SUSPECT — <cluster name>
HYPOTHESIS: The cluster recurs because <one sentence — the structural cause, not the symptom>.
PATTERN: <P1–P10 or the three forbidden patterns — name it>
LOCATION: <file:line ranges, table names, queue names — where the shape physically lives>
PREDICTION: If this hypothesis is correct, we should observe <specific, queryable signal in live data or logs>.
  And we should NOT observe <signal that would falsify the hypothesis>.
ANTI-PREDICTION (kill switch): If we observe <signal>, the hypothesis is wrong and we must restart from Phase 3.
```

**Gate**: a hypothesis without an anti-prediction is not falsifiable and not admissible. Restart this phase if you can't write the kill switch.

---

## Phase 6 — Evidence (verify, don't argue)

**Purpose**: prove the suspect is the killer. Verify the prediction. Try to falsify the anti-prediction. **Data wins over theory.**

**Actions:**
- Run the predicted query / log search / trace inspection. Paste the result, not a summary.
- Run the falsification check. Paste the result.
- For schema/permission claims, query system catalogs (`pg_proc`, `pg_default_acl`, `information_schema.columns`), not migration files. Per `blast-radius-research` 2.5.
- For status/flow claims, query the live tables: `SELECT status, COUNT(*) GROUP BY status`. Per `blast-radius-research` 1.5D.
- For "this code path runs," capture an actual log line, task ID, or trace from a real incident — not a hypothetical walkthrough.

**Deliverable**:

```
EVIDENCE — <cluster name>
PREDICTION CHECK
  Query/command: <exact command>
  Result: <paste raw output>
  Verdict: CONFIRMED / FALSIFIED

ANTI-PREDICTION CHECK
  Query/command: <exact command>
  Result: <paste raw output>
  Verdict: NOT OBSERVED (good) / OBSERVED (bad — hypothesis is wrong)

OUTCOME: SUSPECT CONFIRMED — proceed to Phase 7
       | SUSPECT REFUTED — return to Phase 3 with new info
       | EVIDENCE INCONCLUSIVE — name the missing data; ask user before proceeding
```

**Gate**: do not proceed to Phase 7 unless the verdict is CONFIRMED with raw evidence pasted. "Looks consistent with the theory" is not evidence.

---

## Phase 7 — Prosecution plan (structural fix, not symptom patch)

**Purpose**: the fix must remove the shape, not the symptom. If the fix is "add another exit-path dispatch site" — the shape stays. If the fix is "replace dispatch with a reconciler that derives state from observed rows" — the shape is gone.

**Constraints**:
- The plan must name a **structural change**: delete a duplicate path, collapse two implementations, replace signaling with reconciliation, ship the worker for an existing queue, add a single convergence point, partition a shared quota, add the physical isolation that was missing.
- The plan must pass `architecture-guard` — invoke the skill and answer its checklist before writing code. If the plan triggers a Forbidden Pattern, revise.
- The plan must include a **regression sentinel**: a query, metric, alert, or reconciler that would detect the cluster recurring before a user does.
- The plan must reference whether `blast-radius-research` Phase 2 is needed before implementation (almost always: yes).
- The plan must invoke `hostile-review` AFTER implementation and BEFORE deploy. Structural fixes can still ship runtime-mismatch, serialization-limit, or concurrent-execution bugs — that's the category hostile-review catches and forensic-hunt does not. Do not deploy without it.

**Deliverable**:

```
PROSECUTION PLAN — <cluster name>
STRUCTURAL FIX: <one sentence — what shape gets removed>
WHY THIS IS NOT A SYMPTOM PATCH: <explain how this prevents recurrence at all entry paths>
ARCHITECTURE-GUARD CHECKLIST: <link to or paste the completed checklist>
REGRESSION SENTINEL: <the query/metric/reconciler that would catch the cluster recurring>
NEXT STEPS:
  1. <invoke blast-radius-research Phase 2 on the specific change>
  2. <implement>
  3. <verify with the regression sentinel against real data>
BUGS.md UPDATE: <which entry to update; whether to add a new ARCH-00X entry; whether to retire any old "fix" notes that turned out to be symptom patches>
```

**Gate**: case is closed only when (a) the prosecution plan is written, (b) `architecture-guard` says clean, and (c) the regression sentinel is named and runnable. If any is missing, the killer's still out there.

---

## Composite invocation template

When the user invokes this skill, run this template against the cluster they named:

```
I am running the forensic-hunt protocol on the cluster: <NAME>.

Phase 0 — Cluster framing (printing first; will not proceed until confirmed):
<fill in CLUSTER, EXAMPLES, SURFACE, WHAT'S COMMON, WHAT'S NOT YET KNOWN>

After user confirms Phase 0:

Phase 1 — Scene map (Glob/Grep/live-DB only — no memory):
<fill in>

Phase 2 — Victim catalog (BUGS.md + git log + memory):
<fill in>

Phase 3 — Path map (invoke blast-radius-research Phase 1.2, 1.3, 1.5):
<fill in>

Phase 4 — Pattern match against ARCH-PATTERNS.md P1–P10 + architecture-guard's 3 forbidden patterns:
<fill in>

Phase 5 — Suspect (single named falsifiable hypothesis with anti-prediction):
<fill in>

Phase 6 — Evidence (paste raw query/log output; do not summarize):
<fill in>

Phase 7 — Prosecution plan (invoke architecture-guard before writing code,
         hostile-review before deploy):
<fill in>
```

---

## Failure modes this protocol prevents

| Failure mode | Example | Which phase catches it |
|---|---|---|
| Boiling the ocean ("everything is broken") | Generic "investigate the app" prompt | Phase 0 (cluster framing) |
| Symptom-patching the same cluster N times | extract_citations dispatch fix shipped 3 times | Phase 2 (victim catalog — comebacks visible) |
| Code-only theorizing | "Cost service fails silently" theory (2026-03-18) | Phase 6 (evidence requires raw output) |
| Walking one path of many | Library research traced only upload path | Phase 3 (every entry path, every exit path) |
| Inventing a new shape that's already catalogued | Discovering "convention coordination" again | Phase 4 (match against ARCH-PATTERNS.md first) |
| Multiple suspects, no conviction | "Could be A, B, or C" | Phase 5 (exactly one falsifiable hypothesis) |
| Unfalsifiable hypothesis | "Race conditions are involved" | Phase 5 (anti-prediction required) |
| Symptom-patch passed off as fix | "Add another dispatch site to extract_citations" | Phase 7 (must be structural; architecture-guard veto) |
| Fix ships, cluster goes dormant, returns 6 months later | Many ARCH-003 incidents | Phase 7 (regression sentinel required) |
| Generic recommendation conflicting with existing architecture | Railway cost analysis 2026-04-22 | Phase 3 invokes blast-radius-research Phase 1 |

---

## Escape hatch

If the user explicitly says *"I just need the symptom patched, I know the shape is still there, accept the debt"* — you may skip Phases 4–7 and ship a symptom patch, but you must:

1. Add a victim row to the next forensic hunt's catalog (paste it into `BUGS.md` under the relevant cluster) so the comeback is pre-recorded.
2. Note in the commit message: "symptom patch — forensic-hunt deferred; shape remains".
3. Update `MEMORY.md` with the deferred hunt so future sessions know it's owed.

This escape hatch exists because sometimes the user is on fire and needs the symptom gone now. But the shape doesn't get to hide silently.

## Honest limitation

Like `blast-radius-research`, this is a smart sticky note. The protocol fires only when invoked. The closest to a wall: if the zoom-out guard detects a request matching the "this keeps happening" trigger phrases above, it could enforce that this skill is invoked before any code is written. Until then, the discipline is on the operator (Claude or human) to recognize the cluster signal and reach for the skill.
