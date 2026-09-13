import { ArrowRight, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Footer } from "../components/Footer";
import { Logo } from "../components/Logo";
import { api } from "../lib/api";
import type { AuthStatus } from "../lib/types";

function safeReturnTo(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/dashboard";
}

export function Login() {
  const location = useLocation();
  const nav = useNavigate();
  const params = new URLSearchParams(location.search);
  const returnTo = safeReturnTo(params.get("returnTo"));
  const loginError = params.get("login_error");
  const [auth, setAuth] = useState<AuthStatus | null>(null);

  useEffect(() => {
    api.auth().then((a) => {
      setAuth(a);
      if (a.user) nav(returnTo, { replace: true });
    });
  }, [nav, returnTo]);

  return (
    <div className="flex min-h-full flex-col bg-paper">
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex justify-center">
            <Logo />
          </div>
          <h1 className="mt-6 text-center text-xl font-bold">登录知径</h1>
          <p className="mt-2 text-center text-sm leading-6 text-slate-600">使用知乎账号登录后，你的学习路径、掌握度与学习档案会跟随账号保存，在任何设备继续学习。</p>

          {loginError && <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">登录失败：{loginError}</div>}

          {auth?.enabled ? (
            <a href={api.loginUrl(returnTo)} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-[#0084ff] px-4 py-3 text-[15px] font-semibold text-white shadow-sm hover:bg-[#0070d9]">
              <span className="grid h-6 w-6 place-items-center rounded bg-white/15 text-[13px] font-bold">知</span>
              使用知乎账号登录
              <ArrowRight size={16} />
            </a>
          ) : (
            <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">{auth ? "知乎登录尚未配置，请先以访客身份使用。" : "正在检查登录状态…"}</div>
          )}

          <div className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck size={12} /> 知乎 OAuth 2.0 授权登录 · 测试状态 · 我们只读取昵称与头像
          </div>

          <div className="mt-6 border-t border-slate-100 pt-4 text-center text-sm">
            <Link to={returnTo} className="text-slate-500 hover:text-brand-600">
              暂不登录，以访客身份继续
            </Link>
            <p className="mt-1 text-[11px] text-slate-400">访客期间的学习记录保存在本设备，登录后会自动合并到你的账号。</p>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
