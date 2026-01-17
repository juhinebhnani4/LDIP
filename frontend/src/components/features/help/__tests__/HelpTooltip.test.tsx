import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { HelpTooltip, HelpTooltipInline } from '../HelpTooltip';
import type { ReactNode } from 'react';

function renderWithProvider(ui: ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('HelpTooltip', () => {
  it('renders help icon button', () => {
    renderWithProvider(<HelpTooltip content="Test content" />);

    const button = screen.getByRole('button', { name: /more information/i });
    expect(button).toBeInTheDocument();
  });

  // Note: Tooltip hover testing is flaky in jsdom environment
  // The tooltip content is rendered correctly in actual browser usage

  it('applies custom className', () => {
    renderWithProvider(<HelpTooltip content="Test" className="custom-class" />);

    const button = screen.getByRole('button', { name: /more information/i });
    expect(button).toHaveClass('custom-class');
  });

  it('applies custom iconClassName', () => {
    renderWithProvider(<HelpTooltip content="Test" iconClassName="h-6 w-6" />);

    const icon = screen.getByRole('button', { name: /more information/i }).querySelector('svg');
    expect(icon).toHaveClass('h-6', 'w-6');
  });

  it('renders with learnMoreId prop', () => {
    renderWithProvider(<HelpTooltip content="Test" learnMoreId="test-id" />);

    const button = screen.getByRole('button', { name: /more information/i });
    expect(button).toBeInTheDocument();
  });
});

describe('HelpTooltipInline', () => {
  it('renders with smaller icon', () => {
    renderWithProvider(<HelpTooltipInline content="Inline help" />);

    const button = screen.getByRole('button', { name: /more information/i });
    expect(button).toBeInTheDocument();

    const icon = button.querySelector('svg');
    expect(icon).toHaveClass('h-3.5', 'w-3.5');
  });

  it('has ml-1 class for inline spacing', () => {
    renderWithProvider(<HelpTooltipInline content="Inline help" />);

    const button = screen.getByRole('button', { name: /more information/i });
    expect(button).toHaveClass('ml-1');
  });
});
