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

// Mock openDocumentByName to verify navigation calls
const mockOpenDocumentByName = vi.fn();
vi.mock('@/lib/utils/openDocument', () => ({
  openDocumentByName: (...args: unknown[]) => mockOpenDocumentByName(...args),
}));

describe('CitationLink', () => {
  const defaultProps = {
    documentName: 'petition.pdf',
    pageNumber: 5 as number | null,
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

  it('calls openDocumentByName with page number on click', async () => {
    const user = userEvent.setup();
    render(<CitationLink {...defaultProps} />);

    const link = screen.getByRole('link');
    await user.click(link);

    expect(mockOpenDocumentByName).toHaveBeenCalledWith(
      'test-matter-123',
      'petition.pdf',
      5
    );
  });

  it('calls openDocumentByName without page when page is null', async () => {
    const user = userEvent.setup();
    render(<CitationLink {...defaultProps} pageNumber={null} />);

    const link = screen.getByRole('link');
    await user.click(link);

    expect(mockOpenDocumentByName).toHaveBeenCalledWith(
      'test-matter-123',
      'petition.pdf',
      undefined
    );
  });

  it('renders document name when page is null and no displayText', () => {
    render(<CitationLink {...defaultProps} pageNumber={null} />);

    const link = screen.getByRole('link');
    expect(link).toHaveTextContent('petition.pdf');
    expect(link).not.toHaveTextContent('pg.');
  });

  it('truncates long document names when used as fallback', () => {
    render(
      <CitationLink
        documentName="Writ_Petition_Civil_No_12345_of_2024_filed_by_Petitioner.pdf"
        pageNumber={null}
      />
    );

    const link = screen.getByRole('link');
    // Should be truncated, not show the full 60-char filename
    expect(link.textContent!.length).toBeLessThanOrEqual(33);
  });

  it('renders displayText even when page is null', () => {
    render(
      <CitationLink
        {...defaultProps}
        pageNumber={null}
        displayText="Order, p. 3"
      />
    );

    const link = screen.getByRole('link');
    expect(link).toHaveTextContent('Order, p. 3');
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
