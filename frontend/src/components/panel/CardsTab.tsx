import { Layers, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { Card, NodeDetail } from "../../lib/types";

export function CardsTab({ node }: { node: NodeDetail }) {
  const [cards, setCards] = useState<Card[] | null>(node.cards);
  const [flipped, setFlipped] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCards(node.cards);
    setFlipped(new Set());
  }, [node.id, node.cards]);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      setCards((await api.createCards(node.id)).cards);
      setFlipped(new Set());
    } catch (e) {
      setError(e instanceof ApiError && e.status !== 0 ? "生成卡片时遇到问题，请再试一次。" : "网络不稳定，请再试一次。");
    } finally {
      setBusy(false);
    }
  };

  if (!cards) {
    return (
      <div className="rounded-xl border border-dashed border-violet-200 bg-violet-50/50 p-6 text-center">
        <p className="text-sm text-slate-600 leading-6">一键把这个知识点的知乎高赞内容，压缩成 5-8 张复习卡片。点击卡片翻面。</p>
        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        <button onClick={generate} disabled={busy} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-60">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Layers size={15} />} 生成复习卡片
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-slate-500">{cards.length} 张卡片 · 点击翻面</span>
        <button onClick={generate} disabled={busy} className="inline-flex items-center gap-1 text-xs text-violet-700 hover:underline disabled:opacity-50">
          {busy ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} 重新生成
        </button>
      </div>
      {error && <p className="mb-2 text-sm text-rose-600">{error}</p>}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {cards.map((c, i) => {
          const isFlipped = flipped.has(i);
          return (
            <button
              key={i}
              onClick={() =>
                setFlipped((s) => {
                  const n = new Set(s);
                  if (n.has(i)) n.delete(i);
                  else n.add(i);
                  return n;
                })
              }
              className={`min-h-[120px] rounded-xl border p-4 text-left text-[13px] leading-6 transition ${isFlipped ? "border-violet-300 bg-violet-50" : "border-slate-200 bg-white hover:border-violet-300"}`}
            >
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{isFlipped ? "答案" : `卡片 ${i + 1}`}</div>
              <div className={isFlipped ? "text-slate-800" : "font-medium text-ink"}>{isFlipped ? c.back : c.front}</div>
              {isFlipped && c.source_index > 0 && node.sources[c.source_index - 1] && (
                <a href={node.sources[c.source_index - 1].url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="mt-2 inline-block text-[11px] text-brand-600 hover:underline">
                  来源 [{c.source_index}] {node.sources[c.source_index - 1].title}
                </a>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
