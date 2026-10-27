"""Readback of genuinely generated artifacts; skipped without explicit live run paths."""

import copy
import os
from pathlib import Path

import pytest

RUN = os.environ.get("MICRODUCK_STUDENT_RUN")
ADMISSION = os.environ.get("MICRODUCK_STUDENT_ADMISSION")
pytestmark = pytest.mark.skipif(
    not (RUN and ADMISSION), reason="requires real training/admission artifacts"
)


def test_real_artifact_chain_and_physical_readback():
    from microduck_workshop.policy.student import load_admission, load_manifest, read_json

    manifest = load_manifest(Path(RUN) / "policy_manifest.json")
    training = read_json(Path(RUN) / "training_receipt.json")
    admission = load_admission(Path(ADMISSION) / "admission.json", manifest)
    assert training["actor_init"] == "public_v8_actor_only"
    assert training["critic_init"] == "fresh_random"
    assert training["optimizer_init"] == "fresh_adam"
    assert training["full_ppo_resume"] is False
    assert training["converged_gait"] is False
    assert training["actor_changed_parameters"] > 0
    assert training["saved_optimizer_steps"] == 16
    assert training["physics_steps"] == 512
    assert len(training["updates"]) == 4
    assert all(
        u["actor_weight_delta_l2"] > 0 and u["gradient_norm"] > 0 for u in training["updates"]
    )
    assert training["warmstart_parity"]["samples"] == training["export_parity"]["samples"] == 128
    assert admission["passed"] is True
    assert len(admission["cases"]) == 4
    assert sum(len(c["verdicts"]) for c in admission["cases"]) == 12


@pytest.mark.parametrize("field", ["policy_sha256", "manifest_sha256", "policy_mode", "passed"])
def test_real_admission_refuses_changed_binding(tmp_path, field):
    from microduck_workshop.policy.student import (
        load_admission,
        load_manifest,
        read_json,
        write_json,
    )

    manifest = load_manifest(Path(RUN) / "policy_manifest.json")
    original = read_json(Path(ADMISSION) / "admission.json")
    original[field] = False if field == "passed" else "wrong"
    path = tmp_path / "admission.json"
    write_json(path, original)
    with pytest.raises(ValueError, match="admission"):
        load_admission(path, manifest)


def test_readback_recomputes_physics_instead_of_trusting_passed_boolean():
    from microduck_workshop.policy.student import load_manifest, read_json, verify_case_trace

    manifest = load_manifest(Path(RUN) / "policy_manifest.json")
    original = read_json(Path(ADMISSION) / "admission.json")
    case = copy.deepcopy(original["cases"][0])
    case["verdicts"][0]["metrics"]["forward_displacement_m"] += 1.0
    with pytest.raises(ValueError, match="recomputed"):
        verify_case_trace(Path(ADMISSION), case, manifest)
