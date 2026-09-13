<h1 align="center">知径 LearnWay</h1>
<p align="center"><strong>把知乎的高赞回答，变成你的学习路径。</strong></p>
<p align="center">知乎黑客松 2026 · 校园新锐季 · 方向二「知识炼金场：学习工具与知识生产」参赛作品</p>
<p align="center">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/LLM-Claude%20%7C%20OpenAI--compatible-8A2BE2">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-2EA44F">
</p>

---

## 这是什么

知乎上沉淀了海量「把一个领域讲透」的高赞回答与专栏，但它们是**离散的**：搜到十篇好文章，仍然不知道先看哪篇、看完了算不算懂、下一步学什么。

**知径 LearnWay** 把它们变成**结构化、可验证、会成长**的学习路径：

1. **说出目标** —— 「我想搞懂 Transformer，能读懂论文和源码」，加上你的基础和时间预算。
2. **生成知识图谱** —— AI 把目标拆成模块 → 知识点，标出前置关系、难度和预计时长，画成可视化图谱。
3. **知乎来源锚定** —— 每个知识点自动检索知乎高赞回答与专栏，读取全文，作为讲解和出题的**证据**。
4. **带引用的讲解** —— 定义 → 直觉 → 要点 → 误区 → **知乎观点对照** → 自检，每句话都能点回原文。
5. **证据驱动的掌握度** —— 3 道单选 + 1 道费曼解释题（AI 评分），形成证据链，更新 ★☆☆ 星级。
6. **推荐下一步** —— 按前置关系、掌握度和时间预算推荐「现在最值得学的知识点」。
7. **一键沉淀** —— 复习卡片、追问答疑、导出 Markdown 学习清单（含全部知乎链接）。
8. **从热榜出发** —— 首页接入知乎热榜，一键「学热点背后的知识」（把新闻事件转化为知识领域的学习路线）。

