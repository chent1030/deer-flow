from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import Token

import asyncpg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.postgres.base import BasePostgresSaver

from deerflow.db.asyncpg_compat import AsyncPGCursor

try:
    from blockbuster.blockbuster import blockbuster_skip
except Exception:  # pragma: no cover - optional dependency outside LangGraph server
    blockbuster_skip = None


def _skip_blockbuster() -> Token | None:
    if blockbuster_skip is None:
        return None
    return blockbuster_skip.set(True)


def _reset_blockbuster(token: Token | None) -> None:
    if blockbuster_skip is not None and token is not None:
        blockbuster_skip.reset(token)


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
        pool = await asyncpg.create_pool(conn_string, min_size=2, max_size=10)
        try:
            yield cls(pool=pool, serde=serde)
        finally:
            await pool.close()

    @asynccontextmanager
    async def _cursor(self, *, pipeline: bool = False) -> AsyncIterator[AsyncPGCursor]:
        async with self.lock:
            token = _skip_blockbuster()
            try:
                async with self._pool.acquire() as conn:
                    yield AsyncPGCursor(conn)
            finally:
                _reset_blockbuster(token)
