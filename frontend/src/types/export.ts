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

/**
 * Section edit state for inline editing in export preview.
 * Edits are stored client-side only and passed to export generation.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */
export interface ExportSectionEdit {
  /** Section being edited */
  sectionId: ExportSectionId;
  /** Modified text content (for text-based sections) */
  textContent?: string;
  /** IDs of removed items (for list sections like timeline, entities) */
  removedItemIds: string[];
  /** Added notes to append to section */
  addedNotes: string[];
}

/**
 * Preview mode for the export builder modal.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */
export type ExportPreviewMode = 'sections' | 'preview';

// =============================================================================
// Export Templates (Lawyer UX - Court-Ready Export)
// =============================================================================

/** Template ID for different export styles */
export type ExportTemplateId = 'standard' | 'court-filing' | 'internal-memo';

/** Export template configuration */
export interface ExportTemplate {
  /** Template identifier */
  id: ExportTemplateId;
  /** Display name */
  name: string;
  /** Description for template selection */
  description: string;
  /** Default sections to include */
  defaultSections: ExportSectionId[];
  /** Formatting options */
  formatting: {
    /** Use numbered paragraphs */
    numberedParagraphs: boolean;
    /** Include table of contents */
    tableOfContents: boolean;
    /** Use formal headers with case caption */
    formalHeaders: boolean;
    /** Label exhibits (Exhibit A, B, C...) */
    exhibitLabels: boolean;
    /** Include signature block */
    signatureBlock: boolean;
    /** Use bullet points (for informal memos) */
    bulletPoints: boolean;
    /** Include action items section */
    actionItems: boolean;
  };
  /** Recommended use case */
  useCase: string;
}

/** Available export templates */
export const EXPORT_TEMPLATES: ExportTemplate[] = [
  {
    id: 'standard',
    name: 'Standard Report',
    description: 'Balanced format suitable for most purposes',
    defaultSections: [
      'executive-summary',
      'timeline',
      'entities',
      'citations',
      'contradictions',
      'key-findings',
    ],
    formatting: {
      numberedParagraphs: false,
      tableOfContents: true,
      formalHeaders: false,
      exhibitLabels: false,
      signatureBlock: false,
      bulletPoints: true,
      actionItems: false,
    },
    useCase: 'Client reporting, case reviews, team sharing',
  },
  {
    id: 'court-filing',
    name: 'Court Filing',
    description: 'Formal format for court submissions',
    defaultSections: [
      'executive-summary',
      'timeline',
      'citations',
      'contradictions',
      'key-findings',
    ],
    formatting: {
      numberedParagraphs: true,
      tableOfContents: true,
      formalHeaders: true,
      exhibitLabels: true,
      signatureBlock: true,
      bulletPoints: false,
      actionItems: false,
    },
    useCase: 'Court submissions, formal pleadings, exhibits',
  },
  {
    id: 'internal-memo',
    name: 'Internal Memo',
    description: 'Quick summary for internal team use',
    defaultSections: [
      'executive-summary',
      'key-findings',
      'contradictions',
    ],
    formatting: {
      numberedParagraphs: false,
      tableOfContents: false,
      formalHeaders: false,
      exhibitLabels: false,
      signatureBlock: false,
      bulletPoints: true,
      actionItems: true,
    },
    useCase: 'Team updates, case strategy sessions, quick briefs',
  },
];

/** Get template by ID */
export function getExportTemplate(id: ExportTemplateId): ExportTemplate {
  return EXPORT_TEMPLATES.find((t) => t.id === id) ?? EXPORT_TEMPLATES[0];
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
