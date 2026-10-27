"""Validation tooling does not invent physical measurements."""

import importlib.util
from pathlib import Path


def test_calibration_probe_extracts_actual_command_intervals():
    path = Path(__file__).resolve().parents[1] / "scripts/sim_validate_calibration.py"
    assert path.exists(), "native calibration validation driver must exist"
    spec = importlib.util.spec_from_file_location("probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        {
            "sim_time": t,
            "desired_command": [v, 0, 0],
            "neural_command": [n, 0, 0],
            "observation": [0] * 48 + [n, 0, 0] + [0] * 10,
        }
        for t, v, n in [(0, 0, 0), (0.4, 0.1, 0.25), (1.4, 0, 0), (2.2, 0.1, 0.25), (4.2, 0, 0)]
    ]
    assert module.command_intervals(rows) == [(0.4, 1.4), (2.2, 4.2)]


def test_round1_plan_covers_all_preregistered_cases_without_fit_data():
    import json

    path = Path(__file__).resolve().parents[1] / "provenance/command_calibration.json"
    assert path.exists(), "portable honest calibration receipt is required"
    receipt = json.loads(path.read_text())
    plan = receipt["preregistration"]
    assert {(c["zero_wait_s"], c["duration_s"]) for c in plan["gating_cases"]} == {
        (wait, duration) for wait in (0.4, 0.8, 1.4) for duration in (1, 2)
    }
    assert len(receipt["holdouts"]) == 7
    assert len({c["case"]["id"] for c in receipt["holdouts"]}) == 7
    assert receipt["validation_status"] == "NOT_READY"
    assert receipt["supported_forward_durations_s"] == []
    assert all(not r["both_completed_requests_verified"] for r in receipt["holdouts"])
    text = path.read_text()
    assert "/home/" not in text and "root_pose" not in text and "lease_token" not in text


def test_summary_requires_exact_preregistered_case_ids():
    import pytest

    path = Path(__file__).resolve().parents[1] / "scripts/sim_validate_calibration.py"
    spec = importlib.util.spec_from_file_location("probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        {
            "case": {"id": "case1", "gating": True},
            "plan_sha256": "abc",
            "both_completed_requests_verified": False,
        }
    ]
    result = module.summarize_receipts(rows, {"case1"}, "abc")
    assert result["case_count"] == 1 and not result["cases"][0]["verified"]
    with pytest.raises(ValueError):
        module.summarize_receipts(rows, {"case1", "missing"}, "abc")
    with pytest.raises(ValueError):
        module.summarize_receipts(rows + rows, {"case1"}, "abc")
    with pytest.raises(ValueError):
        module.summarize_receipts(rows, {"case1"}, "wrong_hash")
