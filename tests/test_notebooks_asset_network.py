"""CPU command contracts, not evidence of live SDK downloads or physics."""
import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks"))
from policy_workshop import PolicySession


@pytest.mark.parametrize("filename,role", [
    ("04_train_isaac_lab_3.ipynb", "train"),
    ("05_policy_inference.ipynb", "admission"),
])
def test_native_asset_jobs_explicitly_use_bridge_without_published_ports(filename, role, tmp_path, monkeypatch):
    """Evaluate the real notebook call through the real container builder."""
    notebook = json.loads((ROOT / "notebooks" / filename).read_text())
    calls = [node for cell in notebook["cells"] if cell["cell_type"] == "code"
             for node in ast.walk(ast.parse("".join(cell["source"])))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "job" and node.args and isinstance(node.args[0], ast.Constant)
             and node.args[0].value == role]
    assert len(calls) == 1
    session = PolicySession(ROOT, work=tmp_path / "session")
    assets = tmp_path / "assets"
    for name in ("robot/robot_allcollisions_backlash.xml", "policies/velstand.onnx"):
        path = assets / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("CPU command-only fixture")
    generated = []
    monkeypatch.setattr(session, "start", lambda *args, **kwargs: generated.append(session.container_command(*args, **kwargs)))
    monkeypatch.setattr(session, "run", lambda args, **kwargs: SimpleNamespace(stdout="0\n", returncode=0))
    monkeypatch.setattr(session, "stop", lambda role: None)
    context = dict(session=session, SIM_IMAGE="fixture:sim", GPU="0", ASSETS=assets,
                   run=tmp_path / "run", output=tmp_path / "output", bundle={"run": str(tmp_path / "run")},
                   UPDATES=4, HORIZON=32, SEED=7)
    eval(compile(ast.Expression(calls[0]), filename, "eval"), context)
    command, = generated
    assert command[command.index("--network") + 1] == "bridge"
    assert "--publish" not in command and "-p" not in command and "-P" not in command
    assert command[command.index("--memory") + 1] == "32g"
    assert command[command.index("--cpus") + 1] == "8"
    assert f"{assets}:/assets:ro" in command
    assert next(k.value.value for k in calls[0].keywords if k.arg == "timeout") == 420


def test_non_native_checks_keep_offline_default(tmp_path):
    session = PolicySession(ROOT, work=tmp_path)
    for role in ("capability", "verify-policy", "adapter-tests", "image-attestation"):
        command = session.container_command(role, "fixture:cpu", ["fixture"])
        assert command[command.index("--network") + 1] == "none"
        assert "--publish" not in command and "-p" not in command
