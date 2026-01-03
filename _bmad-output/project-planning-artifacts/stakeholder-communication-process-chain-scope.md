# Stakeholder Communication: Process Chain Scope Clarification

**Date:** 2026-01-03
**From:** Product Management
**To:** All Stakeholders
**Subject:** Clarification on Timeline vs. Process Deviation Detection in MVP

---

## Purpose

This communication clarifies the scope of timeline-related functionality in MVP vs. Phase 2, ensuring alignment between what was discussed in early pitch materials and what the MVP will deliver.

---

## Key Clarification

### What MVP Will Deliver: Timeline Visualization ✅

The MVP includes a **Timeline Construction Engine** that:

- Extracts all dates and events from case documents
- Displays events in chronological order (vertical list, horizontal timeline, multi-track views)
- Links events to source documents with visual highlighting
- Shows which entities were involved in each event
- Flags date ambiguities (e.g., DD/MM vs. MM/DD format)

**Example MVP Output:**
```
TIMELINE: Shah v. Mehta Case
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 15 Mar 2023  |  Filing
                   Complaint filed by Shah
                   [View in Document → page 1]

📧 22 Mar 2023  |  Notice
                   Notice served to Mehta
                   [View in Document → page 45]

⚖️ 18 Jun 2023  |  Hearing
                   First hearing before Magistrate
                   [View in Document → page 78]

📄 30 Sep 2023  |  Order
                   Interim order passed
                   [View in Document → page 112]
```

---

### What MVP Will NOT Deliver: Process Deviation Detection ❌

The early pitch materials referenced detection of unusual patterns like:

> *"Notice sent 9 months after default - unusual. Typical notice period is 2-3 months."*

This **Process Chain Integrity** feature requires:

1. **Process Templates** - Definitions of what "typical" looks like for each legal process (SARFAESI, DRT, IBC, etc.)
2. **Baseline Data** - Statistical baselines from 10-20+ real matters to establish "normal" ranges
3. **Deviation Logic** - Rules to compare actual vs. expected timelines

**Why This Is Deferred:**
- We don't have validated process templates yet
- Creating accurate templates requires real matter data from MVP usage
- Inaccurate templates would produce misleading "deviation" flags
- Better to show accurate timelines now, add smart analysis later

---

## What This Means for Users

### MVP Experience

| Capability | Available? | Notes |
|------------|------------|-------|
| See all dates/events in chronological order | ✅ Yes | Full timeline extraction |
| Click events to see source documents | ✅ Yes | Visual citations |
| Filter by event type, actor, date range | ✅ Yes | Flexible exploration |
| Manually add events | ✅ Yes | User annotations |
| **Automatic "9 months is unusual" alerts** | ❌ No | Phase 2 |
| **"Missing step" detection** | ❌ No | Phase 2 |
| **Process template comparison** | ❌ No | Phase 2 |

### User Workaround for MVP

Attorneys can still identify unusual timelines manually:
1. View the timeline in LDIP
2. Use their expertise to recognize unusual gaps
3. Add notes via the research journal (if they spot something)
4. Verify their findings for court submission

---

## Phase 2 Plan

**Trigger:** After 6 months of MVP usage with 10-20+ real matters

**Process:**
1. Juhi (Product Owner) creates manual process templates from real matter data
2. Templates validated against actual outcomes
3. Template engine built with deviation detection
4. Process Chain Integrity Engine upgraded from basic to full

**Expected Phase 2 Output:**
```
⚠️ TIMELINE DEVIATION DETECTED

Notice Period Analysis:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Default Date: 15 Jan 2023
• Notice Date: 30 Sep 2023
• Actual Duration: 258 days (8.5 months)
• Typical Duration: 60-90 days

❗ This is 3x longer than typical for SARFAESI proceedings.
   Consider investigating reason for delay.

[✓ Verify] [✗ Dismiss] [📝 Add Note]
```

---

## Decision Rationale

| Factor | Decision |
|--------|----------|
| **Accuracy** | Ship accurate timelines now > ship potentially wrong deviation alerts |
| **User Trust** | Better to under-promise MVP, over-deliver Phase 2 |
| **Data-Driven** | Templates should come from real data, not guesses |
| **Timeline** | MVP in 15-16 months stays achievable |
| **Risk** | Lower risk of "false positive" alerts confusing attorneys |

---

## Action Required

**No action required** - this is an informational communication.

If you have questions about timeline capabilities or Phase 2 planning, please contact the Product Management team.

---

## References

- [Requirements-Baseline-v1.0.md](./Requirements-Baseline-v1.0.md) - See "Phase 2: TBD" section
- [Decision-Log.md](./Decision-Log.md) - Decision #6: Process Templates Deferred
- [MVP-Scope-Definition-v1.0.md](./MVP-Scope-Definition-v1.0.md) - Engines 4 & 5 scope

---

**Document Status:** FINAL
**Distribution:** All Stakeholders
**Classification:** Internal
