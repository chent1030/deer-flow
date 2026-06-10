"""LangGraph dev launcher with Windows-compatible event loop.

Fixes psycopg "cannot use ProactorEventLoop" on Windows by forcing
SelectorEventLoop before any async code runs.

Usage:
    uv run python start_langgraph.py --no-browser --no-reload --n-jobs-per-worker 10 --host 0.0.0.0
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn.loops.asyncio as _uv_loop

    _orig_factory = _uv_loop.asyncio_loop_factory

    def _patched_factory(use_subprocess: bool = False):
        if not use_subprocess:
            return asyncio.SelectorEventLoop
        return _orig_factory(use_subprocess=use_subprocess)

    _uv_loop.asyncio_loop_factory = _patched_factory

from langgraph_cli.cli import cli

dev_cmd = cli.commands["dev"]
sys.argv = ["langgraph"] + sys.argv[1:]
dev_cmd.main(standalone_mode=True)
