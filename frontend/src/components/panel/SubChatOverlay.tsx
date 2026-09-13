import { Loader2, MessageSquareQuote, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Citation } from "../../lib/types";
import { Markdown } from "../Markdown";
import { useTutorChat } from "./useTutorChat";

const QUICK = ["解释这句话", "举个例子", "为什么是这样？", "这和前面讲的有什么关系？"];

/** A floating, temporary sub-conversation anchored to a sentence the learner selected. No navigation: it overlays the panel. */
export function SubChatOverlay({ nodeId, threadId, quote, citations, autoAsk, onClose }: { nodeId: string; threadId: string; quote: string; citations: Citation[]; autoAsk?: string; onClose: () => void }) {
  const { messages, busy, ask } = useTutorChat(nodeId, threadId, quote);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  useEffect(() => {
    if (autoAsk && !asked.current) {
      asked.current = true;
      ask(autoAsk);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoAsk]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="pointer-events-auto fixed bottom-5 right-5 z-50 flex max-h-[70vh] w-[min(440px,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-2xl border border-brand-200 bg-white shadow-2xl">
      <div className="flex items-start gap-2 border-b border-slate-100 bg-brand-50/70 px-4 py-3">
        <MessageSquareQuote size={16} className="mt-0.5 shrink-0 text-brand-600" />
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">针对这句提问 · 临时子会话</div>
          <div className="mt-0.5 line-clamp-3 text-[13px] leading-5 text-slate-700">「{quote}」</div>
        </div>
        <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-white hover:text-slate-700" aria-label="关闭">
          <X size={16} />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-1.5">
            {QUICK.map((q) => (
              <button key={q} onClick={() => ask(q)} className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:border-brand-300 hover:text-brand-700">
                {q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[92%] rounded-2xl px-3 py-2 text-[13px] leading-6 ${m.role === "user" ? "bg-brand-500 text-white" : "bg-slate-100 text-ink"}`}>
              {m.role === "user" ? m.content : m.content ? <Markdown text={m.content} citations={citations} /> : <span className="inline-flex items-center gap-1 text-slate-500"><Loader2 size={13} className="animate-spin" /> {m.reasoning ?? "思考中…"}</span>}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
          setInput("");
        }}
        className="flex items-center gap-2 border-t border-slate-100 px-3 py-2"
      >
        <input autoFocus value={input} onChange={(e) => setInput(e.target.value)} placeholder="就这句话继续问…" className="flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-brand-400 focus:outline-none" />
        <button type="submit" disabled={busy || !input.trim()} className="rounded-lg bg-brand-500 px-2.5 py-1.5 text-white hover:bg-brand-600 disabled:opacity-50" aria-label="发送">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
        </button>
      </form>
    </div>
  );
}
