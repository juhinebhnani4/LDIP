# Frontend UX & QA Audit — jaanch.ai

> **Live status of all FE-### symptoms and FE-ARCH-NN debts lives in `BUGS.md`** (§10 and §0 respectively). This file is the dated evidence snapshot — screenshots, viewport measurements, console captures, repro steps, suggested fixes. Update statuses in `BUGS.md`, not here.

**Date:** 2026-05-20
**Target:** https://www.jaanch-ai.in (production)
**Account:** Juhi Nebhnani (logged-in session)
**Method:** Live browser drive via Playwright MCP — Chromium, viewports 1440×900 (desktop), 768×1024 (tablet), 390×844 (mobile), 320×568 (small mobile).
**Pages covered:** Dashboard, Matter detail (Summary / Documents / Verification), Document viewer, Upload, Activity, Notifications panel, Global search, Profile menu, Help Center, 404 route, invalid-matter route.

---

## 1. Executive summary

| Severity | Count |
|----------|-------|
| P0 Blocker | 0 |
| P1 Major | 3 |
| P2 Moderate | 10 |
| P3 Minor | 9 |
| **Total** | **22** |

These 22 symptoms collapse into **4 architectural root causes** — see **§3. Architectural gaps**, the section to read if you are deciding what to actually fix.

**Overall verdict:** The desktop experience is solid — clean pages, no console errors on the main routes, well-built Verification Center and document viewer. **The app is effectively broken on mobile**, and **error/edge states are unhandled**. A lawyer opening this on a phone, or clicking a stale matter link, gets a poor experience.

### The 5 worst issues
1. **FE-001 (P1)** — The matter workspace "Ask jaanch" side panel **never collapses**. It stays side-by-side from 1440px down to 320px, squeezing the actual matter content into an unusable ~190px column on phones. Every matter sub-page is affected.
2. **FE-002 (P1)** — On the matter page at mobile widths, the header **Export / More-actions buttons render off-screen and are clipped** — completely inaccessible on a phone.
3. **FE-003 (P1)** — Visiting an invalid or deleted matter URL renders a **broken "Untitled Matter" workspace with 18 console errors** instead of a clean "not found" page.
4. **FE-010 (P2)** — **No custom 404 page** — bare, unstyled Next.js default with no branding, navigation, or way back.
5. **FE-004 (P2)** — Dashboard has **page-level horizontal scroll at 320px**, and the Quick Stats cards truncate their labels ("Active Ma…", "Veri…").

---

## 2. Issues

### FE-001 — Matter "Ask jaanch" panel never collapses (breaks all matter pages on mobile)
- **Severity:** P1 Major (borderline P0 for mobile users)
- **Category:** B. Responsive
- **Page:** Every matter sub-route — `/matter/{id}/summary`, `/documents`, `/verification`, `/timeline`, `/citations`, `/entities`
- **Viewports:** 768, 390, 320 (all non-desktop)
- **Description:** The matter workspace is a two-pane layout: main content + a persistent "Ask jaanch" Q&A panel on the right. This split never reflows. At 768px the main content is squeezed to ~55%; at 390px and 320px the main content (Summary, Parties, Verification table, etc.) is crushed into a ~190px column while "Ask jaanch" eats the other half. Text wraps one or two words per line; the page is not usable on a phone.
- **Evidence:** `matter-busy-768.png`, `matter-busy-390.png`, `verification-390.png`
- **Repro:** Open any matter on a phone-width viewport.
- **Suggested fix:** Below a tablet breakpoint, collapse "Ask jaanch" into a bottom drawer / floating action button / dedicated tab, and give the main content the full width. This is the single highest-impact fix.

### FE-002 — Matter header action buttons clipped off-screen on mobile
- **Severity:** P1 Major
- **Category:** B. Responsive / C. Functional
- **Page:** `/matter/{id}/*` (matter header)
- **Viewports:** 390, 320
- **Description:** The "Export options" and "More actions" buttons in the matter header render at x≈453px and x≈493px — beyond the 390px viewport. A parent `overflow:hidden` clips them rather than producing scroll, so the buttons are simply unreachable on mobile. Export and bulk/matter actions are inaccessible to phone users.
- **Evidence:** `matter-busy-390.png`; DOM measurement: both buttons have `right` of 453/493 at a 390px viewport.
- **Repro:** Open a matter at 390px width; the header shows only the back link and matter title — the two action buttons are off-screen.
- **Suggested fix:** Make the matter header wrap or collapse its actions into a single overflow menu on small screens.

