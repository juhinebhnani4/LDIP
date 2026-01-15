'use client';

/**
 * EntitiesContent Component
 *
 * Main container for the entities tab, managing view modes, filters, selection,
 * and entity merge functionality.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 * @see Story 10C.2 - Entities Tab Detail Panel and Merge Dialog
 */

import { useCallback, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { EntitiesHeader } from './EntitiesHeader';
import { EntitiesGraph } from './EntitiesGraph';
import { EntitiesDetailPanel } from './EntitiesDetailPanel';
import { EntitiesListView } from './EntitiesListView';
import { EntitiesGridView } from './EntitiesGridView';
import { EntityMergeDialog } from './EntityMergeDialog';
import type { ViewInDocumentParams } from './EntitiesDetailPanel';
import {
  useEntities,
  useEntityDetail,
  useEntityRelationships,
  useEntityStats,
  useEntityMerge,
  useEntityAlias,
} from '@/hooks/useEntities';
import {
  transformEntitiesToNodes,
  transformRelationshipsToEdges,
  filterNodesByTypes,
  filterNodesBySearch,
  filterEdgesForNodes,
} from '@/lib/utils/entityGraph';
import { DEFAULT_ENTITY_FILTERS } from '@/types/entity';
import type {
  EntityViewMode,
  EntityFilterState,
  EntityGraphData,
  EntityListItem,
} from '@/types/entity';

export interface EntitiesContentProps {
  matterId: string;
  onViewInDocument?: (params: ViewInDocumentParams) => void;
  className?: string;
}

export function EntitiesContent({
  matterId,
  onViewInDocument,
  className,
}: EntitiesContentProps) {
  // View state
  const [viewMode, setViewMode] = useState<EntityViewMode>('graph');
  const [filters, setFilters] = useState<EntityFilterState>(DEFAULT_ENTITY_FILTERS);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);

  // Multi-select merge state
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false);
  const [selectedForMerge, setSelectedForMerge] = useState<Set<string>>(new Set());
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [mergeError, setMergeError] = useState<string | null>(null);

  // Fetch entities and relationships
  const {
    entities,
    isLoading: entitiesLoading,
    error: entitiesError,
    mutate: mutateEntities,
  } = useEntities(matterId, { perPage: 500 });

  const { edges, isLoading: edgesLoading } = useEntityRelationships(matterId, entities);

  const {
    entity: selectedEntity,
    isLoading: detailLoading,
    error: detailError,
    mutate: mutateDetail,
  } = useEntityDetail(matterId, selectedEntityId);

  // Merge and alias hooks
  const { merge, isLoading: mergeLoading } = useEntityMerge(matterId);
  const { addAlias: addAliasApi } = useEntityAlias(matterId);

  // Compute statistics
  const stats = useEntityStats(entities);

  // Filter entities for list/grid views
  const filteredEntities = useMemo(() => {
    let filtered = entities;

    if (filters.entityTypes.length > 0) {
      filtered = filtered.filter((e) => filters.entityTypes.includes(e.entityType));
    }

    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      filtered = filtered.filter(
        (e) =>
          e.canonicalName.toLowerCase().includes(query) ||
          e.metadata?.roles?.some((r) => r.toLowerCase().includes(query)) ||
          e.metadata?.aliasesFound?.some((a) => a.toLowerCase().includes(query))
      );
    }

    if (filters.minMentionCount > 0) {
      filtered = filtered.filter((e) => e.mentionCount >= filters.minMentionCount);
    }

    if (filters.verificationStatus !== 'all') {
      filtered = filtered.filter((e) => {
        if (filters.verificationStatus === 'verified') {
          return e.metadata?.verified === true;
        }
        if (filters.verificationStatus === 'flagged') {
          return e.metadata?.flagged === true;
        }
        if (filters.verificationStatus === 'pending') {
          return !e.metadata?.verified && !e.metadata?.flagged;
        }
        return true;
      });
    }

    return filtered;
  }, [entities, filters]);

  // Transform and filter graph data
  const graphData: EntityGraphData = useMemo(() => {
    if (entities.length === 0) {
      return { nodes: [], edges: [] };
    }

    // Transform entities to nodes
    let nodes = transformEntitiesToNodes(entities);

    // Apply filters
    if (filters.entityTypes.length > 0) {
      nodes = filterNodesByTypes(nodes, filters.entityTypes);
    }
    if (filters.searchQuery) {
      nodes = filterNodesBySearch(nodes, filters.searchQuery);
    }

    // Transform edges and filter to visible nodes
    const nodeIds = new Set(nodes.map((n) => n.id));
    const transformedEdges = transformRelationshipsToEdges(edges);
    const filteredEdges = filterEdgesForNodes(transformedEdges, nodeIds);

    return {
      nodes,
      edges: filteredEdges,
    };
  }, [entities, edges, filters]);

  // Get entities selected for merge
  const mergeEntities = useMemo(() => {
    const ids = Array.from(selectedForMerge);
    if (ids.length !== 2) return { source: null, target: null };

    const entity1 = entities.find((e) => e.id === ids[0]) ?? null;
    const entity2 = entities.find((e) => e.id === ids[1]) ?? null;

    return { source: entity1, target: entity2 };
  }, [selectedForMerge, entities]);

  // Handlers
  const handleViewModeChange = useCallback((mode: EntityViewMode) => {
    setViewMode(mode);
  }, []);

  const handleFiltersChange = useCallback((newFilters: EntityFilterState) => {
    setFilters(newFilters);
  }, []);

  const handleEntitySelect = useCallback((entityId: string | null) => {
    setSelectedEntityId(entityId);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedEntityId(null);
  }, []);

  const handleFocusInGraph = useCallback(() => {
    if (selectedEntityId) {
      setViewMode('graph');
      setFocusNodeId(selectedEntityId);
      setTimeout(() => setFocusNodeId(null), 600);
    }
  }, [selectedEntityId]);

  const handleMultiSelectModeChange = useCallback((enabled: boolean) => {
    setIsMultiSelectMode(enabled);
    if (!enabled) {
      setSelectedForMerge(new Set());
    }
  }, []);

  const handleToggleMergeSelection = useCallback((entityId: string) => {
    setSelectedForMerge((prev) => {
      const next = new Set(prev);
      if (next.has(entityId)) {
        next.delete(entityId);
      } else if (next.size < 2) {
        next.add(entityId);
      }
      return next;
    });
  }, []);

  const handleMergeClick = useCallback(() => {
    if (selectedForMerge.size === 2) {
      setMergeError(null);
      setMergeDialogOpen(true);
    }
  }, [selectedForMerge]);

  const handleMergeConfirm = useCallback(
    async (sourceId: string, targetId: string, reason?: string) => {
      try {
        const result = await merge({
          sourceEntityId: sourceId,
          targetEntityId: targetId,
          reason,
        });

        toast.success(
          `Entities merged successfully. ${result.aliasesAdded.length} aliases were added.`
        );

        // Reset state
        setMergeDialogOpen(false);
        setSelectedForMerge(new Set());
        setIsMultiSelectMode(false);

        // If the deleted entity was selected, clear selection
        if (selectedEntityId === sourceId) {
          setSelectedEntityId(result.keptEntityId);
        }

        // Refresh data
        await mutateEntities();
        if (selectedEntityId === result.keptEntityId) {
          await mutateDetail();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to merge entities';
        setMergeError(message);
      }
    },
    [merge, selectedEntityId, mutateEntities, mutateDetail]
  );

  const handleAddAlias = useCallback(
    async (alias: string) => {
      if (!selectedEntityId) return;

      await addAliasApi(selectedEntityId, alias);

      toast.success(`Alias "${alias}" was added to the entity.`);

      await mutateDetail();
    },
    [selectedEntityId, addAliasApi, mutateDetail]
  );

  const isLoading = entitiesLoading || edgesLoading;

  if (entitiesError) {
    return (
      <div
        className={cn(
          'flex items-center justify-center h-[600px] bg-muted/30 border rounded-lg',
          className
        )}
      >
        <p className="text-destructive">
          Failed to load entities. Please try again.
        </p>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      <EntitiesHeader
        stats={{
          ...stats,
          filteredTotal: filteredEntities.length,
        }}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        filters={filters}
        onFiltersChange={handleFiltersChange}
        isMultiSelectMode={isMultiSelectMode}
        onMultiSelectModeChange={handleMultiSelectModeChange}
        selectedForMergeCount={selectedForMerge.size}
        onMergeClick={handleMergeClick}
        className="mb-4"
      />

      <div className="flex-1 flex gap-0 min-h-0">
        {/* Main content area */}
        <div className="flex-1 min-w-0">
          {isLoading ? (
            <div className="h-[600px] bg-muted/30 border rounded-lg flex items-center justify-center">
              <div className="space-y-4 text-center">
                <Skeleton className="h-8 w-8 rounded-full mx-auto" />
                <Skeleton className="h-4 w-32 mx-auto" />
              </div>
            </div>
          ) : viewMode === 'graph' ? (
            <EntitiesGraph
              data={graphData}
              selectedNodeId={selectedEntityId}
              onNodeSelect={handleEntitySelect}
              focusNodeId={focusNodeId}
              className="h-[600px]"
            />
          ) : viewMode === 'list' ? (
            <EntitiesListView
              entities={filteredEntities}
              selectedEntityId={selectedEntityId}
              onEntitySelect={handleEntitySelect}
              isMultiSelectMode={isMultiSelectMode}
              selectedForMerge={selectedForMerge}
              onToggleMergeSelection={handleToggleMergeSelection}
            />
          ) : (
            <EntitiesGridView
              entities={filteredEntities}
              selectedEntityId={selectedEntityId}
              onEntitySelect={handleEntitySelect}
              isMultiSelectMode={isMultiSelectMode}
              selectedForMerge={selectedForMerge}
              onToggleMergeSelection={handleToggleMergeSelection}
            />
          )}
        </div>

        {/* Detail panel */}
        {selectedEntityId && (
          <EntitiesDetailPanel
            entity={selectedEntity}
            matterId={matterId}
            isLoading={detailLoading}
            error={detailError?.message}
            onClose={handleCloseDetail}
            onEntitySelect={handleEntitySelect}
            onFocusInGraph={handleFocusInGraph}
            onViewInDocument={onViewInDocument}
            onAddAlias={handleAddAlias}
          />
        )}
      </div>

      {/* Merge dialog */}
      <EntityMergeDialog
        open={mergeDialogOpen}
        onOpenChange={setMergeDialogOpen}
        sourceEntity={mergeEntities.source}
        targetEntity={mergeEntities.target}
        onConfirm={handleMergeConfirm}
        isLoading={mergeLoading}
        error={mergeError}
      />
    </div>
  );
}

EntitiesContent.displayName = 'EntitiesContent';
