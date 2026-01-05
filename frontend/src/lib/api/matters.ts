'use client';

import { api, apiClient } from './client';
import type {
  Matter,
  MatterCreateRequest,
  MatterInviteRequest,
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
} from '@/types';

/**
 * Matter API client functions.
 *
 * These functions provide a typed interface to the matter API endpoints.
 * All functions handle authentication automatically via the base API client.
 */

/**
 * Create a new matter.
 * The creating user is automatically assigned as owner.
 */
export async function createMatter(data: MatterCreateRequest): Promise<Matter> {
  const response = await api.post<MatterResponse>('/api/matters', data);
  return response.data;
}

/**
 * Get all matters the current user has access to.
 */
export async function getMatters(options?: {
  page?: number;
  perPage?: number;
  status?: MatterStatus;
}): Promise<{ matters: Matter[]; meta: MatterListResponse['meta'] }> {
  const params = new URLSearchParams();

  if (options?.page) {
    params.set('page', String(options.page));
  }
  if (options?.perPage) {
    params.set('per_page', String(options.perPage));
  }
  if (options?.status) {
    params.set('status', options.status);
  }

  const queryString = params.toString();
  const endpoint = queryString ? `/api/matters?${queryString}` : '/api/matters';

  const response = await api.get<MatterListResponse>(endpoint);
  return { matters: response.data, meta: response.meta };
}

/**
 * Get a single matter with its members.
 */
export async function getMatter(matterId: string): Promise<MatterWithMembers> {
  const response = await api.get<MatterWithMembersResponse>(`/api/matters/${matterId}`);
  return response.data;
}

/**
 * Update matter details.
 * Requires editor or owner role.
 */
export async function updateMatter(
  matterId: string,
  data: MatterUpdateRequest
): Promise<Matter> {
  const response = await api.patch<MatterResponse>(`/api/matters/${matterId}`, data);
  return response.data;
}

/**
 * Soft-delete a matter.
 * Requires owner role.
 */
export async function deleteMatter(matterId: string): Promise<void> {
  await apiClient<void>(`/api/matters/${matterId}`, { method: 'DELETE' });
}

/**
 * Get all members of a matter.
 */
export async function getMembers(matterId: string): Promise<MatterMember[]> {
  const response = await api.get<MemberListResponse>(`/api/matters/${matterId}/members`);
  return response.data;
}

/**
 * Invite a new member to a matter.
 * Requires owner role.
 */
export async function inviteMember(
  matterId: string,
  email: string,
  role: MatterRole
): Promise<MatterMember> {
  const data: MatterInviteRequest = { email, role };
  const response = await api.post<MemberResponse>(`/api/matters/${matterId}/members`, data);
  return response.data;
}

/**
 * Update a member's role.
 * Requires owner role. Cannot demote self from owner.
 */
export async function updateMemberRole(
  matterId: string,
  userId: string,
  role: MatterRole
): Promise<MatterMember> {
  const data: MatterMemberUpdateRequest = { role };
  const response = await api.patch<MemberResponse>(
    `/api/matters/${matterId}/members/${userId}`,
    data
  );
  return response.data;
}

/**
 * Remove a member from a matter.
 * Requires owner role. Cannot remove self.
 */
export async function removeMember(matterId: string, userId: string): Promise<void> {
  await apiClient<void>(`/api/matters/${matterId}/members/${userId}`, { method: 'DELETE' });
}

/**
 * Matter API object for convenience.
 */
export const mattersApi = {
  create: createMatter,
  list: getMatters,
  get: getMatter,
  update: updateMatter,
  delete: deleteMatter,
  getMembers,
  inviteMember,
  updateMemberRole,
  removeMember,
};
