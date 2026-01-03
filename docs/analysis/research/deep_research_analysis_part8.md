---
📋 **DOCUMENT STATUS: PHASE 2+ VISION - DEFERRED**
This document is part of the Deep Research vision (8 parts). See [deep_research_analysis_part1.md](./deep_research_analysis_part1.md) for full status information.
**For implementation, use:** [Requirements-Baseline-v1.0.md](../../../_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md)
---

PART 8 — BOUNDED ADAPTIVE COMPUTATION & NOVEL PATTERN DISCOVERY (PHASE 2+ EVOLUTION)

Status: Not MVP. This is the Phase 2+ / Phase 3 evolution of LDIP.
It builds on Option 2 (engines + orchestrator + pre-linking) without changing the core safety rules.

This part defines how LDIP can evolve to handle novel corruption patterns, hidden connections, and cross-matter analysis while still obeying:

matter isolation

no legal advice

evidence-first reasoning

neutral outputs

privilege + conflict protections

strong stop conditions for all loops

Think of this as:

"Adaptive analysis that discovers hidden patterns and connections,
operating within strict bounds and explicit termination criteria,
all under a very strict rulebook (Parts 3, 4, 5, 6, 7)."

8.1 Goals of Bounded Adaptive Computation

Bounded adaptive computation is not about replacing lawyers. It is about:

Novel Pattern Discovery

Discover hidden corruption patterns, manipulation sequences, and non-obvious connections that pre-linking cannot capture.

Cross-Matter Network Analysis (When Authorized)

Identify connections across authorized matters (e.g., same entity appearing in multiple matters with different roles, suspicious timing patterns).

Adaptive Query Planning

For complex questions ("find all hidden connections between Nirav and the Mehta family across documents"), the system plans a one-time analysis strategy and executes bounded loops to discover connections.

Human-First Workflows

Every adaptive computation output is a draft research suggestion for attorney review,
not an instruction or conclusion.

All loops have explicit stop conditions and are logged for audit.

8.2 Architecture Principle: Adaptive Planning on Top of Engines + Pre-Linking

Very important:

Engines (from Part 4 & 7) are the ground truth analyzers.

Pre-linking (from Part 7) provides fast, deterministic relationships.

Adaptive computation is a query-time layer that:

performs one-time planning (not iterative) to determine:
  - which engines to call
  - in what order
  - when bounded loops are needed
  - what stop conditions apply

executes bounded loops for:
  - multi-hop relationship discovery
  - iterative pattern clustering
  - cross-document connection chains
  - novel corruption pattern detection

assembles research narratives from engine outputs

Adaptive computation does not bypass:

RAG rules

matter isolation

privilege checks

safety filters

pre-linking results (uses them as starting points)

It only calls tools that already enforce these.

All loops have explicit, strong stop conditions (see 8.4).

8.3 Adaptive Computation Patterns (Phase 2 / Phase 3)

8.3.1 Novel Connection Discovery

Purpose: Discover hidden relationships and connections that pre-linking missed.

Tasks:

Start from pre-linked entities and relationships

Execute bounded loops to:
  - Traverse multi-hop connections (entity A → document B → entity C → document D)
  - Discover indirect relationships (e.g., "Nirav introduced by Payal, who is related to Ashwin, who appears in Matter X")
  - Identify suspicious timing patterns across documents

Stop Conditions:
  - Maximum hop depth (e.g., 5 connections)
  - No new connections found in last iteration
  - Time limit (e.g., 30 seconds)
  - User checkpoint reached

Input:

matter_id

pre-linked entities and relationships

query intent (e.g., "find all connections between entity X and entity Y")

authorized cross-matter access (if applicable)

Output:

discovered connection chains

confidence scores per connection

evidence citations for each hop

limitations (what was not explored due to stop conditions)

8.3.2 Corruption Pattern Detection

Purpose: Detect novel manipulation patterns that set workflows might miss, especially in India context where corruption patterns are creative and non-standard.

Tasks:

Use Pattern/Anomaly Engine with adaptive planning to:

