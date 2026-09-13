import { AlertTriangle, ChevronRight, Download, LayoutDashboard, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { AuthMenu } from "../components/AuthMenu";
import { Logo } from "../components/Logo";
import { NodePanel } from "../components/panel/NodePanel";
import { api, ApiError, formatMinutes, rememberGraph } from "../lib/api";
import type { Graph } from "../lib/types";

const STEP_TEXT: Record<string, string> = {
  plan: "正在理解你的目标，规划知识图谱…",
  search: "正在知乎上为每个知识点检索优质内容…",
  read: "正在读取高赞回答与专栏全文…",
  ready: "完成",
};

export function GraphPage() {
  const { graphId = "" } = useParams();
  const nav = useNavigate();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [autoRetrying, setAutoRetrying] = useState(false);
  const timer = useRef<number | null>(null);
  const failures = useRef(0);
  const autoRetried = useRef(false);

  const load = useCallback(async () => {
    try {
      const g = await api.getGraph(graphId);
      setGraph(g);
      setError(null);
      failures.current = 0;
      return g;
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      failures.current += 1;
      // a 404 is final; anything else is treated as transient and polled again before we show an error page
      if (status === 404 || failures.current >= 6) setError(status === 404 ? "这条学习路径不存在或已被删除" : "服务暂时不可用，请稍后刷新页面");
      return null;
    }
  }, [graphId]);

  const startPolling = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    const tick = async () => {
      const g = await load();
      const busy = !g || g.status === "generating" || g.status === "grounding";
      if (g && g.status === "failed" && !autoRetried.current) {
        // silent, one-time automatic retry — the user should not have to press a button for a transient failure
        autoRetried.current = true;
        setAutoRetrying(true);
        try {
          await api.retryGraph(graphId);
        } catch {
          /* fall through to polling; the banner will show the error */
        }
        timer.current = window.setTimeout(tick, 1500);
        return;
      }
      if (g && g.status !== "failed") setAutoRetrying(false);
      if (busy && failures.current < 6) timer.current = window.setTimeout(tick, g ? 1500 : 2500);
    };
    tick();
  }, [graphId, load]);

  useEffect(() => {
    rememberGraph(graphId);
    failures.current = 0;
    autoRetried.current = false;
    startPolling();
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [graphId, startPolling]);

  const retry = async () => {
    setSelected(null);
    setAutoRetrying(true);
    try {
      await api.retryGraph(graphId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "重试失败");
      return;
    }
    autoRetried.current = true;
    startPolling();
  };

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-500">
        <AlertTriangle className="text-rose-500" />
        <p>{error}</p>
        <button onClick={() => nav("/")} className="text-brand-600 underline">
          返回首页
        </button>
      </div>
    );
  }
  if (!graph)
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        <Loader2 className="animate-spin" />
      </div>
    );

  const generating = graph.status === "generating" || (graph.status === "failed" && autoRetrying);
  const grounding = graph.status === "grounding";
  const failed = graph.status === "failed" && !autoRetrying;
  const progress = graph.progress ?? {};
  const pct = progress.total ? Math.round(((progress.done ?? 0) / progress.total) * 100) : 0;
  const stats = graph.stats;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-2.5">
        <Logo />
        <ChevronRight size={16} className="text-slate-300" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] font-semibold">{graph.title || graph.goal_text}</div>
          <div className="truncate text-xs text-slate-500">{graph.goal_text}</div>
        </div>
        {stats && (
          <div className="hidden items-center gap-4 text-xs text-slate-600 md:flex">
            <div className="w-40">
              <div className="mb-1 flex justify-between">
                <span>
                  已掌握 {stats.mastered_nodes}/{stats.learnable_nodes}
                </span>
                <span>{Math.round(stats.completion * 100)}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${Math.round(stats.completion * 100)}%` }} />
              </div>
            </div>
            <span>剩余约 {formatMinutes(stats.minutes_remaining)}</span>
          </div>
        )}
        <a href={api.exportUrl(graph.id)} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-700 hover:border-brand-300 hover:text-brand-700" title="导出 Markdown 学习清单">
          <Download size={14} /> 导出
        </a>
        <Link to="/dashboard" className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-700 hover:border-brand-300 hover:text-brand-700" title="控制台">
          <LayoutDashboard size={14} /> 控制台
        </Link>
        <AuthMenu />
      </header>

      {(generating || grounding || failed) && (
        <div className={`flex items-center gap-3 px-4 py-2 text-sm ${failed ? "bg-rose-50 text-rose-700" : "bg-brand-50 text-brand-800"}`}>
          {failed ? <AlertTriangle size={16} /> : <Loader2 size={16} className="animate-spin" />}
          <span className="flex-1 truncate">{failed ? "生成遇到问题，已自动重试仍未成功。可以再试一次，或换一种说法描述目标。" : autoRetrying && graph.status === "failed" ? "生成遇到波动，正在自动重试…" : STEP_TEXT[progress.step ?? "plan"] ?? "处理中…"}</span>
          {!failed && progress.total ? <span className="text-xs">{pct}%</span> : null}
          {failed && (
            <button onClick={retry} className="inline-flex items-center gap-1 rounded-md border border-rose-300 px-2 py-1 text-xs hover:bg-rose-100">
              <RefreshCw size={12} /> 重试
            </button>
          )}
        </div>
      )}

      {graph.degraded && graph.status === "ready" && (
        <div className="flex items-center gap-3 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          <Sparkles size={16} />
          <span className="flex-1 truncate">AI 服务刚才有波动，这是自动生成的基础路线；知乎来源是真实的。想要完整的个性化路线可以重新生成。</span>
          <button onClick={retry} className="inline-flex items-center gap-1 rounded-md border border-amber-300 px-2 py-1 text-xs hover:bg-amber-100">
            <RefreshCw size={12} /> 重新生成
          </button>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          {graph.nodes.length > 0 ? (
            <GraphCanvas graph={graph} selectedId={selected} onSelect={setSelected} viewportKey={selected ? "panel" : "full"} />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-400">
              {!failed && <Loader2 className="animate-spin" />}
              <p className="text-sm">{failed ? "没有生成任何节点" : "正在生成知识图谱，通常需要 1-3 分钟…"}</p>
            </div>
          )}
          {graph.summary && !selected && graph.nodes.length > 0 && (
            <div className="pointer-events-none absolute left-4 top-4 max-w-md rounded-xl border border-slate-200 bg-white/95 p-4 shadow-sm backdrop-blur">
              <div className="text-xs font-semibold text-slate-500">路线总览</div>
              <p className="mt-1 text-[13px] leading-6 text-slate-700">{graph.summary}</p>
              {graph.learner_profile && <p className="mt-1 text-xs text-slate-500">{graph.learner_profile}</p>}
            </div>
          )}
          {graph.next_actions.length > 0 && (
            <div className="absolute bottom-4 left-1/2 flex max-w-[92%] -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full border border-amber-200 bg-white/95 px-3 py-1.5 text-xs shadow-sm backdrop-blur">
              <Sparkles size={14} className="shrink-0 text-amber-500" />
              <span className="shrink-0 text-slate-500">下一步</span>
              {graph.next_actions.slice(0, selected ? 1 : 2).map((a, i) => (
                <button key={a.node_id} onClick={() => setSelected(a.node_id)} className="max-w-[26rem] truncate rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-800 hover:bg-amber-100" title={a.reason}>
                  {a.label}
                  {i === 0 && <span className="font-normal text-amber-600"> · {a.reason}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
        {selected && (
          <aside className="w-[440px] shrink-0 border-l border-slate-200 bg-white xl:w-[520px]">
            <NodePanel nodeId={selected} onClose={() => setSelected(null)} onChanged={load} onNavigate={setSelected} />
          </aside>
        )}
      </div>
    </div>
  );
}
