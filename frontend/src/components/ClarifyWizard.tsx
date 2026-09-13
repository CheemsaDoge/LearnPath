import { ArrowRight, FileUp, Loader2, Paperclip, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, formatBytes, rememberGraph } from "../lib/api";
import type { Attachment, ClarifyAnswer, ClarifyOut, GoalInput } from "../lib/types";

type Selection = Record<string, { picked: string[]; free: string }>;

/** 目标 → 追问（前置知识 / 深度 / 偏好）→ 生成路线。一句话说明后主动询问，选项可点选，也可自己说明。 */
export function ClarifyWizard({ initial, onClose }: { initial: GoalInput; onClose: () => void }) {
  const nav = useNavigate();
  const [clarify, setClarify] = useState<ClarifyOut | null>(null);
  const [selection, setSelection] = useState<Selection>({});
  const [extra, setExtra] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState<"clarify" | "create" | null>("clarify");
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .clarify({ ...initial, attachment_ids: attachments.map((a) => a.id) })
      .then((c) => {
        if (cancelled) return;
        setClarify(c);
        setSelection(Object.fromEntries(c.questions.map((q) => [q.id, { picked: [], free: "" }])));
        setBusy(null);
      })
      .catch(() => {
        if (cancelled) return;
        // clarification is a nicety; never block the learner on it
        setClarify({ intro: "先直接为你规划路线；你也可以在下方补充说明，这些信息会写入学习档案。", questions: [], profile_hint: "" });
        setBusy(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = (qid: string, option: string, multiple: boolean) =>
    setSelection((s) => {
      const cur = s[qid] ?? { picked: [], free: "" };
      const has = cur.picked.includes(option);
      const picked = multiple ? (has ? cur.picked.filter((o) => o !== option) : [...cur.picked, option]) : has ? [] : [option];
      return { ...s, [qid]: { ...cur, picked } };
    });

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const f of Array.from(files)) {
        const att = await api.uploadAttachment(f);
        setAttachments((a) => [...a, att]);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const submit = async (skip = false) => {
    setBusy("create");
    setError(null);
    const answers: ClarifyAnswer[] = [];
    if (!skip && clarify) {
      for (const q of clarify.questions) {
        const sel = selection[q.id];
        const parts = [...(sel?.picked ?? []), sel?.free?.trim()].filter(Boolean) as string[];
        if (parts.length) answers.push({ question: q.question, answer: parts.join("；") });
      }
    }
    if (extra.trim()) answers.push({ question: "学习者补充说明", answer: extra.trim() });
    try {
      const created = await api.createGoal({ ...initial, answers, attachment_ids: attachments.map((a) => a.id) });
      rememberGraph(created.graph_id);
      nav(`/g/${created.graph_id}`);
    } catch (e) {
      setError(e instanceof ApiError && e.status !== 0 ? "创建学习路径时遇到问题，请再点一次。" : "网络不稳定，请再点一次。");
      setBusy(null);
    }
  };

  const answered = clarify ? clarify.questions.filter((q) => (selection[q.id]?.picked.length ?? 0) > 0 || selection[q.id]?.free.trim()).length : 0;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/40 p-0 backdrop-blur-sm sm:items-center sm:p-6" onClick={onClose}>
      <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl bg-white shadow-xl sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-6 py-4">
          <div>
            <div className="text-xs font-medium text-brand-600">第 1 步 · 先弄清几个问题</div>
            <h2 className="mt-0.5 text-lg font-bold">{initial.goal}</h2>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5">
          {busy === "clarify" && (
            <div className="flex items-center gap-2 py-10 text-sm text-slate-500">
              <Loader2 size={16} className="animate-spin" /> 正在理解你的目标，准备几个关键问题…
            </div>
          )}
          {clarify && (
            <>
              <p className="rounded-xl bg-brand-50 px-4 py-3 text-[14px] leading-6 text-brand-900">{clarify.intro}</p>
              {clarify.profile_hint && <p className="mt-1.5 text-xs text-slate-500">{clarify.profile_hint}</p>}
              <ol className="mt-5 space-y-5">
                {clarify.questions.map((q, i) => (
                  <li key={q.id}>
                    <div className="flex items-start gap-2">
                      <span className="mt-0.5 rounded bg-slate-100 px-1.5 text-xs font-semibold text-slate-600">{i + 1}</span>
                      <div className="flex-1">
                        <div className="text-[15px] font-medium leading-6">
                          {q.question}
                          {q.multiple && <span className="ml-1.5 text-xs font-normal text-slate-400">可多选</span>}
                        </div>
                        {q.why && <div className="mt-0.5 text-xs text-slate-400">{q.why}</div>}
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {q.options.map((opt) => {
                            const on = selection[q.id]?.picked.includes(opt);
                            return (
                              <button key={opt} onClick={() => toggle(q.id, opt, q.multiple)} className={`rounded-full border px-3 py-1 text-[13px] transition ${on ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-700 hover:border-slate-300"}`}>
                                {opt}
                              </button>
                            );
                          })}
                        </div>
                        <input
                          value={selection[q.id]?.free ?? ""}
                          onChange={(e) => setSelection((s) => ({ ...s, [q.id]: { picked: s[q.id]?.picked ?? [], free: e.target.value } }))}
                          placeholder="或者自己说明…"
                          className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-1.5 text-[13px] focus:border-brand-400 focus:outline-none"
                        />
                      </div>
                    </div>
                  </li>
                ))}
              </ol>

              <div className="mt-5">
                <div className="text-[13px] font-medium text-slate-700">还有什么想告诉我的？</div>
                <textarea value={extra} onChange={(e) => setExtra(e.target.value)} rows={2} placeholder="例如：我是软件工程专业大三学生，会 Java，做过 Spring Boot 项目；期末考试范围见附件…" className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 text-[13px] leading-6 focus:border-brand-400 focus:outline-none" />
                <p className="mt-1 text-[11px] text-slate-400">这些信息会写入你的学习档案，之后每次讲解和出题都会参考。</p>
              </div>

              <div className="mt-4 rounded-xl border border-dashed border-slate-300 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-[13px] font-medium text-slate-700">
                    <Paperclip size={13} className="mr-1 inline" /> 附件（可选）：课程大纲、考试范围、笔记、PDF
                  </div>
                  <button onClick={() => fileRef.current?.click()} disabled={uploading} className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:border-brand-300 disabled:opacity-50">
                    {uploading ? <Loader2 size={12} className="animate-spin" /> : <FileUp size={12} />} 上传
                  </button>
                  <input ref={fileRef} type="file" multiple className="hidden" accept=".pdf,.txt,.md,.docx,.csv,.json,.py,.java,.tex" onChange={(e) => upload(e.target.files)} />
                </div>
                {attachments.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {attachments.map((a) => (
                      <li key={a.id} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs">
                        <span className="truncate">
                          {a.filename} <span className="text-slate-400">· {formatBytes(a.size)}{a.has_text ? " · 已提取文字" : " · 未能提取文字"}</span>
                        </span>
                        <button onClick={() => setAttachments((list) => list.filter((x) => x.id !== a.id))} className="text-slate-400 hover:text-rose-500" aria-label="移除">
                          <X size={12} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
          {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4">
          <button onClick={() => submit(true)} disabled={busy !== null} className="text-sm text-slate-500 hover:text-slate-700 disabled:opacity-50">
            跳过，直接生成
          </button>
          <button onClick={() => submit(false)} disabled={busy !== null || !clarify} className="inline-flex items-center gap-1.5 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
            {busy === "create" ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {clarify ? `生成学习路径（已答 ${answered}/${clarify.questions.length}）` : "生成学习路径"}
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