### FE-003 — Invalid / deleted matter URL renders a broken "Untitled Matter" shell
- **Severity:** P1 Major
- **Category:** C. Functional / D. Console
- **Page:** `/matter/{non-existent-id}` (e.g. a bookmarked matter that was later deleted)
- **Viewports:** all
- **Description:** Navigating to a matter ID that doesn't exist does **not** produce a "not found" page. Instead the full matter workspace shell renders with the title **"Untitled Matter"**, a fully interactive "Ask jaanch" panel, and an error banner that says *"Failed to load summary data. Please try refreshing the page."* — misleading advice, since refreshing will never help. Each matter feature (summary, documents, citations, entities, timeline, jobs, tab-stats, session, cross-engine) fetches independently and fails independently, producing **18 console errors** in one page load. The backend correctly returns `Matter not found or you don't have access`, but the frontend never uses that to render a proper state.
- **Evidence:** `matter-invalid-1440.png`; console log — 18 × `404` from `/api/matters/00000000-…/{summary,documents,citations,entities,timeline,tab-stats,…}`.
- **Repro:** Visit `https://www.jaanch-ai.in/matter/00000000-0000-0000-0000-000000000000`.
- **Suggested fix:** Gate the matter workspace on a single "does this matter exist / do I have access" check. On 404, render a branded "Matter not found" page with a link back to the dashboard, and skip the downstream feature fetches.

### FE-004 — Dashboard: horizontal page scroll + truncated stat labels at 320px
- **Severity:** P2 Moderate
- **Category:** B. Responsive
- **Page:** `/dashboard`
- **Viewports:** 320 (scroll), 390 + 320 (truncation)
- **Description:** Two related problems. (a) At 320px the page itself scrolls horizontally — `scrollWidth 314 > clientWidth 305`. The offender is the header right cluster (notifications bell + help + avatar, `div.flex items-center gap-1`) which extends to x≈314. (b) The Quick Stats cards ("Active Matters", "Verified", "Pending Reviews") are a fixed-width horizontal-scroll strip on mobile; their labels truncate to "Active Ma…", "Veri…", "Pending" and a third card sits off-screen.
- **Evidence:** `dashboard-320-top.png`, `dashboard-390.png`; DOM measurement confirms `hasHorizontalScroll: true` at 320.
- **Repro:** Open `/dashboard` at 320px; note the bottom horizontal scrollbar and the truncated stat labels.
- **Suggested fix:** Let the header cluster shrink/wrap within the viewport; make the stat cards wrap to a 1-col stack on narrow screens instead of a fixed-width scroll strip with truncated labels.

### FE-005 — Matter tabs row: "Documents" tab label cut off on mobile
- **Severity:** P2 Moderate
- **Category:** B. Responsive
- **Page:** `/matter/{id}/*` (tab bar)
- **Viewports:** 390, 320
- **Description:** The Summary / Timeline / Documents / More tab row does not adapt to narrow widths; the "Documents" tab is clipped to "Do…". (Compounded by FE-001 — the panel eats the width the tabs need.)
- **Evidence:** `matter-busy-390.png`
- **Suggested fix:** Make the tab bar horizontally scrollable as an explicit, styled scroller, or use icons-only with labels in an overflow menu on small screens.

### FE-006 — Verification table is ~1470px wide inside a squeezed mobile column
- **Severity:** P2 Moderate
- **Category:** B. Responsive
- **Page:** `/matter/{id}/verification`
- **Viewports:** 390, 320
- **Description:** The Verification Center contradictions table measures **1470px wide** inside an `overflow-x:auto` parent. On mobile that parent is itself squeezed to ~210px (because of FE-001), so the user must horizontally scroll a 1470px table inside a 210px window. The 22-item verification workflow — a core task — is near-impossible on a phone.
- **Evidence:** `verification-390.png`; DOM measurement: `tableWidth: 1470`, parent `overflow-x: auto`.
- **Suggested fix:** On small screens, render verification items as stacked cards instead of a wide table. (Also depends on FE-001 to reclaim width.)

### FE-007 — Dashboard matter status badge is wrong for a failed matter
- **Severity:** P2 Moderate
- **Category:** C. Functional / F. Content
- **Page:** `/dashboard` (matter cards) vs `/matter/{id}`
- **Description:** "TORTS Act 1992" shows a green **"Ready"** badge on the dashboard, with "0 pages" and "0 issues". Opening the matter reveals the truth: a red **"1 document failed processing"** alert and a summary stuck at *"Generating Summary — Waiting in queue… 0% complete"*. The dashboard's "Ready" status contradicts the matter's actual failed/stuck state.
- **Evidence:** `matter-empty-1440.png` vs the dashboard card.
- **Suggested fix:** Derive the matter card status from the real processing state — a matter with a failed document and no completed summary must not show "Ready".

