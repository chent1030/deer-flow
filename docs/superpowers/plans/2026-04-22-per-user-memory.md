# 按用户隔离记忆实现计划

> **给智能体工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务执行本计划。步骤使用复选框（`- [ ]`）语法进行追踪。

**目标：** 按用户名隔离记忆，使每个登录用户拥有独立的记忆文件，防止跨用户数据泄露。

**架构：** 在整个记忆栈中添加 `username` 参数——存储层、更新器、队列、中间件、API 路由和前端。用户名从 JWT 令牌（通过网关路由中的 `get_current_user` 提取）流入存储层，存储层使用它创建按用户的文件路径，如 `{base_dir}/memory/{username}/memory.json`。中间件从 LangGraph 的可配置元数据（在线程创建时设置）中提取用户名。前端通过 `credentials: "include"` 在所有记忆 fetch 调用中发送凭据。

**技术栈：** Python 3.12（FastAPI、SQLAlchemy、LangGraph），TypeScript（Next.js、TanStack Query）

---

## 需要修改的文件

| 文件 | 职责 |
|------|------|
| `backend/packages/harness/deerflow/config/paths.py` | 添加 `user_memory_file()` 和 `user_agent_memory_file()` |
| `backend/packages/harness/deerflow/agents/memory/storage.py` | 为 ABC + `FileMemoryStorage` 添加 `username` 参数 |
| `backend/packages/harness/deerflow/agents/memory/updater.py` | 在所有 CRUD 函数中传递 `username` |
| `backend/packages/harness/deerflow/agents/memory/queue.py` | 为 `ConversationContext` 和 `add()` 添加 `username` |
| `backend/packages/harness/deerflow/agents/memory/__init__.py` | 更新导出 |
| `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py` | 从可配置元数据中提取用户名 |
| `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` | 将用户名传递给 `_get_memory_context()` |
| `backend/packages/harness/deerflow/client.py` | 为所有记忆客户端方法添加 `username` |
| `backend/app/gateway/routers/memory.py` | 添加认证依赖，提取用户名 |
| `frontend/src/core/memory/api.ts` | 为所有 fetch 调用添加 `credentials: "include"` |
| `backend/tests/test_memory_*.py` | 更新现有测试 |
| `backend/tests/test_admin/conftest.py` | 更新记忆路由夹具 |

---

### 任务 1：为 Paths 添加按用户的路径方法

**文件：**
- 修改：`backend/packages/harness/deerflow/config/paths.py:114-135`

- [ ] **步骤 1：添加 `user_memory_file()` 和 `user_agent_memory_file()` 方法**

在 `agent_memory_file()` 之后（第 135 行）添加：

```python
import re

_SAFE_USERNAME_RE = re.compile(r"^[A-Za-z0-9_\-.@]+$")

def _validate_username(username: str) -> str:
    if not _SAFE_USERNAME_RE.match(username):
        raise ValueError(f"Invalid username {username!r}: only alphanumeric, hyphens, underscores, dots, and @ allowed.")
    return username

# 添加到 Paths 类：

    def user_memory_file(self, username: str) -> Path:
        """按用户的记忆文件：`{base_dir}/memory/{username}/memory.json`。"""
        return self.base_dir / "memory" / _validate_username(username) / "memory.json"

    def user_agent_memory_file(self, username: str, agent_name: str) -> Path:
        """按用户按智能体的记忆：`{base_dir}/memory/{username}/agents/{agent_name}/memory.json`。"""
        return self.base_dir / "memory" / _validate_username(username) / "agents" / agent_name.lower() / "memory.json"
```

- [ ] **步骤 2：验证** — 从 `backend/` 运行 `PYTHONPATH=. uv run python -c "from deerflow.config.paths import get_paths; p=get_paths(); print(p.user_memory_file('alice'))"`

预期输出：以 `memory/alice/memory.json` 结尾

---

### 任务 2：为记忆存储添加 `username` 参数

**文件：**
- 修改：`backend/packages/harness/deerflow/agents/memory/storage.py`

- [ ] **步骤 1：更新 `MemoryStorage` ABC**

修改签名，添加 `username: str | None = None`：

```python
class MemoryStorage(abc.ABC):
    @abc.abstractmethod
    def load(self, agent_name: str | None = None, username: str | None = None) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def reload(self, agent_name: str | None = None, username: str | None = None) -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def save(self, memory_data: dict[str, Any], agent_name: str | None = None, username: str | None = None) -> bool:
        pass
```

