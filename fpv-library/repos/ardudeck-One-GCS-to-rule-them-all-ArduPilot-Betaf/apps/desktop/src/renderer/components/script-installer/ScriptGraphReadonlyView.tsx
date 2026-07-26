/**
 * Read-only React Flow viewer for ArduDeck-shipped script graphs.
 *
 * Renders the existing GraphNodeComponent so visual styling stays consistent
 * with the editor, but all editing affordances are disabled: nodes/edges can't
 * move, select, connect, or delete. Pan + zoom + minimap stay enabled so the
 * user can inspect comfortably.
 *
 * Self-contained: does NOT touch useLuaGraphStore so opening the viewer never
 * disturbs in-progress work the user has open in the real graph editor.
 */

import { ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, MarkerType, type Node, type Edge, type DefaultEdgeOptions } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import GraphNodeComponent from '../lua-graph/GraphNodeComponent';
import { CATEGORY_COLORS, type GraphNodeData, type GraphEdgeData } from '../lua-graph/lua-graph-types';
import { useResolvedTheme } from '../../hooks/useTheme';

const nodeTypes = { graphNode: GraphNodeComponent };

// Default edge styling: bezier curve, soft purple, arrow at the target end so
// data/flow direction is visually obvious without clicking.
const defaultEdgeOptions: DefaultEdgeOptions = {
  type: 'smoothstep',
  style: { stroke: '#a78bfa', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#a78bfa' },
};

interface ScriptGraphReadonlyViewProps {
  nodes: Node<GraphNodeData>[];
  edges: Edge<GraphEdgeData>[];
}

export function ScriptGraphReadonlyView({ nodes, edges }: ScriptGraphReadonlyViewProps) {
  const isLight = useResolvedTheme() === 'light';
  return (
    <ReactFlowProvider>
      <div className="w-full h-full bg-surface-base script-graph-readonly">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll
          zoomOnPinch
          deleteKeyCode={null}
          colorMode={isLight ? 'light' : 'dark'}
          proOptions={{ hideAttribution: true }}
          className="bg-transparent"
        >
          <Background color={isLight ? '#d1d5db' : '#374151'} gap={16} size={1} />
          <Controls
            showInteractive={false}
            className="!bg-surface !border-subtle !rounded-lg !shadow-lg [&>button]:!bg-surface-raised [&>button]:!border [&>button]:!text-content [&>button:hover]:!bg-surface-raised"
          />
          <MiniMap
            pannable
            zoomable
            maskColor={isLight ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'}
            nodeColor={(n) => {
              const cat = (n.data as GraphNodeData | undefined)?.category;
              return cat ? CATEGORY_COLORS[cat] ?? '#6b7280' : '#6b7280';
            }}
            nodeStrokeColor="rgba(0,0,0,0.4)"
            nodeStrokeWidth={2}
            nodeBorderRadius={4}
            className="!bg-surface !border-subtle !rounded-lg"
            style={{ width: 220, height: 160 }}
          />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
