/**
 * VerificationStats Component Tests
 *
 * Story 8-5: Implement Verification Queue UI (Task 10)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VerificationStats } from './VerificationStats';
import type { VerificationStats as StatsType } from '@/types';

const mockStats: StatsType = {
  totalVerifications: 100,
  pendingCount: 40,
  approvedCount: 45,
  rejectedCount: 10,
  flaggedCount: 5,
  requiredPending: 10,
  suggestedPending: 20,
  optionalPending: 10,
  exportBlocked: true,
  blockingCount: 10,
};

describe('VerificationStats', () => {
  it('renders loading skeleton when isLoading is true', () => {
    render(<VerificationStats stats={null} isLoading={true} />);

    // Should show skeleton elements, not actual content
    expect(screen.queryByText('Verification Center')).not.toBeInTheDocument();
  });

  it('renders loading skeleton when stats is null', () => {
    render(<VerificationStats stats={null} />);

    // Should show skeleton elements
    expect(screen.queryByText('Verification Center')).not.toBeInTheDocument();
  });

  it('renders stats header with title', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('Verification Center')).toBeInTheDocument();
  });

  it('displays completion percentage correctly', () => {
    render(<VerificationStats stats={mockStats} />);

    // 45 approved + 10 rejected = 55 completed out of 100 = 55%
    expect(screen.getByText('55% Complete')).toBeInTheDocument();
  });

  it('displays verified count', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('45 verified')).toBeInTheDocument();
  });

  it('displays pending count', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('40 pending')).toBeInTheDocument();
  });

  it('displays flagged count', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('5 flagged')).toBeInTheDocument();
  });

  it('displays rejected count when > 0', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('10 rejected')).toBeInTheDocument();
  });

  it('hides rejected count when 0', () => {
    const statsNoRejected = { ...mockStats, rejectedCount: 0 };
    render(<VerificationStats stats={statsNoRejected} />);

    expect(screen.queryByText('0 rejected')).not.toBeInTheDocument();
  });

  it('displays export blocked badge when export is blocked', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('10 blocking export')).toBeInTheDocument();
  });

  it('hides export blocked badge when export is not blocked', () => {
    const statsNotBlocked = { ...mockStats, exportBlocked: false };
    render(<VerificationStats stats={statsNotBlocked} />);

    expect(screen.queryByText(/blocking export/)).not.toBeInTheDocument();
  });

  it('displays tier breakdown badges', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.getByText('Required: 10 pending')).toBeInTheDocument();
    expect(screen.getByText('Suggested: 20 pending')).toBeInTheDocument();
    expect(screen.getByText('Optional: 10 pending')).toBeInTheDocument();
  });

  it('hides tier badges when count is 0', () => {
    const statsNoRequired = { ...mockStats, requiredPending: 0 };
    render(<VerificationStats stats={statsNoRequired} />);

    expect(screen.queryByText('Required: 0 pending')).not.toBeInTheDocument();
  });

  it('renders Start Review Session button when callback provided', () => {
    const onStartSession = vi.fn();
    render(
      <VerificationStats stats={mockStats} onStartSession={onStartSession} />
    );

    expect(screen.getByText('Start Review Session')).toBeInTheDocument();
  });

  it('does not render Start Review Session button when callback not provided', () => {
    render(<VerificationStats stats={mockStats} />);

    expect(screen.queryByText('Start Review Session')).not.toBeInTheDocument();
  });

  it('calls onStartSession when button is clicked', async () => {
    const user = userEvent.setup();
    const onStartSession = vi.fn();

    render(
      <VerificationStats stats={mockStats} onStartSession={onStartSession} />
    );

    await user.click(screen.getByText('Start Review Session'));

    expect(onStartSession).toHaveBeenCalledTimes(1);
  });

  it('disables Start Review Session button when pendingCount is 0', () => {
    const statsNoPending = { ...mockStats, pendingCount: 0 };
    const onStartSession = vi.fn();

    render(
      <VerificationStats stats={statsNoPending} onStartSession={onStartSession} />
    );

    const button = screen.getByText('Start Review Session');
    expect(button).toBeDisabled();
  });

  it('calculates 0% completion when totalVerifications is 0', () => {
    const emptyStats: StatsType = {
      ...mockStats,
      totalVerifications: 0,
      pendingCount: 0,
      approvedCount: 0,
      rejectedCount: 0,
    };

    render(<VerificationStats stats={emptyStats} />);

    expect(screen.getByText('0% Complete')).toBeInTheDocument();
  });
});
