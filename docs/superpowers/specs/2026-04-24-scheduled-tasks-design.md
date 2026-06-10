# 定时任务功能设计

## 概述

用户可以在主前端设置面板中创建定时任务。定时任务绑定一个自动创建的 Agent 和一个用户可见的技能，按 Cron 表达式周期性执行。执行结果（完整对话记录）在任务详情页查看。

## 方案选择

**APScheduler + langgraph-sdk**（嵌入 Gateway 进程）

- APScheduler `AsyncIOScheduler` 运行在 Gateway 进程内
- 通过 `langgraph-sdk` 调用 LangGraph Server（与前端同路径）
- `max_instances=1` 实现跳过并发
- 无需引入新依赖（Redis/Celery 等）

## 数据模型

### `scheduled_tasks`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 任务 ID |
| `user_id` | FK → users.id | 所属用户，任务间隔离 |
| `agent_name` | VARCHAR | 自动生成的 Agent 名称，格式 `sched-{task_id[:8]}` |
| `agent_description` | TEXT | Agent 描述 |
| `agent_soul` | TEXT | SOUL.md 内容（用户填写的提示词，支持 `{{变量}}` 模板语法） |
| `skill_name` | VARCHAR | 绑定的技能名（从用户可见技能中选择） |
| `cron_expression` | VARCHAR | Cron 表达式 |
| `custom_variables` | JSONB | 用户自定义变量 `{"key": "value"}`，默认 `{}` |
| `is_enabled` | BOOLEAN DEFAULT true | 启用/停用 |
| `status` | ENUM(active, paused, error) | 当前状态 |
| `last_execution_at` | TIMESTAMP | 上次执行时间 |
| `next_execution_at` | TIMESTAMP | 下次预计执行时间 |
| `error_message` | TEXT | 最近一次错误信息 |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

### `task_executions`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 执行 ID |
| `task_id` | FK → scheduled_tasks.id, ON DELETE CASCADE | 关联任务 |
| `status` | ENUM(running, completed, failed, skipped) | 执行状态 |
| `triggered_at` | TIMESTAMP | 触发时间 |
| `completed_at` | TIMESTAMP | 完成时间 |
| `thread_id` | VARCHAR | LangGraph 线程 ID |
| `messages` | JSONB | 完整对话记录（所有 Human/AI/Tool 消息） |
| `error_message` | TEXT | 错误信息 |
| `token_usage` | JSONB | Token 用量统计 |

### 设计要点

- Agent 与任务强绑定：删除任务时连同 Agent 目录一起删除
- `skipped` 状态记录"因上次未完成而跳过"
- `messages` 存 JSONB，独立于 Thread/ThreadMessage 表
- 内置模板变量不存 DB，执行时动态生成

## 后端架构

### 目录结构

```
backend/
├── packages/harness/deerflow/
│   └── scheduler/
│       ├── __init__.py
│       ├── manager.py          # SchedulerManager 单例
│       ├── executor.py         # 任务执行器
│       └── template_engine.py  # 模板变量替换
├── app/
│   ├── admin/models/
│   │   └── scheduled_task.py   # SQLAlchemy models
│   ├── admin/services/
│   │   └── scheduler_service.py # CRUD + 启停逻辑
│   └── gateway/routers/
│       └── scheduler.py        # REST API
```

### SchedulerManager

- **初始化时机**：Gateway `lifespan` 事件中创建 `AsyncIOScheduler`
- **启动加载**：查询所有 `is_enabled=True` 的任务，注册到 APScheduler
- **`max_instances=1`**：每个任务同一时间只允许一个实例
- **`misfire_grace_time=60`**：超过 60s 的错过触发直接跳过

### 执行流程

```
Cron 触发
  → executor.execute_task(task_id)
    → 1. 检查是否存在 status=running 的执行记录 → 是则标记 skipped 并返回
    → 2. 创建 task_execution 记录（status=running）
    → 3. 替换模板变量（内置 + custom_variables）
    → 4. langgraph-sdk 创建 thread，发送消息（含 visible_skills）
    → 5. 等待完成，拉取完整 messages
    → 6. 更新 task_execution（status=completed, messages, token_usage）
    → 7. 更新 scheduled_task（last_execution_at, next_execution_at）
    → 8. [TODO] 调用通知 API
```

### 模板变量引擎

内置变量（执行时动态生成）：

| 变量 | 示例值 |
|------|--------|
| `{{date}}` | `2026-04-24` |
| `{{datetime}}` | `2026-04-24 14:30:00` |
| `{{time}}` | `14:30:00` |
| `{{day_of_week}}` | `周五` |
| `{{user_name}}` | 用户名 |

