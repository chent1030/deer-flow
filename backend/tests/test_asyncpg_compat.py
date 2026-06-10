from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from psycopg.types.json import Jsonb

from deerflow.db.asyncpg_compat import (
    AsyncPGCursor,
    _convert_params,
    _convert_query,
    _parse_rowcount,
)


class TestConvertQuery:
    def test_no_placeholders(self):
        assert _convert_query("SELECT 1") == "SELECT 1"

    def test_single_placeholder(self):
        assert _convert_query("SELECT * FROM t WHERE id = %s") == ("SELECT * FROM t WHERE id = $1")

    def test_multiple_placeholders(self):
        assert _convert_query("INSERT INTO t (a, b, c) VALUES (%s, %s, %s)") == "INSERT INTO t (a, b, c) VALUES ($1, $2, $3)"

    def test_percent_escape(self):
        assert _convert_query("SELECT '100%%'") == "SELECT '100%'"

    def test_mixed_percent_and_placeholder(self):
        assert _convert_query("SELECT '50%%' WHERE id = %s AND name = %s") == "SELECT '50%' WHERE id = $1 AND name = $2"

    def test_type_cast_preserved(self):
        assert _convert_query("SELECT '{a,b}'::text[]") == ("SELECT '{a,b}'::text[]")

    def test_empty_string(self):
        assert _convert_query("") == ""

    def test_consecutive_placeholders(self):
        assert _convert_query("%s%s") == "$1$2"

    def test_percent_at_end(self):
        assert _convert_query("SELECT '%") == "SELECT '%"

    def test_double_percent_at_end(self):
        assert _convert_query("SELECT '%%'") == "SELECT '%'"

    def test_with_cte(self):
        sql = "WITH cte AS (SELECT %s AS x) SELECT * FROM cte WHERE y = %s"
        assert _convert_query(sql) == ("WITH cte AS (SELECT $1 AS x) SELECT * FROM cte WHERE y = $2")


class TestConvertParams:
    def test_none_params(self):
        assert _convert_params(None) == ()

    def test_empty_tuple(self):
        assert _convert_params(()) == ()

    def test_plain_values(self):
        assert _convert_params((1, "hello", 3.14)) == (1, "hello", 3.14)

    def test_jsonb_converted(self):
        result = _convert_params((Jsonb({"key": "value"}),))
        assert len(result) == 1
        assert json.loads(result[0]) == {"key": "value"}

    def test_mixed_params(self):
        result = _convert_params((1, Jsonb([1, 2, 3]), "text"))
        assert result[0] == 1
        assert json.loads(result[1]) == [1, 2, 3]
        assert result[2] == "text"

    def test_none_in_params(self):
        assert _convert_params((None, 42)) == (None, 42)

    def test_nested_jsonb(self):
        obj = {"nested": {"deep": [1, 2]}}
        result = _convert_params((Jsonb(obj),))
        assert json.loads(result[0]) == obj


class TestParseRowcount:
    def test_delete(self):
        assert _parse_rowcount("DELETE 5") == 5

    def test_insert(self):
        assert _parse_rowcount("INSERT 0 1") == 1

    def test_update(self):
        assert _parse_rowcount("UPDATE 3") == 3

    def test_select(self):
        assert _parse_rowcount("SELECT 10") == 10

    def test_empty_string(self):
        assert _parse_rowcount("") == 0

    def test_no_number(self):
        assert _parse_rowcount("CREATE TABLE") == 0

    def test_alter_table(self):
        assert _parse_rowcount("ALTER TABLE") == 0

    def test_multiple_numbers(self):
        assert _parse_rowcount("INSERT 0 42") == 42

    def test_single_number(self):
        assert _parse_rowcount("7") == 7


class TestAsyncPGCursor:
    @pytest.fixture
    def mock_conn(self):
        conn = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_execute_select(self, mock_conn):
        mock_conn.fetch.return_value = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        cursor = AsyncPGCursor(mock_conn)
        result = await cursor.execute("SELECT * FROM t WHERE id = %s", (1,))
        assert result is cursor
        assert cursor.rowcount == 2
        assert await cursor.fetchall() == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

    @pytest.mark.asyncio
    async def test_execute_insert(self, mock_conn):
        mock_conn.execute.return_value = "INSERT 0 1"
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("INSERT INTO t (a) VALUES (%s)", ("val",))
        assert cursor.rowcount == 1
        assert await cursor.fetchall() == []

    @pytest.mark.asyncio
    async def test_execute_delete(self, mock_conn):
        mock_conn.execute.return_value = "DELETE 5"
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("DELETE FROM t WHERE id = %s", (1,))
        assert cursor.rowcount == 5

    @pytest.mark.asyncio
    async def test_execute_with_statement(self, mock_conn):
        mock_conn.fetch.return_value = [{"x": 42}]
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert cursor.rowcount == 1

    @pytest.mark.asyncio
    async def test_execute_no_params(self, mock_conn):
        mock_conn.fetch.return_value = [{"id": 1}]
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("SELECT 1")
        mock_conn.fetch.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_fetchone(self, mock_conn):
        mock_conn.fetch.return_value = [
            {"id": 1},
            {"id": 2},
        ]
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("SELECT id FROM t")
        assert await cursor.fetchone() == {"id": 1}
        assert await cursor.fetchone() == {"id": 2}
        assert await cursor.fetchone() is None

    @pytest.mark.asyncio
    async def test_fetchall_after_fetchone(self, mock_conn):
        mock_conn.fetch.return_value = [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ]
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("SELECT id FROM t")
        await cursor.fetchone()
        assert await cursor.fetchall() == [{"id": 2}, {"id": 3}]

    @pytest.mark.asyncio
    async def test_executemany(self, mock_conn):
        cursor = AsyncPGCursor(mock_conn)
        await cursor.executemany("INSERT INTO t (a) VALUES (%s)", [("a",), ("b",)])
        assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_executemany_no_params(self, mock_conn):
        cursor = AsyncPGCursor(mock_conn)
        await cursor.executemany("INSERT INTO t DEFAULT VALUES", [(), ()])
        assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_async_iteration(self, mock_conn):
        mock_conn.fetch.return_value = [{"id": 1}, {"id": 2}]
        cursor = AsyncPGCursor(mock_conn)
        await cursor.execute("SELECT id FROM t")
        rows = []
        async for row in cursor:
            rows.append(row)
        assert rows == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_conn):
        cursor = AsyncPGCursor(mock_conn)
        async with cursor as c:
            assert c is cursor

    @pytest.mark.asyncio
    async def test_execute_returns_self(self, mock_conn):
        mock_conn.fetch.return_value = []
        cursor = AsyncPGCursor(mock_conn)
        result = await cursor.execute("SELECT 1")
        assert result is cursor

    @pytest.mark.asyncio
    async def test_rowcount_default(self, mock_conn):
        cursor = AsyncPGCursor(mock_conn)
        assert cursor.rowcount == -1
