/**
 * Jaanch Design Tokens
 * From UX Design Document v1.2 - "Intelligent Legal" Theme
 *
 * These tokens provide TypeScript constants for use in components
 * where CSS variables aren't practical (e.g., canvas rendering, SVGs).
 *
 * IMPORTANT: Keep in sync with globals.css
 */

// =============================================================================
// COLOR PALETTE
// =============================================================================

export const colors = {
  // Primary palette
  primary: {
    navy: '#1a2744',      // Deep Navy - headers, buttons, navigation
    navyHover: '#2a3a5c', // Navy hover state
    navyLight: '#3d4f6f', // Light navy for subtle backgrounds
  },

  // Accent
  accent: {
    gold: '#c9a227',      // Warm Gold - CTAs, highlights, selected states
    goldHover: '#b89220', // Gold hover state
    goldLight: '#f5e6b8', // Light gold for backgrounds
  },

  // Backgrounds
  background: {
    page: '#f8f6f2',      // Soft Cream - page backgrounds
    surface: '#ffffff',   // Pure White - cards, modals
    elevated: '#ffffff',  // Elevated surfaces
  },

  // Text
  text: {
    primary: '#2d3748',   // Charcoal - body copy
    secondary: '#64748b', // Slate - captions, helper text
    muted: '#94a3b8',     // Muted text
    inverse: '#ffffff',   // Text on dark backgrounds
  },

  // Semantic colors
  success: '#166534',     // Legal Green - confirmations
  warning: '#d97706',     // Amber - warnings
  error: '#dc2626',       // Error Red
  info: '#3b82f6',        // Steel Blue - informational

  // Borders
  border: {
    default: '#e5e2dd',   // Warm Gray - dividers
    strong: '#d1cdc6',    // Stronger border
  },

  // Special legal accents
  legal: {
    sealRed: '#8b0000',   // Dark red for stamps/seals
    legalPad: '#fffef0',  // Yellow legal pad color
  },

  // Dark mode (Chambers Mode)
  dark: {
    background: '#1a1a1f',
    surface: '#25252d',
    text: '#e5e5e7',
    textMuted: '#9ca3af',
    border: '#3d3d47',
    accentGold: '#dbb536', // Brighter gold for dark mode
  },
} as const

// =============================================================================
// CONFIDENCE BADGES
// =============================================================================

export const confidenceLevels = {
  high: {
    threshold: 90,
    color: colors.success,
    bgColor: '#dcfce7',
    label: 'High',
    guidance: 'Usually correct - verify key details',
  },
  moderate: {
    threshold: 70,
    color: colors.warning,
    bgColor: '#fef3c7',
    label: 'Moderate',
    guidance: 'Review carefully - cross-check before using',
  },
  low: {
    threshold: 0,
    color: colors.error,
    bgColor: '#fee2e2',
    label: 'Low',
    guidance: 'Needs verification - attorney review required',
  },
} as const

export function getConfidenceLevel(score: number) {
  if (score >= confidenceLevels.high.threshold) return confidenceLevels.high
  if (score >= confidenceLevels.moderate.threshold) return confidenceLevels.moderate
  return confidenceLevels.low
}

// =============================================================================
// ENTITY TYPE COLORS
// =============================================================================

export const entityColors = {
  PERSON: {
    bg: '#e0e7ff',        // Light indigo
    text: colors.primary.navy,
    border: '#c7d2fe',
  },
  ORG: {
    bg: '#dcfce7',        // Light green
    text: colors.success,
    border: '#bbf7d0',
  },
  INSTITUTION: {
    bg: '#f3e8ff',        // Light purple
    text: '#7c3aed',
    border: '#e9d5ff',
  },
  ASSET: {
    bg: colors.accent.goldLight,
    text: '#92400e',
    border: '#fde68a',
  },
  DATE: {
    bg: '#e0f2fe',        // Light blue
    text: '#0369a1',
    border: '#bae6fd',
  },
  LOCATION: {
    bg: '#fce7f3',        // Light pink
    text: '#be185d',
    border: '#fbcfe8',
  },
  DEFAULT: {
    bg: '#f3f4f6',        // Light gray
    text: colors.text.primary,
    border: '#e5e7eb',
  },
} as const

// =============================================================================
// NOTIFICATION PRIORITIES
// =============================================================================

export const notificationPriority = {
  critical: {
    sealColor: colors.error,
    pulse: true,
    popup: true,
    sound: true, // optional
  },
  high: {
    sealColor: colors.error,
    pulse: false,
    popup: true,
    sound: false,
  },
  medium: {
    sealColor: colors.accent.gold,
    pulse: false,
    popup: false,
    sound: false,
  },
  low: {
    sealColor: '#9ca3af', // Gray
    pulse: false,
    popup: false,
    sound: false,
  },
} as const

// =============================================================================
// TYPOGRAPHY
// =============================================================================

export const typography = {
  fontFamily: {
    sans: 'Inter, system-ui, sans-serif',
    serif: 'Fraunces, Georgia, serif',
    mono: 'JetBrains Mono, monospace',
    legalExport: '"Times New Roman", Times, serif',
  },
  // Font sizes follow Tailwind defaults
  fontSize: {
    xs: '0.75rem',    // 12px
    sm: '0.875rem',   // 14px
    base: '1rem',     // 16px
    lg: '1.125rem',   // 18px
    xl: '1.25rem',    // 20px
    '2xl': '1.5rem',  // 24px
    '3xl': '1.875rem',// 30px
    '4xl': '2.25rem', // 36px
  },
} as const

// =============================================================================
// ANIMATION
// =============================================================================

export const animation = {
  duration: {
    fast: '150ms',
    normal: '200ms',
    slow: '300ms',
  },
  easing: {
    default: 'ease',
    out: 'ease-out',
    in: 'ease-in',
    inOut: 'ease-in-out',
  },
} as const

// =============================================================================
// SPACING & SIZING
// =============================================================================

export const spacing = {
  // Touch target minimum (WCAG 2.5.5)
  touchTarget: '44px',
  // Border radius
  radius: {
    sm: '0.375rem',   // 6px
    md: '0.5rem',     // 8px
    lg: '0.625rem',   // 10px (default)
    xl: '0.75rem',    // 12px
    full: '9999px',   // Pill shape
  },
} as const

// =============================================================================
// Z-INDEX SCALE
// =============================================================================

export const zIndex = {
  dropdown: 50,
  sticky: 100,
  modal: 200,
  popover: 300,
  tooltip: 400,
  toast: 500,
  courtMode: 1000, // Court mode overlay
} as const
