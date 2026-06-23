from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.anyio
async def test_asyncpg_pool_creation_skips_blockbuster():
    """asyncpg may call os.getcwd while resolving default PostgreSQL SSL files."""
    from deerflow.runtime.checkpointer import asyncpg_saver

    events = []

    class FakeBlockbusterSkip:
        def set(self, value):
            events.append(("set", value))
            return "token"

        def reset(self, token):
            events.append(("reset", token))

    fake_pool = AsyncMock()

    async def fake_create_pool(*args, **kwargs):
        events.append(("create_pool", args, kwargs))
        return fake_pool

    with (
        patch.object(asyncpg_saver, "blockbuster_skip", FakeBlockbusterSkip()),
        patch.object(asyncpg_saver.asyncpg, "create_pool", side_effect=fake_create_pool),
    ):
        async with asyncpg_saver.AsyncPGSaver.from_conn_string("postgresql://localhost/db") as saver:
            assert isinstance(saver, asyncpg_saver.AsyncPGSaver)

    assert events == [
        ("set", True),
        (
            "create_pool",
            ("postgresql://localhost/db",),
            {"min_size": 2, "max_size": 10},
        ),
        ("reset", "token"),
    ]
    fake_pool.close.assert_awaited_once()
