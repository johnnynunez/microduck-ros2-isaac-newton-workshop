"""Publication consistency only; real execution is recorded separately."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def receipt():
    return json.loads((ROOT / "verification/notebook-course-final.json").read_text())


def test_complete_course_receipt_keeps_reference_and_hardware_scope_explicit():
    data = receipt()
    assert data["requested_notebooks"] == data["executed_notebooks"] == 6
    assert data["requested_code_cells"] == data["passed_code_cells"] == 39
    assert data["artifact_count"] == 814 and data["all_artifact_hashes_sizes_match"] is True
    assert data["adapter"]["selection"] == "EXPLICIT_REFERENCE"
    assert data["adapter"]["student_authorship_claimed"] is False
    assert any("Brev/L40S" in value for value in data["limits"])
    assert (ROOT / "verification" / data["prior_failed_attempt"]).exists()


def test_rehearsed_notebooks_match_public_source_without_published_outputs():
    data = receipt()
    names = [item["name"] for item in data["notebooks"]]
    assert len(names) == len(set(names)) == 6
    count = 0
    for item in data["notebooks"]:
        path = ROOT / "notebooks" / item["name"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["public_notebook_sha256"]
        notebook = json.loads(path.read_text())
        code = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        assert len(code) == item["passed_code_cells"]
        assert all(cell["execution_count"] is None and cell["outputs"] == [] for cell in code)
        count += len(code)
    assert count == data["passed_code_cells"]


def test_course_goal_receipt_preserves_request_timing_and_exact_actor():
    data = receipt()
    assert data["goal_success"] is data["agent_success"] is data["physical_success"] is True
    assert data["motion_requests"] == 1 and data["source_proofs_not_restamped"] is True
    assert data["tool_sequence"] == ["microduck.observe", "microduck.step_forward", "microduck.verify", "task_done"]
    assert data["raw_derived_window"]["settle_s"] >= .35
    assert data["native_recomputed"]["verified"] is True
    assert data["admission"]["verified_verdicts"] == 12
    assert data["native_only_replay"]["admission_rows"] == 1637
    assert data["native_only_replay"]["admission_max_abs_action_error"] == 0
    assert data["setup_fix"]["native_training_network"] == "bridge"
    assert data["setup_fix"]["native_admission_network"] == "bridge"
    assert data["setup_fix"]["published_ports"] is data["setup_fix"]["physics_or_policy_changed"] is False
    assert all(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
               for digest in data["identity"].values())
