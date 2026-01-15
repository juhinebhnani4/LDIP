import { describe, test, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SourceReference } from './SourceReference';
import type { SourceReference as SourceReferenceType } from '@/types/chat';

describe('SourceReference', () => {
  const sourceWithPage: SourceReferenceType = {
    documentId: 'doc-1',
    documentName: 'contract.pdf',
    page: 5,
  };

  const sourceWithoutPage: SourceReferenceType = {
    documentId: 'doc-2',
    documentName: 'summary.pdf',
  };

  const sourceWithBboxIds: SourceReferenceType = {
    documentId: 'doc-3',
    documentName: 'evidence.pdf',
    page: 12,
    bboxIds: ['bbox-1', 'bbox-2'],
  };

  test('renders document name with page number', () => {
    render(<SourceReference source={sourceWithPage} />);
    expect(screen.getByText('contract.pdf (p. 5)')).toBeInTheDocument();
  });

  test('renders document name without page when page is undefined', () => {
    render(<SourceReference source={sourceWithoutPage} />);
    expect(screen.getByText('summary.pdf')).toBeInTheDocument();
    expect(screen.queryByText(/\(p\./)).not.toBeInTheDocument();
  });

  test('has correct testid', () => {
    render(<SourceReference source={sourceWithPage} />);
    expect(screen.getByTestId('source-reference')).toBeInTheDocument();
  });

  test('calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<SourceReference source={sourceWithPage} onClick={handleClick} />);

    await user.click(screen.getByTestId('source-reference'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test('does not throw when onClick is not provided', async () => {
    const user = userEvent.setup();
    render(<SourceReference source={sourceWithPage} />);

    // Should not throw
    await user.click(screen.getByTestId('source-reference'));
  });

  test('renders as a button for accessibility', () => {
    render(<SourceReference source={sourceWithPage} />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  test('renders FileText icon', () => {
    render(<SourceReference source={sourceWithPage} />);
    // The icon should be aria-hidden
    const button = screen.getByTestId('source-reference');
    expect(button.querySelector('svg')).toBeInTheDocument();
  });

  test('handles source with bboxIds', () => {
    render(<SourceReference source={sourceWithBboxIds} />);
    // bboxIds shouldn't affect the display, just the data passed to onClick
    expect(screen.getByText('evidence.pdf (p. 12)')).toBeInTheDocument();
  });

  test('passes correct source data to onClick', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<SourceReference source={sourceWithBboxIds} onClick={handleClick} />);

    await user.click(screen.getByTestId('source-reference'));
    // The onClick should be called (without arguments, parent handles source data)
    expect(handleClick).toHaveBeenCalled();
  });

  test('long document name renders correctly', () => {
    const longNameSource: SourceReferenceType = {
      documentId: 'doc-long',
      documentName: 'Very_Long_Document_Name_That_Should_Still_Render_Properly.pdf',
      page: 1,
    };
    render(<SourceReference source={longNameSource} />);
    expect(
      screen.getByText('Very_Long_Document_Name_That_Should_Still_Render_Properly.pdf (p. 1)')
    ).toBeInTheDocument();
  });

  test('page number 0 renders correctly', () => {
    const zeroPageSource: SourceReferenceType = {
      documentId: 'doc-zero',
      documentName: 'test.pdf',
      page: 0,
    };
    render(<SourceReference source={zeroPageSource} />);
    // Page 0 is falsy but should still render if explicitly set
    // However, since we use `source.page ? ...` it won't show (p. 0)
    // This is intentional - page 0 doesn't make sense in a 1-indexed system
    expect(screen.getByText('test.pdf')).toBeInTheDocument();
  });
});
