# 知乎数据开放平台接入说明

> 平台文档：<https://developer.zhihu.com/docs>；凭证申请：<https://developer.zhihu.com/profile>（申请「Access Secret」）。
> 本文记录知径 LearnPath 实际使用的接口、字段映射、额度与缓存策略。核验时间：2026-09-13。

## 1. 用到的能力

| 能力 | 接口 | 在知径中的用途 | 每日额度（邀测） |
| --- | --- | --- | --- |
| 知乎搜索 | `GET /api/v1/content/zhihu_search` | 为每个知识点检索高赞回答与专栏（来源锚定） | 5,000 |
| 知乎热榜 | `GET /api/v1/content/hot_list` | 首页「学热点背后的知识」 | 100 |
| 知乎直答 | `POST /v1/chat/completions` | 追问面板的「直答」引擎（知乎官方 AI 搜索） | 5,000 |
| 额度查询 | `GET /api/v1/quota` | `/api/quota` 与运维排查，不消耗业务额度 | — |
| 问题回答摘要 | `GET /api/v1/content/question_answers` | 已封装（`question_answers`），当前未在产品流程中调用 | 100 |

基础域名 `https://developer.zhihu.com`。所有请求头：

```http
Authorization: Bearer <Access Secret>
X-Request-Timestamp: <Unix 秒级时间戳>
Content-Type: application/json
```

响应统一外层 `{"Code": 0, "Message": "success", "Data": ...}`；`Code` 非 0 视为失败（`20001` 鉴权失败、`30001` 频率/额度限制、`10001` 参数错误、`90001` 内部错误）。

## 2. 配置

`backend/.env`：

| 变量 | 说明 |
| --- | --- |
| `ZHIHU_ACCESS_SECRET` | Access Secret。配置后搜索、热榜、直答优先走官方接口；缺省时退回 `site:zhihu.com` 搜索引擎 + Jina Reader 兜底 |
| `LEARNPATH_ZHIDA_MODEL` | 直答模型档位：`zhida-fast-1p5`（默认）/ `zhida-thinking-1p5` / `zhida-agent` |
| `LEARNPATH_HOT_CACHE_SECONDS` | 热榜缓存秒数，默认 1800（热榜额度每日只有 100 次） |

`GET /api/health` 中 `zhihu_official: true` 与 `zhida: true` 表示已生效；`GET /api/quota` 返回当日剩余额度。

## 3. 字段映射

代码位置：`backend/app/zhihu/official.py`。

**知乎搜索 → 来源（`Source`）**

| 接口字段 | 知径字段 | 说明 |
| --- | --- | --- |
| `Url` | `url` | 带 `utm_medium=openapi_platform` 溯源参数；入库时按知乎规则规范化（`question/answer/article`），去重后保留 |
| `Title` | `title` | 去掉「 - 知乎」后缀 |
| `ContentText` | `snippet` | 去掉 `<em>` 高亮标签，最多 1500 字；讲解/出题的 prompt 直接使用 |
| `VoteUpCount` / `AuthorName` | `votes` / `author` | 来源卡片展示 |
| `AuthorityLevel` / `ContentID` | `meta` | 权威等级（1-4）保留在 `meta`，便于后续排序 |
| `ContentType` | `kind` | `Answer`/`Article`/`Question` → `answer`/`article`/`question` |

搜索 `Count` 上限 10。每个知识点默认取 1 条检索词（LLM 生成），命中不足 2 条时再用第 2 条。

**热榜 → `HotItem`**：`Title`/`Url`/`Summary`/`ThumbnailUrl` → `title`/`url`/`excerpt`/`thumbnail`；官方接口不返回热度值与回答数，前端在缺省时隐藏这两项。官方接口失败时退回匿名 `api.zhihu.com/topstory/hot-list`。

**直答**：OpenAI Chat Completions 兼容协议，`stream: true` 时逐块返回 `reasoning_content` 与 `content`；知径把两者分别以 `reasoning` / `delta` 事件转发到前端，回答落库为该知识点的对话记录并写入证据链（`engine: zhida`）。

## 4. 额度与缓存策略

- 搜索结果按检索词缓存 7 天、页面正文缓存 30 天（SQLite `kv_cache`），同一目标重复演示不再消耗额度。
- 热榜缓存 30 分钟；直答不缓存（用户主动触发）。
- 生成一张 15 节点左右的图谱约消耗 11-16 次知乎搜索额度；5,000/天足够演示。
- 官方接口报 `30001` 或网络错误时自动降级到搜索引擎兜底，并在服务日志记录 `official zhihu search failed`。

## 5. 与 OAuth 的关系

- 内容接口只需 Access Secret，与知乎账号登录（OAuth）相互独立。
- 登录后读取「授权用户的创作列表 / 关注 / 收藏」需要在同一请求上同时带 Access Secret（`Authorization`）与用户的 OAuth token（`X-OAuth-Token`），接口为 `https://developer.zhihu.com/api/v1/user/...`。知径当前未使用这组接口，见 [zhihu-oauth.md](zhihu-oauth.md) 的路线图。

## 6. 黑客松专属内容接口（无需鉴权）

活动另提供知乎故事与知乎知识内容（`https://api.zhihu.com/km-indep-home/hackathon/v2/{story,knowledge}/list` 与 `story/{work_id}` 详情），不需要任何凭证。知径已验证可访问（知识列表 10 条、故事 20 条），当前未接入产品流程；可作为「知识」类学习素材的候选来源。
