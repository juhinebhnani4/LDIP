import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentsHeader } from './DocumentsHeader';
import type { DocumentType } from '@/types/document';

describe('DocumentsHeader', () => {
  const defaultProps = {
    totalCount: 42,
    processingCount: 0,
    processingPercent: 0,
    typeBreakdown: {
      case_file: 20,
      act: 12,
      annexure: 8,
      other: 2,
    } as Record<DocumentType, number>,
    onAddFiles: vi.fn(),
  };

  it('renders title and total count', () => {
    render(<DocumentsHeader {...defaultProps} />);

    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('42 documents in this matter')).toBeInTheDocument();
  });

  it('renders singular form for single document', () => {
    render(<DocumentsHeader {...defaultProps} totalCount={1} />);

    expect(screen.getByText('1 document in this matter')).toBeInTheDocument();
  });

  it('renders Add Files button', () => {
    render(<DocumentsHeader {...defaultProps} />);

    expect(screen.getByRole('button', { name: /add files/i })).toBeInTheDocument();
  });

  it('calls onAddFiles when button is clicked', async () => {
    const user = userEvent.setup();
    const onAddFiles = vi.fn();
    render(<DocumentsHeader {...defaultProps} onAddFiles={onAddFiles} />);

    await user.click(screen.getByRole('button', { name: /add files/i }));

    expect(onAddFiles).toHaveBeenCalledTimes(1);
  });

  describe('Type Breakdown', () => {
    it('renders type badges with counts', () => {
      render(<DocumentsHeader {...defaultProps} />);

      expect(screen.getByText('Case Files:')).toBeInTheDocument();
      expect(screen.getByText('20')).toBeInTheDocument();

      expect(screen.getByText('Acts:')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();

      expect(screen.getByText('Annexures:')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();

      expect(screen.getByText('Other:')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('does not render type badges with zero count', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          typeBreakdown={{
            case_file: 10,
            act: 0,
            annexure: 0,
            other: 0,
          }}
        />
      );

      expect(screen.getByText('Case Files:')).toBeInTheDocument();
      expect(screen.queryByText('Acts:')).not.toBeInTheDocument();
      expect(screen.queryByText('Annexures:')).not.toBeInTheDocument();
      expect(screen.queryByText('Other:')).not.toBeInTheDocument();
    });

    it('does not render type section when total count is zero', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          totalCount={0}
          typeBreakdown={{
            case_file: 0,
            act: 0,
            annexure: 0,
            other: 0,
          }}
        />
      );

      expect(screen.queryByText('Case Files:')).not.toBeInTheDocument();
    });
  });

  describe('Processing Banner', () => {
    it('does not show processing banner when processingCount is 0', () => {
      render(<DocumentsHeader {...defaultProps} processingCount={0} />);

      expect(screen.queryByText(/processing new documents/i)).not.toBeInTheDocument();
    });

    it('shows processing banner with singular form', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          processingCount={1}
          processingPercent={5}
        />
      );

      expect(screen.getByText(/processing new documents: 1 file, 5%/i)).toBeInTheDocument();
    });

    it('shows processing banner with plural form', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          processingCount={5}
          processingPercent={12}
        />
      );

      expect(screen.getByText(/processing new documents: 5 files, 12%/i)).toBeInTheDocument();
    });

    it('renders progress bar when processing', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          processingCount={3}
          processingPercent={25}
        />
      );

      // Check for the progress element (using aria-label)
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible icons with aria-hidden', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          processingCount={1}
          processingPercent={10}
        />
      );

      // Icons should have aria-hidden="true"
      const icons = document.querySelectorAll('[aria-hidden="true"]');
      expect(icons.length).toBeGreaterThan(0);
    });

    it('has accessible progress bar label', () => {
      render(
        <DocumentsHeader
          {...defaultProps}
          processingCount={1}
          processingPercent={25}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label', '75% complete');
    });
  });
});
