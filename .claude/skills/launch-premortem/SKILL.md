---
name: launch-premortem
description: Use BEFORE non-code decisions that could fail expensively — product launches, pricing/billing changes, opening to a new user tier (B2B contracts, marketing push, free tier resizing), vendor swaps (embedding provider, LLM provider, OCR provider), Railway/Vercel tier changes, or any decision that projects load growth or cost growth. NOT for code changes — architecture-guard, blast-radius-research, and hostile-review cover those. Imagines "it's 90 days later and this failed" then walks through LDIP's known failure shapes to ask which one killed it. Returns top 3 named risks with early warning signal, prevention, mitigation, and owner.
---

# Launch Pre-Mortem — LDIP

This skill exists because LDIP's four code-focused skills (`architecture-guard`, `blast-radius-research`, `forensic-hunt`, `hostile-review`) all assume the unit of work is *code*. They have no opinion on "should we offer a B2B tier", "should we swap Voyage for OpenAI embeddings", "can we let marketing send a 10× traffic spike Tuesday", or "should we move to Railway's hibernating tier to save money". Those decisions can fail just as expensively as bad code — and they fail through LDIP-specific shapes that a generic pre-mortem template would miss.

## When this skill MUST be invoked

- Any launch announcement, marketing push, or contract that projects user/document/load growth
- Any pricing or billing change (free tier limits, paid tier definition, per-page costs)
- Any vendor swap or API model change (embedding provider, LLM provider, OCR provider, vector DB, queue broker)
- Any infrastructure tier change (Railway sleep/hibernate, Vercel plan, Supabase plan, GCP project structure)
- Opening the product to a new user segment (B2B, government, education, international)
- Any decision that assumes a piece of meta-tooling will be remembered (a new rule, a new manual workflow, a new "admin will fix it" recovery surface)

## When NOT to invoke (use the right tool instead)

- Code changes touching the pipeline → `architecture-guard`
- Investigations before implementing anything → `blast-radius-research`
- Recurring bug clusters → `forensic-hunt`
- Post-implementation, pre-deploy verification → `hostile-review`

If the decision involves writing code, this skill is the wrong tool. The code-shaped skills are sharper.

## The setup

> *"It's 90 days after [LAUNCH / CHANGE / DECISION]. The outcome was a disaster. Walking backward from the smoking crater — which of LDIP's known failure shapes killed us?"*

This frame matters. Generic pre-mortems ask "what could go wrong?" and get generic answers. LDIP-shaped pre-mortems ask "which of *our* known shapes ate us?" and get answers we can actually defend against.

## The ten LDIP failure shapes — walk through each, answer yes/no

Each is anchored to a real prior incident or known structural constraint. For each, the question is: **does this decision make this shape more likely to fire?** If yes — that's a candidate for the top 3.

1. **Gemini quota saturation (ARCH-002b)**. Every LLM-bound task hits the same Google account's RPM quota. Does this decision increase per-document or per-user LLM calls? Will the new load tier (concurrent docs × LLM calls per doc) fit in the existing quota bucket? Which task class's budget does the new load consume — is a partitioner in place?

2. **N=1 horizontal scale (`scaling-plumbed-not-pressurized`)**. Worker, API, beat all run at single-replica. Does this decision assume horizontal scale that doesn't exist? If load spikes — what's the bottleneck order (Gemini → worker → Supabase pool → API memory)?

3. **OCR per-page cost blowout**. Google Document AI charges per page. Does this decision invite high-page-count documents (case files, judgments, scanned books)? Is the unit economics still positive at the 95th-percentile document size for the new user segment?

4. **Vendor swap requires re-embed / re-OCR**. Embedding model change → every chunk must be re-embedded. OCR provider change → every document must be re-processed. Does this decision assume the swap is reversible cheaply? What's the cost in dollars and downtime to flip back?

