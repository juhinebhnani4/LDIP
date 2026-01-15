/**
 * VerificationBadge Component Tests
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #2)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VerificationBadge } from './VerificationBadge';

describe('VerificationBadge', () => {
  it('shows "Verified" badge for verified status', () => {
    render(
      <VerificationBadge
        decision="verified"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    expect(screen.getByText('Verified')).toBeInTheDocument();
  });

  it('shows "Flagged" badge for flagged status', () => {
    render(
      <VerificationBadge
        decision="flagged"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    expect(screen.getByText('Flagged')).toBeInTheDocument();
  });

  it('displays verified_by and verified_at in tooltip', async () => {
    const user = userEvent.setup();

    render(
      <VerificationBadge
        decision="verified"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    const badge = screen.getByText('Verified');
    await user.hover(badge);

    // Tooltip should show verifiedBy (use getAllByText because radix duplicates content for accessibility)
    const johnDoeElements = await screen.findAllByText(/john doe/i);
    expect(johnDoeElements.length).toBeGreaterThan(0);
  });

  it('renders nothing when decision is undefined', () => {
    const { container } = render(<VerificationBadge />);

    expect(container).toBeEmptyDOMElement();
  });

  it('shows verified badge with green styling', () => {
    render(
      <VerificationBadge
        decision="verified"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    const badge = screen.getByText('Verified');
    expect(badge.closest('[class*="border-green"]')).toBeInTheDocument();
  });

  it('shows flagged badge with amber styling', () => {
    render(
      <VerificationBadge
        decision="flagged"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    const badge = screen.getByText('Flagged');
    expect(badge.closest('[class*="border-amber"]')).toBeInTheDocument();
  });

  it('displays check icon for verified status', () => {
    render(
      <VerificationBadge
        decision="verified"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    // Check icon should be present (aria-hidden for decorative icons)
    const badge = screen.getByText('Verified').closest('span');
    expect(badge?.querySelector('svg')).toBeInTheDocument();
  });

  it('displays flag icon for flagged status', () => {
    render(
      <VerificationBadge
        decision="flagged"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
      />
    );

    // Flag icon should be present
    const badge = screen.getByText('Flagged').closest('span');
    expect(badge?.querySelector('svg')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(
      <VerificationBadge
        decision="verified"
        verifiedBy="John Doe"
        verifiedAt="2026-01-15T10:00:00Z"
        className="custom-class"
      />
    );

    const badge = screen.getByText('Verified').closest('span');
    expect(badge).toHaveClass('custom-class');
  });
});
