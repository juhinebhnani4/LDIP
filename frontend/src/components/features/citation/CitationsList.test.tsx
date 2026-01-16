/**
 * CitationsList Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 * @see Story 10C.4 - Split-View moved to CitationsContent level
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CitationsList } from './CitationsList';
import type { CitationListItem, PaginationMeta } from '@/types/citation';

// Note: useSplitView mock removed in Story 10C.4 - split-view now handled at CitationsContent level

const mockCitations: CitationListItem[] = [
  {
    id: 'cit-1',
    actName: 'Securities Act, 1992',
    sectionNumber: '3',
    subsection: '3',
    clause: null,
    rawCitationText: 'Section 3(3) of the Securities Act, 1992',
    sourcePage: 45,
    verificationStatus: 'verified',
    confidence: 95.0,
    documentId: 'doc-1',
    documentName: 'Petition.pdf',
  },
  {
    id: 'cit-2',
    actName: 'Negotiable Instruments Act, 1881',
    sectionNumber: '138',
    subsection: null,
    clause: null,
    rawCitationText: 'Section 138 of the NI Act',
    sourcePage: 12,
    verificationStatus: 'mismatch',
    confidence: 78.0,
    documentId: 'doc-1',
    documentName: 'Petition.pdf',
  },
  {
    id: 'cit-3',
    actName: 'Companies Act, 2013',
    sectionNumber: '42',
    subsection: null,
    clause: null,
    rawCitationText: 'Section 42 of Companies Act',
    sourcePage: 22,
    verificationStatus: 'pending',
    confidence: 90.0,
    documentId: 'doc-2',
    documentName: 'Reply.pdf',
  },
];

const mockMeta: PaginationMeta = {
  total: 3,
  page: 1,
  perPage: 20,
  totalPages: 1,
};

describe('CitationsList', () => {
  const defaultProps = {
    citations: mockCitations,
    meta: mockMeta,
  };

  it('renders citations table with correct columns', () => {
    render(<CitationsList {...defaultProps} />);

    // Check column headers
    expect(screen.getByText('Act Name')).toBeInTheDocument();
    expect(screen.getByText('Section')).toBeInTheDocument();
    expect(screen.getByText('Citation Text')).toBeInTheDocument();
    expect(screen.getByText('Source Doc')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Conf.')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('renders citation data correctly', () => {
    render(<CitationsList {...defaultProps} />);

    // Check citation content
    expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
    expect(screen.getByText('Section 3(3) of the Securities Act, 1992')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
  });

  it('displays section with subsection correctly', () => {
    render(<CitationsList {...defaultProps} />);

    // Securities Act has section 3 with subsection 3
    expect(screen.getByText('3.3')).toBeInTheDocument();
  });

  it('displays document name with page number', () => {
    render(<CitationsList {...defaultProps} />);

    // There are multiple documents with same name, so use getAllByText
    const docLinks = screen.getAllByText('Petition.pdf');
    expect(docLinks.length).toBeGreaterThan(0);
    expect(screen.getByText(/p\.45/)).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<CitationsList {...defaultProps} isLoading={true} />);

    // Should show skeleton loaders - the Skeleton component renders divs
    // We verify by checking that the actual citation text is NOT shown during loading
    expect(screen.queryByText('Securities Act, 1992')).not.toBeInTheDocument();
  });

  it('shows error state', () => {
    render(<CitationsList {...defaultProps} error="Failed to load citations" />);

    expect(screen.getByText('Failed to load citations')).toBeInTheDocument();
  });

  it('shows empty state when no citations', () => {
    render(<CitationsList {...defaultProps} citations={[]} />);

    expect(screen.getByText('No citations found')).toBeInTheDocument();
  });

  it('highlights issue rows', () => {
    render(<CitationsList {...defaultProps} />);

    // Mismatch row should have issue styling
    const mismatchRow = screen.getByText('Mismatch').closest('tr');
    expect(mismatchRow).toHaveClass('bg-destructive/5');
  });

  it('shows fix button for issue citations', () => {
    render(<CitationsList {...defaultProps} />);

    // Should have a wrench icon button for mismatch citation
    const fixButtons = screen.getAllByTitle('Fix issue');
    expect(fixButtons.length).toBeGreaterThan(0);
  });

  it('renders confidence with correct color for high confidence', () => {
    render(<CitationsList {...defaultProps} />);

    // 95% should be green
    const highConfidence = screen.getByText('95%');
    expect(highConfidence).toHaveClass('text-green-600');
  });

  it('renders confidence with correct color for medium confidence', () => {
    render(<CitationsList {...defaultProps} />);

    // 78% should be amber (between 70-90)
    const medConfidence = screen.getByText('78%');
    expect(medConfidence).toHaveClass('text-amber-600');
  });

  it('has sortable columns with aria-sort attributes', () => {
    render(<CitationsList {...defaultProps} />);

    // Act Name column should have sorting - aria-sort is now on TableHead (th), not button
    const actNameHeader = screen.getByText('Act Name');
    expect(actNameHeader.closest('th')).toHaveAttribute('aria-sort');
  });

  it('changes sort direction when clicking column header twice', async () => {
    const user = userEvent.setup();
    render(<CitationsList {...defaultProps} />);

    const actNameButton = screen.getByText('Act Name').closest('button');
    const actNameTh = screen.getByText('Act Name').closest('th');

    // Act Name is the default sort field, starts as ascending
    // aria-sort is now on the th element, not the button
    expect(actNameTh).toHaveAttribute('aria-sort', 'ascending');

    // First click on same column - toggle to descending
    await user.click(actNameButton!);
    expect(actNameTh).toHaveAttribute('aria-sort', 'descending');

    // Second click - toggle back to ascending
    await user.click(actNameButton!);
    expect(actNameTh).toHaveAttribute('aria-sort', 'ascending');
  });

  it('sorts citations when clicking column header', async () => {
    const user = userEvent.setup();
    render(<CitationsList {...defaultProps} />);

    // Click confidence header to sort by confidence
    const confButton = screen.getByText('Conf.').closest('button');
    await user.click(confButton!);

    // Get all confidence values in order
    const confCells = screen.getAllByText(/%$/);
    const values = confCells.map(el => parseInt(el.textContent!));

    // Should be sorted ascending
    expect(values).toEqual([...values].sort((a, b) => a - b));
  });

  it('does not show pagination for small datasets', () => {
    render(<CitationsList {...defaultProps} />);

    expect(screen.queryByText(/Page \d+ of \d+/)).not.toBeInTheDocument();
  });

  it('shows pagination for large datasets', () => {
    const largeMeta: PaginationMeta = {
      total: 50,
      page: 1,
      perPage: 20,
      totalPages: 3,
    };

    render(<CitationsList {...defaultProps} meta={largeMeta} />);

    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });

  it('calls onPageChange when pagination buttons clicked', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    const largeMeta: PaginationMeta = {
      total: 50,
      page: 1,
      perPage: 20,
      totalPages: 3,
    };

    render(
      <CitationsList
        {...defaultProps}
        meta={largeMeta}
        onPageChange={onPageChange}
      />
    );

    await user.click(screen.getByRole('button', { name: /next/i }));

    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('disables previous button on first page', () => {
    const largeMeta: PaginationMeta = {
      total: 50,
      page: 1,
      perPage: 20,
      totalPages: 3,
    };

    render(<CitationsList {...defaultProps} meta={largeMeta} currentPage={1} />);

    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
  });

  it('disables next button on last page', () => {
    const largeMeta: PaginationMeta = {
      total: 50,
      page: 3,
      perPage: 20,
      totalPages: 3,
    };

    render(<CitationsList {...defaultProps} meta={largeMeta} currentPage={3} />);

    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
  });

  it('calls onDocumentClick when document name is clicked', async () => {
    const user = userEvent.setup();
    const onDocumentClick = vi.fn();

    render(
      <CitationsList
        {...defaultProps}
        onDocumentClick={onDocumentClick}
      />
    );

    // Find the first document link (sorted by Act Name ascending: Companies Act first)
    const docLinks = screen.getAllByText('Petition.pdf');
    const firstLink = docLinks[0];
    if (firstLink) {
      await user.click(firstLink);
    }

    // After sorting by Act Name, Companies Act (page 22) or Negotiable Instruments (page 12) or Securities (page 45)
    // The actual order depends on alphabetical Act Name order
    expect(onDocumentClick).toHaveBeenCalledWith('doc-1', expect.any(Number));
  });

  it('renders view button for each citation', () => {
    render(<CitationsList {...defaultProps} />);

    const viewButtons = screen.getAllByTitle('View in split view');
    expect(viewButtons).toHaveLength(3);
  });

  it('calls onViewCitation when view button is clicked (Story 10C.4)', async () => {
    const user = userEvent.setup();
    const onViewCitation = vi.fn();

    render(
      <CitationsList
        {...defaultProps}
        onViewCitation={onViewCitation}
      />
    );

    // Click the first View button
    const viewButtons = screen.getAllByTitle('View in split view');
    expect(viewButtons.length).toBeGreaterThan(0);
    await user.click(viewButtons[0]!);

    // Should call with the citation ID (order depends on default sorting by actName)
    expect(onViewCitation).toHaveBeenCalledWith(expect.any(String));
  });

  it('calls onViewCitation when fix button is clicked (Story 10C.4)', async () => {
    const user = userEvent.setup();
    const onViewCitation = vi.fn();

    render(
      <CitationsList
        {...defaultProps}
        onViewCitation={onViewCitation}
      />
    );

    // Click the Fix button (only shows for mismatch/section_not_found)
    const fixButtons = screen.getAllByTitle('Fix issue');
    expect(fixButtons.length).toBeGreaterThan(0);
    await user.click(fixButtons[0]!);

    expect(onViewCitation).toHaveBeenCalled();
  });

  it('shows status badges with correct variants', () => {
    render(<CitationsList {...defaultProps} />);

    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Mismatch')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });
});
