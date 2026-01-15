/**
 * CitationLink Component Tests
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #4)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CitationLink } from './CitationLink';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-123' }),
}));

describe('CitationLink', () => {
  const defaultProps = {
    documentName: 'petition.pdf',
    pageNumber: 5,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders link with page number', () => {
    render(<CitationLink {...defaultProps} />);

    const link = screen.getByRole('link');
    expect(link).toHaveTextContent('pg. 5');
  });

  it('renders link with custom display text', () => {
    render(
      <CitationLink
        {...defaultProps}
        displayText="View Source"
      />
    );

    const link = screen.getByRole('link');
    expect(link).toHaveTextContent('View Source');
  });

  it('shows tooltip on hover with document name', async () => {
    const user = userEvent.setup();

    render(<CitationLink {...defaultProps} />);

    const link = screen.getByRole('link');
    await user.hover(link);

    // Tooltip should show document name (use findAllByText because radix may duplicate)
    const docNameElements = await screen.findAllByText(/petition\.pdf/i);
    expect(docNameElements.length).toBeGreaterThan(0);
  });

  it('shows excerpt in tooltip when provided', async () => {
    const user = userEvent.setup();

    render(
      <CitationLink
        {...defaultProps}
        excerpt="This is a sample excerpt from the document"
      />
    );

    const link = screen.getByRole('link');
    await user.hover(link);

    // Tooltip should show excerpt
    const excerptElements = await screen.findAllByText(/sample excerpt/i);
    expect(excerptElements.length).toBeGreaterThan(0);
  });

  it('navigates to documents tab with correct params', () => {
    render(<CitationLink {...defaultProps} />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute(
      'href',
      '/matters/test-matter-123/documents?doc=petition.pdf&page=5'
    );
  });

  it('encodes document name in URL', () => {
    render(
      <CitationLink
        documentName="some document with spaces.pdf"
        pageNumber={10}
      />
    );

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute(
      'href',
      '/matters/test-matter-123/documents?doc=some%20document%20with%20spaces.pdf&page=10'
    );
  });

  it('applies citation link styling', () => {
    render(<CitationLink {...defaultProps} />);

    const link = screen.getByRole('link');
    expect(link).toHaveClass('text-blue-600');
  });

  it('applies custom className', () => {
    render(<CitationLink {...defaultProps} className="custom-class" />);

    const link = screen.getByRole('link');
    expect(link).toHaveClass('custom-class');
  });
});
