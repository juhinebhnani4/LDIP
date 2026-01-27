/**
 * Matter Types
 *
 * Types for the role-per-matter authorization system.
 * Matches backend Pydantic models in app/models/matter.py
 */

/** Role types for matter membership */
export type MatterRole = 'owner' | 'editor' | 'viewer';

/** Status types for matters */
export type MatterStatus = 'active' | 'archived' | 'closed';

/**
 * Verification mode for matter exports (Story 3.1)
 * - advisory: Default mode. Acknowledgment only - exports show warning but allow download.
 * - required: Court-ready mode. 100% verification required before export is allowed.
 */
export type VerificationMode = 'advisory' | 'required';

/**
 * Data residency region for API routing (Story 7.3)
 * - default: Auto-select based on firm settings
 * - us: US regional endpoints
 * - eu: EU regional endpoints (GDPR compliance)
 * - asia: Asia regional endpoints
 */
export type DataResidency = 'default' | 'us' | 'eu' | 'asia';

/** Data residency options for display */
export const DATA_RESIDENCY_OPTIONS: { value: DataResidency; label: string; description: string }[] = [
  { value: 'default', label: 'Auto', description: 'Automatically select based on firm settings' },
  { value: 'us', label: 'United States', description: 'Route API calls to US regional endpoints' },
  { value: 'eu', label: 'European Union', description: 'Route API calls to EU regional endpoints (GDPR)' },
  { value: 'asia', label: 'Asia Pacific', description: 'Route API calls to Asia regional endpoints' },
] as const;

/**
 * Analysis mode for document processing (Story 6.4)
 * - quick_scan: Faster processing, skips contradiction engine, larger chunks
 * - deep_analysis: Full processing with all engines (default)
 */
export type AnalysisMode = 'quick_scan' | 'deep_analysis';

/** Analysis mode options for display */
export const ANALYSIS_MODE_OPTIONS: { value: AnalysisMode; label: string; description: string }[] = [
  { value: 'deep_analysis', label: 'Deep Analysis', description: 'Full processing with all engines including contradictions' },
  { value: 'quick_scan', label: 'Quick Scan', description: 'Faster processing, skips contradiction detection' },
] as const;

/** A member of a matter with their role assignment */
export interface MatterMember {
  id: string;
  userId: string;
  email: string | null;
  fullName: string | null;
  role: MatterRole;
  invitedBy: string | null;
  invitedAt: string | null;
}

/** Base matter properties */
export interface MatterBase {
  title: string;
  description: string | null;
}

/** Request model for creating a new matter */
export interface MatterCreateRequest {
  title: string;
  description?: string;
  /** Practice group for cost reporting (Story 7.2) */
  practiceGroup?: string;
  /** Data residency region for API routing (Story 7.3) */
  dataResidency?: DataResidency;
  /** Analysis mode for document processing (Story 6.4) */
  analysisMode?: AnalysisMode;
}

/** Request model for updating an existing matter */
export interface MatterUpdateRequest {
  title?: string;
  description?: string | null;
  status?: MatterStatus;
  verificationMode?: VerificationMode;
  /** Practice group for cost reporting (Story 7.2) */
  practiceGroup?: string | null;
  /** Analysis mode for document processing (Story 6.4) */
  analysisMode?: AnalysisMode;
  // Note: dataResidency is NOT updateable after creation (immutable once documents uploaded)
}

/** Complete matter model returned from API */
export interface Matter extends MatterBase {
  id: string;
  status: MatterStatus;
  verificationMode: VerificationMode;
  /** Analysis mode for document processing (Story 6.4) */
  analysisMode: AnalysisMode;
  /** Practice group for cost reporting (Story 7.2) */
  practiceGroup: string | null;
  /** Data residency region for API routing (Story 7.3) */
  dataResidency: DataResidency;
  createdAt: string;
  updatedAt: string;
  deletedAt: string | null;
  role: MatterRole | null;
  memberCount: number;
}

/** Matter model including list of members */
export interface MatterWithMembers extends Matter {
  members: MatterMember[];
}

/** Request model for inviting a member to a matter */
export interface MatterInviteRequest {
  email: string;
  role: MatterRole;
}

/** Request model for updating a member's role */
export interface MatterMemberUpdateRequest {
  role: MatterRole;
}

/** Pagination metadata for matter list */
export interface MatterListMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/** API response wrapper for a single matter */
export interface MatterResponse {
  data: Matter;
}

/** API response wrapper for a matter with members */
export interface MatterWithMembersResponse {
  data: MatterWithMembers;
}

/** API response wrapper for matter list */
export interface MatterListResponse {
  data: Matter[];
  meta: MatterListMeta;
}

/** API response wrapper for member list */
export interface MemberListResponse {
  data: MatterMember[];
}

/** API response wrapper for a single member */
export interface MemberResponse {
  data: MatterMember;
}

/** API error response */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

/**
 * Check if a role has edit permissions (owner or editor).
 */
export function canEdit(role: MatterRole | null): boolean {
  return role === 'owner' || role === 'editor';
}

/**
 * Check if a role has owner permissions.
 */
export function isOwner(role: MatterRole | null): boolean {
  return role === 'owner';
}

/**
 * Check if user has any access to the matter.
 */
export function hasAccess(role: MatterRole | null): boolean {
  return role !== null;
}

// ============================================================================
// Story 9-2: Matter Cards Grid Types
// ============================================================================

/** Processing status types for matters (frontend display) */
export type MatterProcessingStatus = 'processing' | 'ready' | 'needs_attention';

/** Sort options for matter list */
export type MatterSortOption = 'recent' | 'alphabetical' | 'most_pages' | 'least_verified' | 'date_created';

/** Filter options for matter list */
export type MatterFilterOption = 'all' | 'processing' | 'ready' | 'needs_attention' | 'archived';

/** View mode for matter cards display */
export type MatterViewMode = 'grid' | 'list';

/**
 * Extended matter data for card display.
 * Extends base Matter with processing and dashboard-specific fields.
 * Note: Some fields are mocked on frontend until backend provides them.
 */
export interface MatterCardData extends Matter {
  /** Total pages across all documents in this matter */
  pageCount: number;
  /** Number of documents uploaded to this matter */
  documentCount: number;
  /** Percentage of findings that have been verified (0-100) */
  verificationPercent: number;
  /** Count of items flagged as needing attention */
  issueCount: number;
  /** Current processing status for display */
  processingStatus: MatterProcessingStatus;
  /** Processing progress percentage (0-100), only when status is 'processing' */
  processingProgress?: number;
  /** Estimated seconds remaining for processing, only when status is 'processing' */
  estimatedTimeRemaining?: number;
  /** ISO timestamp of when user last opened this matter */
  lastOpened?: string;
}

/** Constants for sort options */
export const SORT_OPTIONS: { value: MatterSortOption; label: string }[] = [
  { value: 'recent', label: 'Recent' },
  { value: 'alphabetical', label: 'Alphabetical' },
  { value: 'most_pages', label: 'Most pages' },
  { value: 'least_verified', label: 'Least verified' },
  { value: 'date_created', label: 'Date created' },
] as const;

/** Constants for filter options */
export const FILTER_OPTIONS: { value: MatterFilterOption; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'processing', label: 'Processing' },
  { value: 'ready', label: 'Ready' },
  { value: 'needs_attention', label: 'Needs attention' },
  { value: 'archived', label: 'Archived' },
] as const;

/** LocalStorage key for view preference */
export const VIEW_PREFERENCE_KEY = 'dashboard_view_preference' as const;
