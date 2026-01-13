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
