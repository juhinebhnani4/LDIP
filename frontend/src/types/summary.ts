/**
 * Summary Tab Type Definitions
 *
 * Types for the Matter Summary tab data structure.
 *
 * Story 10B.1: Summary Tab Content
 */

/**
 * Type of attention item requiring user action
 */
export type AttentionItemType = 'contradiction' | 'citation_issue' | 'timeline_gap';

/**
 * Attention item - issues needing user action
 */
export interface AttentionItem {
  /** Type of attention item */
  type: AttentionItemType;
  /** Number of items of this type */
  count: number;
  /** Human-readable label */
  label: string;
  /** Tab to navigate to for resolution */
  targetTab: string;
}

/**
 * Party role in the matter
 */
export type PartyRole = 'petitioner' | 'respondent' | 'other';

/**
 * Party information - key parties in the matter
 */
export interface PartyInfo {
  /** Unique entity ID */
  entityId: string;
  /** Display name of the entity */
  entityName: string;
  /** Role in the matter */
  role: PartyRole;
  /** Source document name */
  sourceDocument: string;
  /** Source page number */
  sourcePage: number;
  /** Whether the party has been verified */
  isVerified: boolean;
}

/**
 * Subject matter source reference
 */
export interface SubjectMatterSource {
  /** Document name */
  documentName: string;
  /** Page range (e.g., "1-3") */
  pageRange: string;
}

/**
 * Subject matter - what the case is about
 */
export interface SubjectMatter {
  /** AI-generated description */
  description: string;
  /** Source citations */
  sources: SubjectMatterSource[];
  /** Whether subject matter has been verified */
  isVerified: boolean;
}

/**
 * Current status - latest order and proceedings
 */
export interface CurrentStatus {
  /** Date of last order (ISO format) */
  lastOrderDate: string;
  /** Description of last order */
  description: string;
  /** Source document name */
  sourceDocument: string;
  /** Source page number */
  sourcePage: number;
  /** Whether status has been verified */
  isVerified: boolean;
}

/**
 * Key issue verification status
 */
export type KeyIssueVerificationStatus = 'verified' | 'pending' | 'flagged';

/**
 * Key issue in the matter
 */
export interface KeyIssue {
  /** Unique ID */
  id: string;
  /** Issue number for display */
  number: number;
  /** Issue title/description */
  title: string;
  /** Verification status */
  verificationStatus: KeyIssueVerificationStatus;
}

/**
 * Matter statistics
 */
export interface MatterStats {
  /** Total pages across all documents */
  totalPages: number;
  /** Number of entities extracted */
  entitiesFound: number;
  /** Number of events extracted */
  eventsExtracted: number;
  /** Number of citations found */
  citationsFound: number;
  /** Verification completion percentage (0-100) */
  verificationPercent: number;
}

/**
 * Complete matter summary data
 */
export interface MatterSummary {
  /** Matter ID */
  matterId: string;
  /** Items requiring attention */
  attentionItems: AttentionItem[];
  /** Key parties in the matter */
  parties: PartyInfo[];
  /** Subject matter description */
  subjectMatter: SubjectMatter;
  /** Current status of proceedings */
  currentStatus: CurrentStatus;
  /** Key issues identified */
  keyIssues: KeyIssue[];
  /** Matter statistics */
  stats: MatterStats;
  /** When summary was generated (ISO timestamp) */
  generatedAt: string;
}

/**
 * API response wrapper for matter summary
 */
export interface MatterSummaryResponse {
  /** Summary data */
  data: MatterSummary;
}
