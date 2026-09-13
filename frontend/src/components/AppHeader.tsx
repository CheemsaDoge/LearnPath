import { LayoutDashboard } from "lucide-react";
import { NavLink } from "react-router-dom";
import { AuthMenu } from "./AuthMenu";
import { Logo } from "./Logo";

export function AppHeader({ children }: { children?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
        <Logo />
        <nav className="ml-2 hidden items-center gap-1 text-sm sm:flex">
          <NavLink to="/" end className={({ isActive }) => `rounded-md px-2.5 py-1.5 ${isActive ? "bg-slate-100 font-medium text-ink" : "text-slate-600 hover:bg-slate-100"}`}>
            首页
          </NavLink>
          <NavLink to="/dashboard" className={({ isActive }) => `inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 ${isActive ? "bg-slate-100 font-medium text-ink" : "text-slate-600 hover:bg-slate-100"}`}>
            <LayoutDashboard size={14} /> 控制台
          </NavLink>
        </nav>
        <div className="flex-1">{children}</div>
        <AuthMenu />
      </div>
    </header>
  );
}
