import { Link } from "react-router-dom";

export function Footer({ className = "" }: { className?: string }) {
  return (
    <footer className={`border-t border-slate-200 bg-white/60 ${className}`}>
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs text-slate-500 sm:flex-row">
        <div>
          © 2026 知径 LearnPath · 知乎黑客松 2026 校园新锐季参赛作品
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span>内容来源：知乎数据开放平台</span>
          <Link to="/dashboard" className="hover:text-brand-600">控制台</Link>
          <a href="https://github.com/CheemsaDoge/LearnPath" target="_blank" rel="noreferrer" className="hover:text-brand-600">GitHub</a>
          <a href="https://github.com/SunnyBoy-y/LearnGraph" target="_blank" rel="noreferrer" className="hover:text-brand-600">灵感来自 LearnGraph</a>
        </div>
      </div>
    </footer>
  );
}
