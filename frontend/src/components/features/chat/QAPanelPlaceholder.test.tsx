import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';

describe('QAPanelPlaceholder', () => {
  it('renders Ask jaanch heading', () => {
    render(<QAPanelPlaceholder />);

    expect(
      screen.getByRole('heading', { name: 'Ask jaanch' })
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

  it('renders jaanch icon', () => {
    render(<QAPanelPlaceholder />);

    // JaanchIcon renders an img element
    const icon = screen.getByRole('img', { name: 'jaanch.ai' });
    expect(icon).toBeInTheDocument();
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

    const heading = screen.getByRole('heading', { name: 'Ask jaanch' });
    expect(heading.tagName).toBe('H3');
    expect(heading).toHaveClass('text-lg');
    expect(heading).toHaveClass('font-medium');
  });
});
