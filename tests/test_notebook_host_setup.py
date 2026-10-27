"""Notebook-first host preparation stays explicit and separate from GPU execution."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_brev_setup_checks_host_tool_before_builds_and_prepares_notebook_kernel():
    source = (ROOT / "scripts/brev_setup.sh").read_text()
    assert "command -v uv" in source
    assert source.index("command -v uv") < source.index("docker build")
    assert "bash scripts/notebook_setup.sh" in source
    assert source.index("bash scripts/notebook_setup.sh") > source.index("bash scripts/model_setup.sh --verify-only")
    assert "bash scripts/notebook_start.sh" not in source


def test_explicit_cdi_gpu_selection_preserves_driver_capabilities(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(ROOT / "notebooks"))
    from workshop import Session  # pyright: ignore[reportMissingImports]

    session = Session(ROOT, work=tmp_path / "notebook")
    monkeypatch.setenv("WORKSHOP_GPU_SELECTOR", "cdi")
    assert session.gpu_options("1") == [
        "--device", "nvidia.com/gpu=1", "-e",
        "NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility",
    ]
    monkeypatch.delenv("WORKSHOP_GPU_SELECTOR")
    assert session.gpu_options("1")[:2] == ["--gpus", "device=1"]
    monkeypatch.setenv("WORKSHOP_GPU_SELECTOR", "unsupported")
    import pytest
    with pytest.raises(ValueError, match="GPU_SELECTOR"):
        session.gpu_options("1")
