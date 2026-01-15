/**
 * MissingActsCard Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { MissingActsCard } from './MissingActsCard';
import type { ActDiscoverySummary } from '@/types/citation';

// Mock the ActUploadDropzone component
vi.mock('./ActUploadDropzone', () => ({
  ActUploadDropzone: ({
    actName,
    onUploadComplete,
    onCancel,
  }: {
    actName: string;
    onUploadComplete: (docId: string) => void;
    onCancel: () => void;
  }) => (
    <div data-testid="upload-dropzone">
      <p>Upload {actName}</p>
      <button onClick={() => onUploadComplete('doc-123')}>Simulate Upload</button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  ),
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockMissingActs: ActDiscoverySummary[] = [
  {
    actName: 'Negotiable Instruments Act, 1881',
    actNameNormalized: 'negotiable_instruments_act_1881',
    citationCount: 8,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  },
  {
    actName: 'Companies Act, 2013',
    actNameNormalized: 'companies_act_2013',
    citationCount: 5,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  },
];

const mockAllActs: ActDiscoverySummary[] = [
  ...mockMissingActs,
  {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 12,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-456',
  },
  {
    actName: 'Tax Act, 2000',
    actNameNormalized: 'tax_act_2000',
    citationCount: 3,
    resolutionStatus: 'skipped',
    userAction: 'skipped',
    actDocumentId: null,
  },
];

describe('MissingActsCard', () => {
  const defaultProps = {
    matterId: 'matter-123',
    acts: mockAllActs,
    onActUploadedAndVerify: vi.fn().mockResolvedValue(undefined),
    onActSkipped: vi.fn().mockResolvedValue(undefined),
  };

  it('renders missing acts with citation counts', () => {
    render(<MissingActsCard {...defaultProps} />);

    expect(screen.getByText('Missing Acts')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // Badge count
    expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();
    expect(screen.getByText('Companies Act, 2013')).toBeInTheDocument();
    expect(screen.getByText(/8 citations? cannot be verified/)).toBeInTheDocument();
    expect(screen.getByText(/5 citations? cannot be verified/)).toBeInTheDocument();
  });

  it('does not show available or skipped acts in main list', () => {
    render(<MissingActsCard {...defaultProps} />);

    expect(screen.queryByText('Securities Act, 1992')).not.toBeInTheDocument();
    // Skipped acts shown in summary only
    expect(screen.queryByText('Tax Act, 2000')).not.toBeInTheDocument();
  });

  it('shows skipped acts count in summary', () => {
    render(<MissingActsCard {...defaultProps} />);

    expect(screen.getByText(/1 Act skipped/)).toBeInTheDocument();
  });

  it('renders Upload and Skip buttons for each missing act', () => {
    render(<MissingActsCard {...defaultProps} />);

    const uploadButtons = screen.getAllByRole('button', { name: /upload/i });
    const skipButtons = screen.getAllByRole('button', { name: /skip/i });

    expect(uploadButtons.length).toBe(2);
    expect(skipButtons.length).toBe(2);
  });

  it('shows upload dropzone when Upload button clicked', async () => {
    const user = userEvent.setup();
    render(<MissingActsCard {...defaultProps} />);

    const uploadButtons = screen.getAllByRole('button', { name: /upload/i });
    const firstUpload = uploadButtons[0];
    if (firstUpload) {
      await user.click(firstUpload);
    }

    expect(screen.getByTestId('upload-dropzone')).toBeInTheDocument();
    expect(screen.getByText('Upload Negotiable Instruments Act, 1881')).toBeInTheDocument();
  });

  it('hides upload dropzone when Cancel clicked', async () => {
    const user = userEvent.setup();
    render(<MissingActsCard {...defaultProps} />);

    // Click upload to show dropzone
    const uploadButtons = screen.getAllByRole('button', { name: /upload/i });
    const firstUpload = uploadButtons[0];
    if (firstUpload) {
      await user.click(firstUpload);
    }

    // Click cancel
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByTestId('upload-dropzone')).not.toBeInTheDocument();
  });

  it('calls onActUploadedAndVerify after successful upload', async () => {
    const user = userEvent.setup();
    const onActUploadedAndVerify = vi.fn().mockResolvedValue(undefined);

    render(
      <MissingActsCard
        {...defaultProps}
        onActUploadedAndVerify={onActUploadedAndVerify}
      />
    );

    // Click upload to show dropzone
    const uploadButtons = screen.getAllByRole('button', { name: /upload/i });
    const firstUpload = uploadButtons[0];
    if (firstUpload) {
      await user.click(firstUpload);
    }

    // Simulate upload completion
    await user.click(screen.getByRole('button', { name: 'Simulate Upload' }));

    expect(onActUploadedAndVerify).toHaveBeenCalledWith(
      'Negotiable Instruments Act, 1881',
      'doc-123'
    );
  });

  it('calls onActSkipped when Skip button clicked', async () => {
    const user = userEvent.setup();
    const onActSkipped = vi.fn().mockResolvedValue(undefined);

    render(
      <MissingActsCard
        {...defaultProps}
        onActSkipped={onActSkipped}
      />
    );

    const skipButtons = screen.getAllByRole('button', { name: /skip/i });
    const firstSkip = skipButtons[0];
    if (firstSkip) {
      await user.click(firstSkip);
    }

    expect(onActSkipped).toHaveBeenCalledWith('Negotiable Instruments Act, 1881');
  });

  it('does not render when no missing acts', () => {
    const noMissingActs: ActDiscoverySummary[] = [
      {
        actName: 'Securities Act, 1992',
        actNameNormalized: 'securities_act_1992',
        citationCount: 12,
        resolutionStatus: 'available',
        userAction: 'uploaded',
        actDocumentId: 'doc-456',
      },
    ];

    const { container } = render(
      <MissingActsCard {...defaultProps} acts={noMissingActs} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('shows loading state', () => {
    render(<MissingActsCard {...defaultProps} isLoading={true} />);

    // Should show spinner (the acts list won't be visible)
    expect(screen.getByText('Missing Acts')).toBeInTheDocument();
  });

  it('can be collapsed and expanded', async () => {
    const user = userEvent.setup();
    render(<MissingActsCard {...defaultProps} />);

    // Initially expanded
    expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();

    // Click header to collapse
    await user.click(screen.getByText('Missing Acts'));

    // Collapsible content should be removed or hidden from DOM
    // After collapse, the text should not be in the document
    await vi.waitFor(() => {
      expect(screen.queryByText('Negotiable Instruments Act, 1881')).not.toBeInTheDocument();
    });

    // Click to expand again
    await user.click(screen.getByText('Missing Acts'));

    expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <MissingActsCard {...defaultProps} className="custom-class" />
    );

    const card = container.querySelector('.custom-class');
    expect(card).toBeInTheDocument();
  });

  it('calls onRefresh after successful upload', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();

    render(
      <MissingActsCard
        {...defaultProps}
        onRefresh={onRefresh}
      />
    );

    // Click upload to show dropzone
    const uploadButtons = screen.getAllByRole('button', { name: /upload/i });
    const firstUpload = uploadButtons[0];
    if (firstUpload) {
      await user.click(firstUpload);
    }

    // Simulate upload completion
    await user.click(screen.getByRole('button', { name: 'Simulate Upload' }));

    expect(onRefresh).toHaveBeenCalled();
  });

  it('calls onRefresh after skip', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();

    render(
      <MissingActsCard
        {...defaultProps}
        onRefresh={onRefresh}
      />
    );

    const skipButtons = screen.getAllByRole('button', { name: /skip/i });
    const firstSkip = skipButtons[0];
    if (firstSkip) {
      await user.click(firstSkip);
    }

    expect(onRefresh).toHaveBeenCalled();
  });
});
