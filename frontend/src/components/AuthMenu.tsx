import { LogIn, LogOut, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import type { AuthStatus } from "../lib/types";

/** 知乎账号登录入口（OAuth 接入处于测试状态；未配置时只显示访客状态）。 */
export function AuthMenu() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const location = useLocation();

  useEffect(() => {
    api.auth().then(setAuth).catch(() => setAuth(null));
  }, [location.pathname]);

  if (!auth) return null;

  if (auth.user) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <Link to="/dashboard" className="flex items-center gap-2 rounded-full border border-slate-200 py-0.5 pl-0.5 pr-2.5 hover:border-brand-300" title="打开控制台">
          {auth.user.avatar ? <img src={auth.user.avatar} alt="" className="h-7 w-7 rounded-full object-cover" /> : <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-100 text-brand-700">{auth.user.name.slice(0, 1)}</span>}
          <span className="max-w-[8rem] truncate font-medium text-slate-700">{auth.user.name}</span>
        </Link>
        <button
          onClick={async () => {
            await api.logout();
            setAuth({ ...auth, user: null });
          }}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          title="退出登录"
        >
          <LogOut size={13} />
        </button>
      </div>
    );
  }

  const returnTo = location.pathname + location.search;
  if (!auth.enabled) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500" title="知乎登录尚未配置，学习记录暂存在本设备">
        <UserRound size={13} /> 访客模式
      </span>
    );
  }
  return (
    <Link to={`/login?returnTo=${encodeURIComponent(returnTo)}`} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600">
      <LogIn size={13} /> 知乎登录
    </Link>
  );
}
