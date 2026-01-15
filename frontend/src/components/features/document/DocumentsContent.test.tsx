import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentsContent, DocumentsSkeleton, DocumentsError } from './DocumentsContent';
import type { DocumentListItem } from '@/types/document';

// Mock the useDocuments hook
vi.mock('@/hooks/useDocuments', () => ({
  useDocuments: vi.fn(),
}));

// Mock the child components to isolate testing
vi.mock('./DocumentList', () => ({
  DocumentList: ({ matterId }: { matterId: string }) => (
    <div data-testid="document-list">DocumentList: {matterId}</div>
  ),
}));

vi.mock('./DocumentsHeader', () => ({
  DocumentsHeader: ({
    totalCount,
    processingCount,
    onAddFiles,
  }: {
    totalCount: number;
    processingCount: number;
    onAddFiles: () => void;
  }) => (
    <div data-testid="documents-header">
      <span>Total: {totalCount}</span>
      <span>Processing: {processingCount}</span>
      <button onClick={onAddFiles}>ADD FILES</button>
    </div>
  ),
}));

vi.mock('./AddDocumentsDialog', () => ({
  AddDocumentsDialog: ({
    open,
    onOpenChange,
    matterId,
    onComplete,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    matterId: string;
    onComplete?: () => void;
  }) => (
    <div data-testid="add-documents-dialog" data-open={open}>
      Dialog: {matterId}
      <button onClick={() => onOpenChange(false)}>Close</button>
      <button onClick={onComplete}>Complete</button>
    </div>
  ),
}));

// Import mocked hook for manipulation
import { useDocuments } from '@/hooks/useDocuments';

const mockDocuments: DocumentListItem[] = [
  {
    id: 'doc-1',
    matterId: 'matter-123',
    filename: 'petition.pdf',
    fileSize: 102400,
    pageCount: 25,
    documentType: 'case_file',
    isReferenceMaterial: false,
    status: 'completed',
    uploadedAt: '2024-01-15T10:00:00Z',
    uploadedBy: 'user-1',
    ocrConfidence: 0.92,
    ocrQualityStatus: 'good',
  },
  {
    id: 'doc-2',
    matterId: 'matter-123',
    filename: 'contract_act.pdf',
    fileSize: 204800,
    pageCount: 120,
    documentType: 'act',
    isReferenceMaterial: true,
    status: 'processing',
    uploadedAt: '2024-01-14T10:00:00Z',
    uploadedBy: 'user-1',
    ocrConfidence: null,
    ocrQualityStatus: null,
  },
];

describe('DocumentsContent', () => {
  const matterId = 'matter-123';
  const mockRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Default successful response
    (useDocuments as ReturnType<typeof vi.fn>).mockReturnValue({
      documents: mockDocuments,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      totalCount: 2,
      hasProcessing: true,
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when loading and no data', () => {
      (useDocuments as ReturnType<typeof vi.fn>).mockReturnValue({
        documents: [],
        isLoading: true,
        error: null,
        refresh: mockRefresh,
        totalCount: 0,
        hasProcessing: false,
      });

      render(<DocumentsContent matterId={matterId} />);

      // Should render the skeleton loader
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Error State', () => {
    it('renders error when error occurs and no data', () => {
      (useDocuments as ReturnType<typeof vi.fn>).mockReturnValue({
        documents: [],
        isLoading: false,
        error: 'Network error',
        refresh: mockRefresh,
        totalCount: 0,
        hasProcessing: false,
      });

      render(<DocumentsContent matterId={matterId} />);

      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('shows inline error when data exists but error occurs', async () => {
      (useDocuments as ReturnType<typeof vi.fn>).mockReturnValue({
        documents: mockDocuments,
        isLoading: false,
        error: 'Refresh failed',
        refresh: mockRefresh,
        totalCount: 2,
        hasProcessing: false,
      });

      render(<DocumentsContent matterId={matterId} />);

      // Should show inline error message
      expect(screen.getByText('Refresh failed')).toBeInTheDocument();

      // But also show the document list
      expect(screen.getByTestId('document-list')).toBeInTheDocument();
    });
  });

  describe('Rendering', () => {
    it('renders header with correct counts', async () => {
      render(<DocumentsContent matterId={matterId} />);

      expect(screen.getByTestId('documents-header')).toBeInTheDocument();
      expect(screen.getByText('Total: 2')).toBeInTheDocument();
      expect(screen.getByText('Processing: 1')).toBeInTheDocument();
    });

    it('renders document list with matterId', async () => {
      render(<DocumentsContent matterId={matterId} />);

      expect(screen.getByTestId('document-list')).toBeInTheDocument();
      expect(screen.getByText(`DocumentList: ${matterId}`)).toBeInTheDocument();
    });
  });

  describe('Add Files Dialog', () => {
    it('opens dialog when Add Files button is clicked', async () => {
      const user = userEvent.setup();
      render(<DocumentsContent matterId={matterId} />);

      // Dialog should be closed initially
      expect(screen.getByTestId('add-documents-dialog')).toHaveAttribute('data-open', 'false');

      // Click add files button
      await user.click(screen.getByRole('button', { name: /add files/i }));

      // Dialog should be open
      expect(screen.getByTestId('add-documents-dialog')).toHaveAttribute('data-open', 'true');
    });

    it('closes dialog and refreshes on complete', async () => {
      const user = userEvent.setup();
      render(<DocumentsContent matterId={matterId} />);

      // Open dialog
      await user.click(screen.getByRole('button', { name: /add files/i }));
      expect(screen.getByTestId('add-documents-dialog')).toHaveAttribute('data-open', 'true');

      // Click complete
      await user.click(screen.getByRole('button', { name: /complete/i }));

      // Dialog should be closed
      expect(screen.getByTestId('add-documents-dialog')).toHaveAttribute('data-open', 'false');

      // Should have called refresh
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  describe('Processing Stats', () => {
    it('calculates processing count correctly', async () => {
      render(<DocumentsContent matterId={matterId} />);

      // One document is processing
      expect(screen.getByText('Processing: 1')).toBeInTheDocument();
    });

    it('shows zero processing when none processing', async () => {
      const completedDocs = mockDocuments.map((d) => ({
        ...d,
        status: 'completed' as const,
      }));

      (useDocuments as ReturnType<typeof vi.fn>).mockReturnValue({
        documents: completedDocs,
        isLoading: false,
        error: null,
        refresh: mockRefresh,
        totalCount: 2,
        hasProcessing: false,
      });

      render(<DocumentsContent matterId={matterId} />);

      expect(screen.getByText('Processing: 0')).toBeInTheDocument();
    });
  });
});

describe('DocumentsSkeleton', () => {
  it('renders skeleton elements', () => {
    render(<DocumentsSkeleton />);

    const skeletons = document.querySelectorAll('[class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

describe('DocumentsError', () => {
  it('renders error message', () => {
    render(<DocumentsError message="Test error" />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Test error')).toBeInTheDocument();
  });

  it('renders default message when not provided', () => {
    render(<DocumentsError />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Failed to load documents. Please try refreshing the page.')).toBeInTheDocument();
  });
});