identify non-obvious timing manipulations (e.g., backdating, sequence inversions)

detect hidden coordination patterns (same entity appearing in multiple roles across documents)

discover process chain deviations that don't match standard templates

Execute bounded loops to:
  - Compare patterns across multiple documents
  - Cluster anomalies that suggest manipulation
  - Identify recurring suspicious sequences

Stop Conditions:
  - Maximum pattern comparisons (e.g., 20 document pairs)
  - No new patterns found
  - Time limit (e.g., 45 seconds)
  - Confidence threshold reached

Output (to lawyer):

"Pattern Analysis for Matter M:
– 3 timing anomalies detected (deviations >3 standard deviations)
– 2 non-standard process sequences identified
– 1 recurring entity role change pattern found
See evidence pages: …"

Still no conclusion about malpractice. Only factual pattern reporting.

8.3.3 Cross-Matter Pattern Analysis (Authorized Only)

Purpose: Identify patterns across authorized matters, especially for corruption detection where cross-matter connections are critical.

Tasks:

When explicit cross-matter authorization is provided:

Use pre-linked entities from multiple matters

Execute bounded loops to:
  - Match entities across matters (using MIG from each matter)
  - Identify recurring patterns (same entity, different roles)
  - Detect timing correlations (suspicious sequences across matters)
  - Surface network connections (entity A in Matter 1 connected to entity B in Matter 2)

Stop Conditions:
  - Maximum matters analyzed (e.g., 10 matters)
  - Maximum entity matches per matter (e.g., 50)
  - No new cross-matter connections found
  - Time limit (e.g., 60 seconds)
  - User checkpoint (pause before accessing new matter)

Output:

"Cross-Matter Analysis (Authorized Matters: M1, M2, M3):
– Entity 'Nirav D. Jobalia' appears in 3 matters with different roles
– Timing pattern: similar sequence delays across all 3 matters
– 2 shared intermediary entities identified
See evidence: [matter-specific citations]"

Everything remains neutral and matter-isolated in storage. Only aggregated patterns are reported.

8.3.4 Iterative Pattern Clustering

Purpose: Group related anomalies and patterns that emerge from multiple engine runs.

Tasks:

Execute bounded loops to:

cluster anomalies by type (timing, process, entity, citation)

identify recurring themes across document sets

group contradictions by topic and entity

discover pattern hierarchies (e.g., timing anomalies → process deviations → entity role changes)

Stop Conditions:
  - Maximum clustering iterations (e.g., 10)
  - No new clusters formed
  - Cluster stability threshold reached (no changes in last 2 iterations)
  - Time limit (e.g., 40 seconds)

Output:

"Pattern Clusters for Matter M:
– Cluster 1: Timing Anomalies (5 instances, avg deviation: 45 days)
– Cluster 2: Process Sequence Deviations (3 instances, all related to demat)
– Cluster 3: Entity Role Inconsistencies (4 entities, 8 role changes)
See evidence: [document citations per cluster]"

No interpretation of why patterns exist. Only factual clustering.

8.3.5 Multi-Hop Relationship Traversal

Purpose: Follow relationship chains across documents to discover indirect connections.

Tasks:

Start from a seed entity (from pre-linking or user query)

Execute bounded loops to:
  - Hop 1: Find all documents mentioning seed entity
  - Hop 2: Extract all other entities mentioned in those documents
  - Hop 3: Find documents mentioning those entities
  - Continue until stop condition reached

Stop Conditions:
  - Maximum hop depth (e.g., 5 hops)
  - Maximum entities explored (e.g., 100 entities)
  - No new entities found in last hop
  - Time limit (e.g., 30 seconds)
  - User checkpoint (pause after each hop for review)

Output:

"Relationship Chain from 'Nirav D. Jobalia' (3 hops):
– Hop 1: Found in 12 documents, linked to 8 entities
– Hop 2: Those 8 entities appear in 25 documents, linked to 15 new entities
– Hop 3: Those 15 entities appear in 18 documents
– Total chain: 41 entities, 55 documents
See evidence: [entity-document mapping]"