### FE-008 — Search snippets polluted with repeated matter name
- **Severity:** P2 Moderate
- **Category:** C. Functional / F. Content
- **Page:** Global search (header searchbox)
- **Description:** Document-page search results show snippet text that begins with the matter name repeated 2–3 times before the real content, e.g. *"Shiju K vs Nalini Shiju K vs Nalini Shiju K vs Nalini IN THE HIGH COURT OF KERALA AT ERNAKULAM…"*. The snippet should show the matched document text, not a repeated title prefix.
- **Evidence:** `search-results-1440.png`; snapshot refs e613, e629, e645, e661.
- **Repro:** Type "Nalini" in the header search; inspect the result snippets.
- **Suggested fix:** Strip the matter/document title prefix from the indexed snippet text; show a clean excerpt around the matched term (ideally with the term highlighted).

### FE-009 — Search returns the same document page multiple times
- **Severity:** P2 Moderate
- **Category:** C. Functional
- **Page:** Global search
- **Description:** Search results list the same page more than once — e.g. "Document (Page 24)" of "8 & 9 juhinebhnani4" appears twice (different snippets, likely two chunks of one page), and "Document (Page 18)" repeats. There is no de-duplication or disambiguation, so results look noisy and redundant.
- **Evidence:** `search-results-1440.png`; snapshot refs e630 & e646 (both "Document (Page 24)").
- **Suggested fix:** De-duplicate results by document+page (collapse multiple chunk hits into one result), or clearly label which section/chunk each hit is.

### FE-010 — No custom 404 page
- **Severity:** P2 Moderate
- **Category:** A. Visual / C. Functional
- **Page:** Any unknown route, e.g. `/zzz-this-page-does-not-exist`
- **Description:** Unknown routes render the bare, unstyled **Next.js default 404** ("404 | This page could not be found.") — no jaanch.ai branding, no header, no navigation, no link back to the dashboard. It looks like the app crashed.
- **Evidence:** `404-1440.png`
- **Suggested fix:** Add an `app/not-found.tsx` with the app shell, branding, and a "Back to Dashboard" link.

### FE-011 — Stuck "Generating Summary / Waiting in queue" — a never-resolving loading state
- **Severity:** P2 Moderate
- **Category:** C. Functional
- **Page:** `/matter/7f890e33-…` (TORTS Act 1992)
- **Description:** This matter shows *"Generating Summary — Waiting in queue… 0% complete"* with a spinner. The matter was last touched 2026-04-30 — the job has been "waiting in queue" for ~20 days. From the user's side this is an infinite spinner with no failure messaging and no retry affordance. (Root cause is likely backend, but the frontend should not present a 20-day-old queued job as an active spinner.)
- **Evidence:** `matter-empty-1440.png`
- **Suggested fix:** Time-box the "in queue / generating" state; after a threshold show a failed state with a Retry action. Also see FE-007.

### FE-012 — `touch` endpoint throws a console warning on every matter open
- **Severity:** P3 Minor
- **Category:** D. Console
- **Page:** Every matter page
- **Description:** Each matter open logs: `touch failed: SyntaxError: Failed to execute 'json' on 'Response': Unexpected end of JSON input`. The `POST /api/matters/{id}/touch` call (records "last opened") returns an empty body, and the client unconditionally calls `.json()` on it. Harmless to the user but noisy, and it masks real warnings in the console.
- **Evidence:** Console warning observed on every `/matter/{id}` load this session.
- **Suggested fix:** Have `touch` return a JSON body (e.g. `{}`/`204` handled correctly), or guard the client: don't call `.json()` on an empty/204 response.

### FE-013 — Search result duplicates the matter name (title = subtitle)
- **Severity:** P3 Minor
- **Category:** F. Content
- **Page:** Global search
- **Description:** The matter result row for "Shiju K vs Nalini" shows the name twice — once as the title line and again as the subtitle (accessible name is literally "Shiju K vs Nalini Shiju K vs Nalini"). The subtitle should be context (e.g. document count / last activity), not a repeat of the title.
- **Evidence:** `search-results-1440.png`; snapshot refs e596 & e597.
- **Suggested fix:** For matter results, use the name once and put metadata in the subtitle.

### FE-014 — Generic "Document (Page N)" search labels — no filename
- **Severity:** P3 Minor
- **Category:** F. Content / UX
- **Page:** Global search
- **Description:** Document hits are titled "Document (Page 4)", "Document (Page 23)", etc. The actual document filename is buried inside the snippet as "[Source: 8. Affidavit in Sur Rejoinder…]". Users can't tell which document a hit belongs to from the result title.
- **Evidence:** `search-results-1440.png`
- **Suggested fix:** Title each hit with the document filename + page; show the matter as subtitle; show a clean snippet as the third line.