设计参考了开源项目 [LearnGraph](https://github.com/SunnyBoy-y/LearnGraph) 的 **G-R-E-M-A 学习闭环**（Goal → Representation → Evidence → Mastery → Action），并把「知乎内容」作为整个闭环的证据底座。

```text
学习目标 ──► 知识图谱（模块/知识点/前置关系）──► 知乎来源锚定（搜索 + 全文）
    ▲                                                     │
    │                                                     ▼
 下一步推荐 ◄── 掌握度（星级/证据链） ◄── 讲解 · 测验 · 费曼解释 · 卡片 · 追问
```

## 产品截图

| 首页：目标输入 · 知乎热榜 | 知识图谱工作台 |
| --- | --- |
| ![首页](docs/screenshots/01-home.png) | ![图谱](docs/screenshots/03-graph.png) |

| 带引用的讲解 | 知乎来源 |
| --- | --- |
| ![讲解](docs/screenshots/05-lesson.png) | ![来源](docs/screenshots/06-sources.png) |

| 小测验与费曼评分 | 复习卡片 |
| --- | --- |
| ![测验](docs/screenshots/08-quiz-result.png) | ![卡片](docs/screenshots/09-cards.png) |

> 截图由 `cd frontend && npm run screenshot` 在离线演示模式下自动生成（Playwright），知乎来源为真实检索结果。

## 快速开始

环境：Python 3.11+、Node.js 20+。推荐用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖。

```bash
git clone <this repo> learnway && cd learnway

# 1) 后端
cd backend
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env            # 按需填写 LLM / 知乎开放平台配置（见下）
.venv/bin/uvicorn app.main:app --port 8000 --reload

# 2) 前端（另一个终端）
cd frontend && npm install && npm run dev      # http://127.0.0.1:5173
```

或者一条命令同时启动两端：`./scripts/dev.sh`。

生产形态（单进程、单端口）：`./scripts/build.sh` 构建前端后，FastAPI 会在 `http://127.0.0.1:8000` 同时提供页面与 `/api`。也可以 `docker compose up --build`。

| 地址 | 说明 |
| --- | --- |
| `http://127.0.0.1:5173` | 开发模式前端（代理 `/api` 到 8000） |
| `http://127.0.0.1:8000` | 生产模式单入口（需先构建前端） |
| `http://127.0.0.1:8000/docs` | OpenAPI 文档 |
| `http://127.0.0.1:8000/api/health` | 当前 LLM / 知乎数据通道状态 |

### 配置 LLM

`backend/.env`（前缀 `LEARNWAY_`）：

| 变量 | 说明 |
| --- | --- |
| `LEARNWAY_LLM_PROVIDER` | `auto`（默认）/ `anthropic` / `openai` / `mock` |
| `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL` | 官方 Anthropic SDK 读取；`LEARNWAY_ANTHROPIC_MODEL` 默认 `claude-opus-5` |
| `LEARNWAY_ANTHROPIC_BETAS` | 某些中转需要的 beta 头，如 `context-1m-2025-08-07` |
| `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LEARNWAY_OPENAI_MODEL` | 任意 OpenAI 兼容接口（DeepSeek / Qwen / Kimi / Ollama…） |

`mock` 模式不需要任何 key：图谱、讲解、测验、卡片都用本地占位内容生成，但**知乎检索与全文读取仍是真实的**，方便离线演示交互流程。

### 配置知乎数据通道

| 通道 | 默认 | 说明 |
| --- | --- | --- |
| 知乎数据开放平台（官方） | 未配置 | 黑客松提供的接口。填写 `LEARNWAY_ZHIHU_OPEN_API_BASE` / `LEARNWAY_ZHIHU_OPEN_API_KEY` 后自动优先使用；接口字段映射集中在 `backend/app/zhihu/official.py`，拿到开发者手册后只需调整这一个文件。 |
| 知乎热榜 | 启用 | `api.zhihu.com/topstory/hot-list`，10 分钟缓存 |
| 站内搜索兜底 | `brave,bing` | 通过搜索引擎的 `site:zhihu.com` 检索，只保留问题 / 回答 / 专栏页面 |
| 全文读取 | Jina Reader | `LEARNWAY_READER_BASE`，可选 `JINA_API_KEY` 提高配额 |

所有检索结果与页面正文都会缓存在 SQLite（`backend/data/learnway.db`），重复演示不再发网络请求。

### 知乎账号登录（OAuth，测试状态）

支持用知乎账号登录（标准 OAuth 2.0 授权码流程），端点与 client 全部走配置；未配置时登录入口自动隐藏。配置项、接口、字段映射与待确认清单见 [docs/zhihu-oauth.md](docs/zhihu-oauth.md)。

## 技术架构

```text
frontend/  React 19 + TypeScript + Vite + Tailwind v4
           ├─ pages/Home           目标输入 · 知乎热榜 · 我的路径
           ├─ pages/GraphPage      图谱工作台（轮询生成进度 · 下一步推荐 · 导出）
           ├─ components/graph     React Flow + dagre 自动布局的知识图谱
           └─ components/panel     讲解(SSE 流式+引用角标) · 知乎来源 · 小测验 · 复习卡片 · 追问

backend/   FastAPI + SQLAlchemy(SQLite WAL) + Anthropic SDK
           ├─ api/routes.py        REST + SSE 接口
           ├─ services/graph_builder   目标 → 结构化图谱（LLM structured output）→ 后台流水线
           ├─ services/grounding       每个知识点：检索 → 去重 → 读取全文 → 关联来源（线程池 + 缓存）
           ├─ services/learning        讲解 / 出题 / 费曼评分 / 卡片 / 答疑 / Markdown 导出
           ├─ services/progress        掌握度星级 · 前置解锁 · 下一步推荐（G-R-E-M-A 的 M 与 A）
           ├─ services/oauth           知乎 OAuth 授权码流程（测试状态）· 签名 state · 会话
           ├─ llm/                     Provider 抽象：Anthropic（官方 SDK）· OpenAI 兼容 · Mock
           └─ zhihu/                   official（开放平台）· search（Brave/Bing site:zhihu.com）· reader（Jina）· hot（热榜）
```

关键设计：

- **证据优先**：讲解、出题、评分的 prompt 都只拿到「编号化的知乎来源」，输出必须用 `[n]` 引用；前端把角标渲染成可点回原文的链接，保证「AI 说的每句话都能溯源」。
- **掌握度是算出来的，不是宣称的**：单选题本地判分、费曼解释由模型按「定义 / 例子 / 机制」三维打分，加权后做指数平滑，映射到 0-3 星；模块星级由子节点聚合。
- **软解锁**：前置知识点未入门的节点会标注「建议先学 …」，但不阻止学习者跳读。
- **可替换的模型与数据通道**：LLM 与知乎数据源都是端口-适配器结构；官方开放平台接口一旦可用，只改一个文件。
- **离线可演示**：Mock LLM + SQLite 缓存，让流程在无 key、弱网环境下也能完整跑通。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/goals` | 创建学习目标，后台生成图谱并锚定知乎来源 |
| GET | `/api/graphs/{id}` | 图谱、节点、边、统计、下一步推荐（生成中可轮询进度） |
| GET | `/api/graphs/{id}/export.md` | 导出 Markdown 学习清单 |
| GET | `/api/nodes/{id}` | 知识点详情：来源、讲解、证据、对话、卡片、前置 |
| POST | `/api/nodes/{id}/lesson` | SSE 流式讲解（带引用） |
| POST | `/api/nodes/{id}/quiz` → `/api/quizzes/{id}/submit` | 出题与评分，更新掌握度 |
| POST | `/api/nodes/{id}/cards` | 复习卡片 |
| POST | `/api/nodes/{id}/chat` | SSE 流式追问 |
| POST | `/api/nodes/{id}/ground` | 重新检索该知识点的知乎来源 |
| GET | `/api/hot` | 知乎热榜 |
| GET/POST | `/api/auth/me` · `/api/auth/zhihu/login` · `/api/auth/zhihu/callback` · `/api/auth/logout` | 知乎 OAuth 登录（测试状态，见 docs/zhihu-oauth.md） |
| GET | `/api/health` | 运行状态 |

## 测试

```bash
cd backend && .venv/bin/python -m pytest -q     # 10 个用例：知乎解析器 + 端到端学习流程（mock LLM，无网络）
cd frontend && npm run typecheck && npm run build
```

## 路线图

- 接入知乎数据开放平台的正式接口（知乎搜索 / 知乎知识 / 直答 Agent）替换搜索引擎兜底
- 多 Agent 协作：资料整理 Agent + 观点对照 Agent + 出题 Agent 并行工作
- 学习状态随时间衰减、复习提醒（间隔重复）
- 图谱人在回路修订：拖拽增删节点、审核 AI 的更新建议
- 移动端与刘看山 IP 形象的学习陪伴

## 致谢

- [LearnGraph](https://github.com/SunnyBoy-y/LearnGraph)（MIT）：G-R-E-M-A 学习闭环、目标图谱 / 能力图谱的产品思路
- 知乎社区的每一位认真回答问题的人

MIT License.
