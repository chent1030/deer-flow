from pathlib import Path
from typing import NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from deerflow.agents.thread_state import ThreadDataState
from deerflow.config.paths import VIRTUAL_PATH_PREFIX


class AutoPresentOutputsMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    thread_data: NotRequired[ThreadDataState | None]
    artifacts: NotRequired[list[str]]


class AutoPresentOutputsMiddleware(AgentMiddleware[AutoPresentOutputsMiddlewareState]):
    """Expose files saved under /mnt/user-data/outputs as downloadable artifacts."""

    state_schema = AutoPresentOutputsMiddlewareState

    @override
    def after_agent(self, state: AutoPresentOutputsMiddlewareState, runtime: Runtime) -> dict | None:
        thread_data = state.get("thread_data") or {}
        outputs_path = thread_data.get("outputs_path")
        if not outputs_path:
            return None

        outputs_dir = Path(outputs_path)
        if not outputs_dir.exists() or not outputs_dir.is_dir():
            return None

        artifacts: list[str] = []
        for path in sorted(p for p in outputs_dir.rglob("*") if p.is_file()):
            rel_path = path.relative_to(outputs_dir)
            if any(part.startswith(".") for part in rel_path.parts):
                continue
            artifacts.append(f"{VIRTUAL_PATH_PREFIX}/outputs/{rel_path.as_posix()}")

        if not artifacts:
            return None
        return {"artifacts": artifacts}
