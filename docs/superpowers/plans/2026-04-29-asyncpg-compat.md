# asyncpg 兼容层实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 asyncpg 替换 langgraph-checkpoint-postgres 内部的 psycopg async 连接，解决 Windows ProactorEventLoop 不兼容问题。

**Architecture:** 创建 AsyncPGCursor 兼容游标，将 psycopg 的 `%s` 占位符和 `Jsonb` 参数转换为 asyncpg 的 `$N` 占位符和原生 JSON。AsyncPGSaver 和 AsyncPGStore 继承原有类，只重写 `_cursor()` 方法，所有业务逻辑从父类继承。

**Tech Stack:** asyncpg, langgraph-checkpoint-postgres (base classes only), Python 3.12+

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `packages/harness/deerflow/db/__init__.py` | 包标记 |
| Create | `packages/harness/deerflow/db/asyncpg_compat.py` | AsyncPGCursor 兼容游标 + 转换工具函数 |
| Create | `packages/harness/deerflow/agents/checkpointer/asyncpg_saver.py` | AsyncPGSaver (继承 AsyncPostgresSaver) |
| Create | `packages/harness/deerflow/runtime/store/asyncpg_store.py` | AsyncPGStore (继承 AsyncPostgresStore) |
| Modify | `packages/harness/deerflow/agents/checkpointer/async_provider.py` | postgres 分支改用 AsyncPGSaver |
| Modify | `packages/harness/deerflow/runtime/store/async_provider.py` | postgres 分支改用 AsyncPGStore |
| Modify | `packages/harness/deerflow/agents/checkpointer/provider.py` | 更新错误信息 |
| Modify | `packages/harness/deerflow/runtime/store/provider.py` | 更新错误信息 |
| Create | `tests/test_asyncpg_compat.py` | 兼容游标单元测试 |

---

### Task 1: AsyncPGCursor 兼容游标

**Files:**
- Create: `packages/harness/deerflow/db/__init__.py`
- Create: `packages/harness/deerflow/db/asyncpg_compat.py`
- Test: `tests/test_asyncpg_compat.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_asyncpg_compat.py`:

```python
import json

import pytest


class TestConvertQuery:
    def test_no_placeholders(self):
        from deerflow.db.asyncpg_compat import _convert_query

        sql = "CREATE TABLE IF NOT EXISTS foo (id INTEGER PRIMARY KEY)"
        assert _convert_query(sql) == sql

    def test_single_placeholder(self):
        from deerflow.db.asyncpg_compat import _convert_query

        assert _convert_query("SELECT * FROM t WHERE id = %s") == "SELECT * FROM t WHERE id = $1"

    def test_multiple_placeholders(self):
        from deerflow.db.asyncpg_compat import _convert_query

        result = _convert_query(
            "INSERT INTO t (a, b, c) VALUES (%s, %s, %s)"
        )
        assert result == "INSERT INTO t (a, b, c) VALUES ($1, $2, $3)"

    def test_placeholder_with_type_cast(self):
        from deerflow.db.asyncpg_compat import _convert_query

        result = _convert_query("SELECT unnest(%s::text[]) AS key")
        assert result == "SELECT unnest($1::text[]) AS key"

    def test_no_trailing_text_lost(self):
        from deerflow.db.asyncpg_compat import _convert_query

        result = _convert_query("SELECT * FROM t WHERE id = %s AND name = %s")
        assert result == "SELECT * FROM t WHERE id = $1 AND name = $2"

    def test_mixed_text_and_placeholders(self):
        from deerflow.db.asyncpg_compat import _convert_query

        sql = "WHERE thread_id = %s AND checkpoint_ns = %s ORDER BY checkpoint_id DESC LIMIT 1"
        result = _convert_query(sql)
        assert result == "WHERE thread_id = $1 AND checkpoint_ns = $2 ORDER BY checkpoint_id DESC LIMIT 1"


class TestConvertParams:
    def test_none_returns_empty_tuple(self):
        from deerflow.db.asyncpg_compat import _convert_params

        assert _convert_params(None) == ()

    def test_plain_values_pass_through(self):
        from deerflow.db.asyncpg_compat import _convert_params

        assert _convert_params(("hello", 42, True)) == ("hello", 42, True)

    def test_jsonb_converted_to_json_string(self):
        from deerflow.db.asyncpg_compat import _convert_params
        from psycopg.types.json import Jsonb

        params = (Jsonb({"key": "value"}),)
        result = _convert_params(params)
        assert len(result) == 1
        assert json.loads(result[0]) == {"key": "value"}

    def test_mixed_jsonb_and_plain(self):
        from deerflow.db.asyncpg_compat import _convert_params
        from psycopg.types.json import Jsonb

        params = ("thread-1", "ns", Jsonb({"v": 1}), Jsonb({"meta": True}))
        result = _convert_params(params)
        assert result[0] == "thread-1"
        assert result[1] == "ns"
        assert json.loads(result[2]) == {"v": 1}
        assert json.loads(result[3]) == {"meta": True}

    def test_list_param_passes_through(self):
        from deerflow.db.asyncpg_compat import _convert_params

        params = (["a", "b", "c"],)
        result = _convert_params(params)
        assert result == (["a", "b", "c"],)


class TestParseRowcount:
    def test_delete_status(self):
        from deerflow.db.asyncpg_compat import _parse_rowcount

        assert _parse_rowcount("DELETE 5") == 5

    def test_insert_status(self):
        from deerflow.db.asyncpg_compat import _parse_rowcount

        assert _parse_rowcount("INSERT 0 1") == 1

    def test_update_status(self):
        from deerflow.db.asyncpg_compat import _parse_rowcount

        assert _parse_rowcount("UPDATE 3") == 3

    def test_empty_string(self):
        from deerflow.db.asyncpg_compat import _parse_rowcount

        assert _parse_rowcount("") == 0

    def test_select_table(self):
        from deerflow.db.asyncpg_compat import _parse_rowcount

        assert _parse_rowcount("SELECT 42") == 0

    def test_create_table(self):
        from deerflow.db.asyncpg_compat import _parse_rowcount

        assert _parse_rowcount("CREATE TABLE") == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_asyncpg_compat.py -v`
