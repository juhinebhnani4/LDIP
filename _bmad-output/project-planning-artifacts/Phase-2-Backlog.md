# LDIP Phase 2 Backlog

**Status:** Deferred from MVP
**Created:** 2026-01-03
**Owner:** Juhi (Product Owner)
**Trigger:** After MVP completion + user creates process templates from 5+ real matters

---

## Document Purpose

This document captures all features, engines, and UI components that were explicitly deferred from MVP to Phase 2. Nothing is deleted - everything is preserved here with clear rationale and trigger criteria.

**Relationship to Requirements Baseline:**
- Requirements Baseline v1.0 remains the source of truth for MVP scope
- This document tracks Phase 2 scope for future planning
- Features move from here back to Requirements when Phase 2 planning begins

---

## Deferred Engines

### Engine 4: Documentation Gap Engine

**Original Scope:**
- Detect missing required documents (e.g., notice not served, affidavit not filed)
- Compare uploaded documents against process templates
- Flag gaps with severity levels (Critical/Important/Optional)
- Generate "missing documents checklist"

**Why Deferred (Decision 10, 2026-01-03):**
- Requires process templates that don't exist yet
- Process templates need to be created manually from real matter experience
- Templates vary by case type (securities fraud, benami, dematerialization)
- Cannot build meaningful gap detection without templates

**Dependency:**
- Juhi creates manual process templates from 5+ completed matters
- Templates define "expected documents" per case type

**Estimated Effort:** 3 weeks development

---

### Engine 5: Process Chain Integrity Engine

**Original Scope:**
- Validate event sequences against expected timelines
- Detect deviations from standard legal processes
- Flag timeline anomalies ("notice should come before attachment")
- Suggest missing procedural steps

**Why Deferred (Decision 10, 2026-01-03):**
- Requires "typical timeline" templates
- Different case types have different expected sequences
- Need real-world data to define "normal" vs "anomaly"

**Dependency:**
- Juhi creates process chain templates from 5+ completed matters
- Templates define expected event sequences per case type

**Estimated Effort:** 3 weeks development

---

## Deferred UI Features

### Contradictions Tab (Dedicated View)

**Original Scope (UX Section 11):**
- Entity-grouped contradiction display
- Side-by-side comparison view
- Severity-based filtering (High/Medium/Low)
- Contradiction resolution workflow
- Export contradictions as standalone report

**Why Deferred:**
- MVP has entity-based contradictions only (Contradiction Engine runs)
- Dedicated tab adds value when full contradiction analysis exists
- Entity-based contradictions can be shown in Verification Tab

**MVP Approach:**
- Contradictions appear in Verification Tab as finding type
- Users filter by type="Contradiction"
- All contradiction data visible, just in different location

**What Users Get in MVP:**
- ✅ Entity-based contradiction detection
- ✅ Contradiction findings in Verification Tab
- ✅ Filter to see only contradictions
- ✅ Verify/reject contradictions
- ❌ Dedicated tab with grouping
- ❌ Side-by-side comparison view

**Estimated Effort:** 2-3 weeks development

---

### Cross-Reference Map Visualization

**Original Scope (UX Section 13.3):**
- Interactive graph showing document relationships
- Click-to-filter by document
- Relationship strength indicators
- Visual navigation between documents
- Export map as image

**Why Deferred:**
- Graph visualization adds complexity without proportional MVP value
- Basic cross-reference links provide immediate utility
- Can be added when users request it

**MVP Approach:**
- Inline cross-reference links in PDF viewer (clickable)
- Cross-reference count shown in Documents Tab
- Click link to navigate to referenced document

**What Users Get in MVP:**
- ✅ Cross-reference extraction during ingestion
- ✅ Clickable links in PDF viewer
- ✅ Reference count per document
- ❌ Interactive graph visualization
- ❌ Relationship strength indicators

**Estimated Effort:** 2-3 weeks development

---

### Timeline Gap Detection UI

