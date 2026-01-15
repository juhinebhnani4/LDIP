'use client';

/**
 * EntitiesContent Component
 *
 * Main container for the entities tab, managing view modes, filters, and selection.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import { useCallback, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { EntitiesHeader } from './EntitiesHeader';
import { EntitiesGraph } from './EntitiesGraph';
import { EntitiesDetailPanel } from './EntitiesDetailPanel';
import {
  useEntities,
  useEntityDetail,
  useEntityRelationships,
  useEntityStats,
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
} from '@/types/entity';

export interface EntitiesContentProps {
  matterId: string;
  className?: string;
}

export function EntitiesContent({ matterId, className }: EntitiesContentProps) {
  const [viewMode, setViewMode] = useState<EntityViewMode>('graph');
  const [filters, setFilters] = useState<EntityFilterState>(DEFAULT_ENTITY_FILTERS);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  // Fetch entities and relationships
  const { entities, isLoading: entitiesLoading, error: entitiesError } = useEntities(
    matterId,
    { perPage: 500 } // Fetch more for graph view
  );

  const { edges, isLoading: edgesLoading } = useEntityRelationships(matterId, entities);

  const {
    entity: selectedEntity,
    isLoading: detailLoading,
    error: detailError,
  } = useEntityDetail(matterId, selectedEntityId);

  // Compute statistics
  const stats = useEntityStats(entities);

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

  const handleViewModeChange = useCallback((mode: EntityViewMode) => {
    setViewMode(mode);
  }, []);

  const handleFiltersChange = useCallback((newFilters: EntityFilterState) => {
    setFilters(newFilters);
  }, []);

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setSelectedEntityId(nodeId);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedEntityId(null);
  }, []);

  const handleFocusInGraph = useCallback(() => {
    // Graph will highlight based on selectedEntityId
  }, []);

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
        stats={stats}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        filters={filters}
        onFiltersChange={handleFiltersChange}
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
              onNodeSelect={handleNodeSelect}
              className="h-[600px]"
            />
          ) : viewMode === 'list' ? (
            <div className="h-[600px] bg-muted/30 border rounded-lg flex items-center justify-center">
              <p className="text-muted-foreground">
                List view coming in Story 10C.2
              </p>
            </div>
          ) : (
            <div className="h-[600px] bg-muted/30 border rounded-lg flex items-center justify-center">
              <p className="text-muted-foreground">
                Grid view coming in Story 10C.2
              </p>
            </div>
          )}
        </div>

        {/* Detail panel */}
        {selectedEntityId && (
          <EntitiesDetailPanel
            entity={selectedEntity}
            isLoading={detailLoading}
            error={detailError?.message}
            onClose={handleCloseDetail}
            onEntitySelect={handleNodeSelect}
            onFocusInGraph={handleFocusInGraph}
          />
        )}
      </div>
    </div>
  );
}

EntitiesContent.displayName = 'EntitiesContent';
