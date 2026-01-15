/**
 * Tests for SuggestedQuestions Component
 *
 * Story 11.4: Implement Suggested Questions and Message Input
 * Task 6: Write comprehensive tests (AC: All)
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SuggestedQuestions, DEFAULT_SUGGESTIONS } from './SuggestedQuestions';

describe('SuggestedQuestions', () => {
  const mockOnQuestionClick = vi.fn();

  beforeEach(() => {
    mockOnQuestionClick.mockClear();
  });

  it('renders the ASK LDIP heading', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    expect(screen.getByText('ASK LDIP')).toBeInTheDocument();
  });

  it('renders the description text', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    expect(
      screen.getByText(/Ask questions about your matter/i)
    ).toBeInTheDocument();
  });

  it('renders the "Try asking" label', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    expect(screen.getByText('Try asking')).toBeInTheDocument();
  });

  it('renders all default suggested questions', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    DEFAULT_SUGGESTIONS.forEach((question) => {
      expect(screen.getByText(question)).toBeInTheDocument();
    });
  });

  it('renders exactly 6 default questions', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    const buttons = screen.getAllByRole('listitem');
    expect(buttons).toHaveLength(6);
  });

  it('calls onQuestionClick with question text when clicked', async () => {
    const user = userEvent.setup();
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    await user.click(screen.getByText('What is this case about?'));

    expect(mockOnQuestionClick).toHaveBeenCalledTimes(1);
    expect(mockOnQuestionClick).toHaveBeenCalledWith('What is this case about?');
  });

  it('calls onQuestionClick with correct text for each question', async () => {
    const user = userEvent.setup();
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    // Test clicking a different question
    await user.click(screen.getByText('Who are the main parties involved?'));

    expect(mockOnQuestionClick).toHaveBeenCalledWith('Who are the main parties involved?');
  });

  it('renders questions as clickable buttons', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    // Verify all questions render as interactive buttons (listitems)
    const buttons = screen.getAllByRole('listitem');
    expect(buttons).toHaveLength(6);

    // Verify buttons are focusable and clickable (behavior test)
    buttons.forEach((button) => {
      expect(button).toBeVisible();
      expect(button).not.toBeDisabled();
    });
  });

  it('questions are keyboard accessible', async () => {
    const user = userEvent.setup();
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    const firstQuestion = screen.getByText('What is this case about?');
    firstQuestion.focus();
    await user.keyboard('{Enter}');

    expect(mockOnQuestionClick).toHaveBeenCalledWith('What is this case about?');
  });

  it('questions are keyboard navigable with Tab', async () => {
    const user = userEvent.setup();
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    // Tab to first button, then Enter
    await user.tab();
    await user.keyboard('{Enter}');

    expect(mockOnQuestionClick).toHaveBeenCalledTimes(1);
  });

  it('has ARIA region with label', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    expect(screen.getByRole('region', { name: 'Suggested questions' })).toBeInTheDocument();
  });

  it('has ARIA list with label', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    expect(screen.getByRole('list', { name: 'Suggested questions list' })).toBeInTheDocument();
  });

  it('each question button has aria-label', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    DEFAULT_SUGGESTIONS.forEach((question) => {
      expect(screen.getByRole('listitem', { name: `Ask: ${question}` })).toBeInTheDocument();
    });
  });

  it('applies custom className when provided', () => {
    render(
      <SuggestedQuestions
        onQuestionClick={mockOnQuestionClick}
        className="custom-class"
      />
    );

    const region = screen.getByRole('region');
    expect(region).toHaveClass('custom-class');
  });

  it('renders MessageSquare icon', () => {
    const { container } = render(
      <SuggestedQuestions onQuestionClick={mockOnQuestionClick} />
    );

    // lucide-react icons have data-slot="icon" or class naming
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('icon is decorative (aria-hidden)', () => {
    const { container } = render(
      <SuggestedQuestions onQuestionClick={mockOnQuestionClick} />
    );

    const icon = container.querySelector('svg');
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('has proper visual layout classes', () => {
    render(<SuggestedQuestions onQuestionClick={mockOnQuestionClick} />);

    const region = screen.getByRole('region');
    expect(region).toHaveClass('flex', 'flex-col', 'items-center', 'text-center');
  });
});
