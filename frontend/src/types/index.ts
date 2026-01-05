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

// Future types (to be added in later stories):
// export type { Document, DocumentUpload } from './document';
