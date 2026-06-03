/**
 * `@/lib/format` — the canonical presentation/format layer for the LDIP frontend.
 *
 * This module is the wall for **FE-ARCH-04** (no presentation layer). Until
 * this file existed, date formatting was done ad hoc at 55+ call sites (each
 * with its own locale and options), there were 8 separate `formatDate`
 * implementations across components, and pluralization was hand-rolled as an
 * inline `count === 1 ? 's' : ''` ternary at 80+ call sites (4 of which
 * silently rendered "1 documents" / "1 pages").
 *
 * Rules of this layer (enforced as ESLint warnings in `eslint.config.mjs`):
 *
 * 1. **No raw `toLocaleDateString` / `toLocaleTimeString` / `Intl.DateTimeFormat`
 *    in components** — import a function from here instead.
 * 2. **No new `formatDate` definitions in feature files** — extend this module.
 * 3. **No inline pluralization ternaries** — use `pluralize` / `formatCount`.
 *
 * Implementation notes:
 * - Date library: `date-fns` (already in the codebase via the timeline module).
 *   Do not introduce a second one.
 * - Locale: default. Pass an explicit option only when the caller has a real
 *   reason (e.g. India-style long form for legal documents → `formatDateLong`).
 * - Invalid dates return the `fallback` argument (default empty string) so
 *   callers never have to wrap in try/catch.
 *
 * Migration status (B4.3, 2026-05-26): this file lands as **Phase 1** alongside
 * an ESLint rule shipped as `warn`. Phase 2 (bulk-migrate the existing 8
 * formatDate impls + 55 Intl call sites + 87 count strings, then flip the rule
 * to `error`) is tracked in BUGS.md §10 FE-015 / FE-016 / FE-017.
 */

import {
  format,
  differenceInCalendarDays,
  isValid,
} from 'date-fns'

// ----- types --------------------------------------------------------------- #

export type DateInput = Date | string | number

// ----- internals ----------------------------------------------------------- #

/** Convert any accepted input to a Date, or null if invalid. */
function toDate(input: DateInput | null | undefined): Date | null {
  if (input == null) return null
  const d = input instanceof Date ? input : new Date(input)
  return isValid(d) ? d : null
}

// Time constants in milliseconds (used by formatRelative). Inline rather than
// pulling date-fns's heavier formatDistanceToNow which produces strings with
// different cadence than the existing UI ("Just now" / "Yesterday" boundaries).
const MS_PER_MINUTE = 60 * 1000
const MS_PER_HOUR = 60 * MS_PER_MINUTE
const MS_PER_DAY = 24 * MS_PER_HOUR
const MS_PER_WEEK = 7 * MS_PER_DAY

// ----- date formatters ----------------------------------------------------- #

/**
 * "Jan 15, 2025" — short date. The default. Replaces ~7 of the 8 hand-rolled
 * `formatDate` impls in the codebase.
 */
export function formatDate(input: DateInput | null | undefined, fallback = ''): string {
  const d = toDate(input)
  return d ? format(d, 'MMM d, yyyy') : fallback
}

/**
 * "Jan 15, 2025, 3:45 PM" — date with time. Used by VerificationBadge,
 * FailedJobCard, etc. for tooltips and timestamps.
 */
export function formatDateTime(input: DateInput | null | undefined, fallback = ''): string {
  const d = toDate(input)
  return d ? format(d, 'MMM d, yyyy, h:mm a') : fallback
}

/**
 * "15 January 2025" — long form, used by `CurrentStatusSection` for legal-
 * document-style dates. Locale-independent (uses date-fns English month names).
 */
export function formatDateLong(input: DateInput | null | undefined, fallback = ''): string {
  const d = toDate(input)
  return d ? format(d, 'd MMMM yyyy') : fallback
}

/** "Jan 2025" — month + year. Used by `TimelineHeader` and chart axes. */
export function formatMonth(input: DateInput | null | undefined, fallback = ''): string {
  const d = toDate(input)
  return d ? format(d, 'MMM yyyy') : fallback
}

/** "8:02 AM" — time only. Used by ActivityFeed grouping. */
export function formatTime(input: DateInput | null | undefined, fallback = ''): string {
  const d = toDate(input)
  return d ? format(d, 'h:mm a') : fallback
}

// ----- relative-time helpers ----------------------------------------------- #

