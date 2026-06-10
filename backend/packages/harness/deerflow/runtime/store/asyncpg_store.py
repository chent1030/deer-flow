from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from langgraph.store.postgres.aio import AsyncPostgresStore

from deerflow.db.asyncpg_compat import AsyncPGCursor


class AsyncPGStore(AsyncPostgresStore):
    """asyncpg-based store that works on all platforms including Windows."""

    _pool: asyncpg.Pool

    def __init__(self, pool: asyncpg.Pool, *, serde=None) -> None:
        AsyncPostgresStore.__init__(self, conn=pool)
        self._pool = pool
        self.supports_pipeline = False

    @classmethod
    @asynccontextmanager
    async def from_conn_string(
        cls,
        conn_string: str,
        *,
        pipeline: bool = False,
        serde=None,
    ) -> AsyncIterator[AsyncPGStore]:
        pool = await asyncpg.create_pool(conn_string, min_size=2, max_size=10)
        try:
            yield cls(pool=pool, serde=serde)
        finally:
            await pool.close()

    @asynccontextmanager
    async def _cursor(self, *, pipeline: bool = False) -> AsyncIterator[AsyncPGCursor]:
        async with self.lock:
            async with self._pool.acquire() as conn:
                yield AsyncPGCursor(conn)
