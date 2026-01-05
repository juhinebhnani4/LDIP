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
}

/** Request model for updating an existing matter */
export interface MatterUpdateRequest {
  title?: string;
  description?: string | null;
  status?: MatterStatus;
}

/** Complete matter model returned from API */
export interface Matter extends MatterBase {
  id: string;
  status: MatterStatus;
  createdAt: string;
  updatedAt: string;
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
 * Type guard for checking if a role has edit permissions
 */
export function canEdit(role: MatterRole | null): boolean {
  return role === 'owner' || role === 'editor';
}

/**
 * Type guard for checking if a role has owner permissions
 */
export function isOwner(role: MatterRole | null): boolean {
  return role === 'owner';
}

/**
 * Type guard for checking if user has any access
 */
export function hasAccess(role: MatterRole | null): boolean {
  return role !== null;
}
