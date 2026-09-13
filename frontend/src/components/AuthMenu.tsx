import { LogIn, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../lib/api";
import type { AuthStatus } from "../lib/types";

/** 知乎账号登录入口（OAuth 接入处于测试状态；未配置时整块隐藏）。 */
export function AuthMenu() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const location = useLocation();
  const loginError = new URLSearchParams(location.search).get("login_error");

  useEffect(() => {
    api.auth().then(setAuth).catch(() => setAuth(null));
  }, []);

  if (!auth || !auth.enabled) return null;

  if (auth.user) {
    return (
      <div className="flex items-center gap-2 text-xs">
        {auth.user.avatar ? <img src={auth.user.avatar} alt="" className="h-7 w-7 rounded-full border border-slate-200 object-cover" /> : <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-100 text-brand-700">{auth.user.name.slice(0, 1)}</span>}
        <span className="max-w-[8rem] truncate font-medium text-slate-700">{auth.user.name}</span>
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

  return (
    <div className="flex items-center gap-2">
      {loginError && <span className="text-xs text-rose-600">登录失败：{loginError}</span>}
      <a href={api.loginUrl(location.pathname)} className="inline-flex items-center gap-1 rounded-lg border border-brand-200 bg-white px-2.5 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50" title="知乎 OAuth 登录（测试状态）">
        <LogIn size={13} /> 知乎登录
        <span className="rounded bg-amber-100 px-1 text-[10px] text-amber-800">测试</span>
      </a>
    </div>
  );
}
