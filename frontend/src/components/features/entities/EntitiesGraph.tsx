'use client';

/**
 * EntitiesGraph Component
 *
 * Main React Flow graph visualization for MIG entities.
 * Displays entities as nodes with relationships as edges.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */

import { useCallback, useMemo, useEffect, useState, useRef } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type OnNodeClick,
  type NodeTypes,
  type EdgeTypes,
  BackgroundVariant,
} from '@xyflow/react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { EntityNode } from './EntityNode';
import { EntityEdge } from './EntityEdge';
import {
  updateNodeStates,
  getEntityTypeColor,
  isLargeGraph,
  applyDagreLayout,
} from '@/lib/utils/entityGraph';
import type { EntityGraphData, EntityGraphNode } from '@/types/entity';

const nodeTypes: NodeTypes = {
  entity: EntityNode,
};

const edgeTypes: EdgeTypes = {
  relationship: EntityEdge,
};

const LARGE_GRAPH_LIMIT = 100;

export interface EntitiesGraphProps {
  data: EntityGraphData;
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  focusNodeId?: string | null;
  className?: string;
}

function EntitiesGraphInner({
  data,
  selectedNodeId,
  onNodeSelect,
  focusNodeId,
  className,
}: EntitiesGraphProps) {
  const [showAllNodes, setShowAllNodes] = useState(false);
  const layoutAppliedRef = useRef(false);
  const prevDataKey = useRef<string>('');
  const { fitView } = useReactFlow();

  const isLarge = isLargeGraph(data.nodes.length);
  const shouldFilter = isLarge && !showAllNodes;

  const initialNodes = useMemo(() => {
    let nodesToUse = data.nodes;
    if (shouldFilter) {
      nodesToUse = [...data.nodes]
        .sort((a, b) => b.data.mentionCount - a.data.mentionCount)
        .slice(0, LARGE_GRAPH_LIMIT);
    }
    return nodesToUse;
  }, [data.nodes, shouldFilter]);

  const nodeIdsSet = useMemo(
    () => new Set(initialNodes.map((n) => n.id)),
    [initialNodes]
  );

  const initialEdges = useMemo(() => {
    return data.edges.filter(
      (e) => nodeIdsSet.has(e.source) && nodeIdsSet.has(e.target)
    );
  }, [data.edges, nodeIdsSet]);

  const layoutedNodes = useMemo(() => {
    if (initialNodes.length === 0) return initialNodes;
    return applyDagreLayout(initialNodes, initialEdges);
  }, [initialNodes, initialEdges]);

  // Generate a key to detect when data changes require re-layout
  const dataKey = `${data.nodes.length}-${showAllNodes}`;

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync layout when data changes - using refs to avoid ESLint setState warnings
  useEffect(() => {
    const needsLayout = prevDataKey.current !== dataKey;

    if (needsLayout || (!layoutAppliedRef.current && layoutedNodes.length > 0)) {
      setNodes(layoutedNodes);
      setEdges(initialEdges);
      layoutAppliedRef.current = true;
      prevDataKey.current = dataKey;
    }
  }, [layoutedNodes, initialEdges, setNodes, setEdges, dataKey]);

  // Focus on specific node when focusNodeId changes
  useEffect(() => {
    if (focusNodeId) {
      // Small delay to ensure nodes are rendered
      const timer = setTimeout(() => {
        fitView({
          nodes: [{ id: focusNodeId }],
          duration: 500,
          padding: 0.5,
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [focusNodeId, fitView]);

  const highlightedNodes = useMemo(() => {
    return updateNodeStates(nodes, selectedNodeId, edges);
  }, [nodes, edges, selectedNodeId]);

  const handleNodeClick: OnNodeClick<EntityGraphNode> = useCallback(
    (_event, node) => {
      onNodeSelect(node.id === selectedNodeId ? null : node.id);
    },
    [selectedNodeId, onNodeSelect]
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect(null);
  }, [onNodeSelect]);

  const handleShowAll = useCallback(() => {
    setShowAllNodes(true);
  }, []);

  if (data.nodes.length === 0) {
    return (
      <div
        className={cn(
          'flex items-center justify-center h-[600px] bg-muted/30 border rounded-lg',
          className
        )}
        role="region"
        aria-label="Entity graph"
      >
        <p className="text-muted-foreground">
          No entities found. Upload documents to extract entities.
        </p>
      </div>
    );
  }

  return (
    <div className={cn('relative', className)} role="region" aria-label="Entity graph">
      {shouldFilter && (
        <Alert className="absolute top-4 left-4 right-4 z-10 max-w-md">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Large graph detected</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>Showing top {LARGE_GRAPH_LIMIT} entities by mentions.</span>
            <Button variant="outline" size="sm" onClick={handleShowAll}>
              Show All ({data.nodes.length})
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="w-full h-[600px] bg-background border rounded-lg">
        <ReactFlow
          nodes={highlightedNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          attributionPosition="bottom-left"
          minZoom={0.25}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Controls
            showInteractive={false}
            aria-label="Graph zoom controls"
          />
          <MiniMap
            nodeColor={(node) => getEntityTypeColor(node.data?.entityType)}
            maskColor="rgba(0, 0, 0, 0.1)"
            aria-hidden="true"
          />
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}

// Wrapper component that provides ReactFlow context
export function EntitiesGraph(props: EntitiesGraphProps) {
  return (
    <ReactFlowProvider>
      <EntitiesGraphInner {...props} />
    </ReactFlowProvider>
  );
}

EntitiesGraph.displayName = 'EntitiesGraph';