替换规则：
1. 先替换内置变量
2. 再替换自定义变量（可覆盖内置）
3. 未匹配的 `{{xxx}}` 保留原文

### langgraph-sdk 调用

```python
from langgraph_sdk import get_client

client = get_client(url="http://localhost:2024")
thread = await client.threads.create()
run = await client.runs.wait(
    thread_id=thread["thread_id"],
    assistant_id="lead-agent",
    input={"messages": [{"role": "user", "content": rendered_prompt}]},
    config={"configurable": {
        "agent_name": task.agent_name,
        "visible_skills": visible_skill_names,
    }}
)
messages = await client.threads.get_state(thread["thread_id"])
```

### REST API

`/api/scheduler/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scheduler/tasks` | 列出当前用户的定时任务 |
| POST | `/api/scheduler/tasks` | 创建任务（同时创建 Agent） |
| GET | `/api/scheduler/tasks/{id}` | 获取任务详情 |
| PUT | `/api/scheduler/tasks/{id}` | 更新任务 |
| DELETE | `/api/scheduler/tasks/{id}` | 删除任务（同时删除 Agent） |
| POST | `/api/scheduler/tasks/{id}/toggle` | 启用/停用切换 |
| POST | `/api/scheduler/tasks/{id}/trigger` | 手动立即触发一次 |
| GET | `/api/scheduler/tasks/{id}/executions` | 执行历史列表 |
| GET | `/api/scheduler/tasks/{id}/executions/{eid}` | 单次执行详情（含完整对话） |

所有端点需要认证，且只能操作当前用户的任务。

## 前端设计

### 入口

在主前端设置对话框中新增 **"定时任务"** 标签页（`scheduler`），排在"技能"之后，图标 `ClockIcon`。

### 标签页内容

**默认视图**：任务列表

| 列 | 说明 |
|------|------|
| 提示词摘要 | agent_description 截断展示 |
| 技能 | 绑定的技能名 |
| Cron | 表达式 + 人话描述（`cronstrue` 库） |
| 状态 | active / paused / error 标签 |
| 上次执行 | 时间 + 状态图标 |
| 下次执行 | 预计触发时间 |
| 操作 | 启停、手动触发、编辑、删除 |

底部：`+ 新建定时任务` 按钮

**创建/编辑**：在面板内展开表单

- 提示词（textarea，支持 `{{变量}}` 语法高亮）
- 技能选择（下拉列表，来自 `GET /api/skills`）
- Cron 表达式（输入框 + 预设快捷按钮 + 人话预览）
- 自定义变量（动态键值对列表）
- 模板预览（实时渲染替换效果）

**执行历史**：点击任务展开执行列表

| 列 | 说明 |
|------|------|
| 触发时间 | triggered_at |
| 状态 | running / completed / failed / skipped |
| 耗时 | completed_at - triggered_at |
| 操作 | 查看详情 |

**执行详情**：子对话框展示完整对话记录，复用现有聊天消息渲染组件。

## 边界情况与错误处理

### 生命周期

| 场景 | 处理方式 |
|------|---------|
| Gateway 启动 | 从 DB 加载 `is_enabled=True` 的任务，注册到 APScheduler |
| Gateway 重启/崩溃 | 重启后从 DB 重新加载，无数据丢失 |
| 任务被删除 | 移除 APScheduler job + 删除 Agent 目录 + 级联删除执行记录 |
| 任务被编辑 | 更新 DB，移除旧 job，重新注册 |
| Cron 表达式非法 | 用 `croniter` 校验，返回 422 |

### 执行异常

- **LangGraph Server 不可达**：标记 `failed`，记录错误，任务状态不变
- **执行超时**：10 分钟，超时标记 `failed`
- **连续失败**：本版本不自动停用，用户手动处理
- **跳过执行**：上次 running 则本次 `skipped`

### 模板变量

- 未匹配的 `{{xxx}}` 保留原文
- 自定义变量可覆盖内置变量
- 变量值为空字符串正常替换

### 数据清理

- 删除任务：级联删除 `task_executions`（`ON DELETE CASCADE`）+ Agent 目录（`shutil.rmtree`）
- 暂不提供执行记录批量清理

## 版本范围

### 本版本包含

- 定时任务 CRUD + 启停 + 手动触发
- APScheduler 调度 + langgraph-sdk 执行
- 模板变量（内置 + 自定义）
- 执行历史 + 完整对话记录查看
- 前端设置页"定时任务"标签页

### 本版本不包含

- 通知回调（预留 TODO）
- 执行记录批量清理
- 连续失败自动停用
- 任务执行结果的导出/分享
