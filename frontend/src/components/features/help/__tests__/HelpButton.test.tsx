import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TooltipProvider } from '@/components/ui/tooltip';
import { HelpButton } from '../HelpButton';
import type { ReactNode } from 'react';

// Mock the HelpPanel component
vi.mock('../HelpPanel', () => ({
  HelpPanel: ({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) => (
    open ? (
      <div data-testid="help-panel">
        <button onClick={() => onOpenChange(false)}>Close</button>
      </div>
    ) : null
  ),
}));

function renderWithProvider(ui: ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('HelpButton', () => {
  it('renders help button with correct aria-label', () => {
    renderWithProvider(<HelpButton />);

    const helpButton = screen.getByRole('button', { name: /help/i });
    expect(helpButton).toBeInTheDocument();
  });

  it('opens help panel when clicked', async () => {
    const user = userEvent.setup();
    renderWithProvider(<HelpButton />);

    expect(screen.queryByTestId('help-panel')).not.toBeInTheDocument();

    const helpButton = screen.getByRole('button', { name: /help/i });
    await user.click(helpButton);

    expect(screen.getByTestId('help-panel')).toBeInTheDocument();
  });

  it('opens help panel when ? key is pressed', () => {
    renderWithProvider(<HelpButton />);

    expect(screen.queryByTestId('help-panel')).not.toBeInTheDocument();

    fireEvent.keyDown(document, { key: '?' });

    expect(screen.getByTestId('help-panel')).toBeInTheDocument();
  });

  it('opens help panel when F1 is pressed', () => {
    renderWithProvider(<HelpButton />);

    expect(screen.queryByTestId('help-panel')).not.toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'F1' });

    expect(screen.getByTestId('help-panel')).toBeInTheDocument();
  });

  it('does not open help when ? is pressed in an input', () => {
    renderWithProvider(
      <>
        <HelpButton />
        <input data-testid="test-input" />
      </>
    );

    const input = screen.getByTestId('test-input');
    fireEvent.keyDown(input, { key: '?', target: input });

    expect(screen.queryByTestId('help-panel')).not.toBeInTheDocument();
  });

  it('closes help panel when escape is pressed', async () => {
    const user = userEvent.setup();
    renderWithProvider(<HelpButton />);

    // Open the panel
    const helpButton = screen.getByRole('button', { name: /help/i });
    await user.click(helpButton);
    expect(screen.getByTestId('help-panel')).toBeInTheDocument();

    // Close with escape
    fireEvent.keyDown(document, { key: 'Escape' });

    expect(screen.queryByTestId('help-panel')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    renderWithProvider(<HelpButton className="custom-class" />);

    const helpButton = screen.getByRole('button', { name: /help/i });
    expect(helpButton).toHaveClass('custom-class');
  });

  it('applies data-tour attribute', () => {
    renderWithProvider(<HelpButton data-tour="help-button" />);

    const helpButton = screen.getByRole('button', { name: /help/i });
    expect(helpButton).toHaveAttribute('data-tour', 'help-button');
  });
});
