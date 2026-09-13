import { Loader2, MessageCircleQuestion, RefreshCw, Send, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, streamSSE } from "../../lib/api";
import type { Citation, NodeDetail } from "../../lib/types";
import { Markdown } from "../Markdown";
import { SubChatOverlay } from "./SubChatOverlay";
import { useTutorChat } from "./useTutorChat";

/** Split a streamed Markdown lesson into tutor "turns" at second-level headings so it reads like a conversation. */
function splitLesson(md: string): string[] {
  const parts = md.split(/\n(?=## )/g).map((p) => p.trim()).filter(Boolean);
  return parts.length ? parts : md ? [md] : [];
}

interface SelectionState {
  text: string;
  x: number;
  y: number;
}

/** Turn a DOM selection into clean text: KaTeX renders MathML + HTML twice, so replace each formula with its TeX source. */
function selectionToText(range: Range): string {
  const fragment = range.cloneContents();
  fragment.querySelectorAll(".katex-display, .katex").forEach((el) => {
    if (el.parentElement?.closest(".katex")) return; // nested: handled by the outer element
    const tex = el.querySelector('annotation[encoding="application/x-tex"]')?.textContent?.trim() ?? "";
    const display = el.classList.contains("katex-display");
    el.replaceWith(document.createTextNode(tex ? (display ? ` $$${tex}$$ ` : ` $${tex}$ `) : ""));
  });
  return (fragment.textContent ?? "").replace(/\s+/g, " ").trim();
}

/**
 * 讲解 = 对话：导师分段发言（流式），学习者在同一线程继续追问；划选任意一句可弹出「解释这句 / 提问」，
 * 在叠加的悬浮窗里开一个临时子会话（独立线程，不跳转）。
 */
export function ConversationTab({ node, onLearned }: { node: NodeDetail; onLearned: () => void }) {
  const [lesson, setLesson] = useState(node.lesson?.content_md ?? "");
  const [citations, setCitations] = useState<Citation[]>(node.lesson?.citations ?? []);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [degraded, setDegraded] = useState(false);
  const [engine, setEngine] = useState<"tutor" | "zhida">("tutor");
  const [zhidaAvailable, setZhidaAvailable] = useState(false);
  const [input, setInput] = useState("");
  const [selection, setSelection] = useState<SelectionState | null>(null);
  const [sub, setSub] = useState<{ threadId: string; quote: string; autoAsk?: string } | null>(null);
  const chat = useTutorChat(node.id, "main");
  const abortRef = useRef<AbortController | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // hydrate from server state when the node changes
  useEffect(() => {
    setLesson(node.lesson?.content_md ?? "");
    setCitations(node.lesson?.citations ?? []);
    chat.setMessages(node.chat.map((m) => ({ id: m.id, role: m.role, content: m.content })));
    setSub(null);
    setSelection(null);
    setStatus(null);
    setDegraded(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.id, node.lesson?.id]);

  useEffect(() => {
    api.health().then((h) => setZhidaAvailable(Boolean(h.zhida))).catch(() => setZhidaAvailable(false));
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    if (chat.messages.length) bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat.messages]);

  const turns = useMemo(() => splitLesson(lesson), [lesson]);
  const allCitations = citations.length ? citations : node.sources.map((s, i) => ({ index: i + 1, title: s.title, url: s.url, kind: s.kind, source_id: s.id }));

  const generate = async (attempt = 1) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStreaming(true);
    setStatus(null);
    setDegraded(false);
    setLesson("");
    let got = false;
    await streamSSE(
      `/nodes/${node.id}/lesson`,
      undefined,
      {
        onMeta: (m) => Array.isArray(m.citations) && setCitations(m.citations as Citation[]),
        onStatus: (t) => setStatus(t),
        onDelta: (d) => {
          got = true;
          setStatus(null);
          setLesson((t) => t + d);
        },
        onDone: (m) => {
          setStreaming(false);
          setDegraded(Boolean(m.degraded));
          onLearned();
        },
        onError: (msg) => {
          if (!got && attempt < 2 && !ctrl.signal.aborted) {
            setStatus("连接波动，正在重新生成…");
            window.setTimeout(() => generate(attempt + 1), 1200);
            return;
          }
          setStatus(got ? "讲解在中途中断了，已保留已生成的部分。" : msg);
          setStreaming(false);
        },
      },
      ctrl.signal,
    );
    setStreaming(false);
  };

  // ---- text selection → floating "解释这句 / 提问" popover
  const onMouseUp = useCallback(() => {
    window.setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !containerRef.current || !containerRef.current.contains(sel.anchorNode)) {
        setSelection(null);
        return;
      }
      const text = selectionToText(sel.getRangeAt(0));
      if (text.length < 4) {
        setSelection(null);
        return;
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      const host = containerRef.current.getBoundingClientRect();
      setSelection({ text: text.slice(0, 500), x: Math.min(Math.max(rect.left + rect.width / 2 - host.left, 90), host.width - 90), y: rect.top - host.top + containerRef.current.scrollTop });
    }, 0);
  }, []);

  const openSub = (autoAsk?: string) => {
    if (!selection) return;
    setSub({ threadId: `sel_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, quote: selection.text, autoAsk });
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  };

  const suggestions = [`「${node.label}」最容易被误解的地方是什么？`, "能再举一个生活中的例子吗？", "它和前一个知识点有什么关系？"];

  return (
    <div className="relative flex h-full flex-col">
      <div ref={containerRef} onMouseUp={onMouseUp} onKeyUp={onMouseUp} className="relative min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {/* selection popover */}
        {selection && !sub && (
          <div className="absolute z-30 -translate-x-1/2 -translate-y-full" style={{ left: selection.x, top: Math.max(selection.y - 6, 0) }}>
            <div className="flex items-center gap-1 rounded-full border border-brand-200 bg-white p-1 shadow-lg">
              <button onMouseDown={(e) => e.preventDefault()} onClick={() => openSub("请解释这句话的意思，以及它在这个知识点里的作用。")} className="rounded-full bg-brand-500 px-3 py-1 text-xs font-medium text-white hover:bg-brand-600">
                解释这句
              </button>
              <button onMouseDown={(e) => e.preventDefault()} onClick={() => openSub()} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50">
                <MessageCircleQuestion size={13} /> 提问
              </button>
            </div>
          </div>
        )}

        {!lesson && !streaming && !status && (
          <div className="rounded-xl border border-dashed border-brand-200 bg-brand-50/50 p-6 text-center">
            <p className="text-sm leading-6 text-slate-600">
              导师会基于 <b>{node.sources.length}</b> 篇知乎来源，用对话的方式一段段讲给你听：定义 → 直觉 → 要点 → 误区 → 观点对照 → 自检。讲到一半随时可以插话，划选任何一句可以单独追问。
            </p>
            <button onClick={() => generate()} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600">
              <Sparkles size={15} /> 开始学习这个知识点
            </button>
          </div>
        )}

        {(lesson || streaming || status) && (
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs text-slate-500">{status ?? (streaming ? "导师正在讲解…" : degraded ? "AI 刚才有波动，这是临时版本；可重新生成" : `讲解引用了 ${citations.length} 篇知乎来源 · 划选任意一句可单独追问`)}</span>
            <button onClick={() => generate()} disabled={streaming} className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline disabled:opacity-50">
              {streaming ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} 重新讲解
            </button>
          </div>
        )}

        {turns.map((turn, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-500 text-[11px] font-bold text-white">师</span>
            <div className="min-w-0 max-w-[94%] rounded-2xl rounded-tl-sm bg-white px-4 py-2.5 shadow-sm ring-1 ring-slate-200">
              <Markdown text={turn} citations={allCitations} />
              {streaming && i === turns.length - 1 && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse-soft bg-brand-500 align-middle" />}
            </div>
          </div>
        ))}

        {chat.messages.map((m) => (
          <div key={m.id} className={`flex items-start gap-2 ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "assistant" && <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-500 text-[11px] font-bold text-white">{m.engine === "zhida" ? "知" : "师"}</span>}
            <div className={`min-w-0 max-w-[88%] rounded-2xl px-4 py-2.5 text-[14px] leading-6 ${m.role === "user" ? "rounded-tr-sm bg-brand-500 text-white" : "rounded-tl-sm bg-white shadow-sm ring-1 ring-slate-200"}`}>
              {m.role === "assistant" && m.engine === "zhida" && <div className="mb-1 text-[11px] font-medium text-brand-600">知乎直答</div>}
              {m.role === "user" ? m.content : m.content ? <Markdown text={m.content} citations={allCitations} /> : <span className="inline-flex items-center gap-1 text-slate-500"><Loader2 size={13} className="animate-spin" /> {m.reasoning ?? "思考中…"}</span>}
            </div>
          </div>
        ))}

        {lesson && !streaming && chat.messages.length === 0 && (
          <div className="flex flex-wrap gap-1.5 pl-9">
            {suggestions.map((sug) => (
              <button key={sug} onClick={() => chat.ask(sug, engine, onLearned)} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-brand-300 hover:text-brand-700">
                {sug}
              </button>
            ))}
          </div>
        )}
        {chat.note && <p className="pl-9 text-xs text-slate-400">（{chat.note}）</p>}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          chat.ask(input, engine, onLearned);
          setInput("");
        }}
        className="mt-3 flex items-center gap-2 border-t border-slate-200 pt-3"
      >
        {zhidaAvailable && (
          <div className="flex shrink-0 rounded-lg border border-slate-200 p-0.5 text-[11px]">
            {(["tutor", "zhida"] as const).map((e) => (
              <button key={e} type="button" onClick={() => setEngine(e)} className={`rounded-md px-2 py-1 ${engine === e ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100"}`} title={e === "tutor" ? "导师：基于本知识点的知乎来源作答" : "知乎直答：知乎官方 AI 搜索"}>
                {e === "tutor" ? "导师" : "直答"}
              </button>
            ))}
          </div>
        )}
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={lesson ? "接着问导师…" : "也可以先直接提问…"} className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none" />
        <button type="submit" disabled={chat.busy || !input.trim()} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-2 text-sm text-white hover:bg-brand-600 disabled:opacity-50" aria-label="发送">
          {chat.busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
        </button>
      </form>

      {sub && <SubChatOverlay nodeId={node.id} threadId={sub.threadId} quote={sub.quote} citations={allCitations} autoAsk={sub.autoAsk} onClose={() => setSub(null)} />}
    </div>
  );
}
