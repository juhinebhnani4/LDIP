/**
 * Entities Feature Components
 *
 * Barrel export for entity graph visualization components.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

export { EntitiesContent } from './EntitiesContent';
export type { EntitiesContentProps } from './EntitiesContent';

export { EntitiesGraph } from './EntitiesGraph';
export type { EntitiesGraphProps } from './EntitiesGraph';

export { EntitiesHeader } from './EntitiesHeader';
export type { EntitiesHeaderProps } from './EntitiesHeader';

export { EntitiesDetailPanel } from './EntitiesDetailPanel';
export type { EntitiesDetailPanelProps, ViewInDocumentParams } from './EntitiesDetailPanel';

export { EntityMergeDialog } from './EntityMergeDialog';
export type { EntityMergeDialogProps } from './EntityMergeDialog';

export { EntityNode, calculateNodeSize } from './EntityNode';
export type { EntityNodeProps } from './EntityNode';

export { EntityEdge, getEdgeStyle } from './EntityEdge';
export type { EntityEdgeProps } from './EntityEdge';

// View components (Story 10C.2)
export { EntitiesListView } from './EntitiesListView';
export type { EntitiesListViewProps } from './EntitiesListView';

export { EntitiesGridView } from './EntitiesGridView';
export type { EntitiesGridViewProps } from './EntitiesGridView';