No interpretation of relationship significance. Only factual traversal.

8.4 Bounded Loop Execution: Stop Conditions & Safety

All adaptive computation that involves loops MUST have explicit, strong stop conditions.

8.4.1 Stop Condition Types

Maximum Iterations:
- Hard limit on loop iterations (e.g., max 5 connection hops, max 10 clustering rounds)
- When reached: loop terminates immediately, partial results returned

No New Findings:
- If an iteration produces no new connections, patterns, or findings
- When triggered: loop terminates, all findings up to that point returned

Time Limits:
- Maximum execution time per loop (e.g., 30 seconds for connection discovery, 60 seconds for cross-matter analysis)
- When reached: loop terminates, current state saved, partial results returned

User Checkpoints:
- Pause points where user must approve continuation (e.g., after each cross-matter access, after 3 connection hops)
- When checkpoint reached: loop pauses, user reviews, can approve/deny/terminate

Confidence Thresholds:
- Stop if confidence in findings drops below threshold (e.g., <0.6 confidence in connection)
- When triggered: loop terminates, only high-confidence findings returned

8.4.2 Loop Execution Guarantees

Every bounded loop MUST:

Log iteration count at start of each iteration

Log stop condition checks at end of each iteration

Record which stop condition triggered termination

Store partial results if loop terminates early

Never proceed if any stop condition is violated

Never execute loops without explicit stop conditions defined

8.4.3 Example: Connection Discovery Loop

```
LOOP: Discover connections between Entity A and Entity B
STOP CONDITIONS:
  - Max iterations: 5 hops
  - No new connections: stop if iteration finds 0 new connections
  - Time limit: 30 seconds
  - User checkpoint: pause after hop 3

ITERATION 1:
  - Found 3 direct connections
  - Iteration time: 2s
  - Continue? YES (new findings)

ITERATION 2:
  - Found 2 indirect connections (via hop 1 entities)
  - Iteration time: 3s
  - Continue? YES (new findings)

ITERATION 3:
  - Found 1 connection (via hop 2 entities)
  - Iteration time: 4s
  - USER CHECKPOINT: Pause for review
  - User approves continuation

ITERATION 4:
  - Found 0 new connections
  - STOP CONDITION TRIGGERED: No new findings
  - Loop terminates
  - Total findings: 6 connections across 3 hops
  - Total time: 9s
```

8.4.4 Safety Constraints

Loops MUST NOT:
- Execute indefinitely
- Bypass matter isolation
- Access unauthorized cross-matter data
- Modify system state (engines remain read-only)
- Proceed without explicit stop conditions

Loops MUST:
- Be deterministic in execution (same inputs → same outputs, given same stop conditions)
- Log all iterations for audit
- Return partial results if terminated early
- Respect privilege filters
- Obey all safety rules from Parts 3, 4, 5, 6, 7

8.5 Adaptive Planning: One-Time Strategy Generation

Adaptive planning is a one-time process (not a loop) that determines how to execute a complex query.

8.5.1 Planning Process

Input:
- User query
- Matter context
- Pre-linked relationships available
- Authorized cross-matter access (if any)

Planning Steps (One-Time):
1. Analyze query complexity
2. Determine which engines are needed
3. Identify if bounded loops are required
4. Define stop conditions for any loops
5. Create execution plan

Output:
- Execution plan (sequence of engine calls, loop definitions, stop conditions)
- Estimated execution time
- Required authorizations

8.5.2 Planning vs. Execution

Planning is:
- One-time (not iterative)
- Deterministic (same query → same plan, given same context)
- Fast (typically <2 seconds)

Execution may involve:
- Bounded loops (with stop conditions)
- Multiple engine calls
- Iterative pattern discovery

8.5.3 Tools and MCP Integration

Adaptive computation interacts with LDIP only via tools, not direct DB access.

Example tools (MCP-style):

tool.get_matter_documents(matter_id)

tool.retrieve_evidence(query, matter_id, engine_type)

tool.run_engine(engine_type, matter_id, params)

tool.get_pre_linked_relationships(matter_id, entity_id)

