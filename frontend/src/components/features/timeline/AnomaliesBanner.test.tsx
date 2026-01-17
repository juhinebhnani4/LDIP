/**
 * AnomaliesBanner Component Tests
 *
 * Tests for the AnomaliesBanner and AnomaliesIndicatorBadge components.
 *
 * Story 14.16: Anomalies UI Integration (AC #2)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnomaliesBanner, AnomaliesIndicatorBadge } from './AnomaliesBanner';
import type { AnomalySummary } from '@/hooks/useAnomalies';

const mockSummary: AnomalySummary = {
  total: 5,
  bySeverity: {
    critical: 1,
    high: 2,
    medium: 1,
    low: 1,
  },
  byType: {
    gap: 2,
    sequence_violation: 2,
    duplicate: 1,
  },
  unreviewed: 3,
  verified: 1,
  dismissed: 1,
};

const mockSummaryNoCritical: AnomalySummary = {
  total: 3,
  bySeverity: {
    medium: 2,
    low: 1,
  },
  byType: {
    gap: 2,
    duplicate: 1,
  },
  unreviewed: 2,
  verified: 1,
  dismissed: 0,
};

describe('AnomaliesBanner', () => {
  it('renders nothing when summary is null', () => {
    const { container } = render(<AnomaliesBanner summary={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when unreviewed count is 0', () => {
    const { container } = render(
      <AnomaliesBanner summary={{ ...mockSummary, unreviewed: 0 }} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders banner with correct title', () => {
    render(<AnomaliesBanner summary={mockSummary} />);
    expect(screen.getByText('Timeline Anomalies Detected')).toBeInTheDocument();
  });

  it('shows unreviewed count badge', () => {
    render(<AnomaliesBanner summary={mockSummary} />);
    expect(screen.getByText('3 to review')).toBeInTheDocument();
  });

  it('shows severity breakdown badges', () => {
    render(<AnomaliesBanner summary={mockSummary} />);
    expect(screen.getByText('1 critical')).toBeInTheDocument();
    expect(screen.getByText('2 high')).toBeInTheDocument();
    expect(screen.getByText('1 medium')).toBeInTheDocument();
  });

  it('shows total active anomalies count', () => {
    render(<AnomaliesBanner summary={mockSummary} />);
    expect(screen.getByText(/4 total anomalies found/)).toBeInTheDocument();
  });

  it('uses destructive variant when critical or high severity present', () => {
    const { container } = render(<AnomaliesBanner summary={mockSummary} />);
    const alert = container.querySelector('[role="alert"]');
    expect(alert?.className).toContain('destructive');
  });

  it('uses default variant when only medium/low severity', () => {
    const { container } = render(<AnomaliesBanner summary={mockSummaryNoCritical} />);
    const alert = container.querySelector('[role="alert"]');
    expect(alert?.className).toContain('orange');
  });

  it('calls onShowAnomalies when Show in Timeline clicked', async () => {
    const user = userEvent.setup();
    const onShowAnomalies = vi.fn();
    render(<AnomaliesBanner summary={mockSummary} onShowAnomalies={onShowAnomalies} />);

    await user.click(screen.getByRole('button', { name: /show in timeline/i }));

    expect(onShowAnomalies).toHaveBeenCalled();
  });

  it('calls onReviewAnomalies when Review clicked', async () => {
    const user = userEvent.setup();
    const onReviewAnomalies = vi.fn();
    render(<AnomaliesBanner summary={mockSummary} onReviewAnomalies={onReviewAnomalies} />);

    await user.click(screen.getByRole('button', { name: /review/i }));

    expect(onReviewAnomalies).toHaveBeenCalled();
  });

  it('can be dismissed when dismissible is true', async () => {
    const user = userEvent.setup();
    render(<AnomaliesBanner summary={mockSummary} dismissible />);

    expect(screen.getByText('Timeline Anomalies Detected')).toBeInTheDocument();

    await user.click(screen.getByLabelText(/dismiss banner/i));

    expect(screen.queryByText('Timeline Anomalies Detected')).not.toBeInTheDocument();
  });

  it('does not show dismiss button when dismissible is false', () => {
    render(<AnomaliesBanner summary={mockSummary} dismissible={false} />);
    expect(screen.queryByLabelText(/dismiss banner/i)).not.toBeInTheDocument();
  });
});

describe('AnomaliesIndicatorBadge', () => {
  it('renders nothing when count is 0', () => {
    const { container } = render(<AnomaliesIndicatorBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders badge with count', () => {
    render(<AnomaliesIndicatorBadge count={5} />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('uses destructive variant when hasCritical is true', () => {
    render(<AnomaliesIndicatorBadge count={3} hasCritical />);
    const badge = screen.getByText('3');
    expect(badge.className).toContain('destructive');
  });

  it('uses secondary variant when hasCritical is false', () => {
    render(<AnomaliesIndicatorBadge count={3} hasCritical={false} />);
    const badge = screen.getByText('3');
    expect(badge.className).toContain('orange');
  });

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<AnomaliesIndicatorBadge count={5} onClick={onClick} />);

    await user.click(screen.getByText('5'));

    expect(onClick).toHaveBeenCalled();
  });
});
