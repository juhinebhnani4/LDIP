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
