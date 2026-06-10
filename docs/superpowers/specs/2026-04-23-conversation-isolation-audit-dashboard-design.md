# 对话隔离、全量审计与管理面板仪表板

日期: 2026-04-23

## 目标

1. **对话隔离**: 每个用户只能查看和访问自己的对话，不能看到其他用户的对话
2. **全量消息审计**: 超级管理员可查看所有用户的所有对话内容和消息记录
3. **管理面板仪表板**: 增加对话统计图表，支持日期筛选和快捷筛选
4. **存储统一迁移**: LangGraph Checkpointer + Store 从 SQLite 迁移到 PostgreSQL
5. **用户画像独立**: USER.md 从全局单文件改为每用户独立一份

## 当前状态

| 存储 | 现状 | 问题 |
|------|------|------|
| Checkpointer | SQLite (`checkpoints.db`) | 所有用户共用一个文件，随用户量增长性能下降 |
| Store | SQLite（跟随 checkpointer） | 同上 |
| 线程列表 | LangGraph SDK `threads.search`，无用户过滤 | 所有用户看到所有对话 |
| 线程 CRUD | Gateway `/api/threads/*` 无认证 | 任何人都可访问任意对话 |
| 用户画像 | 全局 `{base_dir}/USER.md` | 所有用户共用一个画像 |
| 管理面板仪表板 | 仅用户/部门/技能统计 | 无对话相关功能 |

## 架构设计

### 数据流概览

```
用户请求 → Gateway API
  ├─ 线程创建 → 创建 LangGraph 线程 + 写入 threads 表（绑定 user_id）
  ├─ 线程列表 → 从 threads 表查询（按 user_id 过滤）
  ├─ 线程详情 → 验证 user_id 所有权 → 从 LangGraph Checkpointer 读取完整消息
  ├─ 消息发送 (start_run)
  │    ├─ 记录用户消息 → thread_messages 表
  │    ├─ 执行 agent run（通过 LangGraph）
  │    └─ 流完成后记录 assistant 回复 → thread_messages 表
  ├─ 用户画像 → 每用户独立 USER.md 文件
  └─ 审计/统计 → 直接读 PostgreSQL

管理面板:
  ├─ 仪表板 → 对话统计图表 (ECharts)
  ├─ 对话审计 → 线程列表 + 消息详情查看
  └─ 日期筛选器 + 快捷按钮（7天内/上周/一个月内/半年/一年）
```

### 数据源分工

| 场景 | 数据来源 |
|------|----------|
| 用户历史会话列表 | PostgreSQL `threads` 表（按 user_id 过滤） |
| 用户点进对话看消息/继续聊天 | LangGraph Checkpointer（现有逻辑不变） |
| 管理员审计：对话列表 | PostgreSQL `threads` 表（看全部） |
| 管理员审计：消息详情 | PostgreSQL `thread_messages` 表 |
| 仪表板统计图表 | PostgreSQL 聚合查询 |
| 用户画像读写 | `{base_dir}/profiles/{username}/USER.md` |

### 存储迁移计划

| 存储 | 迁移 | 说明 |
|------|------|------|
| LangGraph Checkpointer | SQLite → PostgreSQL | 配置切换，使用 `langgraph-checkpoint-postgres` |
| LangGraph Store | 自动跟随 checkpointer | 共享 checkpointer 配置 |
| 用户画像 | 全局 `USER.md` → `{base_dir}/profiles/{username}/USER.md` | 路径按用户隔离 |
| 用户记忆 | 已完成 | `{base_dir}/memory/{username}/memory.json` |
| 线程工作目录 | 不动 | 文件系统目录，二进制数据不适合入库 |
| 扩展/MCP 配置 | 不动 | 配置文件性质 |

## 数据模型

### threads 表