/**
 * "Just now" / "5 minutes ago" / "Yesterday" / "Apr 30, 2026" / "Apr 30, 2024".
 *
 * Migrated from `frontend/src/utils/formatRelativeTime.ts` (which is now a
 * back-compat shim that re-exports from here). Behavior preserved exactly so
 * the existing 4 callers keep rendering identical strings.
 *
 * - <1 minute → "Just now"
 * - <1 hour → "N minute(s) ago"
 * - <1 day → "N hour(s) ago"
 * - <2 days, different calendar day → "Yesterday"
 * - <1 week → "N days ago"
 * - older → falls through to a compact-date format ("Jan 15" if this year,
 *   "Jan 15, 2024" otherwise)
 *
 * Future dates → "In N minutes" / "Tomorrow" / "In N days".
 */
export function formatRelative(
  input: DateInput | null | undefined,
  referenceDate: Date = new Date(),
): string {
  const target = toDate(input)
  if (!target) return 'Invalid date'

  const diffMs = referenceDate.getTime() - target.getTime()
  if (diffMs < 0) return formatFutureTime(Math.abs(diffMs))

  if (diffMs < MS_PER_MINUTE) return 'Just now'

  if (diffMs < MS_PER_HOUR) {
    const minutes = Math.floor(diffMs / MS_PER_MINUTE)
    return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`
  }

  if (diffMs < MS_PER_DAY) {
    const hours = Math.floor(diffMs / MS_PER_HOUR)
    return hours === 1 ? '1 hour ago' : `${hours} hours ago`
  }

  if (diffMs < MS_PER_DAY * 2 && target.getDate() !== referenceDate.getDate()) {
    return 'Yesterday'
  }

  if (diffMs < MS_PER_WEEK) {
    const days = Math.floor(diffMs / MS_PER_DAY)
    return days === 1 ? 'Yesterday' : `${days} days ago`
  }

  // Older than a week — show a compact date. "Jan 15" if this year, else
  // include the year.
  if (target.getFullYear() === referenceDate.getFullYear()) {
    return format(target, 'MMM d')
  }
  return format(target, 'MMM d, yyyy')
}

function formatFutureTime(diffMs: number): string {
  if (diffMs < MS_PER_MINUTE) return 'In a moment'
  if (diffMs < MS_PER_HOUR) {
    const minutes = Math.floor(diffMs / MS_PER_MINUTE)
    return minutes === 1 ? 'In 1 minute' : `In ${minutes} minutes`
  }
  if (diffMs < MS_PER_DAY) {
    const hours = Math.floor(diffMs / MS_PER_HOUR)
    return hours === 1 ? 'In 1 hour' : `In ${hours} hours`
  }
  const days = Math.floor(diffMs / MS_PER_DAY)
  return days === 1 ? 'Tomorrow' : `In ${days} days`
}

/**
 * "Today" / "Yesterday" / weekday name (within the past week) / compact date.
 * Used by ActivityFeed to group activities by day.
 */
export function getDayGroupLabel(
  input: DateInput | null | undefined,
  referenceDate: Date = new Date(),
): string {
  const target = toDate(input)
  if (!target) return 'Invalid date'

  const diffDays = differenceInCalendarDays(referenceDate, target)
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays > 0 && diffDays < 7) return format(target, 'EEEE')
  return formatDate(target)
}

// ----- count / pluralization ----------------------------------------------- #

/**
 * Return the correct singular or plural form based on `count`.
 *
 * @example
 *   pluralize(1, 'document')            // 'document'
 *   pluralize(2, 'document')            // 'documents'
 *   pluralize(1, 'citation', 'citations')  // 'citation'
 *   pluralize(0, 'matter')              // 'matters' (English convention: 0 is plural)
 *   pluralize(1, 'analysis', 'analyses')   // 'analysis'
 */
export function pluralize(count: number, singular: string, plural?: string): string {
  if (count === 1) return singular
  return plural ?? singular + 's'
}

/**
 * Format a count with a noun: thousands separator + correct pluralization.
 *
 * @example
 *   formatCount(1, 'document')       // '1 document'
 *   formatCount(3, 'document')       // '3 documents'
 *   formatCount(1234, 'document')    // '1,234 documents'
 *   formatCount(1, 'citation', 'citations')  // '1 citation'
 *   formatCount(0, 'result')         // '0 results'
 *
 * This is the canonical replacement for the 80+ inline templates like
 * `` `${count} ${count === 1 ? 'document' : 'documents'}` `` and the four
 * acute hardcoded-plural bugs in FE-015 (`"${pageCount} pages"`,
 * `"${docs.length} documents"`).
 */
export function formatCount(count: number, singular: string, plural?: string): string {
  return `${count.toLocaleString()} ${pluralize(count, singular, plural)}`
}
