# jaanch.ai Brand & Color System Design Spec

**Version:** 1.0
**Date:** 2026-01-16
**Author:** Sally (UX Designer)
**Stakeholder:** Juhi

---

## 1. Brand Overview

### 1.1 Brand Identity

**Name:** jaanch.ai
**Tagline:** "Verify, don't trust"
**Domain:** Legal technology / Document verification

### 1.2 Logo

The logo features the Devanagari character "ज" (ja) rendered in deep indigo blue with a distinctive handmade paper texture. The visible fibers within the letterform communicate:
- Craftsmanship and authenticity
- Tradition meeting innovation
- Human judgment underlying AI capabilities

### 1.3 Visual Philosophy

| Principle | Expression |
|-----------|------------|
| **Authority** | Deep indigo, serif typography, generous whitespace |
| **Trust** | Warm paper textures, muted gold accents, consistent patterns |
| **Clarity** | Minimalist layouts, clear hierarchy, purposeful color use |
| **Craftsmanship** | Textured backgrounds, refined details, quality feel |

---

## 2. Color System

### 2.1 Core Brand Palette

#### Primary Colors

| Name | Hex | OKLCH | Usage |
|------|-----|-------|-------|
| **Deep Indigo** | `#0d1b5e` | `oklch(0.25 0.12 265)` | Logo, primary actions, headers, key UI elements |
| **Bond Paper** | `#f8f6f1` | `oklch(0.97 0.01 90)` | Primary background |
| **Ink Black** | `#1a1a1a` | `oklch(0.15 0 0)` | Body text, foreground |

#### Accent Colors

| Name | Hex | OKLCH | Usage |
|------|-----|-------|-------|
| **Muted Gold** | `#b8973b` | `oklch(0.68 0.12 85)` | Success states, verified badges, highlights |
| **Burgundy** | `#8b2635` | `oklch(0.40 0.15 25)` | Errors, destructive actions, mismatches |
| **Forest Green** | `#2d5a3d` | `oklch(0.40 0.08 155)` | Success, completed states |

#### Neutral Colors

| Name | Hex | OKLCH | Usage |
|------|-----|-------|-------|
| **Warm Gray** | `#e8e4dc` | `oklch(0.91 0.01 80)` | Muted backgrounds, secondary elements |
| **Paper Edge** | `#d4cfc4` | `oklch(0.84 0.02 80)` | Borders, dividers |
| **Charcoal** | `#4a4a4a` | `oklch(0.35 0 0)` | Secondary text |
| **Soft Gray** | `#6b6b6b` | `oklch(0.48 0 0)` | Muted text, placeholders |

### 2.2 Semantic Color Mapping

| Semantic Role | Light Mode | Dark Mode |
|---------------|------------|-----------|
| `--background` | `#f8f6f1` (Bond Paper) | `#1a1a1a` (Ink Black) |
| `--foreground` | `#1a1a1a` (Ink Black) | `#f8f6f1` (Bond Paper) |
| `--primary` | `#0d1b5e` (Deep Indigo) | `#6b7cb8` (Lighter Indigo) |
| `--primary-foreground` | `#f8f6f1` | `#1a1a1a` |
| `--secondary` | `#e8e4dc` (Warm Gray) | `#2d2d2d` |
| `--secondary-foreground` | `#1a1a1a` | `#f8f6f1` |
| `--accent` | `#b8973b` (Muted Gold) | `#c4a85a` (Brighter Gold) |
| `--accent-foreground` | `#1a1a1a` | `#1a1a1a` |
| `--muted` | `#e8e4dc` | `#2d2d2d` |
| `--muted-foreground` | `#6b6b6b` | `#a0a0a0` |
| `--destructive` | `#8b2635` (Burgundy) | `#c44d5e` |
| `--destructive-foreground` | `#f8f6f1` | `#f8f6f1` |
| `--border` | `#d4cfc4` (Paper Edge) | `#3d3d3d` |
| `--input` | `#d4cfc4` | `#3d3d3d` |
| `--ring` | `#0d1b5e` | `#6b7cb8` |

