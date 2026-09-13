import type { Attachment, AuthStatus, Card, ChatMessage, ClarifyOut, ClarifyAnswer, Dashboard, FactKind, Graph, GoalInput, Health, HotItem, Me, NodeDetail, ProfileFact, Quiz, QuizResult } from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const RETRYABLE = new Set([408, 425, 429, 500, 502, 503, 504]);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** JSON request with hidden retries: network errors and 5xx are retried (GET: 3 tries, others: 2) before surfacing. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const attempts = method === "GET" ? 3 : 2;
  let lastError: Error = new ApiError(0, "网络错误");
  for (let attempt = 1; attempt <= attempts; attempt++) {
    let res: Response;
    try {
      res = await fetch(BASE + path, { headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }, ...init });
    } catch (err) {
      lastError = new ApiError(0, "网络连接不稳定，请稍后再试");
      if (attempt < attempts) {
        await sleep(600 * attempt);
        continue;
      }
      throw lastError;
    }
    if (res.ok) {
      if (res.status === 204) return undefined as T;
      return (await res.json()) as T;
    }
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    lastError = new ApiError(res.status, detail);
    if (RETRYABLE.has(res.status) && attempt < attempts) {
      await sleep(800 * attempt);
      continue;
    }
    throw lastError;
  }
  throw lastError;
}

export const api = {
  health: () => request<Health>("/health"),
  auth: () => request<AuthStatus>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  loginUrl: (next = "/") => `${BASE}/auth/zhihu/login?next=${encodeURIComponent(next)}`,
  me: () => request<Me>("/me"),
  dashboard: () => request<Dashboard>("/me/dashboard"),
  clarify: (input: GoalInput) => request<ClarifyOut>("/goals/clarify", { method: "POST", body: JSON.stringify(input) }),
  createFact: (kind: FactKind, text: string) => request<ProfileFact>("/me/facts", { method: "POST", body: JSON.stringify({ kind, text }) }),
  deleteFact: (id: string) => request<void>(`/me/facts/${id}`, { method: "DELETE" }),
  listAttachments: () => request<Attachment[]>("/attachments"),
  deleteAttachment: (id: string) => request<void>(`/attachments/${id}`, { method: "DELETE" }),
  attachmentDownloadUrl: (id: string) => `${BASE}/attachments/${id}/download`,
  uploadAttachment: async (file: File, graphId?: string): Promise<Attachment> => {
    const form = new FormData();
    form.append("file", file);
    if (graphId) form.append("graph_id", graphId);
    const res = await fetch(`${BASE}/attachments`, { method: "POST", body: form });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, String(detail));
    }
    return (await res.json()) as Attachment;
  },
  hot: () => request<HotItem[]>("/hot"),
  createGoal: (input: GoalInput) => request<{ graph_id: string; goal_id: string; status: string }>("/goals", { method: "POST", body: JSON.stringify(input) }),
  listGraphs: () => request<Graph[]>("/graphs"),
  getGraph: (id: string) => request<Graph>(`/graphs/${id}`),
  retryGraph: (id: string) => request<{ graph_id: string }>(`/graphs/${id}/retry`, { method: "POST" }),
  deleteGraph: (id: string) => request<void>(`/graphs/${id}`, { method: "DELETE" }),
  exportUrl: (id: string) => `${BASE}/graphs/${id}/export.md`,
  getNode: (id: string) => request<NodeDetail>(`/nodes/${id}`),
  createQuiz: (nodeId: string) => request<Quiz>(`/nodes/${nodeId}/quiz`, { method: "POST" }),
  submitQuiz: (quizId: string, answers: Record<string, unknown>) => request<QuizResult>(`/quizzes/${quizId}/submit`, { method: "POST", body: JSON.stringify({ answers }) }),
  createCards: (nodeId: string) => request<{ node_id: string; cards: Card[] }>(`/nodes/${nodeId}/cards`, { method: "POST" }),
  regroundNode: (nodeId: string) => request<NodeDetail>(`/nodes/${nodeId}/ground`, { method: "POST" }),
  threadMessages: (nodeId: string, threadId: string) => request<ChatMessage[]>(`/nodes/${nodeId}/threads/${threadId}`),
};

export interface StreamHandlers {
  onMeta?: (meta: Record<string, unknown>) => void;
  onDelta: (text: string) => void;
  onDone?: (meta: Record<string, unknown>) => void;
  onError: (message: string) => void;
  onStatus?: (text: string) => void;
}

/** POST + Server-Sent-Events reader (fetch based so we can send a JSON body).
 *  Connection failures before the first token are retried silently (up to 3 attempts). */
export async function streamSSE(path: string, body: unknown, handlers: StreamHandlers, signal?: AbortSignal): Promise<void> {
  let res: Response | null = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      res = await fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      res = null;
    }
    if (res && res.ok && res.body) break;
    const status = res?.status ?? 0;
    if (attempt < 3 && (status === 0 || RETRYABLE.has(status))) {
      handlers.onStatus?.(`连接不稳定，正在重试（${attempt + 1}/3）…`);
      await sleep(900 * attempt);
      continue;
    }
    let detail = res?.statusText ?? "无法连接服务器";
    try {
      if (res) {
        const j = await res.json();
        detail = typeof j.detail === "string" ? j.detail : detail;
      }
    } catch {
      /* ignore */
    }
    handlers.onError(detail || `HTTP ${status}`);
    return;
  }
  if (!res || !res.body) {
    handlers.onError("无法连接服务器");
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const event = JSON.parse(line.slice(6)) as Record<string, unknown>;
          if (typeof event.error === "string") {
            handlers.onError(event.error);
            return;
          }
          if (typeof event.delta === "string") handlers.onDelta(event.delta);
          else if (typeof event.status === "string") handlers.onStatus?.(event.status);
          else if (event.done) handlers.onDone?.(event);
          else handlers.onMeta?.(event);
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") handlers.onError("连接中断");
  }
}

export function formatMinutes(min: number): string {
  if (min < 60) return `${min} 分钟`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h} 小时 ${m} 分` : `${h} 小时`;
}

/** Strip $…$ math delimiters for places that cannot render KaTeX (graph node labels). */
export function plainMath(text: string): string {
  return text.replace(/\$\$?([^$]+?)\$\$?/g, "$1").replace(/\\(?:mathrm|text|mathbf)\{([^}]*)\}/g, "$1").replace(/\\([A-Za-z]+)/g, "$1").replace(/[{}]/g, "");
}

export function kindLabel(kind: string): string {
  return { question: "问题", answer: "回答", article: "专栏", other: "页面" }[kind] ?? "页面";
}

export const FACT_KIND_LABEL: Record<FactKind, string> = { background: "背景", skill: "已掌握", goal: "目标", preference: "偏好", interest: "兴趣", progress: "进度", other: "其他" };

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatTime(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export type { ClarifyAnswer };

const RECENT_KEY = "learnpath.recent";
export function rememberGraph(id: string) {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]") as string[];
    localStorage.setItem(RECENT_KEY, JSON.stringify([id, ...list.filter((x) => x !== id)].slice(0, 20)));
  } catch {
    /* ignore */
  }
}