tool.get_timeline(matter_id)

tool.write_journal_entry(matter_id, user_id, payload)

tool.execute_bounded_loop(loop_type, stop_conditions, seed_data)

Each tool:

enforces auth

enforces matter isolation

enforces privilege filters

logs usage

enforces stop conditions

Adaptive computation has no secret backdoor.

8.6 Human-in-the-Loop Guarantees

Even at full adaptive computation power, LDIP must guarantee:

No adaptive computation can:

send something to court

email clients

update original documents

change matter status

modify pre-linked relationships (pre-linking is deterministic and immutable)

All outputs are:

drafts

suggestions

internal research

explicitly labeled as "AI-generated – for attorney review only"

include stop condition logs (which conditions triggered, iteration counts)

Senior attorneys can:

disable adaptive computation features

configure stop condition thresholds

limit adaptive computation to specific matters

enforce "manual approval required before bounded loops execute"

require user checkpoints at specific loop iterations

view audit logs of all loop executions

8.7 UX Surfaces for Adaptive Computation Outputs

From a junior lawyer's perspective, adaptive computation shows up as:

Query Results with Loop Information

"Connection Discovery Results (3 hops, stopped: no new findings):
– Found 6 connections between Entity A and Entity B
– Execution time: 9 seconds
– Stop condition triggered: No new findings after iteration 4
See evidence: [citations]"

Dashboards

"Adaptive Analysis Last Run: [date]
– Pattern Clustering: 3 clusters identified
– Cross-Matter Analysis: 2 authorized matters analyzed
– Stop conditions: All loops completed within time limits"

Journal Additions

Each adaptive computation run can create:

a journal entry

with:

what was checked

what found

evidence links

stop condition logs (iterations, termination reason)

execution plan used

So juniors and seniors can see:

"What adaptive analysis has been performed for this matter?"
"Which stop conditions were triggered?"
"How many iterations were executed?"

8.8 Safety & Ethics Constraints for Adaptive Computation

Adaptive computation must obey all constraints from:

Part 3 (question classification / unsafe queries)

Part 4 (reasoning rules, no legal conclusions)

Part 5 (security & ethics)

Part 6 (UX & memory constraints)

Part 7 (architecture & matter isolation, pre-linking)

Specifically, adaptive computation:

CANNOT:

infer malpractice

label behavior as "wrongdoing"

predict court outcomes

suggest legal strategy

use unauthorized cross-matter context

execute loops without stop conditions

proceed past stop conditions

modify pre-linked relationships

MUST:

show evidence for all findings

show limitations

show confidence scores

log everything for audit (including loop iterations, stop condition checks)

respect all stop conditions

return partial results if loops terminate early

use pre-linking as starting point (not bypass it)

8.9 Phased Rollout Plan

To avoid overwhelming complexity, LDIP should adopt a phased rollout:

Phase 1 (already defined) – Option 2 only

Orchestrator + engines + pre-linking

No adaptive computation

Question-driven workflows

All relationships pre-linked during ingestion

Phase 2 – Bounded Adaptive Computation (On-Demand)

One-time adaptive planning

Bounded loops for:
  - Novel connection discovery
  - Multi-hop relationship traversal
  - Iterative pattern clustering

Manual trigger only

User checkpoints at critical loop iterations

Phase 3 – Advanced Adaptive Patterns

Corruption pattern detection (India-specific)

Cross-matter network analysis (with strict authorization)

Complex pattern discovery across large document sets

Background adaptive analysis (optional, user-configurable)

Phase 4 – Advanced Stop Conditions & Optimization

Machine-learned stop condition tuning

Adaptive loop optimization

Predictive checkpoint placement

At every phase, the firm can opt out of adaptive computation features and keep LDIP fully deterministic.

### MVP Scope Limitation

Adaptive computation and bounded loops are disabled in MVP.

All workflows are initiated synchronously via user requests through the Orchestrator.

All relationships are pre-linked during ingestion (deterministic).

This section defines future architecture and does not imply availability of adaptive computation in MVP.
