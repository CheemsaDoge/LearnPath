import { BookOpen, Download, FileUp, Loader2, LogIn, Plus, Sparkles, Trash2, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { Footer } from "../components/Footer";
import { api, ApiError, FACT_KIND_LABEL, formatBytes, formatMinutes, formatTime } from "../lib/api";
import type { Dashboard as DashboardData, FactKind, ProfileFact } from "../lib/types";

const EVENT_ICON: Record<string, string> = { goal: "🎯", clarify: "💬", lesson: "📖", quiz: "✅", chat: "💡", cards: "🃏", upload: "📎", login: "🔐", manual: "✍️" };
const FACT_ORDER: FactKind[] = ["background", "skill", "goal", "preference", "interest", "progress", "other"];

export function Dashboard() {
  const nav = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newFact, setNewFact] = useState<{ kind: FactKind; text: string }>({ kind: "skill", text: "" });
  const [uploading, setUploading] = useState(false);
  const [tab, setTab] = useState<"paths" | "profile" | "archive" | "files">("paths");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => api.dashboard().then(setData).catch((e) => setError(e instanceof ApiError ? e.message : "加载失败"));
  useEffect(() => {
    load();
  }, []);

  const addFact = async () => {
    if (!newFact.text.trim()) return;
    await api.createFact(newFact.kind, newFact.text.trim());
    setNewFact({ ...newFact, text: "" });
    load();
  };
  const removeFact = async (f: ProfileFact) => {
    await api.deleteFact(f.id);
    load();
  };
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const f of Array.from(files)) await api.uploadAttachment(f);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (error && !data)
    return (
      <div className="flex min-h-full flex-col">
        <AppHeader />
        <p className="p-10 text-center text-rose-600">{error}</p>
      </div>
    );
  if (!data)
    return (
      <div className="flex min-h-full flex-col">
        <AppHeader />
        <div className="flex flex-1 items-center justify-center text-slate-400">
          <Loader2 className="animate-spin" />
        </div>
      </div>
    );

  const { user, stats } = data;
  const factsByKind = FACT_ORDER.map((k) => [k, data.facts.filter((f) => f.kind === k)] as const).filter(([, list]) => list.length > 0);

  return (
    <div className="flex min-h-full flex-col bg-paper">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {/* user card */}
        <section className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:flex-row md:items-center">
          {user.avatar ? <img src={user.avatar} alt="" className="h-16 w-16 rounded-full object-cover" /> : <span className="grid h-16 w-16 place-items-center rounded-full bg-brand-100 text-brand-700"><UserRound size={28} /></span>}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold">{user.name}</h1>
              {user.is_guest ? <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">访客</span> : <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">知乎账号</span>}
            </div>
            <p className="mt-0.5 text-sm text-slate-500">{user.headline || "还没有一句话介绍"}</p>
            {user.is_guest && (
              <Link to="/login?returnTo=%2Fdashboard" className="mt-2 inline-flex items-center gap-1 text-sm text-brand-600 hover:underline">
                <LogIn size={14} /> 登录知乎，把档案和学习路径保存到账号
              </Link>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 text-center md:grid-cols-4">
            {[
              ["学习路径", stats.graphs],
              ["已掌握知识点", `${stats.mastered_nodes}/${stats.learnable_nodes}`],
              ["已学时长", formatMinutes(stats.minutes_learned)],
              ["档案条目", stats.facts],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-xl bg-slate-50 px-3 py-2">
                <div className="text-lg font-bold text-ink">{value}</div>
                <div className="text-[11px] text-slate-500">{label}</div>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-6 flex gap-1 overflow-x-auto">
          {(
            [
              ["paths", "学习路径", data.graphs.length],
              ["profile", "学习档案", data.facts.length],
              ["archive", "档案馆 · 互动记录", data.events.length],
              ["files", "附件", data.attachments.length],
            ] as const
          ).map(([id, label, count]) => (
            <button key={id} onClick={() => setTab(id)} className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition ${tab === id ? "bg-ink text-white" : "bg-white text-slate-600 hover:bg-slate-100"}`}>
              {label}
              <span className={`rounded-full px-1.5 text-[11px] ${tab === id ? "bg-white/20" : "bg-slate-100"}`}>{count}</span>
            </button>
          ))}
        </div>
        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

        {tab === "paths" && (
          <section className="mt-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-bold">我的学习路径</h2>
              <button onClick={() => nav("/")} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600">
                <Plus size={15} /> 新建路径
              </button>
            </div>
            {data.graphs.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">还没有学习路径。回到首页，说一句你想学什么。</p>}
            <div className="grid gap-3 md:grid-cols-2">
              {data.graphs.map((g) => (
                <button key={g.id} onClick={() => nav(`/g/${g.id}`)} className="rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:border-brand-300 hover:shadow-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-[15px] font-semibold">{g.title || g.goal_text}</div>
                      <div className="mt-0.5 truncate text-xs text-slate-500">{g.goal_text}</div>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${g.status === "ready" ? "bg-emerald-100 text-emerald-700" : g.status === "failed" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-800"}`}>
                      {g.status === "ready" ? "可学习" : g.status === "failed" ? "生成失败" : "生成中"}
                    </span>
                  </div>
                  {g.stats && (
                    <div className="mt-3">
                      <div className="mb-1 flex justify-between text-xs text-slate-500">
                        <span>
                          已掌握 {g.stats.mastered_nodes}/{g.stats.learnable_nodes} · 剩余约 {formatMinutes(g.stats.minutes_remaining)}
                        </span>
                        <span>{Math.round(g.stats.completion * 100)}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.round(g.stats.completion * 100)}%` }} />
                      </div>
                      {g.next_actions[0] && (
                        <div className="mt-2 inline-flex items-center gap-1 text-xs text-amber-700">
                          <Sparkles size={12} /> 下一步：{g.next_actions[0].label}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="mt-2 text-[11px] text-slate-400">创建于 {formatTime(g.created_at)}</div>
                </button>
              ))}
            </div>
          </section>
        )}

        {tab === "profile" && (
          <section className="mt-4 grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <h2 className="text-lg font-bold">学习档案</h2>
              <p className="mt-1 text-sm text-slate-500">每一次澄清、提问、答题都会更新这里。它决定了路线的起点、讲解的深度和出题的方式。你可以随时补充或删除。</p>
              {factsByKind.length === 0 && <p className="mt-4 rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">档案还是空的。创建一条学习路径并回答几个问题，或在右侧手动补充。</p>}
              <div className="mt-4 space-y-4">
                {factsByKind.map(([kind, list]) => (
                  <div key={kind}>
                    <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">{FACT_KIND_LABEL[kind]}</div>
                    <ul className="space-y-1.5">
                      {list.map((f) => (
                        <li key={f.id} className="group flex items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[14px] leading-6">
                          <span className="flex-1">{f.text}</span>
                          <span className="mt-1 text-[11px] text-slate-400" title={`置信度 ${Math.round(f.confidence * 100)}%`}>
                            {{ clarify: "澄清", chat: "提问", quiz: "测验", lesson: "讲解", upload: "附件", manual: "手动", login: "登录" }[f.source] ?? f.source}
                          </span>
                          <button onClick={() => removeFact(f)} className="mt-1 text-slate-300 opacity-0 transition hover:text-rose-500 group-hover:opacity-100" aria-label="删除">
                            <X size={14} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="text-sm font-semibold">补充一条</div>
                <select value={newFact.kind} onChange={(e) => setNewFact({ ...newFact, kind: e.target.value as FactKind })} className="mt-2 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm">
                  {FACT_ORDER.filter((k) => k !== "progress").map((k) => (
                    <option key={k} value={k}>
                      {FACT_KIND_LABEL[k]}
                    </option>
                  ))}
                </select>
                <textarea value={newFact.text} onChange={(e) => setNewFact({ ...newFact, text: e.target.value })} rows={3} placeholder="例如：软件工程专业大三；会 Java 和 Spring Boot；线性代数学过但不熟" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none" />
                <button onClick={addFact} disabled={!newFact.text.trim()} className="mt-2 w-full rounded-lg bg-ink px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                  保存到档案
                </button>
              </div>
            </div>
          </section>
        )}

        {tab === "archive" && (
          <section className="mt-4">
            <h2 className="text-lg font-bold">档案馆 · 互动记录</h2>
            <p className="mt-1 text-sm text-slate-500">你在知径的每一次互动都留有记录：目标、追问、讲解、测验、卡片、上传、登录。</p>
            {data.events.length === 0 && <p className="mt-4 rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">还没有记录。</p>}
            <ol className="mt-4 space-y-2">
              {data.events.map((e) => (
                <li key={e.id} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <span className="text-lg leading-6">{EVENT_ICON[e.kind] ?? "•"}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] leading-6">{e.summary}</div>
                    <div className="mt-0.5 text-[11px] text-slate-400">
                      {formatTime(e.created_at)}
                      {e.ref_type === "graph" && (
                        <>
                          {" · "}
                          <Link to={`/g/${e.ref_id}`} className="text-brand-600 hover:underline">
                            打开路径
                          </Link>
                        </>
                      )}
                      {e.ref_type === "node" && typeof e.detail.score === "number" && ` · ${e.detail.score} 分`}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {tab === "files" && (
          <section className="mt-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold">附件</h2>
                <p className="mt-1 text-sm text-slate-500">课程大纲、考试范围、笔记、PDF。创建路径时可以选择附件，AI 会把它们作为路线骨架。</p>
              </div>
              <button onClick={() => fileRef.current?.click()} disabled={uploading} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50">
                {uploading ? <Loader2 size={15} className="animate-spin" /> : <FileUp size={15} />} 上传附件
              </button>
              <input ref={fileRef} type="file" multiple className="hidden" accept=".pdf,.txt,.md,.docx,.csv,.json,.py,.java,.tex" onChange={(e) => upload(e.target.files)} />
            </div>
            {data.attachments.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">还没有附件。</p>}
            <ul className="grid gap-2 md:grid-cols-2">
              {data.attachments.map((a) => (
                <li key={a.id} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3">
                  <BookOpen size={18} className="mt-0.5 shrink-0 text-brand-500" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] font-medium">{a.filename}</div>
                    <div className="text-[11px] text-slate-400">
                      {formatBytes(a.size)} · {a.has_text ? "已提取文字" : "未能提取文字"} · {formatTime(a.created_at)}
                    </div>
                    {a.summary && <p className="mt-1 text-xs leading-5 text-slate-500 line-clamp-2">{a.summary}</p>}
                  </div>
                  <a href={api.attachmentDownloadUrl(a.id)} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-brand-600" title="下载">
                    <Download size={15} />
                  </a>
                  <button
                    onClick={async () => {
                      await api.deleteAttachment(a.id);
                      load();
                    }}
                    className="rounded-md p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-500"
                    title="删除"
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <Footer />
    </div>
  );
}
