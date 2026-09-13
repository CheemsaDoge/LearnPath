import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import type { GraphEdge, GraphNode } from "../../lib/types";

export const NODE_W = 208;
export const NODE_H = 72;

export interface FlowNodeData extends Record<string, unknown> {
  node: GraphNode;
  selected: boolean;
  recommended: boolean;
}

export function buildFlow(nodes: GraphNode[], edges: GraphEdge[], selectedId: string | null, recommendedIds: Set<string>): { nodes: Node<FlowNodeData>[]; edges: Edge[] } {
  const layerOf = new Map(nodes.map((n) => [n.id, n.layer]));
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 18, ranksep: 72, marginx: 20, marginy: 20 });
  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: n.node_type === "root" ? 56 : NODE_H });
  for (const e of edges) if (e.relation === "contains") g.setEdge(e.source_id, e.target_id);
  dagre.layout(g);

  const flowNodes: Node<FlowNodeData>[] = nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: "learn",
      position: { x: pos.x - NODE_W / 2, y: pos.y - (n.node_type === "root" ? 28 : NODE_H / 2) },
      data: { node: n, selected: n.id === selectedId, recommended: recommendedIds.has(n.id) },
      draggable: false,
    };
  });

  const flowEdges: Edge[] = edges.map((e) => {
    const isContains = e.relation === "contains";
    const isPre = e.relation === "prerequisite";
    const sameLayer = !isContains && layerOf.get(e.source_id) === layerOf.get(e.target_id);
    return {
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      // LR layout: parent→child edges run left→right; same-layer prerequisite edges run top→bottom
      sourceHandle: sameLayer ? "bottom" : "right",
      targetHandle: sameLayer ? "top" : "left",
      type: isContains || sameLayer ? "smoothstep" : "default",
      animated: false,
      style: isContains
        ? { stroke: "#cbd5e1", strokeWidth: 1.5 }
        : isPre
          ? { stroke: "#0f6fff", strokeWidth: 1.6, strokeDasharray: "6 4", opacity: 0.75 }
          : { stroke: "#a78bfa", strokeWidth: 1.2, strokeDasharray: "2 4", opacity: 0.7 },
      markerEnd: isContains ? undefined : { type: "arrowclosed" as const, color: isPre ? "#0f6fff" : "#a78bfa", width: 16, height: 16 },
      zIndex: isContains ? 0 : 1,
    };
  });
  return { nodes: flowNodes, edges: flowEdges };
}
