import type { AuthStatus, Card, Graph, GoalInput, Health, HotItem, NodeDetail, Quiz, QuizResult } from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),
  auth: () => request<AuthStatus>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  loginUrl: (next = "/") => `${BASE}/auth/zhihu/login?next=${encodeURIComponent(next)}`,
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
};

export interface StreamHandlers {
  onMeta?: (meta: Record<string, unknown>) => void;
  onDelta: (text: string) => void;
  onDone?: (meta: Record<string, unknown>) => void;
  onError: (message: string) => void;
}

/** POST + Server-Sent-Events reader (fetch based so we can send a JSON body). */
export async function streamSSE(path: string, body: unknown, handlers: StreamHandlers, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    handlers.onError("无法连接服务器");
    return;
  }
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : detail;
    } catch {
      /* ignore */
    }
    handlers.onError(detail || `HTTP ${res.status}`);
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

export function kindLabel(kind: string): string {
  return { question: "问题", answer: "回答", article: "专栏", other: "页面" }[kind] ?? "页面";
}

const RECENT_KEY = "learnway.recent";
export function rememberGraph(id: string) {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]") as string[];
    localStorage.setItem(RECENT_KEY, JSON.stringify([id, ...list.filter((x) => x !== id)].slice(0, 20)));
  } catch {
    /* ignore */
  }
}
