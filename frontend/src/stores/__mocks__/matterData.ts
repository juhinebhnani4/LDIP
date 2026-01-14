/**
 * Mock Matter Data
 *
 * Development-only mock data for the matter store.
 * This file will be replaced with real API responses when backend is ready.
 *
 * TODO: Remove this file when backend provides all MatterCardData fields:
 * - pageCount, documentCount, verificationPercent, issueCount
 * - processingStatus, processingProgress, estimatedTimeRemaining
 * - lastOpened
 */

import type { MatterCardData } from '@/types/matter';

/**
 * Generate mock matters with deterministic IDs for stable React keys.
 * Uses fixed IDs to prevent full re-renders on each fetch.
 */
export function getMockMatters(): MatterCardData[] {
  const now = new Date();

  return [
    {
      id: 'mock_matter_shah_v_mehta',
      title: 'Shah v. Mehta',
      description: 'Property dispute case regarding commercial premises',
      status: 'active',
      createdAt: new Date(now.getTime() - 30 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 2 * 60 * 60000).toISOString(),
      role: 'owner',
      memberCount: 3,
      pageCount: 1247,
      documentCount: 89,
      verificationPercent: 85,
      issueCount: 3,
      processingStatus: 'ready',
      lastOpened: new Date(now.getTime() - 2 * 60 * 60000).toISOString(),
    },
    {
      id: 'mock_matter_sebi_v_parekh',
      title: 'SEBI v. Parekh',
      description: 'Securities fraud investigation',
      status: 'active',
      createdAt: new Date(now.getTime() - 7 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 5 * 60000).toISOString(),
      role: 'editor',
      memberCount: 5,
      pageCount: 2100,
      documentCount: 156,
      verificationPercent: 0,
      issueCount: 0,
      processingStatus: 'processing',
      processingProgress: 67,
      estimatedTimeRemaining: 180,
    },
    {
      id: 'mock_matter_reliance_v_bpcl',
      title: 'Reliance v. BPCL',
      description: 'Contract dispute over gas pipeline rights',
      status: 'active',
      createdAt: new Date(now.getTime() - 60 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 24 * 60 * 60000).toISOString(),
      role: 'owner',
      memberCount: 2,
      pageCount: 892,
      documentCount: 45,
      verificationPercent: 62,
      issueCount: 8,
      processingStatus: 'needs_attention',
      lastOpened: new Date(now.getTime() - 24 * 60 * 60000).toISOString(),
    },
    {
      id: 'mock_matter_tata_v_mistry',
      title: 'Tata v. Mistry',
      description: 'Corporate governance dispute',
      status: 'active',
      createdAt: new Date(now.getTime() - 90 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 48 * 60 * 60000).toISOString(),
      role: 'viewer',
      memberCount: 8,
      pageCount: 3456,
      documentCount: 210,
      verificationPercent: 94,
      issueCount: 1,
      processingStatus: 'ready',
      lastOpened: new Date(now.getTime() - 48 * 60 * 60000).toISOString(),
    },
    {
      id: 'mock_matter_infosys_ip',
      title: 'Infosys IP Matter',
      description: 'Intellectual property licensing dispute',
      status: 'archived',
      createdAt: new Date(now.getTime() - 180 * 24 * 60 * 60000).toISOString(),
      updatedAt: new Date(now.getTime() - 30 * 24 * 60 * 60000).toISOString(),
      role: 'owner',
      memberCount: 2,
      pageCount: 567,
      documentCount: 32,
      verificationPercent: 100,
      issueCount: 0,
      processingStatus: 'ready',
      lastOpened: new Date(now.getTime() - 30 * 24 * 60 * 60000).toISOString(),
    },
  ];
}
