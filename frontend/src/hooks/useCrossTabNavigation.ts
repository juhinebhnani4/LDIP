/**
 * Cross-Tab Navigation Hook
 *
 * Gap 5-3: Cross-Engine Correlation Links
 *
 * Provides utilities for navigating between tabs while preserving context,
 * including highlighting specific items and scroll-to behavior.
 */

import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

// =============================================================================
// Types
// =============================================================================

export type WorkspaceTab = 'summary' | 'documents' | 'timeline' | 'entities' | 'contradictions' | 'verifications';

export interface CrossTabNavigationParams {
  /** Target tab to navigate to */
  tab: WorkspaceTab;
  /** Entity ID to highlight/select */
  entityId?: string;
  /** Timeline event ID to highlight/select */
  eventId?: string;
  /** Contradiction ID to highlight/select */
  contradictionId?: string;
  /** Document ID to open */
  documentId?: string;
  /** Page number to navigate to */
  page?: number;
  /** Whether to scroll to the highlighted item */
  scrollTo?: boolean;
}

export interface NavigationContext {
  /** Current highlighted entity */
  highlightedEntityId: string | null;
  /** Current highlighted event */
  highlightedEventId: string | null;
  /** Current highlighted contradiction */
  highlightedContradictionId: string | null;
  /** Source tab the user came from */
  sourceTab: WorkspaceTab | null;
}

// =============================================================================
// Query Parameter Keys
// =============================================================================

const PARAM_KEYS = {
  entity: 'entity',
  event: 'event',
  contradiction: 'contradiction',
  document: 'doc',
  page: 'page',
  source: 'from',
  scrollTo: 'scroll',
} as const;

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook for cross-tab navigation with context preservation.
 *
 * @param matterId - Current matter ID
 * @returns Navigation utilities and current context
 */
