# Jaanch.ai UX Rage Moments Analysis

**Date:** 2026-01-28
**Prepared by:** Sally (UX), John (PM), Winston (Architect)
**For:** Juhi
**Status:** CODE-VERIFIED Strategic Planning Document
**Last Updated:** 2026-01-29 (Post-Egress Optimization Review)

---

## 🎯 FIRST PRINCIPLES SPRINT (2 Weeks)

**The Hard Question:** With 95 rage moments documented, what actually matters?

**Answer:** Users leave for exactly 4 reasons:

| Core Problem | Root Cause | One Fix |
|--------------|------------|---------|
| **"I don't trust the answers"** | Bbox highlights wrong text | Confidence threshold ≥95% |
| **"I can't verify easily"** | Split-view cramps everything | PDF Modal (full focus) |
| **"I feel overwhelmed"** | 7 tabs, dense cards, filters everywhere | Spacing + tab collapse |
| **"It feels slow"** | No loading states | Skeleton loaders |

### The 5 Fixes (2 Weeks Total)

| Fix | Addresses | Effort | Ship By |
|-----|-----------|--------|---------|
| 1. Bbox confidence ≥95% | Trust | 1 hour | Day 1 |
| 2. Inline quotes in responses | Trust | 3-5 days | Week 1 |
| 3. PDF Modal (default) | Verification | 1 day | Day 2 |
| 4. Global spacing + tab consolidation | Overwhelm | 1 day | Day 3 |
| 5. Skeleton loaders all tabs | Speed | 3 hours | Day 1 |

### Week 1: Trust & Focus
```
Day 1: Bbox threshold + Skeleton loaders (4 hours)
Day 2: PDF Modal implementation (1 day)
Day 3: Global spacing + Header consolidation (4 hours)
Day 4-5: Inline quotes in chat responses (2 days)
```

### Week 2: Polish & Test
```
Day 6-7: Inline quotes continued + edge cases
Day 8: Tab consolidation (4+More dropdown)
Day 9: QA + bug fixes
Day 10: Deploy + monitor
```

### Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| "Citation wrong" complaints | High | Near zero |
| Time to verify a quote | 10+ clicks | 2 clicks |
| First-session bounce rate | High | -30% |
| "Overwhelming" feedback | Common | Rare |

**Everything else in this document is Phase 2+.** Ship these 5 fixes first, measure impact, then decide what's next.

---

## Executive Summary

This document catalogs **95 user rage moments** identified across the jaanch.ai user journey (including 7 new visual density issues). Each is assessed for:

- **Impact**: How severely this affects user retention (1-5, where 5 = user never returns)
- **Effort**: Engineering effort to fix (S/M/L/XL) — **NOW CODE-VERIFIED**
- **Risk**: Chance of breaking existing functionality (Low/Med/High/Critical)
- **Dependencies**: Other systems affected

### Key Finding: The Codebase Is More Mature Than Expected

After reviewing the actual implementation, we found:
- **Strong foundations** — RAG pipeline, matter isolation, streaming all production-ready
- **Many "fixes" are actually config/default changes** — not new code
- **Timeline reduced from 16 weeks to 13 weeks** based on actual effort

### The Hard Truth

Fixing everything = 6+ months of work + high risk of regression.
**We must be surgical.**

### Recommended Strategy (REVISED)

1. **Phase 0 (1 day)**: Zero-risk quick wins — bbox threshold, skeleton loaders, binary confidence
2. **Phase 0.5 (2-3 days)**: Visual density fixes — spacing, header, tabs, PDF modal ← NEW
3. **Phase 1 (1-2 weeks)**: Trust-building — inline quotes, query history UI
4. **Phase 2 (1 week)**: Simplification — timeline defaults, entity ranking
5. **Phase 3 (1 week)**: Session continuity — user journey state, welcome screens
6. **Phase 4 (2 weeks)**: Cross-matter search — extend existing patterns
7. **Phase 5 (2-3 weeks)**: View-only collaboration — leverage existing auth

---

## 🆕 RECENT COMMITS IMPACT (2026-01-29)

The following commits have been merged that affect our UX recommendations:

### What Was Just Implemented

| Commit | Change | UX Impact |
|--------|--------|-----------|
| `1332454` | Bbox `include_text` parameter + two-tier caching | ✅ PDF highlights load faster on repeat views |
| `050badb` | Covering indexes + selective column queries | ✅ Job polling 50-70% cheaper, slightly faster |
| `339a4c2` | Polling intervals increased (1s→3s, 2s→5s) | ⚠️ Processing status updates feel slower |
| `066f9da` | Dark mode disabled on mobile | 🔧 Consistency fix |

### What This Means for Our Sprint

**Still Required (NOT implemented):**
- ❌ **Bbox confidence threshold ≥95%** — API returns `confidence` field but NO filtering happens. All bboxes still shown regardless of quality. **This is still the #1 trust fix.**
- ❌ **PDF Modal** — Still uses cramped split-view
- ❌ **Inline quotes** — Not implemented
- ❌ **Tab consolidation** — Still 7 tabs
- ❌ **Global spacing** — Still tight

**Already Implemented (can skip):**
- ✅ **Bbox caching** — Two-tier cache (in-memory + localStorage) now exists in `useBoundingBoxes.ts`
- ✅ **Selective column queries** — Egress optimized

### Revised Day 1 Focus

Since caching is done, Day 1 simplifies:

```
Day 1 (NOW ~3 hours instead of 4):
├─ Bbox threshold 95%     │ 1 hour (STILL PRIORITY #1)
├─ Skeleton loaders       │ 2 hours
└─ Skip bbox caching      │ ALREADY DONE ✓
```

### Trade-off Alert: Polling Intervals

