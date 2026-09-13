import { Loader2, RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { streamSSE } from "../../lib/api";
import type { Citation, NodeDetail } from "../../lib/types";
import { Markdown } from "../Markdown";

export function LessonTab({ node, onLearned }: { node: NodeDetail; onLearned: () => void }) {
  const [text, setText] = useState(node.lesson?.content_md ?? "");
  const [citations, setCitations] = useState<Citation[]>(node.lesson?.citations ?? []);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setText(node.lesson?.content_md ?? "");
    setCitations(node.lesson?.citations ?? []);
    setError(null);
  }, [node.id, node.lesson?.id]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const generate = async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStreaming(true);
    setError(null);
    setText("");
    await streamSSE(
      `/nodes/${node.id}/lesson`,
      undefined,
      {
        onMeta: (m) => Array.isArray(m.citations) && setCitations(m.citations as Citation[]),
        onDelta: (d) => setText((t) => t + d),
        onDone: () => {
          setStreaming(false);
          onLearned();
        },
        onError: (msg) => {
          setError(msg);
          setStreaming(false);
        },
      },
      ctrl.signal,
    );
    setStreaming(false);
  };

  if (!text && !streaming) {
    return (
      <div className="rounded-xl border border-dashed border-brand-200 bg-brand-50/50 p-6 text-center">
        <p className="text-sm text-slate-600 leading-6">
          基于右侧 <b>{node.sources.length}</b> 篇知乎来源，为你生成一份带引用的讲解：定义 → 直觉 → 要点 → 误区 → 观点对照 → 自检。
        </p>
        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        <button onClick={generate} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600">
          <Sparkles size={15} /> 开始学习这个知识点
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-slate-500">{streaming ? "正在基于知乎来源生成讲解…" : `讲解引用了 ${citations.length} 篇知乎来源，点击角标可跳转`}</span>
        <button onClick={generate} disabled={streaming} className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline disabled:opacity-50">
          {streaming ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} 重新生成
        </button>
      </div>
      {error && <p className="mb-2 text-sm text-rose-600">{error}</p>}
      <Markdown text={text} citations={citations} />
      {streaming && <span className="inline-block h-4 w-1.5 animate-pulse-soft bg-brand-500 align-middle" />}
      {citations.length > 0 && !streaming && (
        <div className="mt-5 border-t border-slate-200 pt-3">
          <p className="mb-1 text-xs font-semibold text-slate-500">引用来源</p>
          <ol className="space-y-1">
            {citations.map((c) => (
              <li key={c.index} className="text-[13px] text-slate-600">
                <span className="cite">{c.index}</span>
                <a href={c.url} target="_blank" rel="noreferrer" className="hover:text-brand-600">
                  {c.title}
                </a>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