### FE-015 — Pluralization not handled ("1 documents", "1 citations")
- **Severity:** P3 Minor
- **Category:** F. Content
- **Pages:** Dashboard matter cards, matter Summary alert, Matter Statistics
- **Description:** Singular counts use plural nouns: "1 documents" (Shiju card on dashboard), "1 citations need verification" (matter Summary alert), "1 Citations Found" (Matter Statistics). Should read "1 document", "1 citation needs verification", "1 Citation Found".
- **Evidence:** dashboard snapshot; `matter-busy-1440.png` snapshot refs e263, e461–e462.
- **Suggested fix:** A shared pluralization helper for all count strings.

### FE-016 — Inconsistent date/time formatting across the app
- **Severity:** P3 Minor
- **Category:** F. Content
- **Pages:** Dashboard, Documents tab, matter pages, Activity
- **Description:** At least six date formats coexist: relative ("15m ago", "2m ago", "3 minutes ago"), `M/D/YYYY` ("5/6/2026", "4/30/2026"), `Mon D, YYYY` ("Apr 30, 2026"), long form ("22 January 2024"), and the literal string "Never opened". They appear side by side (the dashboard alone mixes "2m ago", "5/6/2026", "Never opened").
- **Evidence:** dashboard snapshot; `documents-1440.png`; `matter-busy-1440.png`.
- **Suggested fix:** Pick one convention (e.g. relative for <7 days, "Apr 30, 2026" beyond) and apply it through a shared date formatter.

### FE-017 — Inconsistent matter-card metric ("documents" vs "pages")
- **Severity:** P3 Minor
- **Category:** F. Content
- **Page:** `/dashboard`
- **Description:** Most matter cards show "N documents" (e.g. "3 documents"); the two TORTS matters show "0 pages". The dashboard mixes two different metrics for the same card field depending on matter state.
- **Evidence:** dashboard snapshot.
- **Suggested fix:** Use one consistent metric on the matter card (e.g. always document count).

### FE-018 — "Items need attention" count differs between views
- **Severity:** P3 Minor
- **Category:** F. Content
- **Page:** Matter Summary vs Verification Center
- **Description:** The matter Summary banner says **"23 items need attention"** (22 contradictions + 1 citation). The Verification Center for the same matter says **"22 total"**. Two views, similar-sounding metrics, different numbers — because they scope "items" differently (Verification covers contradictions only). This is confusing without a label clarifying scope.
- **Evidence:** `matter-busy-1440.png` (snapshot ref e255) vs `verification-1440.png` (snapshot ref e63).
- **Suggested fix:** Either unify the count or label each clearly ("23 items across contradictions + citations" vs "22 contradictions to verify").

### FE-019 — Internal/technical controls exposed in the end-user UI
- **Severity:** P3 Minor
- **Category:** A. Visual / UX
- **Pages:** Matter "Ask jaanch" panel, Documents tab, Verification Center
- **Description:** Engineer-facing details are surfaced to end users (lawyers): the "Ask jaanch" panel shows **"Embedding: OpenAI Small"** and **"Rerank: Cohere v3.5"** dropdowns; the Documents tab shows a **"1 worker"** indicator; the Verification Center shows a keyboard-shortcuts strip (`j/k`, `a`, `r`, `f`) even on touch/mobile. These add clutter and confusion for the target user.
- **Evidence:** `matter-busy-1440.png`, `documents-1440.png`, `verification-1440.png`.
- **Suggested fix:** Move embedding/rerank/worker controls behind an admin/advanced toggle; hide the shortcut strip on touch devices.

### FE-020 — `href="#"` on source / citation links
- **Severity:** P3 Minor
- **Category:** C. Functional / E. Accessibility
- **Page:** Matter Summary (source links, "pg. 1" links)
- **Description:** Many citation/source links render as `<a href="#">` (the "pg. 1" links and inline source references). Middle-click or "open in new tab" produces a dead tab; activating one risks a scroll-to-top jump. They behave as buttons but are marked up as anchors to nowhere.
- **Evidence:** `matter-busy-1440.png` snapshot — refs e288, e330–e332, e357 all have `/url: "#"`.
- **Suggested fix:** Use real `<button>` elements for JS-driven actions, or give the anchors real `href`s (deep links to the document page).

