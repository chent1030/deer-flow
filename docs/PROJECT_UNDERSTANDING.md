# DeerFlow 项目理解

本文档是对当前仓库的代码级理解，用于帮助后续开发快速建立整体心智模型。它以实际代码路径为准，覆盖运行拓扑、后端边界、前端数据流、管理面板、配置与常见开发注意点。

## 1. 项目定位

DeerFlow 是一个全栈 AI 智能体系统：

- 后端由 Python 3.12+ 实现，核心智能体运行在 LangGraph/LangChain 体系内。
- 前端由 Next.js 16 + React 19 + TypeScript 实现，是主要的用户聊天与工作区界面。
- 管理面板是单独的 Vite + React + Ant Design 应用，用于用户、部门、技能审核和线程审计等管理功能。
- nginx 统一暴露 `http://localhost:2026`，按路径把请求分发到前端、Gateway、LangGraph 或管理面板。

系统的核心目标不是单次问答，而是“线程化的智能体工作台”：每个 thread 有独立文件目录、上传文件、输出 artifacts、运行状态、标题、记忆上下文、工具调用和可选的子智能体委托。

## 2. 顶层目录职责

```text
D:\Develop\clerk
|-- backend/                  Python 后端：Gateway、LangGraph agent、harness 包、管理 API、调度与 IM 通道
|-- frontend/                 Next.js 用户端：聊天工作区、artifact 预览、设置、技能、记忆
|-- admin/                    Vite 管理端：用户/部门/技能/线程审计后台
|-- docker/                   nginx、Docker Compose、基础设施与 provisioner
|-- scripts/                  本地启动、配置、Docker、部署脚本
|-- skills/                   面向智能体的 public/custom skills
|-- docs/                     仓库级设计与变更文档
|-- config.yaml               当前本地主配置
|-- config.example.yaml       配置模板和 schema 演进来源
|-- extensions_config*.json   MCP 和技能启用状态配置
|-- Makefile                  根入口命令
```

依赖目录如 `backend/.venv` 不属于项目源代码理解重点。

## 3. 运行拓扑

标准本地模式由 `make dev` 启动，实际调用 `scripts/serve.sh --dev`：

```text
Browser
  |
  v
nginx :2026
  |-- /                      -> frontend :3000
  |-- /api/langgraph/*       -> langgraph :2024
  |-- /api/*                 -> gateway :8001
  |-- /admin                 -> admin dev server :3002 (本地 nginx.local.conf)
```

标准模式包含 4 个主要进程：

- LangGraph Server `:2024`：加载 `backend/langgraph.json`，图入口是 `deerflow.agents:make_lead_agent`。
- Gateway API `:8001`：FastAPI 应用，入口是 `backend/app/gateway/app.py`。
- Frontend `:3000`：Next.js 开发服务器。
- nginx `:2026`：统一入口和 SSE 代理。

Gateway 模式由 `make dev-pro` 启动，跳过独立 LangGraph Server。脚本会把 `frontend/.env.local` 的 `NEXT_PUBLIC_LANGGRAPH_BASE_URL` 指向 `/api/langgraph-compat`，由 Gateway 内嵌的 LangGraph 兼容接口承接运行流。

Docker 模式使用 `docker/docker-compose*.yaml`。生产 nginx 模板支持通过 `LANGGRAPH_UPSTREAM` 和 `LANGGRAPH_REWRITE` 在标准模式和 Gateway 模式之间切换。基础设施 `make infra-up` 只启动 PostgreSQL 和 MinIO。

## 4. 后端分层

后端有明确的 harness/app 分层：

- `backend/packages/harness/deerflow/` 是可发布的 agent harness 包，导入名是 `deerflow.*`。
- `backend/app/` 是应用层，导入名是 `app.*`，包含 Gateway、管理 API 和 IM 通道。

约束是：`app` 可以导入 `deerflow`，但 `deerflow` 不能导入 `app`。这个边界由 `backend/tests/test_harness_boundary.py` 保护。

### 4.1 LangGraph Agent

Agent 工厂在 `backend/packages/harness/deerflow/agents/lead_agent/agent.py`：

- `make_lead_agent(config)` 是 LangGraph 图入口。
- 根据 runtime config 解析模型、thinking、reasoning effort、plan mode、subagent、agent_name、username。
- 通过 `create_chat_model()` 创建模型。
- 通过 `get_available_tools()` 聚合工具。
- 通过 `apply_prompt_template()` 注入系统提示、skills、memory、subagent 说明等。
- 状态 schema 是 `ThreadState`，扩展了 messages 之外的 sandbox、thread_data、title、artifacts、todos、uploaded_files、viewed_images。

