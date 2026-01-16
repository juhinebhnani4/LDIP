/**
 * Export Builder Type Definitions
 *
 * Types for the Export Builder modal component.
 *
 * @see Story 12.1 - Export Builder Modal with Section Selection
 */

/** Export format options */
export type ExportFormat = 'pdf' | 'word' | 'powerpoint';

/** Section IDs for export builder */
export type ExportSectionId =
  | 'executive-summary'
  | 'timeline'
  | 'entities'
  | 'citations'
  | 'contradictions'
  | 'key-findings';

/** Export section configuration */
export interface ExportSection {
  /** Unique identifier for the section */
  id: ExportSectionId;
  /** Display label for the section */
  label: string;
  /** Description of section contents */
  description: string;
  /** Whether section is included in export */
  enabled: boolean;
  /** Content preview count (e.g., "5 events") */
  count?: number;
  /** Loading state for count */
  isLoadingCount?: boolean;
}

/** Export builder state */
export interface ExportBuilderState {
  /** Ordered list of sections */
  sections: ExportSection[];
  /** Selected export format */
  format: ExportFormat;
}

/** Default export sections configuration */
export const DEFAULT_EXPORT_SECTIONS: Omit<ExportSection, 'count' | 'isLoadingCount'>[] = [
  {
    id: 'executive-summary',
    label: 'Executive Summary',
    description: 'Case overview and key parties',
    enabled: true,
  },
  {
    id: 'timeline',
    label: 'Timeline',
    description: 'Chronological events',
    enabled: true,
  },
  {
    id: 'entities',
    label: 'Entities',
    description: 'Parties and organizations',
    enabled: true,
  },
  {
    id: 'citations',
    label: 'Citations',
    description: 'Act references and verifications',
    enabled: true,
  },
  {
    id: 'contradictions',
    label: 'Contradictions',
    description: 'Conflicting statements',
    enabled: true,
  },
  {
    id: 'key-findings',
    label: 'Key Findings',
    description: 'Verified findings and issues',
    enabled: true,
  },
];
