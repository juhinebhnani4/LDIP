import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FeatureTour, useTourReset } from '../FeatureTour';
import { renderHook } from '@testing-library/react';

const TOUR_STORAGE_KEY = 'ldip-feature-tour-completed';

describe('FeatureTour', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('does not show tour if already completed', () => {
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');

    render(<FeatureTour forceShow={false} />);

    expect(screen.queryByText('Your Matters')).not.toBeInTheDocument();
  });

  it('shows tour immediately when forceShow is true', () => {
    localStorage.setItem(TOUR_STORAGE_KEY, 'true'); // Should be ignored
    render(<FeatureTour forceShow={true} />);

    expect(screen.getByText('Your Matters')).toBeInTheDocument();
  });

  it('renders step indicator', () => {
    render(<FeatureTour forceShow={true} />);

    expect(screen.getByText(/step 1 of 5/i)).toBeInTheDocument();
  });

  it('navigates to next step when Next clicked', async () => {
    const user = userEvent.setup();
    render(<FeatureTour forceShow={true} />);

    expect(screen.getByText('Your Matters')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /next/i }));

    expect(screen.getByText('Upload Documents')).toBeInTheDocument();
    expect(screen.getByText(/step 2 of 5/i)).toBeInTheDocument();
  });

  it('shows Back button on non-first steps', async () => {
    const user = userEvent.setup();
    render(<FeatureTour forceShow={true} />);

    // First step should not have Back button
    expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /next/i }));

    // Second step should have Back button
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument();
  });

  it('navigates back when Back clicked', async () => {
    const user = userEvent.setup();
    render(<FeatureTour forceShow={true} />);

    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByText('Upload Documents')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /back/i }));
    expect(screen.getByText('Your Matters')).toBeInTheDocument();
  });

  it('shows Finish button on last step', async () => {
    const user = userEvent.setup();
    render(<FeatureTour forceShow={true} />);

    // Navigate to last step (5 steps total, so click Next 4 times)
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /next/i }));
    }

    expect(screen.getByRole('button', { name: /finish/i })).toBeInTheDocument();
  });

  it('saves completion and closes on Finish', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    render(<FeatureTour forceShow={true} onComplete={onComplete} />);

    // Navigate to last step
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByRole('button', { name: /next/i }));
    }

    await user.click(screen.getByRole('button', { name: /finish/i }));

    expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe('true');
    expect(onComplete).toHaveBeenCalled();
    expect(screen.queryByText('Get Help')).not.toBeInTheDocument();
  });

  it('closes and saves completion when Skip text clicked', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    render(<FeatureTour forceShow={true} onComplete={onComplete} />);

    // Click the "Skip tour" text link, not the X button
    const skipLink = screen.getByText('Skip tour');
    await user.click(skipLink);

    expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe('true');
    expect(onComplete).toHaveBeenCalled();
    expect(screen.queryByText('Your Matters')).not.toBeInTheDocument();
  });

  it('closes when overlay is clicked', async () => {
    const user = userEvent.setup();
    render(<FeatureTour forceShow={true} />);

    // Click the overlay (bg-black/50 element)
    const overlay = document.querySelector('.bg-black\\/50');
    if (overlay) {
      await user.click(overlay);
    }

    expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe('true');
    expect(screen.queryByText('Your Matters')).not.toBeInTheDocument();
  });

  it('renders step dot indicators', () => {
    render(<FeatureTour forceShow={true} />);

    // Should have 5 step indicators
    const dots = document.querySelectorAll('.rounded-full.w-2.h-2');
    expect(dots.length).toBe(5);
  });
});

describe('useTourReset', () => {
  beforeEach(() => {
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');
  });

  it('clears tour completion from localStorage', () => {
    const { result } = renderHook(() => useTourReset());

    expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe('true');

    act(() => {
      result.current();
    });

    expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBeNull();
  });
});