5. **Cost not tracked for the operation about to scale (`verification-failures` 2026-03-18)**. Some operations don't write to `llm_costs`. If this decision makes one of those operations dominant, will we know what we're spending? Pre-check: `SELECT operation, COUNT(*), SUM(cost_usd) FROM llm_costs GROUP BY operation` — does the operation we're about to scale appear?

6. **No recovery from wrong state (`blast-radius-research` 1.5B pattern)**. Does this decision create a state a user can land in that has no recovery path? (Misclassified library Acts had no reclassification path for months.) If the new feature/tier lets users do something wrong, can support fix it without a SQL console?

7. **Library/main parallel tables (ARCH-001 shape)**. Does this decision add a new content type that'll need its own pipeline, table, and recovery surface — duplicating the existing one? Every column in chunks/ that's missing from library_chunks/ is a future drift bug. If you're adding a third logical pipeline (e.g. "templates", "drafts", "user notes"), you're seeding ARCH-001 v3.

8. **Beat dies when worker sleeps (ARCH-002 shape)**. Does this decision involve any cost-saving sleep/hibernate/auto-pause on Railway? Beat assumes worker is alive; worker assumes Redis is reachable. Which links in the chain go silent if anything sleeps?

9. **Admin retry surface is the only recovery (`admin retry pipeline` history)**. Does this decision route problems to "admin will fix it"? The admin retry endpoint took 5+ iterations to make correct. If the new user segment generates 10× more "stuck document" tickets, can a non-engineer resolve them?

10. **Meta-tooling rot (GUARDRAIL-BACKLOG.md, MEMORY.md is itself rotting)**. Does this decision rely on a NEW rule, manual workflow, or "we'll remember to..." pattern? Every new convention is a future ARCH-003. If the answer to a launch risk is "we'll add a rule that says don't do X" — that's the rot itself; require the structural change instead.

## Required deliverable

After walking through all ten, produce this:

```
PRE-MORTEM — <decision name> — <date>

DECISION: <one sentence — what's being decided, by when, success criteria>

FAILURE SHAPES THAT THIS DECISION MAKES MORE LIKELY (flagged from the ten above):
- Shape #N: <why this decision makes it more likely; what changes>
- Shape #N: ...
- Shape #N: ...

TOP 3 RISKS (by likelihood × cost-of-being-wrong)

RISK 1: <name>
  Early warning signal: <a specific query, metric, dashboard, or user-report shape>
  Prevention: <what to do BEFORE shipping to reduce likelihood>
  Mitigation: <what to do AFTER it fires to reduce impact>
  Owner: <who is watching; how often>
  Go/No-go gate: <what must be true before this decision proceeds>

RISK 2: ...
RISK 3: ...

KILL CRITERIA: <what we'd observe in the first 7/30/90 days that means we
                must reverse this decision — define before launching, not after>

REVERSIBILITY: <if this fails, how reversible is it? Cost in $ and days to undo?>
```

## Honest limitation

The ten shapes above were extracted from the failures LDIP has *already had*. They will miss the failure mode that comes from a shape LDIP hasn't met yet. After each launch, if a new shape kills you, add it as #11. The catalog only stays useful if it grows with reality.

## Anti-rot rule (read at the end of every use)

If walking through all ten shapes turned up zero candidates — that is itself a warning sign, not an all-clear. Either (a) the decision is genuinely outside LDIP's known failure surfaces (rare; possible for pure copy/branding/UX changes), or (b) you walked through them mechanically without engaging the decision. If you didn't feel even one "oh, hmm" while reading the ten — restart and engage harder.

## Escape hatch

If the user explicitly says *"I've thought this through, I accept the risk, just record it"* — you may skip the deliverable and instead append a one-line entry to GUARDRAIL-BACKLOG.md:

```
<date> — <decision name>: pre-mortem deferred at user request. Watch for: <top concern>.
```

This lets the deferred risk surface if it later fires, instead of going silent.
