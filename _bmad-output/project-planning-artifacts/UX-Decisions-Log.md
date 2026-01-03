# LDIP UX Decisions Log

**Document Status:** ACTIVE - Living Document
**Created:** 2026-01-03
**Last Updated:** 2026-01-03
**Owner:** Juhi (Product Owner) + Sally (UX Designer)

---

## Document Purpose

This document captures all UX decisions made during the design phase of LDIP. Each decision includes the rationale and any alternatives considered.

---

## Table of Contents

1. [Global Decisions](#1-global-decisions)
2. [Page Structure](#2-page-structure)
3. [Dashboard / Home](#3-dashboard--home)
4. [Upload & Processing](#4-upload--processing)
5. [Matter Workspace - General](#5-matter-workspace---general)
6. [Matter Workspace - Summary Tab](#6-matter-workspace---summary-tab)
7. [Matter Workspace - Timeline Tab](#7-matter-workspace---timeline-tab)
8. [Cross-Referencing](#8-cross-referencing)
9. [Matter Workspace - Entities Tab](#9-matter-workspace---entities-tab)
10. [Matter Workspace - Citations Tab](#10-matter-workspace---citations-tab)
11. [Contradictions in Verification Tab (MVP)](#11-contradictions-in-verification-tab-mvp)
12. [Matter Workspace - Verification Tab](#12-matter-workspace---verification-tab)
13. [Matter Workspace - Documents Tab](#13-matter-workspace---documents-tab)
14. [Q&A Panel](#14-qa-panel)
15. [PDF Viewer](#15-pdf-viewer)
16. [Export Builder](#16-export-builder)
17. [UX Design Complete](#17-ux-design-complete)
18. [Micro-Interactions](#18-micro-interactions)
19. [Error States](#19-error-states)
20. [Edge Cases](#20-edge-cases)

---

## 1. Global Decisions

### 1.1 Multi-Matter Support

| Decision | Lawyers can work on multiple matters simultaneously |
|----------|-----------------------------------------------------|
| Rationale | Legal cases run long; lawyers juggle multiple active matters at once |
| Impact | Dashboard shows matter cards, not single-matter focus |

### 1.2 Landing Page Priority

| Decision | Dashboard shows BOTH "Start New" AND "Continue Where Left Off" |
|----------|---------------------------------------------------------------|
| Rationale | Cases run long; users need quick access to existing work AND ability to start new |
| Impact | Prominent "+ New Matter" CTA + Recent Matters grid |

### 1.3 Q&A Panel Position

| Decision | User-controlled: resizable, repositionable |
|----------|-------------------------------------------|
| Rationale | Different users have different preferences; power users want flexibility |
| Options | Right sidebar (default), Bottom panel, Floating window, Hidden |
| Impact | Panel has drag handle, position selector, width/height controls |

### 1.4 PDF Viewer Mode

| Decision | Split view by default, expandable to full modal |
|----------|------------------------------------------------|
| Rationale | Users need to see context (workspace) while viewing source; option to focus when needed |
| Impact | PDF opens in split view; [⛶] button expands to modal overlay |

### 1.5 Verification Visibility

| Decision | Dedicated Verification tab + inline verify buttons on all findings |
|----------|------------------------------------------------------------------|
| Rationale | Verification is critical for lawyer trust; needs prominent visibility |
| Impact | Separate "Verification" tab in Matter Workspace; [✓ Verify] on each finding |

### 1.6 Export Format

| Decision | Formal PDF export with customizable sections |
|----------|---------------------------------------------|
| Rationale | Lawyers need court-ready documents; must control what's included |
| Features | Section selection, reordering, inline editing, preview before export |
| Formats | PDF (primary), Word, PowerPoint |

---

## 2. Page Structure

### 2.1 Complete Page Map

```
Dashboard (Home)
    │
    ├── Upload & Processing (New Matter)
    │       │
    │       └── [Processing Complete] ──► Matter Workspace
    │
    └── Matter Workspace (Existing Matter)
            │
            ├── Summary Tab
            ├── Timeline Tab
            ├── Entities Tab
            ├── Citations Tab
            ├── Verification Tab (includes contradiction findings)
            └── Documents Tab
            │
            ├── Q&A Panel (always available, user-positioned)
            ├── PDF Viewer (split/modal)
            └── Export Builder (modal)
```

> **Note (Decision 10):** Dedicated Contradictions Tab deferred to Phase 2. Entity-based contradictions appear as finding type in Verification Tab.

### 2.2 Tab Order

| Decision | Summary → Timeline → Entities → Citations → Verification → Documents |
|----------|---------------------------------------------------------------------|
| Rationale | Follows natural user workflow: understand case → see chronology → identify players → check citations → verify findings → access raw docs |
| Note | Contradictions appear in Verification Tab as finding type (Phase 2: dedicated tab) |

---

## 3. Dashboard / Home

### 3.1 Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  HEADER                                                                         │
│  ┌──────┐                                      ┌────┐ ┌────┐ ┌───────────┐      │
│  │ LDIP │   [🔍 Search all matters...]         │ 🔔 │ │ ❓ │ │ JJ ▼     │      │
│  │      │                                      │ 3  │ │    │ │ Juhi     │      │
│  └──────┘                                      └────┘ └────┘ └───────────┘      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  HERO SECTION                                                                   │
│                                                                                 │
│  Good morning, Juhi                                ┌────────────────────┐       │
│                                                    │  [+ NEW MATTER]    │       │
│  You have 3 findings awaiting verification        │   Upload case      │       │
│  and 1 matter still processing.                    │   documents        │       │
│                                                    └────────────────────┘       │
│  [View Pending Items →]                                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────┐  ┌────────────────────────────┐  │
│  │  YOUR MATTERS                            │  │  ACTIVITY FEED             │  │
│  │                                          │  │                            │  │
│  │  [Grid ▣] [List ☰]  [Sort: Recent ▼]    │  │  Today                     │  │
│  │                                          │  │  ─────                     │  │
│  │  ┌────────────┐ ┌────────────┐          │  │  • 8:02 AM                 │  │
│  │  │ ████████░░ │ │ ✓ Ready    │          │  │    Shah v. Mehta           │  │
│  │  │ SEBI v.    │ │ Shah v.    │          │  │    Processing complete ✓   │  │
│  │  │ Parekh     │ │ Mehta      │          │  │                            │  │
│  │  │ Processing │ │ 1,247 pgs  │          │  │  Yesterday                 │  │
│  │  │ 67%        │ │ 85% ✓      │          │  │  ─────────                 │  │
│  │  │ [View →]   │ │ [Resume →] │          │  │  • 6:15 PM                 │  │
│  │  └────────────┘ └────────────┘          │  │    3 contradictions found  │  │
│  │                                          │  │                            │  │
│  │  ┌────────────┐ ┌────────────┐          │  └────────────────────────────┘  │
│  │  │ ✓ Ready    │ │    ┌──┐    │          │                                  │
│  │  │ Custody    │ │    │+ │    │          │  ┌────────────────────────────┐  │
│  │  │ Dispute    │ │    └──┘    │          │  │  QUICK STATS               │  │
│  │  │ 892 pgs    │ │  Add New   │          │  │  📁 5 Active Matters       │  │
│  │  │ [Resume →] │ │  Matter    │          │  │  ✓ 127 Verified Findings   │  │
│  │  └────────────┘ └────────────┘          │  │  ⏳ 3 Pending Reviews       │  │
│  │                                          │  └────────────────────────────┘  │
│  └──────────────────────────────────────────┘                                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Layout Structure

| Component | Position | Purpose |
|-----------|----------|---------|
| Header | Top | Logo, global search, notifications, profile |
| Hero Section | Below header | Greeting, status summary, "+ New Matter" CTA |
| Matter Cards | Left/Center (70%) | Grid of all matters with status |
| Activity Feed | Right (30%) | Recent actions, processing updates |
| Quick Stats | Right bottom | Aggregate stats across matters |

### 3.3 Matter Card States

```
PROCESSING STATE                    READY STATE
┌────────────────────┐              ┌────────────────────┐
│  ████████░░░ 67%   │              │  ✓ Ready           │
│                    │              │                    │
│  SEBI v. Parekh    │              │  Shah v. Mehta     │
│                    │              │                    │
│  Processing...     │              │  1,247 pages       │
│  Est. 3 min left   │              │  Last opened: 2h ago│
│                    │              │                    │
│  89 documents      │              │  ┌────┐ ┌────┐     │
│  2,100 pages       │              │  │85% │ │ 3  │     │
│                    │              │  │ ✓  │ │ ⚠️ │     │
│  [View Progress →] │              │  └────┘ └────┘     │
│                    │              │  Verified  Issues  │
└────────────────────┘              │                    │
                                    │  [Resume →]        │
                                    └────────────────────┘
```

### 3.4 Matter Card Information

| Field | Description |
|-------|-------------|
| Status indicator | Processing bar OR "✓ Ready" badge |
| Matter name | Case title (user-editable) |
| Page count | Total pages across all documents |
| Last activity | "Last opened: 2h ago" or "Processing..." |
| Verification % | Percentage of findings verified |
| Issue count | Flagged items needing attention |
| Action button | "View Progress" (processing) or "Resume" (ready) |

### 3.3 View Options

| Decision | Grid view (default) + List view toggle |
|----------|---------------------------------------|
| Sort options | Recent, Alphabetical, Most pages, Least verified, Date created |
| Filter options | All, Processing, Ready, Needs attention, Archived |

### 3.4 Activity Feed Types

| Icon | Type | Example |
|------|------|---------|
| 🟢 | Success | Processing complete, verification done |
| 🔵 | Info | Login, opened matter |
| 🟡 | In progress | Upload started, processing |
| ⚠️ | Attention needed | Contradictions found, low confidence |
| 🔴 | Error | Processing failed, upload error |

---

## 4. Upload & Processing

### 4.1 Stage 1: File Selection Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                         CREATE NEW MATTER                                       │
│                                                                                 │
│         ┌─────────────────────────────────────────────────────────┐            │
│         │                                                         │            │
│         │                  ┌───────────────┐                      │            │
│         │                  │   📁 → 📄     │                      │            │
│         │                  └───────────────┘                      │            │
│         │                                                         │            │
│         │            Drag & drop your case files here             │            │
│         │                        or                               │            │
│         │                 [Browse Files]                          │            │
│         │                                                         │            │
│         │     Supported: PDF, ZIP (containing PDFs)               │            │
│         │     Maximum: 500MB per file • 100 files per matter      │            │
│         │                                                         │            │
│         └─────────────────────────────────────────────────────────┘            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Stage 4: Processing & Live Discovery Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                    SEBI v. Parekh Securities Matter       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  PROCESSING YOUR CASE                                                     │ │
│  │  ████████████████████████████░░░░░░░░░░░░░░  67%                         │ │
│  │  Stage 3 of 5: Extracting entities & relationships                        │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │  📄 DOCUMENTS                       │  │  🔍 LIVE DISCOVERIES             │ │
│  │                                     │  │                                  │ │
│  │  ✓ 89 files received                │  │  👤 ENTITIES FOUND (34)          │ │
│  │  ✓ 2,100 pages extracted            │  │  • Mehul Parekh (Petitioner)     │ │
│  │                                     │  │  • Nirav D. Jobalia              │ │
│  │  OCR Progress:                      │  │  • Jitendra Kumar (Custodian)    │ │
│  │  ████████████████░░░░ 78%           │  │  • +8 more...                    │ │
│  │                                     │  │                                  │ │
│  │  ✓ Petition.pdf (234 pg)           │  │  📅 DATES EXTRACTED (47)         │ │
│  │  ✓ Reply_Affidavit.pdf (156 pg)    │  │  Earliest: May 12, 2016          │ │
│  │  ⏳ Annexure_K.pdf...              │  │  Latest: Jan 15, 2024            │ │
│  │  ○ ... 84 more                     │  │                                  │ │
│  │                                     │  │  ⚖️ CITATIONS DETECTED (23)      │ │
│  └─────────────────────────────────────┘  │  • Securities Act 1992 (18)      │ │
│                                           │  • SARFAESI Act 2002 (4)         │ │
│  ┌─────────────────────────────────────┐  │                                  │ │
│  │  📅 TIMELINE PREVIEW                │  └──────────────────────────────────┘ │
│  │  2016 ──●───────2018──●●●──2024──●  │                                      │
│  └─────────────────────────────────────┘                                      │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  💡 EARLY INSIGHTS                                                        │ │
│  │  🔍 "This case spans 7+ years with 4 major procedural stages"            │ │
│  │  ⚠️ "Found potential date discrepancy in notice timeline"                │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│                              [Continue in Background]                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Upload Flow Stages

```
Stage 1: File Selection (drag/drop or browse)
    │
    ▼
Stage 2: Review & Name (edit matter name, see file list, warnings)
    │
    ▼
Stage 2.5: Act Discovery Modal (NEW - per ADR-005)
    │
    ▼
Stage 3: Upload Progress (file-by-file progress)
    │
    ▼
Stage 4: Processing & Live Discovery (the main event)
    │
    ▼
Stage 5: Processing Complete (auto-redirect to workspace)
```

### 4.3.1 Act Discovery Modal Wireframe (Stage 2.5 - per ADR-005)

> **ADR-005 Compliance:** User uploads Acts per matter. No system-maintained Acts database.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                          ACT REFERENCES DETECTED                                │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  Your case files reference 6 Acts. We found 2 in your uploaded files.    │ │
│  │                                                                           │ │
│  │  For accurate citation verification, please upload the missing Acts.     │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ✅ DETECTED IN YOUR FILES (2)                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ✓ Securities Act, 1992         Found in: Annexure_P3.pdf               │ │
│  │  ✓ SARFAESI Act, 2002            Found in: Annexure_K.pdf                │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ⚠️ MISSING ACTS (4)                              [Upload Missing Acts]       │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ○ BNS Act, 2023                  Cited 12 times in your files          │ │
│  │  ○ Negotiable Instruments Act     Cited 8 times                          │ │
│  │  ○ DRT Act, 1993                  Cited 4 times                          │ │
│  │  ○ Companies Act, 2013            Cited 2 times                          │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ℹ️ Citations to missing Acts will show as "Unverified - Act not provided"    │
│     You can upload Acts later from the Documents Tab.                          │
│                                                                                 │
│                         [Skip for Now]     [Continue with Upload]              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Act Upload Behavior:**
| Action | Result |
|--------|--------|
| Upload Act now | File marked as `is_reference_material=true`, stored in matter's acts folder |
| Skip for Now | Continue processing; citations show "Unverified - Act not provided" |
| Upload later (Documents Tab) | User can "Set as Act" action on any document |

### 4.4 Add Documents to Existing Matter Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [Entities] [Citations] [Verification] [■ Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  DOCUMENTS                                                  ┌────────────────┐  │
│  89 documents • 2,100 pages • Last updated: 2 hours ago    │ + ADD FILES    │  │
│                                                             └────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  📄 NAME                    │ PAGES │ ADDED        │ STATUS    │       │  │
│  │  ─────────────────────────────────────────────────────────────────────  │  │
│  │  📄 Petition.pdf            │ 234   │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │  │
│  │  📄 Reply_Affidavit.pdf     │ 156   │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │  │
│  │  ─────────────────────────────────────────────────────────────────────  │  │
│  │  📄 New_Annexure_P12.pdf    │ 45    │ Just now     │ ⏳ Processing│[⋮] │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⏳ PROCESSING NEW DOCUMENTS (2 files)                                  │   │
│  │  ████████████░░░░░░░░░░░░░░░░░░░░  34%                                 │   │
│  │  You can continue working while this processes.                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Live Discovery During Processing

| Decision | Show live updates during processing to keep users engaged |
|----------|----------------------------------------------------------|
| Rationale | 2-5 minute wait feels shorter when seeing progress; builds anticipation |
| Updates shown | Documents processed, entities found, dates extracted, citations detected, early insights |

### 4.3 Processing Stages

| Stage | Description |
|-------|-------------|
| Stage 1 | Upload - File upload, validation, unzip if needed |
| Stage 2 | OCR & Extract - Page-by-page text + bounding boxes |
| Stage 3 | Entity Resolution - Entity extraction, alias resolution, relationships |
| Stage 4 | Analysis Engines - Timeline, Citations, Contradictions |
| Stage 5 | Final Index - Final indexing, cache warming, ready notification |

### 4.4 Background Processing

| Decision | Users can click "Continue in Background" and return to Dashboard |
|----------|----------------------------------------------------------------|
| Notification | Browser notification when processing complete |
| Dashboard | Matter card shows processing progress |

### 4.5 Adding Documents to Existing Matter

| Location | Method |
|----------|--------|
| Documents Tab | Click "+ ADD FILES" button |
| Dashboard | Matter card menu → "Add documents" |
| Anywhere in Workspace | Drag & drop files onto page |

| Behavior | Incremental processing - new docs merge into existing analysis |
|----------|--------------------------------------------------------------|
| User can continue working while new documents process |

---

## 5. Matter Workspace - General

### 5.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  Header: Back to Dashboard | Matter Name | Export | Share | ⚙️  │
├─────────────────────────────────────────────────────────────────┤
│  Tab Bar: [Summary] [Timeline] [Entities] ... [Documents]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────┬─────────────────────────────┐ │
│  │                             │                             │ │
│  │    MAIN CONTENT AREA        │    Q&A PANEL               │ │
│  │    (Changes by tab)         │    (User-positioned)       │ │
│  │                             │                             │ │
│  └─────────────────────────────┴─────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Q&A Panel Options

| Position | Behavior |
|----------|----------|
| Right sidebar (default) | Vertical panel, resizable width (20-60%) |
| Bottom panel | Horizontal panel, resizable height |
| Floating | Draggable anywhere, resizable, can overlap |
| Hidden | Collapsed, small [💬] button to expand |

### 5.3 PDF Viewer Behavior

| Mode | Trigger | Behavior |
|------|---------|----------|
| Split View (default) | Click any citation | Opens PDF in right panel, workspace stays visible |
| Full Modal | Click [⛶] expand button | PDF takes full screen as overlay |

---

## 6. Matter Workspace - Summary Tab

### 6.1 Summary Tab Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ← Dashboard    Shah v. Mehta Securities Matter    [Export ▼] [Share] [⚙️]      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ TABS: [■ Summary] [Timeline] [Entities] [Citations] [Verification] [Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────┬────────────────────────┐ │
│  │                                                   │  💬 ASK LDIP    [─][□] │ │
│  │  EXECUTIVE SUMMARY                      [✎ Edit] │                        │ │
│  │  Generated: 2 hours ago    [🔄 Regenerate]       │  Start a conversation  │ │
│  │                                                   │  about this matter...  │ │
│  │  ┌─────────────────────────────────────────────┐ │                        │ │
│  │  │  ⚠️ 3 ITEMS NEED ATTENTION                  │ │  ┌──────────────────┐  │ │
│  │  │  • 3 contradictions detected                │ │  │ What is this     │  │ │
│  │  │  • 2 citations need verification            │ │  │ case about?      │  │ │
│  │  │  • 1 timeline gap identified                │ │  └──────────────────┘  │ │
│  │  │  [Review All →]                             │ │                        │ │
│  │  └─────────────────────────────────────────────┘ │  [Type question...]    │ │
│  │                                                   │                        │ │
│  │  PARTIES                                          │                        │ │
│  │  ┌───────────────────────┬───────────────────┐   │                        │ │
│  │  │  👤 PETITIONER        │  ⚔️ RESPONDENT    │   │                        │ │
│  │  │  Nirav D. Jobalia     │  The Custodian    │   │                        │ │
│  │  │  📎 Petition, pg 1    │  📎 Petition, pg 2│   │                        │ │
│  │  │  [View Entity] [✓]   │  [View Entity][✓] │   │                        │ │
│  │  └───────────────────────┴───────────────────┘   │                        │ │
│  │                                                   │                        │ │
│  │  SUBJECT MATTER                                   │                        │ │
│  │  ┌─────────────────────────────────────────────┐ │                        │ │
│  │  │  Property attachment and dematerialisation  │ │                        │ │
│  │  │  dispute under Securities Act, 1992...      │ │                        │ │
│  │  │  📎 Sources: Petition pg 1-5, Order pg 1-3  │ │                        │ │
│  │  │  [View Sources]                      [✓]   │ │                        │ │
│  │  └─────────────────────────────────────────────┘ │                        │ │
│  │                                                   │                        │ │
│  │  CURRENT STATUS                                   │                        │ │
│  │  ┌─────────────────────────────────────────────┐ │                        │ │
│  │  │  📅 LAST ORDER: January 15, 2024            │ │                        │ │
│  │  │  Custodian directed to file compliance      │ │                        │ │
│  │  │  📎 Order_Jan_2024.pdf, pg 8-9              │ │                        │ │
│  │  │  [View Full Order]                   [✓]   │ │                        │ │
│  │  └─────────────────────────────────────────────┘ │                        │ │
│  │                                                   │                        │ │
│  │  KEY ISSUES                                       │                        │ │
│  │  1️⃣ Attachment validity          [✓ Verified]   │                        │ │
│  │  2️⃣ Dematerialisation delay      [⏳ Pending]    │                        │ │
│  │  3️⃣ Documentation gaps           [⚠️ Flagged]   │                        │ │
│  │  4️⃣ Contradictory statements     [⚠️ Flagged]   │                        │ │
│  │                                                   │                        │ │
│  │  MATTER STATISTICS                                │                        │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │                        │ │
│  │  │  📄    │ │  👤    │ │  📅    │ │  ⚖️    │    │                        │ │
│  │  │ 1,247  │ │  34    │ │  47    │ │  23    │    │                        │ │
│  │  │ Pages  │ │Entities│ │ Events │ │Citations│   │                        │ │
│  │  └────────┘ └────────┘ └────────┘ └────────┘    │                        │ │
│  │                                                   │                        │ │
│  │  VERIFICATION: ████████████████░░░░░░ 67%        │                        │ │
│  │                                                   │                        │ │
│  └───────────────────────────────────────────────────┴────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Summary Sections (in order)

1. **Attention Banner** - Issues needing action (contradictions, citation issues, gaps)
2. **Parties** - Petitioner, Respondent, Other key parties with entity links
3. **Subject Matter** - What the case is about
4. **Current Status** - Last order, next steps
5. **Case Timeline at a Glance** - Mini timeline preview
6. **Key Issues** - Numbered list with status (verified/pending/flagged)
7. **Key Findings** - Contradictions, citation issues, cross-reference issues
8. **Matter Statistics** - Pages, entities, events, citations counts
9. **Verification Status** - Progress bar + counts

### 6.2 Inline Verification

| Decision | Every section has [✓ Verify] [✗ Flag] [💬 Note] buttons |
|----------|--------------------------------------------------------|
| States | Not verified, Verified (with timestamp), Flagged (with reason), Has notes |

### 6.3 Editable Sections

| Decision | AI-generated summary is editable by user |
|----------|----------------------------------------|
| Behavior | Click [✎ Edit] → inline rich text editor |
| Preservation | Original AI version preserved; user edits saved separately |
| Regenerate | [🔄 Regenerate] creates fresh AI analysis |

### 6.4 Citation Links

| Decision | Every factual claim has clickable citations |
|----------|-------------------------------------------|
| Hover | Shows preview tooltip with excerpt |
| Click | Opens PDF viewer at exact location with highlight |

---

## 7. Matter Workspace - Timeline Tab

### 7.1 Timeline Tab - Vertical List View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [■ Timeline] [Entities] [Citations] [Verification] [Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  TIMELINE • 47 events • May 2016 - Jan 2024                                    │
│                                                                                 │
│  VIEW: [● List] [◐ Horizontal] [☰ Table]     FILTER: [All Types ▼]            │
│  ☐ Show gaps  ☐ Show contradictions                                            │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⚠️ 1 TIMELINE GAP DETECTED: 8 months (Feb 2019 - Oct 2019)            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  2016                                                                          │
│  ════                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  📅 May 12, 2016                                                        │   │
│  │  📋 CASE FILED                                                          │   │
│  │  Petition filed before Special Court                                    │   │
│  │  👤 Actor: Nirav D. Jobalia (Petitioner)                               │   │
│  │  📄 Source: Petition.pdf, pg 1                                         │   │
│  │  [View Source]  [✓ Verified]                                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│          │                                                                     │
│          │ ← 2 years, 1 month                                                 │
│          │                                                                     │
│  2018                                                                          │
│  ════                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  📅 June 5, 2018                                                        │   │
│  │  📧 NOTICE SENT                                                         │   │
│  │  Notice sent to Custodian regarding dematerialisation                   │   │
│  │  👤 Actor: Nirav D. Jobalia                                            │   │
│  │  📄 Source: Petition.pdf, pg 45                                        │   │
│  │  ⚠️ CONTRADICTION: Date conflicts with Reply Affidavit (June 8)        │   │
│  │  🔗 Cross-ref: Annexure P-12 (postal receipt)                          │   │
│  │  [View Source]  [⏳ Pending]                                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│          │                                                                     │
│          │ ← 5 days                                                           │
│          │                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  📅 June 10, 2018                                            🔴 KEY    │   │
│  │  ⚖️ PROPERTY ATTACHMENT ORDER                                          │   │
│  │  Special Court orders attachment under Section 3(3)                    │   │
│  │  👤 Actor: Special Court Mumbai                                        │   │
│  │  📄 Source: Court_Order_June.pdf, pg 1                                 │   │
│  │  ⚖️ Citation: Section 3(3) [View Act]                                  │   │
│  │  [View Source]  [✓ Verified]                                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│          │                                                                     │
│          │ ← 254 days (SIGNIFICANT DELAY - exceeds 90-day statutory limit)   │
│                                                                                 │
│  [... CONTINUES ...]                                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Timeline Tab - Horizontal View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  TIMELINE                                                                       │
│  VIEW: [○ List] [● Horizontal] [○ Table]     ZOOM: [−] ════●════ [+]           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  2016      2017      2018           2019      2020      2021-23   2024         │
│   │         │         │              │         │          │        │           │
│   │         │    ┌────┴────┐         │         │          │        │           │
│   │         │    │ CLUSTER │         │         │          │        │           │
│   │         │    └────┬────┘         │         │          │        │           │
│   ●─────────┼─────────●●●●───────────●─────────●──────────┼────────●           │
│   │         │         ││││           │         │          │        │           │
│ Case       │      Attach│││        Review    Appeal      (quiet)  Latest      │
│ Filed      │      Order│││        Filed     Rejected            Order         │
│            │           │││                                                     │
│            │      Notice││                                                     │
│            │       Sent │└─ Demat Complete                                     │
│            │            └── Response Filed                                     │
│                                                                                │
│  ════════════════════════════════════════════════════════════════════════════  │
│                             ▲ ⚠️ 8-MONTH GAP                                   │
│                                                                                │
│  SELECTED: June 10, 2018 - Property Attachment Order                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │  ⚖️ Special Court orders attachment under Section 3(3)                  │  │
│  │  👤 Actor: Special Court Mumbai  📄 Court_Order_June.pdf, pg 1          │  │
│  │  [View Source]  [View in List]  [✓ Verified]                            │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Timeline Tab - Multi-Track View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  VIEW: [○ Single Track] [● Multi-Track]                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  2018                   2019                   2020                   2024     │
│   │                      │                      │                      │       │
│   │    PETITIONER        │                      │                      │       │
│   ├──●────●──────────────┼──●───────────────────┼──────────────────────┤       │
│   │  │    │              │  │                   │                      │       │
│   │Notice Petition       │ Review              │                      │       │
│   │ Sent  Filed          │ Filed               │                      │       │
│   │                      │                      │                      │       │
│   │    COURT             │                      │                      │       │
│   ├─────●────────────────┼──────────────────────┼──●───────────────────●       │
│   │     │                │                      │  │                   │       │
│   │  Attach              │                    Appeal              Latest      │
│   │  Order               │                   Rejected              Order      │
│   │                      │                      │                      │       │
│   │    CUSTODIAN         │                      │                      │       │
│   ├───────●──────────────┼──●───────────────────┼──────────────────────┤       │
│   │       │              │  │                   │                      │       │
│   │    Response        Demat                   │                      │       │
│   │     Filed         Complete                 │                      │       │
│                                                                                 │
│  Legend: ● Event    ──── Actor timeline                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Gap Detection Display Wireframe (PHASE 2)

> **DEFERRED to Phase 2:** Timeline gap detection requires Process Chain Engine which needs user-created templates. MVP timeline shows chronological events only. See [Phase-2-Backlog.md](Phase-2-Backlog.md).

<details>
<summary>Click to expand Phase 2 Gap Detection Design</summary>

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  📅 February 20, 2019 - Dematerialisation Complete                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│          │                                                                     │
│  ┌───────┴───────────────────────────────────────────────────────────────────┐ │
│  │  ⚠️ TIMELINE GAP DETECTED                                                │ │
│  │  Duration: 8 months (Feb 20, 2019 → Oct 5, 2019)                         │ │
│  │  No events recorded during this period.                                  │ │
│  │                                                                           │ │
│  │  Possible explanations:                                                  │ │
│  │  • Documents for this period not uploaded                               │ │
│  │  • Statutory waiting period                                              │ │
│  │  • Case was dormant                                                      │ │
│  │                                                                           │ │
│  │  [Mark as Expected Gap]  [Add Missing Documents]  [Investigate]          │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│          │                                                                     │
│  ┌───────┴─────────────────────────────────────────────────────────────────┐   │
│  │  📅 October 5, 2019 - Review Petition Filed                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

</details>

### 7.5 View Modes

| View | Best For |
|------|----------|
| Vertical List (default) | Detailed reading, chronological scroll |
| Horizontal Timeline | Visual overview, pattern spotting |
| Table View | Data export, sorting, filtering |

### 7.2 Event Card Information

| Field | Description |
|-------|-------------|
| Date | Event date |
| Type icon | 📋 Filing, ⚖️ Order, 📧 Notice, 🔔 Hearing, 💼 Transaction, etc. |
| Title | Event name |
| Description | What happened |
| Actor(s) | Who was involved (linked to Entities) |
| Source | Document + page (clickable) |
| Cross-references | Links to/from other documents |
| Verification status | Verified/Pending/Flagged |
| Contradiction flag | If this event conflicts with another |

### 7.3 Event Types

| Icon | Type | Examples |
|------|------|----------|
| 📋 | Filing | Petitions, applications, affidavits |
| ⚖️ | Order | Court orders, judgments, rulings |
| 📧 | Notice | Notices sent, received, served |
| 🔔 | Hearing | Court hearings, appearances |
| 💼 | Transaction | Financial transactions, transfers |
| 📄 | Document | Documents submitted, received |
| ⏰ | Deadline | Statutory deadlines, due dates |
| ✍️ | Signature | Documents signed, executed |
| 🏛️ | Registration | Property/document registrations |
| 📬 | Communication | Letters, emails, correspondence |

### 7.4 Gap Detection (PHASE 2)

> **DEFERRED to Phase 2:** Requires Process Chain Engine with user-created templates.

| Aspect | MVP | Phase 2 |
|--------|-----|---------|
| Timeline display | Chronological events only | Gap detection cards |
| Gap highlighting | ❌ Not available | ⚠️ Yellow/orange warning between events |
| Gap actions | ❌ Not available | Mark as expected, Add docs, Investigate |

### 7.5 Duration Calculations

| Decision | Show elapsed time between events |
|----------|--------------------------------|
| Display | Duration shown on connector line between events |
| Highlight | Significant delays flagged (e.g., "254 days - exceeds statutory 90 days") |

### 7.6 Multi-Track Timeline

| Decision | Optional multi-track view for complex cases |
|----------|-------------------------------------------|
| Purpose | Show parallel timelines by actor (Petitioner, Court, Custodian) |
| When to use | Cases with many actors, parallel proceedings |

### 7.7 Manual Event Addition

| Decision | Users can add events LDIP missed |
|----------|--------------------------------|
| Fields | Date, Type, Title, Description, Actor, Source document |
| Marked as | "Manually added" (distinguished from AI-extracted) |

### 7.8 Filter Options

| Filter | Options |
|--------|---------|
| Event Type | Filing, Order, Notice, Hearing, Transaction, etc. |
| Actors | List of all actors in matter |
| Date Range | All time, Last year, Custom range |
| Verification Status | Verified, Pending, Flagged |

---

## 8. Cross-Referencing

### 8.1 PDF Viewer with Cross-Reference Links Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  📄 Petition.pdf - Page 45 of 234                              [⛶][✕]          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │    The petitioner submits that the property in question was              │ │
│  │    duly registered as evidenced in ┌─────────────────────────┐           │ │
│  │                                    │ Annexure P-12, page 3   │           │ │
│  │                                    │        🔗 Click to view │           │ │
│  │                                    └─────────────────────────┘           │ │
│  │    Furthermore, the timeline of events as recorded in                    │ │
│  │    ┌──────────────────────────────┐ clearly establishes that            │ │
│  │    │ Exhibit A, pages 14-18       │                                     │ │
│  │    │         🔗 Click to view     │                                     │ │
│  │    └──────────────────────────────┘                                     │ │
│  │    the notice was served prior to the attachment order                  │ │
│  │    dated 10.06.2018 (see ┌────────────────────────────────┐).          │ │
│  │                          │ Order dated 10.06.2018         │            │ │
│  │                          │ (Court_Order_June.pdf, pg 1)   │            │ │
│  │                          │          🔗 Click to view      │            │ │
│  │                          └────────────────────────────────┘            │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  🔗 3 CROSS-REFERENCES DETECTED ON THIS PAGE                    [Show All ▼]   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Cross-Reference Split View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  🔗 CROSS-REFERENCE VIEW                                              [✕]      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────┐  ┌────────────────────────────────────┐   │
│  │  📄 SOURCE                     │  │  📄 TARGET                         │   │
│  │  Petition.pdf - Page 45        │  │  Annexure_P12.pdf - Page 3         │   │
│  │  ─────────────────────────     │  │  ─────────────────────────────     │   │
│  │                                │  │                                    │   │
│  │  ...the property in question   │  │                                    │   │
│  │  was duly registered as        │  │  REGISTRATION DEED                 │   │
│  │  evidenced in                  │  │  No. 4521/2016                     │   │
│  │  ┌───────────────────────────┐│  │                                    │   │
│  │  │ Annexure P-12, page 3 🔗 ││◄─┼──► Property situated at Plot      │   │
│  │  └───────────────────────────┘│  │  No. 45, Andheri West, Mumbai     │   │
│  │  Furthermore, the timeline... │  │  hereby registered in the name    │   │
│  │                                │  │  of Nirav D. Jobalia...           │   │
│  │                                │  │                                    │   │
│  │  [◀ Prev Ref] [Next Ref ▶]    │  │  [View Full Document]              │   │
│  │                                │  │                                    │   │
│  └────────────────────────────────┘  └────────────────────────────────────┘   │
│                                                                                 │
│  [✓ Verify Match]  [✗ Incorrect]  [Add Note]                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Cross-Reference Map Wireframe (PHASE 2)

> **DEFERRED to Phase 2:** The interactive Cross-Reference Map visualization is deferred. MVP includes inline cross-reference links in PDF viewer and reference counts in Documents Tab. See [Phase-2-Backlog.md](Phase-2-Backlog.md).

<details>
<summary>Click to expand Phase 2 Cross-Reference Map Design</summary>

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ DOCUMENTS TAB                                                                   │
│ VIEW: [List] [Grid] [● Cross-Reference Map]                    [+ ADD FILES]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                        CROSS-REFERENCE MAP                                      │
│                                                                                 │
│                         ┌─────────────┐                                        │
│                         │  Petition   │                                        │
│                         │  (234 pg)   │                                        │
│                         └──────┬──────┘                                        │
│                  ┌─────────────┼─────────────┐                                 │
│                  │             │             │                                 │
│                  ▼             ▼             ▼                                 │
│          ┌───────────┐ ┌───────────┐ ┌───────────┐                            │
│          │Annexure   │ │ Exhibit A │ │  Court    │                            │
│          │  P-12     │ │           │ │  Order    │                            │
│          │ (45 pg)   │ │ (89 pg)   │ │ (12 pg)   │                            │
│          └─────┬─────┘ └───────────┘ └─────┬─────┘                            │
│                │                           │                                   │
│                │         ┌─────────────────┘                                   │
│                ▼         ▼                                                     │
│          ┌─────────────────┐                                                  │
│          │ Reply Affidavit │◄─────── References both                          │
│          │    (156 pg)     │                                                  │
│          └─────────────────┘                                                  │
│                                                                                │
│  Legend: ───► = "references"   Line thickness = frequency                     │
│  Click any document to see its references                                     │
│                                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

</details>

### 8.4 What Cross-References Are

| Pattern | Example |
|---------|---------|
| Exhibit references | "See Exhibit A, page 14" |
| Document references | "As per Document 23, para 5" |
| Annexure references | "Vide Annexure P-12" |
| Order references | "Pursuant to Order dated 15.06.2018" |
| Page/Para references | "Page 45, lines 12-18 of the Petition" |

### 8.2 Where Cross-References Appear (MVP)

| Location | Feature | Status |
|----------|---------|--------|
| PDF Viewer | Inline clickable links on detected references | **MVP** |
| PDF Viewer Sidebar | Panel showing all refs in current document | **MVP** |
| Documents Tab | Reference count per document (→ refs out, ← refs in) | **MVP** |
| Q&A Panel | Follows reference chains, shows linked evidence | **MVP** |
| Timeline Tab | Shows supporting evidence for each event | **MVP** |
| Documents Tab | Cross-Reference Map visualization | **Phase 2** |

### 8.3 Cross-Reference Navigation

| Decision | Split view showing source ↔ target side-by-side |
|----------|------------------------------------------------|
| Click behavior | Opens target document at exact page |
| Original stays open | For comparison |

### 8.4 Unresolved Reference Handling

| Scenario | UX Response |
|----------|-------------|
| Document not uploaded | "Exhibit C not found" → Prompt to upload |
| Ambiguous match | "Multiple matches" → Ask user to select |
| Page doesn't exist | Flag as error |
| OCR misread | Low confidence → Show for manual correction |

---

## 9. Matter Workspace - Entities Tab

### 9.1 Entities Tab - Graph View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [■ Entities] [Citations] [Verification] [Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTITIES • 34 people/orgs • 12 locations • 8 properties                       │
│                                                                                 │
│  VIEW: [● Graph] [○ List] [○ Grid]     FILTER: [All Types ▼] [All Roles ▼]    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                         │   │
│  │                            ┌──────────┐                                │   │
│  │                            │  SEBI    │                                │   │
│  │              opposes       │(Regulator)│    oversees                   │   │
│  │          ┌─────────────────└────┬─────┘─────────────┐                  │   │
│  │          │                      │                   │                  │   │
│  │          ▼                      │                   ▼                  │   │
│  │    ┌───────────┐                │            ┌───────────┐             │   │
│  │    │  Nirav D. │                │            │ Parekh    │             │   │
│  │    │  Jobalia  │◄───────────────┼────────────│Securities │             │   │
│  │    │(Petitioner)│   employed by │            │  Ltd.     │             │   │
│  │    └─────┬─────┘                │            └─────┬─────┘             │   │
│  │          │                      │                  │                   │   │
│  │          │ owns                 │             owns │                   │   │
│  │          │                      │                  │                   │   │
│  │          ▼                      ▼                  ▼                   │   │
│  │    ┌───────────┐         ┌───────────┐      ┌───────────┐             │   │
│  │    │  Plot 45  │         │The Custodian│     │  Shares   │             │   │
│  │    │  Andheri  │         │(Respondent)│      │  Portfolio│             │   │
│  │    │(Property) │         └───────────┘      │(Asset)    │             │   │
│  │    └───────────┘                            └───────────┘             │   │
│  │                                                                         │   │
│  │  [Zoom: − ═══●═══ +]  [Center]  [Expand All]                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  Click any node to see details • Drag to rearrange • Scroll to zoom           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Entities Tab - List View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  VIEW: [○ Graph] [● List] [○ Grid]     FILTER: [All Types ▼] [All Roles ▼]    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  🔍 Search entities...                                                         │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  NAME                    │ TYPE      │ ROLE        │ MENTIONS │ STATUS │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  👤 Nirav D. Jobalia     │ Person    │ Petitioner  │ 127      │ ✓     │   │
│  │     AKA: N.D. Jobalia, Nirav Jobalia                                   │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  🏢 The Custodian        │ Org       │ Respondent  │ 89       │ ✓     │   │
│  │     Full: Official Custodian of Attached Property                      │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  👤 Jitendra Kumar       │ Person    │ Custodian   │ 45       │ ⏳    │   │
│  │     ⚠️ Possible alias: J. Kumar (3 mentions)                          │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  🏢 SEBI                 │ Regulator │ Authority   │ 156      │ ✓     │   │
│  │     Full: Securities and Exchange Board of India                       │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  🏠 Plot No. 45, Andheri │ Property  │ Subject     │ 34       │ ✓     │   │
│  │     Full address: Plot 45, Sector 12, Andheri West, Mumbai             │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  📄 Annexure P-12        │ Document  │ Evidence    │ 12       │ ✓     │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  ... 28 more entities                                          [Load] │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  [+ Add Entity Manually]   [Merge Selected]   [Export Entities]               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Entity Detail Panel Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌────────────────────────────────────────────────┬────────────────────────┐   │
│  │  ENTITY LIST                                   │  ENTITY DETAIL         │   │
│  │  (as above)                                    │                        │   │
│  │                                                │  👤 NIRAV D. JOBALIA   │   │
│  │  ┌──────────────────────────────────────────┐ │  Role: Petitioner      │   │
│  │  │ ► 👤 Nirav D. Jobalia ◄ SELECTED        │ │  Type: Person          │   │
│  │  └──────────────────────────────────────────┘ │  Confidence: 98%       │   │
│  │  ┌──────────────────────────────────────────┐ │  Status: ✓ Verified    │   │
│  │  │   🏢 The Custodian                       │ │                        │   │
│  │  └──────────────────────────────────────────┘ │  ─────────────────────  │   │
│  │  ┌──────────────────────────────────────────┐ │                        │   │
│  │  │   👤 Jitendra Kumar ⚠️                   │ │  ALIASES (3)           │   │
│  │  └──────────────────────────────────────────┘ │  ✓ N.D. Jobalia        │   │
│  │                                                │  ✓ Nirav Jobalia       │   │
│  │                                                │  ⏳ Mr. Jobalia (?)    │   │
│  │                                                │  [+ Add Alias]         │   │
│  │                                                │                        │   │
│  │                                                │  RELATIONSHIPS (4)     │   │
│  │                                                │  → employed by         │   │
│  │                                                │    Parekh Securities   │   │
│  │                                                │  → owns                │   │
│  │                                                │    Plot 45, Andheri    │   │
│  │                                                │  → opposes             │   │
│  │                                                │    SEBI                │   │
│  │                                                │  → represented by      │   │
│  │                                                │    Adv. R.K. Sharma    │   │
│  │                                                │                        │   │
│  │                                                │  MENTIONS (127)        │   │
│  │                                                │  📄 Petition.pdf (45)  │   │
│  │                                                │  📄 Reply_Aff.pdf (32) │   │
│  │                                                │  📄 Order.pdf (18)     │   │
│  │                                                │  [View All →]          │   │
│  │                                                │                        │   │
│  │                                                │  [✓ Verify] [✎ Edit]  │   │
│  └────────────────────────────────────────────────┴────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.4 Alias Detection & Management Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ⚠️ POTENTIAL ALIASES DETECTED                                   [Dismiss All] │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  "J. Kumar" (3 mentions) may be alias for "Jitendra Kumar" (45)        │   │
│  │                                                                         │   │
│  │  Evidence:                                                              │   │
│  │  • Both referred to as "Custodian" in same context                     │   │
│  │  • J. Kumar appears only in informal correspondence                     │   │
│  │  • No conflicting references found                                      │   │
│  │                                                                         │   │
│  │  Confidence: 87%                                                        │   │
│  │                                                                         │   │
│  │  [✓ Confirm - Same Person]  [✗ Different People]  [View Mentions]      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  "Special Court" (23) vs "Hon'ble Special Court Mumbai" (18)           │   │
│  │                                                                         │   │
│  │  Confidence: 94%                                                        │   │
│  │                                                                         │   │
│  │  [✓ Confirm - Same Entity]  [✗ Different Entities]  [View Mentions]    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.5 Entity Merge Modal Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  MERGE ENTITIES                                                         [✕]    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  You are merging 2 entities:                                                    │
│                                                                                 │
│  ┌─────────────────────────┐      ┌─────────────────────────┐                  │
│  │  👤 Jitendra Kumar      │  +   │  👤 J. Kumar            │                  │
│  │  45 mentions            │      │  3 mentions             │                  │
│  │  Custodian              │      │  Custodian              │                  │
│  └─────────────────────────┘      └─────────────────────────┘                  │
│                                                                                 │
│                            ▼                                                    │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  MERGED ENTITY                                                            │ │
│  │                                                                           │ │
│  │  Primary Name: [Jitendra Kumar          ▼]                               │ │
│  │                                                                           │ │
│  │  Aliases:                                                                 │ │
│  │  ✓ J. Kumar                                                              │ │
│  │  ☐ Jitendra K. (add?)                                                    │ │
│  │                                                                           │ │
│  │  Combined mentions: 48                                                    │ │
│  │  Role: Custodian                                                          │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ⚠️ This action cannot be undone. All 48 mentions will point to merged entity.│
│                                                                                 │
│                                        [Cancel]  [Merge Entities]              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.6 View Modes

| View | Best For |
|------|----------|
| Graph (default) | Visualizing relationships, understanding case structure |
| List | Browsing all entities, bulk operations |
| Grid | Quick overview with entity cards |

### 9.7 Entity Types

| Icon | Type | Examples |
|------|------|----------|
| 👤 | Person | Petitioner, Respondent, Witness, Judge, Advocate |
| 🏢 | Organization | Company, Bank, Authority, Court, Government body |
| 🏠 | Property | Land, Building, Asset, Plot, Flat |
| 📍 | Location | Address, City, Jurisdiction |
| 📄 | Document | Referenced exhibits, annexures |
| 💰 | Financial | Bank account, Transaction, Amount |
| ⚖️ | Legal | Case number, Section, Act |
| 📅 | Date | Key dates (extracted as entities when significant) |

### 9.8 Relationship Types

| Relationship | Description |
|--------------|-------------|
| employed by | Person works for organization |
| owns | Ownership of property/asset |
| represents | Advocate represents party |
| opposes | Adversarial relationship |
| related to | Family/business relation |
| located at | Entity is at location |
| issued by | Document issued by authority |
| filed by | Petition/application filed by party |
| directed to | Order directed to party |

### 9.9 Entity Resolution (MIG - Matter Identity Graph)

| Decision | AI automatically links same entities appearing with different names |
|----------|-------------------------------------------------------------------|
| Confidence shown | Each alias shows confidence percentage |
| User override | User can confirm/reject AI suggestions |
| Manual merge | User can manually merge entities they identify |

### 9.10 Graph Interactions

| Action | Behavior |
|--------|----------|
| Click node | Select entity, show detail panel |
| Double-click | Expand to show connected entities |
| Drag node | Rearrange graph layout |
| Scroll | Zoom in/out |
| Click relationship line | Show relationship details |
| Hover node | Tooltip with key info |

### 9.11 Filter Options

| Filter | Options |
|--------|---------|
| Entity Type | Person, Organization, Property, Location, Document, Financial |
| Role | Petitioner, Respondent, Witness, Authority, Court, etc. |
| Verification Status | Verified, Pending, Flagged, Unresolved aliases |
| Mention Count | All, >10 mentions, >50 mentions |
| Has Issues | Show only entities needing attention |

---

## 10. Matter Workspace - Citations Tab

### 10.1 Citations Tab - Main View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [Entities] [■ Citations] [Verification] [Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CITATIONS • 23 found • 18 verified • 3 issues • 2 pending                     │
│                                                                                 │
│  VIEW: [● List] [○ By Document] [○ By Act]     FILTER: [All Status ▼]         │
│  ☐ Show only issues                                                            │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⚠️ 3 CITATIONS NEED ATTENTION                                         │   │
│  │  • 2 citations have incorrect section references                        │   │
│  │  • 1 act title may be outdated                                          │   │
│  │  [Review Issues →]                                                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CITATION                        │ MENTIONS │ STATUS        │ ACTION   │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  ⚖️ Securities Act, 1992         │          │               │          │   │
│  │  ├── Section 3(3)                │    8     │ ✓ Verified    │ [View]  │   │
│  │  ├── Section 11(4)               │    4     │ ✓ Verified    │ [View]  │   │
│  │  ├── Section 15B                 │    3     │ ⚠️ Issue      │ [Fix]   │   │
│  │  │   ⚠️ Section 15B doesn't exist; did you mean 15(b)?                 │   │
│  │  └── Section 24                  │    3     │ ✓ Verified    │ [View]  │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  ⚖️ SARFAESI Act, 2002           │          │               │          │   │
│  │  ├── Section 13(2)               │    2     │ ✓ Verified    │ [View]  │   │
│  │  └── Section 17                  │    2     │ ⏳ Pending    │ [Verify]│   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  ⚖️ Code of Civil Procedure      │          │               │          │   │
│  │  └── Order XXI Rule 58           │    1     │ ✓ Verified    │ [View]  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  [Export Citations]  [+ Add Citation Manually]                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Citation Detail Panel Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌────────────────────────────────────────────────┬────────────────────────┐   │
│  │  CITATIONS LIST                                │  CITATION DETAIL       │   │
│  │  (as above)                                    │                        │   │
│  │                                                │  ⚖️ SECTION 3(3)       │   │
│  │  ┌──────────────────────────────────────────┐ │  Securities Act, 1992  │   │
│  │  │ ► Section 3(3) ◄ SELECTED               │ │                        │   │
│  │  └──────────────────────────────────────────┘ │  Status: ✓ Verified    │   │
│  │                                                │  Mentions: 8           │   │
│  │                                                │                        │   │
│  │                                                │  ─────────────────────  │   │
│  │                                                │                        │   │
│  │                                                │  SECTION TEXT          │   │
│  │                                                │  ┌──────────────────┐  │   │
│  │                                                │  │ "The Court may,  │  │   │
│  │                                                │  │ on an application│  │   │
│  │                                                │  │ made to it by... │  │   │
│  │                                                │  └──────────────────┘  │   │
│  │                                                │  [View Full Act →]     │   │
│  │                                                │                        │   │
│  │                                                │  APPEARS IN            │   │
│  │                                                │  📄 Petition.pdf       │   │
│  │                                                │     pg 12, 34, 45, 67  │   │
│  │                                                │  📄 Order.pdf          │   │
│  │                                                │     pg 1, 3, 8         │   │
│  │                                                │  📄 Reply_Aff.pdf      │   │
│  │                                                │     pg 23              │   │
│  │                                                │                        │   │
│  │                                                │  [✓ Verified by AI]    │   │
│  │                                                │  [✎ Add Note]          │   │
│  └────────────────────────────────────────────────┴────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Citation Issue Resolution Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ⚠️ CITATION ISSUE: Section 15B                                         [✕]    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PROBLEM DETECTED                                                               │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  "Section 15B of the Securities Act, 1992" - mentioned in Petition.pdf   │ │
│  │  page 67, line 14                                                        │ │
│  │                                                                           │ │
│  │  ⚠️ Issue: Section 15B does not exist in the Securities Act, 1992       │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  SUGGESTED CORRECTIONS                                                          │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ○ Section 15(b) - Penalties for failure to furnish information          │ │
│  │    Confidence: 87%                                                        │ │
│  │    [View Section Text]                                                    │ │
│  ├───────────────────────────────────────────────────────────────────────────┤ │
│  │  ○ Section 15A - Penalty for failure to redress investor grievances      │ │
│  │    Confidence: 45%                                                        │ │
│  │    [View Section Text]                                                    │ │
│  ├───────────────────────────────────────────────────────────────────────────┤ │
│  │  ○ This is intentional / correct as written                              │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  SOURCE DOCUMENT                                                                │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  "...as mandated under Section 15B of the Securities Act, 1992, the     │ │
│  │   petitioner was duty-bound to..."                                       │ │
│  │                                            [Open in PDF Viewer]          │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│                         [Dismiss Issue]  [Apply Correction]                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 View By Document Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  VIEW: [○ List] [● By Document] [○ By Act]                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  📄 PETITION.PDF (234 pages)                           12 citations            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  PAGE │ CITATION                           │ STATUS     │ ACTION       │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  12   │ Securities Act, 1992 - Section 3(3)│ ✓ Verified │ [View]      │   │
│  │  34   │ Securities Act, 1992 - Section 3(3)│ ✓ Verified │ [View]      │   │
│  │  45   │ SARFAESI Act, 2002 - Section 13(2) │ ✓ Verified │ [View]      │   │
│  │  67   │ Securities Act - Section 15B       │ ⚠️ Issue   │ [Fix]       │   │
│  │  89   │ CPC - Order XXI Rule 58            │ ✓ Verified │ [View]      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  📄 REPLY_AFFIDAVIT.PDF (156 pages)                    6 citations             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  PAGE │ CITATION                           │ STATUS     │ ACTION       │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  23   │ Securities Act, 1992 - Section 3(3)│ ✓ Verified │ [View]      │   │
│  │  45   │ Securities Act - Section 11(4)     │ ✓ Verified │ [View]      │   │
│  │  ...  │                                    │            │             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  📄 COURT_ORDER.PDF (12 pages)                         5 citations             │
│  [Expand ▼]                                                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 10.5 Citation Types

| Type | Icon | Examples |
|------|------|----------|
| Statute | ⚖️ | Securities Act, SARFAESI Act, Income Tax Act |
| Case Law | 📜 | AIR 2020 SC 1234, (2019) 5 SCC 678 |
| Rules/Orders | 📋 | CPC Order XXI, SEBI Regulations |
| Notifications | 📢 | Government notifications, circulars |
| International | 🌐 | Foreign case law, international conventions |

### 10.6 Citation Status Types

| Status | Icon | Description |
|--------|------|-------------|
| Verified | ✓ | Citation exists and matches source |
| Pending | ⏳ | Not yet verified |
| Issue | ⚠️ | Problem detected (wrong section, outdated, etc.) |
| Manual | 🔧 | User-added citation |
| Cannot Verify | ❓ | Unable to verify (act not in database) |

### 10.7 Issue Types Detected

| Issue | Description | Suggested Action |
|-------|-------------|------------------|
| Section doesn't exist | Referenced section not found in act | Suggest similar sections |
| Outdated act name | Act has been renamed/replaced | Show current name |
| Wrong year | Act year doesn't match | Suggest correct year |
| Typo in citation | OCR or drafting error | Suggest correction |
| Ambiguous reference | "the Act" without specifying which | Ask user to clarify |
| Conflicting citations | Same provision cited differently | Highlight both, ask user |

### 10.8 Filter Options

| Filter | Options |
|--------|---------|
| Status | All, Verified, Pending, Issues, Manual |
| Act Type | Statutes, Case Law, Rules, All |
| Document | Filter by source document |
| Frequency | All, >5 mentions, >10 mentions |

---

## 11. Contradictions in Verification Tab (MVP)

> **DECISION 10 UPDATE (2026-01-03):** The dedicated Contradictions Tab has been **DEFERRED to Phase 2**. In MVP, entity-based contradictions appear as a finding type in the Verification Tab. See [Phase-2-Backlog.md](Phase-2-Backlog.md) for the full Contradictions Tab design.

### 11.1 MVP Approach: Contradictions as Verification Findings

| Aspect | MVP Implementation | Phase 2 |
|--------|-------------------|---------|
| **Location** | Verification Tab (finding type) | Dedicated Contradictions Tab |
| **Scope** | Entity-based contradictions only | Full contradiction analysis |
| **View** | Filter by type="Contradiction" | Entity-grouped display |
| **Comparison** | Click to open PDF side-by-side | In-tab comparison view |
| **Resolution** | Same as other verification actions | Dedicated resolution workflow |

### 11.2 Contradiction Finding in Verification Tab - Wireframe (MVP)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [Entities] [Citations] [■ Verification] [Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  VERIFICATION QUEUE                              Filter: [Contradictions ▼]    │
│  4 findings need review                                                         │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⚡ CONTRADICTION                                    High Priority      │   │
│  │  ─────────────────────────────────────────────────────────────────────  │   │
│  │  Entity: Nirav D. Jobalia                                               │   │
│  │                                                                         │   │
│  │  Statement 1: "Notice sent on June 5, 2018"                             │   │
│  │  📄 Petition.pdf, pg 45                                                 │   │
│  │                                                                         │   │
│  │  Statement 2: "Notice received on June 8, 2018"                         │   │
│  │  📄 Reply_Affidavit.pdf, pg 12                                          │   │
│  │                                                                         │   │
│  │  Explanation: Same entity claims different notice dates                 │   │
│  │                                                                         │   │
│  │  [ ✓ Verify ] [ ✗ Reject ] [ ? Flag for Review ]                       │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⚡ CONTRADICTION                                    Medium Priority    │   │
│  │  ─────────────────────────────────────────────────────────────────────  │   │
│  │  Entity: State Bank of India                                            │   │
│  │                                                                         │   │
│  │  Statement 1: "Account balance was ₹45,00,000"                          │   │
│  │  Statement 2: "Account balance was ₹45,50,000"                          │   │
│  │                                                                         │   │
│  │  [ ✓ Verify ] [ ✗ Reject ] [ ? Flag for Review ]                       │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 What Users Get in MVP

| Feature | MVP | Phase 2 |
|---------|-----|---------|
| Entity-based contradiction detection | ✅ Yes | ✅ Yes |
| Contradictions visible in Verification Tab | ✅ Yes | ✅ Yes (plus dedicated tab) |
| Filter to see only contradictions | ✅ Yes | ✅ Yes |
| Verify/reject contradictions | ✅ Yes | ✅ Yes |
| Click to view source documents | ✅ Yes | ✅ Yes |
| Dedicated Contradictions tab | ❌ No | ✅ Yes |
| Entity-grouped contradiction view | ❌ No | ✅ Yes |
| Side-by-side comparison panel | ❌ No | ✅ Yes |
| Severity-based filtering (High/Medium/Low) | ❌ No | ✅ Yes |
| Timeline integration overlay | ❌ No | ✅ Yes |

### 11.4 Cross-Tab Integration (MVP)

| Tab | How Contradictions Appear |
|-----|---------------------------|
| Summary | Attention banner shows contradiction count |
| Verification | Contradictions appear as finding type with filter |
| Q&A Panel | AI mentions contradictions when relevant to queries |

---

## 11-PHASE2. Contradictions Tab - Dedicated View (DEFERRED)

> **Status:** DEFERRED to Phase 2. See [Phase-2-Backlog.md](Phase-2-Backlog.md).
> **Trigger:** After MVP completion + full contradiction analysis scope defined.

The following wireframes and specifications are preserved for Phase 2 implementation:

<details>
<summary>Click to expand Phase 2 Contradictions Tab Design</summary>

### Phase 2: Contradictions Tab - Main View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [Entities] [Citations] [■ Contradictions]            │
│       [Verification] [Documents]                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CONTRADICTIONS • 7 found • 3 resolved • 4 pending review                      │
│                                                                                 │
│  VIEW: [● All] [○ By Severity] [○ By Document]    FILTER: [All Status ▼]      │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⚠️ 4 CONTRADICTIONS NEED YOUR REVIEW                                  │   │
│  │  These may impact your case arguments. Review and resolve each one.    │   │
│  │  [Start Review →]                                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                         │   │
│  │  🔴 HIGH SEVERITY                                                       │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  ⚡ DATE CONFLICT: Notice Service Date                            │ │   │
│  │  │                                                                   │ │   │
│  │  │  📄 Petition.pdf, pg 45          📄 Reply_Affidavit.pdf, pg 12   │ │   │
│  │  │  "Notice served on               "Notice received on              │ │   │
│  │  │   June 5, 2018"                   June 8, 2018"                   │ │   │
│  │  │                                                                   │ │   │
│  │  │  ⏳ Pending Review          [Compare Side-by-Side]  [Resolve]    │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  ⚡ FACTUAL CONFLICT: Property Ownership                          │ │   │
│  │  │                                                                   │ │   │
│  │  │  📄 Petition.pdf, pg 89          📄 Annexure_P8.pdf, pg 3        │ │   │
│  │  │  "Sole owner since 2014"         "Joint ownership recorded       │ │   │
│  │  │                                   since 2016"                     │ │   │
│  │  │                                                                   │ │   │
│  │  │  ⏳ Pending Review          [Compare Side-by-Side]  [Resolve]    │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                         │   │
│  │  🟡 MEDIUM SEVERITY                                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  ⚡ AMOUNT DISCREPANCY: Transaction Value                         │ │   │
│  │  │  ₹45,00,000 (Petition) vs ₹45,50,000 (Bank Statement)            │ │   │
│  │  │  ✓ Resolved: Rounding difference, noted                          │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Contradiction Detail - Side-by-Side Comparison Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ⚡ CONTRADICTION DETAIL                                                 [✕]    │
│  DATE CONFLICT: Notice Service Date                                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  SEVERITY: 🔴 HIGH        TYPE: Date Conflict        DETECTED: 2 hours ago    │
│                                                                                 │
│  ┌────────────────────────────────┐  ┌────────────────────────────────────┐   │
│  │  📄 SOURCE A                   │  │  📄 SOURCE B                       │   │
│  │  Petition.pdf, Page 45         │  │  Reply_Affidavit.pdf, Page 12     │   │
│  │  ─────────────────────────     │  │  ─────────────────────────────     │   │
│  │                                │  │                                    │   │
│  │  "The petitioner hereby       │  │  "The undersigned acknowledges    │   │
│  │   states that the statutory   │  │   receipt of notice on            │   │
│  │   notice under Section 13(2)  │  │   ┌──────────────────────────┐    │   │
│  │   was duly served on          │  │   │ 8th day of June, 2018    │    │   │
│  │   ┌──────────────────────┐    │  │   └──────────────────────────┘    │   │
│  │   │ 5th June, 2018       │    │  │   as evidenced by the postal     │   │
│  │   └──────────────────────┘    │  │   receipt annexed herewith..."   │   │
│  │   through registered post..." │  │                                    │   │
│  │                                │  │                                    │   │
│  │  [Open Full Document]         │  │  [Open Full Document]              │   │
│  └────────────────────────────────┘  └────────────────────────────────────┘   │
│                                                                                 │
│  AI ANALYSIS                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  This appears to be a genuine date conflict. The 3-day discrepancy       │ │
│  │  could represent:                                                         │ │
│  │  • Sending date vs. receipt date (postal transit time)                   │ │
│  │  • Error in one of the documents                                         │ │
│  │                                                                           │ │
│  │  Recommendation: Check postal receipt in Annexure P-12 for actual dates │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  RESOLUTION                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ○ Not a contradiction - dates refer to different events                 │ │
│  │  ○ Petitioner's date (June 5) is correct                                 │ │
│  │  ○ Respondent's date (June 8) is correct                                 │ │
│  │  ○ Both dates are correct (send vs receive)                              │ │
│  │  ○ Error in documents - note for argument                                │ │
│  │  ○ Other: [_________________________________]                            │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  Add Note: [________________________________________________]                  │
│                                                                                 │
│                              [Dismiss]  [Mark as Resolved]                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 Contradictions in Context (Timeline Integration) Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  TIMELINE TAB - with Contradiction Overlay                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ☑ Show contradictions                                                         │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  📅 June 5, 2018                                                        │   │
│  │  📧 NOTICE SENT                                                         │   │
│  │  Notice sent to Custodian regarding dematerialisation                   │   │
│  │  📄 Source: Petition.pdf, pg 45                                        │   │
│  │                                                                         │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │  ⚠️ CONTRADICTION DETECTED                                      │   │   │
│  │  │  Reply Affidavit states notice received on June 8, 2018        │   │   │
│  │  │  [View Contradiction →]                                         │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                         │   │
│  │  [View Source]  [⏳ Pending]                                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│          │                                                                     │
│          │ ← 3 days (disputed)                                                │
│          │                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  📅 June 8, 2018                                                        │   │
│  │  📧 NOTICE RECEIVED (per Reply Affidavit)                              │   │
│  │  📄 Source: Reply_Affidavit.pdf, pg 12                                 │   │
│  │                                                                         │   │
│  │  ⚠️ Part of contradiction with June 5 notice                          │   │
│  │  [View Contradiction →]                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 11.4 Contradiction Types

| Type | Icon | Description | Example |
|------|------|-------------|---------|
| Date Conflict | 📅 | Same event, different dates | Notice sent June 5 vs June 8 |
| Factual Conflict | 📋 | Contradictory facts | Sole owner vs Joint owner |
| Amount Discrepancy | 💰 | Different monetary values | ₹45L vs ₹45.5L |
| Statement Conflict | 💬 | Contradictory statements | "Never received" vs "Acknowledged receipt" |
| Entity Conflict | 👤 | Different names/roles | "Director" vs "Shareholder" |
| Sequence Conflict | ⏱️ | Events in wrong order | A before B vs B before A |

### 11.5 Severity Levels

| Level | Icon | Criteria | Examples |
|-------|------|----------|----------|
| High | 🔴 | Impacts core case arguments, dates of critical events, key facts | Notice dates, ownership claims |
| Medium | 🟡 | Inconsistencies that may need explanation | Minor amount differences, title variations |
| Low | 🟢 | Minor discrepancies, likely OCR or typo errors | Spelling variations, format differences |

### 11.6 Resolution Status

| Status | Icon | Description |
|--------|------|-------------|
| Pending Review | ⏳ | Not yet reviewed by user |
| Under Investigation | 🔍 | User is actively investigating |
| Resolved | ✓ | User has marked as resolved with explanation |
| Dismissed | ✕ | False positive, not a real contradiction |
| Flagged for Argument | ⚡ | Real contradiction to use in case |

### 11.7 Filter Options

| Filter | Options |
|--------|---------|
| Status | All, Pending, Resolved, Dismissed, Flagged |
| Severity | All, High, Medium, Low |
| Type | Date, Factual, Amount, Statement, Entity, Sequence |
| Document | Filter by source documents |

### Phase 2: Cross-Tab Integration

| Tab | How Contradictions Appear |
|-----|---------------------------|
| Summary | Attention banner shows contradiction count |
| Timeline | Events with contradictions show warning badge |
| Entities | Entity cards show if involved in contradictions |
| Verification | Contradictions appear in verification queue |
| Q&A Panel | AI mentions contradictions when relevant to queries |

</details>

---

## 12. Matter Workspace - Verification Tab

### 12.1 Verification Tab - Main View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [Entities] [Citations] [■ Verification] [Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  VERIFICATION CENTER                                                            │
│  ████████████████████████░░░░░░░░░░  67% Complete                              │
│  127 verified • 42 pending • 3 flagged                                         │
│                                                                                 │
│  VIEW: [● Queue] [○ By Type] [○ History]       [Start Review Session →]       │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  PENDING VERIFICATION (42)                                              │   │
│  │                                                                         │   │
│  │  📊 BY CATEGORY                                                         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │   │
│  │  │ Summary │ │Timeline │ │ Entity  │ │Citation │ │Contradict│          │   │
│  │  │   12    │ │   8     │ │   15    │ │    4    │ │    3    │          │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  VERIFICATION QUEUE                                     [Sort: Priority ▼] │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  🔴 HIGH PRIORITY                                                       │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  ⚡ Contradiction: Notice Date                    [Contradictions] │ │   │
│  │  │  June 5 vs June 8, 2018                                           │ │   │
│  │  │  📄 Petition.pdf pg 45 ↔ Reply_Affidavit.pdf pg 12               │ │   │
│  │  │                                              [Review]  [Skip]     │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  ⚠️ Citation Issue: Section 15B                       [Citations] │ │   │
│  │  │  Section may not exist in Securities Act                         │ │   │
│  │  │  📄 Petition.pdf pg 67                                           │ │   │
│  │  │                                              [Review]  [Skip]     │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                         │   │
│  │  🟡 MEDIUM PRIORITY                                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  👤 Entity Alias: J. Kumar → Jitendra Kumar?          [Entities]  │ │   │
│  │  │  Confidence: 87%                                                  │ │   │
│  │  │                                              [Confirm]  [Reject]  │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │   │
│  │  │  📅 Timeline Event: Property Registration               [Timeline]│ │   │
│  │  │  Date extracted: March 15, 2016                                   │ │   │
│  │  │  📄 Annexure_P8.pdf pg 3                                         │ │   │
│  │  │                                              [Verify]  [Edit]     │ │   │
│  │  └───────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                         │   │
│  │  [Load More...]                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Verification Review Session Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  VERIFICATION SESSION                                    Item 3 of 42    [✕]    │
│  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░  7%                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ITEM: Timeline Event - Notice Sent                                            │
│  TYPE: Timeline     SOURCE: AI Extraction     CONFIDENCE: 92%                 │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  EXTRACTED INFORMATION                                                    │ │
│  │                                                                           │ │
│  │  Date:    June 5, 2018                                                   │ │
│  │  Event:   Notice sent to Custodian                                       │ │
│  │  Actor:   Nirav D. Jobalia (Petitioner)                                  │ │
│  │  Type:    Notice                                                          │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  SOURCE DOCUMENT                                                                │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  📄 Petition.pdf - Page 45                               [Open Full ⛶]  │ │
│  │  ─────────────────────────────────────────────────────────────────────   │ │
│  │                                                                           │ │
│  │  "...the petitioner states that the statutory notice under              │ │
│  │   Section 13(2) was duly served on ┌────────────────────────────┐       │ │
│  │                                    │ 5th June, 2018             │       │ │
│  │                                    └────────────────────────────┘       │ │
│  │   through registered post bearing number AD123456789..."                │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  VERIFICATION ACTION                                                            │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ○ ✓ Correct - Verify as accurate                                        │ │
│  │  ○ ✎ Edit - Information needs correction                                 │ │
│  │  ○ ⚠️ Flag - Mark for further review                                     │ │
│  │  ○ ✕ Dismiss - Not relevant / false positive                             │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  Add Note: [________________________________________________]                  │
│                                                                                 │
│  [◀ Previous]                           [Skip]  [Submit & Next ▶]             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Verification History View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  VIEW: [○ Queue] [○ By Type] [● History]                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  VERIFICATION HISTORY                                   [Export Log]           │
│  127 items verified • Last verified: 2 hours ago                               │
│                                                                                 │
│  🔍 [Search history...]     FILTER: [All ▼]  [All Types ▼]  [All Time ▼]      │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ITEM                      │ TYPE      │ RESULT    │ BY      │ DATE     │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  Case Filed - May 2016     │ Timeline  │ ✓ Verified│ Juhi    │ 2h ago  │   │
│  │  Section 3(3) citation     │ Citation  │ ✓ Verified│ Juhi    │ 2h ago  │   │
│  │  Nirav D. Jobalia         │ Entity    │ ✓ Verified│ Juhi    │ 2h ago  │   │
│  │  Amount ₹45L discrepancy   │ Contradict│ ✓ Resolved│ Juhi    │ 3h ago  │   │
│  │  Property ownership claim  │ Summary   │ ⚠️ Flagged│ Juhi    │ 3h ago  │   │
│  │  SARFAESI Section 13       │ Citation  │ ✓ Verified│ Juhi    │ 3h ago  │   │
│  │  ...                       │           │           │         │         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  STATISTICS                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                             │
│  │ ✓ 124   │ │ ✎ 12    │ │ ⚠️ 3    │ │ ✕ 8     │                             │
│  │Verified │ │ Edited  │ │ Flagged │ │Dismissed│                             │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 Verification Actions

| Action | Icon | Description | Result |
|--------|------|-------------|--------|
| Verify | ✓ | Confirm AI extraction is accurate | Marked as verified with timestamp |
| Edit | ✎ | Correct errors in extracted data | Opens edit modal, saves correction |
| Flag | ⚠️ | Mark for further review | Added to flagged items list |
| Dismiss | ✕ | False positive, not relevant | Removed from queue |

### 12.5 Verification Sources

| Source | Icon | Description |
|--------|------|-------------|
| Summary | 📋 | Key facts in executive summary |
| Timeline | 📅 | Extracted dates and events |
| Entities | 👤 | People, organizations, aliases |
| Citations | ⚖️ | Legal references and sections |
| Contradictions | ⚡ | Detected inconsistencies |
| Cross-References | 🔗 | Document references |

### 12.6 Priority Levels

| Priority | Icon | Auto-assigned When |
|----------|------|-------------------|
| High | 🔴 | Contradictions, citation errors, low confidence extractions |
| Medium | 🟡 | Entity aliases, timeline events, cross-references |
| Low | 🟢 | High-confidence extractions, minor details |

### 12.7 Confidence Scoring

| Level | Range | Display |
|-------|-------|---------|
| High | 90-100% | Green badge, lower priority in queue |
| Medium | 70-89% | Yellow badge, medium priority |
| Low | <70% | Red badge, high priority |

### 12.8 Inline Verification (Across All Tabs)

Every verifiable item across all tabs has inline verification buttons:

| Button | Action |
|--------|--------|
| [✓ Verify] | Mark as verified without leaving current tab |
| [✗ Flag] | Flag for review |
| [💬 Note] | Add a note to this item |

---

## 13. Pending Decisions

### 13.1 To Be Detailed

The following pages/components are planned but not yet detailed:

- [x] Matter Workspace - Entities Tab *(Completed)*
- [x] Matter Workspace - Citations Tab *(Completed)*
- [x] Matter Workspace - Contradictions Tab *(Completed)*
- [x] Matter Workspace - Verification Tab *(Completed)*
- [x] Matter Workspace - Documents Tab *(Completed)*
- [ ] Q&A Panel (full detail)
- [ ] PDF Viewer (full detail)
- [ ] Export Builder (full detail)

---

## 13. Matter Workspace - Documents Tab

### 13.1 Documents Tab - Main View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ TABS: [Summary] [Timeline] [Entities] [Citations] [Verification] [■ Documents]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  DOCUMENTS                                                  ┌────────────────┐  │
│  89 documents • 2,100 pages • Last updated: 2 hours ago    │ + ADD FILES    │  │
│                                                             └────────────────┘  │
│                                                                                 │
│  VIEW: [● List] [○ Grid] [○ Cross-Reference Map]     🔍 [Search documents...] │
│  FILTER: [All Types ▼]  [All Status ▼]                                        │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                         │   │
│  │  📄 NAME                    │ PAGES │ ADDED        │ STATUS    │       │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  📁 CORE PLEADINGS                                              [▼]    │   │
│  │  ├── 📄 Petition.pdf            │ 234   │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │   │
│  │  ├── 📄 Reply_Affidavit.pdf     │ 156   │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │   │
│  │  └── 📄 Rejoinder.pdf           │ 89    │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  📁 ORDERS                                                      [▼]    │   │
│  │  ├── 📄 Court_Order_June.pdf    │ 12    │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │   │
│  │  ├── 📄 Court_Order_Sept.pdf    │ 8     │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │   │
│  │  └── 📄 Final_Order_Jan.pdf     │ 15    │ Dec 28, 2025 │ ✓ Indexed │ [⋮]  │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  📁 ANNEXURES (45 documents)                                    [►]    │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  📁 EXHIBITS (23 documents)                                     [►]    │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  📁 CORRESPONDENCE (12 documents)                               [►]    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⏳ PROCESSING (2 files)                                               │   │
│  │  ████████████░░░░░░░░░░░░░░░░░░░░  34%                                │   │
│  │  📄 New_Annexure_P12.pdf (45 pg) - Extracting text...                 │   │
│  │  📄 Updated_Bank_Statement.pdf (23 pg) - Queued                        │   │
│  │  [Continue working while processing...]                                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Document Detail Panel Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌────────────────────────────────────────────────┬────────────────────────┐   │
│  │  DOCUMENT LIST                                 │  DOCUMENT DETAIL       │   │
│  │  (as above)                                    │                        │   │
│  │                                                │  📄 PETITION.PDF       │   │
│  │  ┌──────────────────────────────────────────┐ │                        │   │
│  │  │ ► 📄 Petition.pdf ◄ SELECTED            │ │  Status: ✓ Indexed     │   │
│  │  └──────────────────────────────────────────┘ │  Pages: 234            │   │
│  │                                                │  Size: 12.4 MB         │   │
│  │                                                │  Added: Dec 28, 2025   │   │
│  │                                                │                        │   │
│  │                                                │  ─────────────────────  │   │
│  │                                                │                        │   │
│  │                                                │  EXTRACTED DATA        │   │
│  │                                                │  👤 45 entities        │   │
│  │                                                │  📅 23 dates           │   │
│  │                                                │  ⚖️ 12 citations       │   │
│  │                                                │  🔗 8 cross-refs       │   │
│  │                                                │                        │   │
│  │                                                │  REFERENCES THIS DOC   │   │
│  │                                                │  ← Reply_Affidavit (5) │   │
│  │                                                │  ← Court_Order (3)     │   │
│  │                                                │                        │   │
│  │                                                │  THIS DOC REFERENCES   │   │
│  │                                                │  → Annexure_P12 (4)    │   │
│  │                                                │  → Exhibit_A (2)       │   │
│  │                                                │                        │   │
│  │                                                │  [Open in Viewer]      │   │
│  │                                                │  [Download]            │   │
│  │                                                │  [Delete]              │   │
│  └────────────────────────────────────────────────┴────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.3 Cross-Reference Map View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  VIEW: [○ List] [○ Grid] [● Cross-Reference Map]                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                        CROSS-REFERENCE MAP                                      │
│                                                                                 │
│                         ┌─────────────┐                                        │
│                         │  Petition   │                                        │
│                         │  (234 pg)   │                                        │
│                         └──────┬──────┘                                        │
│                  ┌─────────────┼─────────────┐                                 │
│                  │             │             │                                 │
│                  ▼             ▼             ▼                                 │
│          ┌───────────┐ ┌───────────┐ ┌───────────┐                            │
│          │Annexure   │ │ Exhibit A │ │  Court    │                            │
│          │  P-12     │ │           │ │  Order    │                            │
│          │ (45 pg)   │ │ (89 pg)   │ │ (12 pg)   │                            │
│          └─────┬─────┘ └───────────┘ └─────┬─────┘                            │
│                │                           │                                   │
│                │         ┌─────────────────┘                                   │
│                ▼         ▼                                                     │
│          ┌─────────────────┐                                                  │
│          │ Reply Affidavit │◄─────── References both                          │
│          │    (156 pg)     │                                                  │
│          └─────────────────┘                                                  │
│                                                                                │
│  Legend: ───► = "references"   Line thickness = frequency                     │
│  Click any document to see its references                                     │
│                                                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  SELECTED: Petition.pdf                                               │   │
│  │  ← Referenced by: Reply_Affidavit (5), Court_Order (3)               │   │
│  │  → References: Annexure_P12 (4), Exhibit_A (2), Court_Order (1)      │   │
│  │  [Open Document]                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.4 Add Files Modal Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ADD DOCUMENTS TO MATTER                                                 [✕]    │
│  Shah v. Mehta Securities Matter                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │                  ┌───────────────┐                                        │ │
│  │                  │   📁 → 📄     │                                        │ │
│  │                  └───────────────┘                                        │ │
│  │                                                                           │ │
│  │            Drag & drop your files here                                   │ │
│  │                        or                                                 │ │
│  │                 [Browse Files]                                            │ │
│  │                                                                           │ │
│  │     Supported: PDF, ZIP (containing PDFs)                                │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ORGANIZE INTO FOLDER                                                           │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  ○ Core Pleadings                                                        │ │
│  │  ○ Orders                                                                 │ │
│  │  ○ Annexures                                                              │ │
│  │  ○ Exhibits                                                               │ │
│  │  ○ Correspondence                                                         │ │
│  │  ○ + Create new folder: [________________]                               │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ⚠️ New documents will be processed and merged into existing analysis.        │
│  You can continue working while processing happens in the background.         │
│                                                                                 │
│                                                    [Cancel]  [Upload Files]    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.5 Document Status Types

| Status | Icon | Description |
|--------|------|-------------|
| Indexed | ✓ | Fully processed, text extracted, analysis complete |
| Processing | ⏳ | Currently being processed |
| Queued | ⏸️ | Waiting to be processed |
| Error | ⚠️ | Processing failed (OCR error, corrupt file) |
| Partial | 🔶 | Partially processed (some pages failed) |

### 13.6 Document Categories (Auto-suggested)

| Category | Contents |
|----------|----------|
| Core Pleadings | Petitions, Applications, Affidavits |
| Orders | Court orders, Judgments, Rulings |
| Annexures | Annexures to pleadings |
| Exhibits | Exhibits referenced in documents |
| Correspondence | Letters, Emails, Communications |
| Uncategorized | New uploads before categorization |

### 13.7 Document Actions Menu [⋮]

| Action | Description |
|--------|-------------|
| Open in Viewer | Opens document in PDF viewer |
| Download | Downloads original file |
| Rename | Rename document |
| Move to Folder | Move to different category |
| View Extracted Data | Shows entities, dates, citations from this doc |
| Re-process | Re-runs OCR and analysis |
| Delete | Removes from matter (with confirmation) |

### 13.8 Filter Options

| Filter | Options |
|--------|---------|
| Type | All, Core Pleadings, Orders, Annexures, Exhibits, Correspondence |
| Status | All, Indexed, Processing, Error |
| Has Issues | Show only documents with problems |
| Date Added | All time, Last 7 days, Last 30 days |

---

## 14. Q&A Panel

### 14.1 Q&A Panel - Default Position (Right Sidebar) Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ MATTER WORKSPACE                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────┬────────────────────────────┐ │
│  │                                               │  💬 ASK LDIP  [─][□][✕]   │ │
│  │                                               │  ═══════════════          │ │
│  │                                               │                            │ │
│  │           MAIN CONTENT AREA                   │  Start a conversation     │ │
│  │           (Current Tab)                       │  about this matter...     │ │
│  │                                               │                            │ │
│  │                                               │  SUGGESTED QUESTIONS       │ │
│  │                                               │  ┌────────────────────┐   │ │
│  │                                               │  │ What is this case  │   │ │
│  │                                               │  │ about?             │   │ │
│  │                                               │  └────────────────────┘   │ │
│  │                                               │  ┌────────────────────┐   │ │
│  │                                               │  │ Who are the main   │   │ │
│  │                                               │  │ parties?           │   │ │
│  │                                               │  └────────────────────┘   │ │
│  │                                               │  ┌────────────────────┐   │ │
│  │                                               │  │ What are the key   │   │ │
│  │                                               │  │ dates?             │   │ │
│  │                                               │  └────────────────────┘   │ │
│  │                                               │                            │ │
│  │◄─────────────────────────────────────────────►│◄─ Drag to resize ────────►│ │
│  │                                               │                            │ │
│  │                                               │  [Type your question...]  │ │
│  │                                               │                    [Ask]  │ │
│  └───────────────────────────────────────────────┴────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 14.2 Q&A Panel - Active Conversation Wireframe

```
┌────────────────────────────────────────┐
│  💬 ASK LDIP              [─][□][✕]   │
├────────────────────────────────────────┤
│                                        │
│  ┌────────────────────────────────┐   │
│  │ 👤 You                         │   │
│  │ What are the key dates in      │   │
│  │ this case?                     │   │
│  └────────────────────────────────┘   │
│                                        │
│  ┌────────────────────────────────┐   │
│  │ 🤖 LDIP                        │   │
│  │                                │   │
│  │ Here are the key dates in     │   │
│  │ this matter:                  │   │
│  │                                │   │
│  │ **May 12, 2016** - Case filed │   │
│  │ 📄 Petition.pdf, pg 1 [→]     │   │
│  │                                │   │
│  │ **June 5, 2018** - Notice sent│   │
│  │ 📄 Petition.pdf, pg 45 [→]    │   │
│  │ ⚠️ Note: Date disputed in    │   │
│  │ Reply Affidavit (June 8)      │   │
│  │                                │   │
│  │ **June 10, 2018** - Attachment│   │
│  │ Order issued                   │   │
│  │ 📄 Court_Order.pdf, pg 1 [→]  │   │
│  │                                │   │
│  │ **Jan 15, 2024** - Latest     │   │
│  │ order                          │   │
│  │ 📄 Final_Order.pdf, pg 1 [→]  │   │
│  │                                │   │
│  │ [View Full Timeline →]         │   │
│  │                                │   │
│  │ [✓] [✗] Was this helpful?    │   │
│  └────────────────────────────────┘   │
│                                        │
│  [Type your question...]              │
│                              [Ask]    │
│                                        │
└────────────────────────────────────────┘
```

### 14.3 Q&A Panel Position Options Wireframe

```
POSITION: RIGHT SIDEBAR (Default)
┌──────────────────────────┬───────────┐
│                          │           │
│    MAIN CONTENT          │   Q&A     │
│                          │           │
└──────────────────────────┴───────────┘

POSITION: BOTTOM PANEL
┌─────────────────────────────────────┐
│                                     │
│         MAIN CONTENT                │
│                                     │
├─────────────────────────────────────┤
│             Q&A PANEL               │
└─────────────────────────────────────┘

POSITION: FLOATING WINDOW
┌─────────────────────────────────────┐
│                                     │
│         MAIN CONTENT    ┌─────────┐ │
│                         │   Q&A   │ │
│                         │         │ │
│                         │         │ │
│                         └─────────┘ │
│                                     │
└─────────────────────────────────────┘

POSITION: HIDDEN (Collapsed)
┌─────────────────────────────────────┐
│                                     │
│         MAIN CONTENT        [💬]   │◄── Click to expand
│                                     │
└─────────────────────────────────────┘
```

### 14.4 Q&A Answer with Visual Citations Wireframe

```
┌────────────────────────────────────────┐
│  🤖 LDIP                              │
│                                        │
│  The attachment order was issued on   │
│  June 10, 2018 under Section 3(3) of  │
│  the Securities Act, 1992.            │
│                                        │
│  ┌────────────────────────────────┐   │
│  │  📄 VISUAL CITATION            │   │
│  │  Court_Order_June.pdf - Pg 1   │   │
│  │  ┌──────────────────────────┐  │   │
│  │  │  ┌────────────────────┐  │  │   │
│  │  │  │ "IT IS HEREBY      │  │  │   │
│  │  │  │ ORDERED under      │  │  │   │
│  │  │  │ Section 3(3)..."   │  │  │   │
│  │  │  └────────────────────┘  │  │   │
│  │  │   ▲ Highlighted          │  │   │
│  │  └──────────────────────────┘  │   │
│  │  [Open Full Document →]        │   │
│  └────────────────────────────────┘   │
│                                        │
│  Related findings:                     │
│  • ⚖️ Citation verified ✓            │
│  • 📅 Added to timeline               │
│  • 👤 Linked to: Special Court Mumbai │
│                                        │
└────────────────────────────────────────┘
```

### 14.5 Panel Controls

| Control | Icon | Action |
|---------|------|--------|
| Minimize | [─] | Collapses to small icon |
| Resize | [□] | Toggle between sizes |
| Close | [✕] | Hide panel completely |
| Position menu | [⚙️] | Choose Right/Bottom/Float/Hidden |
| Drag handle | ═══ | Drag to reposition (floating mode) |
| Resize handle | ◄► | Drag edge to resize width/height |

### 14.6 Conversation Features

| Feature | Description |
|---------|-------------|
| Visual citations | Inline document previews with highlights |
| Source links | Click to open PDF at exact location |
| Follow-up questions | AI suggests related questions |
| Contradiction alerts | AI mentions known contradictions when relevant |
| Cross-reference links | Shows linked evidence across documents |
| Feedback buttons | Thumbs up/down on each response |
| Copy response | Copy AI answer to clipboard |
| Export chat | Download conversation as PDF |

### 14.7 Suggested Questions (Context-Aware)

| Context | Suggested Questions |
|---------|-------------------|
| Initial | "What is this case about?", "Who are the main parties?", "What are the key dates?" |
| After viewing Timeline | "What happened between June 2018 and Jan 2019?", "Why is there a gap?" |
| After viewing Contradictions | "Explain the notice date discrepancy", "Which date is correct?" |
| After viewing Entity | "What is [Entity]'s role in this case?", "Show all mentions of [Entity]" |

### 14.8 Answer Format Types

| Type | Format |
|------|--------|
| Factual | Direct answer with source citations |
| Timeline | Chronological list with dates and sources |
| Comparison | Side-by-side comparison (for contradictions) |
| Summary | Narrative summary with key points |
| List | Bulleted list of findings/entities/citations |

### 14.9 Session Memory

| Decision | Q&A remembers conversation context within the session |
|----------|-----------------------------------------------------|
| Follow-ups | Can reference earlier questions ("What about the second date you mentioned?") |
| Clarification | Can ask for more detail on previous answers |
| Context | Knows what tab user is currently viewing |

---

## 15. PDF Viewer

### 15.1 PDF Viewer - Split View Mode Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ MATTER WORKSPACE                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────┬─────────────────────────────────┐   │
│  │                                       │  📄 Petition.pdf         [⛶][✕] │   │
│  │                                       │  Page 45 of 234    [◀][▶]      │   │
│  │           MAIN CONTENT AREA           │  ─────────────────────────────  │   │
│  │           (Tab content)               │                                 │   │
│  │                                       │  ┌─────────────────────────┐   │   │
│  │                                       │  │                         │   │   │
│  │  Timeline Tab showing                 │  │  ...the petitioner     │   │   │
│  │  the notice event...                  │  │  states that the       │   │   │
│  │                                       │  │  statutory notice      │   │   │
│  │  📅 June 5, 2018                     │  │  under Section 13(2)   │   │   │
│  │  📧 NOTICE SENT                      │  │  was duly served on    │   │   │
│  │  Notice sent to Custodian            │  │  ┌─────────────────┐   │   │   │
│  │  📄 Petition.pdf, pg 45 [→]◄─────────┼──│  │ 5th June, 2018  │   │   │   │
│  │                                       │  │  └─────────────────┘   │   │   │
│  │                                       │  │  through registered    │   │   │
│  │                                       │  │  post...               │   │   │
│  │                                       │  │                         │   │   │
│  │                                       │  └─────────────────────────┘   │   │
│  │                                       │                                 │   │
│  │◄─────────────────────────────────────►│◄── Drag to resize ────────────►│   │
│  │                                       │                                 │   │
│  │                                       │  [Zoom: −][+]  [🔍 Search]     │   │
│  └───────────────────────────────────────┴─────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 15.2 PDF Viewer - Full Modal Mode Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  📄 Petition.pdf                                                 [◰][⛶][✕]     │
│  Page 45 of 234                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────┐  ┌───────────────────────────────────────────────────────────┐  │
│  │  SIDEBAR  │  │                                                           │  │
│  │           │  │                        PAGE CONTENT                       │  │
│  │  Thumbnails│  │                                                           │  │
│  │  ┌─────┐  │  │  ┌──────────────────────────────────────────────────┐    │  │
│  │  │░░░░░│  │  │  │                                                  │    │  │
│  │  │ 43  │  │  │  │  12. The petitioner hereby states that the      │    │  │
│  │  └─────┘  │  │  │  statutory notice under Section 13(2) of the    │    │  │
│  │  ┌─────┐  │  │  │  Securitisation and Reconstruction of Financial │    │  │
│  │  │░░░░░│  │  │  │  Assets and Enforcement of Security Interest    │    │  │
│  │  │ 44  │  │  │  │  Act, 2002 was duly served on                   │    │  │
│  │  └─────┘  │  │  │  ┌────────────────────────────────────────────┐ │    │  │
│  │  ┌─────┐  │  │  │  │               5th June, 2018               │ │    │  │
│  │  │█████│◄─┼──│  │  │              ▲ HIGHLIGHTED ▲               │ │    │  │
│  │  │ 45  │  │  │  │  └────────────────────────────────────────────┘ │    │  │
│  │  └─────┘  │  │  │  through registered post bearing number         │    │  │
│  │  ┌─────┐  │  │  │  AD123456789IN addressed to the Custodian at   │    │  │
│  │  │░░░░░│  │  │  │  the registered office address.                │    │  │
│  │  │ 46  │  │  │  │                                                  │    │  │
│  │  └─────┘  │  │  │  13. The petitioner further states that...      │    │  │
│  │           │  │  │                                                  │    │  │
│  │ [▲ Hide]  │  │  └──────────────────────────────────────────────────┘    │  │
│  └───────────┘  │                                                           │  │
│                 └───────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  [◀ Prev Page]  Page [45] of 234  [Next Page ▶]   [Zoom: −][100%][+]   │   │
│  │  [🔍 Search in document]  [📋 Copy text]  [📥 Download]  [📄 Print]    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 15.3 PDF Viewer - With Cross-Reference Links Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  📄 Petition.pdf - Page 45                                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │    The petitioner submits that the property in question was              │ │
│  │    duly registered as evidenced in ┌─────────────────────────┐           │ │
│  │                                    │ Annexure P-12, page 3   │           │ │
│  │                                    │        🔗 Click to view │           │ │
│  │                                    └─────────────────────────┘           │ │
│  │    Furthermore, the timeline of events as recorded in                    │ │
│  │    ┌──────────────────────────────┐ clearly establishes that            │ │
│  │    │ Exhibit A, pages 14-18       │                                     │ │
│  │    │         🔗 Click to view     │                                     │ │
│  │    └──────────────────────────────┘                                     │ │
│  │    the notice was served prior to the attachment order.                 │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  🔗 3 CROSS-REFERENCES ON THIS PAGE                        [Show All ▼] │   │
│  │  • Annexure P-12, pg 3 - Registration deed                             │   │
│  │  • Exhibit A, pg 14-18 - Timeline evidence                             │   │
│  │  • Order dated 10.06.2018 - Attachment order                           │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 15.4 PDF Viewer - With Bounding Box Highlights Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  📄 Court_Order_June.pdf - Page 1                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  HIGHLIGHTS ON THIS PAGE:                                                       │
│  [📅 Date: June 10, 2018] [⚖️ Citation: Section 3(3)] [👤 Entity: SEBI]       │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │                       IN THE SPECIAL COURT                               │ │
│  │                                                                           │ │
│  │    ORDER                                                                  │ │
│  │    ┌────────────────────────────────────────────────────────────────┐    │ │
│  │    │ Dated: 10th June, 2018                                         │    │ │
│  │    │        ▲ 📅 DATE HIGHLIGHT                                    │    │ │
│  │    └────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                           │ │
│  │    In the matter of the petition filed by ┌───────────────────────┐     │ │
│  │    the                                    │ Securities and         │     │ │
│  │                                           │ Exchange Board of     │     │ │
│  │                                           │ India (SEBI)          │     │ │
│  │                                           │ ▲ 👤 ENTITY HIGHLIGHT │     │ │
│  │                                           └───────────────────────┘     │ │
│  │                                                                           │ │
│  │    IT IS HEREBY ORDERED under ┌──────────────────────────────────────┐  │ │
│  │                               │ Section 3(3) of the Securities Act   │  │ │
│  │                               │ ▲ ⚖️ CITATION HIGHLIGHT              │  │ │
│  │                               └──────────────────────────────────────┘  │ │
│  │    that the property shall be attached...                               │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 15.5 Viewer Modes

| Mode | Description | Trigger |
|------|-------------|---------|
| Split View (default) | Side-by-side with workspace | Click any citation link |
| Full Modal | Full-screen overlay | Click [⛶] expand button |
| Minimized | Collapsed to icon | Click [─] minimize |

### 15.6 Viewer Controls

| Control | Icon | Action |
|---------|------|--------|
| Expand | [⛶] | Open in full modal |
| Split/Restore | [◰] | Toggle between split sizes |
| Close | [✕] | Close viewer |
| Previous Page | [◀] | Go to previous page |
| Next Page | [▶] | Go to next page |
| Page Input | [45] | Jump to specific page |
| Zoom Out | [−] | Decrease zoom |
| Zoom Level | [100%] | Current zoom (click to reset) |
| Zoom In | [+] | Increase zoom |
| Search | [🔍] | Search within document |
| Copy Text | [📋] | Copy selected text |
| Download | [📥] | Download original PDF |
| Print | [📄] | Print document |

### 15.7 Highlight Types

| Type | Color | Icon | Examples |
|------|-------|------|----------|
| Date | Yellow | 📅 | "10th June, 2018" |
| Entity | Blue | 👤 | "SEBI", "Nirav D. Jobalia" |
| Citation | Green | ⚖️ | "Section 3(3)", "Order XXI" |
| Amount | Orange | 💰 | "₹45,00,000" |
| Cross-Reference | Purple | 🔗 | "Annexure P-12" |
| User-selected | Pink | 📌 | Any user-highlighted text |

### 15.8 Navigation Features

| Feature | Description |
|---------|-------------|
| Thumbnail sidebar | Quick page navigation |
| Page jump | Direct input for page number |
| Keyboard shortcuts | Arrow keys for page navigation |
| Scroll sync | Smooth scroll within page |
| Deep linking | Opens at exact page with highlight |
| Back button | Return to previous view position |

### 15.9 Cross-Reference Navigation

| Decision | Clicking a cross-reference link opens the target document |
|----------|----------------------------------------------------------|
| Behavior | Split view shows both source and target |
| Navigation | [◀ Prev Ref] [Next Ref ▶] to move through refs |
| Return | Click "Back to [source]" to return |

---

## 16. Export Builder

### 16.1 Export Builder - Section Selection Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EXPORT BUILDER                                                         [✕]    │
│  Shah v. Mehta Securities Matter                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STEP 1 OF 3: SELECT SECTIONS                                                   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ☑ INCLUDE   │  SECTION                          │  REORDER            │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  ☑           │  📋 Executive Summary             │  ≡ Drag to reorder │   │
│  │  ☑           │  👥 Parties                       │  ≡                  │   │
│  │  ☑           │  📅 Timeline of Events            │  ≡                  │   │
│  │  ☐           │  👤 Entity List                   │  ≡                  │   │
│  │  ☑           │  ⚖️ Citations                     │  ≡                  │   │
│  │  ☑           │  ⚡ Contradictions Found          │  ≡                  │   │
│  │  ☐           │  🔗 Cross-References              │  ≡                  │   │
│  │  ☑           │  ✓ Verification Summary           │  ≡                  │   │
│  │  ☐           │  📄 Document List                 │  ≡                  │   │
│  │  ☐           │  💬 Q&A Session Transcript        │  ≡                  │   │
│  │  ☐           │  📝 User Notes                    │  ≡                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  EXPORT FORMAT                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ● PDF (Formal report)                                                  │   │
│  │  ○ Word (.docx) - Editable                                              │   │
│  │  ○ PowerPoint (.pptx) - Presentation                                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  [◀ Cancel]                                      [Next: Review Sections ▶]     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 16.2 Export Builder - Section Review/Edit Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EXPORT BUILDER                                                         [✕]    │
│  Shah v. Mehta Securities Matter                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STEP 2 OF 3: REVIEW & EDIT SECTIONS                                           │
│                                                                                 │
│  ┌───────────────────────┐  ┌──────────────────────────────────────────────┐   │
│  │  SECTIONS             │  │  SECTION PREVIEW                             │   │
│  │  ─────────────        │  │  📋 EXECUTIVE SUMMARY                  [✎]  │   │
│  │  ▶ 📋 Executive Sum.. │  │  ─────────────────────────────────────────   │   │
│  │    👥 Parties         │  │                                              │   │
│  │    📅 Timeline        │  │  This matter involves a property attachment │   │
│  │    ⚖️ Citations       │  │  dispute under the Securities Act, 1992.   │   │
│  │    ⚡ Contradictions  │  │  The petitioner, Nirav D. Jobalia, seeks   │   │
│  │    ✓ Verification     │  │  release of attached securities held by    │   │
│  │                       │  │  the Custodian.                             │   │
│  │                       │  │                                              │   │
│  │                       │  │  **Key Facts:**                             │   │
│  │                       │  │  • Case filed: May 12, 2016                 │   │
│  │                       │  │  • Attachment order: June 10, 2018          │   │
│  │                       │  │  • Latest order: January 15, 2024           │   │
│  │                       │  │                                              │   │
│  │                       │  │  **Status:**                                │   │
│  │                       │  │  67% findings verified                      │   │
│  │                       │  │  3 contradictions pending review            │   │
│  │                       │  │                                              │   │
│  │  [+ Add Custom Section]│  │  [Edit Content]  [Remove Section]          │   │
│  └───────────────────────┘  └──────────────────────────────────────────────┘   │
│                                                                                 │
│  [◀ Back]                                              [Next: Preview ▶]       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 16.3 Export Builder - Edit Section Modal Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EDIT SECTION: Executive Summary                                        [✕]    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │  [B] [I] [U] [H1] [H2] [•] [1.] [Link] [Undo] [Redo]                     │ │
│  ├───────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                           │ │
│  │  This matter involves a property attachment dispute under the            │ │
│  │  Securities Act, 1992. The petitioner, Nirav D. Jobalia, seeks          │ │
│  │  release of attached securities held by the Custodian.                  │ │
│  │                                                                           │ │
│  │  **Key Facts:**                                                          │ │
│  │  • Case filed: May 12, 2016                                              │ │
│  │  • Attachment order: June 10, 2018                                       │ │
│  │  • Latest order: January 15, 2024                                        │ │
│  │                                                                           │ │
│  │  **Status:**                                                             │ │
│  │  67% findings verified                                                   │ │
│  │  3 contradictions pending review                                         │ │
│  │                                                                           │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ⚠️ Original AI-generated content is preserved separately.                    │
│  [Restore Original]                                                            │
│                                                                                 │
│                                              [Cancel]  [Save Changes]          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 16.4 Export Builder - Final Preview Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EXPORT BUILDER                                                         [✕]    │
│  Shah v. Mehta Securities Matter                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STEP 3 OF 3: PREVIEW & EXPORT                                                  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │                                                                     │ │ │
│  │  │                      SHAH V. MEHTA                                  │ │ │
│  │  │                   SECURITIES MATTER                                 │ │ │
│  │  │                                                                     │ │ │
│  │  │               Case Analysis Report                                  │ │ │
│  │  │               Generated: January 3, 2026                            │ │ │
│  │  │                                                                     │ │ │
│  │  │  ─────────────────────────────────────────────────────────────────  │ │ │
│  │  │                                                                     │ │ │
│  │  │  TABLE OF CONTENTS                                                  │ │ │
│  │  │                                                                     │ │ │
│  │  │  1. Executive Summary ............................ 2                │ │ │
│  │  │  2. Parties ...................................... 4                │ │ │
│  │  │  3. Timeline of Events ........................... 6                │ │ │
│  │  │  4. Citations .................................... 12               │ │ │
│  │  │  5. Contradictions Found ......................... 15               │ │ │
│  │  │  6. Verification Summary ......................... 18               │ │ │
│  │  │                                                                     │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                           │ │
│  │  Page 1 of 20                                [◀][▶]  [Zoom: −][+]       │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  Export as: [PDF ▼]   File name: [Shah_v_Mehta_Analysis_2026-01-03.pdf]       │
│                                                                                 │
│  [◀ Back]                                              [📥 Export Report]      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 16.5 Export Sections Available

| Section | Description | Content Source |
|---------|-------------|----------------|
| Executive Summary | AI-generated case overview | Summary Tab |
| Parties | List of parties with roles | Entities Tab |
| Timeline of Events | Chronological event list | Timeline Tab |
| Entity List | All persons/orgs/properties | Entities Tab |
| Citations | Legal citations with status | Citations Tab |
| Contradictions Found | Detected inconsistencies | Contradictions Tab |
| Cross-References | Document reference map | Cross-Ref system |
| Verification Summary | Verification stats + history | Verification Tab |
| Document List | All documents with metadata | Documents Tab |
| Q&A Session Transcript | Full chat history | Q&A Panel |
| User Notes | All user-added notes | Across tabs |
| Custom Section | User-written content | User input |

### 16.6 Export Formats

| Format | Icon | Use Case |
|--------|------|----------|
| PDF | 📄 | Formal court-ready document |
| Word | 📝 | Editable, collaborative |
| PowerPoint | 📊 | Presentations, summaries |

### 16.7 Editing Features

| Feature | Description |
|---------|-------------|
| Section toggle | Include/exclude any section |
| Drag reorder | Change section order |
| Edit content | Rich text editor for modifications |
| Restore original | Reset to AI-generated content |
| Add custom | Insert user-written sections |
| Remove section | Delete from export |

### 16.8 Export Options

| Option | Description |
|--------|-------------|
| Include citations | Show document source references |
| Include page numbers | Add page numbers to PDF |
| Include TOC | Generate table of contents |
| Include verification status | Show ✓/⏳/⚠️ status |
| Add cover page | Include title page |
| Add LDIP watermark | Generated with LDIP |

### 16.9 Export History

| Decision | Exports are saved and accessible from matter workspace |
|----------|-------------------------------------------------------|
| Access | Documents Tab → Exports folder |
| Naming | Auto-named with date: Matter_Analysis_YYYY-MM-DD.pdf |
| Versions | Multiple exports saved, latest on top |

---

## 17. UX Design Complete

All pages and components have been detailed:

- [x] Dashboard / Home
- [x] Upload & Processing
- [x] Matter Workspace - Summary Tab
- [x] Matter Workspace - Timeline Tab
- [x] Cross-Referencing
- [x] Matter Workspace - Entities Tab
- [x] Matter Workspace - Citations Tab
- [x] Matter Workspace - Contradictions Tab
- [x] Matter Workspace - Verification Tab
- [x] Matter Workspace - Documents Tab
- [x] Q&A Panel
- [x] PDF Viewer
- [x] Export Builder

### 17.1 Open Questions

| Question | Status | Notes |
|----------|--------|-------|
| Mobile responsiveness | Not discussed | Dashboard adapts; workspace TBD |
| Keyboard shortcuts | Not discussed | Power user feature |
| Dark mode | Not discussed | User preference |
| Collaboration features | Mentioned | Share button exists; multi-user TBD |
| Offline support | Not discussed | Legal requirements may need this |

---

## 18. Micro-Interactions

### 18.1 Global Animation Principles

| Decision | Subtle, purposeful animations that don't slow down power users |
|----------|---------------------------------------------------------------|
| Duration | Fast: 150ms, Normal: 250ms, Slow: 400ms |
| Easing | ease-out for entrances, ease-in for exits |
| Reduce motion | Respect prefers-reduced-motion; disable non-essential animations |

### 18.2 Loading States

```
┌─────────────────────────────────────────────────────────────┐
│  SKELETON LOADING (Content areas)                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ████████████████████░░░░░░░░░░  ← Shimmer animation        │
│  ████████████░░░░░░░░░░░░░░░░░░    (subtle pulse)           │
│  ████████████████░░░░░░░░░░░░░░                             │
│                                                             │
│  Shape matches expected content layout                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SPINNER LOADING (Actions/Operations)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│     ◠ ← Rotating spinner (for buttons, small areas)         │
│                                                             │
│  [  ◠  Saving...  ]  ← Button with inline spinner           │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PROGRESS LOADING (Long operations)                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Processing documents...                                    │
│  ████████████████░░░░░░░░░░░░░░░░░░░░  45%                  │
│                                                             │
│  Stage: Extracting citations (3 of 5)                       │
│  Estimated time: ~2 minutes remaining                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| Loading Type | Use Case | Duration Threshold |
|--------------|----------|-------------------|
| Skeleton | Page/section content | > 300ms |
| Spinner | Button actions, small updates | > 150ms |
| Progress bar | File uploads, processing | > 2 seconds |
| Inline text | "Saving...", "Loading..." | > 500ms |

### 18.3 Button Interactions

```
┌─────────────────────────────────────────────────────────────┐
│  BUTTON STATES                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Default:    [ Upload Files ]     ← Normal state            │
│                                                             │
│  Hover:      [ Upload Files ]     ← Slight lift + shadow    │
│              ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔        150ms transition        │
│                                                             │
│  Active:     [ Upload Files ]     ← Scale down 98%          │
│              pressed feeling        Immediate feedback       │
│                                                             │
│  Loading:    [  ◠  Uploading ]    ← Spinner + text change   │
│                                     Disabled state           │
│                                                             │
│  Success:    [  ✓  Uploaded  ]    ← Green flash, then reset │
│                                     2s before reset          │
│                                                             │
│  Disabled:   [ Upload Files ]     ← 50% opacity             │
│              (grayed out)           cursor: not-allowed      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.4 Card & List Item Interactions

```
┌─────────────────────────────────────────────────────────────┐
│  MATTER CARD HOVER                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Default:                          Hover:                   │
│  ┌────────────────────┐            ┌────────────────────┐   │
│  │ Smith v. Jones     │            │ Smith v. Jones   ↗ │   │
│  │ 45 documents       │    →       │ 45 documents       │   │
│  │ Updated 2h ago     │            │ Updated 2h ago     │   │
│  └────────────────────┘            └────────────────────┘   │
│                                    ↑ Elevated shadow        │
│                                    ↑ Reveal action icon     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  LIST ITEM SELECTION                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ○ Citation from Exhibit A, p.12        ← Unselected        │
│  ● Citation from Deposition, p.45       ← Selected (filled) │
│    └── Left border accent + background tint                 │
│  ○ Citation from Contract, p.3          ← Unselected        │
│                                                             │
│  Transition: 150ms background + border                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.5 Panel & Modal Transitions

```
┌─────────────────────────────────────────────────────────────┐
│  SIDE PANEL OPEN (Q&A Panel, Detail panels)                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Frame 1:         Frame 2:         Frame 3:                 │
│  ┌──────────┐     ┌──────────┬──┐  ┌──────────┬─────┐       │
│  │          │     │          │░░│  │          │     │       │
│  │  Content │  →  │  Content │░░│  │  Content │Panel│       │
│  │          │     │          │░░│  │          │     │       │
│  └──────────┘     └──────────┴──┘  └──────────┴─────┘       │
│                                                             │
│  Animation: Slide in from right, 250ms ease-out             │
│  Content area: Compress smoothly (not jump)                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  MODAL OPEN                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Frame 1:              Frame 2:              Frame 3:       │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  │              │      │  ░░░░░░░░░░  │      │  ░░░░░░░░░░  │
│  │   Content    │  →   │  ░┌──────┐░  │  →   │  ░┌──────┐░  │
│  │              │      │  ░│      │░  │      │  ░│ Full │░  │
│  └──────────────┘      │  ░└──────┘░  │      │  ░│Modal │░  │
│                        └──────────────┘      │  ░└──────┘░  │
│                                              └──────────────┘
│                                                             │
│  Animation: Fade backdrop (150ms) + Scale modal 95%→100%    │
│  Focus trap: First focusable element                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.6 Drag & Drop Feedback

```
┌─────────────────────────────────────────────────────────────┐
│  FILE UPLOAD DROP ZONE                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Default:                    Drag Over:                     │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐      ╔═══════════════════════╗      │
│  │                    │      ║  ████████████████████ ║      │
│  │   📁 Drop files    │  →   ║  ██ Drop to upload ██ ║      │
│  │      here          │      ║  ████████████████████ ║      │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘      ╚═══════════════════════╝      │
│                              ↑ Dashed → Solid border        │
│                              ↑ Background highlight         │
│                              ↑ Pulsing animation            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  EXPORT SECTION REORDER                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ⋮⋮ Timeline Summary        ← Grabbing cursor on hover      │
│  ────────────────────                                       │
│  ⋮⋮ │ Key Entities │        ← Being dragged (elevated)      │
│     └──────────────┘          Ghost at 50% opacity          │
│  ────────────────────        ← Drop indicator line          │
│  ⋮⋮ Citation Analysis                                       │
│  ⋮⋮ Contradictions Found                                    │
│                                                             │
│  Animation: Item follows cursor, others animate apart       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.7 Toast Notifications

```
┌─────────────────────────────────────────────────────────────┐
│  TOAST POSITIONS & TYPES                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Position: Bottom-right corner (above Q&A if open)          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │                                                     │    │
│  │                                                     │    │
│  │                                    ┌──────────────┐ │    │
│  │                                    │ ✓ Saved      │ │    │
│  │                                    └──────────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Types:                                                     │
│  ┌──────────────────────┐  Success (green accent)           │
│  │ ✓ Changes saved      │  Auto-dismiss: 3 seconds          │
│  └──────────────────────┘                                   │
│                                                             │
│  ┌──────────────────────┐  Info (blue accent)               │
│  │ ℹ Processing started │  Auto-dismiss: 4 seconds          │
│  └──────────────────────┘                                   │
│                                                             │
│  ┌──────────────────────┐  Warning (yellow accent)          │
│  │ ⚠ Low confidence     │  Auto-dismiss: 5 seconds          │
│  └──────────────────────┘                                   │
│                                                             │
│  ┌──────────────────────────────┐  Error (red accent)       │
│  │ ✕ Upload failed       [Retry]│  Manual dismiss required  │
│  └──────────────────────────────┘                           │
│                                                             │
│  Animation: Slide up + fade in (250ms)                      │
│  Stack: Max 3 visible, older ones collapse                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.8 Form Input Interactions

```
┌─────────────────────────────────────────────────────────────┐
│  TEXT INPUT STATES                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Default:     ┌─────────────────────────┐                   │
│               │ Matter name             │  ← Placeholder    │
│               └─────────────────────────┘    (muted text)   │
│                                                             │
│  Focus:       ┌─────────────────────────┐                   │
│               │ Smith v. Jones█         │  ← Blue border    │
│               └─────────────────────────┘    Label floats   │
│               Matter name                    up (animated)  │
│                                                             │
│  Error:       ┌─────────────────────────┐                   │
│               │ Smith                   │  ← Red border     │
│               └─────────────────────────┘                   │
│               ⚠ Matter name is required     Error below     │
│                                                             │
│  Success:     ┌─────────────────────────┐                   │
│               │ Smith v. Jones        ✓ │  ← Green check    │
│               └─────────────────────────┘    (validated)    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.9 Highlight & Focus Indicators

```
┌─────────────────────────────────────────────────────────────┐
│  PDF CITATION HIGHLIGHT                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Click citation → PDF scrolls → Highlight pulses            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ ...testimony on record. According to the deposition │    │
│  │ ╔═══════════════════════════════════════════════════╗    │
│  │ ║ "The meeting occurred on January 15th at 3pm"    ║    │
│  │ ╚═══════════════════════════════════════════════════╝    │
│  │ This contradicts the earlier statement made in...   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Animation sequence:                                        │
│  1. Scroll to position (400ms ease-out)                     │
│  2. Flash highlight yellow (200ms)                          │
│  3. Settle to subtle yellow background                      │
│  4. Fade after 3 seconds (or on scroll away)                │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ENTITY GRAPH NODE FOCUS                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Hover on entity → Connected nodes highlight                │
│                                                             │
│          ○───○                    ◉═══◉                     │
│         /     \        →         ╱     ╲                    │
│        ○       ●                ○       ◉                   │
│         \     /                  \     ╱                    │
│          ○───○                    ○═══◉                     │
│                                                             │
│  ●/◉ = Hovered/Connected (highlighted)                      │
│  ○ = Unconnected (dimmed to 30% opacity)                    │
│                                                             │
│  Transition: 200ms for opacity changes                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.10 Verification Actions

```
┌─────────────────────────────────────────────────────────────┐
│  VERIFY/REJECT BUTTON FEEDBACK                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Before:  [ ✓ Verify ]  [ ✕ Reject ]  [ ? Flag ]            │
│                                                             │
│  Click Verify:                                              │
│  [ ✓ ════════ ]  ← Green fills left to right (300ms)        │
│  [ ✓ Verified! ]  ← Text changes, checkmark bounces         │
│                                                             │
│  Then:                                                      │
│  Card slides out (250ms) → Next item slides in              │
│  Toast: "Citation verified. 12 remaining."                  │
│                                                             │
│  Click Reject:                                              │
│  ┌────────────────────────────────┐                         │
│  │ Rejection reason:              │  ← Modal appears        │
│  │ ○ Incorrect citation           │                         │
│  │ ○ Page number wrong            │                         │
│  │ ○ Quote inaccurate             │                         │
│  │ ○ Other: _______________       │                         │
│  │              [Cancel] [Reject] │                         │
│  └────────────────────────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 18.11 Progress & Completion

```
┌─────────────────────────────────────────────────────────────┐
│  PROCESSING COMPLETION CELEBRATION                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Stage 5 complete → Brief celebration moment                │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │              ✓ Processing Complete!                 │    │
│  │                                                     │    │
│  │         ✓────✓────✓────✓────✓                       │    │
│  │        Doc  Time Cite  Cont  Gap                    │    │
│  │                                                     │    │
│  │    45 documents · 234 citations · 12 issues         │    │
│  │                                                     │    │
│  │              [ View Analysis → ]                    │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Animation:                                                 │
│  1. Checkmarks appear sequentially (100ms each)             │
│  2. Numbers count up (500ms total)                          │
│  3. Subtle confetti particles (optional, 1 second)          │
│  4. Button pulses once to draw attention                    │
│                                                             │
│  Note: Keep celebration brief - lawyers are busy            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 19. Error States

### 19.1 Error Design Principles

| Principle | Description |
|-----------|-------------|
| Be specific | Tell users exactly what went wrong, not just "Error occurred" |
| Offer solutions | Always provide a clear action to resolve or retry |
| Preserve work | Never lose user's data on error; auto-save where possible |
| Graceful degradation | If a feature fails, rest of app should work |
| Appropriate tone | Professional but human; no blame language |

### 19.2 File Upload Errors

```
┌─────────────────────────────────────────────────────────────┐
│  UNSUPPORTED FILE TYPE                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Can't upload "document.xlsx"                   │    │
│  │                                                     │    │
│  │  LDIP supports PDF files only.                      │    │
│  │                                                     │    │
│  │  Tip: Convert your Excel file to PDF first, or      │    │
│  │  print it as PDF from Excel.                        │    │
│  │                                                     │    │
│  │                              [ Try Different File ] │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Supported formats shown: .pdf                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  FILE TOO LARGE                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  "LargeExhibit.pdf" is too large (256 MB)       │    │
│  │                                                     │    │
│  │  Maximum file size is 100 MB per document.          │    │
│  │                                                     │    │
│  │  Try splitting into smaller files, or contact       │    │
│  │  support for enterprise limits.                     │    │
│  │                                                     │    │
│  │         [ Split PDF Tool ]  [ Contact Support ]     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CORRUPTED / UNREADABLE FILE                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ✕  Can't read "Exhibit_A.pdf"                      │    │
│  │                                                     │    │
│  │  This file appears to be corrupted or password-     │    │
│  │  protected.                                         │    │
│  │                                                     │    │
│  │  What to try:                                       │    │
│  │  • Re-export the PDF from the source application    │    │
│  │  • Remove password protection                       │    │
│  │  • Try a different version of the file              │    │
│  │                                                     │    │
│  │                  [ Try Again ]  [ Skip This File ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PARTIAL UPLOAD FAILURE                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Uploading 12 files...                                      │
│                                                             │
│  ✓ Exhibit_A.pdf                    Uploaded                │
│  ✓ Exhibit_B.pdf                    Uploaded                │
│  ✕ Exhibit_C.pdf                    Failed - Retry?         │
│  ◠ Exhibit_D.pdf                    Uploading...            │
│  ○ Exhibit_E.pdf                    Pending                 │
│  ...                                                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1 file failed. Upload will continue with others.   │    │
│  │                        [ Retry Failed ]  [ Skip ]   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.3 Processing Errors

```
┌─────────────────────────────────────────────────────────────┐
│  PROCESSING STAGE FAILURE                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Processing: Smith v. Jones                                 │
│                                                             │
│  ✓ Document Extraction                 Complete             │
│  ✓ Timeline Construction               Complete             │
│  ✕ Citation Verification               Failed               │
│  ○ Consistency Analysis                Waiting              │
│  ○ Gap Detection                       Waiting              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Citation verification encountered an issue     │    │
│  │                                                     │    │
│  │  We couldn't process some citations in Exhibit_B.   │    │
│  │  You can:                                           │    │
│  │                                                     │    │
│  │  • Retry this stage (may resolve temporary issues)  │    │
│  │  • Skip and continue (some citations may be missing)│    │
│  │  • Contact support if problem persists              │    │
│  │                                                     │    │
│  │     [ Retry Stage ]  [ Skip & Continue ]  [ Help ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PROCESSING TIMEOUT                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⏱️  Processing is taking longer than expected       │    │
│  │                                                     │    │
│  │  Your 2,000-page matter is complex. Processing      │    │
│  │  continues in the background.                       │    │
│  │                                                     │    │
│  │  You'll receive an email when it's ready, or you    │    │
│  │  can check back later.                              │    │
│  │                                                     │    │
│  │  Estimated completion: ~15 minutes                  │    │
│  │                                                     │    │
│  │          [ Notify Me ]  [ Continue Waiting ]        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.4 Network & Connection Errors

```
┌─────────────────────────────────────────────────────────────┐
│  OFFLINE STATE                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  📡  You're offline                                 │    │
│  │                                                     │    │
│  │  Can't connect to LDIP. Check your internet         │    │
│  │  connection and try again.                          │    │
│  │                                                     │    │
│  │  Your unsaved work is preserved locally.            │    │
│  │                                                     │    │
│  │                              [ Retry Connection ]   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Banner appears at top of page until reconnected           │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CONNECTION LOST MID-ACTION                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Connection lost                                │    │
│  │                                                     │    │
│  │  Your verification changes couldn't be saved.       │    │
│  │                                                     │    │
│  │  Don't worry - we'll retry automatically when       │    │
│  │  you're back online.                                │    │
│  │                                                     │    │
│  │  Pending: 3 verifications                           │    │
│  │                                                     │    │
│  │                    [ Retry Now ]  [ Work Offline ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  API/SERVER ERROR                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ✕  Something went wrong on our end                 │    │
│  │                                                     │    │
│  │  We couldn't complete your request. Our team has    │    │
│  │  been notified.                                     │    │
│  │                                                     │    │
│  │  Error ID: ERR-2026-0103-XYZ                        │    │
│  │  (Share this with support if needed)                │    │
│  │                                                     │    │
│  │       [ Try Again ]  [ Go to Dashboard ]  [ Help ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.5 Q&A / AI Errors

```
┌─────────────────────────────────────────────────────────────┐
│  AI RESPONSE FAILURE                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  You: What was the timeline of events?                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Couldn't generate a response                   │    │
│  │                                                     │    │
│  │  The AI assistant is temporarily unavailable.       │    │
│  │  Your question has been saved.                      │    │
│  │                                                     │    │
│  │             [ Retry ]  [ Ask Different Question ]   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  INSUFFICIENT CONTEXT                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  You: What did John say about the meeting?                  │
│                                                             │
│  AI: I found multiple people named "John" in this matter:   │
│                                                             │
│      • John Smith (Plaintiff)                               │
│      • John Davis (Witness)                                 │
│      • John Martinez (Attorney)                             │
│                                                             │
│      Which John are you asking about?                       │
│                                                             │
│      [ John Smith ]  [ John Davis ]  [ John Martinez ]      │
│                                                             │
│  Note: This is handled gracefully, not as an error          │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  NO RESULTS FOUND                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  You: What happened in the Seattle office?                  │
│                                                             │
│  AI: I couldn't find any references to a "Seattle office"   │
│      in the uploaded documents.                             │
│                                                             │
│      Did you mean:                                          │
│      • Portland office (mentioned 12 times)                 │
│      • San Francisco office (mentioned 8 times)             │
│                                                             │
│      Or try rephrasing your question.                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.6 PDF Viewer Errors

```
┌─────────────────────────────────────────────────────────────┐
│  PDF LOAD FAILURE                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │                   📄                                │    │
│  │                                                     │    │
│  │          Can't display this document                │    │
│  │                                                     │    │
│  │   The PDF viewer encountered an issue loading       │    │
│  │   "Exhibit_A.pdf"                                   │    │
│  │                                                     │    │
│  │   [ Reload ]  [ Download Original ]  [ Report ]    │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CITATION NOT FOUND IN PDF                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Can't locate citation                          │    │
│  │                                                     │    │
│  │  The exact text couldn't be found on page 45.       │    │
│  │  The document may have been updated since           │    │
│  │  processing.                                        │    │
│  │                                                     │    │
│  │  Showing page 45 - you can search manually.         │    │
│  │                                                     │    │
│  │         [ Go to Page 45 ]  [ Re-process Document ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.7 Export Errors

```
┌─────────────────────────────────────────────────────────────┐
│  EXPORT GENERATION FAILURE                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ✕  Export couldn't be generated                    │    │
│  │                                                     │    │
│  │  There was a problem creating your PDF report.      │    │
│  │                                                     │    │
│  │  Your selections have been saved - try again or     │    │
│  │  export a smaller section.                          │    │
│  │                                                     │    │
│  │          [ Retry Full Export ]  [ Export Summary ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  WORD EXPORT LIMITATION                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Word export has limitations                    │    │
│  │                                                     │    │
│  │  Some visual elements won't appear correctly in     │    │
│  │  Word format:                                       │    │
│  │  • Entity relationship graphs                       │    │
│  │  • Interactive timeline                             │    │
│  │                                                     │    │
│  │  For best results, use PDF export.                  │    │
│  │                                                     │    │
│  │        [ Continue with Word ]  [ Switch to PDF ]    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.8 Validation & Form Errors

```
┌─────────────────────────────────────────────────────────────┐
│  MATTER CREATION VALIDATION                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Create New Matter                                          │
│                                                             │
│  Matter Name *                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│  ⚠ Matter name is required                                  │
│                                                             │
│  Client Name                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Acme Corp @ Special!                                │    │
│  └─────────────────────────────────────────────────────┘    │
│  ⚠ Client name contains invalid characters (@ !)            │
│                                                             │
│  Case Number                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2024-CV-00123                                    ✓  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│                              [ Cancel ]  [ Create ] (dim)   │
│                                                             │
│  Note: Submit button stays disabled until errors fixed      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.9 Entity Merge Errors

```
┌─────────────────────────────────────────────────────────────┐
│  MERGE CONFLICT                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Can't merge these entities                     │    │
│  │                                                     │    │
│  │  "John Smith" and "Jane Smith" have conflicting     │    │
│  │  properties that suggest they're different people:  │    │
│  │                                                     │    │
│  │  • Different roles: Plaintiff vs Witness            │    │
│  │  • Different companies: Acme vs Beta Corp           │    │
│  │                                                     │    │
│  │  Are you sure these are the same person?            │    │
│  │                                                     │    │
│  │          [ Cancel ]  [ Merge Anyway ]               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 19.10 Error Recovery Summary

| Error Type | Auto-Retry | User Action | Data Loss |
|------------|------------|-------------|-----------|
| Network timeout | Yes (3x) | Manual retry after | None |
| Upload failure | No | Retry or skip | File only |
| Processing failure | Yes (1x) | Retry stage or skip | Partial |
| AI response failure | Yes (2x) | Retry or rephrase | None |
| PDF load failure | Yes (1x) | Reload or download | None |
| Export failure | No | Retry or reduce scope | None |
| Validation error | N/A | Fix and resubmit | None |
| Server error | Yes (2x) | Wait and retry | None |

---

## 20. Edge Cases

### 20.1 Empty States

```
┌─────────────────────────────────────────────────────────────┐
│  NO MATTERS YET (New User)                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │                    📁                               │    │
│  │                                                     │    │
│  │         Welcome to LDIP, Juhi!                      │    │
│  │                                                     │    │
│  │   Get started by uploading documents for your       │    │
│  │   first matter. We'll analyze them and help you     │    │
│  │   find key insights.                                │    │
│  │                                                     │    │
│  │           [ Start Your First Matter → ]             │    │
│  │                                                     │    │
│  │   📖 Take a quick tour (2 min)                      │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  NO SEARCH RESULTS                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Search: "arbitration clause"                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │                    🔍                               │    │
│  │                                                     │    │
│  │   No results for "arbitration clause"               │    │
│  │                                                     │    │
│  │   Suggestions:                                      │    │
│  │   • Check spelling                                  │    │
│  │   • Try broader terms like "arbitration"            │    │
│  │   • Search in a different tab                       │    │
│  │                                                     │    │
│  │   Related terms found:                              │    │
│  │   • "mediation" (15 mentions)                       │    │
│  │   • "dispute resolution" (8 mentions)               │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  NO CONTRADICTIONS FOUND                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Contradictions Tab                                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │                    ✓                                │    │
│  │                                                     │    │
│  │   No contradictions detected                        │    │
│  │                                                     │    │
│  │   All statements in your documents appear           │    │
│  │   consistent with each other.                       │    │
│  │                                                     │    │
│  │   Note: This doesn't mean there are none -          │    │
│  │   complex contradictions may need manual review.    │    │
│  │                                                     │    │
│  │              [ Review All Statements ]              │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  NO ENTITIES IN CATEGORY                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Entities Tab → Filter: Organizations                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │   No organizations found                            │    │
│  │                                                     │    │
│  │   Try a different filter or view all entities.      │    │
│  │                                                     │    │
│  │   [ View All Entities ]  [ Clear Filters ]          │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  EMPTY VERIFICATION QUEUE                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Verification Tab                                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                                                     │    │
│  │                    🎉                               │    │
│  │                                                     │    │
│  │   All caught up!                                    │    │
│  │                                                     │    │
│  │   You've verified all items that need review.       │    │
│  │                                                     │    │
│  │   234 total · 230 verified · 4 rejected             │    │
│  │                                                     │    │
│  │   [ View History ]  [ Export Verification Report ]  │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.2 Extreme Data Volumes

```
┌─────────────────────────────────────────────────────────────┐
│  VERY LARGE MATTER (2000+ pages)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Handling:                                                  │
│  • Progressive loading: Load first 100 items, then pages    │
│  • Virtual scrolling: Only render visible items             │
│  • Background processing: Email when complete               │
│  • Summary first: Show aggregated stats before details      │
│                                                             │
│  Timeline Tab (5000+ events):                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Showing 1-100 of 5,234 events                      │    │
│  │  [ Load More ] or zoom out to see clusters          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Entity Graph (500+ nodes):                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Large graph detected. Showing key entities only.   │    │
│  │  Use filters to explore specific relationships.     │    │
│  │  [ Show All (may be slow) ]  [ Keep Filtered ]      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  VERY LONG DOCUMENT NAMES                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Truncation rules:                                          │
│  • Card titles: 40 chars + "..."                            │
│  • List items: 60 chars + "..."                             │
│  • Hover tooltip: Full name shown                           │
│  • File names: Truncate middle, keep extension              │
│                                                             │
│  Examples:                                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Exhibit_A_Deposition_of_John_Smit...nuary_2024.pdf  │    │
│  │ ──────────────────────────────────────────────────  │    │
│  │ Hover shows:                                        │    │
│  │ Exhibit_A_Deposition_of_John_Smith_Taken_On_       │    │
│  │ January_15_2024_With_Corrections_Final_v2.pdf       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  MANY FILES AT ONCE (50+ uploads)                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Uploading 127 files                                │    │
│  │                                                     │    │
│  │  ████████████░░░░░░░░░░░░░░░░░░░░  34/127 (27%)    │    │
│  │                                                     │    │
│  │  Currently: Exhibit_45.pdf                          │    │
│  │  Speed: 2.3 MB/s                                    │    │
│  │  Remaining: ~8 minutes                              │    │
│  │                                                     │    │
│  │  ▼ Show details (3 failed)                          │    │
│  │                                                     │    │
│  │                    [ Pause ]  [ Cancel All ]        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Note: Collapsed view for many files; expandable details    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.3 Special Content Scenarios

```
┌─────────────────────────────────────────────────────────────┐
│  SCANNED / IMAGE-BASED PDFs                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Processing: Handwritten_Notes.pdf                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ℹ️  This appears to be a scanned document          │    │
│  │                                                     │    │
│  │  OCR (text extraction) is being performed.          │    │
│  │  Results may be less accurate for:                  │    │
│  │  • Handwritten text                                 │    │
│  │  • Poor quality scans                               │    │
│  │  • Non-English text                                 │    │
│  │                                                     │    │
│  │  Confidence: Medium (72%)                           │    │
│  │                                                     │    │
│  │  You may need to verify extracted text manually.    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  NON-ENGLISH CONTENT                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  🌐  Non-English content detected                   │    │
│  │                                                     │    │
│  │  Documents contain text in: Spanish, French         │    │
│  │                                                     │    │
│  │  Analysis will proceed, but:                        │    │
│  │  • Entity names may have variations                 │    │
│  │  • Date formats may differ                          │    │
│  │  • Some citations may not parse correctly           │    │
│  │                                                     │    │
│  │  [ Continue ]  [ Translate First (external) ]       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  DOCUMENT WITH NO EXTRACTABLE TEXT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Can't extract text from "Photo_Evidence.pdf"   │    │
│  │                                                     │    │
│  │  This file appears to be images only (photographs,  │    │
│  │  diagrams, or charts).                              │    │
│  │                                                     │    │
│  │  It will be included in your matter but won't       │    │
│  │  appear in text searches or analysis.               │    │
│  │                                                     │    │
│  │  You can still view and reference it manually.      │    │
│  │                                                     │    │
│  │               [ Include Anyway ]  [ Skip ]          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  DUPLICATE DOCUMENT DETECTED                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  📄  Possible duplicate found                       │    │
│  │                                                     │    │
│  │  "Contract_v2.pdf" appears similar to:              │    │
│  │  "Contract_Final.pdf" (uploaded 2 days ago)         │    │
│  │                                                     │    │
│  │  Similarity: 94%                                    │    │
│  │                                                     │    │
│  │  What would you like to do?                         │    │
│  │                                                     │    │
│  │  [ Keep Both ]  [ Replace Old ]  [ Skip New ]       │    │
│  │                                                     │    │
│  │  [ Compare Side by Side ]                           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.4 Timeline Edge Cases

```
┌─────────────────────────────────────────────────────────────┐
│  EVENTS WITH SAME DATE/TIME                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Jan 15, 2024 3:00 PM                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ● 3 events at this time                            │    │
│  │                                                     │    │
│  │    ├─ Meeting at headquarters                       │    │
│  │    ├─ Email sent to legal team                      │    │
│  │    └─ Phone call with client                        │    │
│  │                                                     │    │
│  │  Click to expand individual events                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  AMBIGUOUS / PARTIAL DATES                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Document states: "sometime in early 2023"                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  📅  Approximate date: Q1 2023                      │    │
│  │                                                     │    │
│  │  This event has an uncertain date.                  │    │
│  │  Shown as a range on the timeline.                  │    │
│  │                                                     │    │
│  │  ════════●═══════════════════════════               │    │
│  │  Jan    Feb    Mar    Apr    May                    │    │
│  │                                                     │    │
│  │  [ Set Specific Date ]  [ Keep Approximate ]        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  DATE RANGE SPANNING LONG PERIOD                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Events span: 1995 to 2024 (29 years)                       │
│                                                             │
│  Default zoom: Year view (most useful)                      │
│  Available: Day | Week | Month | Year | Decade              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Large date range detected. Showing year clusters.  │    │
│  │                                                     │    │
│  │  1995-2000: 12 events                               │    │
│  │  2001-2010: 45 events                               │    │
│  │  2011-2020: 89 events                               │    │
│  │  2021-2024: 234 events ← Most activity             │    │
│  │                                                     │    │
│  │              [ Jump to: 2021-2024 ]                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  FUTURE DATES IN DOCUMENTS                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  📅  Future date found: March 15, 2025              │    │
│  │                                                     │    │
│  │  "Contract expires March 15, 2025"                  │    │
│  │                                                     │    │
│  │  Future events shown in timeline with dashed        │    │
│  │  styling to distinguish from past events.           │    │
│  │                                                     │    │
│  │  ──●───●───●── ┆ ┆ ┆ - - ◇ - -                      │    │
│  │  Past events   │ │ Future                           │    │
│  │               Today                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.5 Entity Edge Cases

```
┌─────────────────────────────────────────────────────────────┐
│  SAME NAME, DIFFERENT PEOPLE                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  👥  Multiple "John Smith" found                    │    │
│  │                                                     │    │
│  │  We detected 3 different people named John Smith:   │    │
│  │                                                     │    │
│  │  1. John Smith (Plaintiff)                          │    │
│  │     → CEO of Acme Corp, age 54                      │    │
│  │                                                     │    │
│  │  2. John Smith (Witness)                            │    │
│  │     → Accountant, mentioned in Exhibit B            │    │
│  │                                                     │    │
│  │  3. John Smith (mentioned)                          │    │
│  │     → No additional context available               │    │
│  │                                                     │    │
│  │  [ Keep Separate ]  [ Merge 1 & 2 ]  [ Review All ] │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ENTITY WITH MANY ALIASES                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Entity: Acme Corporation                                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Known aliases (12):                                │    │
│  │                                                     │    │
│  │  • Acme Corp                                        │    │
│  │  • Acme Corporation                                 │    │
│  │  • ACME Inc.                                        │    │
│  │  • Acme Industries                                  │    │
│  │  • The Company                                      │    │
│  │  + 7 more...                                        │    │
│  │                                                     │    │
│  │  Primary display: Acme Corporation                  │    │
│  │                                                     │    │
│  │  [ Edit Aliases ]  [ Change Primary ]               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  UNRESOLVED ENTITY REFERENCE                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Document mentions: "the defendant"                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ❓  Unresolved reference: "the defendant"          │    │
│  │                                                     │    │
│  │  This term appears 45 times but isn't linked        │    │
│  │  to a specific entity.                              │    │
│  │                                                     │    │
│  │  Who does "the defendant" refer to?                 │    │
│  │                                                     │    │
│  │  ○ John Smith                                       │    │
│  │  ○ Acme Corporation                                 │    │
│  │  ○ Multiple defendants (don't link)                 │    │
│  │  ○ Create new entity                                │    │
│  │                                                     │    │
│  │              [ Apply to All ]  [ Review Each ]      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.6 Citation Edge Cases

```
┌─────────────────────────────────────────────────────────────┐
│  CITATION TO NON-UPLOADED DOCUMENT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Citation: "See Exhibit J, page 45"                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  External reference detected                    │    │
│  │                                                     │    │
│  │  "Exhibit J" is referenced but not in your          │    │
│  │  uploaded documents.                                │    │
│  │                                                     │    │
│  │  [ Upload Exhibit J ]  [ Mark as External ]         │    │
│  │  [ Ignore This Citation ]                           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  AMBIGUOUS PAGE REFERENCE                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Citation: "page 12"                                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ❓  Which document?                                │    │
│  │                                                     │    │
│  │  "Page 12" could refer to:                          │    │
│  │                                                     │    │
│  │  ○ Deposition_Smith.pdf (most likely based on       │    │
│  │    surrounding context)                             │    │
│  │  ○ Contract_2024.pdf                                │    │
│  │  ○ Exhibit_A.pdf                                    │    │
│  │                                                     │    │
│  │              [ Select ]  [ Skip ]                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CITATION WITH PAGE RANGE                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Citation: "Exhibit A, pages 45-52"                         │
│                                                             │
│  Display in PDF viewer:                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Showing pages 45-52                                │    │
│  │                                                     │    │
│  │  ◀ 45  [46]  47  48  49  50  51  52 ▶              │    │
│  │                                                     │    │
│  │  [ View All 8 Pages ]  [ View First Page Only ]     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.7 Q&A Edge Cases

```
┌─────────────────────────────────────────────────────────────┐
│  VERY LONG QUESTION                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Type your question...                              │    │
│  │  ───────────────────────────────────────────────    │    │
│  │  Can you provide me with a comprehensive analysis   │    │
│  │  of all the meetings that John Smith attended       │    │
│  │  between January and March 2024, including the      │    │
│  │  dates, participants, topics discussed, and any     │    │
│  │  decisions that were made, and also cross-reference │    │
│  │  these with the email communications...             │    │
│  │  [▼ Expand to see full question]                    │    │
│  │  ───────────────────────────────────────────────    │    │
│  │  1,247 / 2,000 characters                           │    │
│  │                                                     │    │
│  │  Tip: Long questions may take longer to process.    │    │
│  │  Consider breaking into smaller questions.          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  QUESTION OUTSIDE DOCUMENT SCOPE                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  You: What is the capital of France?                        │
│                                                             │
│  AI: I can only answer questions about the documents in     │
│      this matter (Smith v. Jones).                          │
│                                                             │
│      Your question doesn't appear to be related to the      │
│      uploaded documents.                                    │
│                                                             │
│      Try asking about:                                      │
│      • Events in the timeline                               │
│      • People or organizations mentioned                    │
│      • Specific document contents                           │
│                                                             │
│      [ Suggested: "Who are the key people in this case?" ]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  QUESTION REQUIRING LEGAL ADVICE                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  You: Should I sue the defendant?                           │
│                                                             │
│  AI: I can help you find and analyze information in your    │
│      documents, but I can't provide legal advice.           │
│                                                             │
│      I can help you with:                                   │
│      • Summarizing key facts from documents                 │
│      • Finding relevant citations                           │
│      • Identifying contradictions or gaps                   │
│                                                             │
│      For legal strategy questions, please consult with      │
│      your supervising attorney.                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.8 Browser & Session Edge Cases

```
┌─────────────────────────────────────────────────────────────┐
│  SESSION TIMEOUT                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⏱️  Session expiring soon                          │    │
│  │                                                     │    │
│  │  Your session will expire in 5 minutes due to       │    │
│  │  inactivity.                                        │    │
│  │                                                     │    │
│  │  Your work is auto-saved, but you'll need to log    │    │
│  │  in again to continue.                              │    │
│  │                                                     │    │
│  │           [ Stay Logged In ]  [ Log Out Now ]       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Shows at 5min, 2min, 1min before timeout                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CONCURRENT SESSION (another tab/device)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ℹ️  Matter opened elsewhere                        │    │
│  │                                                     │    │
│  │  This matter is open in another browser tab or      │    │
│  │  device.                                            │    │
│  │                                                     │    │
│  │  Changes made here will sync automatically, but     │    │
│  │  you may see updates from the other session.        │    │
│  │                                                     │    │
│  │                              [ OK, Got It ]         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BROWSER BACK BUTTON                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User clicks back while on Export Builder with selections   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Leave Export Builder?                          │    │
│  │                                                     │    │
│  │  You have unsaved export selections.                │    │
│  │                                                     │    │
│  │  • 8 sections selected                              │    │
│  │  • Custom order applied                             │    │
│  │                                                     │    │
│  │  These will be lost if you leave.                   │    │
│  │                                                     │    │
│  │      [ Stay ]  [ Save as Draft ]  [ Leave Anyway ]  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PAGE REFRESH DURING OPERATION                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User refreshes during file upload                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ⚠️  Upload in progress                             │    │
│  │                                                     │    │
│  │  Refreshing will cancel your current upload.        │    │
│  │                                                     │    │
│  │  12 of 45 files uploaded so far.                    │    │
│  │                                                     │    │
│  │              [ Cancel Refresh ]  [ Refresh Anyway ] │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Uses browser beforeunload event                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.9 Accessibility Edge Cases

```
┌─────────────────────────────────────────────────────────────┐
│  KEYBOARD NAVIGATION                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Focus order (Tab key):                                     │
│  1. Header navigation                                       │
│  2. Tab bar                                                 │
│  3. Filters/controls                                        │
│  4. Main content area                                       │
│  5. Side panels                                             │
│  6. Footer                                                  │
│                                                             │
│  Skip links:                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  [ Skip to main content ]  [ Skip to navigation ]   │    │
│  │  (visible on Tab focus)                             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Focus trap in modals: Tab cycles within modal only         │
│  Escape: Closes modal, side panel, or dropdown              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SCREEN READER ANNOUNCEMENTS                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Dynamic content updates:                                   │
│                                                             │
│  • Processing complete:                                     │
│    "Processing complete. 45 documents analyzed."            │
│                                                             │
│  • New toast notification:                                  │
│    "Notification: Changes saved successfully"               │
│                                                             │
│  • List updated:                                            │
│    "Results updated. Showing 25 of 234 items."              │
│                                                             │
│  • Error occurred:                                          │
│    "Error: Upload failed. Retry button available."          │
│                                                             │
│  Use aria-live regions for dynamic updates                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  HIGH CONTRAST MODE                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Detect system preference: prefers-contrast: more           │
│                                                             │
│  Adjustments:                                               │
│  • Increase border widths from 1px to 2px                   │
│  • Use solid colors instead of subtle gradients             │
│  • Ensure 7:1 contrast ratio minimum                        │
│  • Add visible focus outlines (not just color change)       │
│                                                             │
│  Normal:         High Contrast:                             │
│  ┌──────────┐    ┏━━━━━━━━━━┓                               │
│  │ Button   │    ┃ Button   ┃                               │
│  └──────────┘    ┗━━━━━━━━━━┛                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.10 Edge Cases Summary Table

| Category | Edge Case | Handling |
|----------|-----------|----------|
| Empty States | No matters | Welcome message + CTA |
| Empty States | No results | Suggestions + related terms |
| Volume | 2000+ pages | Progressive loading + virtual scroll |
| Volume | 50+ uploads | Collapsed view + batch progress |
| Content | Scanned PDFs | OCR + confidence warning |
| Content | Non-English | Language notice + continue |
| Content | Duplicates | Detect + merge/skip options |
| Timeline | Same date/time | Cluster with expand |
| Timeline | Ambiguous dates | Range display |
| Timeline | Future dates | Dashed styling |
| Entities | Same name | Disambiguation prompt |
| Entities | Many aliases | Expandable list |
| Citations | External refs | Upload or mark external |
| Q&A | Out of scope | Redirect to document focus |
| Session | Timeout | Warning + stay logged in |
| Session | Back button | Unsaved changes warning |
| Accessibility | Keyboard nav | Skip links + focus trap |

---

## Change Log

| Date | Changes | By |
|------|---------|-----|
| 2026-01-03 | Initial document creation with decisions for Dashboard, Upload, Summary Tab, Timeline Tab, Cross-referencing | Sally (UX Designer) |
| 2026-01-03 | Added wireframe maps for all completed sections: Dashboard, Upload stages, Summary Tab, Timeline views, Cross-referencing | Sally (UX Designer) |
| 2026-01-03 | Added Entities Tab: Graph view, List view, Entity Detail Panel, Alias detection, Entity merge modal, Relationship types | Sally (UX Designer) |
| 2026-01-03 | Added Citations Tab: Main view, Detail panel, Issue resolution modal, View by Document, Citation types and status | Sally (UX Designer) |
| 2026-01-03 | Added Contradictions Tab: Main view, Side-by-side comparison, Timeline integration, Contradiction types and severity | Sally (UX Designer) |
| 2026-01-03 | Added Verification Tab: Queue view, Review session, History view, Inline verification, Priority levels | Sally (UX Designer) |
| 2026-01-03 | Added Documents Tab: List/Grid/Map views, Document detail, Add files modal, Cross-reference map, Categories | Sally (UX Designer) |
| 2026-01-03 | Added Q&A Panel: Position options, Conversation wireframes, Visual citations, Context-aware suggestions, Session memory | Sally (UX Designer) |
| 2026-01-03 | Added PDF Viewer: Split/Modal modes, Bounding box highlights, Cross-reference links, Navigation controls | Sally (UX Designer) |
| 2026-01-03 | Added Export Builder: Section selection, Reordering, Inline editing, Format options, Export history | Sally (UX Designer) |
| 2026-01-03 | Added Micro-Interactions: Animation principles, Loading states, Button/Card/Panel transitions, Drag-drop, Toasts, Forms, Highlights, Verification feedback | Sally (UX Designer) |
| 2026-01-03 | Added Error States: Upload errors, Processing errors, Network errors, AI/Q&A errors, PDF viewer errors, Export errors, Validation, Entity merge conflicts, Recovery summary | Sally (UX Designer) |
| 2026-01-03 | Added Edge Cases: Empty states, Extreme volumes, Special content (OCR, non-English, duplicates), Timeline edge cases, Entity disambiguation, Citation edge cases, Q&A boundaries, Session/browser handling, Accessibility | Sally (UX Designer) |

---

*This is a living document. Update as new decisions are made.*
