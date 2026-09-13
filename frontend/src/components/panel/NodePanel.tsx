import { BookOpen, ClipboardList, Layers, Link2, Loader2, Lock, MessageCircle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { NodeDetail, QuizResult } from "../../lib/types";
import { Stars } from "../Stars";
import { CardsTab } from "./CardsTab";
import { ChatTab } from "./ChatTab";
import { LessonTab } from "./LessonTab";
import { QuizTab } from "./QuizTab";
import { SourcesTab } from "./SourcesTab";

type Tab = "lesson" | "sources" | "quiz" | "cards" | "chat";

const TABS: { id: Tab; label: string; icon: typeof BookOpen }[] = [
  { id: "lesson", label: "讲解", icon: BookOpen },
  { id: "sources", label: "知乎来源", icon: Link2 },
  { id: "quiz", label: "小测验", icon: ClipboardList },
  { id: "cards", label: "复习卡片", icon: Layers },
  { id: "chat", label: "追问", icon: MessageCircle },
];

export function NodePanel({ nodeId, onClose, onChanged, onNavigate }: { nodeId: string; onClose: () => void; onChanged: () => void; onNavigate: (id: string) => void }) {
  const [node, setNode] = useState<NodeDetail | null>(null);
  const [tab, setTab] = useState<Tab>("lesson");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setNode(await api.getNode(nodeId));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    setNode(null);
    setTab("lesson");
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeId]);

  const refresh = async () => {
    await load();
    onChanged();
  };

  const onGraded = async (_r: QuizResult) => {
    await refresh();
  };

  if (error) return <div className="p-6 text-sm text-rose-600">{error}</div>;
  if (!node)
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        <Loader2 className="animate-spin" />
      </div>
    );

  const isModule = node.node_type === "module";
  const blocking = node.prerequisites.filter((p) => !p.satisfied);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-5 pb-3 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
              <span className={`rounded px-1.5 py-0.5 font-medium ${node.node_type === "practice" ? "bg-emerald-100 text-emerald-700" : isModule ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-700"}`}>
                {node.node_type === "practice" ? "练习" : isModule ? "模块" : "知识点"}
              </span>
              <span>难度 {"●".repeat(node.difficulty)}{"○".repeat(5 - node.difficulty)}</span>
              <span>约 {node.est_minutes} 分钟</span>
              {node.attempts > 0 && <span>已练 {node.attempts} 次</span>}
            </div>
            <h2 className="mt-1 text-lg font-bold leading-snug">{node.label}</h2>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>
        <p className="mt-1.5 text-[13px] leading-6 text-slate-600">{node.description}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            掌握度 <Stars value={node.mastery_stars} />
            {node.attempts > 0 && <span>({node.mastery_score.toFixed(0)} 分)</span>}
          </span>
          {blocking.length > 0 && (
            <span className="inline-flex items-center gap-1 text-amber-600">
              <Lock size={11} /> 建议先学
              {blocking.map((p) => (
                <button key={p.id} onClick={() => onNavigate(p.id)} className="underline decoration-amber-300 underline-offset-2 hover:text-amber-700">
                  {p.label}
                </button>
              ))}
            </span>
          )}
        </div>
        <div className="mt-3 flex gap-1 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium transition ${tab === id ? "bg-ink text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            >
              <Icon size={13} /> {label}
              {id === "sources" && node.sources.length > 0 && <span className="ml-0.5 rounded-full bg-white/20 px-1 text-[10px]">{node.sources.length}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {tab === "lesson" && <LessonTab node={node} onLearned={refresh} />}
        {tab === "sources" && <SourcesTab node={node} onUpdated={(n) => { setNode(n); onChanged(); }} />}
        {tab === "quiz" && <QuizTab node={node} onGraded={onGraded} />}
        {tab === "cards" && <CardsTab node={node} />}
        {tab === "chat" && <ChatTab node={node} onAsked={refresh} />}
      </div>
    </div>
  );
}
