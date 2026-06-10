# DeerFlow 开发指南

全栈 AI 超级智能体框架。后端：Python 3.12+ (LangGraph + FastAPI)。前端：Next.js 16 + React 19 (TypeScript)。统一入口：通过 nginx 访问 `http://localhost:2026`。

## 快速开始

```bash
make config      # 首次设置：从模板创建 config.yaml（如已存在则中止）
make install     # 安装后端 + 前端依赖
make dev         # 启动所有服务（4个进程：langgraph, gateway, frontend, nginx）
make stop        # 停止所有服务
```

访问地址：`http://localhost:2026`

## 前置要求

- Node.js 22+
- pnpm 10.26.2+
- Python 3.12+
- `uv` 包管理器
- `nginx`（统一 localhost:2026 入口所需）

验证命令：`make check`

## 命令

### 根目录（完整应用）

| 命令 | 描述 |
|---------|-------------|
| `make config` | 生成 config.yaml（仅首次使用；如已存在则中止） |
| `make config-upgrade` | 将 config.example.yaml 的新字段合并到 config.yaml |
| `make check` | 验证所有前置要求 |
| `make install` | 安装后端 + 前端依赖 |
| `make dev` | 以开发模式启动所有服务（热重载） |
| `make dev-pro` | 开发 + Gateway 模式（实验性，3个进程，无 LangGraph 服务器） |
| `make stop` | 停止所有运行中的服务 |
| `make docker-init` | 拉取沙箱容器镜像 |
| `make docker-start` | 启动 Docker 开发环境 |
| `make docker-stop` | 停止 Docker 开发环境 |
| `make up` | 生产环境 Docker 构建 + 启动 |
| `make down` | 停止生产环境 Docker 容器 |

### 后端目录

在 `backend/` 目录下运行：

```bash
make lint        # Ruff 代码检查
make test        # 运行所有测试（pytest）
make dev         # 仅启动 LangGraph 服务器（端口 2024）
make gateway     # 仅启动 Gateway API（端口 8001）
```

### 前端目录

在 `frontend/` 目录下运行：

```bash
pnpm lint        # ESLint 检查
pnpm typecheck   # TypeScript 类型检查
pnpm build       # 生产构建（需要 BETTER_AUTH_SECRET）
pnpm dev         # 开发服务器（端口 3000）
```

**重要提示**：`pnpm check` 当前已损坏。请分别运行 `pnpm lint && pnpm typecheck`。

### 管理面板

在根目录运行：

| 命令 | 描述 |
|---------|-------------|
| `make admin-install` | 安装管理面板依赖 |
| `make admin-dev` | 启动管理面板开发服务器（端口 5173） |
| `make admin-build` | 构建管理面板生产版本 |
| `make db-migrate` | 运行数据库迁移（Alembic） |
| `make db-seed` | 填充管理面板初始数据 |
| `make infra-up` | 仅启动 PostgreSQL + MinIO（本地开发用） |
| `make infra-down` | 停止 PostgreSQL + MinIO |

管理面板通过 nginx 在 `/admin` 路径下统一访问。

Docker 环境（开发/生产）包含 PostgreSQL（端口 5432）和 MinIO（端口 9000/9001）服务。

## 验证工作流

提交更改前：

1. **后端**：`cd backend && make lint && make test`
2. **前端**：`cd frontend && pnpm lint && pnpm typecheck`
3. **前端构建**（如果修改了 env/routing/auth）：`BETTER_AUTH_SECRET=local-dev-secret pnpm build`

CI 通过 `.github/workflows/backend-unit-tests.yml` 在每个 PR 上运行后端 lint + 测试。

## 架构

### 运行模式

- **标准模式** (`make dev`)：LangGraph 服务器 (2024) + Gateway API (8001) + 前端 (3000) + Nginx (2026)
- **Gateway 模式** (`make dev-pro`，实验性)：Gateway 内嵌智能体运行时 + 前端 (3000) + Nginx (2026)

Nginx 路由：
- `/api/langgraph/*` → LangGraph 服务器（标准模式）或 Gateway（Gateway 模式）
- `/api/*`（其他） → Gateway API
- `/`（非 API） → 前端

### 后端结构

- `packages/harness/deerflow/` — 可发布的智能体框架（导入：`deerflow.*`）
- `app/` — 应用层（导入：`app.*`）：FastAPI Gateway + IM 通道
- **依赖规则**：App 导入 deerflow，但 deerflow 永远不导入 app。由 CI 中的 `tests/test_harness_boundary.py` 强制执行。

核心组件：
- `deerflow/agents/lead_agent/` — 主智能体工厂 + 系统提示
- `deerflow/agents/middlewares/` — 12个中间件组件（线程、沙箱、记忆等）
- `deerflow/sandbox/` — 沙箱执行（本地/Docker 提供者）
- `deerflow/subagents/` — 子智能体委托系统
- `app/gateway/` — FastAPI API（模型、MCP、技能、记忆、上传、制品、线程）

### 前端结构

- `src/app/` — Next.js App Router 页面
- `src/components/` — UI 组件（`ui/`、`workspace/`、`ai-elements/`）
- `src/core/` — 业务逻辑（线程、api、制品、设置、记忆、技能）
- `src/hooks/` — 自定义 React hooks

核心模式：
- 线程 hooks（`core/threads/hooks.ts`）是主要的 API 接口
- LangGraph 客户端是通过 `core/api/` 中的 `getAPIClient()` 获取的单例
- 默认使用服务器组件，仅交互式组件使用 `"use client"`

## 配置

### config.yaml（项目根目录）

主配置文件。设置：

```bash
make config  # 从 config.example.yaml 创建 config.yaml
```

优先级：`DEER_FLOW_CONFIG_PATH` 环境变量 → 当前目录的 `config.yaml` → 父目录的 `config.yaml`（推荐）

核心部分：
- `models[]` — LLM 配置，包含 `use` 类路径、`supports_thinking`、`supports_vision`
- `sandbox.use` — 沙箱提供者类路径
- `tools[]` / `tool_groups[]` — 工具配置
- `memory` — 记忆系统设置

配置中的环境变量：`$OPENAI_API_KEY` 等

配置缓存：文件更改时自动重新加载（开发中无需重启）。

### extensions_config.json（项目根目录）

MCP 服务器和技能配置。

优先级：`DEER_FLOW_EXTENSIONS_CONFIG_PATH` 环境变量 → 当前目录的 `extensions_config.json` → 父目录（推荐）

## 不易察觉的陷阱

1. **`make config` 非幂等**：如果 config.yaml 已存在则中止。仅用于首次设置。
2. **前端构建需要 BETTER_AUTH_SECRET**：设置环境变量或使用 `SKIP_ENV_VALIDATION=1`（不推荐）。
3. **代理环境变量可能破坏前端安装**：如果 `pnpm install` 因代理错误失败，请取消设置代理变量后重试。
4. **Docker 开发模式感知**：`make docker-start` 读取 `config.yaml`，仅在使用 Kubernetes 沙箱模式时启动 provisioner。
5. **Gateway 模式是实验性的**：`make dev-pro` 将智能体运行时嵌入 Gateway，移除 LangGraph 服务器进程。

## 子智能体说明

详细架构请参考：
- 后端：`backend/CLAUDE.md`
- 前端：`frontend/CLAUDE.md`