export function useCrossTabNavigation(matterId: string) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Parse current navigation context from URL
  const [context, setContext] = useState<NavigationContext>(() => ({
    highlightedEntityId: searchParams.get(PARAM_KEYS.entity),
    highlightedEventId: searchParams.get(PARAM_KEYS.event),
    highlightedContradictionId: searchParams.get(PARAM_KEYS.contradiction),
    sourceTab: searchParams.get(PARAM_KEYS.source) as WorkspaceTab | null,
  }));

  // Update context when URL changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Sync context with URL is intentional
    setContext({
      highlightedEntityId: searchParams.get(PARAM_KEYS.entity),
      highlightedEventId: searchParams.get(PARAM_KEYS.event),
      highlightedContradictionId: searchParams.get(PARAM_KEYS.contradiction),
      sourceTab: searchParams.get(PARAM_KEYS.source) as WorkspaceTab | null,
    });
  }, [searchParams]);

  // Determine current tab from pathname
  const getCurrentTab = useCallback((): WorkspaceTab | null => {
    if (!pathname) return null;
    const match = pathname.match(/\/matter\/[^/]+\/([^/?]+)/);
    return (match?.[1] as WorkspaceTab) ?? null;
  }, [pathname]);

  /**
   * Navigate to another tab with optional context preservation.
   */
  const navigateTo = useCallback(
    (params: CrossTabNavigationParams) => {
      const { tab, entityId, eventId, contradictionId, documentId, page, scrollTo = true } = params;

      // Build URL path
      const basePath = `/matter/${matterId}/${tab}`;

      // Build query params
      const queryParams = new URLSearchParams();

      if (entityId) {
        queryParams.set(PARAM_KEYS.entity, entityId);
      }
      if (eventId) {
        queryParams.set(PARAM_KEYS.event, eventId);
      }
      if (contradictionId) {
        queryParams.set(PARAM_KEYS.contradiction, contradictionId);
      }
      if (documentId) {
        queryParams.set(PARAM_KEYS.document, documentId);
      }
      if (page) {
        queryParams.set(PARAM_KEYS.page, page.toString());
      }

      // Add source tab for "back" navigation
      const currentTab = getCurrentTab();
      if (currentTab && currentTab !== tab) {
        queryParams.set(PARAM_KEYS.source, currentTab);
      }

      if (scrollTo) {
        queryParams.set(PARAM_KEYS.scrollTo, 'true');
      }

      const queryString = queryParams.toString();
      const url = queryString ? `${basePath}?${queryString}` : basePath;

      router.push(url);
    },
    [matterId, router, getCurrentTab]
  );

  /**
   * Navigate to entity with optional pre-selection.
   */
  const navigateToEntity = useCallback(
    (entityId: string, options?: { scrollTo?: boolean }) => {
      navigateTo({
        tab: 'entities',
        entityId,
        scrollTo: options?.scrollTo ?? true,
      });
    },
    [navigateTo]
  );

  /**
   * Navigate to timeline with optional event highlight.
   */
  const navigateToTimeline = useCallback(
    (options?: { eventId?: string; entityId?: string; scrollTo?: boolean }) => {
      navigateTo({
        tab: 'timeline',
        eventId: options?.eventId,
        entityId: options?.entityId,
        scrollTo: options?.scrollTo ?? true,
      });
    },
    [navigateTo]
  );

  /**
   * Navigate to contradictions with optional highlight.
   */
  const navigateToContradictions = useCallback(
    (options?: { contradictionId?: string; entityId?: string; scrollTo?: boolean }) => {
      navigateTo({
        tab: 'contradictions',
        contradictionId: options?.contradictionId,
        entityId: options?.entityId,
        scrollTo: options?.scrollTo ?? true,
      });
    },
    [navigateTo]
  );

  /**
   * Navigate back to source tab if available.
   */
  const navigateBack = useCallback(() => {
    if (context.sourceTab) {
      navigateTo({ tab: context.sourceTab, scrollTo: false });
    } else {
      router.back();
    }
  }, [context.sourceTab, navigateTo, router]);

  /**
   * Clear highlight parameters from URL without navigation.
   */
  const clearHighlights = useCallback(() => {
    const currentTab = getCurrentTab();
    if (!currentTab) return;

    const basePath = `/matter/${matterId}/${currentTab}`;
    router.replace(basePath);
  }, [matterId, router, getCurrentTab]);

  /**
   * Check if there's a highlighted item that should be scrolled to.
   */
  const shouldScrollToHighlight = useCallback((): boolean => {
    return searchParams.get(PARAM_KEYS.scrollTo) === 'true';
  }, [searchParams]);

  return {
    // Current context
    context,
    currentTab: getCurrentTab(),

    // Navigation methods
    navigateTo,
    navigateToEntity,
    navigateToTimeline,
    navigateToContradictions,
    navigateBack,

    // Utility methods
    clearHighlights,
    shouldScrollToHighlight,

    // Boolean flags
    hasSourceTab: !!context.sourceTab,
    hasHighlightedEntity: !!context.highlightedEntityId,
    hasHighlightedEvent: !!context.highlightedEventId,
    hasHighlightedContradiction: !!context.highlightedContradictionId,
  };
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Build a cross-tab navigation URL.
 * Useful for generating links without using the hook.
 */
export function buildCrossTabUrl(
  matterId: string,
  params: CrossTabNavigationParams
): string {
  const { tab, entityId, eventId, contradictionId, documentId, page } = params;

  const basePath = `/matter/${matterId}/${tab}`;
  const queryParams = new URLSearchParams();

  if (entityId) queryParams.set(PARAM_KEYS.entity, entityId);
  if (eventId) queryParams.set(PARAM_KEYS.event, eventId);
  if (contradictionId) queryParams.set(PARAM_KEYS.contradiction, contradictionId);
  if (documentId) queryParams.set(PARAM_KEYS.document, documentId);
  if (page) queryParams.set(PARAM_KEYS.page, page.toString());

  const queryString = queryParams.toString();
  return queryString ? `${basePath}?${queryString}` : basePath;
}

/**
 * Parse cross-tab navigation params from URL search params.
 */
export function parseCrossTabParams(
  searchParams: URLSearchParams
): Partial<CrossTabNavigationParams> {
  return {
    entityId: searchParams.get(PARAM_KEYS.entity) ?? undefined,
    eventId: searchParams.get(PARAM_KEYS.event) ?? undefined,
    contradictionId: searchParams.get(PARAM_KEYS.contradiction) ?? undefined,
    documentId: searchParams.get(PARAM_KEYS.document) ?? undefined,
    page: searchParams.get(PARAM_KEYS.page)
      ? parseInt(searchParams.get(PARAM_KEYS.page)!, 10)
      : undefined,
    scrollTo: searchParams.get(PARAM_KEYS.scrollTo) === 'true',
  };
}
