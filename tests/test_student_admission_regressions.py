"""Adversarial CPU copies, NEVER deployable or evidence of new physics.

Set MICRODUCK_REGRESSION_RUN/ADMISSION to the immutable pre-fix native bundle.
These tests exercise real production loaders, graph export and replay.
"""

import copy
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from microduck_workshop.policy import student


@pytest.fixture
def copied_bundle(tmp_path):
    run = os.environ.get("MICRODUCK_REGRESSION_RUN")
    admission = os.environ.get("MICRODUCK_REGRESSION_ADMISSION")
    if not run or not admission:
        pytest.skip("requires immutable recorded native input bundle")
    dest = tmp_path / "ADVERSARIAL_CPU_NOT_DEPLOYABLE"
    dest.mkdir()
    train, admit = dest / "run", dest / "admit"
    train.mkdir()
    admit.mkdir()
    for name in (
        "actor.onnx",
        "checkpoint.pt",
        "initial.pt",
        "training_receipt.json",
        "transitions.jsonl",
    ):
        shutil.copyfile(Path(run) / name, train / name)
    student.create_manifest(train, mode="training")
    manifest = student.load_manifest(train / "policy_manifest.json")
    value = student.read_json(Path(admission) / "admission.json")
    value.update(
        source_sha256=student.source_hashes(),
        manifest_sha256=manifest["manifest_sha256"],
        lifecycle="complete",
    )
    for p in Path(admission).glob("*.jsonl"):
        shutil.copyfile(p, admit / p.name)
    return train, admit, manifest, value


def save(admit, value):
    student.write_json(admit / "admission.json", value)
    return admit / "admission.json"


def rewrite(admit, case, index, mutate):
    path = admit / case["artifacts"][index]["path"]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    case["artifacts"][index] = student.artifact(path)


def test_unmodified_trace_copy_exercises_full_replay(copied_bundle):
    pytest.importorskip("onnx")
    train, admit, _, value = copied_bundle
    save(admit, value)
    _, _, profile = student.select_student(
        train / "policy_manifest.json",
        mode="serve",
        policy_mode="training",
        command_profile="direct",
        step_profile="step-forward-v1",
        admission_path=admit / "admission.json",
    )
    assert profile.receipt()["validation_status"] == "NATIVE_VALIDATED"


def test_different_zero_actor_cannot_reuse_old_native_traces(copied_bundle):
    torch = pytest.importorskip("torch")
    from microduck_workshop.policy.warmstart import export_checkpoint

    train, admit, manifest, value = copied_bundle
    saved = torch.load(train / "checkpoint.pt", weights_only=True, map_location="cpu")
    for name, tensor in saved["model"].items():
        if name.startswith("actor.mlp."):
            tensor.zero_()
    torch.save(saved, train / "checkpoint.pt")
    public = Path(os.environ["MICRODUCK_PUBLIC_ONNX"])
    export_checkpoint(train / "checkpoint.pt", train / "actor.onnx", source_onnx=public)
    receipt = student.read_json(train / "training_receipt.json")
    receipt.update(
        checkpoint_sha256=student.sha256(train / "checkpoint.pt"),
        actor_sha256=student.sha256(train / "actor.onnx"),
    )
    student.write_json(train / "training_receipt.json", receipt)
    student.create_manifest(train, mode="training")
    manifest = student.load_manifest(train / "policy_manifest.json")
    value.update(
        policy_sha256=manifest["policy_sha256"], manifest_sha256=manifest["manifest_sha256"]
    )
    for case in value["cases"]:

        def relabel(rows):
            for row in rows:
                row["policy_sha256"] = manifest["policy_sha256"]
                row["command_profile"]["policy_sha256"] = manifest["policy_sha256"]

        rewrite(admit, case, 0, relabel)
    save(admit, value)
    with pytest.raises(ValueError, match="ONNX.*raw"):
        student.select_student(
            train / "policy_manifest.json",
            mode="serve",
            policy_mode="training",
            command_profile="direct",
            step_profile="step-forward-v1",
            admission_path=admit / "admission.json",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_holdouts",
        "plan",
        "missing_initial",
        "duplicate_initial",
        "time_gap",
        "truth_alignment",
        "phase",
        "nonzero_rest",
        "observation_command",
        "gravity",
        "error",
        "incomplete",
    ],
)
def test_complete_schedule_and_lifecycle_required(copied_bundle, mutation):
    _, admit, manifest, value = copied_bundle
    first = value["cases"][0]
    if mutation == "duplicate_holdouts":
        for case in value["cases"][1:]:
            case["verdicts"] = copy.deepcopy(first["verdicts"])
            for index in (0, 1):
                dest = admit / case["artifacts"][index]["path"]
                shutil.copyfile(admit / first["artifacts"][index]["path"], dest)
                case["artifacts"][index] = student.artifact(dest)
    elif mutation == "plan":
        value["plan"][0]["initial_zero_s"] = 0
    elif mutation == "error":
        value["error"] = "controlled teardown exception"
    elif mutation == "incomplete":
        value["lifecycle"] = "running"
    else:

        def mutate(rows):
            if mutation == "missing_initial":
                rows.pop(0)
            elif mutation == "duplicate_initial":
                rows.insert(0, rows[0])
            elif mutation in {"time_gap", "truth_alignment"}:
                rows[0]["sim_time"] += 0.02
            elif mutation == "phase":
                rows[0]["phase"] = "rest_control"
            elif mutation == "nonzero_rest":
                rows[-1]["neural_command"] = [0.25, 0, 0]
            elif mutation == "observation_command":
                rows[20]["observation"][48] = 0
            elif mutation == "gravity":
                rows[0]["observation"][3:6] = [0, 0, 0]

        for index in (
            (0, 1)
            if mutation in {"missing_initial", "duplicate_initial"}
            else ((1,) if mutation == "truth_alignment" else (0,))
        ):
            rewrite(admit, first, index, mutate)
    with pytest.raises(ValueError):
        student.load_admission(save(admit, value), manifest)