Polling was slowed from 1s→3s for processing status. This saves cost but users may notice:
- "Why is the progress bar stuck?" — It updates every 3s now, not 1s
- Consider adding a "last updated X seconds ago" indicator if complaints arise

---

## CODE VERIFICATION RESULTS

### What We Found Actually Exists

| Component | Status | Notes |
|-----------|--------|-------|
| **RAG Pipeline** | ✅ Production-ready | Hybrid search (BM25 + semantic + Cohere rerank) |
| **Embeddings** | ✅ Complete | pgvector storage, fallback to BM25 if incomplete |
| **Citation Extraction** | ✅ Complete | Gemini + regex, verification against Act documents |
| **Bbox Storage** | ✅ Complete | Full OCR bbox tracking with confidence scores |
| **Bbox Retrieval** | ✅ Complete | Split-view highlighting, canvas-based rendering |
| **Bbox Caching** | ✅ NEW (Jan 29) | Two-tier cache (in-memory + localStorage), 80% egress reduction |
| **Timeline** | ✅ Complete | 3 views, filtering EXISTS, anomaly detection EXISTS |
| **Entity Extraction** | ✅ Complete | MIG-based with fuzzy matching + alias tracking |
| **Matter Isolation** | ✅ 4-layer enforcement | RLS, namespace, query-level, API middleware |
| **Streaming** | ✅ Complete | SSE with engine traces, typing indicator |
| **Chat History** | ✅ Persisted | Per-matter localStorage + backend `/history` endpoint |
| **Zustand Stores** | ✅ Well-architected | Selectors pattern enforced, 10+ stores |

### What We Assumed Was Missing But Exists

| Feature | Reality |
|---------|---------|
| Chat history persistence | **EXISTS** — per-matter in localStorage + backend |
| Timeline filtering | **EXISTS** — event type, actor, date range, anomalies |
| Entity resolution | **EXISTS** — MIG-based with fuzzy matching |
| Q&A panel position persistence | **EXISTS** — persisted to localStorage |
| Skeleton component | **EXISTS** — basic `<Skeleton>` in ui/skeleton.tsx |

### What's Actually Missing (Confirmed)

| Feature | Status | Notes |
|---------|--------|-------|
| Bbox confidence threshold | **MISSING** | Bboxes shown regardless of confidence |
| Inline quotes in responses | **PARTIAL** | Prompts request `[1], [2]` but no quote extraction |
| "Key Events" timeline default | **MISSING** | All events shown equally |
| Entity relevance ranking | **MISSING** | No sorting by mention count |
| "Last session" recovery | **MISSING** | No tracking of last matter/tab/query |
| Cross-matter search | **MISSING** | But pattern exists in `search_with_library` |
| Collaboration/sharing | **MISSING** | But auth pattern exists |

---

## REVISED Phase 0: Actual 1-Day Wins

**Timeline:** 1 day
**Risk:** None to Low
**Theme:** Changes that leverage existing code

| # | Rage Moment | What Exists | What's Needed | Actual Effort |
|---|-------------|-------------|---------------|---------------|
| 31, 37 | "Highlight wrong paragraph" | `confidence` field in bbox table, `BboxOverlay.tsx` uses canvas | Add filter: `bboxes.filter(b => b.confidence >= 0.95)` | **1 HOUR** |
| 15, 32 | "Thinking/PDF slow" | Basic `<Skeleton>` component | Add `loading.tsx` to each tab route | **2-3 hours** |
| 24, 81 | "High confidence but wrong" | Confidence stored as 0-100 | Change display from `87%` to `Verified ✓` / `Needs Review` | **2 hours** |
| 36 | "Clicked citation, nothing" | Click handler in `SourceReference` | Add loading state while fetching document | **30 min** |
| 6 | "How long will this take?" | `processingStore` tracks jobs | Expose "12 of 47" in processing banner | **1 hour** |
| 1 | "Matter" jargon | Just UI copy | Find/replace "Matter" → "Case" | **1 hour** |

**Total Effort:** ~8 hours (1 day)
**Biggest Win:** Bbox confidence threshold eliminates Rage #31, #37 with 1 line of code

### The 1-Line Fix That Prevents Trust Destruction

```typescript
// frontend/src/components/features/pdf/BboxOverlay.tsx
// CURRENT: Shows all bboxes
bboxes.forEach(bbox => drawHighlight(bbox));

// FIXED: Only show high-confidence bboxes
bboxes
  .filter(bbox => bbox.confidence >= 0.95)
  .forEach(bbox => drawHighlight(bbox));
```

**Impact:** Eliminates "wrong highlight" rage moments that destroy user trust permanently.

---

## REVISED Phase 1: Trust Building

**Timeline:** 1-2 weeks
**Risk:** Low-Medium
**Theme:** Make answers verifiable at a glance

| # | Rage Moment | What Exists | What's Needed | Actual Effort |
|---|-------------|-------------|---------------|---------------|
| 23, 26 | "Answer wrong / no citation" | RAG returns chunks with text, prompts request `[1], [2]` | Extract quote from chunk, display inline below answer | **M (3-5 days)** |
| 17, 77 | "Can't see previous questions" | `chatStore.messages` persisted per-matter | Add collapsible "Previous questions" in QAPanel header | **S (1 day)** |
| 14 | "500-word essay" | RAG prompt in `generator.py` | Modify prompt: "Be concise. 2-3 sentences unless detail requested." | **XS (1 hour)** |
| 18 | "Which documents?" | Sources returned with response | Ensure `document_name` always shown in SourceReference | **XS (1 hour)** |

### Inline Quote Implementation

```typescript
// ChatMessage.tsx - Enhanced response display
<div className="response">
  {answer}

  {sources.map(source => (
    <blockquote className="border-l-2 pl-3 mt-2 text-sm text-muted-foreground">
      "{source.chunk_text.slice(0, 200)}..."
      <cite>— {source.document_name}, p. {source.page_number}</cite>
    </blockquote>
  ))}
</div>
```

