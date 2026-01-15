import { describe, it, expect } from 'vitest';
import { formatRelativeTime, formatTime, getDayGroupLabel } from './formatRelativeTime';

describe('formatRelativeTime', () => {
  // Create a stable reference date for testing
  const referenceDate = new Date('2026-01-15T10:00:00Z');

  describe('past times', () => {
    it('returns "Just now" for times less than 1 minute ago', () => {
      const thirtySecondsAgo = new Date(referenceDate.getTime() - 30 * 1000);
      expect(formatRelativeTime(thirtySecondsAgo, referenceDate)).toBe('Just now');
    });

    it('returns "1 minute ago" for exactly 1 minute ago', () => {
      const oneMinuteAgo = new Date(referenceDate.getTime() - 60 * 1000);
      expect(formatRelativeTime(oneMinuteAgo, referenceDate)).toBe('1 minute ago');
    });

    it('returns "X minutes ago" for times less than 1 hour ago', () => {
      const thirtyMinutesAgo = new Date(referenceDate.getTime() - 30 * 60 * 1000);
      expect(formatRelativeTime(thirtyMinutesAgo, referenceDate)).toBe('30 minutes ago');
    });

    it('returns "1 hour ago" for exactly 1 hour ago', () => {
      const oneHourAgo = new Date(referenceDate.getTime() - 60 * 60 * 1000);
      expect(formatRelativeTime(oneHourAgo, referenceDate)).toBe('1 hour ago');
    });

    it('returns "X hours ago" for times less than 24 hours ago', () => {
      const fiveHoursAgo = new Date(referenceDate.getTime() - 5 * 60 * 60 * 1000);
      expect(formatRelativeTime(fiveHoursAgo, referenceDate)).toBe('5 hours ago');
    });

    it('returns "Yesterday" for times 1-2 days ago', () => {
      const yesterday = new Date(referenceDate.getTime() - 30 * 60 * 60 * 1000);
      expect(formatRelativeTime(yesterday, referenceDate)).toBe('Yesterday');
    });

    it('returns "X days ago" for times 2-6 days ago', () => {
      const threeDaysAgo = new Date(referenceDate.getTime() - 3 * 24 * 60 * 60 * 1000);
      expect(formatRelativeTime(threeDaysAgo, referenceDate)).toBe('3 days ago');
    });

    it('returns formatted date for times older than a week', () => {
      const twoWeeksAgo = new Date(referenceDate.getTime() - 14 * 24 * 60 * 60 * 1000);
      const result = formatRelativeTime(twoWeeksAgo, referenceDate);
      // Should be a formatted date string like "Jan 1"
      expect(result).toContain('Jan');
    });
  });

  describe('future times', () => {
    it('returns "In a moment" for times less than 1 minute in the future', () => {
      const thirtySecondsLater = new Date(referenceDate.getTime() + 30 * 1000);
      expect(formatRelativeTime(thirtySecondsLater, referenceDate)).toBe('In a moment');
    });

    it('returns "In 1 minute" for exactly 1 minute in the future', () => {
      const oneMinuteLater = new Date(referenceDate.getTime() + 60 * 1000);
      expect(formatRelativeTime(oneMinuteLater, referenceDate)).toBe('In 1 minute');
    });

    it('returns "In X minutes" for times less than 1 hour in the future', () => {
      const thirtyMinutesLater = new Date(referenceDate.getTime() + 30 * 60 * 1000);
      expect(formatRelativeTime(thirtyMinutesLater, referenceDate)).toBe('In 30 minutes');
    });

    it('returns "In 1 hour" for exactly 1 hour in the future', () => {
      const oneHourLater = new Date(referenceDate.getTime() + 60 * 60 * 1000);
      expect(formatRelativeTime(oneHourLater, referenceDate)).toBe('In 1 hour');
    });

    it('returns "Tomorrow" for 1 day in the future', () => {
      const tomorrow = new Date(referenceDate.getTime() + 24 * 60 * 60 * 1000);
      expect(formatRelativeTime(tomorrow, referenceDate)).toBe('Tomorrow');
    });

    it('returns "In X days" for more than 1 day in the future', () => {
      const threeDaysLater = new Date(referenceDate.getTime() + 3 * 24 * 60 * 60 * 1000);
      expect(formatRelativeTime(threeDaysLater, referenceDate)).toBe('In 3 days');
    });
  });

  describe('input formats', () => {
    it('accepts Date object', () => {
      const date = new Date(referenceDate.getTime() - 60 * 1000);
      expect(formatRelativeTime(date, referenceDate)).toBe('1 minute ago');
    });

    it('accepts ISO string', () => {
      const isoString = new Date(referenceDate.getTime() - 60 * 1000).toISOString();
      expect(formatRelativeTime(isoString, referenceDate)).toBe('1 minute ago');
    });

    it('accepts timestamp number', () => {
      const timestamp = referenceDate.getTime() - 60 * 1000;
      expect(formatRelativeTime(timestamp, referenceDate)).toBe('1 minute ago');
    });

    it('returns "Invalid date" for invalid date string', () => {
      expect(formatRelativeTime('not-a-date', referenceDate)).toBe('Invalid date');
    });

    it('returns "Invalid date" for NaN timestamp', () => {
      expect(formatRelativeTime(NaN, referenceDate)).toBe('Invalid date');
    });
  });

  describe('edge cases', () => {
    it('uses current time as default reference', () => {
      const justNow = new Date();
      const result = formatRelativeTime(justNow);
      expect(result).toBe('Just now');
    });

    it('handles midnight boundary correctly', () => {
      const midnight = new Date('2026-01-15T00:00:00Z');
      const justBeforeMidnight = new Date('2026-01-14T23:59:00Z');
      expect(formatRelativeTime(justBeforeMidnight, midnight)).toBe('1 minute ago');
    });
  });
});