- [ ] **步骤 2：更新 `FileMemoryStorage`**

将缓存键从 `agent_name` 改为 `(username, agent_name)` 元组：

```python
def __init__(self):
    self._memory_cache: dict[tuple[str | None, str | None], tuple[dict[str, Any], float | None]] = {}

def _get_cache_key(self, agent_name: str | None, username: str | None) -> tuple[str | None, str | None]:
    return (username, agent_name)

def _get_memory_file_path(self, agent_name: str | None = None, username: str | None = None) -> Path:
    if username is not None:
        paths = get_paths()
        if agent_name is not None:
            self._validate_agent_name(agent_name)
            return paths.user_agent_memory_file(username, agent_name)
        return paths.user_memory_file(username)
    if agent_name is not None:
        self._validate_agent_name(agent_name)
        return get_paths().agent_memory_file(agent_name)
    config = get_memory_config()
    if config.storage_path:
        p = Path(config.storage_path)
        return p if p.is_absolute() else get_paths().base_dir / p
    return get_paths().memory_file
```

更新 `load()`、`reload()`、`save()` 以使用 `self._get_cache_key(agent_name, username)` 替代裸 `agent_name`，并将 `username` 传递给 `_get_memory_file_path()` 和 `_load_memory_from_file()`。

- [ ] **步骤 3：运行现有测试** — 从 `backend/` 运行 `PYTHONPATH=. uv run pytest tests/test_memory_storage.py -v`

全部应通过（向后兼容——`username=None` 回退到旧行为）。

---

### 任务 3：在记忆更新器中传递 `username`

**文件：**
- 修改：`backend/packages/harness/deerflow/agents/memory/updater.py`

- [ ] **步骤 1：为所有公共函数添加 `username` 参数**

每个调用 `get_memory_storage().load/save()` 或 `get_memory_data()` 的函数都需要 `username: str | None = None`：

- `get_memory_data(agent_name, username=None)` — 调用 `storage.load(agent_name, username)`
- `reload_memory_data(agent_name, username=None)` — 调用 `storage.reload(agent_name, username)`
- `import_memory_data(memory_data, agent_name, username=None)` — 调用 `storage.save/load(agent_name, username)`
- `clear_memory_data(agent_name, username=None)`
- `create_memory_fact(content, category, confidence, agent_name, username=None)`
- `delete_memory_fact(fact_id, agent_name, username=None)`
- `update_memory_fact(fact_id, content, category, confidence, agent_name, username=None)`
- `_save_memory_to_file(memory_data, agent_name, username=None)`

同时为 `MemoryUpdater.update_memory()` 和 `update_memory_from_conversation()` 添加 `username`。

- [ ] **步骤 2：运行测试** — 从 `backend/` 运行 `PYTHONPATH=. uv run pytest tests/test_memory_updater.py -v`

---

### 任务 4：为记忆队列添加 `username`

**文件：**
- 修改：`backend/packages/harness/deerflow/agents/memory/queue.py`

- [ ] **步骤 1：为 `ConversationContext` 添加 `username` 字段**

```python
@dataclass
class ConversationContext:
    thread_id: str
    messages: list[Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent_name: str | None = None
    username: str | None = None
    correction_detected: bool = False
    reinforcement_detected: bool = False
```

- [ ] **步骤 2：为 `MemoryUpdateQueue.add()` 添加 `username` 参数**

添加 `username: str | None = None` 参数，传递给 `ConversationContext()`，并在 `_process_queue()` 中传递给 `updater.update_memory()`。

- [ ] **步骤 3：运行测试** — 从 `backend/` 运行 `PYTHONPATH=. uv run pytest tests/test_memory_queue.py -v`

---

### 任务 5：为记忆中间件和提示注入添加 `username`

