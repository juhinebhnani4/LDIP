---
name: choose-solution
description: Use AFTER you have a problem with more than one viable fix at different levels (local patch vs consistency fix vs systemic refactor) and need to choose the one that is best for LDIP long-term. Especially after a sweep reveals a recurring SHAPE with many instances (active + suppressed + latent). Resolves the two opposing biases — local-patch bias (built ARCH-001/002/003) and grandiosity bias (premature structure for an N=1 system). Returns a scored candidates table and one justified pick. Pairs with blast-radius-research (do the sweep first) and architecture-guard (if the pick touches the pipeline/state).
---

# Choose the Long-Term-Ideal Solution — LDIP

This skill exists because LDIP gets hurt by BOTH directions of the same mistake:

- **Local-patch bias** — patching the flagged instance and leaving the shape.
  This built every P0 architectural debt (ARCH-001/002/003) one reasonable
  local fix at a time.
- **Grandiosity bias** — "fixing it properly" by rewriting working code and
  building structure for a scale this project isn't at. LDIP is deliberately
  N=1 / "plumbed but not pressurized" (see scaling memories); premature
  structure is a failure mode here, not a virtue.

The job of this skill is to pick the solution that threads both: the **smallest
change that eliminates the dangerous SHAPE and leaves a structural guard against
its return — without rewriting working code that isn't part of the hazard, and
without building for a scale this project isn't at.**

This skill does NOT replace the zoom-out (CLAUDE.md) or architecture-guard. Run
the zoom-out always; run architecture-guard if the pick touches the pipeline,
workers, or `documents.status`/`processing_jobs`/locks. Run blast-radius-research
FIRST if you have not yet swept for the shape's full population.

## When this skill MUST be invoked

- A linter / type-checker / audit / bug surfaces N flagged instances and you are
  tempted to patch the N spots. (They are instances of a shape — see the
  "no local fixes" feedback memory.)
- You are choosing between "patch it here", "make it consistent", and "refactor
  the class", and the right boundary is not obvious.
- A fix's blast radius includes WORKING code you would rewrite for elegance.

## Step 1 — Gather inputs (DO NOT decide yet)

State each explicitly; if unknown, go find it before continuing:

1. **THE SHAPE** — the underlying pattern, not the single symptom. How many
   instances exist across the codebase: **active** (tool-flagged), **suppressed**
   (eslint-disable / type-ignore / `# noqa`), and **latent** variants the tool
   structurally cannot see (async setState, runtime dispatch, DB-state coupling)?
   Sweep before you count. "No edge ≠ not coupled."
2. **BLAST RADIUS per candidate** — exactly which files/callers/sites each
   touches. Separate "broken/dangerous sites" from "working sites it would
   rewrite anyway." The second set counts against the candidate.
3. **EXISTING CONVENTION** — does the codebase already handle this shape some way
   (even imperfectly)? Cite the sites. A fix either makes the convention
   CONSISTENT or FORKS it. Forking a convention to fix 2 of 12 sites is usually
   worse than the inconsistency it removes.
4. **SCALE REALITY** — is the pain real at LDIP's current scale, or only at a
   scale this project isn't at? (N=1 workers, one region, current volume.)

## Step 2 — Enumerate candidates across levels

At least three, spanning the range:

- **L1 Local** — patch only the flagged instance(s).
- **L2 Consistency** — fix the flagged instances + latent siblings of the same
  shape, bring them in line with the existing convention, and dedupe via a small
  reusable primitive ONLY where it removes a real hazard.
- **L3 Systemic** — extract primitives/structure and convert the ENTIRE
  population, including currently-working sites.

Add intermediate options if the real choice lives between these.

## Step 3 — Score each against LDIP's criteria (high/med/low + why)

1. **Kills the SHAPE, not just the instance?** (band-aid test — CLAUDE.md
   "fix root causes, not symptoms")
2. **Replaces convention with STRUCTURE?** (ARCH-PATTERNS wall-vs-sticky-note:
   does coordination become derived/enforced rather than "remember to…"?)
3. **Regression risk** — how much WORKING code does it rewrite? Every working
   site rewritten is a chance to inject a subtle bug. Counts AGAINST, hard.
4. **Reversibility & extensibility** — easy to undo? accommodates the next
   document type / provider / panel without another rewrite?
5. **Scale-appropriateness** — investment matched to LDIP's real scale, or
   premature grandiosity for an N=1 system?
6. **Guardability** — can a cheap structural guard (lint rule, reconciler, type,
   CI check) keep the shape from returning, so this is the LAST time?

## Step 4 — Pick, using LDIP's definition of "ideal"

> The smallest change that eliminates the dangerous SHAPE and leaves behind a
> structural guard against its return — WITHOUT rewriting working code that
> isn't part of the hazard, and WITHOUT building for a scale this project
> isn't at.

That definition resolves both biases on purpose:
- It rejects the **L1 local patch** (doesn't kill the shape, no guard).
- It rejects the **L3 grandiose refactor** when most of its blast radius is
  working code rewritten for elegance.

The winner is usually **L2**. State honestly when the shape is dangerous enough
to justify L3, or contained enough that L1 is genuinely correct. A candidate
that FORKS an existing convention to fix a minority of sites is penalized under
criterion #2 even if each edit looks clean.

## Step 5 — Output

- **Candidates table** — each option × the 6 criteria + blast radius (files).
- **THE PICK** — one sentence, mapped to the "ideal" definition.
- **Why the others lost** — explicitly: why not bigger? why not smaller?
- **What this pick DEFERS or FORECLOSES** + the trigger to revisit (e.g. "if a
  3rd instance of the sub-shape appears, extract the primitive"; "if we go
  multi-region, the N=1 assumption breaks").
- **The GUARD** that makes this the last recurrence (or: state plainly that no
  cheap guard exists for the latent sub-shape, so it relies on the primitive
  being the obvious choice).
- **Verification plan** — tsc / lint / tests / live-DB check as applicable.

If, after Step 4, the choice genuinely turns on a product/risk judgment only the
user can make (acceptable regression risk vs completeness), say so and present
the 2 finalists with the tradeoff — do NOT manufacture false certainty.

## Related

- `blast-radius-research` — run FIRST to get the shape's full population.
- `architecture-guard` — run if the pick touches pipeline/workers/state.
- `hostile-review` — run AFTER implementing an L2/L3 pick.
- Memory: "no local fixes — global, blast-radius-aware"; "audit fix sketches
  need Phase 2"; scaling memories (N=1 / plumbed-not-pressurized).
