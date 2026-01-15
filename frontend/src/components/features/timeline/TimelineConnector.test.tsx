import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  TimelineConnector,
  formatDuration,
  isSignificantGap,
  isLargeGap,
} from './TimelineConnector';

describe('TimelineConnector', () => {
  describe('duration display', () => {
    it('shows duration between events', () => {
      render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-02-01"
        />
      );

      expect(screen.getByText(/1 month/)).toBeInTheDocument();
    });

    it('shows left arrow with duration', () => {
      render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-01-15"
        />
      );

      expect(screen.getByText(/← 14 days/)).toBeInTheDocument();
    });
  });

  describe('significant gap styling', () => {
    it('emphasizes gaps over 90 days', () => {
      const { container } = render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-05-01"
        />
      );

      // Check for amber styling on connector line
      const line = container.querySelector('.bg-amber-400');
      expect(line).toBeInTheDocument();
    });

    it('shows normal styling for gaps under 90 days', () => {
      const { container } = render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-02-01"
        />
      );

      // Should have border color, not amber
      const line = container.querySelector('.bg-border');
      expect(line).toBeInTheDocument();
    });

    it('shows SIGNIFICANT DELAY text for gaps over 180 days', () => {
      render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-08-01"
        />
      );

      expect(screen.getByText(/SIGNIFICANT DELAY/)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has separator role', () => {
      render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-02-01"
        />
      );

      expect(screen.getByRole('separator')).toBeInTheDocument();
    });

    it('has aria-label describing the gap', () => {
      render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-02-01"
        />
      );

      expect(
        screen.getByRole('separator', { name: /Time gap: 1 month/ })
      ).toBeInTheDocument();
    });

    it('indicates significant delay in aria-label', () => {
      render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-05-01"
        />
      );

      expect(
        screen.getByRole('separator', { name: /significant delay/ })
      ).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const { container } = render(
        <TimelineConnector
          fromDate="2024-01-01"
          toDate="2024-02-01"
          className="custom-class"
        />
      );

      const connector = container.querySelector('.custom-class');
      expect(connector).toBeInTheDocument();
    });
  });
});

describe('formatDuration', () => {
  it('formats days correctly', () => {
    expect(formatDuration('2024-01-01', '2024-01-15')).toBe('14 days');
    expect(formatDuration('2024-01-01', '2024-01-02')).toBe('1 day');
  });

  it('formats months correctly', () => {
    expect(formatDuration('2024-01-01', '2024-02-01')).toBe('1 month');
    expect(formatDuration('2024-01-01', '2024-03-01')).toBe('2 months');
  });

  it('formats years correctly', () => {
    expect(formatDuration('2024-01-01', '2025-01-01')).toBe('1 year');
    expect(formatDuration('2024-01-01', '2026-01-01')).toBe('2 years');
  });

  it('formats years and months correctly', () => {
    expect(formatDuration('2024-01-01', '2025-04-01')).toBe('1 year, 3 months');
    expect(formatDuration('2024-01-01', '2026-02-01')).toBe('2 years, 1 month');
  });

  it('handles same day', () => {
    expect(formatDuration('2024-01-01', '2024-01-01')).toBe('Same day');
  });

  it('handles invalid dates', () => {
    expect(formatDuration('invalid', '2024-01-01')).toBe('Unknown');
    expect(formatDuration('2024-01-01', 'invalid')).toBe('Unknown');
  });

  it('handles negative range', () => {
    expect(formatDuration('2024-02-01', '2024-01-01')).toBe('Invalid range');
  });
});

describe('isSignificantGap', () => {
  it('returns true for gaps over 90 days', () => {
    expect(isSignificantGap('2024-01-01', '2024-05-01')).toBe(true);
  });

  it('returns false for gaps under 90 days', () => {
    expect(isSignificantGap('2024-01-01', '2024-03-01')).toBe(false);
  });

  it('handles invalid dates', () => {
    expect(isSignificantGap('invalid', '2024-01-01')).toBe(false);
  });
});

describe('isLargeGap', () => {
  it('returns true for gaps over 180 days', () => {
    expect(isLargeGap('2024-01-01', '2024-08-01')).toBe(true);
  });

  it('returns false for gaps under 180 days', () => {
    expect(isLargeGap('2024-01-01', '2024-05-01')).toBe(false);
  });

  it('handles invalid dates', () => {
    expect(isLargeGap('invalid', '2024-01-01')).toBe(false);
  });
});
