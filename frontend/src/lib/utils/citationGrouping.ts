/**
 * Citation Grouping Utilities
 *
 * Groups identical citations (same Act + Section) for cleaner display.
 * Preserves all individual citations for audit trail while showing
 * collapsed view to reduce visual noise.
 *
 * @see Story 10C.3 - Citations Tab UX Improvements
 */

import type {
  CitationListItem,
  GroupedCitation,
  VerificationStatus,
} from '@/types/citation';

/**
 * Generate a unique group key for a citation.
 * Citations with the same key are considered duplicates.
 */
export function getCitationGroupKey(citation: CitationListItem): string {
  const parts = [
    citation.actName.toLowerCase().trim(),
    citation.sectionNumber.toLowerCase().trim(),
    citation.subsection?.toLowerCase().trim() ?? '',
    citation.clause?.toLowerCase().trim() ?? '',
  ];
  return parts.join('|');
}

/**
 * Status priority for determining aggregate status.
 * Lower number = higher priority (shown first).
 */
const STATUS_PRIORITY: Record<VerificationStatus, number> = {
  mismatch: 1, // Issues first
  section_not_found: 2,
  act_unavailable: 3,
  pending: 4,
  verified: 5, // Verified last (best case)
};

/**
 * Get the worst (highest priority) status from a list of statuses.
 */
function getWorstStatus(statuses: VerificationStatus[]): VerificationStatus {
  return statuses.reduce((worst, current) => {
    return STATUS_PRIORITY[current] < STATUS_PRIORITY[worst] ? current : worst;
  }, 'verified' as VerificationStatus);
}

/**
 * Group citations by their grouping key.
 *
 * @param citations - Array of citations to group
 * @returns Array of grouped citations, sorted by count (descending)
 */
export function groupCitations(citations: CitationListItem[]): GroupedCitation[] {
  const groups = new Map<string, CitationListItem[]>();

  // Group by key
  for (const citation of citations) {
    const key = getCitationGroupKey(citation);
    const existing = groups.get(key) ?? [];
    existing.push(citation);
    groups.set(key, existing);
  }

  // Convert to GroupedCitation objects
  const grouped: GroupedCitation[] = [];

  for (const [groupKey, citationsInGroup] of groups) {
    // Sort citations within group by document name, then page
    const sorted = [...citationsInGroup].sort((a, b) => {
      const nameCompare = (a.documentName ?? '').localeCompare(b.documentName ?? '');
      if (nameCompare !== 0) return nameCompare;
      return a.sourcePage - b.sourcePage;
    });

    const representative = sorted[0];
    if (!representative) continue; // Skip empty groups
    const documentIds = [...new Set(sorted.map((c) => c.documentId))];
    const documentNames = [...new Set(sorted.map((c) => c.documentName).filter(Boolean))] as string[];
    const statuses = sorted.map((c) => c.verificationStatus);
    const avgConfidence = sorted.reduce((sum, c) => sum + c.confidence, 0) / sorted.length;

    grouped.push({
      groupKey,
      representative,
      citations: sorted,
      count: sorted.length,
      documentIds,
      documentNames,
      aggregateStatus: getWorstStatus(statuses),
      averageConfidence: avgConfidence,
    });
  }

  // Sort by count descending (most duplicates first), then by act name
  grouped.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return a.representative.actName.localeCompare(b.representative.actName);
  });

  return grouped;
}

/**
 * Filter grouped citations by search query.
 * Searches act name, section number, and raw citation text.
 */
export function filterGroupedCitations(
  groups: GroupedCitation[],
  searchQuery: string
): GroupedCitation[] {
  if (!searchQuery.trim()) return groups;

  const query = searchQuery.toLowerCase().trim();

  return groups.filter((group) => {
    const rep = group.representative;
    // Match on act name
    if (rep.actName.toLowerCase().includes(query)) return true;
    // Match on section number
    if (rep.sectionNumber.toLowerCase().includes(query)) return true;
    // Match on any citation text in the group
    return group.citations.some((c) =>
      c.rawCitationText?.toLowerCase().includes(query)
    );
  });
}

/**
 * Get all citation IDs from a grouped citation.
 * Useful for bulk operations.
 */
export function getGroupCitationIds(group: GroupedCitation): string[] {
  return group.citations.map((c) => c.id);
}

/**
 * Check if a group has any issues (mismatch or section_not_found).
 */
export function groupHasIssues(group: GroupedCitation): boolean {
  return ['mismatch', 'section_not_found'].includes(group.aggregateStatus);
}

/**
 * Get a summary string for the documents in a group.
 */
export function getGroupDocumentSummary(group: GroupedCitation): string {
  if (group.documentNames.length === 0) {
    return `${group.count} occurrence${group.count > 1 ? 's' : ''}`;
  }
  if (group.documentNames.length === 1) {
    return group.documentNames[0] ?? `${group.count} occurrence${group.count > 1 ? 's' : ''}`;
  }
  return `${group.documentNames.length} documents`;
}
