/**
 * Tests for ChatInput Component
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 12: Write comprehensive tests (AC: #1)
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInput } from '../ChatInput';

describe('ChatInput', () => {
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it('renders textarea and submit button', () => {
    render(<ChatInput onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId('chat-input-textarea')).toBeInTheDocument();
    expect(screen.getByTestId('chat-submit-button')).toBeInTheDocument();
  });

  it('displays placeholder text', () => {
    render(<ChatInput onSubmit={mockOnSubmit} />);

    expect(
      screen.getByPlaceholderText('Ask LDIP a question...')
    ).toBeInTheDocument();
  });

  it('displays custom placeholder when provided', () => {
    render(
      <ChatInput
        onSubmit={mockOnSubmit}
        placeholder="Custom placeholder"
      />
    );

    expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument();
  });

  it('calls onSubmit with trimmed value when submit button clicked', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const textarea = screen.getByTestId('chat-input-textarea');
    await user.type(textarea, '  Test query  ');

    const submitButton = screen.getByTestId('chat-submit-button');
    await user.click(submitButton);

    expect(mockOnSubmit).toHaveBeenCalledWith('Test query');
  });

  it('calls onSubmit when Enter is pressed', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const textarea = screen.getByTestId('chat-input-textarea');
    await user.type(textarea, 'Test query{Enter}');

    expect(mockOnSubmit).toHaveBeenCalledWith('Test query');
  });

  it('does not submit on Shift+Enter (allows newline)', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const textarea = screen.getByTestId('chat-input-textarea');
    await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2');

    expect(mockOnSubmit).not.toHaveBeenCalled();
    expect(textarea).toHaveValue('Line 1\nLine 2');
  });

  it('clears input after successful submit', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const textarea = screen.getByTestId('chat-input-textarea');
    await user.type(textarea, 'Test query');
    await user.click(screen.getByTestId('chat-submit-button'));

    expect(textarea).toHaveValue('');
  });

  it('disables submit button when input is empty', () => {
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByTestId('chat-submit-button');
    expect(submitButton).toBeDisabled();
  });

  it('disables submit button when input is only whitespace', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const textarea = screen.getByTestId('chat-input-textarea');
    await user.type(textarea, '   ');

    const submitButton = screen.getByTestId('chat-submit-button');
    expect(submitButton).toBeDisabled();
  });

  it('enables submit button when input has content', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} />);

    const textarea = screen.getByTestId('chat-input-textarea');
    await user.type(textarea, 'Test');

    const submitButton = screen.getByTestId('chat-submit-button');
    expect(submitButton).not.toBeDisabled();
  });

  it('disables textarea and button when disabled prop is true', () => {
    render(<ChatInput onSubmit={mockOnSubmit} disabled />);

    expect(screen.getByTestId('chat-input-textarea')).toBeDisabled();
    expect(screen.getByTestId('chat-submit-button')).toBeDisabled();
  });

  it('shows loading spinner when isLoading is true', () => {
    const { container } = render(
      <ChatInput onSubmit={mockOnSubmit} isLoading />
    );

    // Should have spinning loader icon
    const spinner = container.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('does not submit when disabled', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSubmit={mockOnSubmit} disabled />);

    const textarea = screen.getByTestId('chat-input-textarea');
    // Can't type when disabled, but test the button is disabled
    const submitButton = screen.getByTestId('chat-submit-button');

    expect(submitButton).toBeDisabled();
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it('has correct accessibility labels', () => {
    render(<ChatInput onSubmit={mockOnSubmit} />);

    expect(screen.getByLabelText('Message input')).toBeInTheDocument();
    expect(screen.getByLabelText('Send message')).toBeInTheDocument();
  });

  it('shows loading label when submitting', () => {
    render(<ChatInput onSubmit={mockOnSubmit} isLoading />);

    expect(screen.getByLabelText('Sending message...')).toBeInTheDocument();
  });

  it('has correct test id', () => {
    render(<ChatInput onSubmit={mockOnSubmit} />);

    expect(screen.getByTestId('chat-input')).toBeInTheDocument();
  });
});
