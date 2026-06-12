# Session Post-Mortem & Guardrail Synthesis

> **When to invoke**: after any single-agent or multi-agent (workflow) session whose output fell short of the quality bar — to find every fault, trace root causes, separate "instruction ignored" from "instruction structurally impossible," and propose the specific guardrail that prevents recurrence.
>
> **Why this exists (2026-06-11)**: an FE-ARCH-02 responsive effort (one solo shell PR + an 18-agent workflow) shipped/produced poor-quality UI that passed `tsc`/`eslint` but was never looked at and broke 8 tests. The retrospective surfaced that the failure was the project's oldest shape (proxy-for-correctness accepted in place of the real signal) re-appearing at the UI layer, and that several guardrails were missing. This skill makes that retrospective repeatable.

## Run, in order

1. **CLAIM-vs-TRUTH TIMELINE** — the key decision points in sequence. At each: what was asserted ("verified", "done", "green") vs what was actually true. Mark every gap.

2. **FAULT LEDGER** — one row per mistake:
   `{ what happened · observable harm · the EXISTING skill/hook/memory/CLAUDE rule that should have caught it · why it didn't fire: [not-invoked | fired-but-substituted-a-weaker-check | no-such-rule-exists | structurally-impossible] }`

3. **ROOT-CAUSE CLUSTERS** — collapse the ledger into 2–4 underlying causes (the SHAPE, not the symptoms).

4. **NOT-FOLLOWED vs COULD-NOT-BE-FOLLOWED** — separate negligence from hard structural limits (one shared browser; a parallel agent can't see sibling surfaces; an agent can't see another's mid-edit state). For each "could-not," give the design change that routes AROUND the limit instead of pretending it away.

5. **WORKFLOW-SPECIFIC vs SINGLE-AGENT** — which faults are unique to fan-out parallelism; which happen solo too.

6. **GUARDRAIL PROPOSALS** — for each root cause: `{ artifact (exact: skill name / hook filename / MEMORY entry / CLAUDE.md clause / CI job) · trigger · mechanism · WALL or STICKY-NOTE (+why if sticky) · cost to build }`. Prefer walls (count only goes down). A sticky-note is acceptable only when no cheap wall exists.

7. **THE ONE CHANGE** — if only one guardrail could ship, which kills the most recurrence, and why.

## Rules

Be ruthlessly self-critical; cite specific turns/files/claims. Ban vague fixes ("be more careful"). Every proposal must name WHERE it lives and HOW it triggers. Distinguish the *problem's* origin (often one shape) from the *fix's* duplication (often many).

## Related

- `hostile-review` (the per-change version of this), `architecture-guard`, `choose-solution`
- ARCH-PATTERNS.md (wall-vs-sticky-note frame), GUARDRAIL-BACKLOG.md (where promotable rules live)