**Note:** The chunk text is already returned by RAG. We just need to display it.

---

## REVISED Phase 2: Simplification

**Timeline:** 1 week
**Risk:** Low-Medium
**Theme:** Change defaults, not code

| # | Rage Moment | What Exists | What's Needed | Actual Effort |
|---|-------------|-------------|---------------|---------------|
| 40, 41 | "847 events, need 5" | Timeline filtering exists, event types classified | Add "Key Events" toggle, default ON. Filter: `confidence > 0.8 OR type IN (filing, judgment, breach)` | **S (1-2 days)** |
| 51 | "200 irrelevant names" | `mention_count` in MIG identity_nodes | Sort by mention count DESC, show top 10, "Show all" button | **S (1 day)** |
| 54 | "Everything needs verification" | Verification statuses: pending, verified, mismatch, etc. | Map to binary: "Verified" (verified) vs "Needs Review" (all others) | **XS (2 hours)** |
| 43 | "Can't filter by doc/party" | TimelineFilterBar has event type, actor, date filters | **ALREADY EXISTS** — may just need better UX visibility | **XS (review)** |

### Timeline "Key Events" Filter

```typescript
// TimelineContent.tsx - Add default filter
const [showKeyEventsOnly, setShowKeyEventsOnly] = useState(true);

const KEY_EVENT_TYPES = ['filing', 'judgment', 'breach', 'contract_signed', 'payment_due', 'hearing'];

const displayedEvents = showKeyEventsOnly
  ? events.filter(e => e.confidence > 0.8 || KEY_EVENT_TYPES.includes(e.event_type))
  : events;
```

---

## REVISED Phase 3: Session Continuity

**Timeline:** 1 week
**Risk:** Low (new store, no existing code modified)
**Theme:** Make the app remember the user

| # | Rage Moment | What Exists | What's Needed | Actual Effort |
|---|-------------|-------------|---------------|---------------|
| 74-77 | "Don't remember what I was doing" | Q&A panel position persisted, chat history persisted | New `userJourneyStore` with lastMatterId, lastTab, lastQuery | **M (3-4 days)** |
| 75 | "Looks same as yesterday" | Processing status banner exists | Extend: "3 documents ready since your last visit" | **S (1-2 days)** |

### User Journey Store Implementation

```typescript
// stores/userJourneyStore.ts
interface UserJourneyState {
  // Session tracking
  lastMatterId: string | null;
  lastTabPath: string | null;  // e.g., '/matter/123/timeline'
  lastQuery: string | null;
  lastVisitAt: Date | null;

  // Engagement metrics
  sessionCount: number;
  mattersCreated: number;
  questionsAsked: number;

  // Feature discovery
  tabsVisited: string[];
}

export const useUserJourneyStore = create(
  persist(
    (set, get) => ({
      // ... state
      recordMatterVisit: (matterId: string, tabPath: string) =>
        set({ lastMatterId: matterId, lastTabPath: tabPath, lastVisitAt: new Date() }),
      recordQuery: (query: string) =>
        set(state => ({ lastQuery: query, questionsAsked: state.questionsAsked + 1 })),
    }),
    { name: 'ldip-user-journey' }
  )
);
```

### Contextual Welcome Component

```typescript
// components/features/welcome/ContextualWelcome.tsx
function ContextualWelcome() {
  const { lastMatterId, lastQuery, lastVisitAt } = useUserJourneyStore();
  const hoursSinceLastVisit = /* calculate */;

  if (!lastMatterId) {
    return <FirstTimeWelcome />;
  }

  if (hoursSinceLastVisit < 4) {
    return <ReturningTodayWelcome lastMatterId={lastMatterId} lastQuery={lastQuery} />;
  }

  return <ReturningLaterWelcome lastMatterId={lastMatterId} />;
}
```

---

## REVISED Phase 4: Cross-Matter Search

**Timeline:** 2 weeks
**Risk:** Medium (extends existing pattern)
**Theme:** Leverage existing `search_with_library` pattern

### What Already Exists

```python
# backend/app/services/rag/hybrid_search.py
def search_with_library(self, matter_id, query, ...):
    """Searches matter docs + linked library docs"""
    # Already handles multi-namespace search
    # Already respects matter access permissions
```

### Extension Needed

```python
# backend/app/services/rag/hybrid_search.py
async def search_across_user_matters(
    self,
    user_id: str,
    query: str,
    limit_matters: int = 10,
    limit_per_matter: int = 5
) -> list[SearchResult]:
    """Search across all matters user has access to"""

    # Step 1: Get user's matter IDs (via matter_attorneys table)
    matter_ids = await self.get_user_matter_ids(user_id, limit=limit_matters)

    # Step 2: Search each matter (can parallelize)
    all_results = []
    for matter_id in matter_ids:
        results = await self.search(matter_id, query, limit=limit_per_matter)
        for r in results:
            r.source_matter_id = matter_id
        all_results.extend(results)

    # Step 3: Re-rank across all results
    return await self.rerank(all_results, query, limit=20)
```

### Frontend UI

```typescript
// QAPanel.tsx - Add scope toggle
<div className="search-scope">
  <RadioGroup value={searchScope} onValueChange={setSearchScope}>
    <RadioGroupItem value="current">This case only</RadioGroupItem>
    <RadioGroupItem value="all">All my cases</RadioGroupItem>
  </RadioGroup>
</div>

// Results grouped by matter
{searchScope === 'all' && (
  <div className="results-by-matter">
    {Object.entries(groupedResults).map(([matterId, results]) => (
      <MatterResultGroup key={matterId} matterId={matterId} results={results} />
    ))}
  </div>
)}
```