Expected: FAIL — `deerflow.db` module does not exist

- [ ] **Step 3: Write implementation**

Create `packages/harness/deerflow/db/__init__.py` (empty file).

Create `packages/harness/deerflow/db/asyncpg_compat.py`:

```python
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from types import TracebackType
from typing import Any

import asyncpg
from psycopg.types.json import Jsonb


def _convert_query(sql: str) -> str:
    idx = 1
    result: list[str] = []
    i = 0
    while i < len(sql):
        if i + 1 < len(sql) and sql[i] == "%" and sql[i + 1] == "s":
            result.append(f"${idx}")
            idx += 1
            i += 2
        else:
            result.append(sql[i])
            i += 1
    return "".join(result)


def _convert_param(p: Any) -> Any:
    if isinstance(p, Jsonb):
        return json.dumps(p.obj)
    return p


def _convert_params(params: Any) -> tuple:
    if params is None:
        return ()
    if isinstance(params, (list, tuple)):
        return tuple(_convert_param(p) for p in params)
    return (_convert_param(params),)


def _parse_rowcount(status: str) -> int:
    if not status:
        return 0
    parts = status.split()
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return 0


class AsyncPGCursor:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn
        self._result: list[asyncpg.Record] = []
        self._iter_idx = 0
        self._rowcount = 0

    async def execute(
        self,
        query: str,
        params: Any = None,
        *,
        binary: bool = False,
    ) -> AsyncPGCursor:
        converted_query = _convert_query(query)
        converted_params = _convert_params(params)
        stripped = converted_query.strip().upper()
        if stripped.startswith(("SELECT", "WITH")):
            self._result = await self._conn.fetch(
                converted_query, *converted_params
            )
            self._rowcount = len(self._result)
        else:
            status = await self._conn.execute(
                converted_query, *converted_params
            )
            self._result = []
            self._rowcount = _parse_rowcount(status)
        self._iter_idx = 0
        return self

    async def executemany(
        self, query: str, params_seq: Sequence[tuple]
    ) -> None:
        converted_query = _convert_query(query)
        for params in params_seq:
            converted_params = _convert_params(params)
            await self._conn.execute(converted_query, *converted_params)

    async def fetchone(self) -> dict[str, Any] | None:
        if self._result and self._iter_idx < len(self._result):
            row = dict(self._result[self._iter_idx])
            self._iter_idx += 1
            return row
        return None

    async def fetchall(self) -> list[dict[str, Any]]:
        rows = [dict(r) for r in self._result] if self._result else []
        self._iter_idx = len(self._result)
        return rows

    @property
    def rowcount(self) -> int:
        return self._rowcount

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        self._iter_idx = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._result and self._iter_idx < len(self._result):
            row = dict(self._result[self._iter_idx])
            self._iter_idx += 1
            return row
        raise StopAsyncIteration

    async def __aenter__(self) -> AsyncPGCursor:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_asyncpg_compat.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/harness/deerflow/db/__init__.py packages/harness/deerflow/db/asyncpg_compat.py tests/test_asyncpg_compat.py
git commit -m "feat: add AsyncPGCursor compat layer for asyncpg→psycopg interface"
```

---

### Task 2: AsyncPGSaver (asyncpg-based checkpointer)