实际中间件链由 `build_lead_runtime_middlewares()` 加上 lead-only middlewares 组成，主要包括：

- `ThreadDataMiddleware`：建立 thread 级目录。
- `UploadsMiddleware`：把上传文件状态注入上下文。
- `SandboxMiddleware`：为 thread 获取 sandbox。
- `DanglingToolCallMiddleware`：修复中断后缺失 ToolMessage 的历史。
- `LLMErrorHandlingMiddleware`、`ToolErrorHandlingMiddleware`：把模型或工具异常转成可继续处理的消息。
- `GuardrailMiddleware`：可选工具调用授权。
- `SandboxAuditMiddleware`：记录 sandbox 操作审计。
- `SummarizationMiddleware`：可选上下文压缩。
- `TodoMiddleware`：plan mode 下启用 todo 工具。
- `TokenUsageMiddleware`：可选 token 用量记录。
- `TitleMiddleware`：自动标题。
- `MemoryMiddleware`：异步记忆更新。
- `ViewImageMiddleware`：视觉模型下处理图片。
- `DeferredToolFilterMiddleware`：tool_search 开启时隐藏延迟加载工具 schema。
- `SubagentLimitMiddleware`：限制并发 task 子智能体调用。
- `LoopDetectionMiddleware`：检测重复工具调用循环。
- `ClarificationMiddleware`：拦截澄清请求，必须最后执行。

### 4.2 工具系统

工具聚合入口是 `backend/packages/harness/deerflow/tools/tools.py` 的 `get_available_tools()`：

- 从 `config.yaml` 的 `tools` 读取配置工具，并按 `tool_groups` 或自定义 agent 工具组过滤。
- 本地 sandbox 默认不暴露 host bash，除非安全配置允许。
- 内置工具包括 `present_files`、`ask_clarification`、视觉模型下的 `view_image`。
- ultra/subagent 模式下加入 `task` 委托工具。
- MCP 工具从 `extensions_config.json` 读取，支持缓存和 mtime 失效。
- `tool_search.enabled` 时，MCP 工具可先进入 deferred registry，由 `tool_search` 按需暴露。
- 如果配置了 ACP agents，会加入 `invoke_acp_agent`。

Sandbox 工具在 `backend/packages/harness/deerflow/sandbox/tools.py`，包括 `bash`、`ls`、`glob`、`grep`、`read_file`、`write_file`、`str_replace`。本地 sandbox 会做虚拟路径到真实路径的转换，并将错误输出中的宿主机路径重新 mask 成虚拟路径。

### 4.3 文件与 sandbox

Agent 看到的主要虚拟路径：

```text
/mnt/user-data/workspace
/mnt/user-data/uploads
/mnt/user-data/outputs
/mnt/skills
/mnt/acp-workspace
```

实际 thread 数据位于 `backend/.deer-flow/threads/{thread_id}/user-data/...`。`ThreadDataMiddleware` 和 sandbox 工具共同维护这套路径映射。输出 artifacts 主要从 outputs 目录通过 Gateway 暴露。

Sandbox Provider 抽象位于 `deerflow/sandbox/`：

- local provider 使用宿主文件系统。
- community provider 支持 Docker/aio sandbox。
- provisioner/Kubernetes 模式由 Docker 配置和 `docker/provisioner` 支撑。

### 4.4 Gateway API

FastAPI 应用入口是 `backend/app/gateway/app.py`。启动时会：

- 加载 `config.yaml`。
- 初始化 admin 数据库 session factory 和 MinIO client。
- 初始化 Gateway 内嵌 LangGraph runtime 所需的 `StreamBridge`、checkpointer、store、`RunManager`。
- 启动 IM channel service。
- 启动 scheduler，并从数据库加载 enabled scheduled tasks。

主要 router 位于 `backend/app/gateway/routers/`：

- `models.py`：模型列表和详情。
- `mcp.py`：MCP 配置读取/更新。
- `skills.py`：技能列表、启用状态、安装。
- `memory.py`：记忆读取、导入导出、facts 增删改、状态。
- `uploads.py`：thread 文件上传、列表、删除，支持文档转换。
- `artifacts.py`：thread artifacts 访问。
- `threads.py`：thread 搜索、历史、删除本地 thread 数据、审计记录等。
- `agents.py`：自定义 agent 管理。
- `suggestions.py`：后续问题建议。
- `channels.py`：IM 通道管理。
- `scheduler.py`：定时任务 API。
- `thread_runs.py` 和 `runs.py`：LangGraph Platform 兼容的 runs create/stream/wait/cancel/join。
- `assistants_compat.py`：LangGraph assistant 兼容接口。

