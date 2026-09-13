import { CheckCircle2, ClipboardList, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { NodeDetail, Quiz, QuizResult } from "../../lib/types";
import { Stars } from "../Stars";

export function QuizTab({ node, onGraded }: { node: NodeDetail; onGraded: (r: QuizResult) => void }) {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState<"gen" | "grade" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setQuiz(null);
    setAnswers({});
    setResult(null);
    setError(null);
  }, [node.id]);

  const generate = async () => {
    setBusy("gen");
    setError(null);
    setResult(null);
    setAnswers({});
    try {
      setQuiz(await api.createQuiz(node.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "生成失败");
    } finally {
      setBusy(null);
    }
  };

  const submit = async () => {
    if (!quiz) return;
    setBusy("grade");
    setError(null);
    try {
      const r = await api.submitQuiz(quiz.id, answers);
      setResult(r);
      onGraded(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "提交失败");
    } finally {
      setBusy(null);
    }
  };

  const answered = quiz ? quiz.questions.filter((q) => (q.qtype === "single" ? answers[q.id] !== undefined : typeof answers[q.id] === "string" && (answers[q.id] as string).trim())).length : 0;

  if (!quiz) {
    return (
      <div className="rounded-xl border border-dashed border-emerald-200 bg-emerald-50/50 p-6 text-center">
        <p className="text-sm text-slate-600 leading-6">
          3 道单选题 + 1 道费曼解释题，全部基于知乎来源出题。做完自动评分，更新掌握度 <Stars value={node.mastery_stars} className="align-middle" />。
        </p>
        {node.attempts > 0 && <p className="mt-1 text-xs text-slate-500">已练习 {node.attempts} 次，当前掌握度 {node.mastery_score.toFixed(0)} 分</p>}
        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        <button onClick={generate} disabled={busy === "gen"} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60">
          {busy === "gen" ? <Loader2 size={15} className="animate-spin" /> : <ClipboardList size={15} />} 生成小测验
        </button>
      </div>
    );
  }

  const resultFor = (id: string) => result?.results.find((r) => r.id === id);

  return (
    <div className="space-y-4">
      {result && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-emerald-700">{result.score} 分</div>
              <div className="text-sm text-slate-600">{result.summary}</div>
            </div>
            <div className="text-right">
              <Stars value={result.mastery_stars} size={20} />
              {result.mastery_stars > result.stars_before && <div className="text-xs text-amber-600">掌握度提升！</div>}
            </div>
          </div>
        </div>
      )}
      {quiz.questions.map((q, qi) => {
        const r = resultFor(q.id);
        return (
          <div key={q.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-start gap-2">
              <span className="mt-0.5 rounded bg-slate-100 px-1.5 text-xs font-semibold text-slate-600">{qi + 1}</span>
              <p className="text-[14px] font-medium leading-6">
                {q.stem}
                {q.qtype === "feynman" && <span className="ml-2 rounded bg-violet-100 px-1.5 py-0.5 text-[11px] font-normal text-violet-700">费曼解释</span>}
              </p>
            </div>
            {q.qtype === "single" ? (
              <div className="space-y-1.5">
                {q.options.map((opt, oi) => {
                  const chosen = answers[q.id] === oi;
                  let cls = "border-slate-200 hover:border-brand-300";
                  if (r) {
                    if (oi === r.answer_index) cls = "border-emerald-400 bg-emerald-50";
                    else if (chosen) cls = "border-rose-300 bg-rose-50";
                    else cls = "border-slate-100 text-slate-400";
                  } else if (chosen) cls = "border-brand-500 bg-brand-50";
                  return (
                    <button key={oi} disabled={!!r} onClick={() => setAnswers((a) => ({ ...a, [q.id]: oi }))} className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left text-[13px] leading-6 transition ${cls}`}>
                      <span className="font-semibold text-slate-500">{"ABCD"[oi]}.</span>
                      <span className="flex-1">{opt}</span>
                      {r && oi === r.answer_index && <CheckCircle2 size={16} className="text-emerald-600" />}
                      {r && chosen && oi !== r.answer_index && <XCircle size={16} className="text-rose-500" />}
                    </button>
                  );
                })}
              </div>
            ) : (
              <textarea
                disabled={!!r}
                value={(answers[q.id] as string) ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                placeholder="用自己的话解释：它是什么、为什么重要、举一个例子…"
                rows={4}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[13px] leading-6 focus:border-brand-400 focus:outline-none disabled:bg-slate-50"
              />
            )}
            {r && (
              <div className="mt-3 rounded-lg bg-slate-50 p-3 text-[13px] leading-6 text-slate-700">
                {r.qtype === "feynman" && <div className="mb-1 font-semibold text-violet-700">评分 {r.score} / 100</div>}
                {r.qtype === "feynman" && r.feedback && <p className="whitespace-pre-line">{r.feedback}</p>}
                {r.qtype === "single" && (
                  <p>
                    <b className={r.correct ? "text-emerald-700" : "text-rose-600"}>{r.correct ? "答对了。" : "答错了。"}</b> {r.explanation}
                  </p>
                )}
                {r.qtype === "feynman" && r.explanation && <p className="mt-1 text-slate-500">参考思路：{r.explanation}</p>}
              </div>
            )}
          </div>
        );
      })}
      {error && <p className="text-sm text-rose-600">{error}</p>}
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">
          {result ? "" : `已作答 ${answered} / ${quiz.questions.length}`}
        </span>
        {result ? (
          <button onClick={generate} disabled={busy === "gen"} className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50">
            {busy === "gen" ? <Loader2 size={15} className="animate-spin" /> : <ClipboardList size={15} />} 再来一组
          </button>
        ) : (
          <button onClick={submit} disabled={busy === "grade" || answered === 0} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
            {busy === "grade" ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />} 提交并评分
          </button>
        )}
      </div>
    </div>
  );
}
