# asyncpg 兼容层替换 psycopg

## 问题

`langgraph-checkpoint-postgres` 内部使用 psycopg async，而 psycopg async 在 Windows 上需要 `SelectorEventLoop`，但 Windows 默认使用 `ProactorEventLoop`。通过 wrapper 脚本强制设置 event loop policy 的方案已确认在 Windows 上无效（langgraph dev 可能启动子进程绕过了父进程的 policy）。

项目代码本身从不直接 import psycopg。所有 psycopg 用法都在 `langgraph-checkpoint-postgres` 第三方包内部。

## 方案：Compatibility Cursor（兼容游标）

创建一个薄兼容层，让 asyncpg connection 提供 psycopg cursor 相同的接口。

`AsyncPostgresSaver` 和 `AsyncPostgresStore` 内部所有数据库操作都通过 `_cursor()` 方法获取游标。兼容游标拦截这些调用，将 psycopg 格式（`%s` 占位符、`Jsonb` 包装）转换为 asyncpg 格式（`$N` 占位符、原生 JSON）。

这样无需重写 checkpointer/store 的业务逻辑（SQL 查询、序列化、迁移等），全部从父类继承。

## 文件变更

### 新增

| 文件 | 行数 | 说明 |
|------|------|------|
| `deerflow/db/__init__.py` | 0 | 包标记 |
| `deerflow/db/asyncpg_compat.py` | ~100 | AsyncPGCursor 兼容游标 + 占位符/参数转换 |
| `deerflow/agents/checkpointer/asyncpg_saver.py` | ~50 | AsyncPGSaver，继承 AsyncPostgresSaver，重写 `__init__` + `_cursor` |
| `deerflow/runtime/store/asyncpg_store.py` | ~50 | AsyncPGStore，继承 AsyncPostgresStore，重写 `__init__` + `_cursor` |

### 修改

| 文件 | 改动 |
|------|------|
| `deerflow/agents/checkpointer/async_provider.py` | postgres 分支：import AsyncPGSaver 替换 AsyncPostgresSaver，删除 `_ensure_windows_selector_loop_policy()` |
| `deerflow/runtime/store/async_provider.py` | postgres 分支：import AsyncPGStore 替换 AsyncPostgresStore，删除 `_ensure_windows_selector_loop_policy()` |
| `deerflow/agents/checkpointer/provider.py` | 更新 `POSTGRES_INSTALL` 错误信息，不再提示安装 psycopg |
| `deerflow/runtime/store/provider.py` | 更新 `POSTGRES_STORE_INSTALL` 错误信息 |

### 不修改

- **同步 provider**（sync psycopg 没有 ProactorEventLoop 问题）
- **config.yaml**（`postgresql://...` 格式 asyncpg 同样接受）
- **数据库迁移**（表结构完全不变）
- **start_langgraph.py / start_gateway.py**（保留，但 Windows 上不再需要 event loop hack）

## AsyncPGCursor 兼容游标设计

### 接口映射

| psycopg cursor 方法 | AsyncPGCursor 实现 |
|---|---|
| `execute(query, params, *, binary=False)` | 转换占位符 `%s→$N`，转换参数 `Jsonb→json.dumps`，调用 `conn.fetch()`，存储结果，返回 self |
| `fetchone()` | `dict(result[idx])` 并递增索引 |
| `fetchall()` | `[dict(r) for r in result]` |
| `executemany(query, params_list)` | 循环调用 `conn.execute()` |
| `async for row in cur:` | `__aititer__`/`__anext__` 遍历结果 |
| `rowcount` | 解析 asyncpg status string（如 `"DELETE 5"`） |

### 占位符转换

```python
def _convert_query(sql: str) -> str:
    """将 %s 替换为 $1, $2, ...，处理 %% 转义"""
```

### 参数转换

```python
def _convert_params(params) -> tuple:
    """将 Jsonb(obj) 替换为 json.dumps(obj)，其余原样传递"""
```

asyncpg 原生支持 PostgreSQL 数组（Python list 直接传递），`::text[]` 类型标注保留在 SQL 中不受影响。

## AsyncPGSaver 设计

```python
class AsyncPGSaver(AsyncPostgresSaver):
    """asyncpg-based checkpointer for cross-platform support."""

    def __init__(self, pool: asyncpg.Pool, serde=None):
        BasePostgresSaver.__init__(self, serde=serde)
        self._pool = pool
        self.conn = None
        self.pipe = None
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_running_loop()
        self.supports_pipeline = False

    @classmethod
    @asynccontextmanager
    async def from_conn_string(cls, conn_string, **kwargs):
        pool = await asyncpg.create_pool(conn_string, min_size=2, max_size=10)
        try:
            yield cls(pool=pool)
        finally:
            await pool.close()

    @asynccontextmanager
    async def _cursor(self, *, pipeline=False):
        async with self.lock, self._pool.acquire() as conn:
            yield AsyncPGCursor(conn)
```

继承的方法：`setup()`、`aput()`、`aget_tuple()`、`alist()`、`aput_writes()`、`adelete_thread()`、同步方法（`list`、`get_tuple`、`put`、`put_writes`、`delete_thread`）。

## AsyncPGStore 设计

同样的模式。继承 `AsyncPostgresStore`，重写 `__init__` 和 `_cursor()`。

继承的方法：`setup()`、`abatch()`、`sweep_ttl()`、TTL sweeper、所有 batch 操作。

向量搜索（pgvector）不启用（项目未配置 `index` 参数），对应代码路径不会触发。

## 依赖

| 包 | 状态 | 说明 |
|---|---|---|
| `langgraph-checkpoint-postgres` | 保留 | 继承基类和辅助方法 |
| `psycopg[binary]` | 保留 | 传递依赖，仅 import 不用于 async 连接 |
| `asyncpg` | 已有 | admin panel 已在使用 |
| `psycopg-pool` | 保留 | 传递依赖 |

## 验证

1. macOS: `cd backend && make dev` + `make gateway` 正常启动
2. macOS: `cd backend && make test` 通过
3. Windows: `make dev-win` 不再报 ProactorEventLoop 错误
4. Windows: Gateway 正常连接 PostgreSQL
5. 功能：线程列表、对话历史、checkpoint 存取正常工作