**Risk Mitigation:**
- User can only search matters they have access to (via `matter_attorneys` table)
- Results clearly show which matter each result came from
- No RLS bypass — same permission model as single-matter search

---

## REVISED Phase 5: View-Only Collaboration

**Timeline:** 2-3 weeks
**Risk:** Medium (auth changes, but pattern exists)
**Theme:** Minimal viable sharing

### What Already Exists

```python
# backend/app/api/dependencies.py
async def validate_matter_access(matter_id: str, user_id: str) -> bool:
    """Checks if user has access via matter_attorneys table"""
    # This pattern can be extended to include collaborators
```

### Extension Needed

**Database:**
```sql
CREATE TABLE matter_collaborators (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID REFERENCES matters(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor')),
  invited_by UUID REFERENCES auth.users(id),
  invited_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(matter_id, user_id)
);

-- RLS policy
CREATE POLICY "Users see collaborations they're part of"
ON matter_collaborators FOR SELECT
USING (user_id = auth.uid() OR invited_by = auth.uid());
```

**Backend:**
```python
# Extend validate_matter_access
async def validate_matter_access(matter_id: str, user_id: str) -> bool:
    # Check matter_attorneys (existing)
    is_attorney = await check_matter_attorney(matter_id, user_id)
    if is_attorney:
        return True

    # Check matter_collaborators (new)
    is_collaborator = await check_matter_collaborator(matter_id, user_id)
    return is_collaborator
```

**Frontend:**
```typescript
// ShareDialog.tsx
function ShareDialog({ matterId }: { matterId: string }) {
  const [email, setEmail] = useState('');

  const handleInvite = async () => {
    await api.post(`/matters/${matterId}/collaborators`, {
      email,
      role: 'viewer'
    });
  };

  return (
    <Dialog>
      <DialogContent>
        <h3>Share this case</h3>
        <Input
          placeholder="colleague@lawfirm.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />
        <Button onClick={handleInvite}>Invite (View Only)</Button>

        <CollaboratorList matterId={matterId} />
      </DialogContent>
    </Dialog>
  );
}
```

**Scope for V1:**
- View-only access only (no edit permissions)
- Invite by email (must have jaanch.ai account)
- Owner can remove collaborators
- No comments, no activity feed (future phases)

---

## Complete Rage Moments Catalog (CODE-VERIFIED)

### Stage 1: First Landing & Onboarding

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 1 | "What even is this?" (jargon) | 3 | **XS** | None | 0 | Find/replace UI copy |
| 2 | "Need account to try" | 4 | L | High | Skip | Auth complexity |
| 3 | "Looks like every other AI tool" | 3 | M | Low | 2 | Branding/UX |
| 4 | "Too many options first screen" | 4 | XS | None | 0 | "Start here" badge |
| 5 | "What's difference between tabs" | 4 | M | High | 3+ | Progressive disclosure |

### Stage 2: Document Upload & Processing

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 6 | "How long will this take?" | 3 | **XS** | None | 0 | `processingStore` exists |
| 7 | "Can't do anything while processing" | 3 | L | Med | 2 | Progressive availability |
| 8 | "Failed but doesn't say why" | 4 | M | Low | 1 | Error detail display |
| 9 | "Can't delete wrong file" | 3 | M | Med | 2 | Document management |
| 10 | "Uploaded same file twice" | 2 | M | Low | 2 | Dupe detection |
| 11 | "Can't read scanned PDF" | 4 | XL | High | Skip | OCR external service |
| 12 | "Processing complete, nothing changed" | 3 | **XS** | None | 0 | Toast notification |
| 13 | "Which 3 of 100 docs failed?" | 3 | S | Low | 1 | Failure manifest |

### Stage 3: Asking Questions (Chat)

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 14 | "Simple Q, 500-word essay" | 3 | **XS** | Low | 1 | Prompt change only |
| 15 | "Thinking for 30 seconds" | 4 | **XS** | None | 0 | Skeleton exists |
| 16 | "Answered different question" | 4 | L | High | 3+ | Query understanding |
| 17 | "Can't see previous questions" | 3 | **S** | Low | 1 | Chat history EXISTS |
| 18 | "Which documents?" | 4 | **XS** | Low | 1 | Sources returned |
| 19 | "Confused Party A and B" | 5 | L | High | 3+ | Entity disambiguation |
| 20 | "Says no info but it's there" | 5 | L | High | 3+ | Retrieval improvement |
| 21 | "Contradicts previous answer" | 4 | L | High | 3+ | Consistency |
| 22 | "Won't answer, says legal advice" | 3 | S | Med | 2 | Guardrail tuning |

### Stage 4: Answers & Citations

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 23 | "THE ANSWER IS WRONG" | 5 | **M** | Med | 1 | Inline quotes help |
| 24 | "High confidence but wrong" | 5 | **XS** | Low | 0 | Binary display change |
| 25 | "Can't copy answer properly" | 2 | S | None | 0 | Clipboard fix |
| 26 | "No citation" | 4 | **S** | Low | 1 | Sources exist, display them |
| 27 | "5 sources say same thing" | 2 | M | Low | 2 | Deduplication |
| 28 | "Page 12 is actually page 14" | 5 | M | Med | 1 | OCR audit needed |
| 29 | "Quote doesn't match exactly" | 4 | M | Med | 1 | Verbatim extraction |
| 30 | "Answer from WRONG case" | 5 | **XS** | Critical | 0 | 4-layer isolation EXISTS |