**Files:**
- Create: `packages/harness/deerflow/agents/checkpointer/asyncpg_saver.py`

- [ ] **Step 1: Write AsyncPGSaver**

Create `packages/harness/deerflow/agents/checkpointer/asyncpg_saver.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from deerflow.db.asyncpg_compat import AsyncPGCursor
from langgraph.checkpoint.postgres import _ainternal
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.postgres.base import BasePostgresSaver


class AsyncPGSaver(AsyncPostgresSaver):
    """asyncpg-based checkpointer that works on all platforms including Windows."""

    _pool: asyncpg.Pool

    def __init__(self, pool: asyncpg.Pool, serde=None) -> None:
        BasePostgresSaver.__init__(self, serde=serde)
        self._pool = pool
        self.conn = None
        self.pipe = None
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_running_loop()
        self.supports_pipeline = False

    @classmethod
    @asynccontextmanager
    async def from_conn_string(
        cls,
        conn_string: str,
        *,
        pipeline: bool = False,
        serde=None,
    ) -> AsyncIterator[AsyncPGSaver]:
        pool = await asyncpg.create_pool(
            conn_string, min_size=2, max_size=10
        )
        try:
            yield cls(pool=pool, serde=serde)
        finally:
            await pool.close()

    @asynccontextmanager
    async def _cursor(self, *, pipeline: bool = False) -> AsyncIterator[AsyncPGCursor]:
        async with self.lock:
            async with self._pool.acquire() as conn:
                yield AsyncPGCursor(conn)
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && PYTHONPATH=. uv run python -c "from deerflow.agents.checkpointer.asyncpg_saver import AsyncPGSaver; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/harness/deerflow/agents/checkpointer/asyncpg_saver.py
git commit -m "feat: add AsyncPGSaver using asyncpg instead of psycopg"
```

---

### Task 3: AsyncPGStore (asyncpg-based store)

**Files:**
- Create: `packages/harness/deerflow/runtime/store/asyncpg_store.py`

- [ ] **Step 1: Write AsyncPGStore**

Create `packages/harness/deerflow/runtime/store/asyncpg_store.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from deerflow.db.asyncpg_compat import AsyncPGCursor
from langgraph.checkpoint.postgres import _ainternal
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.store.postgres.base import BasePostgresStore


class AsyncPGStore(AsyncPostgresStore):
    """asyncpg-based store that works on all platforms including Windows."""

    _pool: asyncpg.Pool

    def __init__(self, pool: asyncpg.Pool, *, serde=None) -> None:
        BasePostgresStore.__init__(self)
        self._pool = pool
        self.conn = None
        self.pipe = None
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_running_loop()
        self.supports_pipeline = False
        self.index_config = None
        self.embeddings = None

    @classmethod
    @asynccontextmanager
    async def from_conn_string(
        cls,
        conn_string: str,
        *,
        pipeline: bool = False,
        serde=None,
    ) -> AsyncIterator[AsyncPGStore]:
        pool = await asyncpg.create_pool(
            conn_string, min_size=2, max_size=10
        )
        try:
            yield cls(pool=pool, serde=serde)
        finally:
            await pool.close()

    @asynccontextmanager
    async def _cursor(self, *, pipeline: bool = False) -> AsyncIterator[AsyncPGCursor]:
        async with self.lock:
            async with self._pool.acquire() as conn:
                yield AsyncPGCursor(conn)
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && PYTHONPATH=. uv run python -c "from deerflow.runtime.store.asyncpg_store import AsyncPGStore; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/harness/deerflow/runtime/store/asyncpg_store.py
git commit -m "feat: add AsyncPGStore using asyncpg instead of psycopg"
```

---

### Task 4: Update async providers to use new implementations

**Files:**
- Modify: `packages/harness/deerflow/agents/checkpointer/async_provider.py`
- Modify: `packages/harness/deerflow/runtime/store/async_provider.py`

- [ ] **Step 1: Update checkpointer async_provider.py**

In `packages/harness/deerflow/agents/checkpointer/async_provider.py`, make these changes:

1. Remove the `_ensure_windows_selector_loop_policy` function and its calls.
2. In the `postgres` branch of `_async_checkpointer`, import `AsyncPGSaver` instead of `AsyncPostgresSaver`.

The postgres branch should change from:

```python
    if config.type == "postgres":
        _ensure_windows_selector_loop_policy()
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError as exc:
            raise ImportError(POSTGRES_INSTALL) from exc

        if not config.connection_string:
            raise ValueError(POSTGRES_CONN_REQUIRED)

        async with AsyncPostgresSaver.from_conn_string(config.connection_string) as saver:
            await saver.setup()
            yield saver
        return
```

To:

