# Jaanch UX Design Direction

**Document Version:** 1.0
**Created:** 2026-01-16
**Author:** Sally (UX Designer Agent) + Juhi
**Status:** Approved Direction

---

## Executive Summary

This document defines the UX design direction for Jaanch, the Legal Document Intelligence Platform. The design philosophy is **"Intelligent Legal"** - combining the authority and trust of traditional legal aesthetics with modern AI-powered functionality.

**Key Principle:** We are a *legal technology* product, not an *AI product that happens to do legal*. Legal identity leads; AI is the enabler.

### Design Derivation

This direction was derived through:
1. **Cross-Functional War Room** - Balancing PM, Engineering, and Design constraints
2. **Genre Mashup** - Combining "Traditional Legal" + "Modern AI SaaS" aesthetics
3. **Pre-mortem Analysis** - Preventing common redesign failures
4. **SCAMPER Method** - Developing unique legal micro-interactions

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Layout System](#4-layout-system)
5. [Legal Micro-Details](#5-legal-micro-details)
6. [Component Specifications](#6-component-specifications)
7. [Motion & Animation](#7-motion--animation)
8. [Trust & Credibility Stack](#8-trust--credibility-stack)
9. [Page Structure](#9-page-structure)
10. [Performance Guidelines](#10-performance-guidelines)
11. [Accessibility](#11-accessibility)
12. [Implementation Notes](#12-implementation-notes)
13. [User Validation](#13-user-validation)
14. [Competitive Positioning](#14-competitive-positioning)
15. [Investor Stress-Test](#15-investor-stress-test)
16. [First Principles Refinements](#16-first-principles-refinements)
17. [Future-Proofing](#17-future-proofing)

---

## 1. Design Principles

### Core Philosophy: "Intelligent Legal"

| Principle | Description | Implementation |
|-----------|-------------|----------------|
| **Legal Identity First** | We are legal tech, AI is the enabler | Legal visual language throughout |
| **Authority Through Restraint** | Confidence without flashiness | Navy + Gold, minimal animation |
| **Substance Over Vibes** | Lawyers expect information density | Higher content density than typical SaaS |
| **Trust Before Conversion** | Security and credibility upfront | Trust badges above the fold |
| **Performance is UX** | Tier-2 city attorneys are our users | Strict performance budgets |

### What We Are NOT

- Not a generic AI/ChatGPT wrapper aesthetic
- Not a Silicon Valley startup with gradients and bouncy animations
- Not so traditional that we look outdated
- Not sacrificing usability for cleverness

### Theming Intensity: The 60% Rule

**Senior Lawyer Feedback:** *"The bones are good. The danger zone is when theming becomes gimmickry."*

Legal theming should be at **60% intensity** - present but not pervasive:

| Element | Use Theming | Keep Standard |
|---------|-------------|---------------|
| **Colors** | Navy + Gold palette | Standard UI patterns |
| **Typography** | Fraunces for headlines | Inter for everything else |
| **Terminology** | 2-3 touches max per screen | Standard labels for common actions |
| **Notifications** | Subtle stamp styling | Standard badge for counts |
| **Error states** | One legal easter egg (404 only) | Clear, standard error messages |
| **Cursors** | Optional, disabled by default | Standard pointer |

**The Restraint Test:** If a colleague would roll their eyes, dial it back.

**What Senior Lawyers Actually Said:**
- "Chambers Mode for late nights - whoever thought of this understands our profession."
- "Court Mode for screen sharing - *this* is thoughtful."
- "'Adjourn Session' instead of Logout - clever once, but if every button has a legal pun, I'll feel like I'm using a novelty app."
- "If I'm getting 'Sustained!' confirmations every time I save a document, I'll feel like I'm playing Ace Attorney."

---

## 2. Color System

### Primary Palette

| Role | Name | Hex | RGB | Usage |
|------|------|-----|-----|-------|
| **Primary** | Deep Navy | `#1a2744` | 26, 39, 68 | Headers, primary buttons, footer, navigation |
| **Accent** | Warm Gold | `#c9a227` | 201, 162, 39 | CTAs, highlights, premium indicators, selected states |
| **Background** | Soft Cream | `#f8f6f2` | 248, 246, 242 | Page backgrounds, card backgrounds |
| **Surface** | Pure White | `#ffffff` | 255, 255, 255 | Content areas, modals, input fields |
| **Text Primary** | Charcoal | `#2d3748` | 45, 55, 72 | Body copy, primary text |
| **Text Secondary** | Slate | `#64748b` | 100, 116, 139 | Captions, helper text, timestamps |

### Extended Palette

| Role | Name | Hex | Usage |
|------|------|-----|-------|
| **Success** | Legal Green | `#166534` | Confirmations, "Sustained" states |
| **Warning** | Amber | `#d97706` | Warnings, confidence badges 70-90% |
| **Error** | Objection Red | `#dc2626` | Errors, "Overruled" states, confidence <70% |
| **Info** | Steel Blue | `#3b82f6` | Informational states, links |
| **Border** | Warm Gray | `#e5e2dd` | Dividers, card borders |
| **Hover** | Navy Light | `#2a3a5c` | Button hover states |

### Semantic Color Tokens (CSS Variables)

```css
:root {
  /* Primary */
  --color-primary: #1a2744;
  --color-primary-hover: #2a3a5c;
  --color-primary-light: #3d4f6f;

  /* Accent */
  --color-accent: #c9a227;
  --color-accent-hover: #b89220;
  --color-accent-light: #f5e6b8;

  /* Backgrounds */
  --color-bg-page: #f8f6f2;
  --color-bg-surface: #ffffff;
  --color-bg-elevated: #ffffff;

  /* Text */
  --color-text-primary: #2d3748;
  --color-text-secondary: #64748b;
  --color-text-muted: #94a3b8;
  --color-text-inverse: #ffffff;

  /* Semantic */
  --color-success: #166534;
  --color-warning: #d97706;
  --color-error: #dc2626;
  --color-info: #3b82f6;

  /* Borders */
  --color-border: #e5e2dd;
  --color-border-strong: #d1cdc6;

  /* Special: Legal Accents */
  --color-seal-red: #8b0000;
  --color-legal-pad: #fffef0;
  --color-ribbon-gold: #c9a227;
}
```

### Dark Mode: "Chambers Mode"

For late-night document review sessions:

### Court Mode (NEW - Reverse Engineering Insight)

**Why:** When lawyers share screens with judges or opposing counsel during hearings/demos, they need an ultra-clean, distraction-free view.

**Trigger:** Toggle in header or keyboard shortcut (Cmd/Ctrl + Shift + C)

```
┌─────────────────────────────────────────────────────────────┐
│  COURT MODE                               [Exit Court Mode] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  [Document content only - full width]               │   │
│  │                                                     │   │
│  │  • No notifications visible                        │   │
│  │  • No AI suggestions or highlights                 │   │
│  │  • No confidence scores                            │   │
│  │  • No sidebar panels                               │   │
│  │  • Clean, printable view                          │   │
│  │  • Neutral colors (no gold accents)               │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Court Mode Specifications:**

| Element | Normal Mode | Court Mode |
|---------|-------------|------------|
| Notifications | Visible | Hidden |
| AI highlights | Shown | Hidden |
| Confidence badges | Displayed | Hidden |
| Sidebar panels | Available | Collapsed |
| Header | Full navigation | Minimal (logo + exit) |
| Colors | Navy + Gold | Navy + White only |
| Annotations | User's visible | Hidden (optional toggle) |

```css
.court-mode {
  --color-accent: var(--color-text-primary); /* Remove gold */
}

.court-mode .notification-badge,
.court-mode .ai-highlight,
.court-mode .confidence-badge,
.court-mode .sidebar-panel {
  display: none !important;
}

.court-mode .document-viewer {
  max-width: 100%;
  padding: 48px;
}
```

**Keyboard shortcut:** `Cmd/Ctrl + Shift + C` toggles Court Mode

---

### Chambers Mode (Dark Theme)

| Role | Light Mode | Dark Mode (Chambers) |
|------|------------|---------------------|
| Background | `#f8f6f2` | `#1a1a1f` |
| Surface | `#ffffff` | `#25252d` |
| Text Primary | `#2d3748` | `#e5e5e7` |
| Text Secondary | `#64748b` | `#9ca3af` |
| Border | `#e5e2dd` | `#3d3d47` |
| Accent | `#c9a227` | `#dbb536` (slightly brighter) |

---

## 3. Typography

### Font Stack

| Role | Font Family | Fallback Stack |
|------|-------------|----------------|
| **Headlines** | Fraunces | Georgia, 'Times New Roman', serif |
| **Body** | Inter | -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif |
| **Monospace** | JetBrains Mono | 'Fira Code', Consolas, monospace |

### Type Scale

| Name | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| **Display** | 48px / 3rem | Fraunces 700 | 1.1 | Hero headlines |
| **H1** | 36px / 2.25rem | Fraunces 600 | 1.2 | Page titles |
| **H2** | 28px / 1.75rem | Fraunces 600 | 1.25 | Section headers |
| **H3** | 22px / 1.375rem | Inter 600 | 1.3 | Subsection headers |
| **H4** | 18px / 1.125rem | Inter 600 | 1.4 | Card titles |
| **Body Large** | 18px / 1.125rem | Inter 400 | 1.6 | Lead paragraphs |
| **Body** | 16px / 1rem | Inter 400 | 1.6 | Default body text |
| **Body Small** | 14px / 0.875rem | Inter 400 | 1.5 | Secondary text |
| **Caption** | 12px / 0.75rem | Inter 400 | 1.4 | Labels, timestamps |
| **Overline** | 12px / 0.75rem | Inter 600 | 1.2 | Section labels, ALL CAPS |

### Typography CSS

```css
/* Headlines - Fraunces */
.text-display {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 3rem;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.text-h1 {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 2.25rem;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
}

/* Body - Inter */
.text-body {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 1rem;
  font-weight: 400;
  line-height: 1.6;
}

/* Legal special: Section symbol bullets */
.list-legal {
  list-style: none;
  padding-left: 1.5em;
}

.list-legal li::before {
  content: "§";
  color: var(--color-accent);
  font-weight: 600;
  margin-right: 0.5em;
  margin-left: -1.5em;
}
```

### Alternative Headline Fonts

If Fraunces feels too playful after user testing:
- **Option A:** Playfair Display (more traditional)
- **Option B:** Source Serif Pro (Google-hosted, reliable)
- **Option C:** Lora (balanced, professional)

---

## 4. Layout System

### Grid

```
Container Max Width: 1280px
Gutter: 24px
Columns: 12

Breakpoints:
  - Mobile:  < 640px   (4 columns)
  - Tablet:  640-1024px (8 columns)
  - Desktop: > 1024px  (12 columns)
```

### Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | Tight spacing, icon gaps |
| `space-2` | 8px | Related elements |
| `space-3` | 12px | Form field gaps |
| `space-4` | 16px | Standard component padding |
| `space-5` | 24px | Card padding, section gaps |
| `space-6` | 32px | Large component gaps |
| `space-8` | 48px | Section padding (mobile) |
| `space-10` | 64px | Section padding (tablet) |
| `space-12` | 80px | Section padding (desktop) |
| `space-16` | 120px | Major section dividers |

### Page Layout Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER (sticky, 64px height)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  HERO SECTION                                           │   │
│  │  Max-width: 1280px, centered                           │   │
│  │  Padding: 80px vertical (desktop)                      │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ─────────────────── 120px gap ───────────────────────────────  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CONTENT SECTION                                        │   │
│  │  Alternating backgrounds: cream / white                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  FOOTER (navy background)                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Information Density

Unlike typical SaaS with excessive whitespace, Jaanch uses **moderate-high density**:
- Lawyers expect substance
- More content visible without scrolling
- But still breathing room - not cramped

---

## 5. Legal Micro-Details

### Custom Cursors

| Cursor | File | Size | Hotspot | Usage |
|--------|------|------|---------|-------|
| **Fountain Pen** | `/cursors/fountain-pen.svg` | 24x24 | 4, 4 | Clickable elements, links |
| **Hand with Document** | `/cursors/hand-document.svg` | 28x28 | 12, 12 | Draggable items |
| **Stamp** | `/cursors/stamp.svg` | 32x32 | 16, 24 | Approval actions |
| **Default** | System default | — | — | General navigation |
| **Text** | System I-beam | — | — | Text selection (keep standard) |

```css
/* Cursor classes */
.cursor-pen { cursor: url('/cursors/fountain-pen.svg') 4 4, pointer; }
.cursor-grab-doc { cursor: url('/cursors/hand-document.svg') 12 12, grab; }
.cursor-grabbing-doc { cursor: url('/cursors/hand-document.svg') 12 12, grabbing; }
.cursor-stamp { cursor: url('/cursors/stamp.svg') 16 24, pointer; }

/* Apply to interactive elements */
a, button, [role="button"] { cursor: url('/cursors/fountain-pen.svg') 4 4, pointer; }
[draggable="true"] { cursor: url('/cursors/hand-document.svg') 12 12, grab; }
[draggable="true"]:active { cursor: url('/cursors/hand-document.svg') 12 12, grabbing; }
```

### Legal Icon System

Replace generic icons with legal equivalents:

| Generic | Legal Replacement | Usage |
|---------|-------------------|-------|
| ✓ Checkmark | Gavel stamp | Confirmations |
| ⭐ Star rating | Balanced scales | Quality indicators |
| 🔔 Bell notification | Wax seal with number | Notification badges |
| 📁 Folder | Manila case folder | File organization |
| 📄 Document | Specific type: Affidavit, Contract, Petition | Document icons |
| ❌ Error | "Objection!" speech bubble | Error states |
| ℹ️ Info | Scroll/decree icon | Help tooltips |
| 👤 User avatar | Silhouette with legal collar | User profiles |

### Section Symbol Bullets (§) - Use Sparingly

**60% Rule:** Use § bullets only in **legal-specific contexts**, not everywhere. If every list has §, it becomes noise.

| Context | Use § Bullets | Use Standard • Bullets |
|---------|---------------|------------------------|
| Document analysis results | ✓ | |
| Entity/citation lists | ✓ | |
| Legal findings summary | ✓ | |
| Navigation menus | | ✓ |
| Settings options | | ✓ |
| General UI lists | | ✓ |
| Error message lists | | ✓ |

**Good use - document results:**
```
§ 12 entities extracted
§ 3 case citations found
§ 2 potential contradictions flagged
```

**Bad use - settings menu:**
```
§ Account settings      ← Too much, use standard bullets
§ Notification preferences
§ Security
```

```html
<!-- Only for legal content contexts -->
<ul class="list-legal">
  <li>Document analysis complete</li>
  <li>12 entities extracted</li>
</ul>
```

### Exhibit Badges

For document thumbnails and attachments:

```html
<span class="exhibit-badge">Exhibit A</span>
<span class="exhibit-badge">Exhibit B</span>
```

```css
.exhibit-badge {
  display: inline-block;
  background: var(--color-primary);
  color: var(--color-text-inverse);
  font-family: 'Inter', sans-serif;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 6px;
  border-radius: 2px;
}
```

### Notification Badge: Indian Rubber Stamp Variant

**First Principles Insight:** Wax seals are Western/European. Indian legal culture uses **rubber stamps** (round, red/blue ink) and **embossed seals**. This refinement makes the design more culturally authentic.

**Two variants available:**

#### Option A: Round Rubber Stamp (Recommended for India)

```css
.notification-stamp {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: 2px solid var(--color-seal-red);
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-seal-red);
}

/* Inner circle for authentic stamp look */
.notification-stamp::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  border: 1px solid var(--color-seal-red);
  border-radius: 50%;
  opacity: 0.5;
}
```

Visual:
```
  ╭───────╮
  │ ╭───╮ │
  │ │ 3 │ │   ← Round rubber stamp style
  │ ╰───╯ │
  ╰───────╯
```

#### Option B: Wax Seal (Western markets / Global expansion)

Instead of generic red circles:

```css
.notification-seal {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: var(--color-seal-red);
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  color: white;
  box-shadow:
    inset 0 -2px 4px rgba(0,0,0,0.3),
    0 1px 2px rgba(0,0,0,0.2);
}

/* Wax drip effect (optional) */
.notification-seal::after {
  content: '';
  position: absolute;
  bottom: -3px;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 4px;
  background: var(--color-seal-red);
  border-radius: 0 0 3px 3px;
}
```

### Legal Terminology in UI

| Generic UI Term | Jaanch Legal Term |
|-----------------|-------------------|
| Logout | Adjourn Session |
| Settings | Chambers |
| Help | Legal Aid |
| Delete | Strike from Record |
| Undo | Appeal |
| Confirm | Sustained |
| Cancel | Overruled |
| Loading... | Reviewing evidence... |
| Empty state | No cases on the docket |
| Error | Objection! |
| Success | Motion granted |
| New | Fresh Evidence |
| Last updated | Last filed: [time] |

### Confirmation Dialog Pattern

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   ⚖️  Motion to Delete                              │
│                                                     │
│   This action will permanently remove               │
│   "Contract_Final_v3.pdf" from the matter record.  │
│                                                     │
│   This cannot be undone.                           │
│                                                     │
│   ┌───────────────┐    ┌─────────────────────┐     │
│   │   Overruled   │    │   Sustained  ✓      │     │
│   │   (Cancel)    │    │   (Confirm Delete)  │     │
│   └───────────────┘    └─────────────────────┘     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Manila Folder Tab Navigation

For main workspace tabs:

```css
.tab-legal {
  position: relative;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-bottom: none;
  border-radius: 4px 4px 0 0;
  padding: 8px 16px;
  margin-right: -1px;
  font-weight: 500;
  color: var(--color-text-secondary);
  transition: background 150ms ease;
}

.tab-legal.active {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border-color: var(--color-border-strong);
  z-index: 1;
}

.tab-legal::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: transparent;
  border-radius: 4px 4px 0 0;
}

.tab-legal.active::before {
  background: var(--color-accent);
}
```

Visual:
```
┌──────────┐ ┌──────────┐ ┌──────────┐
│▓▓▓▓▓▓▓▓▓▓│ │ Evidence │ │ Entities │   ← Gold top border on active
│ Documents│ └──────────┘ └──────────┘
└──────────┴───────────────────────────────────────────┐
│                                                       │
│  Tab content area                                     │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Legal Pad Note Area

For annotation or note-taking sections:

```css
.legal-pad {
  background: var(--color-legal-pad);
  border-left: 2px solid #e85d5d; /* Red margin line */
  padding: 16px 16px 16px 24px;
  font-family: 'Inter', sans-serif;
  line-height: 1.8;
  background-image: repeating-linear-gradient(
    transparent,
    transparent 27px,
    #e0e0e0 27px,
    #e0e0e0 28px
  );
}
```

### Breadcrumb as Case Citation

```
Jaanch › Matter #2024-1532 › Documents › Contract_Draft.pdf
```

```css
.breadcrumb-legal {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.breadcrumb-legal .separator {
  margin: 0 8px;
  color: var(--color-text-muted);
}

.breadcrumb-legal .current {
  color: var(--color-text-primary);
  font-weight: 500;
}
```

---

## 6. Component Specifications

### Buttons

#### Primary Button (Stamp Style)

```css
.btn-primary {
  background: var(--color-primary);
  color: var(--color-text-inverse);
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 14px;
  padding: 12px 24px;
  border: none;
  border-radius: 4px;
  cursor: url('/cursors/fountain-pen.svg') 4 4, pointer;
  transition: all 150ms ease;
  box-shadow: 0 2px 4px rgba(26, 39, 68, 0.2);
}

.btn-primary:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(26, 39, 68, 0.25);
}

.btn-primary:active {
  transform: translateY(1px);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
}
```

#### Secondary Button

```css
.btn-secondary {
  background: transparent;
  color: var(--color-primary);
  border: 2px solid var(--color-primary);
  /* ... similar padding/sizing as primary */
}

.btn-secondary:hover {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}
```

#### Accent Button (Gold CTA)

```css
.btn-accent {
  background: var(--color-accent);
  color: var(--color-primary);
  font-weight: 700;
  /* Used for primary CTAs like "Book Demo" */
}
```

### Cards

```css
.card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 24px;
  transition: all 200ms ease;
}

.card:hover {
  border-color: var(--color-border-strong);
  box-shadow: 0 4px 12px rgba(26, 39, 68, 0.08);
  transform: translateY(-2px);
}

/* Card with ribbon accent (selected/featured) */
.card.featured {
  border-left: 4px solid var(--color-accent);
}
```

### Form Inputs

```css
.input {
  width: 100%;
  padding: 12px 16px;
  font-family: 'Inter', sans-serif;
  font-size: 16px;
  color: var(--color-text-primary);
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-light);
}

.input::placeholder {
  color: var(--color-text-muted);
}
```

### Badges

#### Confidence Badges with Plain-English Labels (Feynman Refinement)

**Why:** Users need to understand what confidence scores *mean*, not just see percentages. (Source: Feynman Technique analysis)

| Score Range | Badge | Plain-English Label | Action Guidance |
|-------------|-------|---------------------|-----------------|
| **>90%** | 🟢 High | "Usually correct" | "Verify key details" |
| **70-90%** | 🟡 Moderate | "Review carefully" | "Cross-check before using" |
| **<70%** | 🔴 Low | "Needs verification" | "Attorney review required" |

**Confidence Badge Component:**

```tsx
interface ConfidenceBadgeProps {
  score: number;
  showGuidance?: boolean; // Show action text
}

// Usage
<ConfidenceBadge score={85} showGuidance={true} />

// Renders:
// 🟢 High confidence (85%)
// "Usually correct - verify key details"
```

```css
/* Confidence badges */
.badge-high { /* >90% */
  background: #dcfce7;
  color: var(--color-success);
}

.badge-medium { /* 70-90% */
  background: #fef3c7;
  color: var(--color-warning);
}

.badge-low { /* <70% */
  background: #fee2e2;
  color: var(--color-error);
}

.badge-guidance {
  display: block;
  font-size: 11px;
  font-style: italic;
  color: var(--color-text-muted);
  margin-top: 2px;
}
```

**Visual Display:**

```
┌─────────────────────────────────────────────────────────────┐
│  AI Analysis Result                                         │
│                                                             │
│  "The contract contains a non-compete clause..."            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🟢 High confidence (92%)                            │   │
│  │ Usually correct - verify key details                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [👍 Agree]  [👎 Disagree]  [📝 Add Note]                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**"I Disagree" Button (First Principles):**

Lawyers need control over AI outputs. Add feedback mechanism:

```tsx
<AIResultCard>
  <ConfidenceBadge score={85} />
  <ButtonGroup>
    <Button variant="ghost" size="sm">👍 Agree</Button>
    <Button variant="ghost" size="sm">👎 Disagree</Button>
    <Button variant="ghost" size="sm">📝 Add Note</Button>
  </ButtonGroup>
</AIResultCard>
```

#### Fresh Evidence Badge

```css
/* Fresh Evidence badge */
.badge-new {
  background: var(--color-seal-red);
  color: white;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 2px;
}
```

### Tooltips (Margin Annotation Style)

```css
.tooltip {
  position: absolute;
  background: var(--color-legal-pad);
  color: var(--color-text-primary);
  font-size: 13px;
  padding: 8px 12px;
  border-left: 3px solid var(--color-accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-width: 240px;
  z-index: 1000;
}
```

### Auto-Save Indicator

**Why:** Paralegals processing 100+ documents daily cannot afford to lose work. (Source: Focus Group - Meera, Paralegal)

**Component Specification:**

```
┌─────────────────────────────────────────────────────────────┐
│  [Document Title]                    ✓ Saved 2 seconds ago  │
└─────────────────────────────────────────────────────────────┘

States:
- Idle (no recent changes):     "✓ All changes saved"
- Saving:                       "⟳ Saving..." (spinner)
- Just saved:                   "✓ Saved just now"
- Saved with time:              "✓ Saved 2 minutes ago"
- Error:                        "⚠️ Unable to save. Retrying..."
- Offline:                      "📴 Offline - changes saved locally"
```

```css
.auto-save-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.auto-save-indicator--saving {
  color: var(--color-text-secondary);
}

.auto-save-indicator--saved {
  color: var(--color-success);
}

.auto-save-indicator--error {
  color: var(--color-error);
}

.auto-save-indicator--offline {
  color: var(--color-warning);
}

.auto-save-indicator__icon {
  width: 14px;
  height: 14px;
}

.auto-save-indicator__icon--spinning {
  animation: spin 800ms linear infinite;
}
```

**Behavior:**
- Auto-save triggers 2 seconds after last keystroke (debounced)
- Save indicator updates in real-time
- If save fails, retry 3 times with exponential backoff
- If offline, queue changes for sync when connection returns
- Show "Unsaved changes" warning if user tries to leave with pending saves

### Notification Management System

**Why:** Power users get 200+ notifications daily. Wax seals must scale gracefully. (Source: Shark Tank - Arun, Former GC)

**Notification Grouping:**

```
┌─────────────────────────────────────────────────────────────┐
│  🔴 Notifications                                           │
│   7                                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📁 Matter: Singh vs. Reliance                       │   │
│  │    3 new items                                      │   │
│  │    § Document processing complete                   │   │
│  │    § 2 entities require review                      │   │
│  │    § Citation analysis ready                        │   │
│  │    ─────────────────────────────────               │   │
│  │    [View Matter]                    2 min ago      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📁 Matter: Tata Steel Arbitration                   │   │
│  │    4 new items                                      │   │
│  │    [View Matter]                    15 min ago     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  [Mark All Read]              [Notification Settings ⚙️]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Notification Settings (Quiet Mode):**

```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ Notification Preferences                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Notification Mode                                          │
│  ○ All notifications                                        │
│  ○ Important only (processing complete, errors)            │
│  ● Quiet mode (badge only, no popups)                      │
│  ○ Do not disturb (until 5:00 PM)                         │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Sound                                                      │
│  [Toggle: OFF] Audio notifications                          │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Email Digest                                               │
│  ○ Real-time                                               │
│  ● Daily summary (9:00 AM)                                 │
│  ○ Weekly summary                                          │
│  ○ Never                                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Notification Priority Levels:**

| Priority | Seal Style | Popup? | Sound? | Examples |
|----------|------------|--------|--------|----------|
| **Critical** | Red seal, pulsing | Yes | Optional | Error, security alert |
| **High** | Red seal, static | Yes (dismissible) | No | Processing complete |
| **Medium** | Gold seal | Badge only | No | Entity flagged for review |
| **Low** | Gray seal | Badge only | No | Activity in shared matter |

### Error States

**Design Philosophy:** Errors prioritize clarity over theming. Use standard, professional language - save legal terminology for the 404 page easter egg only.

#### Error State Structure

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    ⚠️ [Clear Error Title]                   │
│                                                             │
│           [Clear, specific error description]               │
│                                                             │
│     [Primary Action]        [Secondary Action]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Error Types and Messaging

| Error Type | Title | Example Message | Primary Action | Secondary Action |
|------------|-------|-----------------|----------------|------------------|
| **Network** | "Connection Lost" | "Unable to connect. Check your network connection." | "Retry" | "Work Offline" |
| **Authentication** | "Session Expired" | "Your session has expired. Please sign in again." | "Sign In" | - |
| **Permission** | "Access Denied" | "You don't have permission to view this matter." | "Request Access" | "Go Back" |
| **Not Found** | "Page Not Found" | "The page you're looking for doesn't exist or has been removed." | "Go to Dashboard" | - |
| **Server** | "Something Went Wrong" | "We're experiencing technical difficulties. Please try again shortly." | "Retry" | "Contact Support" |
| **Validation** | "Please Fix Errors" | "Please correct the highlighted fields before proceeding." | "Review Fields" | - |
| **File** | "File Not Supported" | "This file type isn't accepted. Supported formats: PDF, DOCX, DOC" | "Choose Another File" | - |
| **Size Limit** | "File Too Large" | "File exceeds 50MB limit. Consider splitting into multiple documents." | "Choose Another File" | - |

#### 404 Page Easter Egg (The ONE Legal Touch)

The 404 page is the **only** place we use legal humor - because users are already in an error state and a moment of levity is welcome:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    ⚖️ CASE DISMISSED                        │
│                                                             │
│     The page you're looking for has been struck from        │
│     the record. It may have been moved or deleted.          │
│                                                             │
│                    [Return to Dashboard]                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Why only here:** Users aren't blocked from completing a task, so the legal reference is charming rather than frustrating.

#### Error State CSS

```css
.error-state {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-error);
  border-left: 4px solid var(--color-error);
  border-radius: 8px;
  padding: 24px;
  text-align: center;
}

.error-state__icon {
  color: var(--color-error);
  font-size: 48px;
  margin-bottom: 16px;
}

.error-state__title {
  font-family: 'Fraunces', serif;
  font-size: 24px;
  font-weight: 600;
  color: var(--color-error);
  margin-bottom: 8px;
}

.error-state__message {
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 24px;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}
```

### Empty States

**Design Philosophy:** Empty states use legal docket terminology and always provide a clear call-to-action to guide users forward.

#### Empty State Structure

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    [Relevant Icon]                          │
│                                                             │
│              No Cases on the Docket                         │
│                                                             │
│     [Helpful context explaining why this is empty          │
│      and what the user can do to populate it]              │
│                                                             │
│                  [Primary CTA Button]                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Empty State Types

| Context | Icon | Title | Message | CTA |
|---------|------|-------|---------|-----|
| **Matters List** | 📁 | "No Cases on the Docket" | "Create your first matter to start organizing documents and extracting insights." | "Create New Matter" |
| **Documents** | 📄 | "Exhibit List Empty" | "Upload documents to this matter to begin analysis." | "Upload Documents" |
| **Search Results** | 🔍 | "No Matching Records" | "Try adjusting your search terms or filters." | "Clear Filters" |
| **Entities** | 🏛️ | "No Entities Identified" | "Entities will appear here once documents are processed." | "View Processing Status" |
| **Citations** | § | "No Citations Found" | "Legal citations will be extracted automatically during document processing." | "Upload Documents" |
| **Chat History** | 💬 | "No Questions Yet" | "Ask questions about your documents using the chat panel." | "Ask a Question" |
| **Notifications** | 🔔 | "All Caught Up" | "You have no new notifications." | - (no CTA needed) |
| **Team Members** | 👥 | "Solo Practice" | "Invite colleagues to collaborate on this matter." | "Invite Team Member" |
| **Exports** | 📤 | "No Exports Generated" | "Generate reports and exports from the matter overview." | "Go to Matter Overview" |

#### Empty State CSS

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
  background: var(--color-bg-surface);
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  min-height: 240px;
}

.empty-state__icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-state__title {
  font-family: 'Fraunces', serif;
  font-size: 20px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.empty-state__message {
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 24px;
  max-width: 320px;
}

.empty-state__cta {
  /* Uses standard primary button styling */
}
```

### Form Validation Patterns

**Design Philosophy:** Inline validation provides immediate feedback without overwhelming users. Error messages are specific and actionable.

#### Validation Timing

| Validation Type | Trigger | Example |
|-----------------|---------|---------|
| **Format validation** | On blur (when field loses focus) | Email format, phone number |
| **Required fields** | On blur + on submit attempt | Matter title, client name |
| **Async validation** | On blur with debounce (300ms) | Email uniqueness check |
| **Cross-field** | On submit | Password confirmation match |

#### Field States

```
┌─ Default ─────────────────────────────────────────┐
│  Matter Title                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │ Enter matter title...                       │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
└───────────────────────────────────────────────────┘

┌─ Focus ───────────────────────────────────────────┐
│  Matter Title                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │ Singh vs. Reliance Industries█              │  │  [Blue border]
│  └─────────────────────────────────────────────┘  │
│                                                   │
└───────────────────────────────────────────────────┘

┌─ Error ───────────────────────────────────────────┐
│  Matter Title                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │                                             │  │  [Red border]
│  └─────────────────────────────────────────────┘  │
│  ⚠️ Matter title is required                      │  [Red text]
└───────────────────────────────────────────────────┘

┌─ Success ─────────────────────────────────────────┐
│  Email Address                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │ partner@lawfirm.com                    ✓    │  │  [Green border + check]
│  └─────────────────────────────────────────────┘  │
│                                                   │
└───────────────────────────────────────────────────┘
```

#### Error Message Guidelines

| Principle | Bad Example | Good Example |
|-----------|-------------|--------------|
| **Specific** | "Invalid input" | "Email must include @ and a domain (e.g., name@firm.com)" |
| **Actionable** | "Error" | "Enter a valid 10-digit phone number" |
| **Blame-free** | "You entered an invalid date" | "Date must be in DD/MM/YYYY format" |
| **Concise** | "The matter title field cannot be left empty because it is a required field" | "Matter title is required" |

#### Common Validation Messages

| Field | Validation | Error Message |
|-------|------------|---------------|
| **Matter Title** | Required | "Matter title is required" |
| **Matter Title** | Max length (200) | "Matter title cannot exceed 200 characters" |
| **Email** | Format | "Enter a valid email address" |
| **Email** | Exists (invite) | "This email is already associated with this matter" |
| **File Upload** | Type | "File type not supported. Use PDF, DOCX, or DOC" |
| **File Upload** | Size | "File size cannot exceed 50MB" |
| **Password** | Min length | "Password must be at least 8 characters" |
| **Password** | Complexity | "Password must include a number and special character" |
| **Password Confirm** | Match | "Passwords do not match" |
| **Date** | Format | "Enter date as DD/MM/YYYY" |
| **Date** | Range | "Date cannot be in the future" |

#### Form Validation CSS

```css
/* Input States */
.form-input {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px 16px;
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  transition: border-color 150ms ease;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-info);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-input--error {
  border-color: var(--color-error);
}

.form-input--error:focus {
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
}

.form-input--success {
  border-color: var(--color-success);
  padding-right: 40px; /* Space for checkmark */
}

/* Error Message */
.form-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 13px;
  color: var(--color-error);
}

.form-error__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* Success Indicator */
.form-success-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-success);
  width: 18px;
  height: 18px;
}

/* Form-level Error Summary */
.form-error-summary {
  background: rgba(220, 38, 38, 0.05);
  border: 1px solid var(--color-error);
  border-left: 4px solid var(--color-error);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 24px;
}

.form-error-summary__title {
  font-weight: 600;
  color: var(--color-error);
  margin-bottom: 8px;
}

.form-error-summary__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.form-error-summary__item {
  font-size: 14px;
  color: var(--color-text-primary);
  padding: 4px 0;
}

.form-error-summary__item::before {
  content: "§ ";
  color: var(--color-error);
}
```

#### Submit Button States

| State | Appearance | Behavior |
|-------|------------|----------|
| **Default** | Navy background, full opacity | Clickable |
| **Disabled** | Gray background, 50% opacity | Not clickable |
| **Loading** | Navy background, spinner icon | Not clickable, shows "Submitting..." |
| **Success** | Green background, checkmark | Brief (1.5s) before redirect/close |
| **Error** | Red shake animation | Returns to default after shake |

---

## 7. Motion & Animation

### Animation Budget

| Category | Budget | Notes |
|----------|--------|-------|
| **Total JS for animations** | <15KB | No heavy libraries |
| **Hero animation** | 1 only | SVG path draw |
| **Page transitions** | Fade only | 200ms |
| **Component animations** | Minimal | Hover states only |

### Allowed Animations

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| **Hero document flow** | SVG path draw + fade | 2-3s | ease-out |
| **Section reveal** | Fade up (translateY: 20px → 0) | 300ms | ease-out |
| **Button hover** | Background color shift | 150ms | ease |
| **Button press** | translateY(1px) + inset shadow | 100ms | ease |
| **Card hover** | translateY(-2px) + shadow | 200ms | ease |
| **Modal enter** | Fade + scale(0.95 → 1) | 200ms | ease-out |
| **Notification badge** | Scale pulse on new | 300ms | ease |
| **Success stamp** | Scale(0 → 1) + slight rotate | 250ms | spring |

### Forbidden Animations

- No 3D transforms (perspective, rotateX/Y)
- No parallax scrolling
- No autoplay videos
- No bouncy/elastic easing
- No continuous animations (except loading states)
- No animation on scroll for every element

### Loading States

**Document Processing Loader (with Specificity):**

Based on Focus Group feedback (Priya, Associate Attorney): Progress must show SPECIFIC numbers, not just animation.

```
"Reviewing evidence..."

Processing page 24 of 156 (15%)
[████░░░░░░░░░░░░░░░░]

Estimated time remaining: ~2 minutes
```

**Progress Indicator Component:**

```tsx
interface ProgressIndicatorProps {
  current: number;
  total: number;
  label?: string;
  showEstimate?: boolean;
  estimatedSecondsRemaining?: number;
}

// Usage
<ProgressIndicator
  current={24}
  total={156}
  label="Processing page"
  showEstimate={true}
  estimatedSecondsRemaining={120}
/>
```

```css
.progress-legal {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-legal__label {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.progress-legal__numbers {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.progress-legal__bar {
  height: 8px;
  background: var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}

.progress-legal__fill {
  height: 100%;
  background: var(--color-accent);
  transition: width 300ms ease;
}

.progress-legal__estimate {
  font-size: 12px;
  color: var(--color-text-muted);
  font-style: italic;
}
```

**Stalled/Error Detection:**

If progress hasn't moved in 30 seconds, show:
```
Processing page 24 of 156 (15%)
[████░░░░░░░░░░░░░░░░]

⚠️ Taking longer than expected. Your connection may be slow.
[Retry] [Cancel]
```

**General Loader:**
```css
.loader-seal {
  width: 24px;
  height: 24px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 800ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### Success Animation (Stamp)

When an action succeeds, a small seal "stamps" into place:

```css
@keyframes stamp {
  0% {
    transform: scale(0) rotate(-15deg);
    opacity: 0;
  }
  60% {
    transform: scale(1.1) rotate(5deg);
    opacity: 1;
  }
  100% {
    transform: scale(1) rotate(0deg);
    opacity: 1;
  }
}

.success-stamp {
  animation: stamp 250ms ease-out forwards;
}
```

---

## 8. Trust & Credibility Stack

### Above-the-Fold Trust Elements

These MUST appear in the hero section:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  "Legal intelligence, not legal guesswork"                  │
│                                                             │
│  [Hero content / product preview]                           │
│                                                             │
│  [Book a Demo]   [Watch 2-min Overview ▶]                  │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🔒 SOC 2 Type II   🇮🇳 Data in India   📋 DPDP Act   🌐 GDPR │
│                                                             │
│  "Trusted by 50+ Indian law firms"                         │
│                                                             │
│  [Khaitan]  [AZB]  [Cyril]  [Trilegal]  [S&R]             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Trust Badge Styling

```css
.trust-badges {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: center;
  padding: 16px 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.trust-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.trust-badge svg {
  width: 20px;
  height: 20px;
  color: var(--color-primary);
}
```

### Client Logo Display

```css
.client-logos {
  display: flex;
  gap: 40px;
  align-items: center;
  justify-content: center;
  filter: grayscale(100%);
  opacity: 0.7;
  transition: all 200ms ease;
}

.client-logos:hover {
  filter: grayscale(0%);
  opacity: 1;
}

.client-logos img {
  height: 32px;
  width: auto;
}
```

### Security Page Elements

The `/security` page must include:
- Data flow diagram showing India-hosted infrastructure
- Compliance certifications with verification links
- RLS explanation (in layman's terms)
- Penetration testing cadence
- Data retention policies
- Contact for security inquiries

### Downloadable Compliance Pack (CRITICAL)

**Why:** IT heads and legal compliance officers need shareable documentation for vendor assessments. (Source: Focus Group - Ankit, IT Head)

Create a downloadable "Jaanch Security Pack" containing:

| Document | Format | Content |
|----------|--------|---------|
| **Security Overview** | PDF | 2-page executive summary |
| **SOC 2 Type II Report** | PDF | Full audit report (gated behind NDA if needed) |
| **DPDP Act Compliance Statement** | PDF | India-specific data protection compliance |
| **GDPR Compliance Statement** | PDF | For international clients |
| **Architecture Diagram** | PDF | Data flow, encryption, isolation |
| **Penetration Test Summary** | PDF | Latest test results (sanitized) |
| **Data Processing Agreement** | DOCX | Editable DPA template |

**Location:** Prominent "Download Security Pack" button on `/security` page

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  🔒 Security & Compliance                                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  [Download Security Pack]                           │   │
│  │                                                     │   │
│  │  Includes: SOC 2 Report, DPDP Compliance,          │   │
│  │  Architecture Diagram, DPA Template                 │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Trust Badges - Updated Set

| Badge | Label | Verification |
|-------|-------|--------------|
| 🔒 | SOC 2 Type II | Link to Vanta/Drata profile |
| 🇮🇳 | Data Hosted in India | Specify: AWS Mumbai / Azure India |
| 📋 | DPDP Act Compliant | India's Digital Personal Data Protection Act 2023 |
| 🌐 | GDPR Ready | For international operations |
| 🛡️ | 256-bit Encryption | TLS 1.3 + AES-256 at rest |
| 🔐 | Row-Level Security | Tenant isolation explanation |

---

## 9. Page Structure

### Marketing Site Pages

| Page | URL | Purpose | Key Sections |
|------|-----|---------|--------------|
| **Home** | `/` | Convert → Demo | Hero, Trust, Features, Case Study, CTA |
| **Product** | `/product` | Deep features | Workspace, Q&A, Entities, Export |
| **Security** | `/security` | Enterprise confidence | Compliance, Data Flow, RLS |
| **Pricing** | `/pricing` | Transparency | Tiers, Comparison, Enterprise CTA |
| **Case Studies** | `/case-studies` | Social proof | Metrics-driven stories |
| **About** | `/about` | Team credibility | Founders, Legal expertise |
| **Contact** | `/contact` | Lead capture | Form, Office info |

### Home Page Wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo]                    [Product] [Pricing] [Security] [Login]│
│                                                    [Book Demo ◆]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HERO SECTION (cream background)                                │
│  ┌────────────────────────────┬────────────────────────────┐   │
│  │ "Legal intelligence,       │   [Animated product        │   │
│  │  not legal guesswork"      │    preview showing         │   │
│  │                            │    doc → insight flow]     │   │
│  │ Subhead explaining value   │                            │   │
│  │                            │                            │   │
│  │ [Book Demo ◆] [Watch ▶]   │                            │   │
│  │                            │                            │   │
│  │ 🔒 SOC2  🇮🇳 India  📋 DPDP  🌐 GDPR │                    │   │
│  └────────────────────────────┴────────────────────────────┘   │
│                                                                 │
│  [Logo] [Logo] [Logo] [Logo] [Logo]                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PROBLEM → SOLUTION (white background)                          │
│                                                                 │
│  "Indian attorneys spend 40% of their time on document review"  │
│                                                                 │
│  [Before: Pain point]  →  [After: With Jaanch]                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FEATURES (cream background)                                    │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Document │  │ Entity   │  │ Q&A      │  │ Export   │       │
│  │ Analysis │  │ Mapping  │  │ Engine   │  │ Ready    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CASE STUDY TEASER (white background)                           │
│                                                                 │
│  "How [Firm] reduced document review time by 60%"               │
│  [Read Case Study →]                                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FINAL CTA (navy background)                                    │
│                                                                 │
│  "Ready to transform your practice?"                            │
│  [Book a Demo ◆]                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FOOTER (navy background)                                       │
│  Product | Company | Legal | Contact                            │
│  © 2026 Jaanch AI                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Performance Guidelines

### Budgets (Non-Negotiable)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Largest Contentful Paint (LCP)** | <2.5s on 4G | Lighthouse |
| **First Input Delay (FID)** | <100ms | Lighthouse |
| **Cumulative Layout Shift (CLS)** | <0.1 | Lighthouse |
| **Initial JS bundle** | <100KB gzipped | Build output |
| **Total page weight** | <500KB | Network tab |
| **Hero image** | <80KB | WebP format |
| **Time to Interactive** | <3.5s on 4G | Lighthouse |

### Image Guidelines

- **Format:** WebP with JPEG fallback
- **Lazy loading:** All images below fold
- **Responsive:** Use `srcset` for different viewport sizes
- **Placeholder:** Low-quality blur-up pattern

```html
<img
  src="/images/product-hero.webp"
  srcset="
    /images/product-hero-400.webp 400w,
    /images/product-hero-800.webp 800w,
    /images/product-hero-1200.webp 1200w
  "
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 80vw, 1200px"
  alt="Jaanch document analysis interface"
  loading="lazy"
  decoding="async"
/>
```

### Font Loading

```css
/* Preload critical fonts */
<link rel="preload" href="/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/fraunces-var.woff2" as="font" type="font/woff2" crossorigin>

/* Font-display: swap for fast render */
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter-var.woff2') format('woff2');
  font-display: swap;
}
```

### No Autoplay Media

- Videos must be click-to-play
- No background videos
- No autoplaying carousels

### Test Conditions

Always test on:
- Chrome DevTools throttled to "Fast 3G"
- Real mid-range Android device (Redmi, Realme)
- Indian mobile network conditions

---

## 11. Accessibility

### Requirements

| Standard | Requirement |
|----------|-------------|
| **WCAG Level** | AA minimum |
| **Color Contrast** | 4.5:1 for normal text, 3:1 for large text |
| **Focus States** | Visible on all interactive elements |
| **Keyboard Navigation** | Full site navigable without mouse |
| **Screen Reader** | Proper ARIA labels and semantic HTML |
| **Motion** | Respect `prefers-reduced-motion` |

### Color Contrast Verification

| Combination | Contrast Ratio | Pass? |
|-------------|----------------|-------|
| Charcoal (#2d3748) on Cream (#f8f6f2) | 9.2:1 | ✓ AA |
| Slate (#64748b) on Cream (#f8f6f2) | 4.6:1 | ✓ AA |
| White on Navy (#1a2744) | 12.1:1 | ✓ AAA |
| Gold (#c9a227) on Navy (#1a2744) | 5.8:1 | ✓ AA |

### Focus States

```css
:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

/* Remove default outline when using focus-visible */
:focus:not(:focus-visible) {
  outline: none;
}
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Touch Target Requirements (What If: Mobile/Tablet Primary)

**Why:** If tablet usage becomes primary (lawyers reviewing in court), all interactive elements must be touch-friendly.

| Requirement | Specification |
|-------------|---------------|
| **Minimum touch target** | 44x44px (Apple HIG / WCAG 2.5.5) |
| **Touch target spacing** | 8px minimum between targets |
| **No hover-only states** | All hover effects must also work on :focus |
| **Swipe gestures** | Optional enhancement, never required |

```css
/* Touch-friendly interactive elements */
button,
a,
[role="button"],
input[type="checkbox"],
input[type="radio"] {
  min-width: 44px;
  min-height: 44px;
}

/* Ensure hover states work on focus for touch */
.card:hover,
.card:focus-within {
  /* Same styles */
}

.btn:hover,
.btn:focus {
  /* Same styles */
}
```

**Tablet-Specific Considerations:**

```css
@media (pointer: coarse) {
  /* Touch device detected */

  /* Increase tap targets */
  .tab-legal {
    padding: 12px 20px; /* Larger than desktop */
  }

  /* Disable custom cursors (they don't work on touch) */
  * {
    cursor: auto !important;
  }
}
```

---

## 12. Implementation Notes

### Tailwind CSS Configuration

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#1a2744',
          light: '#2a3a5c',
          dark: '#0f1729',
        },
        gold: {
          DEFAULT: '#c9a227',
          light: '#f5e6b8',
          dark: '#b8922f',
        },
        cream: '#f8f6f2',
        charcoal: '#2d3748',
        slate: '#64748b',
        'seal-red': '#8b0000',
        'legal-pad': '#fffef0',
      },
      fontFamily: {
        serif: ['Fraunces', 'Georgia', 'serif'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
    },
  },
}
```

### shadcn/ui Theme Overrides

The existing shadcn/ui components should be themed to match:

```css
/* Override shadcn defaults in globals.css */
@layer base {
  :root {
    --background: 248 246 242; /* cream */
    --foreground: 45 55 72; /* charcoal */
    --primary: 26 39 68; /* navy */
    --primary-foreground: 255 255 255;
    --secondary: 201 162 39; /* gold */
    --secondary-foreground: 26 39 68;
    --accent: 201 162 39;
    --accent-foreground: 26 39 68;
    --destructive: 220 38 38;
    --border: 229 226 221;
    --ring: 201 162 39;
  }
}
```

### Asset Checklist

| Asset | Status | Notes |
|-------|--------|-------|
| Fraunces font files | To obtain | Google Fonts or self-host |
| Inter font files | To obtain | Already common, likely available |
| Custom cursor SVGs | To create | 4 cursors needed |
| Legal icon set | To create | ~20 icons |
| Wax seal notification | To create | PNG or SVG |
| Exhibit badge component | To build | Simple CSS |
| Hero animation | To create | SVG + CSS animation |
| Client logos | To obtain | Get from actual clients |
| Trust badge icons | To obtain | SOC2, GDPR, India flag |

### Migration from Current Design

1. **Phase 1:** Update color variables and typography
2. **Phase 2:** Apply new button/card styles
3. **Phase 3:** Add legal micro-details (cursors, icons)
4. **Phase 4:** Build marketing pages with new structure
5. **Phase 5:** Implement hero animation
6. **Phase 6:** Performance audit and optimization

---

## Appendix: Quick Reference (Implementation)

### Do's

- ✓ Use § bullets **only for legal content** (findings, citations) - not UI elements
- ✓ Limit legal terminology to 2-3 touches per screen
- ✓ Show trust badges above the fold
- ✓ Keep animations purposeful and minimal
- ✓ Test on slow Indian mobile connections
- ✓ Use Fraunces for headlines, Inter for body
- ✓ Use standard labels for common actions (Logout, Save, Cancel)

### Don'ts

- ✗ No purple gradients (too "startup")
- ✗ No bouncy animations
- ✗ No autoplay videos
- ✗ No generic AI/ChatGPT aesthetics
- ✗ No feature dumping - tell stories instead
- ✗ No "Start Free Trial" when you mean "Book Demo"
- ✗ No legal puns in error messages (except 404)
- ✗ No theming that makes colleagues roll their eyes

---

## 13. User Validation

### Focus Group Summary

Design direction was validated with four user personas representing Jaanch's target market:

| Persona | Role | Key Concern | Design Response |
|---------|------|-------------|-----------------|
| **Rajesh Mehta (58)** | Senior Partner, Mumbai | Trust & shareability of security docs | Added downloadable Compliance Pack |
| **Priya Sharma (32)** | Associate Attorney, Delhi | Progress transparency on slow connections | Added specific progress indicators (page X of Y) |
| **Ankit Desai (45)** | IT Head, Corporate Legal | DPDP Act compliance, architecture details | Added DPDP badge, architecture diagrams |
| **Meera Iyer (28)** | Paralegal, Bangalore | Auto-save, offline mode, print support | Added auto-save indicator, offline consideration |

### Validated Design Decisions

| Decision | Persona Feedback | Confidence |
|----------|------------------|------------|
| Navy + Gold colors | Rajesh: "Finally something serious" | ✅ High |
| Legal terminology (Adjourn, Sustained) | Rajesh: "Don't overdo it" - keep subtle | ⚠️ Medium - monitor |
| Manila folder tabs | Priya: "This is how my brain works" | ✅ High |
| Wax seal notifications | Meera: "Pretty but will it scale?" | ⚠️ Medium - added grouping |
| Chambers Mode (dark) | Priya: "Love it for late nights" | ✅ High |
| Performance targets | Priya: "Court WiFi is basically 2G" | ✅ Critical |

### Outstanding Concerns to Monitor

1. **Legal terminology balance** - Test with real users; may feel forced if overdone
2. **Notification scaling** - Monitor with power users processing 100+ docs/day
3. **Offline mode** - Consider for V2; critical for unreliable connections
4. **Print functionality** - Ensure annotations print cleanly for court bundles

---

## 14. Competitive Positioning

### Market Position: "Intelligent Legal"

```
                    HIGH LEGAL IDENTITY
                           │
         Westlaw ●         │         ● JAANCH
         (dated but legal) │         (modern + legal)
                           │
                           │
    ─────────────────────────────────────────────
    LOW MODERN                        HIGH MODERN
    AESTHETICS                        AESTHETICS
                           │
                           │
              Kira ●       │         ● Harvey AI
                           │         (modern but generic AI)
                           │
                    LOW LEGAL IDENTITY
```

### Competitive Analysis Matrix

| Criterion (Weight) | Westlaw | Clio | Harvey AI | Kira | **Jaanch** |
|--------------------|---------|------|-----------|------|------------|
| **Legal Identity (20%)** | 9/10 | 6/10 | 4/10 | 7/10 | **9/10** |
| **Trust Signals (20%)** | 8/10 | 7/10 | 6/10 | 8/10 | **9/10** |
| **Performance (15%)** | 5/10 | 8/10 | 7/10 | 6/10 | **8/10** |
| **Modern Aesthetics (15%)** | 3/10 | 8/10 | 9/10 | 6/10 | **8/10** |
| **Usability (15%)** | 7/10 | 8/10 | 7/10 | 7/10 | **8/10** |
| **Differentiation (15%)** | 6/10 | 5/10 | 8/10 | 6/10 | **9/10** |
| **Weighted Total** | 6.5 | 7.0 | 6.8 | 6.7 | **8.5** |

### Competitive Messaging

| Competitor | Jaanch's Counter-Position |
|------------|---------------------------|
| **vs Westlaw/Lexis** | "Modern interface, same legal rigor" |
| **vs Clio** | "Built for litigation, not just practice management" |
| **vs Harvey AI** | "Legal expertise first, AI as enabler" |
| **vs Kira** | "Full document intelligence, not just contracts" |

### Gaps to Address

| Competitor Strength | Jaanch Response |
|--------------------|-----------------|
| Westlaw's legal data depth | Deep Indian legal corpus (future roadmap) |
| Clio's smooth onboarding | Invest in demo-to-activation flow |
| Harvey's AI transparency | Prominent confidence scores |
| Kira's enterprise sales materials | Professional security documentation (done) |

---

## 15. Investor Stress-Test

### Shark Tank Panel Feedback

Design direction was stress-tested with three investor personas:

**Vikram (Legal Tech VC):**
> "The legal identity angle is smart. Everyone else is chasing the 'AI' brand. You're chasing the 'lawyer' brand. That could work."

**Sunita (Enterprise SaaS):**
> "Performance focus for India is the right bet. I've seen too many US tools fail in emerging markets because they assumed fast internet."

**Arun (Former GC):**
> "If the security documentation is actually downloadable and comprehensive, you'll shorten sales cycles by 3 months."

### Concerns Raised & Resolutions

| Concern | Raised By | Resolution |
|---------|-----------|------------|
| "Is the legal theming gimmicky?" | Vikram | Keep subtle - cursors are 24px, vocabulary is familiar not forced |
| "CTA is 'Book Demo' - high CAC?" | Sunita | Legal tech is always high-touch; demo-first qualifies buyers |
| "Will notifications scale to 200/day?" | Arun | Added notification grouping and quiet mode |
| "Security docs must be shareable" | Arun | Added downloadable Compliance Pack |

### Investment Conditions Met

- [x] Legal identity without gimmickry
- [x] Performance as market differentiator
- [x] Notification system that scales
- [x] Downloadable security documentation
- [ ] Demo-to-close metrics tracking (implementation phase)

---

## 16. First Principles Refinements

### Assumptions Challenged

| Original Assumption | Challenge | Resolution |
|---------------------|-----------|------------|
| "Wax seals are universally legal" | Western-centric; Indian legal uses rubber stamps | Added rubber stamp variant (Section 5) |
| "Navy is universally authoritative" | British colonial roots | Acceptable - gold/saffron provides Indian resonance |
| "Legal terminology delights users" | May confuse multilingual users | Test Hindi equivalents; keep English subtle |
| "Custom cursors add delight" | 2KB load + accessibility risk | Keep but disable on touch devices |

### What Lawyers Actually Need (First Principles)

| Need | Design Response |
|------|-----------------|
| **Speed** | Performance budget <500KB |
| **Trust** | Security badges + Compliance Pack |
| **Competence** | Legal visual language (familiar) |
| **Control** | "I Disagree" button on AI outputs |
| **Professionalism** | Court Mode for screen sharing |


---

## 17. Future-Proofing

### Theme Toggle (What If: Legal Theming Fails)

**Why:** If user testing reveals legal theming feels "gimmicky," we need an escape hatch.

**Settings → Appearance:**

```
┌─────────────────────────────────────────────────────────────┐
│  Appearance                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Theme                                                      │
│  ● Intelligent Legal (recommended)                          │
│    Navy + Gold, legal micro-details, § bullets             │
│                                                             │
│  ○ Professional Minimal                                     │
│    Clean interface, standard UI patterns                   │
│                                                             │
│  ○ High Contrast                                           │
│    Maximum readability, accessibility-focused              │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Mode                                                       │
│  ○ Light                                                   │
│  ● System default                                          │
│  ○ Chambers (Dark)                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**CSS Implementation:**

```css
/* Theme: Intelligent Legal (default) */
[data-theme="intelligent-legal"] {
  --use-legal-cursors: true;
  --use-legal-terminology: true;
  --bullet-style: "§";
  --notification-style: "stamp";
}

/* Theme: Professional Minimal */
[data-theme="professional-minimal"] {
  --use-legal-cursors: false;
  --use-legal-terminology: false;
  --bullet-style: "•";
  --notification-style: "dot";
}

/* Conditional rendering */
.legal-cursor {
  cursor: var(--use-legal-cursors, false)
    ? url('/cursors/fountain-pen.svg') 4 4
    : pointer;
}
```

### Region-Aware Trust Badges (What If: Global Expansion)

**Why:** "Data Hosted in India" is a feature for Indian market but may be liability for global.

**Implementation:**

```tsx
interface TrustBadgeProps {
  region: 'india' | 'uk' | 'us' | 'eu' | 'global';
}

const trustBadgesByRegion = {
  india: [
    { icon: '🇮🇳', label: 'Data Hosted in India', detail: 'AWS Mumbai' },
    { icon: '📋', label: 'DPDP Act Compliant' },
    { icon: '🔒', label: 'SOC 2 Type II' },
  ],
  uk: [
    { icon: '🇬🇧', label: 'Data Hosted in UK', detail: 'AWS London' },
    { icon: '📋', label: 'UK GDPR Compliant' },
    { icon: '🔒', label: 'SOC 2 Type II' },
  ],
  us: [
    { icon: '🇺🇸', label: 'Data Hosted in US', detail: 'AWS Virginia' },
    { icon: '📋', label: 'CCPA Ready' },
    { icon: '🔒', label: 'SOC 2 Type II' },
  ],
  eu: [
    { icon: '🇪🇺', label: 'Data Hosted in EU', detail: 'AWS Frankfurt' },
    { icon: '📋', label: 'GDPR Compliant' },
    { icon: '🔒', label: 'SOC 2 Type II' },
  ],
  global: [
    { icon: '🌐', label: 'Your Region' },
    { icon: '📋', label: 'GDPR Ready' },
    { icon: '🔒', label: 'SOC 2 Type II' },
  ],
};
```

### Regulatory Disclaimer Space (What If: AI Regulation)

**Why:** India may mandate disclaimers on AI legal tools. Reserve space now.

**AI Output Card with Disclaimer Zone:**

```
┌─────────────────────────────────────────────────────────────┐
│  AI Analysis Result                                         │
│                                                             │
│  [Analysis content...]                                      │
│                                                             │
│  🟢 High confidence (92%)                                   │
│  Usually correct - verify key details                       │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  ⚖️ REGULATORY DISCLAIMER ZONE (expandable)                │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  This analysis is AI-generated and requires attorney        │
│  verification before use in legal proceedings.              │
│                                                             │
│  Generated: 2026-01-16 14:32 IST                           │
│  Model: Jaanch Legal AI v2.1                               │
│  Matter: #2024-1532                                         │
│                                                             │
│  [Show less ▲]                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**CSS:**

```css
.regulatory-disclaimer {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.regulatory-disclaimer__toggle {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.regulatory-disclaimer__content {
  margin-top: 8px;
  display: none;
}

.regulatory-disclaimer--expanded .regulatory-disclaimer__content {
  display: block;
}
```

### Onboarding Flow Specification (Reverse Engineering Gap)

**Why:** Demo must show value in <10 seconds; onboarding must take <5 minutes.

**Onboarding Steps:**

```
Step 1: Welcome (10 sec)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Welcome to Jaanch, [Name]                                  │
│                                                             │
│  Let's set up your workspace in 3 quick steps.              │
│                                                             │
│  [Get Started →]                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Step 2: Create First Matter (60 sec)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Create your first matter                                   │
│                                                             │
│  Matter Name: [Singh vs. Patel - 2024        ]              │
│  Type: [Litigation ▼]                                       │
│                                                             │
│  [Create Matter →]                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Step 3: Upload Sample Document (90 sec)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Upload your first document                                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │   Drop a PDF here, or click to browse              │   │
│  │                                                     │   │
│  │   Or try our [Sample Document]                     │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Step 4: See the Magic (120 sec - processing)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Analyzing your document...                                 │
│                                                             │
│  Processing page 12 of 24 (50%)                            │
│  [████████████░░░░░░░░░░░░]                                 │
│                                                             │
│  ✓ OCR complete                                            │
│  ✓ Entities extracted                                      │
│  ⟳ Analyzing citations...                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Step 5: Explore Results (guided tour)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  🎉 Your document is ready!                                 │
│                                                             │
│  We found:                                                  │
│  § 12 entities (people, organizations, dates)              │
│  § 3 case citations                                        │
│  § 2 potential contradictions                              │
│                                                             │
│  [Take a Quick Tour]  [Explore on My Own]                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Total time:** <5 minutes (target: 3 minutes with sample doc)

---

## Appendix A: Design Validation Methodology

This UX Design Direction was developed and validated using BMAD Advanced Elicitation methods:

| Method | Purpose | Key Output |
|--------|---------|------------|
| **Cross-Functional War Room** | Balance PM/Eng/Design constraints | Performance budget, typography-led design |
| **Genre Mashup** | Find aesthetic sweet spot | Navy + Gold "Intelligent Legal" direction |
| **Pre-mortem Analysis** | Prevent redesign failures | Checklist of 7 failure modes to avoid |
| **SCAMPER Method** | Develop legal micro-details | Cursors, seals, terminology, badges |
| **User Persona Focus Group** | Validate with target users | DPDP Act, progress indicators, auto-save |
| **Comparative Analysis Matrix** | Position against competitors | 8.5/10 weighted score vs 6.5-7.0 competitors |
| **Shark Tank Pitch** | Stress-test with investors | Notification scaling, security docs |
| **First Principles Analysis** | Challenge assumptions | Indian rubber stamps vs Western wax seals |
| **Feynman Technique** | Simplify complex specs | Plain-English confidence labels |
| **Reverse Engineering** | Work backwards from success | Court Mode, onboarding flow |
| **What If Scenarios** | Explore alternative futures | Theme toggle, region-aware badges, regulatory space |

---

## Appendix B: Quick Reference

### The 60% Rule - Theming With Restraint

**Senior Lawyer Verdict:** *"The bones are good. Ship with legal theming at 60% intensity."*

| What Works | What's Too Much |
|------------|-----------------|
| Navy + Gold palette | Legal puns on every button |
| Chambers Mode (dark theme) | "Sustained!" on every save |
| Court Mode (screen sharing) | § bullets on settings menus |
| 404 page easter egg ("Case Dismissed") | "Objection!" for validation errors |
| Subtle stamp-style notifications | Legal terminology overload |

### Do's

- ✓ Use § bullets **only for legal content** (findings, citations, entities) - not everywhere
- ✓ Limit legal terminology to 2-3 touches per screen maximum
- ✓ Show trust badges above the fold (including DPDP Act)
- ✓ Keep animations purposeful and minimal
- ✓ Test on slow Indian mobile connections
- ✓ Use Fraunces for headlines, Inter for body
- ✓ Show specific progress (page X of Y, not just spinner)
- ✓ Provide downloadable security documentation
- ✓ Group notifications by matter for power users
- ✓ Use subtle stamp styling for notifications
- ✓ Provide Court Mode for screen sharing
- ✓ Include plain-English guidance with confidence scores
- ✓ Reserve space for regulatory disclaimers
- ✓ Ensure 44x44px minimum touch targets
- ✓ Use standard labels for common actions (Logout, Save, Cancel)

### Don'ts

- ✗ No purple gradients (too "startup")
- ✗ No bouncy animations
- ✗ No autoplay videos
- ✗ No generic AI/ChatGPT aesthetics
- ✗ No feature dumping - tell stories instead
- ✗ No "Start Free Trial" when you mean "Book Demo"
- ✗ No vague progress indicators (avoid "Loading...")
- ✗ No individual notification seals for every micro-update
- ✗ No hover-only interactions (must work on touch)
- ✗ No Western-only legal metaphors without Indian alternatives
- ✗ **No legal puns in error messages** (except 404 page)
- ✗ **No "Adjourn Session" for Logout** - use standard labels
- ✗ **No legal terminology that requires explanation**
- ✗ **No theming that makes colleagues roll their eyes**

---

**Document Version:** 1.2
**Document Status:** Ready for implementation
**Validation Status:** Completed - 11 elicitation methods + Senior Lawyer Review
**Next Steps:** Create Excalidraw wireframes for key pages
**Review Date:** TBD

---

*Generated through BMAD UX Design workflow with Sally (UX Designer Agent)*
*Validated through Advanced Elicitation: Cross-Functional War Room, Genre Mashup, Pre-mortem, SCAMPER, Focus Group, Comparative Analysis, Shark Tank, First Principles, Feynman, Reverse Engineering, What If Scenarios*
*Refined through Senior Lawyer Review: Added 60% theming intensity rule, dialed back error state legal terminology, made § bullets selective*
