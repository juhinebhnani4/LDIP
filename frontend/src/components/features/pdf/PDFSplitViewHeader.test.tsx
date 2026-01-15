/**
 * PDFSplitViewHeader Unit Tests
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode (AC: #2, #5)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PDFSplitViewHeader } from './PDFSplitViewHeader';

describe('PDFSplitViewHeader', () => {
  const defaultProps = {
    documentName: 'Test Document.pdf',
    onClose: vi.fn(),
    onExpand: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders document name (AC: #2)', () => {
    render(<PDFSplitViewHeader {...defaultProps} />);

    expect(screen.getByText('Test Document.pdf')).toBeInTheDocument();
  });

  it('truncates long document names', () => {
    const longName = 'This is a very long document name that should be truncated in the UI.pdf';

    render(
      <PDFSplitViewHeader
        {...defaultProps}
        documentName={longName}
      />
    );

    const nameElement = screen.getByText(longName);
    expect(nameElement).toHaveClass('truncate');
    expect(nameElement).toHaveAttribute('title', longName);
  });

  it('renders expand button with correct title (AC: #2)', () => {
    render(<PDFSplitViewHeader {...defaultProps} />);

    const expandButton = screen.getByRole('button', { name: /open document in full screen/i });
    expect(expandButton).toBeInTheDocument();
    expect(expandButton).toHaveAttribute('title', 'Open full screen (F)');
  });

  it('renders close button with correct title (AC: #5)', () => {
    render(<PDFSplitViewHeader {...defaultProps} />);

    const closeButton = screen.getByRole('button', { name: /close pdf viewer/i });
    expect(closeButton).toBeInTheDocument();
    expect(closeButton).toHaveAttribute('title', 'Close (Esc)');
  });

  it('calls onClose when close button is clicked (AC: #5)', () => {
    const onClose = vi.fn();

    render(
      <PDFSplitViewHeader
        {...defaultProps}
        onClose={onClose}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /close pdf viewer/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onExpand when expand button is clicked', () => {
    const onExpand = vi.fn();

    render(
      <PDFSplitViewHeader
        {...defaultProps}
        onExpand={onExpand}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /open document in full screen/i }));

    expect(onExpand).toHaveBeenCalledTimes(1);
  });

  it('has correct header role and label for accessibility', () => {
    render(<PDFSplitViewHeader {...defaultProps} />);

    const header = screen.getByRole('banner', { name: /pdf viewer header/i });
    expect(header).toBeInTheDocument();
  });

  it('displays document name as aria-label for accessibility', () => {
    render(<PDFSplitViewHeader {...defaultProps} />);

    const nameElement = screen.getByLabelText(/document: test document\.pdf/i);
    expect(nameElement).toBeInTheDocument();
  });

  describe('page information display (AC: #2)', () => {
    it('displays page number and total pages when both are provided', () => {
      render(
        <PDFSplitViewHeader
          {...defaultProps}
          currentPage={5}
          totalPages={20}
        />
      );

      expect(screen.getByText('5 / 20')).toBeInTheDocument();
    });

    it('does not display page info when currentPage is undefined', () => {
      render(
        <PDFSplitViewHeader
          {...defaultProps}
          totalPages={20}
        />
      );

      expect(screen.queryByText(/\/ 20/)).not.toBeInTheDocument();
    });

    it('does not display page info when totalPages is undefined', () => {
      render(
        <PDFSplitViewHeader
          {...defaultProps}
          currentPage={5}
        />
      );

      expect(screen.queryByText(/5 \//)).not.toBeInTheDocument();
    });

    it('has correct aria-label for page info', () => {
      render(
        <PDFSplitViewHeader
          {...defaultProps}
          currentPage={3}
          totalPages={10}
        />
      );

      const pageInfo = screen.getByLabelText('Page 3 of 10');
      expect(pageInfo).toBeInTheDocument();
    });
  });
});
