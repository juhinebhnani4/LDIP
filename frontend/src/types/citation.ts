/**
 * Citation Types for Act Citation Extraction and Verification
 *
 * Types for citations extracted from legal documents and verification results.
 * Matches backend Pydantic models in app/models/citation.py
 *
 * Story 3-1: Act Citation Extraction
 * Story 3-3: Citation Verification
 */

/** Verification status for citations */
export type VerificationStatus =
  | 'pending'
  | 'verified'
  | 'mismatch'
  | 'section_not_found'
  | 'act_unavailable';

/** Act resolution status */
export type ActResolutionStatus = 'available' | 'missing' | 'skipped';

/** User action on Act resolution */
export type UserAction = 'uploaded' | 'skipped' | 'pending';

// =============================================================================
// Citation Types
// =============================================================================

/** Base citation properties */
export interface CitationBase {
  actName: string;
  sectionNumber: string;
  subsection: string | null;
  clause: string | null;
}

/** Citation list item (summary view) */
export interface CitationListItem extends CitationBase {
  id: string;
  rawCitationText: string | null;
  sourcePage: number;
  verificationStatus: VerificationStatus;
  confidence: number;
  documentId: string;
  documentName: string | null;
}

/** Complete citation model from API */
export interface Citation extends CitationBase {
  id: string;
  matterId: string;
  documentId: string;
  sourcePage: number;
  sourceBboxIds: string[];
  actNameOriginal: string | null;
  rawCitationText: string | null;
  quotedText: string | null;
  verificationStatus: VerificationStatus;
  targetActDocumentId: string | null;
  targetPage: number | null;
  targetBboxIds: string[];
  confidence: number;
  extractionMetadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  documentName?: string;
}

// =============================================================================
// Act Resolution Types
// =============================================================================

/** Act resolution record */
export interface ActResolution {
  id: string;
  matterId: string;
  actNameNormalized: string;
  actNameDisplay: string | null;
  actDocumentId: string | null;
  resolutionStatus: ActResolutionStatus;
  userAction: UserAction;
  citationCount: number;
  firstSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

// =============================================================================
// Act Discovery Types
// =============================================================================

/** Summary of an Act for the Act Discovery Report */
export interface ActDiscoverySummary {
  actName: string;
  actNameNormalized: string;
  citationCount: number;
  resolutionStatus: ActResolutionStatus;
  userAction: UserAction;
  actDocumentId: string | null;
}

// =============================================================================
// API Response Types
// =============================================================================

/** Pagination metadata */
export interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number | null;
}

/** Paginated citations response */
export interface CitationsListResponse {
  data: CitationListItem[];
  meta: PaginationMeta;
}

/** Single citation response */
export interface CitationResponse {
  data: Citation;
}

/** Citation count summary by Act */
export interface CitationSummaryItem {
  actName: string;
  citationCount: number;
  verifiedCount: number;
  pendingCount: number;
}

/** Citation summary response */
export interface CitationSummaryResponse {
  data: CitationSummaryItem[];
}

/** Act Discovery Report response */
export interface ActDiscoveryResponse {
  data: ActDiscoverySummary[];
}

/** Act resolution update response */
export interface ActResolutionResponse {
  success: boolean;
  actName: string;
  resolutionStatus: ActResolutionStatus;
}

/** Citation statistics */
export interface CitationStats {
  totalCitations: number;
  uniqueActs: number;
  verifiedCount: number;
  pendingCount: number;
  missingActsCount: number;
}

// =============================================================================
// Request Types
// =============================================================================

/** Request to mark an Act as uploaded */
export interface MarkActUploadedRequest {
  actName: string;
  actDocumentId: string;
}

/** Request to mark an Act as skipped */
export interface MarkActSkippedRequest {
  actName: string;
}

/** Query options for listing citations */
export interface CitationListOptions {
  actName?: string;
  verificationStatus?: VerificationStatus;
  documentId?: string;
  page?: number;
  perPage?: number;
}

// =============================================================================
// Verification Types (Story 3-3)
// =============================================================================

/** Match type for text comparison */
export type MatchType = 'exact' | 'paraphrase' | 'mismatch';

/** Diff details for mismatched citations */
export interface DiffDetail {
  citationText: string;
  actText: string;
  matchType: MatchType;
  differences: string[];
}

/** Section match result */
export interface SectionMatch {
  sectionNumber: string;
  sectionText: string;
  chunkId: string;
  pageNumber: number;
  bboxIds: string[];
  confidence: number;
}

/** Quote comparison result */
export interface QuoteComparison {
  similarityScore: number;
  matchType: MatchType;
  explanation: string;
}

/** Verification result for a citation */
export interface VerificationResult {
  status: VerificationStatus;
  sectionFound: boolean;
  sectionText: string | null;
  targetPage: number | null;
  targetBboxIds: string[];
  similarityScore: number;
  explanation: string;
  diffDetails: DiffDetail | null;
}

/** Verification result response */
export interface VerificationResultResponse {
  data: VerificationResult;
}

/** Batch verification response */
export interface BatchVerificationResponse {
  taskId: string;
  status: string;
  totalCitations: number;
  actName: string;
}

/** Request to verify citations for an Act */
export interface VerifyActRequest {
  actName: string;
  actDocumentId: string;
}

/** Request to verify a single citation */
export interface VerifyCitationRequest {
  actDocumentId: string;
  actName: string;
}

// =============================================================================
// Real-Time Verification Events (Story 3-3)
// =============================================================================

/** Verification progress event from WebSocket */
export interface VerificationProgressEvent {
  event: 'verification_progress';
  matterId: string;
  actName: string;
  verifiedCount: number;
  totalCount: number;
  progressPct: number;
  taskId?: string;
}

/** Single citation verified event */
export interface CitationVerifiedEvent {
  event: 'citation_verified';
  matterId: string;
  citationId: string;
  status: VerificationStatus;
  explanation: string;
  similarityScore?: number;
}

/** Verification complete event */
export interface VerificationCompleteEvent {
  event: 'verification_complete';
  matterId: string;
  actName: string;
  totalVerified: number;
  verifiedCount: number;
  mismatchCount: number;
  notFoundCount: number;
  taskId?: string;
}

/** Union type for all verification events */
export type VerificationEvent =
  | VerificationProgressEvent
  | CitationVerifiedEvent
  | VerificationCompleteEvent;

// =============================================================================
// Error Types
// =============================================================================

/** Citation error detail */
export interface CitationErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

/** Citation error response */
export interface CitationErrorResponse {
  error: CitationErrorDetail;
}

// =============================================================================
// Split-View Types (Story 3-4)
// =============================================================================

/** Bounding box data for split view display */
export interface SplitViewBoundingBox {
  bboxId: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
}

/** Document view data for one side of split view */
export interface DocumentViewData {
  documentId: string;
  documentUrl: string;
  pageNumber: number;
  boundingBoxes: SplitViewBoundingBox[];
}

/** Complete split view data for citation display */
export interface SplitViewData {
  citation: Citation;
  sourceDocument: DocumentViewData;
  targetDocument: DocumentViewData | null;
  verification: VerificationResult | null;
}

/** Response for split view endpoint */
export interface SplitViewResponse {
  data: SplitViewData;
}
