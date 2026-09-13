import { useEffect, useMemo } from "react";
import { Background, Controls, ReactFlow, useNodesState, useEdgesState, useReactFlow, ReactFlowProvider, type NodeMouseHandler, type Node } from "@xyflow/react";
import type { Graph } from "../../lib/types";
import { buildFlow, type FlowNodeData } from "./layout";
import { LearnNode } from "./LearnNode";

const nodeTypes = { learn: LearnNode };

function Canvas({ graph, selectedId, onSelect, viewportKey }: { graph: Graph; selectedId: string | null; onSelect: (id: string) => void; viewportKey: string }) {
  const recommended = useMemo(() => new Set(graph.next_actions.slice(0, 1).map((a) => a.node_id)), [graph.next_actions]);
  const flow = useMemo(() => buildFlow(graph.nodes, graph.edges, selectedId, recommended), [graph.nodes, graph.edges, selectedId, recommended]);
  const [nodes, setNodes] = useNodesState<Node<FlowNodeData>>(flow.nodes);
  const [edges, setEdges] = useEdgesState(flow.edges);
  const { fitView } = useReactFlow();

  useEffect(() => {
    setNodes(flow.nodes);
    setEdges(flow.edges);
  }, [flow, setNodes, setEdges]);

  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.12, duration: 300 }), 60);
    return () => clearTimeout(t);
  }, [graph.id, graph.nodes.length, viewportKey, fitView]);

  const onNodeClick: NodeMouseHandler<Node<FlowNodeData>> = (_e, node) => onSelect(node.id);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={onNodeClick}
      nodesConnectable={false}
      elementsSelectable={false}
      minZoom={0.3}
      maxZoom={1.6}
      proOptions={{ hideAttribution: true }}
      fitView
    >
      <Background gap={24} size={1} color="#e2e8f0" />
      <Controls showInteractive={false} position="bottom-left" />
    </ReactFlow>
  );
}

export function GraphCanvas(props: { graph: Graph; selectedId: string | null; onSelect: (id: string) => void; viewportKey: string }) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