### FE-021 — Redundant filename shown twice in the document viewer toolbar
- **Severity:** P3 Minor
- **Category:** A. Visual
- **Page:** Document viewer
- **Viewports:** all (most noticeable on mobile)
- **Description:** The document viewer shows the filename in the top bar and again in the second toolbar row directly below it — the (long) filename is duplicated, consuming scarce toolbar space on mobile.
- **Evidence:** `docviewer-390.png`
- **Suggested fix:** Show the filename once; use the freed space for controls.

### FE-022 — Page content shifts/re-centers during load on desktop (intermittent)
- **Severity:** P2 Moderate
- **Category:** B. Responsive / C. Functional
- **Page:** `/dashboard` (measured); the pattern applies app-wide
- **Viewports:** desktop only (1440) — does **not** affect mobile (overlay scrollbars have no width)
- **Description:** Intermittently on desktop, the page renders at one width/position during load and then visibly jumps. Measured on a fresh `/dashboard` load: **CLS = 0.1138** (Google's "good" threshold is < 0.1) and **first-contentful-paint = 3.7 s** (blank screen for 3.7 s). Three compounding causes:
  1. **Scrollbar-driven re-centering.** `<main>` uses Tailwind's `container mx-auto` (fixed 1280 px, auto-centered). When content loads and the page grows tall enough to need a vertical scrollbar, the usable width drops ~16 px and `mx-auto` re-centers the 1280 px container — shifting **everything 8 px sideways** (measured: `main` x went 80 → 72 → 80). This is the largest single shift (0.0998).
  2. **Header reflow on hydration.** The header's right cluster (notification badge count, avatar + user name) renders only after its data loads. Until then the centered search box is wider; when the cluster appears, the search container snaps from **932 px → 804 px wide** and shifts ~128 px right.
  3. **Backend 503 + retry storms.** This load returned **HTTP 503** from `/api/dashboard/stats`, `/api/matters`, `/api/activity-feed`, `/api/admin/status`, and the client retried (stats 3×, activity-feed 2×). Each fail→retry→success cycle re-renders the page at a different height, toggling the scrollbar and re-triggering causes 1 & 2. A clean all-200 load is stable; a 503-retry load janks — **this is why it's intermittent.**
- **Evidence:** Two consecutive `/dashboard` loads measured via `PerformanceObserver('layout-shift')` — load A: CLS 0.1138, `main` x 80→72→80, header 932→804; load B: zero shift, `main` steady at x 80. Console: 7 × `503` on load A.
- **Repro:** Hard-reload `/dashboard` on desktop several times; on a slow/failing API load the content visibly jumps as it settles.
- **Suggested fix:**
  - Add `scrollbar-gutter: stable` to the scroll container (or `html`) — reserves scrollbar space permanently so width never changes (kills cause 1).
  - Reserve fixed width for the header right cluster (min-width / skeleton placeholder) so it doesn't reflow (cause 2).
  - Render skeletons that occupy the **final** dimensions, so a retry doesn't change page height (cause 3).
  - Separately: investigate the API 503s — `/api/dashboard/stats` and `/api/matters` returning 503 on a normal dashboard load is a backend availability problem worth its own ticket.

---

## 3. Architectural gaps — the root causes (read this section)

The 22 issues above are symptoms. Grouped by what *generates* them, they collapse into **four architectural gaps**. All four were verified by reading `frontend/src` (not inferred from the browser), and all four are the same disease the backend's ARCH-001/002/003 debts share — the one `CLAUDE.md` already names: **implicit coordination through convention instead of explicit coordination through structure.**

A recurring nuance: in three of the four, **the structure exists but was abandoned** — a central API client, error boundaries, a resizable-panel system, a shared relative-time util were all built, then not used consistently. The gap isn't "nobody built it"; it's "nothing makes using it mandatory." That is exactly how the backend ARCH debts accreted — one reasonable local change at a time.

### FE-ARCH-01 — The matter workspace has no convergence point: 7 panels each fetch, judge, and fail alone

**The shape.** Opening a matter renders the workspace shell *unconditionally*, then **~17–22 API calls fan out** from **7+ independent feature panels** (summary, timeline, documents, verification, citations, entities, contradictions). Nothing decides "does this matter exist / may this user see it" *once, before* the panels render. `middleware.ts` checks auth only; `matter/[matterId]/layout.tsx` renders the shell with no guard; each panel owns its own SWR hook, its own loading state, its own error UI.

When the matter doesn't exist, `matterStore.fetchMatter()` (lines ~261–300) **catches the 404 and fabricates a placeholder** — `{ title: 'Untitled Matter', … }` — so the shell renders happily while all 7 panels independently 404 (FE-003: 18 console errors). *The store invented fake data to cover for a missing structural state.* Relatedly, `processingStatus` is only ever `'processing'` or `'ready'` — there is **no `'failed'` state in the model**, so a matter whose document failed shows **"Ready"** (FE-007).

The structure to do this right already exists and is **unused**: `components/ui/api-error-boundary.tsx` (`ApiErrorBoundary`) is defined but not wrapped around the panels; there is no root `not-found.tsx`; `matter/[matterId]/error.tsx` *guesses* the error type by string-matching the message.

**Convention vs structure.** Every panel must *remember* to handle not-found / empty / unauthorized / stuck. There is no fan-in point that handles them once. This is the frontend twin of backend forbidden-pattern #3 — "remember to signal," no single convergence point. (Credit where due: the API *client* and SWR config **are** centralized — the gap is the uncoordinated *orchestration* of which calls fire and how their failures combine.)

**Symptoms it generates:** FE-003, FE-007, FE-011, and the per-panel patchwork loading.

**Structural fix.** One matter existence/authorization gate in the matter layout (or a server check + `not-found.tsx`) that resolves *once*; panels render only behind it. Add a real `'failed'` state to `processingStatus`. Delete the placeholder-fabrication path. Wire `ApiErrorBoundary` around the panel region.

### FE-ARCH-02 — Responsiveness is a per-component convention; there is no layout system

**The shape.** There is **no `useMediaQuery`, no breakpoint hook, no responsive layout component** anywhere in `frontend/src` (verified: zero matches). Responsiveness is ~70 files each hand-adding `sm:`/`md:`/`lg:` classes wherever the author remembered. The matter two-pane layout (`WorkspaceContentArea.tsx` + `qaPanelStore.ts`) is a Radix resizable panel with four positions — right / bottom / float / hidden — but **the position is hardcoded; nothing switches it by viewport.** The user must manually move the "Ask jaanch" panel, so on a phone it stays side-by-side (FE-001).

**Convention vs structure.** "Be responsive" is an instruction every component is trusted to follow individually. Nothing *owns* the question "what does the layout do below 768px?" — so the matter shell simply never got an answer, and no structure or test catches that it didn't.

**Symptoms it generates:** FE-001, FE-002, FE-005, FE-006 — the entire mobile-broken cluster.

**Structural fix.** A real layout layer: a `useBreakpoint` hook plus a workspace layout component that *structurally* collapses the Q&A panel to a drawer below the tablet breakpoint. Then "mobile" is one decision in one place, not 70.

### FE-ARCH-03 — Loading skeletons are a parallel, hand-synced copy of the real UI

**The shape.** Every feature skeleton (`DocumentCardSkeleton`, `EntityPanelSkeleton`, `CitationListSkeleton`, … in `ProcessingSkeleton.tsx`, plus inline ones like `DocumentsSkeleton`) is a **separate, hand-authored component** with **hardcoded dimensions** (`h-5`, `w-48`, …) that do not derive from the real component. Two implementations of the same UI, kept dimensionally in sync by hand.

**Convention vs structure.** This is backend forbidden-pattern #1 exactly — *parallel duplicate paths for the same logical work* — on the frontend. When a real component's height/padding changes, someone must *remember* to update its skeleton to match. They won't. Skeleton and final layout drift apart → content jumps when real data replaces the skeleton (this is a direct contributor to FE-022's layout shift).

**Symptoms it generates:** FE-022 (layout instability), patchwork loading.

**Structural fix.** A skeleton should be the *real* component rendered in a "skeleton" mode (same DOM, same dimensions, shimmer instead of content) — one source of truth, so the skeleton *cannot* drift from the final layout.

### FE-ARCH-04 — There is no presentation layer: dates, counts, and status are formatted ad hoc at every call site

**The shape.** `frontend/src/lib/utils.ts` contains exactly one helper (`cn()`). There is **no shared formatter.** Verified counts:
- **8 separate `formatDate()` implementations**, plus **55 ad-hoc `toLocaleDateString()` call sites** and **16 `date-fns` call sites** — at least **7 distinct date formats** live in production simultaneously (FE-016). *(Counts census-verified — see `FRONTEND-ARCH-DEBT.md`; the deep census corrected an earlier `~35` date-fns estimate to 16.)*
- **Zero `pluralize()` helper**; **87 ad-hoc count strings** built inline (83 hand-written `=== 1 ?` ternaries + 4 hardcoded plurals that render "1 documents" / "1 pages" — FE-015). *(Census-corrected from an earlier `237+` estimate.)*
- Aggregate facts ("items need attention") are computed independently per view → 23 on the Summary, 22 in the Verification Center (FE-018).
- (The one partial exception — `utils/formatRelativeTime.ts`, used in 79 places — proves the model works when a shared util exists.)

**Convention vs structure.** Backend forbidden-pattern #1 again — the same logical operation (format a date, pluralize a noun) reimplemented N times. There *should* be one `formatDate`, used structurally; instead each component invents its own and they drift.

**Symptoms it generates:** FE-013, FE-014, FE-015, FE-016, FE-017, FE-018.

**Structural fix.** A `frontend/src/lib/format/` layer — `formatDate` / `formatDateTime` / `formatRelative`, `pluralize` / `formatCount` — on one date library, plus a lint rule banning raw `toLocaleDateString` in components. Migrate the ~71 date call sites and 87 count strings onto it incrementally. Full census + detectors in `FRONTEND-ARCH-DEBT.md`.

### Meta-finding

All four gaps are one disease — **coordination by convention where structure is needed** — and it is the *same* disease as backend ARCH-001/002/003. The frontend was simply never put under the `architecture-guard` lens, so it accumulated the debt unobserved. Every new panel added its own fetch + error handling; every new component formatted its own dates; every skeleton was hand-copied. No single PR looked wrong — which is precisely the failure mode `CLAUDE.md` was written to stop.

**Recommendation:** extend the `architecture-guard` discipline (and a `forensic-hunt` pass) to `frontend/src`, not just the Celery pipeline. The frontend forbidden patterns are now named — FE-ARCH-01 through FE-ARCH-04 — and should be checked before new panels, new pages, or new formatters are added.

---

## 4. Per-page notes

| Page | Desktop | Mobile | Notes |
|------|---------|--------|-------|
| Dashboard | ✅ Clean, 0 console errors | ⚠️ FE-004 (h-scroll @320, truncated stats) | Activity Feed correctly collapses to an accordion on mobile |
| Matter — Summary | ✅ Rich, well-structured | ❌ FE-001, FE-002, FE-005 | Worst mobile offender |
| Matter — Documents | ✅ Clean table, data consistent (1+33+16=50 pages ✓) | ❌ FE-001 (panel) | 9-column table |
| Matter — Verification | ✅ Accurate counters, keyboard shortcuts | ❌ FE-001, FE-006 | Well-built on desktop |
| Matter — empty/failed (TORTS) | ⚠️ FE-007, FE-011 | ❌ FE-001 | Status mismatch + stuck spinner |
| Document viewer | ✅ Good | ✅ Fullscreen modal adapts well | FE-021 (minor) |
| Upload / New Matter | ✅ Clean | ✅ Clean, centered, no overflow | One of the healthiest pages |
| Activity | ✅ Clean, good date grouping | ✅ Clean | — |
| Notifications panel | ✅ Works | (not deep-tested) | — |
| Global search | ⚠️ FE-008, FE-009, FE-013, FE-014 | (not deep-tested) | Results quality is the issue |
| Profile menu / Help | ✅ Clean (Help is a tidy slide-over) | (not deep-tested) | — |
| 404 route | ❌ FE-010 (bare default) | ❌ Same | — |
| Invalid matter route | ❌ FE-003 (18 errors) | ❌ Same | — |

---

## 5. Responsive matrix

| Page | 1440 | 768 | 390 | 320 |
|------|:----:|:---:|:---:|:---:|
| Dashboard | ✅ | ✅ | ⚠️ | ❌ |
| Matter (Summary) | ✅ | ⚠️ | ❌ | ❌ |
| Matter (Verification) | ✅ | ⚠️ | ❌ | ❌ |
| Document viewer | ✅ | ✅ | ✅ | ✅ |
| Upload | ✅ | ✅ | ✅ | ✅ |
| Activity | ✅ | ✅ | ✅ | ✅ |

✅ good · ⚠️ usable with defects · ❌ broken / unusable

**Pattern:** Standalone pages (Dashboard, Upload, Activity, Document viewer) are responsive. **Everything inside the matter workspace shell is not** — because the "Ask jaanch" panel (FE-001) never yields width.

---

## 6. Console & network appendix

| Page | Errors | Warnings | Notes |
|------|:------:|:--------:|-------|
| Dashboard | 0–7 | 0 | Intermittent: a later pass returned 7 × `503` from `/api/dashboard/stats`, `/api/matters`, `/api/activity-feed`, `/api/admin/status` (with retries) — see FE-022 |
| Matter (any) | 0 | 1 | FE-012 — `touch failed: … Unexpected end of JSON input` |
| Verification | 0 | 1 | Same `touch` warning |
| Documents | 0 | 1 | Same `touch` warning |
| Activity | 0 | 0 | Clean |
| Upload | 0 | 0 | Clean |
| 404 route | 1 | 0 | Expected (404 resource) |
| **Invalid matter** | **18** | 1 | FE-003 — 13+ endpoints each 404 independently |

---

## 7. What's working well (for balance)

- **No console errors** on any of the main authenticated pages (dashboard, activity, upload, documents, verification).
- **Verification Center** — accurate progress counters ("0 of 22 verified"), keyboard shortcuts, sortable/filterable table. Strong on desktop.
- **Document viewer** — fullscreen modal with entity highlights; adapts cleanly to mobile with no overflow.
- **Upload, Activity** — clean and fully responsive at every viewport tested.
- **Help Center** — tidy categorized slide-over.
- Dashboard data is internally consistent (page counts add up; document counts match).

---

## 8. Coverage gaps — what this audit did NOT cover

A one-session, single-browser audit. Known blind spots, so nobody mistakes "not reported" for "not present":

**Pages / flows not exercised**
- **Logged-out landing page (`/`)** — `/` 307-redirects to `/dashboard` while authenticated; reaching the marketing page needs a logout with no way back in. Needs a separate incognito pass.
- **Auth flows** — login, signup, password reset (the `(auth)` route group) — not audited (would require logging out).
- **Upload end-to-end** — the static upload page was audited, but no file was submitted; the file-selected state, matter-creation form, upload progress bar, and post-upload processing UI were not exercised (avoided creating a throwaway matter).
- **Timeline / Citations / Entities / Contradictions matter sub-tabs** — not individually deep-audited; they share the matter shell, so FE-ARCH-01/02 and FE-001/002/005/006 apply to them too.
- **Settings / Usage / Admin pages** — not audited.
- **"Ask jaanch" panel actually answering a question** — never asked a real question; the resize / reposition modes (right / bottom / float) were not exercised.
- **Export, document-compare, bulk-select, notifications mark-read, search pagination, dashboard list-view + sort/filter** — controls were seen but not driven end to end.

**Environments / conditions not tested**
- **Only Chromium** — no Firefox, no Safari/WebKit. **Important:** iOS Safari uses *overlay* scrollbars, which changes FE-022's scrollbar re-centering behaviour — that finding must be re-verified on real Safari.
- **No real-device testing** — viewport emulation only; real touch, on-screen keyboards, notches / safe-areas, and device DPI untested.
- **No network-condition testing** — no slow-3G / offline / throttled runs (would surface more loading-state and retry behaviour).
- **Dark mode / theming** — the root layout hard-applies a `light` class; if a dark theme exists it was not audited.
- **Single account, single dataset** — one user's 4 matters. Multi-user, large matters (hundreds of documents), and a brand-new empty account were not seen.

**Depth not reached**
- **Accessibility** — only spot-checked (accessible names exist; heading order looks sane on the matter page). No contrast-ratio measurement, no full keyboard-only traversal, no screen-reader pass, no automated axe / Lighthouse run.
- **Performance** — FCP was measured incidentally (3.7 s, see FE-022); no full Lighthouse / Web Vitals / bundle-size analysis.

---

## 9. Recommended priority order

> The FE-### fixes below are symptom-level. The durable fix is to **close the four architectural gaps in §3** — ideally each symptom fix is done *as a step toward* its parent gap (e.g. fix FE-001 by building the layout primitive from FE-ARCH-02, not by bolting one more breakpoint onto the shell).

1. **FE-001** *(→ FE-ARCH-02)* — Collapse "Ask jaanch" into a drawer on small screens. Unlocks the entire mobile experience and partly resolves FE-002, FE-005, FE-006.
2. **FE-003 + FE-010** *(→ FE-ARCH-01)* — Add a proper "Matter not found" state and a custom 404. Both are small, high-visibility fixes.
3. **FE-002, FE-004** *(→ FE-ARCH-02)* — Header overflow fixes (matter header buttons; dashboard 320 scroll + stat cards).
4. **FE-007, FE-011** *(→ FE-ARCH-01)* — Make matter status reflect real processing state (add a `'failed'` state); time-box stuck "generating" spinners.
5. **FE-008, FE-009** — Clean up search snippets and de-duplicate results.
6. **FE-012 → FE-021** *(→ FE-ARCH-04)* — Content/polish batch (pluralization, date formats, `href="#"`, console warning, exposed internal controls) — do it by building the `lib/format/` layer, not by patching call sites.
7. **FE-022** *(→ FE-ARCH-03)* — `scrollbar-gutter: stable` + make skeletons the real component in skeleton mode.