### Stage 5: PDF Viewer & Bounding Boxes

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 31 | "Highlight wrong paragraph" | 5 | **1 HOUR** | Low | 0 | Confidence threshold filter |
| 32 | "PDF takes forever" | 3 | **XS** | None | 0 | Skeleton exists |
| 33 | "Scroll is janky" | 3 | M | Med | 2 | Virtualization exists |
| 34 | "Highlight covers 3 pages" | 4 | M | Med | 1 | Bbox size limit |
| 35 | "Text blurry/small" | 3 | S | Low | 2 | Zoom controls exist |
| 36 | "Clicked citation, nothing" | 4 | **30 min** | None | 0 | Loading state |
| 37 | "Bbox slightly off" | 5 | **1 HOUR** | Low | 0 | Same as #31 |
| 38 | "Can't search in PDF" | 3 | M | Med | 2 | PDF.js supports it |
| 39 | "Split view cramped" | 2 | **XS** | Low | - | Resizable panels EXIST |

### Stage 6: Timeline

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 40 | "847 events, need 5" | 4 | **S** | Med | 2 | Change default filter |
| 41 | "Every email is event" | 3 | **S** | Med | 2 | Same as #40 |
| 42 | "Dates are wrong" | 5 | L | High | 3+ | Date parsing |
| 43 | "Can't filter by doc/party" | 3 | **EXISTS** | - | - | TimelineFilterBar |
| 44 | "Events not chronological" | 4 | S | Med | 1 | Sort bug |
| 45 | "Can't export timeline" | 3 | M | Low | 2 | Export feature |
| 46 | "Same date different times" | 3 | S | Med | 2 | Time granularity |
| 47 | "Missed important event" | 5 | L | High | 3+ | Extraction improvement |

### Stage 7: Entities

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 48 | "Singh ≠ Mr. Singh" | 4 | **EXISTS** | - | - | MIG resolver EXISTS |
| 49 | "Merged two companies" | 4 | M | High | 3+ | Resolver tuning |
| 50 | "Law firm listed as party" | 3 | M | Med | 2 | Role classification |
| 51 | "200 irrelevant names" | 3 | **S** | Low | 2 | Sort by mention_count |
| 52 | "Can't manually correct" | 3 | M | Med | 2 | Edit UI |
| 53 | "Relationships wrong" | 4 | L | High | 3+ | Relationship extraction |

### Stage 8: Verification & Contradictions

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 54 | "Everything needs verification" | 4 | **XS** | Low | 2 | Binary status display |
| 55 | "False positive contradiction" | 3 | M | Med | 2 | Threshold tuning |
| 56 | "Missed contradiction" | 4 | L | High | 3+ | Detection improvement |
| 57 | "Verification doesn't persist" | 3 | **EXISTS** | - | - | Check implementation |
| 58 | "Can't dismiss false positive" | 3 | S | Low | 2 | Dismiss action |

### Stage 9: Search & Navigation

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 59 | "Search found nothing" | 4 | L | High | 3+ | Retrieval improvement |
| 60 | "Results not ranked" | 3 | **EXISTS** | - | - | Cohere rerank EXISTS |
| 61 | "Can't find previous view" | 3 | M | Low | 2 | Breadcrumbs |
| 62 | "Clicked link, lost place" | 3 | S | Low | 1 | Navigation state |
| 63 | "Search single matter only" | 2 | **M** | Med | 4 | Cross-matter search |

### Stage 10: Export & Output

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 64 | "Export to Word broken" | 4 | M | Med | 2 | Template fix |
| 65 | "Can't export partial" | 3 | M | Low | 2 | Selection export |
| 66 | "Missing page numbers" | 4 | S | Low | 1 | Include in template |
| 67 | "Can't share" | 3 | **M** | Med | 5 | View-only sharing |
| 68 | "Export takes forever" | 2 | M | Med | 2 | Async export |

### Stage 11: Performance & Latency

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 69 | "Every tab 5 seconds" | 4 | M | Med | 2 | Pre-fetch adjacent tabs |
| 70 | "App freezes" | 4 | M | High | 2 | Render optimization |
| 71 | "Typing laggy" | 3 | **XS** | Low | 0 | Reduce debounce |
| 72 | "Logged out randomly" | 4 | M | Med | 2 | Session handling |
| 73 | "Mobile broken" | 3 | XL | High | Skip | Separate effort |

### Stage 12: Returning Users

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 74 | "Don't remember" | 4 | **M** | Low | 3 | userJourneyStore |
| 75 | "Same as yesterday" | 4 | **S** | Med | 3 | Welcome screen |
| 76 | "Which docs reviewed?" | 3 | M | Med | 2 | Read tracking |
| 77 | "Previous questions" | 3 | **S** | Low | 1 | Chat history UI |
| 78 | "No notification" | 3 | M | Med | 2 | Push/email |

### Stage 13: Trust & Accuracy

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 79 | "Wrong once, never again" | 5 | - | - | - | Meta (fixed by trust stack) |
| 80 | "Confidently wrong" | 5 | **XS** | Low | 0 | Binary confidence |
| 81 | "Certain vs guessing?" | 4 | **XS** | Low | 0 | Same as #24 |
| 82 | "Making up facts" | 5 | L | High | 3+ | Hallucination reduction |
| 83 | "Summary without sources" | 4 | M | Med | 1 | Enforce source display |

### Stage 14: The "Why Bother" Moments

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 84 | "Longer than manual" | 5 | - | - | - | Meta |
| 85 | "Still verify everything" | 5 | - | - | - | Meta |
| 86 | "Paralegal better" | 5 | - | - | - | Meta |
| 87 | "Can't explain to partners" | 4 | - | - | - | Meta |
| 88 | "Learning curve" | 4 | - | - | - | Meta |

### Stage 15: Visual Density & Layout (NEW)