describe('formatTime', () => {
  it('formats time with hour and minute', () => {
    const morning = new Date('2026-01-15T08:02:00');
    const result = formatTime(morning);
    // Result should contain the hour and minute
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });

  it('handles Date object input', () => {
    const date = new Date();
    date.setHours(14, 30, 0, 0);
    const result = formatTime(date);
    // Should contain formatted time
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });

  it('handles timestamp input', () => {
    const now = new Date();
    now.setHours(9, 15, 0, 0);
    const timestamp = now.getTime();
    const result = formatTime(timestamp);
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });

  it('returns "Invalid time" for invalid input', () => {
    expect(formatTime('not-a-date')).toBe('Invalid time');
  });
});

describe('getDayGroupLabel', () => {
  const referenceDate = new Date('2026-01-15T10:00:00Z');

  it('returns "Today" for same day', () => {
    const today = new Date('2026-01-15T08:00:00Z');
    expect(getDayGroupLabel(today, referenceDate)).toBe('Today');
  });

  it('returns "Yesterday" for previous day', () => {
    const yesterday = new Date('2026-01-14T15:00:00Z');
    expect(getDayGroupLabel(yesterday, referenceDate)).toBe('Yesterday');
  });

  it('returns weekday name for dates within a week', () => {
    const fourDaysAgo = new Date('2026-01-11T10:00:00Z'); // Saturday
    const result = getDayGroupLabel(fourDaysAgo, referenceDate);
    // Should be a weekday name
    expect(result).toMatch(/Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday/);
  });

  it('returns formatted date for dates older than a week', () => {
    const twoWeeksAgo = new Date('2026-01-01T10:00:00Z');
    const result = getDayGroupLabel(twoWeeksAgo, referenceDate);
    expect(result).toContain('Jan');
  });

  it('handles ISO string input', () => {
    expect(getDayGroupLabel('2026-01-15T05:00:00Z', referenceDate)).toBe('Today');
  });

  it('handles timestamp input', () => {
    const timestamp = new Date('2026-01-15T05:00:00Z').getTime();
    expect(getDayGroupLabel(timestamp, referenceDate)).toBe('Today');
  });

  it('returns "Invalid date" for invalid input', () => {
    expect(getDayGroupLabel('not-a-date', referenceDate)).toBe('Invalid date');
  });
});
