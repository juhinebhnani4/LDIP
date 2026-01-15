import { describe, test, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatMessage } from './ChatMessage';
import type { ChatMessage as ChatMessageType } from '@/types/chat';

describe('ChatMessage', () => {
  const userMessage: ChatMessageType = {
    id: 'msg-1',
    role: 'user',
    content: 'What is this case about?',
    timestamp: new Date().toISOString(),
  };

  const assistantMessage: ChatMessageType = {
    id: 'msg-2',
    role: 'assistant',
    content: 'This case involves a dispute between two parties regarding a contract breach.',
    timestamp: new Date().toISOString(),
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'petition.pdf',
        page: 5,
      },
      {
        documentId: 'doc-2',
        documentName: 'evidence.pdf',
        page: 12,
      },
    ],
  };

  const assistantMessageWithoutSources: ChatMessageType = {
    id: 'msg-3',
    role: 'assistant',
    content: 'I can help you with that.',
    timestamp: new Date().toISOString(),
  };

  test('renders user message content', () => {
    render(<ChatMessage message={userMessage} />);
    expect(screen.getByText(userMessage.content)).toBeInTheDocument();
  });

  test('renders assistant message content', () => {
    render(<ChatMessage message={assistantMessage} />);
    expect(screen.getByText(assistantMessage.content)).toBeInTheDocument();
  });

  test('user message has correct testid', () => {
    render(<ChatMessage message={userMessage} />);
    expect(screen.getByTestId('chat-message-user')).toBeInTheDocument();
  });

  test('assistant message has correct testid', () => {
    render(<ChatMessage message={assistantMessage} />);
    expect(screen.getByTestId('chat-message-assistant')).toBeInTheDocument();
  });

  test('user message displays User icon', () => {
    render(<ChatMessage message={userMessage} />);
    // User messages should have the right-aligned flex layout
    const messageContainer = screen.getByTestId('chat-message-user');
    expect(messageContainer).toHaveClass('flex-row-reverse');
  });

  test('assistant message displays Bot icon', () => {
    render(<ChatMessage message={assistantMessage} />);
    // Assistant messages should have the left-aligned flex layout
    const messageContainer = screen.getByTestId('chat-message-assistant');
    expect(messageContainer).toHaveClass('flex-row');
    expect(messageContainer).not.toHaveClass('flex-row-reverse');
  });

  test('renders source references for assistant messages', () => {
    render(<ChatMessage message={assistantMessage} />);
    expect(screen.getByText('petition.pdf (p. 5)')).toBeInTheDocument();
    expect(screen.getByText('evidence.pdf (p. 12)')).toBeInTheDocument();
  });

  test('does not render source references for user messages', () => {
    // Even if we somehow had sources on a user message, they shouldn't render
    const userWithSources: ChatMessageType = {
      ...userMessage,
      sources: [{ documentId: 'doc-1', documentName: 'test.pdf' }],
    };
    render(<ChatMessage message={userWithSources} />);
    expect(screen.queryByTestId('source-reference')).not.toBeInTheDocument();
  });

  test('assistant message without sources does not show source section', () => {
    render(<ChatMessage message={assistantMessageWithoutSources} />);
    expect(screen.queryByTestId('source-reference')).not.toBeInTheDocument();
  });

  test('calls onSourceClick when source is clicked', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<ChatMessage message={assistantMessage} onSourceClick={handleClick} />);

    await user.click(screen.getByText('petition.pdf (p. 5)'));
    expect(handleClick).toHaveBeenCalledWith(assistantMessage.sources![0]);
  });

  test('calls onSourceClick with correct source data', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<ChatMessage message={assistantMessage} onSourceClick={handleClick} />);

    await user.click(screen.getByText('evidence.pdf (p. 12)'));
    expect(handleClick).toHaveBeenCalledWith({
      documentId: 'doc-2',
      documentName: 'evidence.pdf',
      page: 12,
    });
  });

  test('displays relative timestamp', () => {
    render(<ChatMessage message={userMessage} />);
    // Since the timestamp is "now", it should show something like "less than a minute ago"
    expect(screen.getByText(/ago/i)).toBeInTheDocument();
  });

  test('handles multiline message content', () => {
    const multilineMessage: ChatMessageType = {
      id: 'msg-multi',
      role: 'user',
      content: 'Line 1\nLine 2\nLine 3',
      timestamp: new Date().toISOString(),
    };
    render(<ChatMessage message={multilineMessage} />);
    // The whitespace-pre-wrap class should preserve line breaks
    const contentElement = screen.getByText(/Line 1/);
    expect(contentElement).toHaveClass('whitespace-pre-wrap');
  });

  test('source reference without page number displays correctly', () => {
    const messageWithPagelessSource: ChatMessageType = {
      id: 'msg-4',
      role: 'assistant',
      content: 'Here is the information.',
      timestamp: new Date().toISOString(),
      sources: [
        {
          documentId: 'doc-3',
          documentName: 'summary.pdf',
        },
      ],
    };
    render(<ChatMessage message={messageWithPagelessSource} />);
    expect(screen.getByText('summary.pdf')).toBeInTheDocument();
    expect(screen.queryByText(/\(p\./)).not.toBeInTheDocument();
  });

  test('empty sources array does not render source section', () => {
    const messageWithEmptySources: ChatMessageType = {
      id: 'msg-5',
      role: 'assistant',
      content: 'No sources here.',
      timestamp: new Date().toISOString(),
      sources: [],
    };
    render(<ChatMessage message={messageWithEmptySources} />);
    expect(screen.queryByTestId('source-reference')).not.toBeInTheDocument();
  });

  test('user message has correct aria-label', () => {
    render(<ChatMessage message={userMessage} />);
    expect(screen.getByRole('article', { name: 'Your message' })).toBeInTheDocument();
  });

  test('assistant message has correct aria-label', () => {
    render(<ChatMessage message={assistantMessage} />);
    expect(screen.getByRole('article', { name: 'LDIP assistant message' })).toBeInTheDocument();
  });

  test('handles invalid timestamp gracefully', () => {
    const invalidTimestampMessage: ChatMessageType = {
      id: 'msg-invalid',
      role: 'user',
      content: 'Test message',
      timestamp: 'invalid-date-string',
    };
    render(<ChatMessage message={invalidTimestampMessage} />);
    expect(screen.getByText('Unknown time')).toBeInTheDocument();
  });
});