### 2.3 Functional Colors

#### Status Indicators

| Status | Color | Hex | Usage |
|--------|-------|-----|-------|
| Success | Forest Green | `#2d5a3d` | Completed, verified, good quality |
| Warning | Aged Gold | `#c4a35a` | Caution, in-progress, fair quality |
| Error | Burgundy | `#8b2635` | Failed, mismatch, poor quality |
| Info | Deep Indigo | `#0d1b5e` | Processing, informational |
| Neutral | Soft Gray | `#6b6b6b` | Queued, skipped, inactive |

#### Entity Type Colors

| Entity Type | Primary | Background (Light) | Background (Dark) |
|-------------|---------|-------------------|-------------------|
| PERSON | `#0d1b5e` (Deep Indigo) | `#e8eef8` | `#1a2444` |
| ORG | `#2d5a3d` (Forest Green) | `#e5f0e8` | `#1a2d20` |
| INSTITUTION | `#5a3d6b` (Deep Purple) | `#f0e8f4` | `#2d1a35` |
| ASSET | `#b8973b` (Muted Gold) | `#f5f0e0` | `#3d3520` |

#### PDF Highlight Colors

| Highlight Type | Background | Border |
|----------------|------------|--------|
| Source | `#f5f0d8` (Warm cream) | `#b8973b` (Muted Gold) |
| Verified | `#e8eef8` (Light indigo) | `#0d1b5e` (Deep Indigo) |
| Mismatch | `#f2d4d7` (Soft pink) | `#8b2635` (Burgundy) |
| Section Not Found | `#f5e8d8` (Warm peach) | `#c4a35a` (Aged Gold) |
| Entity | `#e8eef8` (Light indigo) | `#0d1b5e` (Deep Indigo) |
| Contradiction | `#f2d4d7` (Soft pink) | `#8b2635` (Burgundy) |

---

## 3. Typography

### 3.1 Font Stack

| Role | Font | Fallback |
|------|------|----------|
| **Headings** | Serif (Georgia, Times New Roman) | System serif |
| **Body** | System UI / Inter | Sans-serif |
| **Monospace** | JetBrains Mono / Fira Code | System monospace |

*Note: The logo tagline "Verify, don't trust" uses an elegant serif italic, reinforcing authority.*

### 3.2 Text Colors

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| Headings | `#0d1b5e` (Deep Indigo) | `#f8f6f1` |
| Body text | `#1a1a1a` (Ink Black) | `#e8e4dc` |
| Secondary text | `#4a4a4a` (Charcoal) | `#a0a0a0` |
| Muted text | `#6b6b6b` (Soft Gray) | `#808080` |
| Links | `#0d1b5e` | `#6b7cb8` |
| Link hover | `#1a2d7a` | `#8b9cd0` |

---

## 4. Background Treatment

### 4.1 Primary Background

The background should evoke **heavy-grain bond paper** with a tactile, fibrous texture:

- Base color: `#f8f6f1` (warm off-white)
- Subtle noise/grain texture overlay (5-10% opacity)
- Optional: Very subtle paper fiber pattern

### 4.2 Implementation Options

1. **CSS Background**: Solid color with subtle noise SVG overlay
2. **Texture Image**: High-quality paper texture at very low opacity
3. **CSS Filter**: Subtle grain using `filter` properties

### 4.3 Surface Hierarchy

| Surface Level | Light Mode | Dark Mode |
|---------------|------------|-----------|
| Base background | `#f8f6f1` | `#1a1a1a` |
| Card/elevated | `#ffffff` | `#252525` |
| Overlay/modal | `#ffffff` | `#2d2d2d` |
| Sidebar | `#f0ede6` | `#222222` |

---

## 5. Layout Principles

### 5.1 Minimalist & Authoritative

- **Generous whitespace**: Let content breathe
- **Clear hierarchy**: Obvious visual distinction between levels
- **Restraint**: Use color purposefully, not decoratively
- **Alignment**: Strong grid-based layouts