```sql
CREATE TABLE threads (
    id VARCHAR(36) PRIMARY KEY,           -- LangGraph thread_id
    user_id VARCHAR(36) NOT NULL,         -- FK → users.id
    title VARCHAR(500),                    -- 对话标题
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active/archived/deleted
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,         -- UTC+8
    updated_at TIMESTAMP NOT NULL,         -- UTC+8
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_threads_user_id ON threads(user_id);
CREATE INDEX idx_threads_created_at ON threads(created_at);
CREATE INDEX idx_threads_status ON threads(status);
```

### thread_messages 表

```sql
CREATE TABLE thread_messages (
    id VARCHAR(36) PRIMARY KEY,
    thread_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,             -- user/assistant/tool/system
    content TEXT,                           -- 消息文本内容
    raw_content JSON,                      -- 原始消息结构（含 tool_calls 等）
    token_count INTEGER,
    created_at TIMESTAMP NOT NULL,          -- UTC+8
    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
);

CREATE INDEX idx_thread_messages_thread_id ON thread_messages(thread_id);
CREATE INDEX idx_thread_messages_created_at ON thread_messages(created_at);
CREATE INDEX idx_thread_messages_role ON thread_messages(role);
```

## 后端改动

### 1. Checkpointer 迁移到 PostgreSQL

**文件**: `config.yaml`，`packages/harness/pyproject.toml`

- 修改 `checkpointer.type` 为 `postgres`
- 修改 `checkpointer.connection_string` 指向 admin PostgreSQL 数据库
- 添加 `langgraph-checkpoint-postgres` 依赖
- 验证 `AsyncPostgresSaver` 和 `AsyncPostgresStore` 的创建和连接

**影响文件**:
- `packages/harness/deerflow/agents/checkpointer/async_provider.py` — 已有 postgres 分支
- `packages/harness/deerflow/runtime/store/async_provider.py` — 已有 postgres 分支
- `langgraph.json` — LangGraph Server 配置

### 2. Thread CRUD 加认证 + 所有权

**文件**: `app/gateway/routers/threads.py`

- 所有端点添加 `current_user: User = Depends(get_current_user)`
- `create_thread`: 创建后写入 `threads` 表，绑定 `user_id`
- `search_threads`: 从 `threads` 表查询，按 `current_user.id` 过滤；超级管理员可看全部
- `get_thread`: 验证 `thread.user_id == current_user.id` 或超级管理员
- `delete_thread`: 验证所有权后软删除（标记 deleted）

### 3. 消息审计双写

**文件**: `app/gateway/services.py`

在 `start_run` 流程中:

1. **运行前**: 记录用户消息到 `thread_messages` 表
   - 从 input messages 中提取最后一条 human message
   - role = "user", content = 消息文本

2. **流完成后**: 记录 assistant 回复到 `thread_messages` 表
   - 从最终状态中提取最后一条 AI message
   - role = "assistant", content = 消息文本, raw_content = 完整消息结构
   - 同步更新 `threads.message_count` 和 `threads.updated_at`

### 4. Thread 审计 API

**文件**: `app/admin/routers/` 新增或扩展

- `GET /api/admin/threads` — 管理员查看所有对话列表（支持分页、按用户/日期筛选）
- `GET /api/admin/threads/{id}` — 管理员查看对话详情
- `GET /api/admin/threads/{id}/messages` — 管理员查看对话消息记录
- `GET /api/admin/threads/stats` — 对话统计数据（按日期聚合）
  - 参数: `start_date`, `end_date`
  - 返回: 每日对话数、每日消息数、活跃用户数

### 5. 用户画像独立

**文件**: `packages/harness/deerflow/config/paths.py`, `app/gateway/routers/agents.py`

- 新增 `user_profile_file(username)` 路径方法 → `{base_dir}/profiles/{username}/USER.md`
- 全局 `USER.md` 改为按用户读取 `{base_dir}/profiles/{username}/USER.md`
- 读取时: 根据当前用户获取路径，文件不存在则返回空字符串
- 写入时: 根据当前用户获取路径，自动创建目录
- `apply_prompt_template` 中注入用户画像时，传入 username 参数

## 前端改动

### 1. 线程列表改为通过 Gateway

**文件**: `frontend/src/core/threads/hooks.ts`