注意：前端主要通过 nginx 访问 `/api/*`。认证相关请求由前端和 Gateway 共同处理，普通用户端请求使用 cookie，管理端使用 JWT。

### 4.5 管理、调度与 IM

`backend/app/admin/` 是管理后台后端：

- SQLAlchemy async models：用户、部门、技能、线程审计、定时任务等。
- JWT 登录刷新在 `/api/admin/auth/*`。
- PostgreSQL 默认连接来自 `config.yaml` 的 `admin.database_url`。
- MinIO 配置用于技能等对象存储能力。

`deerflow/scheduler/` 和 Gateway lifespan 共同支撑定时任务。`app/channels/` 支持 Feishu、Slack、Telegram、WeCom 等 IM 通道，通过 LangGraph/Gateway URL 和消息总线桥接外部聊天平台。

## 5. 前端用户端

前端源代码在 `frontend/src/`：

- `app/`：Next.js App Router。
- `components/`：UI 组件、workspace 组件、AI elements。
- `core/`：业务逻辑核心，包括 threads、api、uploads、skills、memory、agents、scheduler、settings、messages。
- `hooks/`、`lib/`、`styles/`：共享 hooks、工具和全局样式。

主要页面：

```text
/                                      首页
/workspace                             工作区入口
/workspace/chats/[thread_id]           默认 agent 的聊天线程
/workspace/agents                      自定义 agents 列表
/workspace/agents/new                  创建 agent
/workspace/agents/[agent]/chats/[id]   指定 agent 的聊天线程
/[lang]/docs/...                       文档页面
```

### 5.1 LangGraph 客户端

`frontend/src/core/api/api-client.ts` 创建单例 LangGraph SDK client：

- base URL 来自 `getLangGraphBaseURL()`。
- 默认浏览器环境下是当前 origin 的 `/api/langgraph`。
- mock 模式使用 `/mock/api`。
- Gateway 模式由脚本写入 `/api/langgraph-compat`。
- 对 SDK 的 stream/joinStream options 做兼容清洗。
- 非 mock 模式下重写 `threads.getHistory()`，改走 Gateway 的 `/api/threads/{id}/history`。

### 5.2 聊天流

核心 hook 是 `frontend/src/core/threads/hooks.ts` 的 `useThreadStream()`：

1. `useStream()` 连接 LangGraph SDK。
2. 用户发送消息前先处理本地 optimistic message。
3. 如果有附件，先通过 `/api/threads/{id}/uploads` 上传，转成虚拟路径 metadata。
4. `thread.submit()` 提交 human message。
5. context 中注入当前模式：
   - `flash` 关闭 thinking。
   - `pro` / `ultra` 启用 plan mode。
   - `ultra` 启用 subagent。
   - reasoning effort 根据模式设置。
   - 传入 `thread_id`、`username`、可见技能列表。
6. SSE 更新 messages、title、artifacts、todos 和 custom events。
7. 完成后刷新 thread 列表并记录审计。

线程列表和删除也在该文件中：

- `useThreads()` 调 Gateway `/api/threads/search`。
- `useDeleteThread()` 先删 LangGraph thread，再删 DeerFlow 本地 thread 目录。
- `useRenameThread()` 通过 LangGraph SDK 更新 state 中的 title。

### 5.3 用户端认证和 API

`frontend/src/core/api/auth-fetch.ts` 是用户端通用 fetch 包装：

- 相对路径请求默认走当前 origin。
- 自动带 `credentials: "include"`。
- 默认补 `Content-Type: application/json`。
- 401 时调用 `/api/logout` 并跳回 `/`。

`frontend/src/env.js` 使用 `@t3-oss/env-nextjs` 校验环境变量。生产构建需要 `BETTER_AUTH_SECRET`，除非使用 `SKIP_ENV_VALIDATION=1`。

## 6. 管理面板

管理面板在 `admin/`，是独立 Vite 应用：

- 技术栈：React 19、React Router 7、Ant Design 6、TanStack Query、Zustand、Axios。
- 本地开发端口在 `admin/vite.config.ts` 中是 `3002`。
- `make admin-dev` 直接运行 `pnpm dev`。
- 本地 nginx 的 `/admin` 会代理到 `127.0.0.1:3002`。

主要路由在 `admin/src/App.tsx`：

- `/login`
- `/admin/dashboard`
- `/admin/users`
- `/admin/skills`
- `/admin/skills/review`
- `/admin/departments`
- `/admin/threads`

管理端 API client 在 `admin/src/api/client.ts`：

- JWT 存在 `localStorage.access_token` 和 `refresh_token`。
- 请求自动加 `Authorization: Bearer ...`。
- 401 时调用 `/api/admin/auth/refresh` 刷新 token，失败则回 `/login`。

## 7. 配置模型

