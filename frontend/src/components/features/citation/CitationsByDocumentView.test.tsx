/**
 * CitationsByDocumentView Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CitationsByDocumentView } from './CitationsByDocumentView';
import type { CitationListItem } from '@/types/citation';

const mockCitations: CitationListItem[] = [
  {
    id: 'cit-1',
    actName: 'Securities Act, 1992',
    sectionNumber: '3',
    subsection: '3',
    clause: null,
    rawCitationText: 'Section 3(3) of the Securities Act',
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
    sourcePage: 50,
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
    sourcePage: 12,
    verificationStatus: 'pending',
    confidence: 90.0,
    documentId: 'doc-2',
    documentName: 'Reply.pdf',
  },
];

describe('CitationsByDocumentView', () => {
  const defaultProps = {
    citations: mockCitations,
  };

  it('renders document groups as collapsible sections', () => {
    render(<CitationsByDocumentView {...defaultProps} />);

    expect(screen.getByText('Petition.pdf')).toBeInTheDocument();
    expect(screen.getByText('Reply.pdf')).toBeInTheDocument();
  });

  it('shows citation and page count for each document', () => {
    render(<CitationsByDocumentView {...defaultProps} />);

    expect(screen.getByText(/2 citations? on 2 pages?/)).toBeInTheDocument();
    expect(screen.getByText(/1 citation on 1 page/)).toBeInTheDocument();
  });

  it('shows page range badge', () => {
    render(<CitationsByDocumentView {...defaultProps} />);

    expect(screen.getByText('Pages: 45-50')).toBeInTheDocument();
    expect(screen.getByText('Pages: 12-12')).toBeInTheDocument();
  });

  it('shows Issues badge for documents with problematic citations', () => {
    render(<CitationsByDocumentView {...defaultProps} />);

    // Petition.pdf has a mismatch citation
    const issuesBadges = screen.getAllByText('Issues');
    expect(issuesBadges.length).toBe(1);
  });

  it('expands document on click to show citations', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    // Click on Petition.pdf to expand
    await user.click(screen.getByText('Petition.pdf'));

    // Should show citations in table
    expect(screen.getByText('Page')).toBeInTheDocument();
    expect(screen.getByText('Citation')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();
  });

  it('collapses document on second click', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    // Click to expand
    await user.click(screen.getByText('Petition.pdf'));
    expect(screen.getByText('Section 3(3) of the Securities Act')).toBeInTheDocument();

    // Click to collapse
    await user.click(screen.getByText('Petition.pdf'));

    // Content should be removed from DOM or hidden after collapse
    await vi.waitFor(() => {
      const content = screen.queryByText('Section 3(3) of the Securities Act');
      expect(content === null || !content.checkVisibility()).toBeTruthy();
    });
  });

  it('shows citation details within document', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    await user.click(screen.getByText('Petition.pdf'));

    expect(screen.getByText('Securities Act, 1992 § 3.3')).toBeInTheDocument();
    expect(screen.getByText('Section 3(3) of the Securities Act')).toBeInTheDocument();
  });

  it('shows page number as clickable', async () => {
    const user = userEvent.setup();
    const onDocumentClick = vi.fn();

    render(<CitationsByDocumentView {...defaultProps} onDocumentClick={onDocumentClick} />);

    await user.click(screen.getByText('Petition.pdf'));
    await user.click(screen.getByText('45'));

    expect(onDocumentClick).toHaveBeenCalledWith('doc-1', 45);
  });

  it('shows status with icon and label', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    await user.click(screen.getByText('Petition.pdf'));

    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Mismatch')).toBeInTheDocument();
  });

  it('shows View button for each citation', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    await user.click(screen.getByText('Petition.pdf'));

    // Should have action buttons in the table rows
    const tableRows = document.querySelectorAll('tbody tr');
    expect(tableRows.length).toBeGreaterThan(0);
    // Each row should have action buttons
    const actionButtons = document.querySelectorAll('td button');
    expect(actionButtons.length).toBeGreaterThan(0);
  });

  it('shows Fix button for citations with issues', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    await user.click(screen.getByText('Petition.pdf'));

    // Mismatch citation should have a fix button (wrench icon)
    const mismatchRow = screen.getByText('Mismatch').closest('tr');
    expect(mismatchRow?.querySelectorAll('button').length).toBeGreaterThan(1);
  });

  it('calls onViewCitation when View button clicked', async () => {
    const user = userEvent.setup();
    const onViewCitation = vi.fn();

    render(<CitationsByDocumentView {...defaultProps} onViewCitation={onViewCitation} />);

    await user.click(screen.getByText('Petition.pdf'));

    // Wait for the expanded content to render
    await screen.findByText('Verified');

    // Click the first action button in the first data row
    const rows = document.querySelectorAll('tbody tr');
    const firstRow = rows[0];
    const viewButton = firstRow?.querySelector('td:last-child button');
    if (viewButton) {
      await user.click(viewButton);
    }

    expect(onViewCitation).toHaveBeenCalled();
  });

  it('calls onFixCitation when Fix button clicked', async () => {
    const user = userEvent.setup();
    const onFixCitation = vi.fn();

    render(<CitationsByDocumentView {...defaultProps} onFixCitation={onFixCitation} />);

    await user.click(screen.getByText('Petition.pdf'));

    // Wait for the expanded content to render
    await screen.findByText('Mismatch');

    // Find the mismatch row which has the fix button
    const mismatchRow = screen.getByText('Mismatch').closest('tr');
    expect(mismatchRow).toBeInTheDocument();

    // Find the action buttons in the last column
    const actionCell = mismatchRow?.querySelector('td:last-child');
    const buttons = actionCell?.querySelectorAll('button');

    // Mismatch row should have 2 buttons (View and Fix)
    expect(buttons?.length).toBe(2);

    // The fix button has a Wrench icon and text-destructive class on the button
    // Click the second button (the fix button)
    if (buttons && buttons[1]) {
      await user.click(buttons[1]);
      expect(onFixCitation).toHaveBeenCalledWith('cit-2');
    }
  });

  it('sorts citations by page within document', async () => {
    const user = userEvent.setup();
    render(<CitationsByDocumentView {...defaultProps} />);

    await user.click(screen.getByText('Petition.pdf'));

    // Citations should be sorted by page (45, then 50)
    const rows = screen.getAllByRole('row').filter(row => row.querySelector('td'));
    const pages = rows.map(row => row.querySelector('td')?.textContent).filter(Boolean);

    expect(pages).toEqual(['45', '50']);
  });

  it('shows loading state', () => {
    render(<CitationsByDocumentView {...defaultProps} isLoading={true} />);

    expect(screen.queryByText('Petition.pdf')).not.toBeInTheDocument();
  });

  it('shows error state', () => {
    render(<CitationsByDocumentView {...defaultProps} error="Failed to load" />);

    expect(screen.getByText('Failed to load')).toBeInTheDocument();
  });

  it('shows empty state when no citations', () => {
    render(<CitationsByDocumentView citations={[]} />);

    expect(screen.getByText('No citations found')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <CitationsByDocumentView {...defaultProps} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('handles citations with unknown document name', () => {
    const baseCitation = mockCitations[0];
    const citationsWithUnknown: CitationListItem[] = baseCitation
      ? [{ ...baseCitation, documentName: null }]
      : [];

    render(<CitationsByDocumentView citations={citationsWithUnknown} />);

    expect(screen.getByText('Unknown Document')).toBeInTheDocument();
  });
});
