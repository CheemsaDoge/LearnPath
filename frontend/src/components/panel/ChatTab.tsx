import { Loader2, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, streamSSE } from "../../lib/api";
import type { Citation, ChatMessage, NodeDetail } from "../../lib/types";
import { Markdown } from "../Markdown";

interface LocalMsg {
  role: "user" | "assistant";
  content: string;
  engine?: "tutor" | "zhida";
  reasoning?: string;
}

export function ChatTab({ node, onAsked }: { node: NodeDetail; onAsked: () => void }) {
  const [messages, setMessages] = useState<LocalMsg[]>(node.chat.map((m: ChatMessage) => ({ role: m.role, content: m.content })));
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState<"tutor" | "zhida">("tutor");
  const [zhidaAvailable, setZhidaAvailable] = useState(false);
  const citations: Citation[] = node.sources.map((s, i) => ({ index: i + 1, title: s.title, url: s.url, kind: s.kind, source_id: s.id }));
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(node.chat.map((m) => ({ role: m.role, content: m.content })));
  }, [node.id]);

  useEffect(() => {
    api.health().then((h) => setZhidaAvailable(Boolean(h.zhida))).catch(() => setZhidaAvailable(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", engine }]);
    const patchLast = (fn: (last: LocalMsg) => LocalMsg) =>
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = fn(copy[copy.length - 1]);
        return copy;
      });
    const run = (attempt: number): Promise<void> =>
      streamSSE(`/nodes/${node.id}/chat`, { question: q, mode: engine }, {
        onMeta: (meta) => {
          if (typeof meta.reasoning === "string") patchLast((last) => ({ ...last, reasoning: (last.reasoning ?? "") + meta.reasoning }));
        },
        onStatus: (t) => patchLast((last) => ({ ...last, reasoning: t })),
        onDelta: (d) => patchLast((last) => ({ ...last, content: last.content + d })),
        onDone: () => onAsked(),
        onError: async (msg) => {
          if (attempt < 2) {
            patchLast((last) => ({ ...last, reasoning: "连接波动，正在重试…" }));
            await new Promise((r) => setTimeout(r, 1000));
            return run(attempt + 1);
          }
          patchLast((last) => ({ ...last, content: last.content || "抱歉，这次没能连上 AI 服务。你可以稍后再问一次，或先看右侧「知乎来源」。" }));
          setError(msg);
        },
      });
    await run(1);
    setBusy(false);
  };

  const suggestions = [`「${node.label}」最容易被误解的地方是什么？`, "能举一个生活中的例子吗？", "它和前一个知识点有什么关系？"];

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
            围绕这个知识点提问，回答会引用右侧的知乎来源。试试：
            <div className="mt-2 flex flex-wrap gap-1.5">
              {suggestions.map((s) => (
                <button key={s} onClick={() => ask(s)} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-brand-300 hover:text-brand-700">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[92%] rounded-2xl px-3.5 py-2 text-[13px] leading-6 ${m.role === "user" ? "bg-brand-500 text-white" : "bg-slate-100 text-ink"}`}>
              {m.role === "assistant" && m.engine === "zhida" && <div className="mb-1 text-[11px] font-medium text-brand-600">知乎直答</div>}
              {m.role === "user" ? m.content : m.content ? <Markdown text={m.content} citations={citations} /> : m.reasoning ? <span className="text-slate-500">{m.reasoning.slice(-160)}</span> : <Loader2 size={14} className="animate-spin text-slate-400" />}
            </div>
          </div>
        ))}
        {error && <p className="text-xs text-slate-400">（{error}）</p>}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="mt-3 flex items-center gap-2 border-t border-slate-200 pt-3"
      >
        {zhidaAvailable && (
          <div className="flex shrink-0 rounded-lg border border-slate-200 p-0.5 text-[11px]">
            {(["tutor", "zhida"] as const).map((e) => (
              <button key={e} type="button" onClick={() => setEngine(e)} className={`rounded-md px-2 py-1 ${engine === e ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100"}`} title={e === "tutor" ? "基于本知识点的知乎来源作答" : "调用知乎直答（知乎官方 AI 搜索）"}>
                {e === "tutor" ? "导师" : "直答"}
              </button>
            ))}
          </div>
        )}
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="问一个关于这个知识点的问题…" className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none" />
        <button type="submit" disabled={busy || !input.trim()} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-2 text-sm text-white hover:bg-brand-600 disabled:opacity-50">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
        </button>
      </form>
    </div>
  );
}
