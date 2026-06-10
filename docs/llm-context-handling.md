# DeerFlow LLM 上下文管理机制

DeerFlow 的 LLM 上下文管理涉及多个层面，以下是完整的分析。

---

## 1. 对话摘要（Summarization）

当上下文接近 token 上限时自动压缩历史消息。

- **配置**：`backend/packages/harness/deerflow/config/summarization_config.py` — 定义触发条件（`trigger`：按消息数/token数/fraction）和保留策略（`keep`：保留多少历史）
- **中间件**：`backend/packages/harness/deerflow/agents/lead_agent/agent.py:41-80` — `_create_summarization_middleware()` 读取配置并创建 LangChain 的 `SummarizationMiddleware` 实例
- **注册位置**：`agent.py:221-224` — 在中间件链中**尽早执行**，先压缩上下文再让后续中间件处理
- **文档**：`backend/docs/summarization.md`

## 2. 长期记忆（Memory）

跨会话持久化用户画像、偏好和知识，注入到 system prompt 的 `<memory>` 标签中。

| 文件 | 职责 |
|------|------|
| `agents/memory/updater.py` | LLM 驱动的记忆更新：提取 facts、更新 user/history 摘要、去重 |
| `agents/memory/queue.py` | 防抖队列（默认30s），按 thread 去重后批量处理 |
| `agents/memory/prompt.py` | `MEMORY_UPDATE_PROMPT` 提示模板 + `format_memory_for_injection()` 按 token 预算裁剪后注入 system prompt |
| `agents/memory/storage.py` | 文件存储（`memory.json`），支持 per-agent 隔离，mtime 缓存自动失效 |
| `agents/middlewares/memory_middleware.py` | `MemoryMiddleware` — 每次智能体执行后过滤消息（仅保留 user + 最终 AI 回复），检测纠正/强化信号，入队异步更新 |

**注入方式**（`prompt.py:507-536`）：`_get_memory_context()` 读取 memory 数据 → `format_memory_for_injection()` 按 confidence 排序 facts 并在 token 预算内截断 → 注入到 `<memory>` XML 标签

## 3. 系统提示组装（Prompt Template）

`agents/lead_agent/prompt.py` 是上下文组装的核心，将以下内容拼接到 `SYSTEM_PROMPT_TEMPLATE` 中：

- `{memory_context}` — 长期记忆
- `{skills_section}` — 已启用的技能列表（渐进加载）
- `{subagent_section}` — 子智能体编排指令（含并发限制）
- `{soul}` — 自定义智能体人格（`SOUL.md`）
- `{deferred_tools_section}` — 延迟加载的工具名
- `{acp_section}` — ACP 智能体路径说明

## 4. 循环检测（Loop Detection）

`agents/middlewares/loop_detection_middleware.py` — 在 `after_model` 阶段检测重复 tool calls：
- 同样的 tool call 出现 ≥3 次 → 注入警告消息
- ≥5 次 → **强制剥离 tool_calls**，迫使智能体输出文本回复

## 5. 中间件执行顺序（关键）

`agent.py:198-270` 中的 `_build_middlewares()` 定义了严格的顺序：

```
ToolErrorHandling → DanglingToolCall → Summarization（尽早压缩）
→ TodoList → TokenUsage → Title → Memory → ViewImage
→ SubagentLimit → LoopDetection → Clarification（最后）
```

`SummarizationMiddleware` 排在前面，先压缩上下文再让其他中间件处理，减少整体 token 消耗。

## 6. 其他上下文相关机制

- **`ViewImageMiddleware`**：视觉模型时将图片 base64 注入上下文
- **`DanglingToolCallMiddleware`**：修补缺失的 ToolMessage（如用户中断导致），防止 LLM 因不完整的 tool call 历史出错
- **`UploadsMiddleware`**：将上传文件列表注入 human message 的 `<uploaded_files>` 标签

## 文件索引

所有路径相对于 `backend/packages/harness/deerflow/`：

```
agents/
├── lead_agent/
│   ├── agent.py                    # 中间件链构建 + SummarizationMiddleware 创建
│   └── prompt.py                   # System prompt 模板 + 记忆注入 + 技能加载
├── middlewares/
│   ├── memory_middleware.py         # 记忆更新触发 + 消息过滤 + 纠正/强化检测
│   ├── loop_detection_middleware.py # 重复 tool call 检测与强制终止
│   ├── dangling_tool_call_middleware.py  # 修补缺失 ToolMessage
│   ├── view_image_middleware.py     # 图片 base64 注入
│   └── uploads_middleware.py        # 上传文件列表注入
├── memory/
│   ├── updater.py                  # LLM 驱动的记忆更新 + facts 去重
│   ├── queue.py                    # 防抖队列 + 批量处理
│   ├── prompt.py                   # 记忆更新提示模板 + 注入格式化
│   └── storage.py                  # 文件存储 + mtime 缓存
config/
├── summarization_config.py         # 摘要触发/保留策略配置
└── memory_config.py                # 记忆系统配置
```
