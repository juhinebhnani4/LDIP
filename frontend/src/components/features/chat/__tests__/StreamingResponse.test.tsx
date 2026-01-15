/**
 * Tests for StreamingResponse Component
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 12: Write comprehensive tests (AC: #1)
 */

import { render, screen } from '@testing-library/react';
import { StreamingResponse } from '../StreamingResponse';

describe('StreamingResponse', () => {
  it('shows typing indicator when typing and no content', () => {
    render(
      <StreamingResponse
        content=""
        isTyping={true}
        isStreaming={true}
      />
    );

    expect(screen.getByText('LDIP is thinking...')).toBeInTheDocument();
  });

  it('hides typing indicator when content starts arriving', () => {
    render(
      <StreamingResponse
        content="Hello"
        isTyping={false}
        isStreaming={true}
      />
    );

    expect(screen.queryByText('LDIP is thinking...')).not.toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('displays accumulated content', () => {
    render(
      <StreamingResponse
        content="This is the accumulated response text."
        isTyping={false}
        isStreaming={true}
      />
    );

    expect(
      screen.getByText('This is the accumulated response text.')
    ).toBeInTheDocument();
  });

  it('shows cursor animation during streaming', () => {
    const { container } = render(
      <StreamingResponse
        content="Streaming..."
        isTyping={false}
        isStreaming={true}
      />
    );

    // Cursor should be present during streaming
    const cursor = container.querySelector('.animate-pulse');
    expect(cursor).toBeInTheDocument();
  });

  it('hides cursor when streaming completes', () => {
    const { container } = render(
      <StreamingResponse
        content="Complete response."
        isTyping={false}
        isStreaming={false}
      />
    );

    // Cursor should not be present after streaming
    const cursor = container.querySelector('.animate-pulse');
    expect(cursor).not.toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(
      <StreamingResponse
        content=""
        isTyping={true}
        isStreaming={true}
      />
    );

    const statusElement = screen.getByRole('status');
    expect(statusElement).toBeInTheDocument();
    expect(statusElement).toHaveAttribute('aria-live', 'polite');
  });

  it('has correct test id', () => {
    render(
      <StreamingResponse
        content="Test"
        isTyping={false}
        isStreaming={true}
      />
    );

    expect(screen.getByTestId('streaming-response')).toBeInTheDocument();
  });
});
