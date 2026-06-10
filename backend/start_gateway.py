"""Gateway API launcher with Windows-compatible event loop.

Usage:
    PYTHONPATH=. uv run python start_gateway.py
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

import uvicorn

from app.gateway.app import app

uvicorn.run(app, host="0.0.0.0", port=8001, loop="asyncio")