| # | Rage | Impact | Effort | Risk | Phase | Notes |
|---|------|--------|--------|------|-------|-------|
| 89 | "Everything feels cramped/tight" | 4 | **S** | None | 0.5 | Global CSS spacing |
| 90 | "Header has too many buttons" | 3 | **S** | Low | 0.5 | Overflow menu |
| 91 | "7 tabs is overwhelming" | 4 | **S** | Low | 0.5 | 4 + More dropdown |
| 92 | "Filter bar wastes space" | 3 | **XS** | None | 0.5 | Collapse by default |
| 93 | "Cards too dense, can't scan" | 3 | **S** | Low | 0.5 | Whitespace redesign |
| 94 | "PDF split-view makes everything tiny" | 4 | **M** | Low | 0.5 | Modal as default |
| 95 | "Q&A messages squeezed together" | 3 | **XS** | None | 0.5 | Message padding |

---

## REVISED Implementation Roadmap

```
┌─────────────────────────────────────────────────────────────────────┐
│  CODE-VERIFIED IMPLEMENTATION ROADMAP                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Phase 0 (Day 1)           │ ~8 hours                              │
│  ├─ Bbox threshold 95%     │ 1 hour (!!! biggest trust win)        │
│  ├─ loading.tsx all tabs   │ 2-3 hours                             │
│  ├─ Binary confidence UI   │ 2 hours                               │
│  ├─ Citation click loading │ 30 min                                │
│  ├─ Processing progress    │ 1 hour                                │
│  └─ "Matter" → "Case"      │ 1 hour                                │
│                                                                     │
│  Phase 0.5 (Days 2-4)      │ 2-3 days  ← NEW: VISUAL DENSITY       │
│  ├─ Global spacing increase│ 1-2 hours (CSS only)                  │
│  ├─ Header consolidation   │ 2 hours (overflow menu)               │
│  ├─ Tab consolidation 4+   │ 3 hours (4 visible + More dropdown)   │
│  ├─ Filter bar collapse    │ 2 hours (hidden by default)           │
│  ├─ Card whitespace        │ 1 day (visual hierarchy)              │
│  ├─ PDF Modal (default)    │ 1 day (!!! fixes split-view cramping) │
│  └─ Q&A panel spacing      │ 2 hours (message breathing room)      │
│                                                                     │
│  Phase 1 (Weeks 2-3)       │ 1-2 weeks                             │
│  ├─ Inline quote display   │ 3-5 days (chunk text exists)          │
│  ├─ Query history UI       │ 1 day (chatStore exists)              │
│  ├─ Shorter responses      │ 1 hour (prompt change)                │
│  └─ Source clarity         │ 1 hour (display fix)                  │
│                                                                     │
│  Phase 2 (Week 4)          │ 1 week                                │
│  ├─ Timeline "Key Events"  │ 1-2 days (change default filter)      │
│  ├─ Entity ranking         │ 1 day (sort by mention_count)         │
│  └─ Binary verification    │ 2 hours (UI mapping)                  │
│                                                                     │
│  Phase 3 (Weeks 5-6)       │ 1 week                                │
│  ├─ userJourneyStore       │ 3-4 days (new store)                  │
│  └─ Welcome screens        │ 2-3 days (conditional UI)             │
│                                                                     │
│  Phase 4 (Weeks 7-8)       │ 2 weeks                               │
│  └─ Cross-matter search    │ Extend search_with_library pattern    │
│                                                                     │
│  Phase 5 (Weeks 9-11)      │ 2-3 weeks                             │
│  └─ View-only sharing      │ Extend validate_matter_access         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

TOTAL: 11-12 weeks
```

---

## Visual Density & Layout Fixes (NEW)

**Timeline:** 2-3 days (can run parallel to Phase 0-1)
**Risk:** Low (CSS/layout changes, no logic changes)
**Theme:** Make the app breathe

### The Problem

The workspace feels cramped because:
1. **5 layers of UI** compete for attention (header, tabs, filters, content, Q&A panel)
2. **Minimal whitespace** — everything edge-to-edge with small padding
3. **PDF split-view** creates 3-way squeeze when opened
4. **Visual hierarchy is flat** — everything screams equally

### New Rage Moments (Added to Catalog)

| # | Rage Moment | Impact | Effort | Phase |
|---|-------------|--------|--------|-------|
| 89 | "Everything feels cramped/tight" | 4 | S | 0.5 |
| 90 | "Header has too many buttons" | 3 | S | 0.5 |
| 91 | "7 tabs is overwhelming" | 4 | S | 0.5 |
| 92 | "Filter bar takes up space even when not filtering" | 3 | XS | 0.5 |
| 93 | "Cards are too dense, can't scan" | 3 | S | 0.5 |
| 94 | "PDF split-view makes everything tiny" | 4 | M | 0.5 |
| 95 | "Q&A messages are squeezed together" | 3 | XS | 0.5 |

### Fix 1: Global Spacing Increase

**Current:** `p-2`, `p-3`, `gap-2`, `gap-3`
**Proposed:** `p-4`, `p-6`, `gap-4`, `gap-6`

```css
/* globals.css or tailwind overrides */

/* Workspace content areas */
.workspace-content {
  @apply p-6 gap-6;  /* was p-3 gap-3 */
}

/* Cards */
.card, [data-slot="card"] {
  @apply p-5 space-y-3;  /* was p-3 space-y-1 */
}

/* Chat messages */
.chat-message {
  @apply py-4 px-4;  /* was py-2 px-3 */
}

/* Tab bar */
.tab-item {
  @apply px-4 py-2.5;  /* was px-2 py-1 */
}
```

**Effort:** 1-2 hours
**Risk:** None

### Fix 2: Header Consolidation

**Current:**
```
← Back | Matter Name ✏️ | Processing... | 47 docs | ⚠️ Issues | Export ▾ | Share | ⚙️ | 🗑️
```

**Proposed:**
```
← | Singh vs. Builders Ltd                                    ⋮
    Processing 12/47...
```

Move to overflow menu `⋮`:
- Export
- Share
- Settings
- Delete

**Effort:** 2 hours
**Risk:** Low

### Fix 3: Tab Consolidation (4 + More)