```python
    if config.type == "postgres":
        try:
            from deerflow.agents.checkpointer.asyncpg_saver import AsyncPGSaver
        except ImportError as exc:
            raise ImportError(POSTGRES_INSTALL) from exc

        if not config.connection_string:
            raise ValueError(POSTGRES_CONN_REQUIRED)

        async with AsyncPGSaver.from_conn_string(config.connection_string) as saver:
            await saver.setup()
            yield saver
        return
```

Also remove the `_ensure_windows_selector_loop_policy` function definition and the unused `sys` import.

- [ ] **Step 2: Update store async_provider.py**

In `packages/harness/deerflow/runtime/store/async_provider.py`, make these changes:

1. Remove the `_ensure_windows_selector_loop_policy` function and its calls.
2. In the `postgres` branch of `_async_store`, import `AsyncPGStore` instead of `AsyncPostgresStore`.

The postgres branch should change from:

```python
    if config.type == "postgres":
        _ensure_windows_selector_loop_policy()
        try:
            from langgraph.store.postgres.aio import AsyncPostgresStore
        except ImportError as exc:
            raise ImportError(POSTGRES_STORE_INSTALL) from exc

        if not config.connection_string:
            raise ValueError(POSTGRES_CONN_REQUIRED)

        async with AsyncPostgresStore.from_conn_string(config.connection_string) as store:
            await store.setup()
            logger.info("Store: using AsyncPostgresStore")
            yield store
        return
```

To:

```python
    if config.type == "postgres":
        try:
            from deerflow.runtime.store.asyncpg_store import AsyncPGStore
        except ImportError as exc:
            raise ImportError(POSTGRES_STORE_INSTALL) from exc

        if not config.connection_string:
            raise ValueError(POSTGRES_CONN_REQUIRED)

        async with AsyncPGStore.from_conn_string(config.connection_string) as store:
            await store.setup()
            logger.info("Store: using AsyncPGStore (asyncpg)")
            yield store
        return
```

Also remove the `_ensure_windows_selector_loop_policy` function definition and the unused `sys` import.

- [ ] **Step 3: Run existing checkpointer tests**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_checkpointer.py -v`
Expected: ALL PASS (these tests use mocks, should not be affected)

- [ ] **Step 4: Commit**

```bash
git add packages/harness/deerflow/agents/checkpointer/async_provider.py packages/harness/deerflow/runtime/store/async_provider.py
git commit -m "feat: switch async providers to asyncpg-based implementations"
```

---

### Task 5: Update error messages in sync providers

**Files:**
- Modify: `packages/harness/deerflow/agents/checkpointer/provider.py`
- Modify: `packages/harness/deerflow/runtime/store/provider.py`

- [ ] **Step 1: Update checkpointer provider error message**

In `packages/harness/deerflow/agents/checkpointer/provider.py`, update line 39:

```python
POSTGRES_INSTALL = "langgraph-checkpoint-postgres is required for the PostgreSQL checkpointer. Install it with: uv add langgraph-checkpoint-postgres psycopg[binary] psycopg-pool"
```

To:

```python
POSTGRES_INSTALL = "langgraph-checkpoint-postgres and asyncpg are required for the PostgreSQL checkpointer. Install it with: uv add langgraph-checkpoint-postgres asyncpg"
```

- [ ] **Step 2: Update store provider error message**

In `packages/harness/deerflow/runtime/store/provider.py`, update line 39:

```python
POSTGRES_STORE_INSTALL = "langgraph-checkpoint-postgres is required for the PostgreSQL store. Install it with: uv add langgraph-checkpoint-postgres psycopg[binary] psycopg-pool"
```

To:

```python
POSTGRES_STORE_INSTALL = "langgraph-checkpoint-postgres and asyncpg are required for the PostgreSQL store. Install it with: uv add langgraph-checkpoint-postgres asyncpg"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_checkpointer.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add packages/harness/deerflow/agents/checkpointer/provider.py packages/harness/deerflow/runtime/store/provider.py
git commit -m "chore: update postgres install error messages for asyncpg"
```

---

### Task 6: Full verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && PYTHONPATH=. uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run lint**

Run: `cd backend && make lint`
Expected: No errors

- [ ] **Step 3: Run format check**

Run: `cd backend && uvx ruff format --check .`
Expected: No errors (fix if needed with `uvx ruff format .`)

- [ ] **Step 4: Manual integration test**

Start the backend services and verify the checkpointer/store connect to PostgreSQL:

```bash
cd backend
make gateway
```

Expected: Log shows `Store: using AsyncPGStore (asyncpg)` and no psycopg/ProactorEventLoop errors.

- [ ] **Step 5: Final commit if any formatting fixes needed**

```bash
git add -u
git commit -m "chore: formatting fixes"
```
