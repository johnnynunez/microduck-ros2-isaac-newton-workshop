"""Fail-closed explicit selection and evidence-bound native admission."""

import json
from pathlib import Path

import pytest


def test_explicit_manifest_missing_never_falls_back(tmp_path):
    from microduck_workshop.policy import student

    with pytest.raises((FileNotFoundError, ValueError)):
        student.load_manifest(tmp_path / "missing.json")


@pytest.mark.parametrize("value", [{}, {"schema_version": 1}, {"schema_version": float("nan")}])
def test_malformed_manifest_rejected(tmp_path, value):
    from microduck_workshop.policy.student import load_manifest

    path = tmp_path / "policy_manifest.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_train_and_play_expose_explicit_handoff():
    from microduck_workshop.sim.play import parser as play_parser
    from microduck_workshop.sim.train import parser as train_parser

    train = train_parser().parse_args(
        ["--asset-root", "/assets", "--warm-start-onnx", "/policy.onnx"]
    )
    assert train.warm_start_onnx == Path("/policy.onnx")
    play = play_parser().parse_args(
        [
            "--asset-root",
            "/assets",
            "--policy-manifest",
            "/run/policy_manifest.json",
            "--policy-admission",
            "/run/admission/admission.json",
        ]
    )
    assert play.policy_manifest == Path("/run/policy_manifest.json")


def test_training_manifest_cannot_admit_a_false_positive_receipt(tmp_path):
    from microduck_workshop.policy.student import (
        ADMISSION_CASES,
        fixed_step_spec,
        load_admission,
        source_hashes,
        write_json,
    )

    expected = {"policy_sha256": "a" * 64, "manifest_sha256": "b" * 64, "policy_mode": "training"}
    fake_trace = tmp_path / "fake.jsonl"
    fake_trace.write_text("{}\n")
    from microduck_workshop.policy.student import artifact

    value = dict(
        schema_version=1,
        passed=True,
        scope="native_only_not_ros_agent_acceptance",
        source_sha256=source_hashes(),
        fixed_step=fixed_step_spec(),
        **expected,
        cases=[
            {
                "id": c[0],
                "verdicts": [
                    {"request": r, "verified": True} for r in ("step", "resume", "rest_control")
                ],
                "artifacts": [artifact(fake_trace)] * 2,
            }
            for c in ADMISSION_CASES
        ],
    )
    path = tmp_path / "admission.json"
    write_json(path, value)
    with pytest.raises((ValueError, KeyError), match="trace|artifact|runtime|admission"):
        load_admission(path, expected)


def test_student_admission_absent_or_failed_is_not_ready(tmp_path):
    from microduck_workshop.policy.student import load_admission

    with pytest.raises((FileNotFoundError, ValueError)):
        load_admission(tmp_path / "missing.json", {"sha256": "a" * 64})
    path = tmp_path / "admission.json"
    path.write_text(json.dumps({"passed": False}))
    with pytest.raises(ValueError):
        load_admission(path, {"sha256": "a" * 64})
