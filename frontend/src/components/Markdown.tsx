import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "../lib/types";

/** Turn `[3]` / `[1][2]` citation markers into fragment links our renderer can style
 *  (react-markdown strips unknown URL protocols, so we use `#cite-n` rather than a custom scheme). */
function linkCitations(md: string): string {
  return md.replace(/\[(\d{1,2})\](?!\()/g, (_m, n: string) => `[${n}](#cite-${n})`);
}

export function Markdown({ text, citations }: { text: string; citations?: Citation[] }) {
  const map = new Map((citations ?? []).map((c) => [c.index, c]));
  return (
    <div className="prose-learn">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#cite-")) {
              const n = Number(href.slice(6));
              const c = map.get(n);
              return (
                <a className="cite" href={c?.url ?? "#"} target="_blank" rel="noreferrer" title={c ? `${c.title}` : `来源 ${n}`}>
                  {n}
                </a>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {linkCitations(text)}
      </ReactMarkdown>
    </div>
  );
}
