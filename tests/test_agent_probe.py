"""A parsed function name alone is not a successful tool call."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def test_probe_rejects_schema_refused_calls():
    path = Path(__file__).parents[1] / "scripts/agent_model_probe.py"
    spec = importlib.util.spec_from_file_location("probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    report = SimpleNamespace(
        success=False,
        tool_log=[
            dict(tool="microduck.observe", args={"action": "observe"}, result={"ok": False}),
            dict(tool="microduck.verify", args={"action": "verify"}, result={"ok": False}),
            dict(tool="task_done", args={"success": False}, result={"success": False}),
        ],
    )
    assert probe.valid_diagnostic(report) is False
