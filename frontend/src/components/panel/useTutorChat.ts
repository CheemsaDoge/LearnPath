import { useCallback, useState } from "react";
import { streamSSE } from "../../lib/api";

export interface TutorMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  engine?: "tutor" | "zhida";
  reasoning?: string;
  streaming?: boolean;
}

let seq = 0;
const nextId = () => `local_${Date.now()}_${seq++}`;

/** Shared streaming-chat state machine for the main lesson thread and selection sub-threads. */
export function useTutorChat(nodeId: string, threadId: string, quote = "") {
  const [messages, setMessages] = useState<TutorMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const patchLast = useCallback((fn: (last: TutorMsg) => TutorMsg) => {
    setMessages((m) => {
      if (!m.length) return m;
      const copy = [...m];
      copy[copy.length - 1] = fn(copy[copy.length - 1]);
      return copy;
    });
  }, []);

  const ask = useCallback(
    async (question: string, engine: "tutor" | "zhida" = "tutor", onDone?: () => void) => {
      const q = question.trim();
      if (!q || busy) return;
      setBusy(true);
      setNote(null);
      setMessages((m) => [...m, { id: nextId(), role: "user", content: q }, { id: nextId(), role: "assistant", content: "", engine, streaming: true }]);
      const run = (attempt: number): Promise<void> =>
        streamSSE(`/nodes/${nodeId}/chat`, { question: q, mode: engine, thread_id: threadId, quote }, {
          onMeta: (meta) => {
            if (typeof meta.reasoning === "string") patchLast((last) => ({ ...last, reasoning: (last.reasoning ?? "") + meta.reasoning }));
          },
          onStatus: (t) => patchLast((last) => ({ ...last, reasoning: t })),
          onDelta: (d) => patchLast((last) => ({ ...last, content: last.content + d, reasoning: undefined })),
          onDone: () => {
            patchLast((last) => ({ ...last, streaming: false }));
            onDone?.();
          },
          onError: async (msg) => {
            if (attempt < 2) {
              patchLast((last) => ({ ...last, reasoning: "连接波动，正在重试…" }));
              await new Promise((r) => setTimeout(r, 1000));
              return run(attempt + 1);
            }
            patchLast((last) => ({ ...last, streaming: false, content: last.content || "抱歉，这次没能连上 AI 服务。稍后再问一次，或先看「知乎来源」。" }));
            setNote(msg);
          },
        });
      await run(1);
      setBusy(false);
    },
    [busy, nodeId, threadId, quote, patchLast],
  );

  return { messages, setMessages, busy, note, ask };
}
