import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';

describe('QAPanelPlaceholder', () => {
  it('renders ASK LDIP heading', () => {
    render(<QAPanelPlaceholder />);

    expect(
      screen.getByRole('heading', { name: 'ASK LDIP' })
    ).toBeInTheDocument();
  });

  it('renders description text', () => {
    render(<QAPanelPlaceholder />);

    expect(
      screen.getByText(
        /Ask questions about your matter\. The AI will analyze documents/i
      )
    ).toBeInTheDocument();
  });

  it('shows Coming in Epic 11 note', () => {
    render(<QAPanelPlaceholder />);

    expect(screen.getByText('Coming in Epic 11')).toBeInTheDocument();
  });

  it('renders message square icon', () => {
    const { container } = render(<QAPanelPlaceholder />);

    // MessageSquare icon should be present
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass('h-12');
    expect(icon).toHaveClass('w-12');
  });

  it('has proper layout structure', () => {
    const { container } = render(<QAPanelPlaceholder />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('flex');
    expect(wrapper).toHaveClass('flex-1');
    expect(wrapper).toHaveClass('flex-col');
    expect(wrapper).toHaveClass('items-center');
    expect(wrapper).toHaveClass('justify-center');
    expect(wrapper).toHaveClass('text-center');
  });

  it('has proper text styling', () => {
    render(<QAPanelPlaceholder />);

    const heading = screen.getByRole('heading', { name: 'ASK LDIP' });
    expect(heading.tagName).toBe('H3');
    expect(heading).toHaveClass('text-lg');
    expect(heading).toHaveClass('font-medium');

    const comingSoon = screen.getByText('Coming in Epic 11');
    expect(comingSoon).toHaveClass('text-xs');
    expect(comingSoon).toHaveClass('text-muted-foreground');
  });
});
