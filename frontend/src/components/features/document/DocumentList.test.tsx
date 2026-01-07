import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import { DocumentList } from './DocumentList';
import type { DocumentListItem, DocumentListResponse } from '@/types/document';

// Mock the API module
vi.mock('@/lib/api/documents', () => ({
  fetchDocuments: vi.fn(),
  updateDocument: vi.fn(),
  bulkUpdateDocuments: vi.fn(),
}));

// Import mocked functions for manipulation
import { fetchDocuments, updateDocument, bulkUpdateDocuments } from '@/lib/api/documents';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

const mockDocuments: DocumentListItem[] = [
  {
    id: 'doc-1',
    matterId: 'matter-123',
    filename: 'petition.pdf',
    fileSize: 1024 * 100, // 100 KB
    documentType: 'case_file',
    isReferenceMaterial: false,
    status: 'completed',
    uploadedAt: '2024-01-15T10:00:00Z',
    uploadedBy: 'user-1',
  },
  {
    id: 'doc-2',
    matterId: 'matter-123',
    filename: 'indian_contract_act.pdf',
    fileSize: 1024 * 500, // 500 KB
    documentType: 'act',
    isReferenceMaterial: true,
    status: 'pending',
    uploadedAt: '2024-01-14T10:00:00Z',
    uploadedBy: 'user-1',
  },
  {
    id: 'doc-3',
    matterId: 'matter-123',
    filename: 'annexure_a.pdf',
    fileSize: 1024 * 250, // 250 KB
    documentType: 'annexure',
    isReferenceMaterial: false,
    status: 'processing',
    uploadedAt: '2024-01-13T10:00:00Z',
    uploadedBy: 'user-1',
  },
];

const mockResponse: DocumentListResponse = {
  data: mockDocuments,
  meta: {
    total: 3,
    page: 1,
    perPage: 20,
    totalPages: 1,
  },
};