主配置文件是 `config.yaml`，由 `deerflow.config.app_config.AppConfig` 加载。解析优先级：

1. 显式传入路径。
2. `DEER_FLOW_CONFIG_PATH`。
3. `backend/config.yaml`。
4. 仓库根目录 `config.yaml`。

配置值如果以 `$` 开头，会解析为环境变量。`get_app_config()` 带缓存，并在配置文件 mtime 变化时自动重载。

重要配置区块：

- `models`：模型列表、provider class、API key、thinking/vision 支持。
- `sandbox`：sandbox provider、mounts、输出截断、安全开关。
- `tools` / `tool_groups`：工具注册和分组。
- `skills`：skills 宿主路径和容器路径。
- `skill_evolution`：agent 管理技能的能力开关。
- `tool_search`：延迟工具搜索。
- `title`：自动标题。
- `summarization`：上下文摘要。
- `memory`：记忆存储、注入、facts 限制。
- `subagents`：子智能体运行配置。
- `guardrails`：工具授权策略。
- `checkpointer` / `stream_bridge`：运行状态与流桥实现。
- `admin`：PostgreSQL、MinIO、JWT、初始管理员。

扩展配置是 `extensions_config.json`，由 `ExtensionsConfig` 单独加载，主要包含：

- `mcpServers`：MCP server 定义和启用状态。
- `skills`：技能启用状态。

## 8. 数据与持久化

项目同时使用文件系统和数据库：

- `backend/.deer-flow/threads/{thread_id}`：thread 本地工作目录、上传和输出。
- `backend/.deer-flow/memory.json`：默认记忆文件。
- `.langgraph_api` 或配置的 checkpointer/store：LangGraph checkpoint/state。
- PostgreSQL：管理用户、部门、技能审核、线程审计、定时任务。
- MinIO：管理面板相关对象存储。

上传文件经 Gateway 进入 thread 的 uploads 目录，Office/PDF 等文档会通过 harness 上传管理器转换为 Markdown 或可读格式，再由 `UploadsMiddleware` 放入上下文。

Artifacts 由 agent 写入 outputs 目录，再通过 Gateway artifact endpoint 暴露。主动内容类型如 HTML/SVG 会强制下载以降低 XSS 风险。

## 9. 开发与验证

根目录常用命令：

```bash
make check
make install
make dev
make dev-pro
make stop
make infra-up
make infra-down
```

后端：

```bash
cd backend
make lint
make test
make dev
make gateway
```

前端：

```bash
cd frontend
pnpm lint
pnpm typecheck
pnpm build
```

管理面板：

```bash
make admin-install
make admin-dev
make admin-build
make db-migrate
make db-seed
```

当前项目说明中特别强调：前端不要依赖 `pnpm check`，提交前分别跑 `pnpm lint && pnpm typecheck`。

## 10. 容易误判的点

- `backend/README.md` 中仍有旧的 `src/` 结构描述，实际后端代码是 `app/` + `packages/harness/deerflow/`。
- 根 AGENTS 里写管理面板端口为 5173，但实际 `admin/vite.config.ts` 是 3002，本地 nginx 也代理到 3002。
- Gateway 不只是“辅助 REST API”，现在也包含 LangGraph Platform 兼容 runs runtime，可在 Gateway 模式下承接 agent 执行。
- 本地标准 nginx 配置有 `/api/langgraph-compat/`，用于 Gateway 模式；生产 Docker nginx 模板用环境变量控制 `/api/langgraph/` 的上游和 rewrite。
- LocalSandboxProvider 下默认不暴露 host bash，bash 工具是否可用取决于 sandbox 安全配置。
- `make config` 不是幂等操作，已有 `config.yaml` 时会中止；升级字段应用 `make config-upgrade`。
- `config.yaml` 变更可被自动 mtime reload，但环境变量缺失会在解析 `$VAR` 时直接报错。
- 前端聊天上传依赖已有 thread id；新建聊天带文件时需要注意 thread 创建和上传顺序。

## 11. 推荐阅读入口

后续改动前建议优先看这些文件：

- `Makefile`
- `scripts/serve.sh`
- `docker/nginx/nginx.local.conf`
- `backend/langgraph.json`
- `backend/app/gateway/app.py`
- `backend/app/gateway/routers/`
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
- `backend/packages/harness/deerflow/tools/tools.py`
- `backend/packages/harness/deerflow/sandbox/tools.py`
- `backend/packages/harness/deerflow/config/app_config.py`
- `frontend/src/core/threads/hooks.ts`
- `frontend/src/core/api/api-client.ts`
- `frontend/src/core/config/index.ts`
- `admin/src/App.tsx`
- `admin/src/api/client.ts`
