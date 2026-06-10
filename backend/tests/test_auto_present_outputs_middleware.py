from langgraph.runtime import Runtime

from deerflow.agents.middlewares.auto_present_outputs_middleware import AutoPresentOutputsMiddleware


def _as_posix(path: str) -> str:
    return path.replace("\\", "/")


def test_after_agent_returns_output_files_as_artifacts(tmp_path):
    outputs = tmp_path / "outputs"
    nested = outputs / "reports"
    nested.mkdir(parents=True)
    (outputs / "summary.md").write_text("# Summary", encoding="utf-8")
    (nested / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    result = AutoPresentOutputsMiddleware().after_agent(
        state={"thread_data": {"outputs_path": str(outputs)}},
        runtime=Runtime(context={"thread_id": "thread-1"}),
    )

    assert result == {
        "artifacts": [
            "/mnt/user-data/outputs/reports/data.csv",
            "/mnt/user-data/outputs/summary.md",
        ]
    }


def test_after_agent_ignores_missing_outputs_path():
    result = AutoPresentOutputsMiddleware().after_agent(
        state={"thread_data": {"outputs_path": None}},
        runtime=Runtime(context={"thread_id": "thread-1"}),
    )

    assert result is None
