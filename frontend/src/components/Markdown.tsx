import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import type { Citation } from "../lib/types";

/** LLMs sometimes emit LaTeX-style \( … \) / \[ … \] delimiters; remark-math only understands $ … $ / $$ … $$. */
function normalizeMath(md: string): string {
  return md
    .replace(/\\\[([\s\S]+?)\\\]/g, (_m, inner: string) => `\n$$\n${inner.trim()}\n$$\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_m, inner: string) => `$${inner.trim()}$`);
}

/** Turn `[3]` / `[1][2]` citation markers into fragment links our renderer can style
 *  (react-markdown strips unknown URL protocols, so we use `#cite-n` rather than a custom scheme). */
function linkCitations(md: string): string {
  // don't touch bracketed numbers inside math ($…$ / $$…$$)
  return md
    .split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$)/g)
    .map((part, i) => (i % 2 === 1 ? part : part.replace(/\[(\d{1,2})\](?!\()/g, (_m, n: string) => `[${n}](#cite-${n})`)))
    .join("");
}

export function Markdown({ text, citations }: { text: string; citations?: Citation[] }) {
  const map = new Map((citations ?? []).map((c) => [c.index, c]));
  return (
    <div className="prose-learn">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
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
        {linkCitations(normalizeMath(text))}
      </ReactMarkdown>
    </div>
  );
}
