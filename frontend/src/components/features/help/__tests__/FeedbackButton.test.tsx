import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TooltipProvider } from '@/components/ui/tooltip';
import { FeedbackButton } from '../FeedbackButton';
import type { ReactNode } from 'react';

function renderWithProvider(ui: ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('FeedbackButton', () => {
  let windowOpenSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
  });

  it('renders icon variant by default', () => {
    renderWithProvider(<FeedbackButton />);

    const button = screen.getByRole('button', { name: /send feedback/i });
    expect(button).toBeInTheDocument();
  });

  it('renders full variant with text', () => {
    renderWithProvider(<FeedbackButton variant="full" />);

    expect(screen.getByRole('button', { name: /send feedback/i })).toBeInTheDocument();
    expect(screen.getByText('Send Feedback')).toBeInTheDocument();
  });

  it('opens feedback URL when clicked', async () => {
    const user = userEvent.setup();
    renderWithProvider(<FeedbackButton />);

    const button = screen.getByRole('button', { name: /send feedback/i });
    await user.click(button);

    expect(windowOpenSpy).toHaveBeenCalledWith(
      expect.stringContaining('github.com'),
      '_blank',
      'noopener,noreferrer'
    );
  });

  it('includes page context in feedback URL', async () => {
    const user = userEvent.setup();
    renderWithProvider(<FeedbackButton />);

    const button = screen.getByRole('button', { name: /send feedback/i });
    await user.click(button);

    const [url] = windowOpenSpy.mock.calls[0] as [string, string, string];
    expect(url).toContain('template=bug_report.md');
    expect(url).toContain('Page');
  });

  it('applies custom className to icon variant', () => {
    renderWithProvider(<FeedbackButton className="custom-class" />);

    const button = screen.getByRole('button', { name: /send feedback/i });
    expect(button).toHaveClass('custom-class');
  });

  it('applies custom className to full variant', () => {
    renderWithProvider(<FeedbackButton variant="full" className="custom-class" />);

    const button = screen.getByRole('button', { name: /send feedback/i });
    expect(button).toHaveClass('custom-class');
  });
});