**文件：**
- 修改：`backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py`
- 修改：`backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

- [ ] **步骤 1：在 `MemoryMiddleware.after_agent()` 中从 LangGraph 可配置项提取用户名**

用户名将在 LangGraph 线程的可配置元数据中设置（线程创建时）。提取 `thread_id` 之后，同时提取 `username`：

```python
config_data = get_config()
thread_id = config_data.get("configurable", {}).get("thread_id")
username = config_data.get("configurable", {}).get("username")
```

将 `username` 传递给 `queue.add()`。

- [ ] **步骤 2：更新 `apply_prompt_template()` 和 `_get_memory_context()`**

为 `_get_memory_context()` 和 `apply_prompt_template()` 添加 `username: str | None = None` 参数。传递给 `get_memory_data(agent_name, username)`。

`username` 也必须来自 LangGraph 可配置元数据。这将在 `apply_prompt_template()` 被调用的地方（通常在智能体工厂中）进行传递。

- [ ] **步骤 3：更新智能体工厂以传递用户名**

找到 `apply_prompt_template()` 被调用的位置，确保 `username` 从可配置元数据中提取并传递。

---

### 任务 6：为记忆 API 路由添加认证

**文件：**
- 修改：`backend/app/gateway/routers/memory.py`

- [ ] **步骤 1：为所有端点添加认证依赖**

从 `app.admin.deps` 导入 `get_current_user`，并为每个端点添加 `current_user: User = Depends(get_current_user)`。提取 `current_user.username` 并作为 `username` 传递给所有记忆函数。

```python
from app.admin.deps import get_current_user
from app.admin.models.user import User

@router.get("/memory")
async def get_memory(current_user: User = Depends(get_current_user)) -> MemoryResponse:
    memory_data = get_memory_data(username=current_user.username)
    return MemoryResponse(**memory_data)
```

对所有 10 个端点应用相同模式。

**重要：** 使用 `get_current_user`（而非 `require_role`），以便所有认证用户都能访问自己的记忆，无论角色如何。

---

### 任务 7：前端——在记忆 API 调用中发送凭据

**文件：**
- 修改：`frontend/src/core/memory/api.ts`

- [ ] **步骤 1：为所有 fetch 调用添加 `credentials: "include"`**

记忆 API 现在需要通过 httpOnly cookie 进行认证。每个 `fetch()` 调用都需要 `credentials: "include"` 以发送跨域（或同源——无论哪种都无碍）cookie：

```typescript
export async function loadMemory(): Promise<UserMemory> {
  const response = await fetch(`${getBackendBaseURL()}/api/memory`, {
    credentials: "include",
  });
  return readMemoryResponse(response, "Failed to fetch memory");
}
```

对所有 7 个函数应用：`loadMemory`、`clearMemory`、`deleteMemoryFact`、`exportMemory`、`importMemory`、`createMemoryFact`、`updateMemoryFact`。

对于已有选项对象（POST/PATCH/DELETE）的函数，将 `credentials: "include"` 添加到现有选项中。对于没有选项的 GET 调用，添加 `{ credentials: "include" }`。

---

### 任务 8：更新现有测试

**文件：**
- 修改：`backend/tests/test_memory_storage.py`
- 修改：`backend/tests/test_memory_updater.py`
- 修改：`backend/tests/test_memory_queue.py`
- 修改：`backend/tests/test_memory_router.py`

- [ ] **步骤 1：验证所有现有测试仍然通过**

从 `backend/` 运行 `PYTHONPATH=. uv run pytest tests/test_memory_storage.py tests/test_memory_updater.py tests/test_memory_queue.py tests/test_memory_router.py -v`

全部应通过，因为 `username=None` 向后兼容（回退到旧的全局行为）。

- [ ] **步骤 2：为存储层添加按用户测试**

添加一个测试，验证 `storage.load(username="alice")` 返回与 `storage.load(username="bob")` 独立的数据，且保存到 alice 的记忆不会影响 bob 的。

- [ ] **步骤 3：运行所有后端测试** — 从 `backend/` 运行 `PYTHONPATH=. uv run pytest tests/test_memory_*.py tests/test_admin/ -v`

---

### 任务 9：验证

- [ ] **步骤 1：运行后端 lint** — 从 `backend/` 运行 `PYTHONPATH=. uv run ruff check app/ packages/`
- [ ] **步骤 2：运行所有后端测试** — 从 `backend/` 运行 `PYTHONPATH=. uv run pytest tests/ -v`
- [ ] **步骤 3：运行前端类型检查** — 从 `frontend/` 运行 `node_modules/.bin/tsc --noEmit`
- [ ] **步骤 4：运行管理端类型检查** — 从 `admin/` 运行 `node_modules/.bin/tsc --noEmit`
