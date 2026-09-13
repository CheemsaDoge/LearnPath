import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { BookOpen, Dumbbell, Lock, Loader2, Sparkles } from "lucide-react";
import { Stars } from "../Stars";
import type { FlowNodeData } from "./layout";

const TYPE_STYLE: Record<string, string> = {
  root: "bg-brand-600 text-white border-brand-600 shadow-md",
  module: "bg-white border-brand-300 text-ink",
  concept: "bg-white border-slate-200 text-ink",
  practice: "bg-emerald-50 border-emerald-300 text-ink",
};

export function LearnNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const { node, selected, recommended } = data;
  const isRoot = node.node_type === "root";
  const locked = !node.unlocked;
  const grounding = node.grounding_status === "pending";
  return (
    <div
      className={`relative rounded-xl border px-3 py-2 w-[208px] transition-all ${TYPE_STYLE[node.node_type] ?? TYPE_STYLE.concept} ${
        selected ? "ring-2 ring-brand-500 ring-offset-2" : ""
      } ${locked && !isRoot ? "opacity-60" : ""} ${recommended && !selected ? "ring-2 ring-amber-300" : ""} ${isRoot ? "text-center" : ""}`}
    >
      <Handle id="left" type="target" position={Position.Left} className="!bg-slate-300 !w-1.5 !h-1.5 !border-0" />
      <Handle id="top" type="target" position={Position.Top} className="!bg-transparent !w-1 !h-1 !border-0" />
      <Handle id="right" type="source" position={Position.Right} className="!bg-slate-300 !w-1.5 !h-1.5 !border-0" />
      {recommended && !isRoot && (
        <span className="absolute -top-2 -right-2 inline-flex items-center gap-0.5 rounded-full bg-amber-400 text-[10px] font-semibold text-amber-950 px-1.5 py-0.5 shadow">
          <Sparkles size={10} /> 推荐
        </span>
      )}
      <div className={`flex items-start gap-1.5 ${isRoot ? "justify-center" : ""}`}>
        {!isRoot && node.node_type === "practice" && <Dumbbell size={14} className="mt-0.5 shrink-0 text-emerald-600" />}
        {!isRoot && node.node_type === "concept" && <BookOpen size={14} className="mt-0.5 shrink-0 text-brand-500" />}
        <div className={`font-semibold leading-snug ${isRoot ? "text-[15px]" : "text-[13px]"} line-clamp-2`}>{node.label}</div>
      </div>
      {!isRoot && (
        <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
          <Stars value={node.mastery_stars} size={11} />
          <span className="flex items-center gap-1">
            {grounding ? <Loader2 size={11} className="animate-spin" /> : node.source_count > 0 ? <span>{node.source_count} 篇知乎</span> : null}
            {locked && <Lock size={11} />}
            {node.node_type !== "module" && <span>{node.est_minutes}′</span>}
          </span>
        </div>
      )}
      <Handle id="bottom" type="source" position={Position.Bottom} className="!bg-transparent !w-1 !h-1 !border-0" />
    </div>
  );
}