**Current:** 7 tabs always visible
```
Summary | Timeline | Entities | Citations | Contradictions | Verification | Documents
```

**Proposed:** 4 primary + overflow
```
Summary | Timeline | Documents | More ▾
                                 └─ Entities
                                 └─ Citations
                                 └─ Contradictions
                                 └─ Verification
```

**Implementation:**
```typescript
// WorkspaceTabBar.tsx
const PRIMARY_TABS = ['summary', 'timeline', 'documents'];
const OVERFLOW_TABS = ['entities', 'citations', 'contradictions', 'verification'];

<TabsList>
  {PRIMARY_TABS.map(tab => <TabItem key={tab} />)}
  <DropdownMenu>
    <DropdownMenuTrigger>More ▾</DropdownMenuTrigger>
    <DropdownMenuContent>
      {OVERFLOW_TABS.map(tab => <DropdownMenuItem key={tab} />)}
    </DropdownMenuContent>
  </DropdownMenu>
</TabsList>
```

**Effort:** 3 hours
**Risk:** Low

### Fix 4: Filter Bar Collapse

**Current:** Always visible with 4-5 dropdowns
```
┌──────────────────────────────────────────────────────────┐
│ Event Type ▾ | Actor ▾ | Date From 📅 | Date To 📅 | ☐ Anomalies │
└──────────────────────────────────────────────────────────┘
```

**Proposed:** Collapsed by default
```
┌──────────────────────────────────────────────────────────┐
│ Showing 5 key events                         [🔍 Filter] │
└──────────────────────────────────────────────────────────┘
```

**Implementation:**
```typescript
const [filtersExpanded, setFiltersExpanded] = useState(false);

<div className="flex justify-between items-center">
  <span>Showing {events.length} events</span>
  <Button variant="ghost" onClick={() => setFiltersExpanded(!filtersExpanded)}>
    <Filter className="h-4 w-4 mr-2" />
    Filter
  </Button>
</div>

{filtersExpanded && <TimelineFilterBar />}
```

**Effort:** 2 hours
**Risk:** None

### Fix 5: Card Whitespace Redesign

**Current card:**
```
┌─────────────────────────────────────────────────────────┐
│ Nov 15, 2024 | Contract | Singh, ABC Corp | High | ✓    │
│ Contract signed between Singh and ABC Corp for...       │
│ Source: Contract.pdf p.1 | Confidence: 94% | [Edit][Del]│
└─────────────────────────────────────────────────────────┘
```

**Proposed card:**
```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Contract Signed                                        │
│  November 15, 2024                                      │
│                                                         │
│  Singh ↔ ABC Corp                                       │
│                                                         │
│  Contract.pdf, page 1                      ✓ Verified   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Changes:**
- Remove inline actions (move to hover or card click)
- Remove confidence % (use checkmark for verified)
- More vertical padding
- Clearer visual hierarchy (title → date → parties → source)

**Effort:** 1 day
**Risk:** Low

### Fix 6: PDF Modal Instead of Split-View (CRITICAL)

**Current behavior:**
Click citation → Split-view opens → Content + PDF + Q&A all cramped

**Proposed behavior:**
Click citation → Modal overlay opens → Full-focus PDF → Escape to return

**Implementation:**
```typescript
// pdfSplitViewStore.ts - Add modal mode
interface PdfViewerState {
  // Existing
  isOpen: boolean;
  isSplitView: boolean;

  // New
  isModalOpen: boolean;
  viewMode: 'modal' | 'split' | 'replace';
}