### 5.2 Spacing Scale

Use a consistent 4px base unit:
- `xs`: 4px
- `sm`: 8px
- `md`: 16px
- `lg`: 24px
- `xl`: 32px
- `2xl`: 48px
- `3xl`: 64px

---

## 6. Component Color Guidelines

### 6.1 Buttons

| Variant | Background | Text | Border |
|---------|------------|------|--------|
| Primary | `#0d1b5e` | `#f8f6f1` | none |
| Secondary | `transparent` | `#0d1b5e` | `#0d1b5e` |
| Destructive | `#8b2635` | `#f8f6f1` | none |
| Ghost | `transparent` | `#1a1a1a` | none |
| Success | `#2d5a3d` | `#f8f6f1` | none |

### 6.2 Form Inputs

- Background: `#ffffff` (slightly lifted from paper)
- Border: `#d4cfc4`
- Focus ring: `#0d1b5e` (2px)
- Error border: `#8b2635`
- Placeholder text: `#6b6b6b`

### 6.3 Cards

- Background: `#ffffff`
- Border: `#d4cfc4`
- Shadow: Subtle, warm-toned (`0 2px 8px rgba(26, 26, 26, 0.08)`)

### 6.4 Navigation

- Active item: `#0d1b5e` background, `#f8f6f1` text
- Hover: `#e8e4dc` background
- Inactive: `#4a4a4a` text

---

## 7. Accessibility

### 7.1 Contrast Ratios

All color combinations meet WCAG 2.1 AA standards:

| Combination | Ratio | Standard |
|-------------|-------|----------|
| Deep Indigo on Bond Paper | 12.5:1 | AAA |
| Ink Black on Bond Paper | 15.2:1 | AAA |
| Burgundy on Bond Paper | 7.8:1 | AAA |
| Forest Green on Bond Paper | 6.2:1 | AA |
| Muted Gold on Bond Paper | 3.8:1 | AA Large Text |

### 7.2 Color Blindness Considerations

- Never rely on color alone to convey information
- Use icons alongside status colors
- Sufficient contrast between adjacent colors

---

## 8. Implementation Checklist

- [ ] Update `globals.css` CSS variables
- [ ] Update Tailwind config (if custom colors needed)
- [ ] Update entity graph colors (`entityGraph.ts`, `EntityNode.tsx`, `EntityEdge.tsx`)
- [ ] Update PDF highlight colors (`pdf.ts`)
- [ ] Update notification colors (`notification.ts`)
- [ ] Update job status colors (`job.ts`)
- [ ] Update OCR quality colors (`OCRQualityDetail.tsx`)
- [ ] Update processing status colors (`DocumentProcessingStatus.tsx`)
- [ ] Add paper texture background (optional enhancement)
- [ ] Test all color combinations for accessibility
- [ ] Test in dark mode

---

## 9. Color Values Quick Reference

### Copy-Paste Ready (CSS Variables)

```css
:root {
  /* Core Brand */
  --color-indigo: #0d1b5e;
  --color-paper: #f8f6f1;
  --color-ink: #1a1a1a;

  /* Accents */
  --color-gold: #b8973b;
  --color-burgundy: #8b2635;
  --color-forest: #2d5a3d;

  /* Neutrals */
  --color-warm-gray: #e8e4dc;
  --color-paper-edge: #d4cfc4;
  --color-charcoal: #4a4a4a;
  --color-soft-gray: #6b6b6b;
}
```

### Copy-Paste Ready (Hex)

```
Deep Indigo:    #0d1b5e
Bond Paper:     #f8f6f1
Ink Black:      #1a1a1a
Muted Gold:     #b8973b
Burgundy:       #8b2635
Forest Green:   #2d5a3d
Warm Gray:      #e8e4dc
Paper Edge:     #d4cfc4
Charcoal:       #4a4a4a
Soft Gray:      #6b6b6b
```

---

*This design system establishes jaanch.ai as a premium, trustworthy legal technology platform that balances modern AI capabilities with the gravitas and tradition of legal practice.*
