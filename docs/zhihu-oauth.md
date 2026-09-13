# 知乎 OAuth 登录接入说明

> **状态：测试（Test）。** 本接入基于知乎提供的 OAuth quickstart（https://www.zhihu.com/ring/moltbook/api/oauth/oauth_quickstart，需登录知乎查看）。
> 接口、字段与配额以知乎方最终文档为准；上线前需要用真实 client 走通一次完整流程。当前未配置 client 时，站点会自动隐藏登录入口，其余功能不受影响。

## 1. 流程

标准 OAuth 2.0 授权码（Authorization Code）流程，由后端完成换 token，浏览器只接触知径自己的会话 Cookie：

```text
浏览器                       知径后端                              知乎授权服务器
  │  GET /api/auth/zhihu/login    │                                      │
  │──────────────────────────────►│ 生成签名 state，写入 Cookie             │
  │  302 → authorize_url?client_id&redirect_uri&state&scope               │
  │──────────────────────────────────────────────────────────────────────►│
  │                               │              用户在知乎确认授权          │
  │  302 → /api/auth/zhihu/callback?code&state                            │
  │◄──────────────────────────────────────────────────────────────────────│
  │──────────────────────────────►│ 校验 state（签名 + 10 分钟有效 + Cookie 一致）
  │                               │ POST token_url (code → access_token) ─►│
  │                               │ GET userinfo_url (Bearer token) ──────►│
  │                               │ upsert users 表，创建 login_sessions    │
  │  302 → next（原页面），Set-Cookie: learnway_session（HttpOnly, SameSite=Lax, 30 天）
  │◄──────────────────────────────│                                      │
```

## 2. 配置项（`backend/.env`）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `LEARNWAY_PUBLIC_ORIGIN` | 是 | 站点公网地址，例如 `https://learn.cosheaf.com`；用于拼默认回调地址 |
| `LEARNWAY_SESSION_SECRET` | 是 | 会话与 state 的签名密钥，生产环境必须随机：`python -c "import secrets;print(secrets.token_hex(32))"` |
| `LEARNWAY_ZHIHU_OAUTH_CLIENT_ID` | 是 | 知乎分配的 client_id |
| `LEARNWAY_ZHIHU_OAUTH_CLIENT_SECRET` | 是 | 知乎分配的 client_secret，只存在服务端 |
| `LEARNWAY_ZHIHU_OAUTH_AUTHORIZE_URL` | 是 | 授权页地址（quickstart 中的 authorize endpoint） |
| `LEARNWAY_ZHIHU_OAUTH_TOKEN_URL` | 是 | 换取 access_token 的地址 |
| `LEARNWAY_ZHIHU_OAUTH_USERINFO_URL` | 建议 | 获取用户资料的地址；留空则只用 token 响应里的 uid |
| `LEARNWAY_ZHIHU_OAUTH_SCOPE` | 视文档 | 申请的权限范围，多个用空格分隔 |
| `LEARNWAY_ZHIHU_OAUTH_REDIRECT_URI` | 否 | 默认 `{PUBLIC_ORIGIN}/api/auth/zhihu/callback`；必须与知乎后台登记的回调地址完全一致 |

四个「是」的字段齐全后登录入口才会出现（`GET /api/auth/me` 返回 `enabled: true`）。修改后执行 `systemctl --user restart learnway`。

当前线上环境应登记的回调地址：`https://learn.cosheaf.com/api/auth/zhihu/callback`

## 3. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/auth/me` | `{enabled, stage: "test", provider: "zhihu", login_url, user}`；未登录时 `user` 为 `null` |
| GET | `/api/auth/zhihu/login?next=/g/xxx` | 生成 state 并 302 到知乎授权页；未配置时返回 503 |
| GET | `/api/auth/zhihu/callback?code&state` | 回调：换 token → 拉资料 → 建会话 → 302 回 `next`；失败时 302 到 `/?login_error=...` |
| POST | `/api/auth/logout` | 删除会话并清 Cookie |

## 4. 请求与字段映射（需与 quickstart 对齐的部分）

- **换 token**：`POST token_url`，`application/x-www-form-urlencoded`，字段 `grant_type=authorization_code, code, redirect_uri, client_id, client_secret`。响应支持 JSON 或 query-string；`access_token` 可位于顶层或 `data` 内。
  如果知乎要求把 client 凭据放在 HTTP Basic 头、或使用 `client_secret_post` 以外的方式，只需修改 `backend/app/services/oauth.py` 的 `exchange_code`。
- **用户资料**：`GET userinfo_url`，`Authorization: Bearer <access_token>`。字段映射在 `normalize_profile`，按以下顺序取值：
  - 唯一标识：`id` → `uid` → `open_id` → `openid` → `url_token` → `user_id`（都没有时退回 token 响应里的 `uid`/`user_id`/`open_id`）
  - 昵称：`name` → `nickname` → `screen_name` → `username`
  - 头像：`avatar_url` → `avatar` → `avatar_url_template` → `head_url`
  - 一句话介绍：`headline` → `bio` → `description`
- 原始资料整份保存在 `users.profile`（JSON），便于后续对照文档调整映射。

## 5. 数据与安全

- 表：`users`（provider + provider_uid 唯一）、`login_sessions`（随机 32 字节 id，30 天过期，保存 access_token 供后续调用知乎接口）。
- `state` 使用 HMAC-SHA256 签名并带时间戳，10 分钟内有效；回调同时校验 Cookie 中的 state，防 CSRF。`next` 只允许站内相对路径。
- 会话 Cookie 为 `HttpOnly + SameSite=Lax`，HTTPS 环境自动加 `Secure`（含 Cloudflare Tunnel 的 `X-Forwarded-Proto`）。
- client_secret 与 access_token 不会进入前端、日志或导出内容。

## 6. 本地联调

1. 在知乎侧登记回调地址 `http://127.0.0.1:8000/api/auth/zhihu/callback`（若知乎要求 HTTPS，则用 Cloudflare Tunnel 的域名）。
2. `backend/.env` 填好配置，`LEARNWAY_PUBLIC_ORIGIN=http://127.0.0.1:8000`。
3. 启动后打开首页，右上角出现「知乎登录 · 测试」按钮；点击 → 授权 → 回到原页面，右上角显示头像与昵称。
4. 排查：`GET /api/auth/me` 看 `enabled`；失败原因会以 `login_error` 参数带回首页，服务端日志有 `zhihu oauth failed` 记录。

## 7. 待确认清单（拿到 quickstart 后逐项核对）

- [ ] authorize / token / userinfo 三个地址与 scope 取值
- [ ] token 请求的凭据传递方式（表单 / Basic）与响应字段名
- [ ] userinfo 的字段名（尤其是唯一标识与头像）
- [ ] 回调地址是否要求 HTTPS、是否允许多个
- [ ] token 有效期与刷新方式（当前未实现 refresh_token）
- [ ] 测试期间的白名单账号与调用配额
