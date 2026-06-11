/**
 * Workspace store shared types.
 *
 * Extracted from workspaceStore.ts to break a circular dependency:
 * workspaceStore.ts imports the tab-stats API client (lib/api/tabStats.ts),
 * which in turn needs these tab types. Keeping the types in a dependency-free
 * leaf module lets both files import them without forming an import cycle
 * (see FE-023 in BUGS.md). These types are re-exported from workspaceStore.ts,
 * so existing `@/stores/workspaceStore` imports continue to work.
 */

/**
 * Tab ID type - must match route segments
 */
export type TabId =
  | 'summary'
  | 'timeline'
  | 'entities'
  | 'citations'
  | 'contradictions'
  | 'verification'
  | 'documents';

/**
 * Tab statistics for displaying counts and issues
 */
export interface TabStats {
  /** Number of items in this tab */
  count: number;
  /** Number of issues requiring attention */
  issueCount: number;
}

/**
 * Processing status for each tab.
 * 'failed' = a document in this matter terminally failed (documents.status);
 * surfaced on the documents tab and rolled up to the matter badge (FE-007).
 */
export type TabProcessingStatus = 'ready' | 'processing' | 'failed';
