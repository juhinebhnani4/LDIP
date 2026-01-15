import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QAPanel } from './QAPanel';

// Mock the child components
vi.mock('./QAPanelHeader', () => ({
  QAPanelHeader: () => <div data-testid="qa-panel-header">Header</div>,
}));

vi.mock('./QAPanelPlaceholder', () => ({
  QAPanelPlaceholder: () => <div data-testid="qa-panel-placeholder">Placeholder</div>,
}));

describe('QAPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the QAPanelHeader', () => {
    render(<QAPanel />);

    const header = screen.getByTestId('qa-panel-header');
    expect(header).toBeInTheDocument();
  });

  it('renders the QAPanelPlaceholder', () => {
    render(<QAPanel />);

    expect(screen.getByTestId('qa-panel-placeholder')).toBeInTheDocument();
  });

  it('has proper layout structure with flex column', () => {
    const { container } = render(<QAPanel />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('flex');
    expect(wrapper).toHaveClass('flex-col');
    expect(wrapper).toHaveClass('h-full');
  });

  it('has background color class', () => {
    const { container } = render(<QAPanel />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('bg-background');
  });
});
