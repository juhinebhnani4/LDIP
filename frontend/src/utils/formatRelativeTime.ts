/**
 * Format Relative Time Utility
 *
 * Formats timestamps into human-readable relative time strings.
 * Used by ActivityFeed and other components for timestamp display.
 */

// Time constants in milliseconds for readability
const MS_PER_SECOND = 1000;
const MS_PER_MINUTE = MS_PER_SECOND * 60;
const MS_PER_HOUR = MS_PER_MINUTE * 60;
const MS_PER_DAY = MS_PER_HOUR * 24;
const MS_PER_WEEK = MS_PER_DAY * 7;

/**
 * Format a date into a relative time string.
 *
 * @param date - Date to format (Date object, ISO string, or timestamp)
 * @param referenceDate - Reference date to compare against (defaults to now)
 * @returns Human-readable relative time string
 *
 * @example
 * formatRelativeTime(new Date()) // "Just now"
 * formatRelativeTime(new Date(Date.now() - 5 * 60000)) // "5 minutes ago"
 * formatRelativeTime(new Date(Date.now() - 2 * 3600000)) // "2 hours ago"
 * formatRelativeTime(new Date(Date.now() - 86400000)) // "Yesterday"
 */
export function formatRelativeTime(
  date: Date | string | number,
  referenceDate: Date = new Date()
): string {
  // Parse the input date
  const targetDate = date instanceof Date ? date : new Date(date);

  // Handle invalid dates
  if (isNaN(targetDate.getTime())) {
    return 'Invalid date';
  }

  const diffMs = referenceDate.getTime() - targetDate.getTime();

  // Handle future dates
  if (diffMs < 0) {
    return formatFutureTime(Math.abs(diffMs));
  }

  // Just now (less than 1 minute)
  if (diffMs < MS_PER_MINUTE) {
    return 'Just now';
  }

  // Minutes ago (1-59 minutes)
  if (diffMs < MS_PER_HOUR) {
    const minutes = Math.floor(diffMs / MS_PER_MINUTE);
    return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`;
  }

  // Hours ago (1-23 hours)
  if (diffMs < MS_PER_DAY) {
    const hours = Math.floor(diffMs / MS_PER_HOUR);
    return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
  }

  // Yesterday (24-47 hours, same calendar day logic)
  if (diffMs < MS_PER_DAY * 2) {
    const targetDay = targetDate.getDate();
    const referenceDay = referenceDate.getDate();
    if (targetDay !== referenceDay) {
      return 'Yesterday';
    }
  }

  // Days ago (2-6 days)
  if (diffMs < MS_PER_WEEK) {
    const days = Math.floor(diffMs / MS_PER_DAY);
    return days === 1 ? 'Yesterday' : `${days} days ago`;
  }

  // Older than a week - show formatted date
  return formatDate(targetDate);
}

/**
 * Format future time (for scheduled activities).
 */
function formatFutureTime(diffMs: number): string {
  if (diffMs < MS_PER_MINUTE) {
    return 'In a moment';
  }

  if (diffMs < MS_PER_HOUR) {
    const minutes = Math.floor(diffMs / MS_PER_MINUTE);
    return minutes === 1 ? 'In 1 minute' : `In ${minutes} minutes`;
  }

  if (diffMs < MS_PER_DAY) {
    const hours = Math.floor(diffMs / MS_PER_HOUR);
    return hours === 1 ? 'In 1 hour' : `In ${hours} hours`;
  }

  const days = Math.floor(diffMs / MS_PER_DAY);
  return days === 1 ? 'Tomorrow' : `In ${days} days`;
}

/**
 * Format a date as a localized short date string.
 */
function formatDate(date: Date): string {
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
  });
}

/**
 * Format a date as a time string (for grouping activities by time of day).
 *
 * @param date - Date to format
 * @returns Formatted time string (e.g., "8:02 AM")
 */
export function formatTime(date: Date | string | number): string {
  const targetDate = date instanceof Date ? date : new Date(date);

  if (isNaN(targetDate.getTime())) {
    return 'Invalid time';
  }

  return targetDate.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Get the day group label for an activity (Today, Yesterday, or date).
 *
 * @param date - Date to get group label for
 * @param referenceDate - Reference date for comparison
 * @returns Group label string
 */
export function getDayGroupLabel(
  date: Date | string | number,
  referenceDate: Date = new Date()
): string {
  const targetDate = date instanceof Date ? date : new Date(date);

  if (isNaN(targetDate.getTime())) {
    return 'Invalid date';
  }

  // Normalize to start of day for comparison
  const targetDay = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate());
  const referenceDay = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate()
  );

  const diffDays = Math.floor((referenceDay.getTime() - targetDay.getTime()) / MS_PER_DAY);

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return targetDate.toLocaleDateString(undefined, { weekday: 'long' });

  return formatDate(targetDate);
}
