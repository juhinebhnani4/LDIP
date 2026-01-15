import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QAPanel } from './QAPanel';

// Mock the child components
vi.mock('./QAPanelHeader', () => ({
  QAPanelHeader: ({ matterId }: { matterId: string }) => (
    <div data-testid="qa-panel-header">Header: {matterId}</div>
  ),
}));

vi.mock('./QAPanelPlaceholder', () => ({
  QAPanelPlaceholder: () => <div data-testid="qa-panel-placeholder">Placeholder</div>,
}));

describe('QAPanel', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the QAPanelHeader with matterId', () => {
    render(<QAPanel matterId={mockMatterId} />);

    const header = screen.getByTestId('qa-panel-header');
    expect(header).toBeInTheDocument();
    expect(header).toHaveTextContent(`Header: ${mockMatterId}`);
  });

  it('renders the QAPanelPlaceholder', () => {
    render(<QAPanel matterId={mockMatterId} />);

    expect(screen.getByTestId('qa-panel-placeholder')).toBeInTheDocument();
  });

  it('has proper layout structure with flex column', () => {
    const { container } = render(<QAPanel matterId={mockMatterId} />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('flex');
    expect(wrapper).toHaveClass('flex-col');
    expect(wrapper).toHaveClass('h-full');
  });

  it('has background color class', () => {
    const { container } = render(<QAPanel matterId={mockMatterId} />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('bg-background');
  });
});
