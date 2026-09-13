import { ExternalLink, FileText, MessageSquareQuote, RefreshCw } from "lucide-react";
import { useState } from "react";
import { api, kindLabel } from "../../lib/api";
import type { NodeDetail } from "../../lib/types";

export function SourcesTab({ node, onUpdated }: { node: NodeDetail; onUpdated: (n: NodeDetail) => void }) {
  const [busy, setBusy] = useState(false);
  const reground = async () => {
    setBusy(true);
    try {
      onUpdated(await api.regroundNode(node.id));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">
          检索词：
          {node.search_queries.map((q) => (
            <span key={q} className="ml-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
              {q}
            </span>
          ))}
        </p>
        <button onClick={reground} disabled={busy} className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline disabled:opacity-50">
          <RefreshCw size={12} className={busy ? "animate-spin" : ""} /> 重新检索
        </button>
      </div>
      {node.sources.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
          {node.grounding_status === "pending" ? "正在知乎上检索优质内容…" : "暂未找到相关的知乎内容。可以点击「重新检索」，或直接开始学习（讲解会标注缺少来源）。"}
        </div>
      )}
      <ol className="space-y-2">
        {node.sources.map((s, i) => (
          <li key={s.id} className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="flex items-start gap-2">
              <span className="cite mt-0.5">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <a href={s.url} target="_blank" rel="noreferrer" className="font-medium text-[14px] text-ink hover:text-brand-600 line-clamp-2">
                  {s.title || s.url}
                  <ExternalLink size={12} className="ml-1 inline text-slate-400" />
                </a>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                  <span className="inline-flex items-center gap-0.5 rounded bg-brand-50 px-1.5 py-0.5 text-brand-700">
                    {s.kind === "article" ? <FileText size={11} /> : <MessageSquareQuote size={11} />}
                    知乎{kindLabel(s.kind)}
                  </span>
                  {s.author && <span>{s.author}</span>}
                  {s.votes > 0 && <span>{s.votes.toLocaleString()} 赞同</span>}
                  <span className={s.has_content ? "text-emerald-600" : "text-slate-400"}>{s.has_content ? "已读取全文" : "仅摘要"}</span>
                </div>
                {s.snippet && <p className="mt-1.5 text-[13px] leading-6 text-slate-600 line-clamp-3">{s.snippet}</p>}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