- `useThreads()` 改为调用 Gateway API `/api/threads/search` 而不是 LangGraph SDK `threads.search`
- Gateway 返回的线程已经是按用户过滤后的结果
- 响应格式需要适配现有 `AgentThread` 类型

### 2. 线程 CRUD 请求带认证

**文件**: `frontend/src/core/api/api-client.ts`

- LangGraph SDK client 的请求需要带上 `Authorization` header 或 cookie
- 或者改为所有线程操作都通过 Gateway 代理

### 3. 侧边栏最近对话

**文件**: `frontend/src/components/workspace/recent-chat-list.tsx`

- 同样改为从 Gateway 获取，自动按用户过滤

## 管理面板改动

### 1. 仪表板对话统计

**文件**: `admin/src/pages/dashboard/DashboardPage.tsx`

新增模块:

**统计卡片**:
- 总对话数
- 今日对话数
- 今日消息数
- 活跃用户数

**折线图**（ECharts）:
- X 轴: 日期
- Y 轴: 对话数 / 消息数
- 支持双 Y 轴展示

**日期筛选器**:
- 日期范围选择器（Ant Design RangePicker）
- 快捷按钮: 7天内、上周、一个月内、半年、一年
- 默认展示最近 7 天

### 2. 对话审计页面

**新文件**: `admin/src/pages/threads/`

**ThreadListPage.tsx**:
- 对话列表表格: 标题、所属用户、消息数、创建时间、最后活跃时间
- 支持按用户名搜索
- 支持按日期范围筛选
- 点击行展开查看消息详情

**ThreadMessageDrawer.tsx**:
- 侧边抽屉展示对话的完整消息记录
- 按时间顺序排列
- 区分 user/assistant 消息样式
- 显示 raw_content 中的 tool_calls 信息

### 3. API 和 Hooks

**新文件**: `admin/src/api/threads.ts`
- `getThreadStats(start_date, end_date)` — 获取统计数据
- `getThreads(page, size, user_id, start_date, end_date)` — 获取对话列表
- `getThreadMessages(thread_id)` — 获取对话消息

**新文件**: `admin/src/hooks/useThreads.ts`
- `useThreadStats(dateRange)` — 统计数据 hook
- `useAdminThreads(filters)` — 对话列表 hook

## UI 文本

所有 UI 文本使用中文。示例:

- "对话统计"
- "总对话数"、"今日对话"、"今日消息"、"活跃用户"
- "7天内"、"上周"、"一个月内"、"半年"、"一年"
- "对话审计"
- "对话详情"、"消息记录"
- "所属用户"、"消息数"、"创建时间"、"最后活跃"

## 时间格式

所有时间戳使用 UTC+8（Asia/Shanghai），复用已有的 `now_utc8()` 工具函数。

## 依赖

### 后端新增

- `langgraph-checkpoint-postgres` — PostgreSQL checkpointer（需添加到 pyproject.toml）
- `psycopg` 或 `psycopg2` — PostgreSQL 驱动（可能已有）

### 管理面板新增

- `echarts` + `echarts-for-react` — 图表库
- 无需额外 Ant Design 组件（RangePicker 等已包含在 antd 中）

## 测试要点

1. **对话隔离**: 用户 A 无法看到用户 B 的对话
2. **超级管理员审计**: 超级管理员可以看到所有对话
3. **消息双写**: 发送消息后 PostgreSQL 中有对应的审计记录
4. **统计准确性**: 图表数据与实际对话数一致
5. **PostgreSQL checkpointer**: agent run 正常工作，上下文正确恢复
6. **用户画像隔离**: 不同用户读写各自的 USER.md
7. **日期筛选**: 快捷按钮和自定义日期范围都正确过滤

## 不涉及

- 线程工作目录（uploads/workspace/outputs）的隔离 — 文件系统按 thread_id 天然隔离
- MCP/扩展配置的迁移 — 配置文件性质，不适合入库
- 用户记忆迁移 — 已在之前的迭代中完成
- 前端实时流式响应的修改 — 流式机制不变，只是额外写审计记录
