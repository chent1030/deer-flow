from __future__ import annotations

import json
import re
from typing import Any

from psycopg.types.json import Jsonb


def _convert_query(sql: str) -> str:
    result: list[str] = []
    i = 0
    n = len(sql)
    param_index = 1
    while i < n:
        if sql[i] == "%" and i + 1 < n:
            if sql[i + 1] == "%":
                result.append("%")
                i += 2
            elif sql[i + 1] == "s":
                result.append(f"${param_index}")
                param_index += 1
                i += 2
            else:
                result.append(sql[i])
                i += 1
        else:
            result.append(sql[i])
            i += 1
    return "".join(result)


def _convert_params(params: tuple | None) -> tuple:
    if params is None:
        return ()

    converted: list[Any] = []
    for p in params:
        if isinstance(p, Jsonb):
            converted.append(json.dumps(p.obj))
        else:
            converted.append(p)
    return tuple(converted)


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    current = value
    for _ in range(2):
        stripped = current.strip()
        if not stripped or stripped[0] not in "[{\"":
            return current
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return current
        if not isinstance(parsed, str):
            return parsed
        current = parsed
    return current


def _convert_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_convert_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _convert_value(item) for key, item in value.items()}
    return _maybe_json(value)


def _convert_record(record: Any) -> dict:
    return {key: _convert_value(value) for key, value in dict(record).items()}


def _parse_rowcount(status: str) -> int:
    if not status:
        return 0
    numbers = re.findall(r"\d+", status)
    if numbers:
        return int(numbers[-1])
    return 0


class AsyncPGCursor:
    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._rows: list[dict] = []
        self._index = 0
        self._rowcount = -1

    async def execute(self, query: str, params: tuple | None = None, *, binary: bool = False) -> AsyncPGCursor:
        converted_query = _convert_query(query)
        converted_params = _convert_params(params)
        stripped = converted_query.strip().upper()

        if stripped.startswith(("SELECT", "WITH")):
            if converted_params:
                records = await self._conn.fetch(converted_query, *converted_params)
            else:
                records = await self._conn.fetch(converted_query)
            self._rows = [_convert_record(r) for r in records]
            self._rowcount = len(self._rows)
        else:
            if converted_params:
                status = await self._conn.execute(converted_query, *converted_params)
            else:
                status = await self._conn.execute(converted_query)
            self._rows = []
            self._rowcount = _parse_rowcount(status) if status else 0

        self._index = 0
        return self

    async def executemany(self, query: str, params_seq: list[tuple]) -> None:
        converted_query = _convert_query(query)
        for params in params_seq:
            converted_params = _convert_params(params)
            if converted_params:
                await self._conn.execute(converted_query, *converted_params)
            else:
                await self._conn.execute(converted_query)
        self._rows = []
        self._index = 0

    async def fetchone(self) -> dict | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    async def fetchall(self) -> list[dict]:
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows

    @property
    def rowcount(self) -> int:
        return self._rowcount

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        row = await self.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row

    async def __aenter__(self) -> AsyncPGCursor:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass
