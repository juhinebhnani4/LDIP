/**
 * TypeScript Types
 *
 * Naming conventions (from project-context.md):
 * - Types/Interfaces: PascalCase (e.g., Matter, DocumentUpload)
 * - Use `satisfies` operator for type-safe object literals
 * - No `any` types - use `unknown` + type guards instead
 */

// Matter types
export type {
  ApiError,
  Matter,
  MatterCreateRequest,
  MatterInviteRequest,
  MatterListMeta,
  MatterListResponse,
  MatterMember,
  MatterMemberUpdateRequest,
  MatterResponse,
  MatterRole,
  MatterStatus,
  MatterUpdateRequest,
  MatterWithMembers,
  MatterWithMembersResponse,
  MemberListResponse,
  MemberResponse,
} from './matter';

export { canEdit, hasAccess, isOwner } from './matter';

// Document types
export type {
  Document,
  DocumentStatus,
  DocumentType,
  UploadFile,
  UploadRequest,
  UploadResponse,
  UploadStatus,
  ValidationError,
  ValidationResult,
  ValidationWarning,
} from './document';

// Search types
export type {
  BM25SearchRequest,
  SearchMeta,
  SearchMode,
  SearchRequest,
  SearchResponse,
  SearchResult,
  SemanticSearchRequest,
  SingleModeSearchMeta,
  SingleModeSearchResponse,
} from './search';

export { DEFAULT_SEARCH_WEIGHTS, SEARCH_LIMITS } from './search';

// Entity types (MIG)
export type {
  EntitiesListResponse,
  Entity,
  EntityBase,
  EntityEdge,
  EntityListItem,
  EntityListOptions,
  EntityMention,
  EntityMentionsOptions,
  EntityMentionsResponse,
  EntityMetadata,
  EntityResponse,
  EntityType,
  EntityWithRelations,
  PaginationMeta,
  RelationshipType,
} from './entity';

// Job types (Story 2c-3: Background Job Tracking)
export type {
  DocumentProcessingStatus,
  JobCancelResponse,
  JobDetailResponse,
  JobEvent,
  JobListResponse,
  JobProgressEvent,
  JobQueueStats,
  JobRetryRequest,
  JobRetryResponse,
  JobSkipResponse,
  JobStageHistory,
  JobStatus,
  JobStatusChangeEvent,
  JobType,
  ProcessingJob,
  ProcessingJobWithHistory,
  ProcessingSummaryEvent,
  StageStatus,
} from './job';

export {
  canCancelJob,
  canRetryJob,
  canSkipJob,
  getJobStatusColor,
  getJobStatusLabel,
  isJobActive,
  isJobTerminal,
  STAGE_LABELS,
} from './job';

// Citation types (Story 3-1: Act Citation Extraction, Story 3-3: Verification, Story 3-4: Split View)
export type {
  ActDiscoveryResponse,
  ActDiscoverySummary,
  ActResolution,
  ActResolutionResponse,
  ActResolutionStatus,
  BatchVerificationResponse,
  Citation,
  CitationBase,
  CitationErrorDetail,
  CitationErrorResponse,
  CitationListItem,
  CitationListOptions,
  CitationResponse,
  CitationsListResponse,
  CitationStats,
  CitationSummaryItem,
  CitationSummaryResponse,
  CitationVerifiedEvent,
  DiffDetail,
  DocumentViewData,
  MarkActSkippedRequest,
  MarkActUploadedRequest,
  MatchType,
  QuoteComparison,
  SectionMatch,
  SplitViewBoundingBox,
  SplitViewData,
  SplitViewResponse,
  UserAction,
  VerificationCompleteEvent,
  VerificationEvent,
  VerificationProgressEvent,
  VerificationResult,
  VerificationResultResponse,
  VerificationStatus,
  VerifyActRequest,
  VerifyCitationRequest,
} from './citation';

// PDF types (Story 3-4: Split-View Citation Highlighting)
export type {
  BoundingBox as PdfBoundingBox,
  BoundingBoxData,
  CanvasRect,
  HighlightColors,
  HighlightStatus,
  PdfViewerError,
  PdfViewerState,
  ZoomLevel,
} from './pdf';

export { HIGHLIGHT_COLORS, PDF_KEYBOARD_SHORTCUTS } from './pdf';

// Verification types (Story 8-5: Verification Queue UI)
export type {
  ApproveVerificationRequest,
  BulkVerificationRequest,
  BulkVerificationResponse as FindingBulkVerificationResponse,
  ConfidenceTier,
  FindingVerification,
  FlagVerificationRequest,
  RejectVerificationRequest,
  VerificationFilters,
  VerificationListResponse as FindingVerificationListResponse,
  VerificationQueueItem,
  VerificationQueueResponse,
  VerificationResponse as FindingVerificationResponse,
  VerificationStats,
  VerificationStatsResponse,
  VerificationView,
} from './verification';

export { VerificationDecision, VerificationRequirement } from './verification';

// Summary types (Story 10B.1: Summary Tab Content, Story 10B.2: Verification and Edit)
export type {
  AttentionItem,
  AttentionItemType,
  CurrentStatus,
  KeyIssue,
  KeyIssueVerificationStatus,
  MatterStats,
  MatterSummary,
  MatterSummaryResponse,
  PartyInfo,
  PartyRole,
  SubjectMatter,
  SubjectMatterSource,
  SummaryEditHistory,
  SummaryNote,
  SummarySectionType,
  SummaryVerification,
  SummaryVerificationDecision,
} from './summary';

// Timeline types (Story 10B.3: Timeline Tab Vertical List View, Story 10B.4: Alternative Views)
export type {
  DatePrecision,
  EventCluster,
  TimelineEntityReference,
  TimelineEvent,
  TimelineEventType,
  TimelineGap,
  TimelinePaginationMeta,
  TimelineResponse,
  TimelineScale,
  TimelineStats,
  TimelineStatsResponse,
  TimelineTrack,
  TimelineViewMode,
  UseTimelineOptions,
  YearLabel,
  ZoomLevel as TimelineZoomLevel,
} from './timeline';