**Original Scope (UX Section 7.4):**
- Visual gap indicators on timeline
- "Expected gap" marking
- Gap investigation workflow
- "Add Missing Documents" action
- Gap explanations

**Why Deferred:**
- Requires Process Chain Engine (Engine 5) to detect gaps
- Engine 5 requires process templates
- Without templates, system can't know what's "missing"

**MVP Approach:**
- Timeline shows extracted events chronologically
- No gap detection or gap highlighting
- Users manually identify gaps by viewing timeline

**What Users Get in MVP:**
- ✅ Chronological event display
- ✅ Zoom levels (Day/Week/Month/Year)
- ✅ Event filtering by type
- ✅ Click to view source document
- ❌ Automatic gap detection
- ❌ Gap investigation workflow

**Estimated Effort:** Included with Engine 5 (3 weeks total)

---

## Phase 2 Trigger Criteria

Phase 2 planning should begin when ALL of the following are met:

| Criterion | Status | Verification |
|-----------|--------|--------------|
| MVP successfully deployed | ⬜ | Production launch complete |
| 5+ real matters processed by Juhi | ⬜ | Matter count in production |
| Manual process templates created | ⬜ | Templates documented |
| User feedback collected on MVP | ⬜ | Feedback synthesis document |
| Business case validated | ⬜ | User requests for Phase 2 features |

---

## Phase 2 Stories (Ready for Estimation)

These stories are ready to be pulled into Phase 2 sprint planning when triggered:

### Documentation Gap Engine Stories

```markdown
Story DG-1: Implement process template schema
As a system, I need to store process templates so gap detection can compare against expected documents.

Story DG-2: Create template management UI
As Juhi, I want to create and edit process templates so the system knows what documents to expect.

Story DG-3: Implement gap detection algorithm
As a litigator, I want the system to flag missing documents so I can identify gaps in my case file.

Story DG-4: Display gap findings in UI
As a litigator, I want to see missing documents highlighted so I can take action.
```

### Process Chain Engine Stories

```markdown
Story PC-1: Implement timeline template schema
As a system, I need to store expected event sequences so chain validation can detect anomalies.

Story PC-2: Create timeline template management UI
As Juhi, I want to define expected event sequences for different case types.

Story PC-3: Implement chain validation algorithm
As a litigator, I want the system to flag timeline anomalies so I can identify procedural issues.

Story PC-4: Display chain findings in Timeline Tab
As a litigator, I want to see deviations highlighted on the timeline.
```

### Contradictions Tab Stories

```markdown
Story CT-1: Implement dedicated Contradictions Tab
As a litigator, I want a dedicated tab for contradictions so I can focus on inconsistencies.

Story CT-2: Implement entity grouping
As a litigator, I want contradictions grouped by entity so I can see all conflicts per person/org.

Story CT-3: Implement side-by-side comparison
As a litigator, I want to compare contradicting statements side-by-side.

Story CT-4: Implement severity filtering
As a litigator, I want to filter by severity so I can prioritize high-impact contradictions.
```

### Cross-Reference Map Stories

```markdown
Story XR-1: Implement graph data structure
As a system, I need to model document relationships as a graph for visualization.

Story XR-2: Implement interactive graph UI
As a litigator, I want to see document relationships visually so I can navigate complex references.

Story XR-3: Implement click-to-filter
As a litigator, I want to click a document node to filter related documents.

Story XR-4: Implement export as image
As a litigator, I want to export the map for reports.
```

---

## Relationship to MVP

| Phase 2 Feature | MVP Alternative | User Impact |
|-----------------|-----------------|-------------|
| Documentation Gap Engine | Manual review | Users identify gaps manually |
| Process Chain Engine | Manual review | Users identify sequence issues manually |
| Contradictions Tab | Verification Tab filter | Same data, different location |
| Cross-Reference Map | Inline links | Basic navigation works |
| Timeline Gap UI | Chronological view | Users see timeline, no auto-gaps |

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-01-03 | Document created with all Phase 2 deferrals | John (PM) |

---

*This is a living document. Update as Phase 2 planning progresses.*
