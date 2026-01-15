/**
 * InlineVerificationButtons Component Tests
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #1, #2)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InlineVerificationButtons } from './InlineVerificationButtons';

describe('InlineVerificationButtons', () => {
  const defaultProps = {
    sectionType: 'subject_matter' as const,
    sectionId: 'test-section-123',
    onVerify: vi.fn(),
    onFlag: vi.fn(),
    onAddNote: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all three buttons', () => {
    render(<InlineVerificationButtons {...defaultProps} />);

    expect(screen.getByRole('button', { name: /verify this section/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /flag this section/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add note to this section/i })).toBeInTheDocument();
  });

  it('shows loading state during verify action', async () => {
    const user = userEvent.setup();
    const onVerify = vi.fn(() => new Promise<void>((resolve) => setTimeout(resolve, 100)));

    render(<InlineVerificationButtons {...defaultProps} onVerify={onVerify} />);

    const verifyButton = screen.getByRole('button', { name: /verify this section/i });
    await user.click(verifyButton);

    // Button should be disabled during loading
    expect(verifyButton).toBeDisabled();

    // Wait for action to complete
    await waitFor(() => {
      expect(verifyButton).not.toBeDisabled();
    });
  });

  it('shows loading state during flag action', async () => {
    const user = userEvent.setup();
    const onFlag = vi.fn(() => new Promise<void>((resolve) => setTimeout(resolve, 100)));

    render(<InlineVerificationButtons {...defaultProps} onFlag={onFlag} />);

    const flagButton = screen.getByRole('button', { name: /flag this section/i });
    await user.click(flagButton);

    // Button should be disabled during loading
    expect(flagButton).toBeDisabled();

    // Wait for action to complete
    await waitFor(() => {
      expect(flagButton).not.toBeDisabled();
    });
  });

  it('disables verify button when already verified', () => {
    render(
      <InlineVerificationButtons
        {...defaultProps}
        currentDecision="verified"
      />
    );

    const verifyButton = screen.getByRole('button', { name: /verify this section/i });
    expect(verifyButton).toBeDisabled();
  });

  it('disables flag button when already flagged', () => {
    render(
      <InlineVerificationButtons
        {...defaultProps}
        currentDecision="flagged"
      />
    );

    const flagButton = screen.getByRole('button', { name: /flag this section/i });
    expect(flagButton).toBeDisabled();
  });

  it('calls onVerify when verify button clicked', async () => {
    const user = userEvent.setup();
    const onVerify = vi.fn().mockResolvedValue(undefined);

    render(<InlineVerificationButtons {...defaultProps} onVerify={onVerify} />);

    await user.click(screen.getByRole('button', { name: /verify this section/i }));

    expect(onVerify).toHaveBeenCalledTimes(1);
  });

  it('calls onFlag when flag button clicked', async () => {
    const user = userEvent.setup();
    const onFlag = vi.fn().mockResolvedValue(undefined);

    render(<InlineVerificationButtons {...defaultProps} onFlag={onFlag} />);

    await user.click(screen.getByRole('button', { name: /flag this section/i }));

    expect(onFlag).toHaveBeenCalledTimes(1);
  });

  it('calls onAddNote when notes button clicked', async () => {
    const user = userEvent.setup();
    const onAddNote = vi.fn();

    render(<InlineVerificationButtons {...defaultProps} onAddNote={onAddNote} />);

    await user.click(screen.getByRole('button', { name: /add note to this section/i }));

    expect(onAddNote).toHaveBeenCalledTimes(1);
  });

  it('hides buttons when isVisible is false', () => {
    render(<InlineVerificationButtons {...defaultProps} isVisible={false} />);

    const container = screen.getByLabelText('Verification actions');
    expect(container).toHaveClass('opacity-0');
  });

  it('shows buttons when isVisible is true', () => {
    render(<InlineVerificationButtons {...defaultProps} isVisible={true} />);

    const container = screen.getByLabelText('Verification actions');
    expect(container).toHaveClass('opacity-100');
  });

  it('applies custom className', () => {
    render(<InlineVerificationButtons {...defaultProps} className="custom-class" />);

    const container = screen.getByLabelText('Verification actions');
    expect(container).toHaveClass('custom-class');
  });

  it('handles verify error gracefully', async () => {
    const user = userEvent.setup();
    const onVerify = vi.fn().mockRejectedValue(new Error('API Error'));

    render(<InlineVerificationButtons {...defaultProps} onVerify={onVerify} />);

    const verifyButton = screen.getByRole('button', { name: /verify this section/i });
    await user.click(verifyButton);

    // Button should be re-enabled after error
    await waitFor(() => {
      expect(verifyButton).not.toBeDisabled();
    });
  });

  it('handles flag error gracefully', async () => {
    const user = userEvent.setup();
    const onFlag = vi.fn().mockRejectedValue(new Error('API Error'));

    render(<InlineVerificationButtons {...defaultProps} onFlag={onFlag} />);

    const flagButton = screen.getByRole('button', { name: /flag this section/i });
    await user.click(flagButton);

    // Button should be re-enabled after error
    await waitFor(() => {
      expect(flagButton).not.toBeDisabled();
    });
  });
});
