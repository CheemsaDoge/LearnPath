import { ArrowRight, Flame, Loader2, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { api, ApiError, rememberGraph } from "../lib/api";
import type { Graph, Health, HotItem } from "../lib/types";

const BACKGROUNDS = ["零基础", "有一点基础", "有相关经验，想进阶"];
const BUDGETS = ["1 周内速通", "每天 1 小时，1 个月", "每周末，3 个月"];
const EXAMPLES = [
  "我想搞懂 Transformer，能读懂论文和源码",
  "面试前系统复习操作系统的进程与内存管理",
  "零基础学会用 Python 做数据分析",
  "理解宏观经济学里的通胀与利率是怎么回事",
  "复变函数期末：留数定理与围道积分",
];

export function Home() {
  const nav = useNavigate();
  const [goal, setGoal] = useState("");
  const [background, setBackground] = useState(BACKGROUNDS[0]);
  const [budget, setBudget] = useState(BUDGETS[1]);
  const [purpose, setPurpose] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hot, setHot] = useState<HotItem[] | null>(null);
  const [recent, setRecent] = useState<Graph[]>([]);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api.hot().then(setHot).catch(() => setHot([]));
    api.listGraphs().then(setRecent).catch(() => setRecent([]));
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const submit = async (text = goal, extraPurpose = purpose) => {
    const g = text.trim();
    if (g.length < 2 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createGoal({ goal: g, background, time_budget: budget, purpose: extraPurpose });
      rememberGraph(created.graph_id);
      nav(`/g/${created.graph_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "创建失败，请稍后重试");
      setBusy(false);
    }
  };

  const learnHot = (item: HotItem) => {
    setGoal(`我想系统理解这个热点背后的知识：${item.title}`);
    submit(`我想系统理解这个热点背后的知识：${item.title}`, `知乎热榜话题（${item.heat}）：${item.excerpt.slice(0, 200)}`);
  };

  const remove = async (id: string) => {
    await api.deleteGraph(id);
    setRecent((r) => r.filter((g) => g.id !== id));
  };

  return (
    <div className="min-h-full">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Logo />
        <div className="flex items-center gap-3 text-xs text-slate-500">
          {health && (
            <span className={`rounded-full px-2 py-0.5 ${health.llm_provider === "mock" ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>
              {health.llm_provider === "mock" ? "离线演示模式" : `模型：${health.llm_model}`}
            </span>
          )}
          <a href="https://github.com/SunnyBoy-y/LearnGraph" target="_blank" rel="noreferrer" className="hover:text-brand-600">
            灵感来自 LearnGraph
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20">
        <section className="pt-8 pb-10 text-center">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
            <Sparkles size={13} /> 知乎黑客松 2026 · 学习工具与知识生产
          </div>
          <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            把知乎的高赞回答，
            <br className="sm:hidden" />
            变成<span className="text-brand-500">你的学习路径</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-[15px] leading-7 text-slate-600">
            说出一个真实的学习目标，知径会为你生成一张可视化的知识图谱；每个知识点都关联知乎上的优质讨论，
            并基于这些来源生成带引用的讲解、小测验、复习卡片，用证据追踪你的掌握程度，推荐下一步。
          </p>
        </section>

        <section className="mx-auto max-w-3xl rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
            }}
            rows={3}
            placeholder="例如：我想在一个月内搞懂 Transformer，能读懂论文并跑通一个小实验"
            className="w-full resize-none rounded-xl border border-slate-200 px-4 py-3 text-[15px] leading-7 focus:border-brand-400 focus:outline-none"
          />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-xs font-medium text-slate-500">我的基础</div>
              <div className="flex flex-wrap gap-1.5">
                {BACKGROUNDS.map((b) => (
                  <button key={b} onClick={() => setBackground(b)} className={`rounded-full border px-3 py-1 text-xs transition ${background === b ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>
                    {b}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-slate-500">时间预算</div>
              <div className="flex flex-wrap gap-1.5">
                {BUDGETS.map((b) => (
                  <button key={b} onClick={() => setBudget(b)} className={`rounded-full border px-3 py-1 text-xs transition ${budget === b ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>
                    {b}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="为什么学？（可选：期末考试 / 面试 / 工作需要 / 纯好奇）" className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none" />
          {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
          <div className="mt-4 flex items-center justify-between">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.slice(0, 3).map((ex) => (
                <button key={ex} onClick={() => setGoal(ex)} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-200">
                  {ex}
                </button>
              ))}
            </div>
            <button onClick={() => submit()} disabled={busy || goal.trim().length < 2} className="inline-flex items-center gap-1.5 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-600 disabled:opacity-50">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />} 生成我的学习路径
            </button>
          </div>
        </section>

        <section className="mt-12 grid gap-8 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <div className="mb-3 flex items-center gap-2">
              <Flame size={18} className="text-orange-500" />
              <h2 className="text-lg font-bold">今日知乎热榜 · 学点热点背后的知识</h2>
            </div>
            <p className="mb-3 text-sm text-slate-500">点一个热点，知径会识别理解它所需要的知识领域，生成一条学习路线。</p>
            {hot === null && <Loader2 className="animate-spin text-slate-400" />}
            {hot && hot.length === 0 && <p className="text-sm text-slate-400">热榜暂时不可用。</p>}
            <ol className="space-y-2">
              {hot?.slice(0, 8).map((item, i) => (
                <li key={item.id} className="group flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 transition hover:border-brand-300">
                  <span className={`mt-0.5 w-5 text-center text-sm font-bold ${i < 3 ? "text-orange-500" : "text-slate-400"}`}>{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-medium leading-6 line-clamp-2">{item.title}</div>
                    <div className="mt-0.5 text-xs text-slate-400">
                      {item.heat} · {item.answer_count} 回答 ·{" "}
                      <a href={item.url} target="_blank" rel="noreferrer" className="hover:text-brand-600">
                        去知乎看
                      </a>
                    </div>
                  </div>
                  <button onClick={() => learnHot(item)} disabled={busy} className="shrink-0 rounded-lg border border-brand-200 px-2.5 py-1 text-xs text-brand-700 opacity-80 transition group-hover:opacity-100 hover:bg-brand-50">
                    学背后的知识
                  </button>
                </li>
              ))}
            </ol>
          </div>
          <div className="lg:col-span-2">
            <h2 className="mb-3 text-lg font-bold">我的学习路径</h2>
            {recent.length === 0 && <p className="text-sm text-slate-400">还没有学习路径。从上面输入一个目标开始吧。</p>}
            <ul className="space-y-2">
              {recent.map((g) => (
                <li key={g.id} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 hover:border-brand-300">
                  <button onClick={() => nav(`/g/${g.id}`)} className="min-w-0 flex-1 text-left">
                    <div className="truncate text-[14px] font-medium">{g.title || g.goal_text}</div>
                    <div className="mt-0.5 text-xs text-slate-400">
                      {g.status === "ready" && g.stats ? `${g.stats.mastered_nodes}/${g.stats.learnable_nodes} 已掌握 · 剩余约 ${Math.round(g.stats.minutes_remaining / 60)} 小时` : g.status === "failed" ? "生成失败" : "生成中…"}
                    </div>
                  </button>
                  <button onClick={() => remove(g.id)} className="rounded-md p-1 text-slate-300 hover:bg-rose-50 hover:text-rose-500" aria-label="删除">
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mt-16 grid gap-4 sm:grid-cols-3">
          {[
            ["目标 → 图谱", "一句话目标，生成模块化的知识图谱与前置关系，按你的基础和时间预算裁剪。"],
            ["知乎来源锚定", "每个知识点自动关联知乎高赞回答与专栏，讲解逐句引用，观点对照可回溯。"],
            ["证据驱动掌握度", "小测验 + 费曼解释评分，形成证据链，更新星级，推荐你下一步该学什么。"],
          ].map(([t, d]) => (
            <div key={t} className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="text-[15px] font-semibold">{t}</div>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-600">{d}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