// Default to modal for citation clicks
openPdfViewer: (doc, mode: 'modal' | 'split' = 'modal') => {
  if (mode === 'modal') {
    set({ isModalOpen: true, documentUrl: doc.url, ... });
  } else {
    set({ isSplitOpen: true, ... });
  }
}
```

**Modal component:**
```typescript
// PdfModal.tsx
function PdfModal() {
  const { isModalOpen, documentUrl, documentName, currentPage, boundingBoxes, closePdfModal } = usePdfStore();

  if (!isModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6">
      <div className="bg-background rounded-lg w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <div>
            <h2 className="font-semibold">{documentName}</h2>
            <p className="text-sm text-muted-foreground">Page {currentPage}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={closePdfModal}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* PDF Viewer - Full focus */}
        <div className="flex-1 overflow-hidden p-4">
          <PdfViewer url={documentUrl} bboxes={boundingBoxes} />
        </div>

        {/* Footer controls */}
        <div className="p-4 border-t flex justify-between items-center">
          <PaginationControls />
          <div className="flex gap-2">
            <ZoomControls />
            <Button variant="outline" onClick={() => switchToSplitView()}>
              Open in Split View
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Keyboard support:**
- `Escape` — Close modal
- `←` `→` — Previous/next page
- `+` `-` — Zoom

**When to use split-view:**
- User explicitly clicks "Open in Split View"
- User is in Documents tab browsing (not verifying)
- Comparison mode (future feature)

**Effort:** 1 day
**Risk:** Low (additive, doesn't break existing)

### Fix 7: Q&A Panel Breathing Room

**Current:**
```
┌─────────────────────────┐
│ Position: ⚙️            │
│ User: What is the...    │
│ AI: The payment dead... │
│ [Source][Source]        │
│ User: And what about... │
└─────────────────────────┘
```

**Proposed:**
```
┌─────────────────────────────┐
│                             │
│  You                        │
│  What is the deadline?      │
│                             │
│  ─────────────────────────  │
│                             │
│  jaanch                     │
│  The payment deadline is    │
│  November 15, 2024.         │
│                             │
│  > "...no later than        │
│    November 15, 2024..."    │
│    — Contract.pdf, p.12     │
│                             │
└─────────────────────────────┘
```

**CSS changes:**
```css
.chat-message {
  @apply py-5 px-4;
}

.chat-message + .chat-message {
  @apply border-t border-border/50;
}

.message-sources {
  @apply mt-3 space-y-2;
}
```

**Effort:** 2 hours
**Risk:** None

---

### Visual Density Implementation Summary

| Fix | Addresses Rage # | Effort | Risk |
|-----|------------------|--------|------|
| Global spacing | 89 | 1-2 hours | None |
| Header consolidation | 90 | 2 hours | Low |
| Tab consolidation | 91 | 3 hours | Low |
| Filter bar collapse | 92 | 2 hours | None |
| Card whitespace | 93 | 1 day | Low |
| **PDF Modal** | **94** | **1 day** | **Low** |
| Q&A spacing | 95 | 2 hours | None |

**Total: 2-3 days**

---

### Before & After

**Before (Current):**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ ← | Name ✏️ | Status | Stats | Export | Share | ⚙️ | 🗑️                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Summary|Timeline|Entities|Citations|Contradictions|Verification|Docs    │
├─────────────────────────────────────────────────────────────────────────┤
│ [Filter][Filter][Filter][Filter][Sort]                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ Content (squeezed) │ PDF (squeezed) │ Q&A (squeezed)                    │
│ CardCardCardCard   │ [highlight]    │ msgmsgmsgmsg                      │
│ CardCardCardCard   │                │ srcssrcsrcs                        │
└─────────────────────────────────────────────────────────────────────────┘
```

**After (Proposed):**
```
┌─────────────────────────────────────────────────────────────────────────┐
│ ←  Singh vs. Builders Ltd                                          ⋮   │
│     Processing 12/47...                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Summary    Timeline    Documents    More ▾                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   5 Key Events                                          [🔍 Filter]     │
│                                                                         │
│   ┌───────────────────────────────────────────────────────────────┐     │
│   │                                                               │     │
│   │  Contract Signed                                              │     │
│   │  November 15, 2024                                            │     │
│   │                                                               │     │
│   │  Singh ↔ ABC Corp                                             │     │
│   │                                                               │     │
│   └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
│   [Show all 847 events]                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

(Q&A Panel collapsed to 💬 button or in right sidebar with proper spacing)
(PDF opens as MODAL overlay when citation clicked)
```

---

## What To Skip (Confirmed)

| # | Feature | Why Skip |
|---|---------|----------|
| 2 | Trial without account | Auth complexity, security risk |
| 11 | Better OCR for scans | External service (Google Document AI) |
| 73 | Mobile optimization | Separate effort, different team |
| 16, 19, 20 | Query understanding | Deep LLM improvements, high risk |
| 42, 47 | Date extraction accuracy | Complex NLP, diminishing returns |

---

## Key Insights From Code Review

### 1. The 1-Hour Trust Fix

The bbox confidence threshold in `BboxOverlay.tsx` is a **1-hour fix** that eliminates the #1 trust destroyer: wrong highlights.

### 2. Many Features Already Exist

- Timeline filtering: **EXISTS** (just need better defaults)
- Entity resolution: **EXISTS** (MIG with fuzzy matching)
- Chat history: **EXISTS** (persisted per-matter)
- Search ranking: **EXISTS** (Cohere rerank)

### 3. Cross-Matter Search Is Tractable

The `search_with_library` pattern already handles multi-namespace search. Cross-matter search is an extension, not a rewrite.

### 4. Collaboration Extends Existing Auth

The `validate_matter_access` pattern can be extended to include collaborators. No auth rewrite needed.

---

## Resource Requirements (Revised)

| Phase | Frontend | Backend | Duration |
|-------|----------|---------|----------|
| 0 | 1 day | 0 | 1 day |
| 1 | 1 week | 2 days | 2 weeks |
| 2 | 1 week | 0 | 1 week |
| 3 | 1 week | 0 | 1 week |
| 4 | 3 days | 1 week | 2 weeks |
| 5 | 1 week | 1 week | 2-3 weeks |

**Total: 1 senior frontend dev + 0.5 backend dev for 11 weeks**

---

## Success Metrics

### Phase 0 Success (After Day 1)
- [ ] Zero wrong bbox highlights (threshold working)
- [ ] Skeleton loaders visible on all tabs
- [ ] Binary confidence displayed

### Phase 1 Success (After 2 Weeks)
- [ ] Inline quotes visible in 100% of responses
- [ ] Query history accessible in QAPanel
- [ ] "Wrong answer" reports down 30%

### Phase 2 Success (After 4 Weeks)
- [ ] Timeline defaults to "Key Events"
- [ ] Entity list shows top 10 by default
- [ ] Avg time on Timeline tab down 50%

### Phase 3-5 Success (After 11 Weeks)
- [ ] "Continue where I left off" used by 60%+ returning users
- [ ] Cross-matter search available
- [ ] View-only sharing launched

---

## Summary

**What we learned from the code review:**
1. The codebase is more mature than expected — many features exist
2. Most "fixes" are default/display changes, not new code
3. The biggest trust fix (bbox threshold) takes 1 hour
4. Cross-matter search and collaboration extend existing patterns
5. Timeline reduced from 16 weeks to 11-12 weeks

**What we learned about visual density:**
1. The app feels cramped because 5 layers of UI compete for attention
2. PDF split-view creates unusable 3-way squeeze — modal is better
3. 2-3 days of CSS/layout work will make the app "breathe"
4. **PDF Modal is the single biggest UX improvement for verification flow**

**Core philosophy:**
> *"The code is good. The defaults are wrong. Fix the defaults."*
> *"The app needs to breathe. Give users focus, not a dashboard."*

---

*Document prepared by Sally (UX), John (PM), and Winston (Architect)*
*Code review completed: 2026-01-28*
*Visual density section added: 2026-01-28*
*Last updated: 2026-01-28*