describe('DocumentList', () => {
  const matterId = 'matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
    // Default successful response
    (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);
    (updateDocument as ReturnType<typeof vi.fn>).mockResolvedValue(mockDocuments[0]);
    (bulkUpdateDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
      updatedCount: 2,
      requestedCount: 2,
      documentType: 'act',
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows skeleton while loading', () => {
      // Make fetch hang indefinitely
      (fetchDocuments as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      render(<DocumentList matterId={matterId} />);

      // Should show multiple skeleton elements
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Rendering Documents', () => {
    it('renders document list after loading', async () => {
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
        expect(screen.getByText('indian_contract_act.pdf')).toBeInTheDocument();
        expect(screen.getByText('annexure_a.pdf')).toBeInTheDocument();
      });
    });

    it('displays document type badges', async () => {
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('Case File')).toBeInTheDocument();
        expect(screen.getByText('Act')).toBeInTheDocument();
        expect(screen.getByText('Annexure')).toBeInTheDocument();
      });
    });

    it('displays file sizes in human-readable format', async () => {
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('100.0 KB')).toBeInTheDocument();
        expect(screen.getByText('500.0 KB')).toBeInTheDocument();
        expect(screen.getByText('250.0 KB')).toBeInTheDocument();
      });
    });

    it('displays status labels', async () => {
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('Completed')).toBeInTheDocument();
        expect(screen.getByText('Pending')).toBeInTheDocument();
        expect(screen.getByText('Processing')).toBeInTheDocument();
      });
    });

    it('shows pending classification hint for pending documents', async () => {
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('Needs classification')).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no documents', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: [],
        meta: { total: 0, page: 1, perPage: 20, totalPages: 0 },
      });

      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('No documents found')).toBeInTheDocument();
        expect(screen.getByText('Upload documents to get started')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('shows error state on API failure', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });

    it('retries on Try Again button click', async () => {
      const user = userEvent.setup();

      // First call fails, second succeeds
      (fetchDocuments as ReturnType<typeof vi.fn>)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockResponse);

      render(<DocumentList matterId={matterId} />);

      // Wait for error state
      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Click retry
      await user.click(screen.getByRole('button', { name: /try again/i }));

      // Should reload and show documents
      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });
    });
  });

  describe('Selection', () => {
    it('allows selecting individual documents', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Find checkbox for first document
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[1]); // Index 0 is "select all"

      // Should show selection count
      expect(screen.getByText('1 selected')).toBeInTheDocument();
    });

    it('allows selecting all documents', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Click "select all" checkbox
      const selectAllCheckbox = screen.getAllByRole('checkbox')[0];
      await user.click(selectAllCheckbox);

      // Should show all selected
      expect(screen.getByText('3 selected')).toBeInTheDocument();
    });

    it('deselects all when clicking select all twice', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      const selectAllCheckbox = screen.getAllByRole('checkbox')[0];

      // Select all
      await user.click(selectAllCheckbox);
      expect(screen.getByText('3 selected')).toBeInTheDocument();

      // Deselect all
      await user.click(selectAllCheckbox);
      expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
    });
  });

  describe('Filtering', () => {
    it('calls API with type filter when selected', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Open type filter dropdown - find the trigger with "All types" text
      const typeFilters = screen.getAllByRole('combobox');
      const typeFilter = typeFilters[0]; // First combobox is the type filter
      await user.click(typeFilter);

      // Select "Act"
      const actOption = screen.getByRole('option', { name: /^act$/i });
      await user.click(actOption);

      // Should call API with filter
      await waitFor(() => {
        expect(fetchDocuments).toHaveBeenLastCalledWith(
          matterId,
          expect.objectContaining({
            filters: expect.objectContaining({ documentType: 'act' }),
          })
        );
      });
    });

    it('calls API with status filter when selected', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Open status filter dropdown - second combobox
      const statusFilters = screen.getAllByRole('combobox');
      const statusFilter = statusFilters[1]; // Second combobox is the status filter
      await user.click(statusFilter);

      // Select "Completed"
      const completedOption = screen.getByRole('option', { name: /completed/i });
      await user.click(completedOption);

      // Should call API with filter
      await waitFor(() => {
        expect(fetchDocuments).toHaveBeenLastCalledWith(
          matterId,
          expect.objectContaining({
            filters: expect.objectContaining({ status: 'completed' }),
          })
        );
      });
    });
  });

  describe('Pagination', () => {
    it('shows pagination controls when multiple pages exist', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: mockDocuments,
        meta: { total: 100, page: 1, perPage: 20, totalPages: 5 },
      });

      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText(/page 1 of 5/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
      });
    });

    it('disables Previous button on first page', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: mockDocuments,
        meta: { total: 100, page: 1, perPage: 20, totalPages: 5 },
      });

      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        const prevButton = screen.getByRole('button', { name: /previous/i });
        expect(prevButton).toBeDisabled();
      });
    });

    it('disables Next button on last page', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: mockDocuments,
        meta: { total: 100, page: 5, perPage: 20, totalPages: 5 },
      });

      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /next/i });
        expect(nextButton).toBeDisabled();
      });
    });

    it('navigates to next page when clicking Next', async () => {
      const user = userEvent.setup();

      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: mockDocuments,
        meta: { total: 100, page: 1, perPage: 20, totalPages: 5 },
      });

      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText(/page 1 of 5/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /next/i }));

      await waitFor(() => {
        expect(fetchDocuments).toHaveBeenLastCalledWith(
          matterId,
          expect.objectContaining({ page: 2 })
        );
      });
    });
  });

  describe('Document Click Handler', () => {
    it('calls onDocumentClick when row is clicked', async () => {
      const user = userEvent.setup();
      const onDocumentClick = vi.fn();

      render(<DocumentList matterId={matterId} onDocumentClick={onDocumentClick} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Click on the row (find by filename text and get parent row)
      const row = screen.getByText('petition.pdf').closest('tr');
      if (row) {
        await user.click(row);
      }

      expect(onDocumentClick).toHaveBeenCalledWith(mockDocuments[0]);
    });
  });

  describe('Bulk Operations', () => {
    it('shows bulk action dropdown when documents are selected', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Select a document
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[1]);

      // Should show "Change type" dropdown (it's the third combobox now after filters)
      const comboboxes = screen.getAllByRole('combobox');
      expect(comboboxes.length).toBe(3); // Type filter, Status filter, Change type
    });

    it('calls bulk update API when type is selected', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Select two documents
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[1]);
      await user.click(checkboxes[2]);

      // Open bulk action dropdown (third combobox)
      const comboboxes = screen.getAllByRole('combobox');
      const bulkDropdown = comboboxes[2]; // Third is the bulk action dropdown
      await user.click(bulkDropdown);

      // Select "Act"
      const actOption = screen.getByRole('option', { name: /^act$/i });
      await user.click(actOption);

      await waitFor(() => {
        expect(bulkUpdateDocuments).toHaveBeenCalledWith({
          documentIds: ['doc-1', 'doc-2'],
          documentType: 'act',
        });
      });

      // Should show success toast
      expect(toast.success).toHaveBeenCalledWith('Updated 2 documents');
    });

    it('clears selection after bulk update', async () => {
      const user = userEvent.setup();
      render(<DocumentList matterId={matterId} />);

      await waitFor(() => {
        expect(screen.getByText('petition.pdf')).toBeInTheDocument();
      });

      // Select all
      await user.click(screen.getAllByRole('checkbox')[0]);
      expect(screen.getByText('3 selected')).toBeInTheDocument();

      // Open bulk action dropdown (third combobox after filters)
      const comboboxes = screen.getAllByRole('combobox');
      const bulkDropdown = comboboxes[2];
      await user.click(bulkDropdown);
      await user.click(screen.getByRole('option', { name: /^act$/i }));

      // Selection should be cleared
      await waitFor(() => {
        expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
      });
    });
  });
});