def test_teardown_exception_invalidates_passed_receipt(tmp_path, monkeypatch):
    from microduck_workshop.sim import admit_policy

    class Runtime:
        identity = {"fixture": "CPU_LIFECYCLE_ONLY"}
        bam_receipt = {"fixture": "CPU_LIFECYCLE_ONLY"}
        sim_time = 0.0
        sequence = 0

        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            raise RuntimeError("controlled teardown exception")

        def enable_bam(self):
            pass

        def _initial_reset(self):
            pass

        def sample(self):
            return {"imu": {"angular_velocity": [0, 0, 0], "linear_acceleration": [0, 0, 9.81]}}

        def step_target(self, target):
            self.sim_time += 0.005
            self.sequence += 1
            return self.sample()

        def evaluator_truth(self):
            return {"fixture": "CPU_LIFECYCLE_ONLY"}

    monkeypatch.setattr(
        admit_policy,
        "load_manifest",
        lambda _: {"policy_sha256": "p", "manifest_sha256": "m", "policy_mode": "training"},
    )
    monkeypatch.setattr(admit_policy, "MicroDuckRuntime", Runtime)
    monkeypatch.setattr(admit_policy, "StudentPolicy", lambda _: object())
    monkeypatch.setattr(admit_policy, "infer_command", lambda *a: (None, {}))
    monkeypatch.setattr(admit_policy, "evaluate_motion", lambda *a: {"verified": True})
    out = tmp_path / "worker"
    with pytest.raises(RuntimeError, match="controlled teardown"):
        admit_policy.main(
            [
                "--asset-root",
                str(tmp_path),
                "--policy-manifest",
                "fixture",
                "--output",
                str(out),
                "--_native-worker",
            ]
        )
    receipt = student.read_json(out / "admission.json")
    assert receipt["passed"] is False
    assert receipt["lifecycle"] == "failed"


@pytest.mark.parametrize(
    "field",
    [
        "evidence_kind",
        "actor_init",
        "policy_mode",
        "saved_optimizer_steps",
        "training_source_sha256",
        "export_parity",
    ],
)
def test_training_receipt_metadata_not_just_positive_counters(copied_bundle, field):
    train, _, _, _ = copied_bundle
    receipt = student.read_json(train / "training_receipt.json")
    receipt[field] = (
        1
        if field == "saved_optimizer_steps"
        else ({} if field.endswith("sha256") or field == "export_parity" else "wrong")
    )
    student.write_json(train / "training_receipt.json", receipt)
    student.create_manifest(train, mode="training")
    with pytest.raises(ValueError, match="training receipt"):
        student.load_manifest(train / "policy_manifest.json")


@pytest.mark.parametrize("raises", [False, True])
def test_nonzero_worker_exit_invalidates_a_complete_receipt(tmp_path, monkeypatch, raises):
    from microduck_workshop.sim import admit_policy

    monkeypatch.setattr(admit_policy, "load_manifest", lambda _: {})
    out = tmp_path / "worker"

    def worker(*args, **kwargs):
        out.mkdir()
        student.write_json(out / "admission.json", {"passed": True, "lifecycle": "complete"})
        if raises:
            raise RuntimeError("controlled supervisor wait failure")
        return SimpleNamespace(returncode=3)

    monkeypatch.setattr(admit_policy.subprocess, "run", worker)
    with pytest.raises(BaseException):
        admit_policy.main(
            ["--asset-root", str(tmp_path), "--policy-manifest", "fixture", "--output", str(out)]
        )
    final = student.read_json(out / "admission.json")
    assert final["passed"] is False
    assert final["lifecycle"] == "failed"
    assert "error" in final


@pytest.mark.parametrize("exists", [False, True])
def test_zero_exit_without_complete_receipt_fails(tmp_path, monkeypatch, exists):
    from microduck_workshop.sim import admit_policy

    monkeypatch.setattr(admit_policy, "load_manifest", lambda _: {})
    monkeypatch.setattr(admit_policy, "StudentPolicy", lambda _: None)
    out = tmp_path / "worker"

    def worker(*args, **kw):
        out.mkdir()
        if exists:
            student.write_json(out / "admission.json", {"passed": False, "lifecycle": "running"})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(admit_policy.subprocess, "run", worker)
    with pytest.raises((ValueError, FileNotFoundError)):
        admit_policy.main(
            ["--asset-root", str(tmp_path), "--policy-manifest", "fixture", "--output", str(out)]
        )
