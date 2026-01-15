/**
 * useCitations Hook Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  useCitationsList,
  useCitationStats,
  useCitationSummaryByAct,
  useActDiscoveryReport,
  useActMutations,
  useCitationIssueStats,
  getActNamesFromSummary,
} from './useCitations';
import * as citationsApi from '@/lib/api/citations';
import type {
  CitationListItem,
  CitationStats,
  CitationSummaryItem,
  ActDiscoverySummary,
} from '@/types';

// Mock the API module
vi.mock('@/lib/api/citations');

// Mock data
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
    verificationStatus: 'act_unavailable',
    confidence: 90.0,
    documentId: 'doc-2',
    documentName: 'Reply.pdf',
  },
];

const mockStats: CitationStats = {
  totalCitations: 23,
  uniqueActs: 6,
  verifiedCount: 18,
  pendingCount: 2,
  missingActsCount: 2,
};

const mockSummary: CitationSummaryItem[] = [
  { actName: 'Securities Act, 1992', citationCount: 12, verifiedCount: 10, pendingCount: 2 },
  { actName: 'Negotiable Instruments Act, 1881', citationCount: 8, verifiedCount: 6, pendingCount: 0 },
  { actName: 'Companies Act, 2013', citationCount: 3, verifiedCount: 2, pendingCount: 1 },
];

const mockActDiscovery: ActDiscoverySummary[] = [
  {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 12,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-123',
  },
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
    citationCount: 3,
    resolutionStatus: 'skipped',
    userAction: 'skipped',
    actDocumentId: null,
  },
];

describe('useCitationsList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch citations with default options', async () => {
    vi.mocked(citationsApi.getCitations).mockResolvedValue({
      data: mockCitations,
      meta: { total: 3, page: 1, perPage: 20, totalPages: 1 },
    });

    const { result } = renderHook(() => useCitationsList('matter-123'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.citations).toHaveLength(3);
    expect(result.current.meta?.total).toBe(3);
    expect(citationsApi.getCitations).toHaveBeenCalledWith('matter-123', {
      page: 1,
      perPage: 20,
    });
  });

  it('should filter citations by verification status', async () => {
    const firstCitation = mockCitations[0];
    vi.mocked(citationsApi.getCitations).mockResolvedValue({
      data: firstCitation ? [firstCitation] : [],
      meta: { total: 1, page: 1, perPage: 20, totalPages: 1 },
    });

    const { result } = renderHook(() =>
      useCitationsList('matter-123', {
        filters: {
          verificationStatus: 'verified',
          actName: null,
          showOnlyIssues: false,
        },
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(citationsApi.getCitations).toHaveBeenCalledWith('matter-123', {
      page: 1,
      perPage: 20,
      verificationStatus: 'verified',
    });
  });

  it('should filter citations by Act name', async () => {
    const firstCitation = mockCitations[0];
    vi.mocked(citationsApi.getCitations).mockResolvedValue({
      data: firstCitation ? [firstCitation] : [],
      meta: { total: 1, page: 1, perPage: 20, totalPages: 1 },
    });

    const { result } = renderHook(() =>
      useCitationsList('matter-123', {
        filters: {
          verificationStatus: null,
          actName: 'Securities Act, 1992',
          showOnlyIssues: false,
        },
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(citationsApi.getCitations).toHaveBeenCalledWith('matter-123', {
      page: 1,
      perPage: 20,
      actName: 'Securities Act, 1992',
    });
  });

  it('should apply showOnlyIssues filter client-side', async () => {
    vi.mocked(citationsApi.getCitations).mockResolvedValue({
      data: mockCitations,
      meta: { total: 3, page: 1, perPage: 20, totalPages: 1 },
    });

    const { result } = renderHook(() =>
      useCitationsList('matter-123', {
        filters: {
          verificationStatus: null,
          actName: null,
          showOnlyIssues: true,
        },
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should filter to only mismatch and section_not_found (not act_unavailable - that's just awaiting upload)
    expect(result.current.citations).toHaveLength(1);
    expect(result.current.citations.every((c) =>
      ['mismatch', 'section_not_found'].includes(c.verificationStatus)
    )).toBe(true);
    // Verify metadata is updated for client-side filtering
    expect(result.current.meta?.total).toBe(1);
  });

  it('should handle pagination', async () => {
    vi.mocked(citationsApi.getCitations).mockResolvedValue({
      data: mockCitations.slice(0, 2),
      meta: { total: 3, page: 2, perPage: 2, totalPages: 2 },
    });

    const { result } = renderHook(() =>
      useCitationsList('matter-123', { page: 2, perPage: 2 })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(citationsApi.getCitations).toHaveBeenCalledWith('matter-123', {
      page: 2,
      perPage: 2,
    });
  });

  it('should return empty array when matterId is empty', async () => {
    const { result } = renderHook(() => useCitationsList(''));

    // Should not make API call
    expect(citationsApi.getCitations).not.toHaveBeenCalled();
    expect(result.current.citations).toEqual([]);
  });
});

describe('useCitationStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch citation statistics', async () => {
    vi.mocked(citationsApi.getCitationStats).mockResolvedValue(mockStats);

    const { result } = renderHook(() => useCitationStats('matter-123'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.stats).toEqual(mockStats);
    expect(result.current.stats?.totalCitations).toBe(23);
  });

  it('should return null stats when matterId is empty', async () => {
    const { result } = renderHook(() => useCitationStats(''));

    expect(citationsApi.getCitationStats).not.toHaveBeenCalled();
    expect(result.current.stats).toBeNull();
  });
});

describe('useCitationSummaryByAct', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch citation summary grouped by Act', async () => {
    vi.mocked(citationsApi.getCitationSummary).mockResolvedValue({
      data: mockSummary,
    });

    const { result } = renderHook(() => useCitationSummaryByAct('matter-123'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.summary).toHaveLength(3);
    const firstSummary = result.current.summary[0];
    expect(firstSummary?.actName).toBe('Securities Act, 1992');
  });
});

describe('useActDiscoveryReport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch Act discovery report', async () => {
    vi.mocked(citationsApi.getActDiscoveryReport).mockResolvedValue({
      data: mockActDiscovery,
    });

    const { result } = renderHook(() => useActDiscoveryReport('matter-123'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.acts).toHaveLength(3);
    expect(result.current.missingCount).toBe(1);
    expect(result.current.availableCount).toBe(1);
    expect(result.current.skippedCount).toBe(1);
  });

  it('should count missing acts correctly', async () => {
    const missingActTemplate = mockActDiscovery[1];
    const manyMissingActs: ActDiscoverySummary[] = missingActTemplate
      ? [
          { ...missingActTemplate, actName: 'Act 1' },
          { ...missingActTemplate, actName: 'Act 2' },
          { ...missingActTemplate, actName: 'Act 3' },
        ]
      : [];

    vi.mocked(citationsApi.getActDiscoveryReport).mockResolvedValue({
      data: manyMissingActs,
    });

    // Use different matter ID to avoid SWR cache
    const { result } = renderHook(() => useActDiscoveryReport('matter-456'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.missingCount).toBe(3);
    expect(result.current.availableCount).toBe(0);
    expect(result.current.skippedCount).toBe(0);
  });
});

describe('useActMutations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should call markActUploaded API', async () => {
    vi.mocked(citationsApi.markActUploaded).mockResolvedValue({
      success: true,
      actName: 'Test Act',
      resolutionStatus: 'available',
    });

    const { result } = renderHook(() => useActMutations('matter-123'));

    await act(async () => {
      await result.current.markUploaded({
        actName: 'Test Act',
        actDocumentId: 'doc-1',
      });
    });

    expect(citationsApi.markActUploaded).toHaveBeenCalledWith('matter-123', {
      actName: 'Test Act',
      actDocumentId: 'doc-1',
    });
  });

  it('should call markActSkipped API', async () => {
    vi.mocked(citationsApi.markActSkipped).mockResolvedValue({
      success: true,
      actName: 'Test Act',
      resolutionStatus: 'skipped',
    });

    const { result } = renderHook(() => useActMutations('matter-123'));

    await act(async () => {
      await result.current.markSkipped({ actName: 'Test Act' });
    });

    expect(citationsApi.markActSkipped).toHaveBeenCalledWith('matter-123', {
      actName: 'Test Act',
    });
  });

  it('should call markActUploadedAndVerify API', async () => {
    vi.mocked(citationsApi.markActUploadedAndVerify).mockResolvedValue({
      success: true,
      actName: 'Test Act',
      resolutionStatus: 'available',
    });

    const { result } = renderHook(() => useActMutations('matter-123'));

    await act(async () => {
      await result.current.markUploadedAndVerify({
        actName: 'Test Act',
        actDocumentId: 'doc-1',
      });
    });

    expect(citationsApi.markActUploadedAndVerify).toHaveBeenCalledWith(
      'matter-123',
      {
        actName: 'Test Act',
        actDocumentId: 'doc-1',
      }
    );
  });
});

describe('useCitationIssueStats', () => {
  it('should compute issue statistics from stats', () => {
    const result = useCitationIssueStats(mockStats);

    // total 23 - verified 18 - pending 2 = 3 issues
    expect(result.totalIssues).toBe(3);
    expect(result.actUnavailableCount).toBe(2);
  });

  it('should return zeros when stats is null', () => {
    const result = useCitationIssueStats(null);

    expect(result.totalIssues).toBe(0);
    expect(result.mismatchCount).toBe(0);
    expect(result.notFoundCount).toBe(0);
    expect(result.actUnavailableCount).toBe(0);
  });

  it('should handle edge case where issue count would be negative', () => {
    const statsWithHighVerified: CitationStats = {
      totalCitations: 10,
      uniqueActs: 5,
      verifiedCount: 8,
      pendingCount: 5, // 8 + 5 = 13 > 10, so would result in negative
      missingActsCount: 0,
    };

    const result = useCitationIssueStats(statsWithHighVerified);

    expect(result.totalIssues).toBe(0); // Should be 0, not negative
  });
});

describe('getActNamesFromSummary', () => {
  it('should extract and sort Act names from summary', () => {
    const result = getActNamesFromSummary(mockSummary);

    expect(result).toEqual([
      'Companies Act, 2013',
      'Negotiable Instruments Act, 1881',
      'Securities Act, 1992',
    ]);
  });

  it('should return empty array for empty summary', () => {
    const result = getActNamesFromSummary([]);
    expect(result).toEqual([]);
  });
});
