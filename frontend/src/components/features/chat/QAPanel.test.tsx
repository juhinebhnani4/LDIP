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

vi.mock('./ConversationHistory', () => ({
  ConversationHistory: ({ matterId, userId }: { matterId: string; userId: string }) => (
    <div data-testid="conversation-history" data-matter-id={matterId} data-user-id={userId}>
      Conversation History
    </div>
  ),
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

  it('renders the QAPanelPlaceholder when no matterId or userId', () => {
    render(<QAPanel />);

    expect(screen.getByTestId('qa-panel-placeholder')).toBeInTheDocument();
  });

  it('renders the QAPanelPlaceholder when only matterId is provided', () => {
    render(<QAPanel matterId="matter-123" />);

    expect(screen.getByTestId('qa-panel-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('conversation-history')).not.toBeInTheDocument();
  });

  it('renders the QAPanelPlaceholder when only userId is provided', () => {
    render(<QAPanel userId="user-456" />);

    expect(screen.getByTestId('qa-panel-placeholder')).toBeInTheDocument();
    expect(screen.queryByTestId('conversation-history')).not.toBeInTheDocument();
  });

  it('renders ConversationHistory when both matterId and userId are provided', () => {
    render(<QAPanel matterId="matter-123" userId="user-456" />);

    expect(screen.getByTestId('conversation-history')).toBeInTheDocument();
    expect(screen.queryByTestId('qa-panel-placeholder')).not.toBeInTheDocument();
  });

  it('passes matterId and userId to ConversationHistory', () => {
    render(<QAPanel matterId="matter-123" userId="user-456" />);

    const conversationHistory = screen.getByTestId('conversation-history');
    expect(conversationHistory).toHaveAttribute('data-matter-id', 'matter-123');
    expect(conversationHistory).toHaveAttribute('data-user-id', 'user-456');
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
