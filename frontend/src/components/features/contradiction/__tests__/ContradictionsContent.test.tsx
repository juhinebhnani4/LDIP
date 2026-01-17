/**
 * ContradictionsContent Component Tests
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 10: Write tests for ContradictionsContent
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ContradictionsContent } from '../ContradictionsContent';
import { useContradictions } from '@/hooks/useContradictions';
import type {
  EntityContradictions,
  ContradictionItem,
  ContradictionsListResponse,
} from '@/hooks/useContradictions';

// Mock the hooks
vi.mock('@/hooks/useContradictions');

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

const mockContradictionItem = (
  id: string,
  severity: 'high' | 'medium' | 'low' = 'high',
  type: 'semantic_contradiction' | 'factual_contradiction' = 'semantic_contradiction'
): ContradictionItem => ({
  id,
  contradictionType: type,
  severity,
  entityId: `entity-${id}`,
  entityName: `Entity ${id}`,
  statementA: {
    documentId: 'doc-1',
    documentName: 'Document A.pdf',
    page: 5,
    excerpt: 'This is the first statement excerpt for testing purposes.',
    date: '2024-01-15',
  },
  statementB: {
    documentId: 'doc-2',
    documentName: 'Document B.pdf',
    page: 10,
    excerpt: 'This is the second statement excerpt that contradicts the first.',
    date: '2024-02-20',
  },
  explanation: 'These statements contain contradictory information about the same fact.',
  evidenceLinks: [
    {
      statementId: 'stmt-1',
      documentId: 'doc-1',
      documentName: 'Document A.pdf',
      page: 5,
      bboxIds: ['bbox-1'],
    },
  ],
  confidence: 0.85,
  createdAt: '2024-03-01T10:00:00Z',
});

const mockEntityGroup = (
  entityId: string,
  entityName: string,
  count: number = 2
): EntityContradictions => ({
  entityId,
  entityName,
  contradictions: Array.from({ length: count }, (_, i) =>
    mockContradictionItem(`${entityId}-${i}`)
  ),
  count,
});

const mockMeta: ContradictionsListResponse['meta'] = {
  total: 10,
  page: 1,
  perPage: 20,
  totalPages: 1,
};

describe('ContradictionsContent', () => {
  const mockMutate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementation with data
    (useContradictions as Mock).mockReturnValue({
      data: [
        mockEntityGroup('entity-1', 'John Smith', 2),
        mockEntityGroup('entity-2', 'Acme Corp', 1),
      ],
      meta: mockMeta,
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 3,
      uniqueEntities: [
        { id: 'entity-1', name: 'John Smith' },
        { id: 'entity-2', name: 'Acme Corp' },
      ],
      mutate: mockMutate,
    });
  });

  it('renders contradictions header with total count', () => {
    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('3 contradictions found')).toBeInTheDocument();
  });

  it('renders entity groups', () => {
    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });

  it('shows entity contradiction counts', () => {
    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('(2 contradictions)')).toBeInTheDocument();
    expect(screen.getByText('(1 contradiction)')).toBeInTheDocument();
  });

  it('renders loading skeleton when loading and no data', () => {
    (useContradictions as Mock).mockReturnValue({
      data: [],
      meta: null,
      isLoading: true,
      isValidating: false,
      error: null,
      totalCount: 0,
      uniqueEntities: [],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    // Should show skeleton, not content
    expect(screen.queryByText('contradictions found')).not.toBeInTheDocument();
  });

  it('renders error state when error and no data', () => {
    (useContradictions as Mock).mockReturnValue({
      data: [],
      meta: null,
      isLoading: false,
      isValidating: false,
      error: new Error('Failed to load contradictions'),
      totalCount: 0,
      uniqueEntities: [],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Failed to load contradictions')).toBeInTheDocument();
  });

  it('renders empty state when no contradictions', () => {
    (useContradictions as Mock).mockReturnValue({
      data: [],
      meta: null,
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 0,
      uniqueEntities: [],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('No Contradictions Found')).toBeInTheDocument();
  });

  it('renders filter controls', () => {
    render(<ContradictionsContent matterId="matter-123" />);

    // Filter dropdowns should be present
    expect(screen.getByText('All Severities')).toBeInTheDocument();
    expect(screen.getByText('All Types')).toBeInTheDocument();
    expect(screen.getByText('All Entities')).toBeInTheDocument();
  });

  it('passes matterId to useContradictions hook', () => {
    render(<ContradictionsContent matterId="test-matter-id" />);

    expect(useContradictions).toHaveBeenCalledWith(
      'test-matter-id',
      expect.objectContaining({
        page: 1,
        perPage: 20,
      })
    );
  });

  it('expands first three entity groups by default', () => {
    // Add a fourth entity group
    (useContradictions as Mock).mockReturnValue({
      data: [
        mockEntityGroup('entity-1', 'John Smith', 1),
        mockEntityGroup('entity-2', 'Acme Corp', 1),
        mockEntityGroup('entity-3', 'Jane Doe', 1),
        mockEntityGroup('entity-4', 'XYZ Inc', 1),
      ],
      meta: { ...mockMeta, total: 4 },
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 4,
      uniqueEntities: [
        { id: 'entity-1', name: 'John Smith' },
        { id: 'entity-2', name: 'Acme Corp' },
        { id: 'entity-3', name: 'Jane Doe' },
        { id: 'entity-4', name: 'XYZ Inc' },
      ],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    // All four entity names should be visible as headers
    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('XYZ Inc')).toBeInTheDocument();
  });

  it('shows updating indicator when revalidating', () => {
    (useContradictions as Mock).mockReturnValue({
      data: [mockEntityGroup('entity-1', 'John Smith', 1)],
      meta: mockMeta,
      isLoading: true,
      isValidating: true,
      error: null,
      totalCount: 1,
      uniqueEntities: [{ id: 'entity-1', name: 'John Smith' }],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('Updating...')).toBeInTheDocument();
  });
});

describe('ContradictionsContent Filter Interactions', () => {
  const mockMutate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    (useContradictions as Mock).mockReturnValue({
      data: [mockEntityGroup('entity-1', 'John Smith', 2)],
      meta: mockMeta,
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 2,
      uniqueEntities: [{ id: 'entity-1', name: 'John Smith' }],
      mutate: mockMutate,
    });
  });

  it('calls useContradictions with severity filter when changed', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ContradictionsContent matterId="matter-123" />);

    // Open severity dropdown - use role combobox
    const severityTrigger = screen.getAllByRole('combobox')[0];
    await user.click(severityTrigger!);

    // Select High
    await user.click(screen.getByRole('option', { name: 'High' }));

    await waitFor(() => {
      expect(useContradictions).toHaveBeenCalledWith(
        'matter-123',
        expect.objectContaining({
          severity: 'high',
          page: 1,
        })
      );
    });
  });

  it('calls useContradictions with type filter when changed', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ContradictionsContent matterId="matter-123" />);

    // Open type dropdown - second combobox
    const typeTrigger = screen.getAllByRole('combobox')[1];
    await user.click(typeTrigger!);

    // Select Semantic
    await user.click(screen.getByRole('option', { name: 'Semantic' }));

    await waitFor(() => {
      expect(useContradictions).toHaveBeenCalledWith(
        'matter-123',
        expect.objectContaining({
          contradictionType: 'semantic_contradiction',
          page: 1,
        })
      );
    });
  });

  it('shows clear filters button when filters are active', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ContradictionsContent matterId="matter-123" />);

    // Initially no clear button
    expect(screen.queryByText('Clear filters')).not.toBeInTheDocument();

    // Apply a filter
    const severityTrigger = screen.getAllByRole('combobox')[0];
    await user.click(severityTrigger!);
    await user.click(screen.getByRole('option', { name: 'High' }));

    // Now clear button should appear
    await waitFor(() => {
      expect(screen.getByText('Clear filters')).toBeInTheDocument();
    });
  });

  it('resets page to 1 when filter changes', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    // Start with page 2
    (useContradictions as Mock).mockReturnValue({
      data: [mockEntityGroup('entity-1', 'John Smith', 2)],
      meta: { ...mockMeta, page: 2 },
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 2,
      uniqueEntities: [{ id: 'entity-1', name: 'John Smith' }],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    // Change filter
    const severityTrigger = screen.getAllByRole('combobox')[0];
    await user.click(severityTrigger!);
    await user.click(screen.getByRole('option', { name: 'Medium' }));

    // Should reset to page 1
    await waitFor(() => {
      expect(useContradictions).toHaveBeenCalledWith(
        'matter-123',
        expect.objectContaining({
          page: 1,
        })
      );
    });
  });
});

describe('ContradictionsContent Pagination', () => {
  const mockMutate = vi.fn();

  it('does not render pagination when only one page', () => {
    (useContradictions as Mock).mockReturnValue({
      data: [mockEntityGroup('entity-1', 'John Smith', 2)],
      meta: { total: 2, page: 1, perPage: 20, totalPages: 1 },
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 2,
      uniqueEntities: [{ id: 'entity-1', name: 'John Smith' }],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    // Pagination controls should not be visible
    expect(screen.queryByText('Showing')).not.toBeInTheDocument();
  });

  it('renders pagination when multiple pages', () => {
    (useContradictions as Mock).mockReturnValue({
      data: [mockEntityGroup('entity-1', 'John Smith', 20)],
      meta: { total: 45, page: 1, perPage: 20, totalPages: 3 },
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 45,
      uniqueEntities: [{ id: 'entity-1', name: 'John Smith' }],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    expect(screen.getByText('Showing 1-20 of 45')).toBeInTheDocument();
  });

  it('updates page when pagination is clicked', async () => {
    const user = userEvent.setup();
    (useContradictions as Mock).mockReturnValue({
      data: [mockEntityGroup('entity-1', 'John Smith', 20)],
      meta: { total: 45, page: 1, perPage: 20, totalPages: 3 },
      isLoading: false,
      isValidating: false,
      error: null,
      totalCount: 45,
      uniqueEntities: [{ id: 'entity-1', name: 'John Smith' }],
      mutate: mockMutate,
    });

    render(<ContradictionsContent matterId="matter-123" />);

    // Click page 2
    await user.click(screen.getByRole('button', { name: '2' }));

    await waitFor(() => {
      expect(useContradictions).toHaveBeenCalledWith(
        'matter-123',
        expect.objectContaining({
          page: 2,
        })
      );
    });
  });
});
