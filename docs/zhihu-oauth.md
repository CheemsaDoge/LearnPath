# 知乎 OAuth 登录接入说明

> **状态：测试（Test）。** 代码已按知乎 OAuth 2.0 授权码规范实现并通过 Mock 测试；**尚未用真实 App ID / App Key 完成线上联调**（凭证由黑客松「创建项目」后在活动页面分配）。未配置凭证时站点自动隐藏登录入口，其余功能不受影响。
>
> 依据：知乎 OAuth API 快速开始（`openapi.zhihu.com`）、黑客松 OAuth 接入补充资料（2026-09）。

## 1. 流程

标准 OAuth 2.0 授权码流程，token 交换在后端完成，浏览器只持有知径自己的会话 Cookie：

```text
浏览器                          知径后端                                 openapi.zhihu.com
  │ GET /api/auth/zhihu/login?next=/g/x │                                       │
  │────────────────────────────────────►│ 生成签名 state，写入 Cookie             │
  │ 302 → /authorize?redirect_uri&app_id&response_type=code&state              │
  │───────────────────────────────────────────────────────────────────────────►│
  │                                     │              用户登录知乎并确认授权      │
  │ 302 → {redirect_uri}?authorization_code=…&state=…                          │
  │◄───────────────────────────────────────────────────────────────────────────│
  │────────────────────────────────────►│ 校验 state（签名 + 10 分钟 + Cookie 一致）
  │                                     │ POST /access_token（表单）──────────►│
  │                                     │ GET /user（Bearer access_token）────►│
  │                                     │ upsert users，创建 login_sessions     │
  │ 302 → next；Set-Cookie: learnpath_session（HttpOnly, SameSite=Lax, Secure, 30 天）
  │◄────────────────────────────────────│                                       │
```

## 2. 配置项（`backend/.env`）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `LEARNPATH_PUBLIC_ORIGIN` | 是 | 站点公网地址，例如 `https://learn.cosheaf.com`；用于拼默认回调地址 |
| `LEARNPATH_SESSION_SECRET` | 是 | state 与会话签名密钥；生产环境用 `python -c "import secrets;print(secrets.token_hex(32))"` 生成 |
| `ZHIHU_OAUTH_APP_ID` | 是 | 黑客松项目页面分配的 App ID（可公开） |
| `ZHIHU_OAUTH_APP_KEY` | 是 | App Key，只在后端换取 token，不进入前端/日志/仓库 |
| `ZHIHU_OAUTH_REDIRECT_URI` | 否 | 默认 `{PUBLIC_ORIGIN}/api/auth/zhihu/callback`；必须与活动页面登记的回调地址逐字一致（协议、域名、端口、路径、尾部斜杠） |
| `LEARNPATH_ZHIHU_OAUTH_REQUIRE_STATE` | 否 | 默认 `true`。黑客松 OAuth 服务已支持 `state` 原样透传；若平台某次回调不带 `state`，可临时设为 `false`（仍以 Cookie 校验登录请求） |

授权页、token、用户信息三个端点默认为 `https://openapi.zhihu.com/{authorize,access_token,user}`，可用 `LEARNPATH_ZHIHU_OAUTH_AUTHORIZE_URL` 等覆盖。

App ID 与 App Key 齐全后登录入口才会出现（`GET /api/auth/me` 返回 `enabled: true`）。修改后执行 `systemctl --user restart learnpath`。

**当前线上环境应登记的回调地址：`https://learn.cosheaf.com/api/auth/zhihu/callback`**

## 3. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/auth/me` | `{enabled, stage: "test", provider: "zhihu", login_url, user}`；未登录时 `user` 为 `null` |
| GET | `/api/auth/zhihu/login?next=/g/xxx` | 生成 state 并 302 到知乎授权页；未配置时返回 503 |
| GET | `/api/auth/zhihu/callback?authorization_code&state` | 回调：换 token → 拉资料 → 建会话 → 302 回 `next`；失败时 302 到 `/?login_error=...` |
| POST | `/api/auth/logout` | 删除会话并清 Cookie |

## 4. 与知乎协议对齐的实现细节

代码：`backend/app/services/oauth.py`、`backend/app/api/auth.py`。

- **授权 URL**：`GET https://openapi.zhihu.com/authorize?redirect_uri={urlencoded}&app_id={app_id}&response_type=code&state={state}`。
- **回调参数名是 `authorization_code`**（不是标准的 `code`）；后端同时接受 `code` 以兼容协议修订。
- **换 token**：`POST https://openapi.zhihu.com/access_token`，`application/x-www-form-urlencoded`，字段 `app_id, app_key, grant_type=authorization_code, redirect_uri, code`。成功响应 `{access_token, token_type, expires_in}`（有效期默认 30 天，**无 refresh_token**，过期后需重新授权）。
- **用户信息**：`GET https://openapi.zhihu.com/user`，`Authorization: Bearer <access_token>`。字段映射：`uid`→唯一标识（int64，按字符串无损保存，不经过 JS Number），`fullname`→昵称，`avatar_path`→头像，`headline`（缺省 `description`）→一句话介绍；`hash_id`、`gender`、`email`、`phone_no` 等原样保存在 `users.profile`。
- **错误约定**：知乎的业务错误以 HTTP 200 返回 `{"code": 401|403|404, "data": "..."}`；`code: 20000` 表示成功。后端优先检查是否拿到 `access_token` / 用户对象，再看 `code`，不把 `20000` 当错误。
- **state**：HMAC-SHA256 签名 + 时间戳（10 分钟有效）+ base64url 编码的 `next`；回调时同时校验 Cookie 中的 state，防 CSRF；`next` 只允许站内相对路径。
- **会话**：`login_sessions`（随机 32 字节 id，30 天过期，服务端保存 access_token）；Cookie `HttpOnly + SameSite=Lax`，HTTPS 或 `X-Forwarded-Proto: https`（Cloudflare Tunnel）时加 `Secure`。
- App Key 与 access_token 不进入前端、日志、SSE 或导出内容。

## 5. 联调步骤

1. 在活动页面「创建项目」后获取 App ID / App Key，并登记回调地址 `https://learn.cosheaf.com/api/auth/zhihu/callback`。
2. 写入 `backend/.env` 后重启；`GET /api/auth/me` 应返回 `enabled: true`。
3. 打开首页 → 右上角「知乎登录 · 测试」→ 在知乎完成授权 → 回到原页面，右上角显示头像与昵称。
4. 验证清单（黑客松交付要求）：正确 `state` 可登录；缺失 / 不匹配 / 过期 / 重复的 `state` 被拒绝（400）；退出后 `user` 为 `null`；浏览器与截图中不出现 App Key 或 access_token。
5. 排查：服务端日志 `zhihu oauth failed: ...`；首页 URL 的 `login_error` 参数带回失败原因。

## 6. 路线图

- 登录后用 `X-OAuth-Token` + Access Secret 调用 `developer.zhihu.com/api/v1/user/{contents,followees,favlists,...}`，把学习者的创作与收藏作为个性化起点（见 [zhihu-open-platform.md](zhihu-open-platform.md) 第 5 节）。
- 学习进度按用户隔离（当前图谱不绑定用户，登录仅建立身份）。
